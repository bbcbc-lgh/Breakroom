from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class StoredMemory:
    memory_id: str
    memory_type: str
    summary: str
    terms: tuple[str, ...]
    importance: int
    created_at: datetime
    last_recalled_at: datetime | None
    recall_count: int
