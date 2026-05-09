from __future__ import annotations

from investment_tracker.mcp_tools.portfolio_summary_tool import PortfolioSummaryTool


SAMPLE_POSITION = {
    "asset_type": "FOREX",
    "asset_code": "USD",
    "quantity": 1000,
    "average_cost_cny": 7.2,
    "current_value_cny": 7300,
    "unrealized_pnl_cny": 100,
    "return_pct": 1.39,
}


def test_portfolio_summary_computed_correctly() -> None:
    tool = PortfolioSummaryTool()

    response = tool.execute({"positions": [SAMPLE_POSITION]})

    assert response["ok"] is True
    summary = response["result"]["portfolio_summary"]
    assert summary["positions_count"] == 1
    assert summary["total_value_cny"] == 7300
    assert summary["total_pnl_cny"] == 100
    assert "advice" not in response["result"]


def test_exposure_pct_sums_to_100() -> None:
    tool = PortfolioSummaryTool()

    response = tool.execute({
        "positions": [
            SAMPLE_POSITION,
            {
                "asset_type": "BOND",
                "asset_code": "123456",
                "quantity": 10,
                "average_cost_cny": 99.5,
                "current_value_cny": 1005,
                "unrealized_pnl_cny": 10,
                "return_pct": 1.0,
            },
        ],
    })

    assert response["ok"] is True
    exposure = response["result"]["portfolio_summary"]["exposure_pct"]
    assert abs(sum(exposure.values()) - 100.0) < 0.01


def test_empty_positions_returns_error() -> None:
    tool = PortfolioSummaryTool()

    response = tool.execute({"positions": []})

    assert response["ok"] is False
    assert response["error"]["code"] == "positions_required"
