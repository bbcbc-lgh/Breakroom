from __future__ import annotations

import argparse
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

import uvicorn
from fastapi import FastAPI

from src.Agent.MockDialogueModelClient import MockDialogueModelClient
from src.Agent.NPCContextBuilder import NPCContextBuilder
from src.Agent.NPCDialogueAgent import NPCDialogueAgent
from src.Agent.OpenAICompatibleDialogueModelClient import (
    OpenAICompatibleDialogueModelClient,
)
from src.API.DialogueRouter import router as dialogue_router
from src.API.ErrorHandler import register_error_handlers
from src.API.HealthRouter import router as health_router
from src.API.NPCRouter import router as npc_router
from src.Config import APP_VERSION, Settings, get_settings
from src.Infrastructure.NPCConfigLoader import NPCConfigLoader
from src.Observability.Logging import configure_logging
from src.Observability.RequestContext import (
    new_request_id,
    reset_request_id,
    set_request_id,
)
from src.Repository.Database import Database
from src.Repository.DialogueRepository import DialogueRepository
from src.Repository.MemoryRepository import MemoryRepository
from src.Repository.RelationshipRepository import RelationshipRepository
from src.RuntimeStreams import ensure_standard_streams
from src.Service.DialogueService import DialogueService
from src.Service.MemoryService import MemoryService
from src.Service.NPCService import NPCService
from src.Service.RelationshipService import RelationshipService

logger = logging.getLogger("CyberTown.API")


def _valid_port(value: str) -> int:
    port = int(value)
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1024 and 65535")
    return port


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    document = NPCConfigLoader().load(app_settings.content_path)
    npc_service = NPCService(document)
    if app_settings.dialogue_mode == "model":
        model_client = OpenAICompatibleDialogueModelClient(
            base_url=app_settings.model_base_url,
            model_name=app_settings.model_name,
            api_key=app_settings.model_api_key.get_secret_value(),
            timeout_seconds=app_settings.model_timeout_seconds,
        )
    else:
        model_client = MockDialogueModelClient()
    dialogue_agent = NPCDialogueAgent(model_client)
    database = Database(app_settings.database_path)
    dialogue_repository = DialogueRepository()
    relationship_repository = RelationshipRepository()
    memory_service = MemoryService(MemoryRepository())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await database.initialize()
        yield

    app = FastAPI(
        title="赛博小镇后端服务",
        description="Cyber Town local NPC dialogue backend",
        version=APP_VERSION,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.database = database
    app.state.npc_service = npc_service
    app.state.dialogue_service = DialogueService(
        database=database,
        npc_service=npc_service,
        context_builder=NPCContextBuilder(),
        dialogue_agent=dialogue_agent,
        dialogue_repository=dialogue_repository,
        relationship_repository=relationship_repository,
        memory_service=memory_service,
        relationship_service=RelationshipService(),
    )

    @app.middleware("http")
    async def request_context(request, call_next):
        request_id = new_request_id()
        request.state.request_id = request_id
        token = set_request_id(request_id)
        started_at = perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request completed",
                extra={
                    "details": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": round((perf_counter() - started_at) * 1000),
                    }
                },
            )
            return response
        except Exception:
            logger.error(
                "request failed",
                extra={
                    "details": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": 500,
                        "duration_ms": round((perf_counter() - started_at) * 1000),
                        "error_code": "INTERNAL_ERROR",
                        "retryable": True,
                    }
                },
            )
            raise
        finally:
            reset_request_id(token)

    app.include_router(health_router)
    app.include_router(npc_router)
    app.include_router(dialogue_router)
    register_error_handlers(app)
    return app


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cyber Town local backend")
    parser.add_argument("--host")
    parser.add_argument("--port", type=_valid_port)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--content-path", type=Path)
    parser.add_argument("--dialogue-mode", choices=("mock", "model"))
    return parser.parse_args(argv)


def _settings_from_args(args: argparse.Namespace) -> Settings:
    settings = get_settings()
    overrides = {
        name: value
        for name, value in {
            "host": args.host,
            "port": args.port,
            "data_dir": args.data_dir,
            "content_path": args.content_path,
            "dialogue_mode": args.dialogue_mode,
        }.items()
        if value is not None
    }
    return Settings.model_validate({**settings.model_dump(), **overrides})


def run(argv: list[str] | None = None) -> None:
    ensure_standard_streams()
    settings = _settings_from_args(_parse_args(argv))
    configure_logging(settings.log_dir)
    runtime_app = create_app(settings)
    uvicorn.run(runtime_app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
