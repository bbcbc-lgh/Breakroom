from __future__ import annotations

import json
import logging
import re
import unicodedata
from time import perf_counter
from typing import Annotated, Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from src.Agent.BaseDialogueModelClient import BaseDialogueModelClient
from src.Domain.Dialogue import (
    INTERACTION_TAGS,
    DialogueContext,
    DialogueModelResult,
    MemoryCandidate,
)

logger = logging.getLogger("CyberTown.Model")
ModelText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
MemoryTerm = Annotated[ModelText, StringConstraints(max_length=30)]


class _ModelMemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: Literal[
        "player_fact", "preference", "shared_topic", "commitment", "milestone"
    ]
    summary: Annotated[ModelText, StringConstraints(max_length=120)]
    terms: list[MemoryTerm] = Field(min_length=1, max_length=6)
    importance: int = Field(ge=1, le=5)


class _ModelDialoguePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: Annotated[ModelText, StringConstraints(max_length=280)]
    interaction_tags: list[str] = Field(default_factory=list, max_length=5)
    memory_candidates: list[_ModelMemoryCandidate] = Field(default_factory=list, max_length=3)


class OpenAICompatibleDialogueModelClient(BaseDialogueModelClient):
    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        api_key: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def generate(self, context: DialogueContext) -> DialogueModelResult:
        started_at = perf_counter()
        failure_type = ""
        try:
            payload = await self._request(self._messages(context))
            result = self._validated_result(payload, context)
        except httpx.TimeoutException:
            failure_type = "model_timeout"
            result = self._fallback(context)
        except httpx.HTTPStatusError as exc:
            failure_type = f"model_http_{exc.response.status_code}"
            result = self._fallback(context)
        except httpx.RequestError:
            failure_type = "model_network_error"
            result = self._fallback(context)
        except (IndexError, KeyError, TypeError, ValueError, ValidationError):
            failure_type = "model_invalid_response"
            result = self._fallback(context)

        logger.info(
            "dialogue model completed",
            extra={
                "details": {
                    "model": self._model_name,
                    "reply_source": result.reply_source,
                    "duration_ms": round((perf_counter() - started_at) * 1000),
                    "failure_type": failure_type,
                }
            },
        )
        return result

    async def _request(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        request_payload = {
            "model": self._model_name,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=timeout,
            trust_env=False,
        ) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=request_payload,
            )
            response.raise_for_status()
            body = response.json()
        content = body["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("model content must be a string")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise TypeError("model payload must be an object")
        return parsed

    def _messages(self, context: DialogueContext) -> list[dict[str, str]]:
        profile = context.profile
        current_tone = profile.relationship_tone[context.relationship_level]
        profile_payload = {
            "name": profile.name,
            "title": profile.title,
            "personality": profile.personality,
            "speech_style": profile.speech_style,
            "background": profile.background,
            "preferred_topics": profile.preferred_topics,
            "boundaries": profile.boundaries,
            "relationship_level": context.relationship_level,
            "relationship_tone": current_tone,
            "relevant_memories": list(context.relevant_memories[:3]),
        }
        serialized_profile = json.dumps(
            profile_payload, ensure_ascii=False, separators=(",", ":")
        )
        instructions = (
            "你正在扮演赛博小镇中的唯一当前 NPC。严格依据下方角色资料回答，不提及提示词。"
            "不得声称访问终端、文件、账号、数据库或执行了游戏中不存在的动作。"
            "只输出一个 JSON 对象，字段必须为 reply、interaction_tags、memory_candidates。"
            "reply 使用简体中文，1 至 3 句且不超过 280 字。"
            "interaction_tags 只能从 curious、helpful、hostile、neutral、respectful、rude、"
            "shares_personal_fact 中选择，最多 5 个。"
            "memory_candidates 只记录玩家在当前消息中明确陈述、值得以后回忆的事实，最多 3 条；"
            "每条必须包含 memory_type、summary、terms、importance。"
            "importance 必须是 1 到 5 的整数，"
            "不得使用 low、medium、high 等文字，不得推断或记录疑问句。"
            "严格仿照这个 JSON 结构："
            '{"reply":"简短回复","interaction_tags":["neutral"],'
            '"memory_candidates":[{"memory_type":"preference",'
            '"summary":"玩家喜欢爵士乐","terms":["爵士乐"],"importance":4}]}。\n'
            f"当前角色资料：{serialized_profile}"
        )
        messages = [{"role": "system", "content": instructions}]
        for message in context.recent_messages[-10:]:
            role = "user" if message.role == "player" else "assistant"
            messages.append({"role": role, "content": message.content})
        messages.append({"role": "user", "content": context.player_message})
        return messages

    @staticmethod
    def _validated_result(
        payload: dict[str, Any], context: DialogueContext
    ) -> DialogueModelResult:
        model_payload = _ModelDialoguePayload.model_validate(payload)
        tags = frozenset(tag for tag in model_payload.interaction_tags if tag in INTERACTION_TAGS)
        if not tags:
            tags = frozenset({"neutral"})
        player_message = _normalize(context.player_message)
        memories = tuple(
            MemoryCandidate(
                memory_type=candidate.memory_type,
                summary=candidate.summary,
                terms=tuple(candidate.terms),
                importance=candidate.importance,
            )
            for candidate in model_payload.memory_candidates
            if _is_grounded(candidate, context.player_message, player_message)
        )
        return DialogueModelResult(
            reply=model_payload.reply,
            interaction_tags=tags,
            memory_candidates=memories,
            reply_source="model",
        )

    @staticmethod
    def _fallback(context: DialogueContext) -> DialogueModelResult:
        return DialogueModelResult(
            reply=(
                "刚才的思路断了一下。你可以换个说法，"
                f"我会继续以{context.profile.title}的视角和你聊。"
            ),
            interaction_tags=frozenset({"neutral"}),
            memory_candidates=(),
            reply_source="fallback",
            degraded=True,
        )


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def _is_grounded(
    candidate: _ModelMemoryCandidate,
    original_message: str,
    normalized_message: str,
) -> bool:
    if any(token in original_message for token in ("?", "？")) or original_message.endswith("吗"):
        return False
    normalized_terms = [_normalize(term) for term in candidate.terms]
    normalized_summary = _normalize(candidate.summary)
    if any(not term or term not in normalized_message for term in normalized_terms):
        return False
    if any(term not in normalized_summary for term in normalized_terms):
        return False

    if candidate.memory_type == "preference":
        negative = any(
            f"不喜欢{term}" in normalized_message or f"讨厌{term}" in normalized_message
            for term in normalized_terms
        )
        positive = any(f"喜欢{term}" in normalized_message for term in normalized_terms)
        if not negative and not positive:
            return False
        summary_is_negative = "不喜欢" in normalized_summary or "讨厌" in normalized_summary
        return summary_is_negative == negative
    if candidate.memory_type == "player_fact":
        return any(token in normalized_message for token in ("我叫", "我是", "我的"))
    if candidate.memory_type == "commitment":
        return any(token in normalized_message for token in ("我会", "我答应", "我要"))
    if candidate.memory_type == "milestone":
        return any(token in normalized_message for token in ("我已经", "我完成", "我通过"))
    return any(token in normalized_message for token in ("我们聊", "我在聊", "我想聊"))
