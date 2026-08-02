from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import aiosqlite

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS players (
    player_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dialogue_turns (
    turn_id TEXT PRIMARY KEY,
    request_id TEXT UNIQUE NOT NULL,
    client_request_id TEXT UNIQUE NOT NULL,
    request_fingerprint TEXT NOT NULL,
    player_id TEXT NOT NULL REFERENCES players(player_id),
    npc_id TEXT NOT NULL,
    npc_name_snapshot TEXT NOT NULL,
    player_message TEXT NOT NULL,
    npc_reply TEXT NOT NULL,
    reply_source TEXT NOT NULL CHECK(reply_source IN ('mock', 'model', 'fallback')),
    interaction_tags_json TEXT NOT NULL,
    relationship_delta INTEGER NOT NULL,
    relationship_reason TEXT NOT NULL,
    memory_saved INTEGER NOT NULL CHECK(memory_saved IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_turns_conversation
ON dialogue_turns(player_id, npc_id, created_at DESC);

CREATE TABLE IF NOT EXISTS relationships (
    player_id TEXT NOT NULL REFERENCES players(player_id),
    npc_id TEXT NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    interaction_count INTEGER NOT NULL,
    positive_points_today INTEGER NOT NULL,
    positive_points_date TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(player_id, npc_id)
);

CREATE TABLE IF NOT EXISTS relationship_events (
    event_id TEXT PRIMARY KEY,
    turn_id TEXT UNIQUE NOT NULL REFERENCES dialogue_turns(turn_id),
    player_id TEXT NOT NULL,
    npc_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    old_score INTEGER NOT NULL,
    delta INTEGER NOT NULL,
    new_score INTEGER NOT NULL,
    reason TEXT NOT NULL,
    interaction_count INTEGER NOT NULL,
    positive_points_today INTEGER NOT NULL,
    positive_points_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_events (
    memory_id TEXT PRIMARY KEY,
    source_turn_id TEXT NOT NULL REFERENCES dialogue_turns(turn_id),
    player_id TEXT NOT NULL,
    npc_id TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK(
        memory_type IN ('player_fact', 'preference', 'shared_topic', 'commitment', 'milestone')
    ),
    summary TEXT NOT NULL,
    normalized_terms_json TEXT NOT NULL,
    importance INTEGER NOT NULL CHECK(importance BETWEEN 1 AND 5),
    created_at TEXT NOT NULL,
    last_recalled_at TEXT,
    recall_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(player_id, npc_id, memory_type, summary)
);

CREATE INDEX IF NOT EXISTS idx_memories_lookup
ON memory_events(player_id, npc_id, importance DESC, created_at DESC);
"""

MIGRATION_2 = """
ALTER TABLE dialogue_turns
ADD COLUMN npc_title_snapshot TEXT NOT NULL DEFAULT '';
"""

MIGRATIONS = ((1, MIGRATION_1), (2, MIGRATION_2))

REQUIRED_SCHEMA_V1 = {
    "players": {"player_id", "display_name", "created_at"},
    "dialogue_turns": {
        "turn_id", "request_id", "client_request_id", "request_fingerprint",
        "player_id", "npc_id", "npc_name_snapshot", "player_message", "npc_reply",
        "reply_source", "interaction_tags_json", "relationship_delta",
        "relationship_reason", "memory_saved", "created_at",
    },
    "relationships": {
        "player_id", "npc_id", "score", "interaction_count",
        "positive_points_today", "positive_points_date", "updated_at",
    },
    "relationship_events": {
        "event_id", "turn_id", "player_id", "npc_id", "rule_id", "old_score", "delta",
        "new_score", "reason", "interaction_count", "positive_points_today",
        "positive_points_date", "created_at",
    },
    "memory_events": {
        "memory_id", "source_turn_id", "player_id", "npc_id", "memory_type", "summary",
        "normalized_terms_json", "importance", "created_at", "last_recalled_at",
        "recall_count",
    },
}
REQUIRED_SCHEMA = {
    **REQUIRED_SCHEMA_V1,
    "dialogue_turns": REQUIRED_SCHEMA_V1["dialogue_turns"] | {"npc_title_snapshot"},
}


class IncompatibleSchemaError(RuntimeError):
    pass


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.ready = False

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ready = False
        async with self.connection() as connection:
            await connection.execute("PRAGMA journal_mode = WAL")
            try:
                await connection.execute("BEGIN IMMEDIATE")
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    )
                    """
                )
                for version, migration in MIGRATIONS:
                    cursor = await connection.execute(
                        "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
                    )
                    if await cursor.fetchone() is not None:
                        if version == 1:
                            await self._validate_schema(connection, REQUIRED_SCHEMA_V1)
                        continue
                    await connection.executescript(migration)
                    await connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) "
                        "VALUES(?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                        (version,),
                    )
                await self._validate_schema(connection, REQUIRED_SCHEMA)
                await connection.commit()
            except Exception:
                with suppress(aiosqlite.Error):
                    await connection.rollback()
                raise
        self.ready = True

    async def _validate_schema(
        self, connection: aiosqlite.Connection, schema: dict[str, set[str]]
    ) -> None:
        for table_name, expected_columns in schema.items():
            cursor = await connection.execute(f'PRAGMA table_info("{table_name}")')
            columns = {row["name"] for row in await cursor.fetchall()}
            if not expected_columns <= columns:
                missing = ", ".join(sorted(expected_columns - columns))
                raise IncompatibleSchemaError(
                    f"database schema is incomplete: {table_name} missing {missing}"
                )

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        connection = await aiosqlite.connect(self.path)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA foreign_keys = ON")
        await connection.execute("PRAGMA busy_timeout = 3000")
        try:
            yield connection
        finally:
            await connection.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        async with self.connection() as connection:
            await connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise
            else:
                await connection.commit()
