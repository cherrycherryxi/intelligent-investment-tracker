"""Generate structured investment advice from holdings and market context."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from investment_tracker.mcp_tools.base import MCPTool, ToolExecutionError
from investment_tracker.utils.ai_client import AIClient


class AdvicePositionInput(BaseModel):
    asset_type: str
    asset_code: str
    quantity: float
    average_cost_cny: float
    current_value_cny: float
    unrealized_pnl_cny: float
    return_pct: float


class InvestmentAdvisorInput(BaseModel):
    positions: List[AdvicePositionInput]
    market_data: Dict[str, Any] = {}
    risk_preference: str = "balanced"


class InvestmentAdvisorTool(MCPTool):
    name = "generate_advice"
    description = "Generate structured investment advice using the configured AI client."
    input_model = InvestmentAdvisorInput

    def __init__(self, ai_client: Optional[AIClient] = None) -> None:
        self.ai_client = ai_client or AIClient()

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        positions = payload["positions"]
        if not positions:
            raise ToolExecutionError("positions are required", code="positions_required")

        summary = self._build_portfolio_summary(positions)
        risk_preference = payload["risk_preference"]
        market_data = payload.get("market_data", {})

        prompt = self._build_prompt(summary=summary, market_data=market_data, risk_preference=risk_preference)
        ai_response = self.ai_client.generate(
            prompt,
            system_prompt=(
                "You are a conservative investment assistant. "
                "Respond with valid JSON only."
            ),
        )
        parsed = self._parse_ai_payload(ai_response.content)

        return {
            "portfolio_summary": summary,
            "advice": parsed,
            "ai_provider": ai_response.provider,
            "model": ai_response.model,
            "token_usage": {
                "input_tokens": ai_response.input_tokens,
                "output_tokens": ai_response.output_tokens,
            },
        }

    def _build_portfolio_summary(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_cost = sum((position["current_value_cny"] - position["unrealized_pnl_cny"]) for position in positions)
        total_value = sum(position["current_value_cny"] for position in positions)
        total_pnl = sum(position["unrealized_pnl_cny"] for position in positions)
        total_return_pct = (total_pnl / total_cost * 100) if total_cost else 0.0
        exposure = {
            position["asset_code"]: round(
                (position["current_value_cny"] / total_value) * 100,
                2,
            )
            if total_value
            else 0.0
            for position in positions
        }
        return {
            "total_cost_cny": round(total_cost, 2),
            "total_value_cny": round(total_value, 2),
            "total_pnl_cny": round(total_pnl, 2),
            "total_return_pct": round(total_return_pct, 4),
            "exposure_pct": exposure,
            "positions_count": len(positions),
        }

    def _build_prompt(self, *, summary: Dict[str, Any], market_data: Dict[str, Any], risk_preference: str) -> str:
        return (
            "Generate investment advice as JSON with keys "
            "summary, risk_level, actions, reasoning, warnings.\n"
            f"Risk preference: {risk_preference}\n"
            f"Portfolio summary: {json.dumps(summary, ensure_ascii=False)}\n"
            f"Market data: {json.dumps(market_data, ensure_ascii=False)}\n"
            "Actions must be an array of objects with keys asset_code, action, rationale."
        )

    def _parse_ai_payload(self, content: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ToolExecutionError(
                "AI response was not valid JSON",
                code="invalid_ai_response",
                details={"content": content},
            ) from exc

        required = {"summary", "risk_level", "actions", "reasoning", "warnings"}
        missing = required.difference(parsed)
        if missing:
            raise ToolExecutionError(
                "AI response missing required fields",
                code="invalid_ai_response",
                details={"missing_fields": sorted(missing)},
            )
        return parsed
