import json
import logging
from pathlib import Path

from src.Observability.Logging import JsonFormatter, configure_logging, sanitize


def test_sanitize_redacts_nested_sensitive_values() -> None:
    payload = {
        "api_key": "secret",
        "nested": {"authorization": "Bearer secret", "safe": "visible"},
    }

    assert sanitize(payload) == {
        "api_key": "[REDACTED]",
        "nested": {"authorization": "[REDACTED]", "safe": "visible"},
    }


def test_json_formatter_does_not_expose_details_secret() -> None:
    record = logging.LogRecord("CyberTown", logging.INFO, "", 0, "event", (), None)
    record.details = {"model_api_key": "secret-value", "mode": "mock"}

    payload = json.loads(JsonFormatter().format(record))

    assert "secret-value" not in json.dumps(payload)
    assert payload["details"]["model_api_key"] == "[REDACTED]"


def test_configure_logging_writes_json_file(tmp_path: Path) -> None:
    logger = logging.getLogger("CyberTown")
    previous_handlers = list(logger.handlers)
    logger.handlers.clear()
    try:
        configure_logging(tmp_path)
        logging.getLogger("CyberTown.Runtime").info(
            "runtime event", extra={"details": {"mode": "mock"}}
        )
        for handler in logger.handlers:
            handler.flush()
        content = (tmp_path / "CyberTown.log").read_text(encoding="utf-8")
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers[:] = previous_handlers

    assert '"message": "runtime event"' in content
    assert '"mode": "mock"' in content


def test_configure_logging_is_idempotent_and_rotates_utf8_log(tmp_path: Path) -> None:
    logger = logging.getLogger("CyberTown")
    previous_handlers = list(logger.handlers)
    logger.handlers.clear()
    try:
        configure_logging(tmp_path)
        configure_logging(tmp_path)
        file_handlers = [
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.FileHandler)
        ]
        assert len(file_handlers) == 1
        file_handler = file_handlers[0]
        file_handler.maxBytes = 160
        for index in range(12):
            logging.getLogger("CyberTown.Runtime").info(
                "中文轮转事件 %s", index, extra={"details": {"index": index}}
            )
        file_handler.flush()
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers[:] = previous_handlers

    assert (tmp_path / "CyberTown.log.1").exists()
    combined = "".join(
        path.read_text(encoding="utf-8") for path in tmp_path.glob("CyberTown.log*")
    )
    assert "中文轮转事件" in combined
