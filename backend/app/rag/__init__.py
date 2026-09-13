"""
Orbit AI memory package.

The memory system uses:
    memory_store.py    -> persistent JSON storage
    memory_service.py  -> memory save/search logic
"""

from .memory_service import (
    remember,
    search_memory,
    remove_memory,
    clear_user_memory,
)

__all__ = [
    "remember",
    "search_memory",
    "remove_memory",
    "clear_user_memory",
]