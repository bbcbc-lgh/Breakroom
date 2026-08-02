from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.ready = False

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connection() as connection:
            await connection.execute("PRAGMA journal_mode = WAL")
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            cursor = await connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = 1"
            )
            if await cursor.fetchone() is None:
                await connection.executescript(MIGRATION_1)
                await connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) "
                    "VALUES(1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"
                )
            await connection.commit()
        self.ready = True

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
