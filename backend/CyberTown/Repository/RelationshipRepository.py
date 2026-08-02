from __future__ import annotations

import aiosqlite

from CyberTown.Domain.Relationship import RelationshipDecision, RelationshipState


class RelationshipRepository:
    async def get(
        self, connection: aiosqlite.Connection, player_id: str, npc_id: str
    ) -> RelationshipState:
        cursor = await connection.execute(
            """
            SELECT score, interaction_count, positive_points_today, positive_points_date
            FROM relationships WHERE player_id = ? AND npc_id = ?
            """,
            (player_id, npc_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return RelationshipState()
        return RelationshipState(
            score=row["score"],
            interaction_count=row["interaction_count"],
            positive_points_today=row["positive_points_today"],
            positive_points_date=row["positive_points_date"],
        )

    async def save(
        self,
        connection: aiosqlite.Connection,
        player_id: str,
        npc_id: str,
        decision: RelationshipDecision,
        updated_at: str,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO relationships(
                player_id, npc_id, score, interaction_count,
                positive_points_today, positive_points_date, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, npc_id) DO UPDATE SET
                score = excluded.score,
                interaction_count = excluded.interaction_count,
                positive_points_today = excluded.positive_points_today,
                positive_points_date = excluded.positive_points_date,
                updated_at = excluded.updated_at
            """,
            (
                player_id,
                npc_id,
                decision.new_score,
                decision.interaction_count,
                decision.positive_points_today,
                decision.positive_points_date,
                updated_at,
            ),
        )

    async def add_event(
        self,
        connection: aiosqlite.Connection,
        *,
        event_id: str,
        turn_id: str,
        player_id: str,
        npc_id: str,
        decision: RelationshipDecision,
        created_at: str,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO relationship_events(
                event_id, turn_id, player_id, npc_id, rule_id,
                old_score, delta, new_score, reason, interaction_count,
                positive_points_today, positive_points_date, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                turn_id,
                player_id,
                npc_id,
                decision.rule_id,
                decision.old_score,
                decision.delta,
                decision.new_score,
                decision.reason,
                decision.interaction_count,
                decision.positive_points_today,
                decision.positive_points_date,
                created_at,
            ),
        )
