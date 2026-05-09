"""Parse a Markdown skill file into a SkillSpec."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from investment_tracker.skills.spec import AISettings, PreToolStep, SkillSpec


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)
_SECTION_RE = re.compile(r"^#\s+(System|Prompt)\s*$", re.MULTILINE)


class SkillLoadError(ValueError):
    """Raised when a skill MD file is malformed."""


def load_spec(path: str | Path) -> SkillSpec:
    """Load a single Markdown skill file into a SkillSpec."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return parse_spec(text, source_path=str(path))


def parse_spec(text: str, *, source_path: Optional[str] = None) -> SkillSpec:
    """Parse a skill MD string into a SkillSpec."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise SkillLoadError("missing YAML frontmatter delimited by '---' lines")

    frontmatter_yaml, body = match.group(1), match.group(2)
    try:
        frontmatter = yaml.safe_load(frontmatter_yaml) or {}
    except yaml.YAMLError as exc:
        raise SkillLoadError(f"invalid YAML frontmatter: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise SkillLoadError("frontmatter must be a mapping")

    name = frontmatter.get("name")
    if not name:
        raise SkillLoadError("frontmatter must include 'name'")

    sections = _split_sections(body)
    system_prompt = sections.get("System", "").strip()
    user_prompt = sections.get("Prompt", "").strip()
    if not user_prompt:
        raise SkillLoadError(f"skill '{name}' must have a non-empty '# Prompt' section")

    return SkillSpec(
        name=name,
        description=frontmatter.get("description", ""),
        version=str(frontmatter.get("version", "0.1.0")),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        input_schema=frontmatter.get("input_schema", {}) or {},
        output_schema=frontmatter.get("output_schema", {}) or {},
        pre_tools=_parse_pre_tools(frontmatter.get("pre_tools", []) or []),
        ai=_parse_ai(frontmatter.get("ai", {}) or {}),
        source_path=source_path,
    )


def load_specs_from_dir(path: str | Path) -> List[SkillSpec]:
    """Load every *.md file in a directory as a SkillSpec."""
    path = Path(path)
    if not path.is_dir():
        raise SkillLoadError(f"skill spec directory not found: {path}")
    return [load_spec(file) for file in sorted(path.glob("*.md"))]


def _split_sections(body: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    for index, match in enumerate(matches):
        heading = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[heading] = body[start:end]
    return sections


def _parse_pre_tools(items: Any) -> List[PreToolStep]:
    if not isinstance(items, list):
        raise SkillLoadError("pre_tools must be a list")
    steps: List[PreToolStep] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise SkillLoadError(f"pre_tools[{index}] must be a mapping")
        if "tool" not in item:
            raise SkillLoadError(f"pre_tools[{index}] is missing 'tool'")
        steps.append(
            PreToolStep(
                tool=item["tool"],
                args=item.get("args", {}) or {},
                when=item.get("when"),
                output_var=item.get("output_var"),
                map_to_context=item.get("map_to_context", {}) or {},
                short_circuit_if=item.get("short_circuit_if"),
                short_circuit_return=item.get("short_circuit_return"),
            )
        )
    return steps


def _parse_ai(payload: Dict[str, Any]) -> AISettings:
    return AISettings(
        temperature=float(payload.get("temperature", 0.2)),
        max_tokens=int(payload.get("max_tokens", 2000)),
        on_failure=payload.get("on_failure", "raise"),
        on_failure_var=payload.get("on_failure_var"),
    )
