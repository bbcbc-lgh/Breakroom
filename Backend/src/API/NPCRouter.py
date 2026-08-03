from fastapi import APIRouter, Request

from src.Schema.NPCSchema import NPCListResponse, NPCResponse, SpawnResponse

router = APIRouter(prefix="/api/v1", tags=["npcs"])


@router.get("/npcs", response_model=NPCListResponse)
async def list_npcs(request: Request) -> NPCListResponse:
    npc_service = request.app.state.npc_service
    profiles = npc_service.list_profiles()
    return NPCListResponse(
        content_version=npc_service.content_version,
        npcs=[
            NPCResponse(
                npc_id=profile.npc_id,
                name=profile.name,
                title=profile.title,
                appearance_key=profile.appearance_key,
                spawn=SpawnResponse(x=profile.spawn.x, y=profile.spawn.y),
                wander_enabled=profile.wander.enabled,
                ambient_line=profile.ambient_lines[0],
            )
            for profile in profiles
        ],
    )
