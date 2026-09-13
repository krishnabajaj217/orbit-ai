import asyncio
from enum import Enum


class RunStatus(str, Enum):
    IDLE = "IDLE"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    RETRIEVING = "RETRIEVING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepType(str, Enum):
    UNDERSTAND = "understand"
    PLAN = "plan"
    RETRIEVE = "retrieve"
    DECIDE = "decide"
    ACT = "act"
    HOLD = "hold"
    RESUME = "resume"
    VERIFY = "verify"
    COMPLETE = "complete"
    FAIL = "fail"


class EventBus:
    """In-process pub/sub so the SSE endpoint can stream live step updates.

    NOTE: this is a single-process implementation, adequate for local dev /
    a single backend instance. For a multi-instance production deployment,
    swap this for a Redis pub/sub channel keyed by run_id (the interface
    below would not need to change).
    """

    def __init__(self):
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(run_id, []).append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        if run_id in self._queues and q in self._queues[run_id]:
            self._queues[run_id].remove(q)

    async def publish(self, run_id: str, event: dict) -> None:
        for q in self._queues.get(run_id, []):
            await q.put(event)


event_bus = EventBus()
