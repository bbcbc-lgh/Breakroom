from pathlib import Path

from CyberTown.Config import PROJECT_ROOT, Settings


def test_settings_use_safe_local_defaults() -> None:
    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.dialogue_mode == "mock"
    assert settings.content_path == PROJECT_ROOT / "Content" / "NPCProfiles.json"
    assert settings.data_dir is None
    assert settings.log_dir is None


def test_settings_accept_explicit_content_path(tmp_path: Path) -> None:
    path = tmp_path / "NPCProfiles.json"

    settings = Settings(content_path=path)

    assert settings.content_path == path
