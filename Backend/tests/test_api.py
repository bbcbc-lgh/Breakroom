from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import httpx

from src.Config import Settings
from src.main import create_app


@asynccontextmanager
async def _client() -> AsyncIterator[httpx.AsyncClient]:
    with TemporaryDirectory() as temp_dir:
        app = create_app(Settings(dialogue_mode="mock", data_dir=Path(temp_dir)))
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield client


def _dialogue_payload(npc_id: str, message: str = "请给我一个建议") -> dict:
    return {
        "client_request_id": str(uuid4()),
        "player_id": "local-player",
        "npc_id": npc_id,
        "message": message,
    }


async def test_health_reports_mock_mode_and_content_version() -> None:
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "version": "0.1.0",
        "dialogue_mode": "mock",
        "database_ready": True,
        "content_version": "1",
    }
    assert response.headers["X-Request-ID"]


async def test_lists_three_configured_npcs() -> None:
    async with _client() as client:
        response = await client.get("/api/v1/npcs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_version"] == "1"
    assert [npc["npc_id"] for npc in payload["npcs"]] == [
        "zhang_xu",
        "fan_yueyi",
        "hu_jialao",
    ]


async def test_mock_dialogue_styles_are_distinct() -> None:
    replies = {}
    async with _client() as client:
        for npc_id in ("zhang_xu", "fan_yueyi", "hu_jialao"):
            response = await client.post(
                "/api/v1/dialogues", json=_dialogue_payload(npc_id, "如何开始这个项目？")
            )
            replies[npc_id] = response.json()["reply"]

    assert "可复现" in replies["zhang_xu"]
    assert "目标用户" in replies["fan_yueyi"]
    assert "体验层级" in replies["hu_jialao"]
    assert len(set(replies.values())) == 3


async def test_dialogue_response_matches_public_contract() -> None:
    request = _dialogue_payload("zhang_xu", "谢谢，请帮我梳理测试边界")
    async with _client() as client:
        response = await client.post("/api/v1/dialogues", json=request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["client_request_id"] == request["client_request_id"]
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert payload["npc"]["name"] == "张旭"
    assert payload["reply_source"] == "mock"
    assert payload["relationship"] == {
        "score": 13,
        "level": "陌生",
        "delta": 3,
        "reason": "认真交流",
    }
    assert payload["memory_saved"] is False
    assert payload["degraded"] is False


async def test_unknown_npc_returns_public_error() -> None:
    async with _client() as client:
        response = await client.post("/api/v1/dialogues", json=_dialogue_payload("missing_npc"))

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"] == {
        "code": "NPC_NOT_FOUND",
        "message": "没有找到这个角色。",
        "retryable": False,
    }
    assert payload["request_id"] == response.headers["X-Request-ID"]


async def test_invalid_message_returns_sanitized_validation_error() -> None:
    async with _client() as client:
        response = await client.post("/api/v1/dialogues", json=_dialogue_payload("zhang_xu", "   "))

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "INVALID_REQUEST",
        "message": "请求字段无效，请检查后重试。",
        "retryable": False,
    }


async def test_message_longer_than_limit_is_rejected() -> None:
    async with _client() as client:
        response = await client.post(
            "/api/v1/dialogues", json=_dialogue_payload("zhang_xu", "长" * 301)
        )

    assert response.status_code == 422
