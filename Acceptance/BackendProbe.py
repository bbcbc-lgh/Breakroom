from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import SecretStr

CHAPTER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CHAPTER_ROOT / "backend"))

from CyberTown.Config import Settings, get_settings
from CyberTown.main import create_app

CONTENT_PATH = CHAPTER_ROOT / "Content" / "NPCProfiles.json"
NPC_MESSAGES = {
    "zhang_xu": "请从工程角度给我一个简短建议。",
    "fan_yueyi": "请从产品角度给我一个简短建议。",
    "hu_jialao": "请从视觉角度给我一个简短建议。",
}


def _payload(npc_id: str, message: str) -> dict[str, str]:
    return {
        "client_request_id": str(uuid4()),
        "player_id": "acceptance-player",
        "npc_id": npc_id,
        "message": message,
    }


async def _request(
    app, method: str, path: str, payload: dict[str, str] | None = None
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://acceptance"
    ) as client:
        return await client.request(method, path, json=payload)


async def _probe_mode(
    label: str, settings: Settings, *, retry_degraded: bool = False
) -> dict:
    app = create_app(settings)
    results = []
    async with app.router.lifespan_context(app):
        health = (await _request(app, "GET", "/health")).json()
        for npc_id, message in NPC_MESSAGES.items():
            attempts = 0
            while True:
                attempts += 1
                response = await _request(
                    app,
                    "POST",
                    "/api/v1/dialogues",
                    _payload(npc_id, message),
                )
                body = response.json()
                if not retry_degraded or not body.get("degraded") or attempts == 2:
                    break
            results.append(
                {
                    "npc_id": npc_id,
                    "status": response.status_code,
                    "reply_source": body.get("reply_source"),
                    "degraded": body.get("degraded"),
                    "attempts": attempts,
                }
            )
    return {
        "probe": label,
        "health_mode": health.get("dialogue_mode"),
        "results": results,
    }


async def _probe_persistence(data_dir: Path) -> dict:
    settings = Settings(
        content_path=CONTENT_PATH,
        data_dir=data_dir,
        dialogue_mode="mock",
        model_base_url="",
        model_name="",
        model_api_key=SecretStr(""),
    )
    first_app = create_app(settings)
    async with first_app.router.lifespan_context(first_app):
        saved = (
            await _request(
                first_app,
                "POST",
                "/api/v1/dialogues",
                _payload("zhang_xu", "我喜欢蓝色"),
            )
        ).json()

    second_app = create_app(settings)
    async with second_app.router.lifespan_context(second_app):
        recalled = (
            await _request(
                second_app,
                "POST",
                "/api/v1/dialogues",
                _payload("zhang_xu", "你还记得我喜欢什么吗？"),
            )
        ).json()
        isolated = (
            await _request(
                second_app,
                "POST",
                "/api/v1/dialogues",
                _payload("hu_jialao", "你还记得我喜欢什么吗？"),
            )
        ).json()
        conversation = (
            await _request(
                second_app,
                "GET",
                "/api/v1/conversations/zhang_xu?player_id=acceptance-player",
            )
        ).json()

    return {
        "probe": "sqlite_restart",
        "memory_saved": saved.get("memory_saved"),
        "same_npc_recalled": "蓝色" in recalled.get("reply", ""),
        "cross_npc_isolated": "蓝色" not in isolated.get("reply", ""),
        "persisted_message_count": len(conversation.get("messages", [])),
    }


def _passed(records: list[dict]) -> bool:
    expected_sources = {
        "mock": ("mock", False),
        "fallback": ("fallback", True),
        "configured_model": ("model", False),
    }
    for record in records[:3]:
        expected_source, expected_degraded = expected_sources[record["probe"]]
        if len(record["results"]) != 3:
            return False
        if any(
            result["status"] != 200
            or result["reply_source"] != expected_source
            or result["degraded"] is not expected_degraded
            for result in record["results"]
        ):
            return False
    persistence = records[3]
    return (
        persistence["memory_saved"] is True
        and persistence["same_npc_recalled"] is True
        and persistence["cross_npc_isolated"] is True
        and persistence["persisted_message_count"] == 4
    )


async def main() -> int:
    records = []
    with tempfile.TemporaryDirectory(prefix="cyber-town-acceptance-") as temp:
        root = Path(temp)
        records.append(
            await _probe_mode(
                "mock",
                Settings(
                    content_path=CONTENT_PATH,
                    data_dir=root / "mock",
                    dialogue_mode="mock",
                    model_base_url="",
                    model_name="",
                    model_api_key=SecretStr(""),
                ),
            )
        )
        records.append(
            await _probe_mode(
                "fallback",
                Settings(
                    content_path=CONTENT_PATH,
                    data_dir=root / "fallback",
                    dialogue_mode="model",
                    model_base_url="http://127.0.0.1:9/v1",
                    model_name="unreachable-acceptance-model",
                    model_api_key=SecretStr("acceptance-placeholder"),
                    model_timeout_seconds=1.0,
                ),
            )
        )
        configured = get_settings()
        model_settings = Settings.model_validate(
            {
                **configured.model_dump(),
                "content_path": CONTENT_PATH,
                "data_dir": root / "model",
                "log_dir": root / "logs",
            }
        )
        records.append(
            await _probe_mode(
                "configured_model", model_settings, retry_degraded=True
            )
        )
        records.append(await _probe_persistence(root / "persistence"))

    result = {"passed": _passed(records), "records": records}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
