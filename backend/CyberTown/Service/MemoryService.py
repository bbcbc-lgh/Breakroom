from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import aiosqlite

from CyberTown.Domain.Dialogue import MemoryCandidate
from CyberTown.Domain.MemoryEvent import StoredMemory
from CyberTown.Repository.MemoryRepository import MemoryRepository


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def _terms(value: str) -> set[str]:
    normalized = _normalize(value)
    result = {normalized} if normalized else set()
    result.update(normalized[index : index + 2] for index in range(max(0, len(normalized) - 1)))
    return {term for term in result if term}


@dataclass(frozen=True, slots=True)
class MemoryMatch:
    memory_id: str
    summary: str
    score: int


class MemoryService:
    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def retrieve(
        self,
        connection: aiosqlite.Connection,
        player_id: str,
        npc_id: str,
        query: str,
        limit: int = 3,
    ) -> tuple[MemoryMatch, ...]:
        query_terms = _terms(query)
        candidates = await self._repository.list_candidates(connection, player_id, npc_id)
        ranked: list[MemoryMatch] = []
        now = datetime.now(UTC)
        for memory in candidates:
            memory_terms = set(memory.terms)
            overlap = query_terms & memory_terms
            score = len(overlap) * 2 + memory.importance
            if any(term in _normalize(query) for term in memory.terms if len(term) > 1):
                score += 3
            if _as_utc(memory.created_at) >= now - timedelta(days=30):
                score += 1
            if memory.last_recalled_at and _as_utc(memory.last_recalled_at) >= now - timedelta(
                days=30
            ):
                score += 1
            score += min(memory.recall_count, 2)
            if score >= 6:
                ranked.append(
                    MemoryMatch(memory_id=memory.memory_id, summary=memory.summary, score=score)
                )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return tuple(ranked[:limit])

    async def save_candidates(
        self,
        connection: aiosqlite.Connection,
        *,
        source_turn_id: str,
        player_id: str,
        npc_id: str,
        candidates: tuple[MemoryCandidate, ...],
        created_at: str,
    ) -> bool:
        saved = False
        for candidate in candidates:
            normalized_terms = set(_terms(candidate.summary))
            for term in candidate.terms:
                normalized_terms.update(_terms(term))
            saved = (
                await self._repository.save_candidate(
                    connection,
                    memory_id=str(uuid4()),
                    source_turn_id=source_turn_id,
                    player_id=player_id,
                    npc_id=npc_id,
                    candidate=candidate,
                    normalized_terms=tuple(sorted(normalized_terms)),
                    created_at=created_at,
                )
                or saved
            )
        return saved

    async def mark_recalled(
        self, connection: aiosqlite.Connection, matches: tuple[MemoryMatch, ...]
    ) -> None:
        await self._repository.mark_recalled(
            connection,
            tuple(match.memory_id for match in matches),
            datetime.now(UTC).isoformat(),
        )

    async def list_all(
        self, connection: aiosqlite.Connection, player_id: str, npc_id: str
    ) -> list[StoredMemory]:
        return await self._repository.list_candidates(connection, player_id, npc_id)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
