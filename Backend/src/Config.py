from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"
APP_DIR_NAME = "Breakroom"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 旧版本（CyberTown）的用户数据目录、数据库和日志文件名，仅用于一次性迁移。
_LEGACY_ROOT_NAMES = ("CyberTown", ".cyber-town")
_LEGACY_ARTIFACTS = (
    ("Data", "CyberTown.db", f"{APP_DIR_NAME}.db"),
    ("Logs", "CyberTown.log", f"{APP_DIR_NAME}.log"),
)


def _rename_artifact(source: Path, target: Path) -> None:
    if not source.exists() or target.exists():
        return
    try:
        source.rename(target)
    except OSError:
        shutil.copy2(source, target)


def _migrate_legacy_root(root: Path) -> None:
    """把旧版本的用户目录整体迁移到新目录，迁移失败时保留原数据并继续启动。"""
    if root.exists():
        return
    for name in _LEGACY_ROOT_NAMES:
        legacy = root.parent / name
        if not legacy.is_dir():
            continue
        try:
            legacy.rename(root)
        except OSError:
            shutil.copytree(legacy, root, dirs_exist_ok=True)
        break
    if not root.is_dir():
        return
    for folder, legacy_name, current_name in _LEGACY_ARTIFACTS:
        _rename_artifact(root / folder / legacy_name, root / folder / current_name)


def _user_root() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    root = Path(base) / APP_DIR_NAME if base else Path.home() / f".{APP_DIR_NAME.lower()}"
    _migrate_legacy_root(root)
    return root


def _env_path() -> Path:
    if getattr(sys, "frozen", False):
        return _user_root() / ".env"
    return PROJECT_ROOT / "Backend" / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BREAKROOM_",
        env_file=None,
        extra="ignore",
        populate_by_name=True,
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    dialogue_mode: Literal["mock", "model"] = "mock"
    content_path: Path = PROJECT_ROOT / "Content" / "NPCProfiles.json"
    data_dir: Path = Field(default_factory=lambda: _user_root() / "Data")
    log_dir: Path = Field(default_factory=lambda: _user_root() / "Logs")
    model_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("BREAKROOM_MODEL_BASE_URL", "LLM_BASE_URL"),
    )
    model_name: str = Field(
        default="",
        validation_alias=AliasChoices("BREAKROOM_MODEL_NAME", "LLM_MODEL_ID"),
    )
    model_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("BREAKROOM_MODEL_API_KEY", "LLM_API_KEY"),
    )
    model_timeout_seconds: float = Field(default=15.0, gt=0, le=60)

    @model_validator(mode="after")
    def resolve_dialogue_mode(self) -> Settings:
        configured = bool(
            self.model_base_url.strip()
            and self.model_name.strip()
            and self.model_api_key.get_secret_value().strip()
        )
        if "dialogue_mode" not in self.model_fields_set and configured:
            self.dialogue_mode = "model"
        elif self.dialogue_mode == "model" and not configured:
            self.dialogue_mode = "mock"
        return self

    @property
    def database_path(self) -> Path:
        return self.data_dir / "Breakroom.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(_env_file=_env_path(), _env_file_encoding="utf-8")
