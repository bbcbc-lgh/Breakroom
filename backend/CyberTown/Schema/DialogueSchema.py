from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DialogueRequest(BaseModel):
    client_request_id: UUID
    player_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    npc_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    message: str = Field(min_length=1, max_length=300)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class DialogueNPCResponse(BaseModel):
    npc_id: str
    name: str
    title: str


class RelationshipResponse(BaseModel):
    score: int
    level: str
    delta: int
    reason: str


class DialogueResponse(BaseModel):
    request_id: str
    client_request_id: str
    npc: DialogueNPCResponse
    reply: str
    reply_source: Literal["mock", "model", "fallback"]
    relationship: RelationshipResponse
    memory_saved: bool
    degraded: bool
    created_at: datetime
