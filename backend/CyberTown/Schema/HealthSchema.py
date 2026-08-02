from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["starting", "ready", "degraded"]
    version: str
    dialogue_mode: Literal["mock", "model"]
    database_ready: bool
    content_version: str
