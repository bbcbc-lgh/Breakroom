from fastapi import APIRouter, Request

from CyberTown.Config import APP_VERSION
from CyberTown.Schema.HealthSchema import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ready",
        version=APP_VERSION,
        dialogue_mode=request.app.state.settings.dialogue_mode,
        database_ready=False,
        content_version=request.app.state.npc_service.content_version,
    )
