from __future__ import annotations

import json
import logging

from investment_tracker.settings import AppSettings
from investment_tracker.utils.logger import configure_logging, get_logger


def test_configure_logging_creates_log_file(tmp_path) -> None:
    settings = AppSettings(log_dir=str(tmp_path), log_filename="test.log", environment="test")
    configure_logging(settings)
    logger = get_logger("tests.logger")

    logger.info("hello")

    log_file = tmp_path / "test.log"
    assert log_file.exists()

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[-1])
    assert payload["message"] == "hello"
    assert payload["environment"] == "test"


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("investment_tracker.tests")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "investment_tracker.tests"

