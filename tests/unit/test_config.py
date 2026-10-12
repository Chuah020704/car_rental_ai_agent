"""Phase 1 smoke tests: settings load with defaults, config.yaml parses, exceptions behave."""

from app.utils.config import get_config_dict, get_settings
from app.utils.exception.exceptions import ReservationNotFoundException


def test_settings_load_with_defaults() -> None:
    settings = get_settings()
    assert settings.auth.auth_mode in {"simulated", "entra"}
    assert settings.llm.llm_provider


def test_config_yaml_has_expected_top_level_keys() -> None:
    config = get_config_dict()
    assert "SETTINGS" in config
    assert "RAG" in config
    assert "AGENT" in config


def test_app_exception_carries_detail_and_status_code() -> None:
    exc = ReservationNotFoundException(detail="R999 not found")
    assert exc.status_code == 404
    assert exc.detail == "R999 not found"
