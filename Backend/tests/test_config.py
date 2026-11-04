from pathlib import Path

from pydantic import SecretStr

from src.Config import PROJECT_ROOT, Settings, _env_path


def test_settings_use_safe_local_defaults() -> None:
    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.dialogue_mode == "mock"
    assert settings.content_path == PROJECT_ROOT / "Content" / "NPCProfiles.json"
    assert settings.data_dir.name == "Data"
    assert settings.log_dir.name == "Logs"
    assert settings.database_path == settings.data_dir / "Breakroom.db"


def test_settings_accept_explicit_content_path(tmp_path: Path) -> None:
    path = tmp_path / "NPCProfiles.json"

    settings = Settings(content_path=path)

    assert settings.content_path == path


def test_settings_accept_existing_llm_environment_names(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://model.example/v1")
    monkeypatch.setenv("LLM_MODEL_ID", "model-name")
    monkeypatch.setenv("LLM_API_KEY", "test-secret")

    settings = Settings()

    assert settings.dialogue_mode == "model"
    assert settings.model_base_url == "https://model.example/v1"
    assert settings.model_name == "model-name"
    assert isinstance(settings.model_api_key, SecretStr)
    assert "test-secret" not in repr(settings)


def test_explicit_mock_mode_wins_over_complete_model_configuration() -> None:
    settings = Settings(
        dialogue_mode="mock",
        model_base_url="https://model.example/v1",
        model_name="model-name",
        model_api_key="test-secret",
    )

    assert settings.dialogue_mode == "mock"


def test_incomplete_model_configuration_falls_back_to_mock() -> None:
    settings = Settings(dialogue_mode="model", model_name="model-name")

    assert settings.dialogue_mode == "mock"


def test_frozen_backend_reads_user_env(monkeypatch) -> None:
    monkeypatch.setattr("src.Config.sys.frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", "C:/Users/test/AppData/Roaming")

    assert _env_path() == Path("C:/Users/test/AppData/Roaming/Breakroom/.env")


def test_legacy_user_data_is_migrated(monkeypatch, tmp_path: Path) -> None:
    appdata = tmp_path / "Roaming"
    legacy_data = appdata / "CyberTown" / "Data"
    legacy_logs = appdata / "CyberTown" / "Logs"
    legacy_data.mkdir(parents=True)
    legacy_logs.mkdir(parents=True)
    (legacy_data / "CyberTown.db").write_bytes(b"legacy-db")
    (legacy_logs / "CyberTown.log").write_text("legacy-log", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(appdata))

    settings = Settings()

    assert settings.data_dir == appdata / "Breakroom" / "Data"
    assert (settings.data_dir / "Breakroom.db").read_bytes() == b"legacy-db"
    log_path = appdata / "Breakroom" / "Logs" / "Breakroom.log"
    assert log_path.read_text(encoding="utf-8") == "legacy-log"
    assert not (appdata / "CyberTown").exists()


def test_existing_user_data_is_not_overwritten(monkeypatch, tmp_path: Path) -> None:
    appdata = tmp_path / "Roaming"
    (appdata / "Breakroom" / "Data").mkdir(parents=True)
    (appdata / "Breakroom" / "Data" / "Breakroom.db").write_bytes(b"current-db")
    (appdata / "CyberTown" / "Data").mkdir(parents=True)
    (appdata / "CyberTown" / "Data" / "CyberTown.db").write_bytes(b"legacy-db")
    monkeypatch.setenv("APPDATA", str(appdata))

    settings = Settings()

    assert (settings.data_dir / "Breakroom.db").read_bytes() == b"current-db"
    legacy_db = appdata / "CyberTown" / "Data" / "CyberTown.db"
    assert legacy_db.read_bytes() == b"legacy-db"
