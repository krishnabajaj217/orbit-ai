"""
The planner asks the LLM to reason about *this specific request* and decide,
dynamically, what capabilities it needs. Nothing here special-cases any
particular question — the classification + plan are both LLM-generated.
"""
from app.llm import client as llm_client
from app.llm.client import LLMNotConfigured, OllamaAPIError
from app.tools.registry import registry

CLASSIFY_SYSTEM_PROMPT = """You are the planning module of Orbit Agent, an autonomous personal AI agent.
Given a user's request, decide what capabilities are needed to answer it well. Do not answer the
request yet. Respond ONLY with a JSON object with this exact shape:

{
  "complexity": "simple" | "current_info" | "personal" | "complex",
  "needs_web_search": boolean,
  "needs_personal_context": boolean,
  "needs_calculator": boolean,
  "needs_clarification": boolean,
  "clarification_question": string,   // empty string if needs_clarification is false
  "reasoning_summary": string,        // ONE short sentence, safe to show the user, e.g. "This needs current prices."
  "plan_steps": [string]              // short human-readable plan steps, e.g. ["Search current laptop prices", "Compare against budget", "Recommend best fit"]
}

Guidance:
- "simple": a general-knowledge question answerable directly, e.g. "what is 18% of 72000" (still needs_calculator=true for arithmetic) or a definitional question.
- "current_info": needs up-to-date facts (prices, news, current events, current docs) -> needs_web_search=true.
- "personal": the answer depends on things the user has previously told the agent about themselves (preferences, projects, goals, skills) -> needs_personal_context=true.
- "complex": multi-step task combining several of the above, e.g. research + compare + recommend, or a project/career plan.
- Only set needs_clarification=true if the request is genuinely impossible to do well without a specific missing fact (e.g. no budget given for a purchase recommendation, or no info about a described error). Do not ask clarifying questions for information you could reasonably infer or that isn't essential.
- Keep plan_steps short (max 6) and only include steps actually needed for this request.
"""

VERIFY_SYSTEM_PROMPT = """You are the verification module of Orbit Agent. You will be given a user's
request and the agent's draft final result. Check it for internal consistency, whether it actually
answers the request, and whether it appropriately used any sources / calculations provided. Respond
ONLY with JSON: {"passed": boolean, "notes": string, "revised_result": string}
"revised_result" should be the same as the draft if no changes are needed, or a corrected version if you
found an issue. Keep "notes" to one short sentence, safe to show the user (e.g. "Checked recommendation against stated budget.")."""


async def classify_and_plan(user_request: str) -> dict:
    try:
        result = await llm_client.structured_json(CLASSIFY_SYSTEM_PROMPT, user_request)
    except (LLMNotConfigured, OllamaAPIError):
        # Deterministic, honest fallback so the app remains usable without a key configured.
        result = {
            "complexity": "simple",
            "needs_web_search": False,
            "needs_personal_context": False,
            "needs_calculator": False,
            "needs_clarification": False,
            "clarification_question": "",
            "reasoning_summary": "The local AI service is unavailable, so planning is limited.",
            "plan_steps": ["Answer directly (LLM not configured)"],
        }
    return result


async def verify_result(user_request: str, draft_result: str) -> dict:
    try:
        prompt = f"Request: {user_request}\n\nDraft result:\n{draft_result}"
        return await llm_client.structured_json(VERIFY_SYSTEM_PROMPT, prompt)
    except (LLMNotConfigured, OllamaAPIError):
        return {"passed": True, "notes": "Verification skipped (LLM not configured).", "revised_result": draft_result}


def build_agent_system_prompt(personal_context: list[dict], sources_so_far: list[dict]) -> str:
    context_block = "\n".join(f"- ({m['type']}) {m['content']}" for m in personal_context) or "None retrieved."
    return f"""You are Orbit Agent, an autonomous personal assistant. Use the available tools when
they would materially improve your answer (current info, calculations, personal memory). Do not call
a tool you don't need. When you have enough information, respond with a final, complete, well-formatted
answer in plain text (no tool call) — this ends the task. If the request requires information you truly
cannot infer, ask a single, direct clarifying question in plain text instead of calling a tool.

Relevant personal context already retrieved for this user:
{context_block}

Available tools: {', '.join(t.name for t in registry.all())}.
Never fabricate a data point that a tool could verify — call the tool instead."""
