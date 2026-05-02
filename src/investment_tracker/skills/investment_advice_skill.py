"""Skill for portfolio-level investment advice."""

from __future__ import annotations

import json
from typing import Any, Dict

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.skills.base import BaseSkill


class InvestmentAdviceSkill(BaseSkill):
    name = "investment_advice_skill"
    description = "Generate AI-based portfolio advice."

    def build_system_prompt(self, payload: Dict[str, Any]) -> str:
        return "You are a cautious investment advisor. Return JSON only."

    def build_prompt(self, payload: Dict[str, Any]) -> str:
        return (
            "Provide portfolio advice based on the following inputs.\n"
            f"Positions: {json.dumps(payload['positions'], ensure_ascii=False)}\n"
            f"Market data: {json.dumps(payload.get('market_data', {}), ensure_ascii=False)}\n"
            f"Risk preference: {payload.get('risk_preference', 'balanced')}\n"
            "Return JSON with keys summary, actions, reasoning, warnings."
        )

    def parse_response(self, content: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ToolExecutionError(
                "investment advice skill returned invalid JSON",
                code="invalid_skill_response",
                details={"content": content},
            ) from exc

