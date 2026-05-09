"""SkillRegistry: a container of SkillSpec objects keyed by name."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List

from investment_tracker.skills.loader import load_specs_from_dir
from investment_tracker.skills.spec import SkillSpec


class SkillRegistry:
    """Holds SkillSpec instances. Does not execute them."""

    def __init__(self) -> None:
        self._specs: dict[str, SkillSpec] = {}

    def register(self, spec: SkillSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"skill '{spec.name}' is already registered")
        self._specs[spec.name] = spec

    def get(self, name: str) -> SkillSpec:
        try:
            return self._specs[name]
        except KeyError as exc:
            raise KeyError(f"skill '{name}' is not registered") from exc

    def has(self, name: str) -> bool:
        return name in self._specs

    def list(self) -> List[SkillSpec]:
        return list(self._specs.values())

    def names(self) -> List[str]:
        return list(self._specs.keys())

    def __iter__(self) -> Iterator[SkillSpec]:
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)

    @classmethod
    def from_dir(cls, path: str | Path) -> "SkillRegistry":
        """Construct a registry by loading all *.md files in a directory."""
        registry = cls()
        for spec in load_specs_from_dir(path):
            registry.register(spec)
        return registry
