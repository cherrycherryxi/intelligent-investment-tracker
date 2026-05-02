"""Investment advice API routes."""

from __future__ import annotations

from fastapi import APIRouter

from investment_tracker.data.db import get_db_session
from investment_tracker.data.services import PortfolioService
from investment_tracker.mcp_tools.investment_advisor_tool import InvestmentAdvisorTool


router = APIRouter(prefix="/api/advice", tags=["advice"])


@router.get("")
async def get_advice(
    user_id: int = 1,
    risk_preference: str = "balanced",
) -> dict:
    with get_db_session() as session:
        portfolio_service = PortfolioService(session)
        positions = portfolio_service.build_positions(user_id=user_id)

    tool = InvestmentAdvisorTool()
    response = tool.execute(
        {
            "positions": positions,
            "market_data": {"generated_at": "local"},
            "risk_preference": risk_preference,
        }
    )
    return response
