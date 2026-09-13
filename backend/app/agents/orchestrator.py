import json
import re
from datetime import datetime

from sqlalchemy import select

from app.agents.executor import (
    execute_tool,
    requires_confirmation,
    safe_tool_call_summary,
)
from app.agents.planner import (
    build_agent_system_prompt,
    classify_and_plan,
    verify_result,
)
from app.agents.state import RunStatus, StepType, event_bus
from app.database.session import AsyncSessionLocal
from app.llm import client as llm_client
from app.llm.client import LLMNotConfigured, OllamaAPIError
from app.models.models import AgentRun, AgentStep
from app.rag.retriever import retrieve_relevant_memories
from app.tools.registry import registry


MAX_ITERATIONS = 8


# ============================================================
# DATABASE HELPERS
# ============================================================

async def _get_run(db, run_id: str) -> AgentRun:
    result = await db.execute(
        select(AgentRun).where(AgentRun.id == run_id)
    )

    run = result.scalar_one_or_none()

    if not run:
        raise ValueError(f"AgentRun {run_id} not found")

    return run


async def _set_status(
    db,
    run: AgentRun,
    status: RunStatus,
    current_step: str = "",
) -> None:

    run.status = status.value

    if current_step:
        run.current_step = current_step

    await db.commit()

    await event_bus.publish(
        run.id,
        {
            "event": "status",
            "status": run.status,
        },
    )


async def _add_step(
    db,
    run: AgentRun,
    step_type: StepType,
    title: str,
    tool_name: str = "",
    status: str = "running",
) -> AgentStep:

    step = AgentStep(
        run_id=run.id,
        step_type=step_type.value,
        title=title,
        tool_name=tool_name,
        status=status,
    )

    db.add(step)

    await db.commit()
    await db.refresh(step)

    await event_bus.publish(
        run.id,
        {
            "event": "step",
            "step": _step_dict(step),
        },
    )

    return step


async def _complete_step(
    db,
    run: AgentRun,
    step: AgentStep,
    safe_summary: str,
    status: str = "completed",
    result_metadata: dict | None = None,
) -> None:

    step.status = status
    step.safe_summary = safe_summary
    step.result_metadata = result_metadata or {}
    step.completed_at = datetime.utcnow()

    await db.commit()

    await event_bus.publish(
        run.id,
        {
            "event": "step",
            "step": _step_dict(step),
        },
    )


def _step_dict(step: AgentStep) -> dict:
    return {
        "id": step.id,
        "step_type": step.step_type,
        "status": step.status,
        "title": step.title,
        "safe_summary": step.safe_summary,
        "tool_name": step.tool_name,
        "started_at": (
            step.started_at.isoformat()
            if step.started_at
            else None
        ),
        "completed_at": (
            step.completed_at.isoformat()
            if step.completed_at
            else None
        ),
    }


# ============================================================
# FAST LOCAL OPERATIONS
# ============================================================

def _simple_percentage(request: str) -> float | None:
    """
    Detect very simple percentage calculations locally.

    Examples:

        What is 18% of 72,000?
        18% of 72000
        calculate 25% of 1000

    Returns the result without calling the LLM.
    """

    text = request.lower().replace(",", "").strip()

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)",
        text,
    )

    if not match:
        return None

    percentage = float(match.group(1))
    number = float(match.group(2))

    return (percentage / 100.0) * number


def _simple_arithmetic(request: str) -> float | None:
    """Evaluate a bare arithmetic expression without involving the LLM."""
    expression = request.lower().replace(",", "").strip()
    expression = re.sub(r"^(what is|calculate|compute)\s+", "", expression)
    if not re.fullmatch(r"[\d\s.+*/()%^-]+", expression):
        return None
    try:
        tree = __import__("ast").parse(expression, mode="eval")
        allowed = {__import__("ast").Expression, __import__("ast").Constant, __import__("ast").BinOp,
                   __import__("ast").UnaryOp, __import__("ast").Add, __import__("ast").Sub,
                   __import__("ast").Mult, __import__("ast").Div, __import__("ast").Pow,
                   __import__("ast").Mod, __import__("ast").USub, __import__("ast").UAdd}
        if any(type(node) not in allowed for node in __import__("ast").walk(tree)):
            return None
        return float(eval(compile(tree, "<calculator>", "eval"), {"__builtins__": {}}, {}))
    except (ArithmeticError, SyntaxError, ValueError, TypeError, OverflowError):
        return None


