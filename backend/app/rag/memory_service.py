from __future__ import annotations

import re
from typing import Any

from .memory_store import (
    add_memory,
    clear_memories,
    delete_memory,
    get_all_memories,
    load_memories,
)


# ============================================================
# TOKEN NORMALIZATION
# ============================================================

def _normalize(
    text: str,
) -> set[str]:

    words = re.findall(
        r"[a-zA-Z0-9_+#.-]+",
        text.lower(),
    )

    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "am",
        "are",
        "was",
        "were",
        "i",
        "me",
        "my",
        "you",
        "your",
        "that",
        "this",
        "for",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "with",
        "do",
        "did",
        "does",
        "what",
        "which",
        "how",
        "why",
        "can",
        "could",
        "would",
        "should",
        "tell",
        "about",
    }

    return {
        word
        for word in words
        if word not in stop_words
    }


# ============================================================
# SIMILARITY
# ============================================================

def _similarity(
    query: str,
    content: str,
) -> float:

    query_words = _normalize(
        query
    )

    memory_words = _normalize(
        content
    )

    if not query_words or not memory_words:
        return 0.0

    intersection = (
        query_words
        & memory_words
    )

    if not intersection:
        return 0.0

    union = (
        query_words
        | memory_words
    )

    return (
        len(intersection)
        / len(union)
    )


# ============================================================
# REMEMBER
# ============================================================

async def remember(
    user_id: str,
    content: str,
    memory_type: str = "general",
    importance: float = 0.8,
) -> dict[str, Any]:

    return add_memory(
        user_id=user_id,
        memory_type=memory_type,
        content=content,
        importance=importance,
    )


# ============================================================
# SEARCH MEMORY
# ============================================================

async def search_memory(
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:

    memories = load_memories(
        user_id
    )

    if not memories:
        return []

    scored: list[
        dict[str, Any]
    ] = []

    for memory in memories:

        if not isinstance(
            memory,
            dict,
        ):
            continue

        content = memory.get(
            "content"
        )

        if not isinstance(
            content,
            str,
        ):
            continue

        similarity = _similarity(
            query,
            content,
        )

        try:

            importance = float(
                memory.get(
                    "importance",
                    0.5,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            importance = 0.5

        importance = max(
            0.0,
            min(
                1.0,
                importance,
            ),
        )

        # Similarity is the main ranking factor.
        score = (
            similarity * 0.8
            + importance * 0.2
        )

        result = dict(
            memory
        )

        result["similarity"] = score

        scored.append(
            result
        )

    scored.sort(
        key=lambda item: float(
            item.get(
                "similarity",
                0.0,
            )
        ),
        reverse=True,
    )

    return scored[:top_k]


# ============================================================
# DELETE MEMORY
# ============================================================

async def remove_memory(
    user_id: str,
    memory_id: str,
) -> bool:

    return delete_memory(
        user_id=user_id,
        memory_id=memory_id,
    )


# ============================================================
# CLEAR MEMORY
# ============================================================

async def clear_user_memory(
    user_id: str,
) -> None:

    clear_memories(
        user_id=user_id
    )


# ============================================================
# GET MEMORY
# ============================================================

async def get_user_memories(
    user_id: str,
) -> list[dict]:

    return get_all_memories(
        user_id
    )