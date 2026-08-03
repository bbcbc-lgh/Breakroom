from __future__ import annotations

from CyberTown.Domain.NPCProfile import NPCProfile, NPCProfileDocument


class NPCNotFoundError(LookupError):
    pass


class NPCService:
    def __init__(self, document: NPCProfileDocument) -> None:
        self.content_version = document.content_version
        self._profiles = {profile.npc_id: profile for profile in document.npcs if profile.enabled}

    def list_profiles(self) -> list[NPCProfile]:
        return list(self._profiles.values())

    def get_profile(self, npc_id: str) -> NPCProfile:
        profile = self._profiles.get(npc_id)
        if profile is None:
            raise NPCNotFoundError(npc_id)
        return profile
