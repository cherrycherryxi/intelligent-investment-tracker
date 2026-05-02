"""Skill for assessing portfolio risk."""

from __future__ import annotations

import json
from typing import Any, Dict

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.skills.base import BaseSkill


class RiskAssessmentSkill(BaseSkill):
    name = "risk_assessment_skill"
    description = "Assess portfolio risk level and drivers."

    def build_system_prompt(self, payload: Dict[str, Any]) -> str:
        return "You are a portfolio risk assessment assistant. Return JSON only."

    def build_prompt(self, payload: Dict[str, Any]) -> str:
        return (
            "Assess the portfolio risk.\n"
            f"Positions: {json.dumps(payload['positions'], ensure_ascii=False)}\n"
            f"Volatility data: {json.dumps(payload.get('volatility_data', {}), ensure_ascii=False)}\n"
            "Return JSON with keys risk_level, factors, diversification_suggestions."
        )

    def parse_response(self, content: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ToolExecutionError(
                "risk assessment skill returned invalid JSON",
                code="invalid_skill_response",
                details={"content": content},
            ) from exc

