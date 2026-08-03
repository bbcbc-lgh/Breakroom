from __future__ import annotations

from src.Domain.Dialogue import ConversationMessage, DialogueContext
from src.Domain.NPCProfile import NPCProfile


class NPCContextBuilder:
    def build(
        self,
        *,
        profile: NPCProfile,
        player_id: str,
        player_message: str,
        relationship_level: str = "陌生",
        recent_messages: tuple[ConversationMessage, ...] = (),
        relevant_memories: tuple[str, ...] = (),
    ) -> DialogueContext:
        return DialogueContext(
            profile=profile,
            player_id=player_id,
            player_message=player_message,
            relationship_level=relationship_level,
            recent_messages=recent_messages[-10:],
            relevant_memories=relevant_memories[:3],
        )
