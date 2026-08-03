from __future__ import annotations

from abc import ABC, abstractmethod

from CyberTown.Domain.Dialogue import DialogueContext, DialogueModelResult


class BaseDialogueModelClient(ABC):
    @abstractmethod
    async def generate(self, context: DialogueContext) -> DialogueModelResult:
        raise NotImplementedError
