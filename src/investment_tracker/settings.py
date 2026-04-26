"""Application settings with environment-first configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import ValidationError, field_validator

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - fallback for restricted environments
    from pydantic import BaseSettings  # type: ignore

    SettingsConfigDict = dict  # type: ignore


def _load_dotenv_into_environ(dotenv_path: Path) -> None:
    """Load simple KEY=VALUE pairs without requiring python-dotenv."""
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _normalize_boolean_env(var_name: str, default: str = "false") -> None:
    raw_value = os.environ.get(var_name)
    if raw_value is None:
        return

    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        os.environ[var_name] = "true"
        return
    if normalized in {"0", "false", "no", "off", ""}:
        os.environ[var_name] = "false"
        return

    os.environ[var_name] = default


_load_dotenv_into_environ(Path(".env"))
_normalize_boolean_env("DEBUG")
_normalize_boolean_env("DATABASE_ECHO")
_normalize_boolean_env("LOG_JSON", default="true")


class AppSettings(BaseSettings):
    """Central application settings."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    app_name: str = "intelligent-investment-tracker"
    environment: Literal["local", "test", "dev", "prod"] = "local"
    debug: bool = False

    database_url: str = "sqlite:///./investment_tracker.db"
    database_echo: bool = False

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_dir: str = "logs"
    log_filename: str = "app.log"
    log_json: bool = True

    ocr_provider: Literal["tesseract", "baidu", "tencent"] = "tesseract"
    ocr_confidence_threshold: float = 0.8
    baidu_ocr_api_key: Optional[str] = None
    baidu_ocr_secret_key: Optional[str] = None
    tencent_ocr_secret_id: Optional[str] = None
    tencent_ocr_secret_key: Optional[str] = None

    exchange_rate_primary_url: Optional[str] = None
    exchange_rate_fallback_url: Optional[str] = None
    exchange_rate_cache_ttl_seconds: int = 900

    ai_provider: Literal["claude", "deepseek"] = "deepseek"
    ai_model_name: str = "deepseek-reasoner"
    ai_temperature: float = 0.2
    ai_max_tokens: int = 4000
    ai_api_key: Optional[str] = None

    @field_validator("debug", "database_echo", "log_json", mode="before")
    @classmethod
    def normalize_bool_values(cls, value):  # type: ignore[no-untyped-def]
        if isinstance(value, bool) or value is None:
            return value

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("database_url must not be empty")
        return value

    @field_validator("ocr_confidence_threshold")
    @classmethod
    def validate_ocr_confidence_threshold(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("ocr_confidence_threshold must be between 0 and 1")
        return value

    @field_validator("ai_temperature")
    @classmethod
    def validate_ai_temperature(cls, value: float) -> float:
        if not 0 <= value <= 2:
            raise ValueError("ai_temperature must be between 0 and 2")
        return value


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return a cached settings instance."""
    return AppSettings()


__all__ = ["AppSettings", "ValidationError", "get_settings"]
