import inspect
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.registry import PermissionLevel, ToolResult, registry


async def execute_tool(db: AsyncSession, user_id: str, tool_name: str, arguments: dict) -> ToolResult:
    tool = registry.get(tool_name)
    if not tool:
        return ToolResult(ok=False, error=f"Unknown tool: {tool_name}")

    try:
        sig = inspect.signature(tool.execute)
        kwargs = dict(arguments)
        if "db" in sig.parameters:
            kwargs["db"] = db
        if "user_id" in sig.parameters:
            kwargs["user_id"] = user_id
        return await tool.execute(**kwargs)
    except TypeError as exc:
        return ToolResult(ok=False, error=f"Invalid arguments for tool '{tool_name}': {exc}")
    except Exception as exc:  # noqa: BLE001 - tool failures must never crash the agent loop
        return ToolResult(ok=False, error=f"Tool '{tool_name}' failed: {exc}")


def requires_confirmation(tool_name: str) -> bool:
    tool = registry.get(tool_name)
    return bool(tool and tool.permission in (PermissionLevel.CONFIRMATION_REQUIRED, PermissionLevel.DANGEROUS))


def is_dangerous(tool_name: str) -> bool:
    tool = registry.get(tool_name)
    return bool(tool and tool.permission == PermissionLevel.DANGEROUS)


def safe_tool_call_summary(tool_name: str, arguments: dict) -> str:
    """Human-readable, non-technical summary of a tool call for the activity timeline."""
    summaries = {
        "web_search": lambda a: f"Searching current sources for \u201c{a.get('query', '')}\u201d",
        "personal_rag_search": lambda a: "Retrieving relevant memory from your personal knowledge base",
        "calculator": lambda a: f"Running calculation: {a.get('expression', '')}",
        "save_memory": lambda a: "Preparing to save a new memory to your knowledge base",
        "retrieve_memory": lambda a: "Retrieving stored memories",
        "create_task": lambda a: f"Preparing to create task: \u201c{a.get('title', '')}\u201d",
        "update_task": lambda a: "Updating a task",
        "get_current_time": lambda a: "Checking current date/time",
    }
    fn = summaries.get(tool_name)
    if fn:
        try:
            return fn(arguments)
        except Exception:  # noqa: BLE001
            pass
    return f"Running tool: {tool_name}"


def safe_args_preview(arguments: dict) -> dict:
    """Never leak internal-only fields (db sessions etc. can't get here anyway) —
    kept as a hook for future PII scrubbing before showing args in the UI."""
    return json.loads(json.dumps(arguments, default=str))
