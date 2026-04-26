"""Structured logging configuration."""

from __future__ import annotations

import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict

from investment_tracker.settings import AppSettings

try:
    from pythonjsonlogger.json import JsonFormatter as _JsonFormatter
except ImportError:  # pragma: no cover - fallback for restricted environments
    class _JsonFormatter(logging.Formatter):
        """Minimal JSON formatter compatible with project tests."""

        def format(self, record: logging.LogRecord) -> str:
            payload: Dict[str, Any] = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "line": record.lineno,
            }
            if hasattr(record, "environment"):
                payload["environment"] = record.environment
            return json.dumps(payload, ensure_ascii=True)


class EnvironmentFilter(logging.Filter):
    """Attach environment metadata to each record."""

    def __init__(self, environment: str) -> None:
        super().__init__()
        self.environment = environment

    def filter(self, record: logging.LogRecord) -> bool:
        record.environment = self.environment
        return True


def _build_formatter(settings: AppSettings) -> logging.Formatter:
    if settings.log_json:
        return _JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(module)s %(lineno)d %(environment)s"
        )

    return logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s (%(module)s:%(lineno)d, env=%(environment)s)"
    )


def configure_logging(settings: AppSettings) -> None:
    """Configure root logger with console and rotating file handlers."""
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = _build_formatter(settings)
    env_filter = EnvironmentFilter(settings.environment)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(env_filter)

    file_handler = TimedRotatingFileHandler(
        filename=log_dir / settings.log_filename,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(env_filter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)


__all__ = ["configure_logging", "get_logger"]
