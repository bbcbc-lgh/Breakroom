import json
import logging

from CyberTown.Observability.Logging import JsonFormatter, sanitize


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
