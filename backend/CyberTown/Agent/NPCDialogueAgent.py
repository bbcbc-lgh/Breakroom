from __future__ import annotations

from CyberTown.Agent.BaseDialogueModelClient import BaseDialogueModelClient
from CyberTown.Domain.Dialogue import INTERACTION_TAGS, DialogueContext, DialogueModelResult


class NPCDialogueAgent:
    def __init__(self, model_client: BaseDialogueModelClient) -> None:
        self._model_client = model_client

    async def respond(self, context: DialogueContext) -> DialogueModelResult:
        result = await self._model_client.generate(context)
        reply = result.reply.strip()
        if not reply:
            raise ValueError("dialogue model returned an empty reply")
        if len(reply) > 280:
            reply = reply[:279].rstrip() + "…"
        tags = frozenset(tag for tag in result.interaction_tags if tag in INTERACTION_TAGS)
        if not tags:
            tags = frozenset({"neutral"})
        return DialogueModelResult(
            reply=reply,
            interaction_tags=tags,
            memory_candidates=result.memory_candidates,
            reply_source=result.reply_source,
            degraded=result.degraded,
        )
