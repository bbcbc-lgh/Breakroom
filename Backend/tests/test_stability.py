from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from uuid import uuid4

import httpx

from src.Config import Settings
from src.main import create_app
from src.Observability.Logging import JsonFormatter

NPC_IDS = ("zhang_xu", "fan_yueyi", "hu_jialao")


def _payload(npc_id: str, message: str) -> dict:
    return {
        "client_request_id": str(uuid4()),
        "player_id": "stability-player",
        "npc_id": npc_id,
        "message": message,
    }


async def test_thirty_mock_dialogues_remain_isolated(tmp_path: Path) -> None:
    app = create_app(Settings(dialogue_mode="mock", data_dir=tmp_path))
    responses: list[dict] = []
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        for index in range(30):
            npc_id = NPC_IDS[index % len(NPC_IDS)]
            response = await client.post(
                "/api/v1/dialogues",
                json=_payload(npc_id, f"稳定性轮次 {index}"),
            )
            assert response.status_code == 200
            responses.append(response.json())

        histories = {}
        for npc_id in NPC_IDS:
            response = await client.get(
                f"/api/v1/conversations/{npc_id}",
                params={"player_id": "stability-player", "limit": 50},
            )
            assert response.status_code == 200
            histories[npc_id] = response.json()

        async with app.state.database.connection() as connection:
            counts = {}
            for table in ("dialogue_turns", "relationship_events", "memory_events"):
                row = await (await connection.execute(f"SELECT COUNT(*) FROM {table}")).fetchone()
                counts[table] = row[0]
            relationship_rows = await (
                await connection.execute(
                    "SELECT npc_id, score, interaction_count FROM relationships ORDER BY npc_id"
                )
            ).fetchall()

    assert len({item["request_id"] for item in responses}) == 30
    assert all(item["reply_source"] == "mock" for item in responses)
    assert all(item["relationship"]["delta"] == 0 for item in responses)
    assert counts == {
        "dialogue_turns": 30,
        "relationship_events": 30,
        "memory_events": 0,
    }
    relationship_values = [
        (row["npc_id"], row["score"], row["interaction_count"])
        for row in relationship_rows
    ]
    assert relationship_values == [
        ("fan_yueyi", 10, 10),
        ("hu_jialao", 10, 10),
        ("zhang_xu", 10, 10),
    ]
    for npc_id, history in histories.items():
        assert history["npc"]["npc_id"] == npc_id
        assert len(history["messages"]) == 20
        expected_indices = {
            str(index) for index in range(30) if NPC_IDS[index % len(NPC_IDS)] == npc_id
        }
        player_messages = {
            message["content"].removeprefix("稳定性轮次 ")
            for message in history["messages"]
            if message["role"] == "player"
        }
        assert player_messages == expected_indices


async def test_sqlite_write_lock_returns_retryable_error_without_partial_turn(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(dialogue_mode="mock", data_dir=tmp_path))
    request = _payload("zhang_xu", "数据库锁测试")
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        locker = sqlite3.connect(app.state.database.path, timeout=0)
        locker.execute("BEGIN IMMEDIATE")
        try:
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/dialogues",
                    json=request,
                )
        finally:
            locker.rollback()
            locker.close()

        async with app.state.database.connection() as connection:
            cursor = await connection.execute("SELECT COUNT(*) FROM dialogue_turns")
            count_after_failure = (await cursor.fetchone())[0]
            cursor = await connection.execute("SELECT COUNT(*) FROM relationship_events")
            events_after_failure = (await cursor.fetchone())[0]

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            retry = await client.post("/api/v1/dialogues", json=request)
            replay = await client.post("/api/v1/dialogues", json=request)

        async with app.state.database.connection() as connection:
            cursor = await connection.execute("SELECT COUNT(*) FROM dialogue_turns")
            count = (await cursor.fetchone())[0]
            cursor = await connection.execute("SELECT COUNT(*) FROM relationship_events")
            event_count = (await cursor.fetchone())[0]

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "DATABASE_UNAVAILABLE",
        "message": "本次对话未能保存，请重试。",
        "retryable": True,
    }
    assert count_after_failure == 0
    assert events_after_failure == 0
    assert retry.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["reply"] == retry.json()["reply"]
    assert count == 1
    assert event_count == 1


class _ImmediateJsonHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


async def test_request_id_correlates_dialogue_and_http_logs(tmp_path: Path) -> None:
    app = create_app(Settings(dialogue_mode="mock", data_dir=tmp_path / str(uuid4())))
    logger = logging.getLogger("Breakroom")
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    handler = _ImmediateJsonHandler()
    logger.addHandler(handler)
    try:
        transport = httpx.ASGITransport(app=app)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        ):
            response = await client.post(
                "/api/v1/dialogues",
                json=_payload("zhang_xu", "日志链路测试"),
            )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    records = [json.loads(line) for line in handler.lines]
    assert response.status_code == 200, (response.text, records)
    dialogue = next(item for item in records if item["message"] == "dialogue completed")
    request = next(item for item in records if item["message"] == "request completed")
    assert response.status_code == 200
    assert dialogue["request_id"] == response.headers["X-Request-ID"]
    assert request["request_id"] == response.headers["X-Request-ID"]
    assert dialogue["details"]["memory_hits"] == 0
    assert dialogue["details"]["relationship_rule"] == "REL_NEUTRAL"
