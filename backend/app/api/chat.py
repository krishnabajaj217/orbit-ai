from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from datetime import date

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..config import get_settings
from ..llm.ollama import (
    OllamaError,
    stream_chat,
)
from ..tools.calculator import (
    CalculatorError,
    calculate,
)
from ..tools.web_search import (
    WebSearchError,
    search,
)


# ============================================================
# MEMORY
# ============================================================

MEMORY_AVAILABLE = False
MEMORY_IMPORT_ERROR = ""

try:

    from ..rag.memory_service import (
        remember,
        search_memory,
    )

    MEMORY_AVAILABLE = True

except Exception as error:

    MEMORY_AVAILABLE = False
    MEMORY_IMPORT_ERROR = str(error)

    print("=" * 60)
    print("MEMORY IMPORT FAILED")
    print(MEMORY_IMPORT_ERROR)
    print("=" * 60)


router = APIRouter(
    prefix="/api"
)


# ============================================================
# REQUEST
# ============================================================

class ChatRequest(BaseModel):

    user_id: str = Field(
        min_length=1,
        max_length=100,
    )

    conversation_id: str = Field(
        min_length=1,
        max_length=100,
    )

    message: str = Field(
        min_length=1,
        max_length=20_000,
    )

    history: list[
        dict[str, str]
    ] = Field(
        default_factory=list,
        max_length=100,
    )


# ============================================================
# ORBIT PLANNER
# ============================================================

ORBIT_SYSTEM_PROMPT = """
You are Orbit's task router.

Return ONLY valid JSON.

Format:

{
  "action": "calculator" | "web_search" | "direct_answer",
  "reason": "short explanation",
  "expression": "calculator expression or empty string"
}

Rules:

- calculator:
  mathematical calculations only.

- web_search:
  current, latest, today's, recent, news, prices, live information,
  current events, recent developments, current AI technologies,
  current software/framework/model releases, current products,
  current companies, current people information, or requests
  requiring external sources.

- direct_answer:
  normal explanations, coding questions, DSA questions,
  programming concepts, greetings, casual conversation,
  and stable knowledge.

Never use Markdown.
Never output anything outside the JSON object.
"""


# ============================================================
# ASSISTANT
# ============================================================

ASSISTANT_SYSTEM_PROMPT = """
You are Orbit, a capable professional AI assistant.

Answer the user's actual request directly and completely.

Rules:

- Be conversational and helpful.
- Use Markdown when useful.
- Give concise answers for simple questions.
- Give detailed explanations when required.
- Use conversation context when appropriate.
- Use the provided MEMORY CONTEXT when relevant.
- Treat MEMORY CONTEXT as information about the user.
- Do not mention memory retrieval or internal processing.
- Do not claim actions that were not performed.
"""


# ============================================================
# MEMORY REQUEST DETECTION
# ============================================================

def _looks_like_memory_request(
    message: str,
) -> bool:

    text = message.strip().lower()

    phrases = [
        "remember that",
        "remember this",
        "remember my",
        "remember i",
        "remember i'm",
        "remember im",
        "don't forget that",
        "do not forget that",
        "keep in mind that",
        "save this",
        "store this",
    ]

    return any(
        phrase in text
        for phrase in phrases
    )


# ============================================================
# EXTRACT MEMORY
# ============================================================

def _extract_memory_content(
    message: str,
) -> str:

    pattern = (
        r"^\s*("
        r"remember that|"
        r"remember this|"
        r"remember my|"
        r"remember i|"
        r"remember i'm|"
        r"remember im|"
        r"don't forget that|"
        r"do not forget that|"
        r"keep in mind that|"
        r"save this|"
        r"store this"
        r")\s*"
    )

    content = re.sub(
        pattern,
        "",
        message.strip(),
        flags=re.IGNORECASE,
    ).strip()

    return (
        content
        or message.strip()
    )


# ============================================================
# SAVE MEMORY
# ============================================================

async def _save_user_memory(
    user_id: str,
    message: str,
) -> tuple[bool, str]:

    if not MEMORY_AVAILABLE:

        return (
            False,
            MEMORY_IMPORT_ERROR
            or "Memory service is unavailable.",
        )

    content = _extract_memory_content(
        message
    )

    try:

        memory = await remember(
            user_id=user_id,
            content=content,
            memory_type="general",
            importance=0.8,
        )

        print(
            "MEMORY SAVED:",
            memory.get("content"),
        )

        return True, ""

    except Exception as error:

        print(
            "MEMORY SAVE ERROR:",
            repr(error),
        )

        return False, str(error)


