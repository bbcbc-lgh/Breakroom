import json
import os
import subprocess
import sys

import pytest
from pydantic import SecretStr

from src.Config import APP_VERSION, Settings
from src.main import _parse_args, _settings_from_args, create_app
from src.RuntimeStreams import ensure_standard_streams


def test_create_app_keeps_explicit_settings() -> None:
    settings = Settings(port=8877, dialogue_mode="mock")

    app = create_app(settings)

    assert app.version == APP_VERSION
    assert app.state.settings is settings


def test_windowed_backend_restores_missing_standard_streams(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    ensure_standard_streams()

    assert sys.stdout is not None
    assert sys.stderr is not None
    sys.stdout.close()
    sys.stderr.close()


def test_command_line_overrides_runtime_paths(tmp_path) -> None:
    content_path = tmp_path / "NPCProfiles.json"
    data_dir = tmp_path / "Data"
    args = _parse_args(
        [
            "--host",
            "127.0.0.1",
            "--port",
            "8877",
            "--data-dir",
            str(data_dir),
            "--content-path",
            str(content_path),
            "--dialogue-mode",
            "mock",
        ]
    )

    settings = _settings_from_args(args)

    assert settings.port == 8877
    assert settings.data_dir == data_dir
    assert settings.content_path == content_path
    assert settings.dialogue_mode == "mock"


def test_command_line_rejects_privileged_port() -> None:
    with pytest.raises(SystemExit):
        _parse_args(["--port", "80"])


def test_command_line_model_mode_without_model_config_falls_back_to_mock(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "src.main.get_settings",
        lambda: Settings(
            dialogue_mode="mock",
            model_base_url="",
            model_name="",
            model_api_key=SecretStr(""),
        ),
    )

    settings = _settings_from_args(_parse_args(["--dialogue-mode", "model"]))

    assert settings.dialogue_mode == "mock"


def test_command_line_overrides_preserve_complete_model_config(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.main.get_settings",
        lambda: Settings(
            dialogue_mode="model",
            model_base_url="https://model.example/v1",
            model_name="test-model",
            model_api_key=SecretStr("test-key"),
        ),
    )

    settings = _settings_from_args(_parse_args(["--port", "8877"]))

    assert settings.dialogue_mode == "model"
    assert settings.model_base_url == "https://model.example/v1"
    assert settings.model_name == "test-model"
    assert settings.model_api_key.get_secret_value() == "test-key"


def test_backend_entrypoint_uses_cli_content_before_creating_app(tmp_path) -> None:
    source = Settings().content_path
    content_path = tmp_path / "NPCProfiles.json"
    data_dir = tmp_path / "Data"
    argv = [
        "RunBackend.py",
        "--content-path",
        str(content_path),
        "--data-dir",
        str(data_dir),
        "--dialogue-mode",
        "mock",
    ]
    content_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    probe = "; ".join(
        (
            "import json, runpy, sys, uvicorn",
            (
                "uvicorn.run=lambda app, **kwargs: print(json.dumps("
                "{'content_path': str(app.state.settings.content_path), "
                "'mode': app.state.settings.dialogue_mode}, ensure_ascii=False))"
            ),
            f"sys.argv={argv!r}",
            "runpy.run_path('RunBackend.py', run_name='__main__')",
        )
    )
    environment = os.environ.copy()
    environment["CYBER_TOWN_CONTENT_PATH"] = str(tmp_path / "missing.json")

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Settings().content_path.parents[1] / "backend",
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload == {"content_path": str(content_path), "mode": "mock"}
