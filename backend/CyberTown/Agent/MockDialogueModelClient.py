from __future__ import annotations

import re

from CyberTown.Agent.BaseDialogueModelClient import BaseDialogueModelClient
from CyberTown.Domain.Dialogue import DialogueContext, DialogueModelResult, MemoryCandidate


class MockDialogueModelClient(BaseDialogueModelClient):
    async def generate(self, context: DialogueContext) -> DialogueModelResult:
        tags = self._classify_tags(context.player_message)
        memories = self._extract_memories(context.player_message)
        reply = self._build_reply(context)
        return DialogueModelResult(
            reply=reply,
            interaction_tags=frozenset(tags),
            memory_candidates=tuple(memories),
            reply_source="mock",
        )

    def _build_reply(self, context: DialogueContext) -> str:
        message = context.player_message
        memory_hint = (
            f"我记得你提过{context.relevant_memories[0]}。" if context.relevant_memories else ""
        )
        if context.profile.npc_id == "zhang_xu":
            return (
                f"{memory_hint}先把边界说清楚：你提到“{message[:36]}”。"
                "建议先定义一个可复现的最小例子，再用测试确认结果。"
            )
        if context.profile.npc_id == "fan_yueyi":
            return (
                f"{memory_hint}我先确认一下：你现在最想解决的是“{message[:32]}”带来的什么问题？"
                "把目标用户和成功标准定下来，我们就能排优先级。"
            )
        return (
            f"{memory_hint}从体验层级看，“{message[:34]}”需要先明确最重要的信息。"
            "我会先保证它清楚可读，再用颜色和动效补充反馈。"
        )

    def _classify_tags(self, message: str) -> set[str]:
        normalized = message.casefold()
        tags: set[str] = set()
        if any(token in normalized for token in ("谢谢", "感谢", "请", "麻烦")):
            tags.add("respectful")
        question_tokens = ("帮", "建议", "怎么", "如何", "为什么", "?", "？")
        if any(token in normalized for token in question_tokens):
            tags.add("curious")
        if any(token in normalized for token in ("笨", "滚", "讨厌", "垃圾")):
            tags.add("rude")
        if any(token in normalized for token in ("威胁", "伤害", "毁掉")):
            tags.add("hostile")
        if self._extract_memories(message):
            tags.add("shares_personal_fact")
        if not tags:
            tags.add("neutral")
        return tags

    def _extract_memories(self, message: str) -> list[MemoryCandidate]:
        patterns = (
            ("player_fact", r"我叫([^，。！？,.!?]{1,20})", "玩家叫{}"),
            ("preference", r"我喜欢([^，。！？,.!?]{1,30})", "玩家喜欢{}"),
            ("preference", r"我不喜欢([^，。！？,.!?]{1,30})", "玩家不喜欢{}"),
        )
        candidates: list[MemoryCandidate] = []
        for memory_type, pattern, template in patterns:
            match = re.search(pattern, message)
            if not match:
                continue
            value = match.group(1).strip()
            candidates.append(
                MemoryCandidate(
                    memory_type=memory_type,
                    summary=template.format(value),
                    terms=(value,),
                    importance=4,
                )
            )
        return candidates
