from __future__ import annotations

import pytest

from investment_tracker.settings import AppSettings, ValidationError, get_settings


def test_default_settings_load() -> None:
    settings = AppSettings()
    assert settings.app_name == "intelligent-investment-tracker"
    assert settings.database_url.startswith("sqlite")


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "custom-tracker")
    monkeypatch.setenv("AI_MAX_TOKENS", "2048")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "custom-tracker"
    assert settings.ai_max_tokens == 2048

    get_settings.cache_clear()


def test_invalid_ocr_confidence_threshold_raises() -> None:
    with pytest.raises(ValidationError):
        AppSettings(ocr_confidence_threshold=1.5)


def test_invalid_log_level_raises() -> None:
    with pytest.raises(ValidationError):
        AppSettings(log_level="TRACE")

