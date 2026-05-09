"""SkillSpec: pure data loaded from a Markdown skill file."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PreToolStep:
    """One declarative pre-tool step in a SkillSpec."""

    tool: str
    args: Dict[str, Any] = field(default_factory=dict)
    when: Optional[str] = None
    output_var: Optional[str] = None
    map_to_context: Dict[str, str] = field(default_factory=dict)
    short_circuit_if: Optional[str] = None
    short_circuit_return: Optional[Any] = None


@dataclass(frozen=True)
class AISettings:
    temperature: float = 0.2
    max_tokens: int = 2000
    on_failure: str = "raise"  # "raise" | "return_var"
    on_failure_var: Optional[str] = None  # dotted path inside context, e.g. "rule_result.result"


@dataclass(frozen=True)
class SkillSpec:
    """Declarative skill description loaded from a Markdown file.

    A SkillSpec is pure data. It does not know how to execute itself —
    SkillRunner is responsible for that.
    """

    name: str
    description: str
    version: str
    system_prompt: str
    user_prompt: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    pre_tools: List[PreToolStep] = field(default_factory=list)
    ai: AISettings = field(default_factory=AISettings)
    source_path: Optional[str] = None
