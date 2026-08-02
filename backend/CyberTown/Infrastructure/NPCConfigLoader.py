from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from CyberTown.Domain.NPCProfile import NPCProfileDocument


class NPCConfigError(ValueError):
    pass


def _format_location(location: tuple[Any, ...]) -> str:
    parts: list[str] = []
    for item in location:
        if isinstance(item, int):
            parts[-1] = f"{parts[-1]}[{item}]"
        else:
            parts.append(str(item))
    return ".".join(parts) or "document"


class NPCConfigLoader:
    def load(self, path: Path) -> NPCProfileDocument:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise NPCConfigError(f"NPC config not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise NPCConfigError(
                f"NPC config JSON error at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc

        try:
            return NPCProfileDocument.model_validate(payload)
        except ValidationError as exc:
            messages = [
                f"{_format_location(error['loc'])}: {error['msg']}" for error in exc.errors()
            ]
            raise NPCConfigError("; ".join(messages)) from exc
