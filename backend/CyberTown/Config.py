from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _user_root() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    return Path(base) / "CyberTown" if base else Path.home() / ".cyber-town"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CYBER_TOWN_",
        env_file=None,
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    dialogue_mode: Literal["mock", "model"] = "mock"
    content_path: Path = PROJECT_ROOT / "Content" / "NPCProfiles.json"
    data_dir: Path = Field(default_factory=lambda: _user_root() / "Data")
    log_dir: Path = Field(default_factory=lambda: _user_root() / "Logs")
    model_base_url: str = ""
    model_name: str = ""
    model_api_key: str = ""
    model_timeout_seconds: float = Field(default=15.0, gt=0, le=60)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "CyberTown.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
