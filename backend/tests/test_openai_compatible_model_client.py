from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from CyberTown.Agent.OpenAICompatibleDialogueModelClient import (
    OpenAICompatibleDialogueModelClient,
)
from CyberTown.Config import PROJECT_ROOT
from CyberTown.Domain.Dialogue import ConversationMessage, DialogueContext
from CyberTown.Infrastructure.NPCConfigLoader import NPCConfigLoader


def _context(npc_index: int = 0) -> DialogueContext:
    profile = NPCConfigLoader().load(PROJECT_ROOT / "Content" / "NPCProfiles.json").npcs[
        npc_index
    ]
    return DialogueContext(
        profile=profile,
        player_id="private-player-id",
        player_message="我喜欢爵士乐，请给我一个建议",
        relationship_level="友好",
        recent_messages=(
            ConversationMessage(role="player", content="之前的话题"),
            ConversationMessage(role="npc", content="之前的回答"),
        ),
        relevant_memories=("玩家喜欢蓝色",),
    )


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> OpenAICompatibleDialogueModelClient:
    return OpenAICompatibleDialogueModelClient(
        base_url="https://model.example/v1/",
        model_name="test-model",
        api_key="test-api-secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )


def _completion(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


async def test_success_filters_unknown_tags_and_unfounded_memories() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured.update(json.loads(request.content))
        return _completion(
            json.dumps(
                {
                    "reply": "先明确听众，再把爵士乐元素放到关键反馈里。",
                    "interaction_tags": ["helpful", "write_database"],
                    "memory_candidates": [
                        {
                            "memory_type": "preference",
                            "summary": "玩家喜欢爵士乐",
                            "terms": ["爵士乐"],
                            "importance": 4,
                        },
                        {
                            "memory_type": "player_fact",
                            "summary": "玩家住在上海",
                            "terms": ["上海"],
                            "importance": 5,
                        },
                    ],
                },
                ensure_ascii=False,
            )
        )

    result = await _client(handler).generate(_context())

    assert result.reply_source == "model"
    assert result.degraded is False
    assert result.interaction_tags == frozenset({"helpful"})
    assert [item.summary for item in result.memory_candidates] == ["玩家喜欢爵士乐"]
    assert captured["model"] == "test-model"
    assert captured["url"] == "https://model.example/v1/chat/completions"
    serialized_request = json.dumps(captured, ensure_ascii=False)
    assert "张旭" in serialized_request
    assert "private-player-id" not in serialized_request
    assert "test-api-secret" not in serialized_request


async def test_memory_grounding_rejects_inverted_preference_and_questions() -> None:
    payload = {
        "reply": "知道了。",
        "interaction_tags": ["shares_personal_fact"],
        "memory_candidates": [
            {
                "memory_type": "preference",
                "summary": "玩家喜欢蓝色",
                "terms": ["蓝色"],
                "importance": 4,
            }
        ],
    }

    negative_context = _context()
    negative_context = DialogueContext(
        profile=negative_context.profile,
        player_id=negative_context.player_id,
        player_message="我不喜欢蓝色",
        relationship_level=negative_context.relationship_level,
    )
    question_context = DialogueContext(
        profile=negative_context.profile,
        player_id=negative_context.player_id,
        player_message="你记得我喜欢蓝色吗？",
        relationship_level=negative_context.relationship_level,
    )

    negative = await _client(lambda _request: _completion(json.dumps(payload))).generate(
        negative_context
    )
    question = await _client(lambda _request: _completion(json.dumps(payload))).generate(
        question_context
    )

    assert negative.memory_candidates == ()
    assert question.memory_candidates == ()


@pytest.mark.parametrize(
    "handler",
    [
        lambda _request: httpx.Response(503, json={"error": "unavailable"}),
        lambda _request: _completion("not-json"),
        lambda _request: _completion(
            json.dumps(
                {
                    "reply": "太长" * 141,
                    "interaction_tags": [],
                    "memory_candidates": [],
                }
            )
        ),
        lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=request)),
    ],
    ids=["http-error", "non-json", "overlong-reply", "timeout"],
)
async def test_invalid_or_failed_model_response_uses_fallback(handler) -> None:
    result = await _client(handler).generate(_context())

    assert result.reply_source == "fallback"
    assert result.degraded is True
    assert result.interaction_tags == frozenset({"neutral"})
    assert result.memory_candidates == ()
    assert "Python / AI 工程师" in result.reply


async def test_request_context_is_limited_to_current_npc_and_five_turns() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _completion(
            json.dumps(
                {
                    "reply": "收到。",
                    "interaction_tags": ["neutral"],
                    "memory_candidates": [],
                }
            )
        )

    context = _context(1)
    messages = tuple(
        ConversationMessage(
            role="player" if index % 2 == 0 else "npc",
            content=f"history-{index}",
        )
        for index in range(14)
    )
    context = DialogueContext(
        profile=context.profile,
        player_id=context.player_id,
        player_message=context.player_message,
        relationship_level=context.relationship_level,
        recent_messages=messages,
        relevant_memories=("one", "two", "three", "must-not-send"),
    )

    await _client(handler).generate(context)

    request_messages = captured["messages"]
    assert len(request_messages) == 12
    assert "history-0" not in json.dumps(request_messages)
    assert "history-4" in json.dumps(request_messages)
    assert "must-not-send" not in request_messages[0]["content"]
    assert "樊玥燚" in request_messages[0]["content"]
    assert "张旭" not in request_messages[0]["content"]
