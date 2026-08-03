from __future__ import annotations

import json
from datetime import datetime

import aiosqlite

from src.Domain.Dialogue import MemoryCandidate
from src.Domain.MemoryEvent import StoredMemory


class MemoryRepository:
    async def list_candidates(
        self,
        connection: aiosqlite.Connection,
        player_id: str,
        npc_id: str,
        limit: int = 50,
    ) -> list[StoredMemory]:
        cursor = await connection.execute(
            """
            SELECT * FROM memory_events
            WHERE player_id = ? AND npc_id = ?
            ORDER BY importance DESC, created_at DESC
            LIMIT ?
            """,
            (player_id, npc_id, limit),
        )
        return [
            StoredMemory(
                memory_id=row["memory_id"],
                memory_type=row["memory_type"],
                summary=row["summary"],
                terms=tuple(json.loads(row["normalized_terms_json"])),
                importance=row["importance"],
                created_at=datetime.fromisoformat(row["created_at"]),
                last_recalled_at=(
                    datetime.fromisoformat(row["last_recalled_at"])
                    if row["last_recalled_at"]
                    else None
                ),
                recall_count=row["recall_count"],
            )
            for row in await cursor.fetchall()
        ]

    async def save_candidate(
        self,
        connection: aiosqlite.Connection,
        *,
        memory_id: str,
        source_turn_id: str,
        player_id: str,
        npc_id: str,
        candidate: MemoryCandidate,
        normalized_terms: tuple[str, ...],
        created_at: str,
    ) -> bool:
        cursor = await connection.execute(
            """
            INSERT INTO memory_events(
                memory_id, source_turn_id, player_id, npc_id, memory_type,
                summary, normalized_terms_json, importance, created_at,
                last_recalled_at, recall_count
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0)
            ON CONFLICT(player_id, npc_id, memory_type, summary) DO UPDATE SET
                source_turn_id = excluded.source_turn_id,
                normalized_terms_json = excluded.normalized_terms_json,
                importance = MAX(memory_events.importance, excluded.importance)
            """,
            (
                memory_id,
                source_turn_id,
                player_id,
                npc_id,
                candidate.memory_type,
                candidate.summary,
                json.dumps(normalized_terms, ensure_ascii=False),
                candidate.importance,
                created_at,
            ),
        )
        return cursor.rowcount > 0

    async def mark_recalled(
        self,
        connection: aiosqlite.Connection,
        memory_ids: tuple[str, ...],
        recalled_at: str,
    ) -> None:
        if not memory_ids:
            return
        placeholders = ",".join("?" for _ in memory_ids)
        await connection.execute(
            f"""
            UPDATE memory_events
            SET last_recalled_at = ?, recall_count = recall_count + 1
            WHERE memory_id IN ({placeholders})
            """,  # noqa: S608 - placeholders are generated, not user supplied
            (recalled_at, *memory_ids),
        )
