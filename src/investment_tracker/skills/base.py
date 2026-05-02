"""Base abstractions for reusable AI skills."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from investment_tracker.utils.ai_client import AIClient


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    version: str
    temperature: float
    max_tokens: int


class SkillRegistry:
    """Simple registry for reusable skill instances."""

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: "BaseSkill") -> None:
        if skill.name in self._skills:
            raise ValueError(f"skill '{skill.name}' is already registered")
        self._skills[skill.name] = skill

    def get(self, name: str) -> "BaseSkill":
        return self._skills[name]

    def list_metadata(self) -> Iterable[SkillMetadata]:
        return [skill.metadata() for skill in self._skills.values()]


class BaseSkill(ABC):
    """Common contract for AI-backed reusable skills."""

    name = "base_skill"
    description = "Base skill"
    version = "0.1.0"

    def __init__(
        self,
        *,
        ai_client: Optional[AIClient] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> None:
        self.ai_client = ai_client or AIClient()
        self.temperature = temperature
        self.max_tokens = max_tokens

    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self.name,
            description=self.description,
            version=self.version,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self.build_prompt(payload)
        system_prompt = self.build_system_prompt(payload)
        response = self.ai_client.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return self.parse_response(response.content, payload)

    @abstractmethod
    def build_prompt(self, payload: Dict[str, Any]) -> str:
        """Build the user prompt."""

    def build_system_prompt(self, payload: Dict[str, Any]) -> Optional[str]:
        return None

    @abstractmethod
    def parse_response(self, content: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the model response."""

