from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from CyberTown.Config import Settings
from CyberTown.Domain.Dialogue import DialogueModelResult
from CyberTown.main import create_app
from CyberTown.Observability.Logging import JsonFormatter
from CyberTown.Repository.Database import MIGRATION_1, Database, IncompatibleSchemaError
from CyberTown.Service.DialogueService import PersistenceError


async def _request(
    app, method: str, path: str, *, raise_app_exceptions: bool = True, **kwargs
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def _payload(npc_id: str, message: str, request_id: str | None = None) -> dict:
    return {
        "client_request_id": request_id or str(uuid4()),
        "player_id": "local-player",
        "npc_id": npc_id,
        "message": message,
    }


async def test_idempotent_replay_returns_first_result(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    request = _payload("zhang_xu", "谢谢，请帮我分析", str(uuid4()))
    async with app.router.lifespan_context(app):
        first = await _request(app, "POST", "/api/v1/dialogues", json=request)
        replay = await _request(app, "POST", "/api/v1/dialogues", json=request)
        history = await _request(
            app, "GET", "/api/v1/conversations/zhang_xu?player_id=local-player"
        )

    assert first.status_code == 200
    assert {key: value for key, value in replay.json().items() if key != "request_id"} == {
        key: value for key, value in first.json().items() if key != "request_id"
    }
    assert len(history.json()["messages"]) == 2


async def test_replay_uses_current_request_trace_id(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    request = _payload("zhang_xu", "请给我一个建议", str(uuid4()))
    async with app.router.lifespan_context(app):
        first = await _request(app, "POST", "/api/v1/dialogues", json=request)
        replay = await _request(app, "POST", "/api/v1/dialogues", json=request)

    assert replay.json()["request_id"] != first.json()["request_id"]
    assert replay.json()["request_id"] == replay.headers["X-Request-ID"]


async def test_replay_keeps_original_npc_display_snapshot(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    request = _payload("zhang_xu", "请给我一个建议", str(uuid4()))
    async with app.router.lifespan_context(app):
        first = await _request(app, "POST", "/api/v1/dialogues", json=request)
        profile = app.state.npc_service.get_profile("zhang_xu")
        renamed = profile.model_copy(update={"name": "新名字", "title": "新职位"})
        app.state.npc_service._profiles["zhang_xu"] = renamed
        replay = await _request(app, "POST", "/api/v1/dialogues", json=request)

    assert replay.json()["npc"] == first.json()["npc"]
    assert replay.json()["reply"] == first.json()["reply"]


async def test_conflicting_idempotency_key_is_rejected(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    request_id = str(uuid4())
    async with app.router.lifespan_context(app):
        first = await _request(
            app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("zhang_xu", "第一条", request_id),
        )
        conflict = await _request(
            app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("zhang_xu", "另一条", request_id),
        )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "REQUEST_ID_CONFLICT"


async def test_memory_survives_restart_and_is_isolated_by_npc(tmp_path: Path) -> None:
    first_app = create_app(Settings(data_dir=tmp_path))
    async with first_app.router.lifespan_context(first_app):
        saved = await _request(
            first_app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("zhang_xu", "我喜欢蓝色"),
        )
    assert saved.json()["memory_saved"] is True

    second_app = create_app(Settings(data_dir=tmp_path))
    async with second_app.router.lifespan_context(second_app):
        recalled = await _request(
            second_app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("zhang_xu", "你还记得我喜欢什么吗？"),
        )
        isolated = await _request(
            second_app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("hu_jialao", "你还记得我喜欢什么吗？"),
        )

    assert "蓝色" in recalled.json()["reply"]
    assert "蓝色" not in isolated.json()["reply"]
    assert recalled.json()["memory_saved"] is False

    third_app = create_app(Settings(data_dir=tmp_path))
    async with third_app.router.lifespan_context(third_app):
        unrelated = await _request(
            third_app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("zhang_xu", "今天天气怎么样"),
        )
    assert "蓝色" not in unrelated.json()["reply"]


async def test_model_fallback_is_persisted_without_relationship_or_memory_change(
    tmp_path: Path, monkeypatch
) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    async def fallback(_context):
        return DialogueModelResult(
            reply="刚才的思路断了一下，请稍后重试。",
            interaction_tags=frozenset({"respectful", "shares_personal_fact"}),
            reply_source="fallback",
            degraded=True,
        )

    monkeypatch.setattr(app.state.dialogue_service._dialogue_agent, "respond", fallback)
    async with app.router.lifespan_context(app):
        response = await _request(
            app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("zhang_xu", "我喜欢蓝色，谢谢你"),
        )
        history = await _request(
            app, "GET", "/api/v1/conversations/zhang_xu?player_id=local-player"
        )
        async with app.state.database.connection() as connection:
            memory_count = (
                await (await connection.execute("SELECT COUNT(*) FROM memory_events")).fetchone()
            )[0]

    body = response.json()
    assert response.status_code == 200
    assert body["reply_source"] == "fallback"
    assert body["degraded"] is True
    assert body["relationship"]["delta"] == 0
    assert body["memory_saved"] is False
    assert history.json()["messages"][-1]["reply_source"] == "fallback"
    assert memory_count == 0


async def test_relationship_and_history_survive_restart(tmp_path: Path) -> None:
    first_app = create_app(Settings(data_dir=tmp_path))
    async with first_app.router.lifespan_context(first_app):
        response = await _request(
            first_app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("fan_yueyi", "谢谢，请帮我定义目标用户"),
        )
    score = response.json()["relationship"]["score"]

    second_app = create_app(Settings(data_dir=tmp_path))
    async with second_app.router.lifespan_context(second_app):
        history = await _request(
            second_app,
            "GET",
            "/api/v1/conversations/fan_yueyi?player_id=local-player",
        )

    assert history.json()["relationship"]["score"] == score
    assert len(history.json()["messages"]) == 2


async def test_memory_is_isolated_by_player(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    async with app.router.lifespan_context(app):
        saved_payload = _payload("zhang_xu", "我喜欢绿色")
        saved_payload["player_id"] = "player-one"
        await _request(app, "POST", "/api/v1/dialogues", json=saved_payload)

        other_payload = _payload("zhang_xu", "你记得我喜欢什么吗？")
        other_payload["player_id"] = "player-two"
        other = await _request(app, "POST", "/api/v1/dialogues", json=other_payload)

    assert "绿色" not in other.json()["reply"]


async def test_duplicate_memory_updates_one_record(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    async with app.router.lifespan_context(app):
        first = await _request(
            app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("zhang_xu", "我喜欢蓝色"),
        )
        second = await _request(
            app,
            "POST",
            "/api/v1/dialogues",
            json=_payload("zhang_xu", "我喜欢蓝色"),
        )
        async with app.state.database.connection() as connection:
            cursor = await connection.execute(
                "SELECT COUNT(*), MAX(recall_count) FROM memory_events"
            )
            count, recall_count = await cursor.fetchone()

    assert first.json()["memory_saved"] is True
    assert second.json()["memory_saved"] is True
    assert count == 1
    assert recall_count >= 1


async def test_conversation_database_error_is_public(tmp_path: Path, monkeypatch) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    async def fail_conversation(*_args, **_kwargs):
        raise PersistenceError("forced conversation failure")

    monkeypatch.setattr(app.state.dialogue_service, "conversation", fail_conversation)
    async with app.router.lifespan_context(app):
        response = await _request(
            app, "GET", "/api/v1/conversations/zhang_xu?player_id=local-player"
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


async def test_failed_transaction_leaves_no_partial_turn(tmp_path: Path, monkeypatch) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    async with app.router.lifespan_context(app):
        async def fail_memory_save(*_args, **_kwargs):
            raise RuntimeError("forced memory failure")

        monkeypatch.setattr(
            app.state.dialogue_service._memory_service,
            "save_candidates",
            fail_memory_save,
        )
        with pytest.raises(PersistenceError, match="dialogue persistence failed"):
            await app.state.dialogue_service.create_dialogue(
                request_id=str(uuid4()),
                client_request_id=str(uuid4()),
                player_id="local-player",
                npc_id="zhang_xu",
                message="我喜欢红色",
            )

        async with app.state.database.connection() as connection:
            turn_cursor = await connection.execute("SELECT COUNT(*) FROM dialogue_turns")
            turn_count = (await turn_cursor.fetchone())[0]
            relationship_count = (
                await (await connection.execute("SELECT COUNT(*) FROM relationships")).fetchone()
            )[0]
            memory_cursor = await connection.execute("SELECT COUNT(*) FROM memory_events")
            memory_count = (await memory_cursor.fetchone())[0]

    assert (turn_count, relationship_count, memory_count) == (0, 0, 0)


async def test_short_context_uses_only_latest_turn_when_all_are_old(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    async with app.router.lifespan_context(app):
        for index in range(3):
            await _request(
                app,
                "POST",
                "/api/v1/dialogues",
                json=_payload("zhang_xu", f"旧消息 {index}"),
            )
        async with app.state.database.connection() as connection:
            cursor = await connection.execute(
                "SELECT turn_id FROM dialogue_turns ORDER BY created_at"
            )
            for index, row in enumerate(await cursor.fetchall()):
                old_time = (
                    datetime.now(UTC) - timedelta(hours=3, minutes=3 - index)
                ).isoformat()
                await connection.execute(
                    "UPDATE dialogue_turns SET created_at = ? WHERE turn_id = ?",
                    (old_time, row["turn_id"]),
                )
            await connection.commit()
            messages = await app.state.dialogue_service._dialogue_repository.list_recent_messages(
                connection, "local-player", "zhang_xu"
            )

    assert [message.content for message in messages if message.role == "player"] == ["旧消息 2"]


async def test_incomplete_schema_marker_fails_startup(tmp_path: Path) -> None:
    database_path = tmp_path / "CyberTown.db"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_migrations VALUES(1, '2026-08-02T00:00:00Z');
        """
    )
    connection.commit()
    connection.close()

    database = Database(database_path)
    with pytest.raises(IncompatibleSchemaError, match="schema is incomplete"):
        await database.initialize()
    assert database.ready is False


async def test_version_one_database_is_upgraded(tmp_path: Path) -> None:
    database_path = tmp_path / "CyberTown.db"
    database = Database(database_path)
    async with database.connection() as connection:
        await connection.executescript(MIGRATION_1)
        await connection.execute(
            "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        await connection.execute(
            "INSERT INTO schema_migrations VALUES(1, '2026-08-02T00:00:00Z')"
        )
        await connection.commit()

    await database.initialize()
    async with database.connection() as connection:
        cursor = await connection.execute('PRAGMA table_info("dialogue_turns")')
        columns = {row["name"] for row in await cursor.fetchall()}
        cursor = await connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        versions = [row["version"] for row in await cursor.fetchall()]

    assert "npc_title_snapshot" in columns
    assert versions == [1, 2]


async def test_unexpected_error_keeps_request_id(tmp_path: Path, monkeypatch) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    def fail_list():
        raise RuntimeError("forced API failure")

    monkeypatch.setattr(app.state.npc_service, "list_profiles", fail_list)
    logger = logging.getLogger("CyberTown")
    records: list[str] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(self.format(record))

    handler = CaptureHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    try:
        async with app.router.lifespan_context(app):
            response = await _request(
                app, "GET", "/api/v1/npcs", raise_app_exceptions=False
            )
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    failed = next(json.loads(line) for line in records if '"message": "request failed"' in line)
    assert failed["request_id"] == response.headers["X-Request-ID"]
    assert failed["details"]["error_code"] == "INTERNAL_ERROR"


async def test_database_schema_matches_design_tables(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    async with (
        app.router.lifespan_context(app),
        app.state.database.connection() as connection,
    ):
        cursor = await connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        tables = {row["name"] for row in await cursor.fetchall()}

    assert {
        "schema_migrations",
        "players",
        "dialogue_turns",
        "relationships",
        "relationship_events",
        "memory_events",
    } <= tables