# ============================================================
# RETRIEVE MEMORY
# ============================================================

async def _retrieve_memory(
    user_id: str,
    message: str,
) -> str:

    if not MEMORY_AVAILABLE:
        return ""

    try:

        results = await search_memory(
            user_id=user_id,
            query=message,
            top_k=5,
        )

    except Exception as error:

        print(
            "MEMORY SEARCH ERROR:",
            repr(error),
        )

        return ""

    if not results:
        return ""

    memory_text: list[str] = []

    for item in results:

        if not isinstance(
            item,
            dict,
        ):
            continue

        content = item.get(
            "content"
        )

        if not isinstance(
            content,
            str,
        ):
            continue

        similarity = item.get(
            "similarity",
            0.0,
        )

        try:

            similarity = float(
                similarity
            )

        except (
            TypeError,
            ValueError,
        ):

            similarity = 0.0

        if similarity < 0.30:
            continue

        memory_text.append(
            f"- {content}"
        )

    if memory_text:

        print(
            "MEMORY RETRIEVED:",
            memory_text,
        )

    return "\n".join(
        memory_text
    )


# ============================================================
# CALCULATOR
# ============================================================

def _is_bare_calculation(
    message: str,
) -> bool:

    text = message.strip()

    if not text:
        return False

    if not re.search(
        r"\d",
        text,
    ):
        return False

    return bool(
        re.fullmatch(
            r"[0-9\s+\-*/().%^]+",
            text,
        )
    )


# ============================================================
# WEB SEARCH
# ============================================================

def _needs_web_search(
    message: str,
) -> bool:

    text = message.strip().lower()

    if not text:
        return False

    web_phrases = [
        "latest",
        "current",
        "currently",
        "today",
        "today's",
        "tonight",
        "recent",
        "recently",
        "newest",
        "up-to-date",
        "up to date",
        "this week",
        "this month",
        "this year",
        "breaking news",
        "news",
        "live",
        "real-time",
        "realtime",
        "right now",
        "as of today",
        "what is happening",
        "what's happening",
    ]

    if any(
        phrase in text
        for phrase in web_phrases
    ):
        return True

    external_phrases = [
        "search the web",
        "search online",
        "look it up",
        "look this up",
        "find online",
        "browse the web",
        "on the internet",
        "from the internet",
        "online sources",
        "web sources",
        "according to recent sources",
    ]

    if any(
        phrase in text
        for phrase in external_phrases
    ):
        return True

    dynamic_categories = [
        "weather",
        "stock price",
        "stock prices",
        "share price",
        "bitcoin price",
        "crypto price",
        "cryptocurrency price",
        "exchange rate",
        "flight status",
        "movie timings",
        "movie showtimes",
        "restaurant availability",
        "sports score",
        "live score",
        "election results",
        "market price",
    ]

    return any(
        phrase in text
        for phrase in dynamic_categories
    )


# ============================================================
# SSE
# ============================================================

def _event(
    event_type: str,
    data: object,
) -> str:

    if event_type == "token":

        payload = {
            "type": "content",
            "content": str(data),
        }

    elif event_type == "agent":

        payload = {
            "type": "agent",
            **data,
        }

    elif event_type == "source":

        payload = {
            "type": "source",
            **data,
        }

    elif event_type == "status":

        payload = {
            "type": "status",
            "status": data,
        }

    elif event_type == "error":

        payload = {
            "type": "error",
            "message": str(data),
        }

    elif event_type == "done":

        payload = {
            "type": "done",
        }

    else:

        payload = {
            "type": event_type,
        }

    return (
        f"data: {json.dumps(payload)}\n\n"
    )


# ============================================================
# DECIDE ACTION
# ============================================================

