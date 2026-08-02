from fastapi import APIRouter, Request

from CyberTown.API.ErrorHandler import PublicError
from CyberTown.Observability.RequestContext import get_request_id
from CyberTown.Schema.DialogueSchema import (
    DialogueNPCResponse,
    DialogueRequest,
    DialogueResponse,
    RelationshipResponse,
)
from CyberTown.Service.NPCService import NPCNotFoundError

router = APIRouter(prefix="/api/v1", tags=["dialogue"])


@router.post("/dialogues", response_model=DialogueResponse)
async def create_dialogue(payload: DialogueRequest, request: Request) -> DialogueResponse:
    try:
        result = await request.app.state.dialogue_service.create_dialogue(
            request_id=get_request_id(),
            client_request_id=str(payload.client_request_id),
            player_id=payload.player_id,
            npc_id=payload.npc_id,
            message=payload.message,
        )
    except NPCNotFoundError as exc:
        raise PublicError(404, "NPC_NOT_FOUND", "没有找到这个角色。", retryable=False) from exc

    return DialogueResponse(
        request_id=result.request_id,
        client_request_id=result.client_request_id,
        npc=DialogueNPCResponse(
            npc_id=result.profile.npc_id,
            name=result.profile.name,
            title=result.profile.title,
        ),
        reply=result.reply,
        reply_source=result.reply_source,
        relationship=RelationshipResponse(
            score=result.relationship.score,
            level=result.relationship.level,
            delta=result.relationship.delta,
            reason=result.relationship.reason,
        ),
        memory_saved=result.memory_saved,
        degraded=result.degraded,
        created_at=result.created_at,
    )
