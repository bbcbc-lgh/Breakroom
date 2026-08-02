from CyberTown.Config import APP_VERSION, Settings
from CyberTown.main import create_app


def test_create_app_keeps_explicit_settings() -> None:
    settings = Settings(port=8877, dialogue_mode="mock")

    app = create_app(settings)

    assert app.version == APP_VERSION
    assert app.state.settings is settings
