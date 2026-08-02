from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from CyberTown.Config import APP_VERSION, Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(
        title="赛博小镇后端服务",
        description="Cyber Town local NPC dialogue backend",
        version=APP_VERSION,
    )
    app.state.settings = app_settings
    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
