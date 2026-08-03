from __future__ import annotations

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
ToneText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
RELATIONSHIP_LEVELS = {"陌生", "熟悉", "友好", "亲密", "挚友"}
APPEARANCE_KEYS = {"engineer_teal", "planner_amber", "designer_coral"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SpawnPoint(StrictModel):
    x: int = Field(ge=0, le=1280)
    y: int = Field(ge=0, le=720)


class PauseSeconds(StrictModel):
    minimum: float = Field(alias="min", ge=0.5, le=30)
    maximum: float = Field(alias="max", ge=0.5, le=30)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.minimum > self.maximum:
            raise ValueError("min must not exceed max")
        return self


class WanderConfig(StrictModel):
    enabled: bool
    radius: int = Field(ge=0, le=160)
    speed: float = Field(gt=0, le=120)
    pause_seconds: PauseSeconds


class NPCProfile(StrictModel):
    npc_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    enabled: bool
    name: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=40)
    personality: list[ShortText] = Field(min_length=1, max_length=8)
    speech_style: str = Field(min_length=1, max_length=160)
    background: str = Field(min_length=1, max_length=300)
    preferred_topics: list[ShortText] = Field(default_factory=list, max_length=12)
    boundaries: list[ShortText] = Field(min_length=1, max_length=12)
    relationship_tone: dict[str, ToneText]
    appearance_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    spawn: SpawnPoint
    wander: WanderConfig
    ambient_lines: list[ShortText] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_relationship_tone(self) -> Self:
        levels = set(self.relationship_tone)
        if levels != RELATIONSHIP_LEVELS:
            missing = sorted(RELATIONSHIP_LEVELS - levels)
            extra = sorted(levels - RELATIONSHIP_LEVELS)
            raise ValueError(f"relationship_tone mismatch: missing={missing}, extra={extra}")
        return self

    @model_validator(mode="after")
    def validate_appearance_key(self) -> Self:
        if self.appearance_key not in APPEARANCE_KEYS:
            raise ValueError(f"unknown appearance_key: {self.appearance_key}")
        return self


class NPCProfileDocument(StrictModel):
    schema_version: int = Field(ge=1, le=1)
    content_version: str = Field(min_length=1, max_length=32)
    npcs: list[NPCProfile] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        ids = [npc.npc_id for npc in self.npcs]
        duplicates = sorted({npc_id for npc_id in ids if ids.count(npc_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate npc_id values: {duplicates}")
        return self
