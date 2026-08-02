from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import aiosqlite

from CyberTown.Domain.Dialogue import ConversationMessage, DialogueModelResult
from CyberTown.Domain.Relationship import RelationshipDecision, relationship_level


@dataclass(frozen=True, slots=True)
class StoredTurn:
    turn_id: str
    request_id: str
    client_request_id: str
    request_fingerprint: str
    player_id: str
    npc_id: str
    player_message: str
    npc_reply: str
    reply_source: str
    interaction_tags: frozenset[str]
    relationship: RelationshipDecision
    memory_saved: bool
    created_at: datetime


class DialogueRepository:
    async def ensure_player(
        self, connection: aiosqlite.Connection, player_id: str, created_at: str
    ) -> None:
        await connection.execute(
            "INSERT OR IGNORE INTO players(player_id, display_name, created_at) VALUES(?, ?, ?)",
            (player_id, "本地玩家", created_at),
        )

    async def find_by_client_request_id(
        self, connection: aiosqlite.Connection, client_request_id: str
    ) -> StoredTurn | None:
        cursor = await connection.execute(
            """
            SELECT dt.*, re.rule_id, re.old_score, re.new_score,
                   re.positive_points_today, re.positive_points_date,
                   re.interaction_count
            FROM dialogue_turns AS dt
            LEFT JOIN relationship_events AS re ON re.turn_id = dt.turn_id
            WHERE dt.client_request_id = ?
            """,
            (client_request_id,),
        )
        row = await cursor.fetchone()
        return self._to_stored_turn(row) if row else None

    async def set_memory_saved(
        self, connection: aiosqlite.Connection, turn_id: str, memory_saved: bool
    ) -> None:
        await connection.execute(
            "UPDATE dialogue_turns SET memory_saved = ? WHERE turn_id = ?",
            (int(memory_saved), turn_id),
        )

    async def insert_turn(
        self,
        connection: aiosqlite.Connection,
        *,
        turn_id: str,
        request_id: str,
        client_request_id: str,
        request_fingerprint: str,
        player_id: str,
        npc_id: str,
        npc_name: str,
        player_message: str,
        model_result: DialogueModelResult,
        relationship: RelationshipDecision,
        memory_saved: bool,
        created_at: str,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO dialogue_turns(
                turn_id, request_id, client_request_id, request_fingerprint,
                player_id, npc_id, npc_name_snapshot, player_message, npc_reply,
                reply_source, interaction_tags_json, relationship_delta,
                relationship_reason, memory_saved, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                turn_id,
                request_id,
                client_request_id,
                request_fingerprint,
                player_id,
                npc_id,
                npc_name,
                player_message,
                model_result.reply,
                model_result.reply_source,
                json.dumps(sorted(model_result.interaction_tags), ensure_ascii=False),
                relationship.delta,
                relationship.reason,
                int(memory_saved),
                created_at,
            ),
        )

    async def list_recent_messages(
        self,
        connection: aiosqlite.Connection,
        player_id: str,
        npc_id: str,
        *,
        turn_limit: int = 5,
    ) -> tuple[ConversationMessage, ...]:
        cursor = await connection.execute(
            """
            SELECT player_message, npc_reply
            FROM dialogue_turns
            WHERE player_id = ? AND npc_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (player_id, npc_id, turn_limit),
        )
        rows = list(reversed(await cursor.fetchall()))
        messages: list[ConversationMessage] = []
        for row in rows:
            messages.append(ConversationMessage(role="player", content=row["player_message"]))
            messages.append(ConversationMessage(role="npc", content=row["npc_reply"]))
        return tuple(messages)

    async def list_turns(
        self,
        connection: aiosqlite.Connection,
        player_id: str,
        npc_id: str,
        limit: int,
    ) -> list[aiosqlite.Row]:
        cursor = await connection.execute(
            """
            SELECT turn_id, player_message, npc_reply, reply_source, created_at
            FROM dialogue_turns
            WHERE player_id = ? AND npc_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (player_id, npc_id, limit),
        )
        return list(reversed(await cursor.fetchall()))

    async def recent_player_messages(
        self,
        connection: aiosqlite.Connection,
        player_id: str,
        npc_id: str,
        since: str,
    ) -> list[str]:
        cursor = await connection.execute(
            """
            SELECT player_message FROM dialogue_turns
            WHERE player_id = ? AND npc_id = ? AND created_at >= ?
            """,
            (player_id, npc_id, since),
        )
        return [row["player_message"] for row in await cursor.fetchall()]

    def _to_stored_turn(self, row: aiosqlite.Row) -> StoredTurn:
        new_score = row["new_score"] if row["new_score"] is not None else 10
        return StoredTurn(
            turn_id=row["turn_id"],
            request_id=row["request_id"],
            client_request_id=row["client_request_id"],
            request_fingerprint=row["request_fingerprint"],
            player_id=row["player_id"],
            npc_id=row["npc_id"],
            player_message=row["player_message"],
            npc_reply=row["npc_reply"],
            reply_source=row["reply_source"],
            interaction_tags=frozenset(json.loads(row["interaction_tags_json"])),
            relationship=RelationshipDecision(
                old_score=row["old_score"] if row["old_score"] is not None else 10,
                new_score=new_score,
                delta=row["relationship_delta"],
                level=relationship_level(new_score),
                rule_id=row["rule_id"] or "REL_NEUTRAL",
                reason=row["relationship_reason"],
                interaction_count=row["interaction_count"] or 1,
                positive_points_today=row["positive_points_today"] or 0,
                positive_points_date=row["positive_points_date"] or "",
            ),
            memory_saved=bool(row["memory_saved"]),
            created_at=datetime.fromisoformat(row["created_at"]).astimezone(UTC),
        )
