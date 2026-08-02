from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from CyberTown.Agent.MockDialogueModelClient import MockDialogueModelClient
from CyberTown.Agent.NPCContextBuilder import NPCContextBuilder
from CyberTown.Agent.NPCDialogueAgent import NPCDialogueAgent
from CyberTown.API.DialogueRouter import router as dialogue_router
from CyberTown.API.ErrorHandler import register_error_handlers
from CyberTown.API.HealthRouter import router as health_router
from CyberTown.API.NPCRouter import router as npc_router
from CyberTown.Config import APP_VERSION, Settings, get_settings
from CyberTown.Infrastructure.NPCConfigLoader import NPCConfigLoader
from CyberTown.Observability.Logging import configure_logging
from CyberTown.Observability.RequestContext import (
    new_request_id,
    reset_request_id,
    set_request_id,
)
from CyberTown.Service.DialogueService import DialogueService
from CyberTown.Service.NPCService import NPCService


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    document = NPCConfigLoader().load(app_settings.content_path)
    npc_service = NPCService(document)
    dialogue_agent = NPCDialogueAgent(MockDialogueModelClient())
    app = FastAPI(
        title="赛博小镇后端服务",
        description="Cyber Town local NPC dialogue backend",
        version=APP_VERSION,
    )
    app.state.settings = app_settings
    app.state.npc_service = npc_service
    app.state.dialogue_service = DialogueService(
        npc_service=npc_service,
        context_builder=NPCContextBuilder(),
        dialogue_agent=dialogue_agent,
    )

    @app.middleware("http")
    async def request_context(request, call_next):
        request_id = new_request_id()
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)

    app.include_router(health_router)
    app.include_router(npc_router)
    app.include_router(dialogue_router)
    register_error_handlers(app)
    return app


configure_logging()
app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
