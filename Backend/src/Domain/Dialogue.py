from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from src.Domain.NPCProfile import NPCProfile
from src.Domain.Relationship import RelationshipDecision

ReplySource = Literal["mock", "model", "fallback"]
INTERACTION_TAGS = {
    "curious",
    "helpful",
    "hostile",
    "neutral",
    "respectful",
    "rude",
    "shares_personal_fact",
}


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: Literal["player", "npc"]
    content: str


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    memory_type: Literal["player_fact", "preference", "shared_topic", "commitment", "milestone"]
    summary: str
    terms: tuple[str, ...]
    importance: int


@dataclass(frozen=True, slots=True)
class DialogueContext:
    profile: NPCProfile
    player_id: str
    player_message: str
    relationship_level: str
    recent_messages: tuple[ConversationMessage, ...] = ()
    relevant_memories: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DialogueModelResult:
    reply: str
    interaction_tags: frozenset[str] = frozenset({"neutral"})
    memory_candidates: tuple[MemoryCandidate, ...] = ()
    reply_source: ReplySource = "mock"
    degraded: bool = False


@dataclass(frozen=True, slots=True)
class DialogueResult:
    request_id: str
    client_request_id: str
    profile: NPCProfile
    reply: str
    reply_source: ReplySource
    relationship: RelationshipDecision
    memory_saved: bool
    degraded: bool
    created_at: datetime
    interaction_tags: frozenset[str] = field(repr=False)
    memory_candidates: tuple[MemoryCandidate, ...] = field(repr=False)
