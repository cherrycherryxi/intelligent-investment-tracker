"""Tests for SkillRegistry."""

from __future__ import annotations

from pathlib import Path

import pytest

from investment_tracker.skills.loader import parse_spec
from investment_tracker.skills.registry import SkillRegistry


SPECS_DIR = Path(__file__).parent.parent / "src" / "investment_tracker" / "skills" / "specs"


def _make_spec(name: str):
    return parse_spec(f"---\nname: {name}\n---\n\n# Prompt\n\nhello\n")


def test_register_and_get() -> None:
    registry = SkillRegistry()
    registry.register(_make_spec("alpha"))
    assert registry.has("alpha")
    assert registry.get("alpha").name == "alpha"


def test_duplicate_registration_raises() -> None:
    registry = SkillRegistry()
    registry.register(_make_spec("alpha"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_make_spec("alpha"))


def test_get_unknown_raises_key_error() -> None:
    registry = SkillRegistry()
    with pytest.raises(KeyError, match="not registered"):
        registry.get("missing")


def test_from_dir_loads_specs_directory() -> None:
    registry = SkillRegistry.from_dir(SPECS_DIR)
    assert len(registry) == 5
    assert registry.has("investment_advice_skill")
    assert registry.has("ocr_parsing_skill")
    assert "natural_language_understanding_skill" in registry.names()
