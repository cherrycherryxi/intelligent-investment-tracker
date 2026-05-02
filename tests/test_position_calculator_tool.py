from __future__ import annotations

from investment_tracker.mcp_tools.position_calculator_tool import PositionCalculatorTool


def test_weighted_average_cost_for_forex() -> None:
    tool = PositionCalculatorTool()
    response = tool.execute(
        {
            "transactions": [
                {
                    "asset_type": "FOREX",
                    "asset_code": "USD",
                    "direction": "BUY",
                    "quantity": "1000",
                    "unit_price": "7.20",
                    "trade_currency": "CNY",
                },
                {
                    "asset_type": "FOREX",
                    "asset_code": "USD",
                    "direction": "BUY",
                    "quantity": "500",
                    "unit_price": "7.50",
                    "trade_currency": "CNY",
                },
            ],
            "current_price": "7.40",
        }
    )

    assert response["ok"] is True
    assert response["result"]["quantity"] == 1500.0
    assert response["result"]["average_cost_cny"] == 7.3


def test_sell_reduces_position_and_cost_basis() -> None:
    tool = PositionCalculatorTool()
    response = tool.execute(
        {
            "transactions": [
                {
                    "asset_type": "BOND",
                    "asset_code": "123456",
                    "direction": "BUY",
                    "quantity": "10",
                    "unit_price": "100",
                },
                {
                    "asset_type": "BOND",
                    "asset_code": "123456",
                    "direction": "SELL",
                    "quantity": "4",
                    "unit_price": "101",
                },
            ],
            "current_price": "102",
        }
    )

    assert response["ok"] is True
    assert response["result"]["quantity"] == 6.0
    assert response["result"]["cost_basis_cny"] == 600.0


def test_sell_more_than_position_fails() -> None:
    tool = PositionCalculatorTool()
    response = tool.execute(
        {
            "transactions": [
                {
                    "asset_type": "BOND",
                    "asset_code": "123456",
                    "direction": "BUY",
                    "quantity": "2",
                    "unit_price": "100",
                },
                {
                    "asset_type": "BOND",
                    "asset_code": "123456",
                    "direction": "SELL",
                    "quantity": "3",
                    "unit_price": "100",
                },
            ],
            "current_price": "100",
        }
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "insufficient_position"

