"""Compute portfolio summary metrics. Used as a pre_tool by the investment_advice skill."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel

from investment_tracker.mcp_tools.base import MCPTool, ToolExecutionError


class PortfolioPositionInput(BaseModel):
    asset_type: str
    asset_code: str
    quantity: float
    average_cost_cny: float
    current_value_cny: float
    unrealized_pnl_cny: float
    return_pct: float


class PortfolioSummaryInput(BaseModel):
    positions: List[PortfolioPositionInput]


class PortfolioSummaryTool(MCPTool):
    """Compute deterministic portfolio aggregates (totals, exposure, return%)."""

    name = "build_portfolio_summary"
    description = "Compute total cost, total value, PnL, and per-asset exposure for a portfolio."
    input_model = PortfolioSummaryInput

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        positions = payload["positions"]
        if not positions:
            raise ToolExecutionError("positions are required", code="positions_required")
        return {"portfolio_summary": self._build_portfolio_summary(positions)}

    def _build_portfolio_summary(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_cost = sum((p["current_value_cny"] - p["unrealized_pnl_cny"]) for p in positions)
        total_value = sum(p["current_value_cny"] for p in positions)
        total_pnl = sum(p["unrealized_pnl_cny"] for p in positions)
        total_return_pct = (total_pnl / total_cost * 100) if total_cost else 0.0
        exposure = {
            p["asset_code"]: round((p["current_value_cny"] / total_value) * 100, 2) if total_value else 0.0
            for p in positions
        }
        return {
            "total_cost_cny": round(total_cost, 2),
            "total_value_cny": round(total_value, 2),
            "total_pnl_cny": round(total_pnl, 2),
            "total_return_pct": round(total_return_pct, 4),
            "exposure_pct": exposure,
            "positions_count": len(positions),
        }
