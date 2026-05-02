"""Skill for extracting transaction parameters from natural language."""

from __future__ import annotations

import json
from typing import Any, Dict

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.skills.base import BaseSkill


class NaturalLanguageUnderstandingSkill(BaseSkill):
    name = "natural_language_understanding_skill"
    description = "Extract structured transaction parameters from natural language."

    def build_system_prompt(self, payload: Dict[str, Any]) -> str:
        return "You are a financial NLU assistant. Return JSON only."

    def build_prompt(self, payload: Dict[str, Any]) -> str:
        return (
            "Extract trade parameters from the user input.\n"
            f"User input: {payload['text']}\n"
            "Return JSON with keys asset_code, direction, quantity, unit_price, trade_time, missing_fields."
        )

    def parse_response(self, content: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ToolExecutionError(
                "NLU skill returned invalid JSON",
                code="invalid_skill_response",
                details={"content": content},
            ) from exc

