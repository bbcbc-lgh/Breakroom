from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from src.Observability.RequestContext import get_request_id

SENSITIVE_KEYS = {"api_key", "authorization", "cookie", "model_api_key", "password", "token"}


def sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if str(key).casefold() in SENSITIVE_KEYS else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [sanitize(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        if hasattr(record, "details"):
            payload["details"] = sanitize(record.details)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_dir: Path | None = None) -> None:
    logger = logging.getLogger("CyberTown")
    formatter = JsonFormatter()
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = (log_dir / "CyberTown.log").resolve()
        existing_files = {
            Path(handler.baseFilename).resolve()
            for handler in logger.handlers
            if isinstance(handler, logging.FileHandler)
        }
        if log_path not in existing_files:
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=2 * 1024 * 1024,
                backupCount=2,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