async def _complete_simple_calculation(
    db,
    run: AgentRun,
    result: float,
) -> None:
    """
    Complete a simple calculation immediately.

    No LLM call.
    No planner.
    No verification API call.
    """

    await _set_status(
        db,
        run,
        RunStatus.EXECUTING,
        "Calculating",
    )

    step = await _add_step(
        db,
        run,
        StepType.ACT,
        "Calculating",
        tool_name="calculator",
    )

    if result.is_integer():
        answer = f"{int(result):,}"
    else:
        answer = f"{result:,.2f}"

    await _complete_step(
        db,
        run,
        step,
        f"Calculated locally: {answer}",
        result_metadata={
            "result": result,
            "local": True,
        },
    )

    run.final_result = answer

    await db.commit()

    await _set_status(
        db,
        run,
        RunStatus.COMPLETED,
        "Completed",
    )

    complete_step = await _add_step(
        db,
        run,
        StepType.COMPLETE,
        "Task completed",
    )

    await _complete_step(
        db,
        run,
        complete_step,
        "Result delivered.",
    )


# ============================================================
# MAIN AGENT ENTRY POINT
# ============================================================

async def run_agent(run_id: str) -> None:
    """
    Entry point invoked as a background task after an AgentRun
    is created.

    Fast/simple requests are handled locally first.
    Everything else goes through the normal agent pipeline.
    """

    async with AsyncSessionLocal() as db:

        run = await _get_run(db, run_id)

        try:

            # ------------------------------------------------
            # FAST PATH
            # ------------------------------------------------

            calculation = _simple_percentage(run.original_request)
            if calculation is None:
                calculation = _simple_arithmetic(run.original_request)

            if calculation is not None:

                await _complete_simple_calculation(
                    db,
                    run,
                    calculation,
                )

                return

            # ------------------------------------------------
            # NORMAL AGENT
            # ------------------------------------------------

            await _run_understanding_phase(
                db,
                run,
            )

        except Exception as exc:
            await _fail_run(
                db,
                run,
                str(exc),
            )


# ============================================================
# UNDERSTANDING / PLANNING
# ============================================================

async def _run_understanding_phase(
    db,
    run: AgentRun,
) -> None:

    await _set_status(
        db,
        run,
        RunStatus.UNDERSTANDING,
        "Understanding request",
    )

    step = await _add_step(
        db,
        run,
        StepType.UNDERSTAND,
        "Understanding request",
    )

    classification = await classify_and_plan(
        run.original_request
    )

    await _complete_step(
        db,
        run,
        step,
        classification.get(
            "reasoning_summary",
            "Request understood.",
        ),
    )

    # --------------------------------------------------------
    # CLARIFICATION
    # --------------------------------------------------------

    if classification.get("needs_clarification"):

        question = (
            classification.get("clarification_question")
            or "Could you provide a bit more detail?"
        )

        run.pending_action = {
            "type": "clarification",
            "question": question,
        }

        hold = await _add_step(
            db,
            run,
            StepType.HOLD,
            "Waiting for your input",
        )

        await _complete_step(
            db,
            run,
            hold,
            question,
            status="waiting",
        )

        await _set_status(
            db,
            run,
            RunStatus.WAITING_FOR_USER,
            "Waiting for clarification",
        )

        return

    # --------------------------------------------------------
    # PERSONAL CONTEXT
    # --------------------------------------------------------

    personal_context: list[dict] = []

    needs_personal = (
        classification.get("needs_personal_context")
        or classification.get("complexity")
        in ("personal", "complex")
    )

    if needs_personal:

        await _set_status(
            db,
            run,
            RunStatus.RETRIEVING,
            "Retrieving personal context",
        )

        step = await _add_step(
            db,
            run,
            StepType.RETRIEVE,
            "Retrieving personal context",
        )

        personal_context = await retrieve_relevant_memories(
            db,
            run.user_id,
            run.original_request,
        )

        summary = (
            f"Found {len(personal_context)} relevant memory item(s)."
            if personal_context
            else "No relevant personal context found."
        )

        await _complete_step(
            db,
            run,
            step,
            summary,
            result_metadata={
                "count": len(personal_context),
            },
        )

    # --------------------------------------------------------
    # PLAN
    # --------------------------------------------------------

    plan_steps = classification.get(
        "plan_steps"
    ) or []

    if (
        classification.get("complexity") == "complex"
        or len(plan_steps) > 1
    ):

        await _set_status(
            db,
            run,
            RunStatus.PLANNING,
            "Creating execution plan",
        )

        step = await _add_step(
            db,
            run,
            StepType.PLAN,
            "Creating execution plan",
        )

        run.plan = {
            "steps": plan_steps,
        }

        plan_summary = (
            "Plan: " + "; ".join(plan_steps)
            if plan_steps
            else "Plan created."
        )

        await _complete_step(
            db,
            run,
            step,
            plan_summary,
        )

    # --------------------------------------------------------
    # BUILD AGENT CONTEXT
    # --------------------------------------------------------

    system_prompt = build_agent_system_prompt(
        personal_context,
        run.sources,
    )

    run.messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": run.original_request,
        },
    ]

    await db.commit()

    # --------------------------------------------------------
    # AGENT LOOP
    # --------------------------------------------------------

    await _agentic_loop(
        db,
        run,
    )


