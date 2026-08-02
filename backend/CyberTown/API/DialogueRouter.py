import aiosqlite
from fastapi import APIRouter, Request

from CyberTown.API.ErrorHandler import PublicError
from CyberTown.Domain.Relationship import relationship_level
from CyberTown.Observability.RequestContext import get_request_id
from CyberTown.Schema.DialogueSchema import (
    ConversationMessageResponse,
    ConversationResponse,
    DialogueNPCResponse,
    DialogueRequest,
    DialogueResponse,
    RelationshipResponse,
)
from CyberTown.Service.DialogueService import PersistenceError, RequestIdConflictError
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
    except RequestIdConflictError as exc:
        raise PublicError(
            409,
            "REQUEST_ID_CONFLICT",
            "请求标识已被其他内容使用。",
            retryable=False,
        ) from exc
    except (PersistenceError, aiosqlite.Error) as exc:
        raise PublicError(
            503,
            "DATABASE_UNAVAILABLE",
            "本次对话未能保存，请重试。",
            retryable=True,
        ) from exc

    return DialogueResponse(
        request_id=get_request_id(),
        client_request_id=result.client_request_id,
        npc=DialogueNPCResponse(
            npc_id=result.profile.npc_id,
            name=result.profile.name,
            title=result.profile.title,
        ),
        reply=result.reply,
        reply_source=result.reply_source,
        relationship=RelationshipResponse(
            score=result.relationship.new_score,
            level=result.relationship.level,
            delta=result.relationship.delta,
            reason=result.relationship.reason,
        ),
        memory_saved=result.memory_saved,
        degraded=result.degraded,
        created_at=result.created_at,
    )


@router.get("/conversations/{npc_id}", response_model=ConversationResponse)
async def get_conversation(
    npc_id: str,
    request: Request,
    player_id: str = "local-player",
    limit: int = 20,
) -> ConversationResponse:
    if not 1 <= limit <= 50:
        raise PublicError(422, "INVALID_REQUEST", "limit 必须在 1 到 50 之间。", retryable=False)
    try:
        profile, state, turns = await request.app.state.dialogue_service.conversation(
            player_id, npc_id, limit
        )
    except NPCNotFoundError as exc:
        raise PublicError(404, "NPC_NOT_FOUND", "没有找到这个角色。", retryable=False) from exc
    except (PersistenceError, aiosqlite.Error) as exc:
        raise PublicError(
            503,
            "DATABASE_UNAVAILABLE",
            "本次会话读取失败，请重试。",
            retryable=True,
        ) from exc
    messages = []
    for turn in turns:
        messages.extend(
            (
                ConversationMessageResponse(
                    message_id=f"{turn['turn_id']}:player",
                    role="player",
                    content=turn["player_message"],
                    created_at=turn["created_at"],
                ),
                ConversationMessageResponse(
                    message_id=f"{turn['turn_id']}:npc",
                    role="npc",
                    content=turn["npc_reply"],
                    created_at=turn["created_at"],
                    reply_source=turn["reply_source"],
                ),
            )
        )
    return ConversationResponse(
        npc=DialogueNPCResponse(npc_id=profile.npc_id, name=profile.name, title=profile.title),
        relationship=RelationshipResponse(
            score=state.score,
            level=relationship_level(state.score),
            delta=0,
            reason="当前关系",
        ),
        messages=messages,
    )
