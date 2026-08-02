from __future__ import annotations

from datetime import UTC, datetime

from CyberTown.Agent.NPCContextBuilder import NPCContextBuilder
from CyberTown.Agent.NPCDialogueAgent import NPCDialogueAgent
from CyberTown.Domain.Dialogue import DialogueResult, RelationshipResult
from CyberTown.Service.NPCService import NPCService


class DialogueService:
    def __init__(
        self,
        npc_service: NPCService,
        context_builder: NPCContextBuilder,
        dialogue_agent: NPCDialogueAgent,
    ) -> None:
        self._npc_service = npc_service
        self._context_builder = context_builder
        self._dialogue_agent = dialogue_agent

    async def create_dialogue(
        self,
        *,
        request_id: str,
        client_request_id: str,
        player_id: str,
        npc_id: str,
        message: str,
    ) -> DialogueResult:
        profile = self._npc_service.get_profile(npc_id)
        context = self._context_builder.build(
            profile=profile,
            player_id=player_id,
            player_message=message,
        )
        model_result = await self._dialogue_agent.respond(context)
        return DialogueResult(
            request_id=request_id,
            client_request_id=client_request_id,
            profile=profile,
            reply=model_result.reply,
            reply_source=model_result.reply_source,
            relationship=RelationshipResult(),
            memory_saved=False,
            degraded=model_result.degraded,
            created_at=datetime.now(UTC),
            interaction_tags=model_result.interaction_tags,
            memory_candidates=model_result.memory_candidates,
        )
