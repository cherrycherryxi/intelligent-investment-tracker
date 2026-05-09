"""Tests for skill MD loader and SkillSpec dataclass."""

from __future__ import annotations

from pathlib import Path

import pytest

from investment_tracker.skills.loader import (
    SkillLoadError,
    load_spec,
    load_specs_from_dir,
    parse_spec,
)


SPECS_DIR = Path(__file__).parent.parent / "src" / "investment_tracker" / "skills" / "specs"


def test_parse_spec_minimal() -> None:
    text = """---
name: test_skill
description: A minimal skill
version: 0.1.0
---

# Prompt

Hello {{ name }}.
"""
    spec = parse_spec(text)

    assert spec.name == "test_skill"
    assert spec.description == "A minimal skill"
    assert spec.version == "0.1.0"
    assert spec.user_prompt == "Hello {{ name }}."
    assert spec.system_prompt == ""
    assert spec.pre_tools == []


def test_parse_spec_with_system_and_pre_tools() -> None:
    text = """---
name: composed_skill
description: composed
version: 0.2.0
pre_tools:
  - tool: ocr_extract
    when: "not ocr_text"
    args:
      language: zh-CN
    output_var: ocr_extraction
    map_to_context:
      ocr_text: "{{ ocr_extraction.result.text }}"
ai:
  temperature: 0.5
  max_tokens: 1000
---

# System

You are an assistant.

# Prompt

Process: {{ ocr_text }}
"""
    spec = parse_spec(text)

    assert spec.system_prompt == "You are an assistant."
    assert len(spec.pre_tools) == 1
    pre = spec.pre_tools[0]
    assert pre.tool == "ocr_extract"
    assert pre.when == "not ocr_text"
    assert pre.args == {"language": "zh-CN"}
    assert pre.output_var == "ocr_extraction"
    assert pre.map_to_context == {"ocr_text": "{{ ocr_extraction.result.text }}"}
    assert spec.ai.temperature == 0.5
    assert spec.ai.max_tokens == 1000


def test_parse_spec_missing_frontmatter_raises() -> None:
    with pytest.raises(SkillLoadError, match="missing YAML frontmatter"):
        parse_spec("# Prompt\n\nHello.\n")


def test_parse_spec_missing_name_raises() -> None:
    text = """---
description: no name
---

# Prompt

x
"""
    with pytest.raises(SkillLoadError, match="must include 'name'"):
        parse_spec(text)


def test_parse_spec_missing_prompt_raises() -> None:
    text = """---
name: bad_skill
---

# System

just a system.
"""
    with pytest.raises(SkillLoadError, match="non-empty '# Prompt'"):
        parse_spec(text)


def test_load_specs_from_dir_returns_all_five_skills() -> None:
    specs = load_specs_from_dir(SPECS_DIR)
    names = {spec.name for spec in specs}

    assert names == {
        "ocr_parsing_skill",
        "natural_language_understanding_skill",
        "investment_advice_skill",
        "risk_assessment_skill",
        "transaction_analysis_skill",
    }


def test_load_spec_includes_source_path(tmp_path: Path) -> None:
    file = tmp_path / "x.md"
    file.write_text("---\nname: x\n---\n\n# Prompt\n\nhello\n", encoding="utf-8")
    spec = load_spec(file)
    assert spec.source_path == str(file)
