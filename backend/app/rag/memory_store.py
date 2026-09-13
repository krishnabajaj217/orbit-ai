from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


# ============================================================
# PATHS
# ============================================================

# backend/
#   app/
#     rag/
#       memory_store.py
#
# parents[0] = rag
# parents[1] = app
# parents[2] = backend

BASE_DIR = Path(__file__).resolve().parents[2]

MEMORY_DIR = BASE_DIR / "data" / "memories"

MEMORY_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# MEMORY FILE
# ============================================================

def _memory_file(user_id: str) -> Path:
    """
    Return the JSON memory file for one user.
    """

    safe_user_id = "".join(
        character
        for character in str(user_id)
        if character.isalnum()
        or character in ("-", "_", ".")
    )

    if not safe_user_id:
        raise ValueError("Invalid user ID.")

    return MEMORY_DIR / f"{safe_user_id}.json"


# ============================================================
# LOAD
# ============================================================

def load_memories(
    user_id: str,
) -> list[dict]:

    file_path = _memory_file(user_id)

    if not file_path.exists():
        return []

    try:

        with file_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if not isinstance(data, list):
            return []

        return [
            item
            for item in data
            if isinstance(item, dict)
        ]

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return []


# ============================================================
# SAVE
# ============================================================

def save_memories(
    user_id: str,
    memories: list[dict],
) -> None:

    file_path = _memory_file(user_id)

    temporary_file = file_path.with_suffix(
        ".tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            memories,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary_file.replace(
        file_path
    )


# ============================================================
# ADD MEMORY
# ============================================================

def add_memory(
    user_id: str,
    memory_type: str,
    content: str,
    importance: float = 0.5,
    embedding: list[float] | None = None,
) -> dict:

    content = content.strip()

    if not content:
        raise ValueError(
            "Memory content cannot be empty."
        )

    memories = load_memories(
        user_id
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    memory = {
        "id": str(uuid4()),
        "type": memory_type,
        "content": content,
        "importance": max(
            0.0,
            min(
                1.0,
                float(importance),
            ),
        ),
        "embedding": embedding,
        "created_at": now,
        "updated_at": now,
    }

    memories.append(memory)

    save_memories(
        user_id,
        memories,
    )

    return memory


# ============================================================
# DELETE ONE MEMORY
# ============================================================

def delete_memory(
    user_id: str,
    memory_id: str,
) -> bool:

    memories = load_memories(
        user_id
    )

    updated_memories = [
        memory
        for memory in memories
        if memory.get("id") != memory_id
    ]

    if len(updated_memories) == len(
        memories
    ):
        return False

    save_memories(
        user_id,
        updated_memories,
    )

    return True


# ============================================================
# CLEAR ALL MEMORY
# ============================================================

def clear_memories(
    user_id: str,
) -> None:

    file_path = _memory_file(
        user_id
    )

    if file_path.exists():
        file_path.unlink()


# ============================================================
# GET ALL MEMORY
# ============================================================

def get_all_memories(
    user_id: str,
) -> list[dict]:

    return load_memories(
        user_id
    )