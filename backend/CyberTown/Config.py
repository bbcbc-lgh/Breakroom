from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
    data_dir: Path | None = None
    log_dir: Path | None = None
    model_base_url: str = ""
    model_name: str = ""
    model_api_key: str = ""
    model_timeout_seconds: float = Field(default=15.0, gt=0, le=60)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
