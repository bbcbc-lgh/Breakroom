from pydantic import BaseModel


class SpawnResponse(BaseModel):
    x: int
    y: int


class NPCResponse(BaseModel):
    npc_id: str
    name: str
    title: str
    appearance_key: str
    spawn: SpawnResponse
    wander_enabled: bool
    ambient_line: str


class NPCListResponse(BaseModel):
    content_version: str
    npcs: list[NPCResponse]