# ============================================================
# AGENTIC LOOP
# ============================================================

async def _agentic_loop(
    db,
    run: AgentRun,
) -> None:

    await _set_status(
        db,
        run,
        RunStatus.EXECUTING,
        "Executing",
    )

    tools_schema = registry.openai_schemas()

    draft: str | None = None

    for _ in range(MAX_ITERATIONS):

        try:

            message = await llm_client.chat(
                run.messages,
                tools=tools_schema,
            )

        except LLMNotConfigured as exc:

            await _fail_run(
                db,
                run,
                str(exc),
            )

            return

        except OllamaAPIError as exc:

            await _fail_run(
                db,
                run,
                str(exc),
            )

            return

        tool_calls = getattr(
            message,
            "tool_calls",
            None,
        )

        # ----------------------------------------------------
        # TOOL CALL
        # ----------------------------------------------------

        if tool_calls:

            run.messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            paused = await _handle_tool_calls(
                db,
                run,
                tool_calls,
            )

            await db.commit()

            if paused:
                return

            continue

        # ----------------------------------------------------
        # FINAL ANSWER
        # ----------------------------------------------------

        draft = (
            message.content
            or "I don't have a response for that."
        )

        break

    else:

        draft = (
            draft
            or
            "I reached the maximum number of reasoning "
            "steps for this task. Here is my best result "
            "so far."
        )

    await _finalize_run(
        db,
        run,
        draft,
    )


# ============================================================
# TOOL EXECUTION
# ============================================================

async def _handle_tool_calls(
    db,
    run: AgentRun,
    tool_calls,
) -> bool:
    """
    Execute tool calls in order.

    Returns True if execution paused because
    user confirmation is required.
    """

    for tc in tool_calls:

        name = tc.function.name

        try:

            args = json.loads(
                tc.function.arguments or "{}"
            )

        except json.JSONDecodeError:

            args = {}

        # ----------------------------------------------------
        # CONFIRMATION REQUIRED
        # ----------------------------------------------------

        if requires_confirmation(name):

            decide_step = await _add_step(
                db,
                run,
                StepType.DECIDE,
                f"Preparing to use tool: {name}",
                tool_name=name,
            )

            summary = safe_tool_call_summary(
                name,
                args,
            )

            await _complete_step(
                db,
                run,
                decide_step,
                summary,
            )

            hold_step = await _add_step(
                db,
                run,
                StepType.HOLD,
                "Waiting for your approval",
                tool_name=name,
            )

            await _complete_step(
                db,
                run,
                hold_step,
                summary,
                status="waiting",
            )

            run.pending_action = {
                "type": "tool_confirmation",
                "tool_name": name,
                "arguments": args,
                "tool_call_id": tc.id,
            }

            await _set_status(
                db,
                run,
                RunStatus.WAITING_FOR_USER,
                f"Waiting for approval: {name}",
            )

            return True

        # ----------------------------------------------------
        # EXECUTE SAFE TOOL
        # ----------------------------------------------------

        step = await _add_step(
            db,
            run,
            StepType.ACT,
            safe_tool_call_summary(
                name,
                args,
            ),
            tool_name=name,
        )

        result = await execute_tool(
            db,
            run.user_id,
            name,
            args,
        )

        status = (
            "completed"
            if result.ok
            else "failed"
        )

        summary = (
            safe_tool_call_summary(name, args)
            if result.ok
            else f"{name} failed: {result.error}"
        )

        await _complete_step(
            db,
            run,
            step,
            summary,
            status=status,
            result_metadata=(
                result.data
                if result.ok
                else {"error": result.error}
            ),
        )

        # ----------------------------------------------------
        # SAVE WEB SOURCES
        # ----------------------------------------------------

        if (
            name == "web_search"
            and result.ok
        ):

            new_sources = [
                {
                    "title": r["title"],
                    "url": r["url"],
                }
                for r in result.data.get(
                    "results",
                    [],
                )
            ]

            run.sources = (
                (run.sources or [])
                + new_sources
            )

        # ----------------------------------------------------
        # SEND TOOL RESULT BACK TO LLM
        # ----------------------------------------------------

        tool_content = json.dumps(
            result.data
            if result.ok
            else {
                "error": result.error
            }
        )

        run.messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_content,
            }
        )

    return False


# ============================================================
# RESUME
# ============================================================