async def _decide_action(
    message: str,
    history: list[dict[str, str]],
) -> dict[str, str]:

    if _is_bare_calculation(
        message
    ):

        return {
            "action": "calculator",
            "reason": (
                "The request is a mathematical calculation."
            ),
            "expression": message.strip(),
        }

    if _needs_web_search(
        message
    ):

        return {
            "action": "web_search",
            "reason": (
                "The request requires current or external information."
            ),
            "expression": "",
        }

    decision_messages = [
        {
            "role": "system",
            "content": ORBIT_SYSTEM_PROMPT,
        },
        *history[-10:],
        {
            "role": "user",
            "content": message,
        },
    ]

    response = ""

    async for chunk in stream_chat(
        decision_messages
    ):

        response += chunk

    response = response.strip()

    try:

        decision = json.loads(
            response
        )

        action = str(
            decision.get(
                "action",
                "direct_answer",
            )
        )

        reason = str(
            decision.get(
                "reason",
                "",
            )
        )

        expression = str(
            decision.get(
                "expression",
                "",
            )
        )

        if action not in {
            "calculator",
            "web_search",
            "direct_answer",
        }:

            action = "direct_answer"

        return {
            "action": action,
            "reason": reason,
            "expression": expression,
        }

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):

        return {
            "action": "direct_answer",
            "reason": (
                "The request can be answered directly."
            ),
            "expression": "",
        }


# ============================================================
# DIRECT ANSWER
# ============================================================

async def _direct_answer(
    message: str,
    history: list[dict[str, str]],
    memory_context: str = "",
) -> AsyncIterator[str]:

    system_prompt = (
        ASSISTANT_SYSTEM_PROMPT
    )

    if memory_context:

        system_prompt += (
            "\n\nMEMORY CONTEXT:\n"
            f"{memory_context}\n\n"
            "Use this information when it is relevant "
            "to the user's current request. "
            "Do not mention that it came from memory."
        )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        *history[-40:],
        {
            "role": "user",
            "content": message,
        },
    ]

    async for chunk in stream_chat(
        messages
    ):

        yield chunk


# ============================================================
# RESPONSE STREAM
# ============================================================

