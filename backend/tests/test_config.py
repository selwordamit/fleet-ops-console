from app.core.config import get_settings


def test_settings_defaults():
    s = get_settings()
    assert s.app_name == "Fleet Operations Console"
    assert s.environment == "development"
    assert s.debug is False
    assert s.api_prefix == "/api"
    assert s.database_url == "postgresql+asyncpg://fleetops:fleetops@localhost:5432/fleetops"


def test_get_settings_returns_same_instance():
    assert get_settings() is get_settings()
