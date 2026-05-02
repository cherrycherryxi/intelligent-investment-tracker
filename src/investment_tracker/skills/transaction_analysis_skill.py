"""Skill for analyzing transaction patterns and anomalies."""

from __future__ import annotations

import json
from typing import Any, Dict

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.skills.base import BaseSkill


class TransactionAnalysisSkill(BaseSkill):
    name = "transaction_analysis_skill"
    description = "Analyze transaction history for patterns and anomalies."

    def build_system_prompt(self, payload: Dict[str, Any]) -> str:
        return "You are a transaction analysis assistant. Return JSON only."

    def build_prompt(self, payload: Dict[str, Any]) -> str:
        return (
            "Analyze the following transaction list for patterns, anomalies, and concentration risks.\n"
            f"Transactions: {json.dumps(payload['transactions'], ensure_ascii=False)}\n"
            "Return JSON with keys frequency_summary, anomalies, concentration_risk, recommendations."
        )

    def parse_response(self, content: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ToolExecutionError(
                "transaction analysis skill returned invalid JSON",
                code="invalid_skill_response",
                details={"content": content},
            ) from exc