async def resume_run(
    run_id: str,
    approved: bool | None = None,
    user_input: str | None = None,
) -> None:

    async with AsyncSessionLocal() as db:

        run = await _get_run(
            db,
            run_id,
        )

        if (
            run.status
            != RunStatus.WAITING_FOR_USER.value
        ):
            raise ValueError(
                "This task is not currently waiting for input."
            )

        pending = run.pending_action or {}

        try:

            # ------------------------------------------------
            # CLARIFICATION
            # ------------------------------------------------

            if pending.get("type") == "clarification":

                run.messages = (
                    run.messages or []
                ) + [
                    {
                        "role": "user",
                        "content": user_input or "",
                    }
                ]

                step = await _add_step(
                    db,
                    run,
                    StepType.RESUME,
                    "Resumed with your answer",
                )

                await _complete_step(
                    db,
                    run,
                    step,
                    "Continuing with the information you provided.",
                )

                run.pending_action = {}

                await db.commit()

                await _agentic_loop(
                    db,
                    run,
                )

            # ------------------------------------------------
            # TOOL CONFIRMATION
            # ------------------------------------------------

            elif pending.get(
                "type"
            ) == "tool_confirmation":

                name = pending["tool_name"]
                args = pending["arguments"]
                tc_id = pending["tool_call_id"]

                if approved:

                    step = await _add_step(
                        db,
                        run,
                        StepType.ACT,
                        safe_tool_call_summary(
                            name,
                            args,
                        ),
                        tool_name=name,
                    )

                    result = await execute_tool(
                        db,
                        run.user_id,
                        name,
                        args,
                    )

                    status = (
                        "completed"
                        if result.ok
                        else "failed"
                    )

                    await _complete_step(
                        db,
                        run,
                        step,
                        (
                            safe_tool_call_summary(
                                name,
                                args,
                            )
                            if result.ok
                            else
                            f"{name} failed: {result.error}"
                        ),
                        status=status,
                        result_metadata=(
                            result.data
                            if result.ok
                            else {"error": result.error}
                        ),
                    )

                    tool_content = json.dumps(
                        result.data
                        if result.ok
                        else {
                            "error": result.error
                        }
                    )

                else:

                    step = await _add_step(
                        db,
                        run,
                        StepType.ACT,
                        f"Action cancelled: {name}",
                        tool_name=name,
                    )

                    await _complete_step(
                        db,
                        run,
                        step,
                        "You declined this action.",
                        status="cancelled",
                    )

                    tool_content = json.dumps(
                        {
                            "cancelled": True,
                            "note": "The user declined this action.",
                        }
                    )

                run.messages = (
                    run.messages or []
                ) + [
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": tool_content,
                    }
                ]

                run.pending_action = {}

                await db.commit()

                await _agentic_loop(
                    db,
                    run,
                )

            else:

                raise ValueError(
                    "Unknown pending action type."
                )

        except Exception as exc:

            await _fail_run(
                db,
                run,
                str(exc),
            )


# ============================================================
# CANCEL
# ============================================================

async def cancel_run(
    run_id: str,
) -> None:

    async with AsyncSessionLocal() as db:

        run = await _get_run(
            db,
            run_id,
        )

        run.status = RunStatus.CANCELLED.value
        run.pending_action = {}

        await db.commit()

        step = await _add_step(
            db,
            run,
            StepType.FAIL,
            "Task cancelled",
        )

        await _complete_step(
            db,
            run,
            step,
            "Cancelled by user.",
            status="cancelled",
        )

        await event_bus.publish(
            run_id,
            {
                "event": "status",
                "status": run.status,
            },
        )


# ============================================================
# FINAL RESULT
# ============================================================

async def _finalize_run(
    db,
    run: AgentRun,
    draft: str,
) -> None:

    await _set_status(
        db,
        run,
        RunStatus.VERIFYING,
        "Verifying result",
    )

    step = await _add_step(
        db,
        run,
        StepType.VERIFY,
        "Verifying result",
    )

    verification = await verify_result(
        run.original_request,
        draft,
    )

    final_text = (
        verification.get("revised_result")
        or draft
    )

    await _complete_step(
        db,
        run,
        step,
        verification.get(
            "notes",
            "Result verified.",
        ),
    )

    run.final_result = final_text

    await db.commit()

    await _set_status(
        db,
        run,
        RunStatus.COMPLETED,
        "Completed",
    )

    complete_step = await _add_step(
        db,
        run,
        StepType.COMPLETE,
        "Task completed",
    )

    await _complete_step(
        db,
        run,
        complete_step,
        "Result delivered.",
    )


# ============================================================
# FAILURE
# ============================================================

async def _fail_run(
    db,
    run: AgentRun,
    error: str,
) -> None:

    run.status = RunStatus.FAILED.value
    run.error = error

    await db.commit()

    step = await _add_step(
        db,
        run,
        StepType.FAIL,
        "Task failed",
    )

    await _complete_step(
        db,
        run,
        step,
        "Something went wrong. You can retry this task.",
        status="failed",
        result_metadata={
            "error": error,
        },
    )

    await event_bus.publish(
        run.id,
        {
            "event": "status",
            "status": run.status,
        },
    )