async def _response_stream(
    request: ChatRequest,
) -> AsyncIterator[str]:

    message = request.message.strip()

    # ========================================================
    # SAVE MEMORY
    # ========================================================

    if _looks_like_memory_request(
        message
    ):

        yield _event(
            "agent",
            {
                "step": "memory",
                "label": "Saving memory",
                "status": "started",
            },
        )

        saved, error_message = (
            await _save_user_memory(
                request.user_id,
                message,
            )
        )

        if saved:

            yield _event(
                "agent",
                {
                    "step": "memory",
                    "label": "Memory saved",
                    "status": "completed",
                    "result": "Memory stored successfully.",
                },
            )

            yield _event(
                "token",
                "Got it — I'll remember that.",
            )

            yield _event(
                "done",
                {},
            )

            return

        yield _event(
            "agent",
            {
                "step": "memory",
                "label": "Memory unavailable",
                "status": "failed",
                "reason": error_message,
            },
        )

    # ========================================================
    # RETRIEVE MEMORY
    # ========================================================

    memory_context = (
        await _retrieve_memory(
            request.user_id,
            message,
        )
    )

    # ========================================================
    # DECIDE
    # ========================================================

    try:

        decision = await _decide_action(
            message,
            request.history,
        )

    except OllamaError as error:

        if _needs_web_search(
            message
        ):

            decision = {
                "action": "web_search",
                "reason": (
                    "The request requires current or external information."
                ),
                "expression": "",
            }

        else:

            yield _event(
                "error",
                str(error),
            )

            yield _event(
                "done",
                {},
            )

            return

    action = decision[
        "action"
    ]

    reason = decision[
        "reason"
    ]

    expression = decision[
        "expression"
    ]

    # ========================================================
    # WEB SEARCH
    # ========================================================

    if action == "web_search":

        yield _event(
            "agent",
            {
                "step": "request_received",
                "label": "Request received",
                "status": "completed",
            },
        )

        yield _event(
            "agent",
            {
                "step": "planning",
                "label": "Agent planning",
                "status": "completed",
                "reason": reason,
                "action": "web_search",
            },
        )

        settings = get_settings()

        if not settings.tavily_api_key:

            yield _event(
                "agent",
                {
                    "step": "web_search",
                    "label": "Web search unavailable",
                    "status": "failed",
                    "reason": "TAVILY_API_KEY is missing.",
                },
            )

            yield _event(
                "error",
                (
                    "Web search isn't configured yet. "
                    "Add TAVILY_API_KEY to backend/.env."
                ),
            )

            yield _event(
                "done",
                {},
            )

            return

        yield _event(
            "agent",
            {
                "step": "web_search",
                "label": "Searching the web",
                "status": "started",
            },
        )

        yield _event(
            "status",
            "searching",
        )

        try:

            results = await search(
                message
            )

        except WebSearchError as error:

            yield _event(
                "agent",
                {
                    "step": "web_search",
                    "label": "Web search failed",
                    "status": "failed",
                    "reason": str(error),
                },
            )

            yield _event(
                "error",
                str(error),
            )

            yield _event(
                "done",
                {},
            )

            return

        for result in results:

            yield _event(
                "source",
                result,
            )

        yield _event(
            "agent",
            {
                "step": "web_search",
                "label": f"Found {len(results)} sources",
                "status": "completed",
                "count": len(results),
            },
        )

        clean_sources = "\n\n".join(
            (
                f"{index}. {result['title']}\n"
                f"URL: {result['url']}\n"
                f"Summary: {result['snippet']}"
            )
            for index, result in enumerate(
                results,
                start=1,
            )
        )

        memory_section = ""

        if memory_context:

            memory_section = (
                "\n\nRELEVANT USER MEMORY:\n"
                f"{memory_context}"
            )

        summary_messages = [
            {
                "role": "system",
                "content": (
                    f"Today is {date.today().isoformat()}.\n\n"
                    "You are Orbit.\n"
                    "Answer the user's request using ONLY "
                    "the web sources provided below for "
                    "current/external claims.\n"
                    "Do not invent facts.\n"
                    "Use relevant user memory when appropriate.\n"
                    "Use Markdown when helpful.\n\n"
                    f"WEB SOURCES:\n{clean_sources}"
                    f"{memory_section}"
                ),
            },
            {
                "role": "user",
                "content": message,
            },
        ]

        yield _event(
            "agent",
            {
                "step": "analysis",
                "label": "Analyzing sources",
                "status": "started",
            },
        )

        yield _event(
            "agent",
            {
                "step": "analysis",
                "label": "Sources analyzed",
                "status": "completed",
            },
        )

        yield _event(
            "agent",
            {
                "step": "writing",
                "label": "Writing answer",
                "status": "started",
            },
        )

        yield _event(
            "status",
            "writing",
        )

        try:

            async for chunk in stream_chat(
                summary_messages
            ):

                yield _event(
                    "token",
                    chunk,
                )

        except OllamaError as error:

            yield _event(
                "agent",
                {
                    "step": "writing",
                    "label": "Answer generation failed",
                    "status": "failed",
                    "reason": str(error),
                },
            )

            yield _event(
                "error",
                str(error),
            )

            yield _event(
                "done",
                {},
            )

            return

        yield _event(
            "agent",
            {
                "step": "writing",
                "label": "Answer written",
                "status": "completed",
            },
        )

        yield _event(
            "agent",
            {
                "step": "completed",
                "label": "Task completed",
                "status": "completed",
            },
        )

        yield _event(
            "done",
            {},
        )

        return

    # ========================================================
    # CALCULATOR
    # ========================================================

    if action == "calculator":

        try:

            if not expression:
                expression = message

            result = calculate(
                expression.replace(
                    "^",
                    "**",
                )
            )

            display_expression = (
                expression.replace(
                    "*",
                    " × ",
                )
            )

            yield _event(
                "token",
                f"{display_expression} = {result}",
            )

            yield _event(
                "done",
                {},
            )

            return

        except CalculatorError as error:

            yield _event(
                "error",
                str(error),
            )

            yield _event(
                "done",
                {},
            )

            return

    # ========================================================
    # DIRECT ANSWER
    # ========================================================

    try:

        async for chunk in _direct_answer(
            message,
            request.history,
            memory_context,
        ):

            yield _event(
                "token",
                chunk,
            )

    except OllamaError as error:

        yield _event(
            "error",
            str(error),
        )

        yield _event(
            "done",
            {},
        )

        return

    yield _event(
        "done",
        {},
    )


# ============================================================
# API
# ============================================================

@router.post(
    "/chat"
)
async def chat(
    request: ChatRequest,
) -> StreamingResponse:

    return StreamingResponse(
        _response_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )