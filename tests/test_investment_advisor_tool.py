from __future__ import annotations

import json

from investment_tracker.mcp_tools.investment_advisor_tool import InvestmentAdvisorTool
from investment_tracker.utils.ai_client import AIResponse


class StubAIClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def generate(self, prompt, *, system_prompt=None, provider=None, model=None, temperature=None, max_tokens=None):
        return AIResponse(
            content=self.content,
            model="deepseek-reasoner",
            provider="deepseek",
            input_tokens=100,
            output_tokens=50,
            raw_response={},
        )


def test_generate_investment_advice() -> None:
    ai_payload = {
        "summary": "Portfolio is concentrated in USD.",
        "risk_level": "medium",
        "actions": [{"asset_code": "USD", "action": "HOLD", "rationale": "trend remains stable"}],
        "reasoning": "Exposure is manageable.",
        "warnings": ["Monitor FX volatility."],
    }
    tool = InvestmentAdvisorTool(ai_client=StubAIClient(json.dumps(ai_payload)))

    response = tool.execute(
        {
            "positions": [
                {
                    "asset_type": "FOREX",
                    "asset_code": "USD",
                    "quantity": 1000,
                    "average_cost_cny": 7.2,
                    "current_value_cny": 7300,
                    "unrealized_pnl_cny": 100,
                    "return_pct": 1.39,
                }
            ],
            "market_data": {"usd_cny_trend": "stable"},
            "risk_preference": "balanced",
        }
    )

    assert response["ok"] is True
    assert response["result"]["advice"]["risk_level"] == "medium"
    assert response["result"]["portfolio_summary"]["positions_count"] == 1


def test_risk_preference_is_reflected_in_summary() -> None:
    ai_payload = {
        "summary": "Use a conservative stance.",
        "risk_level": "low",
        "actions": [{"asset_code": "123456", "action": "HOLD", "rationale": "preserve income"}],
        "reasoning": "Low-risk profile.",
        "warnings": ["Avoid concentration."],
    }
    tool = InvestmentAdvisorTool(ai_client=StubAIClient(json.dumps(ai_payload)))

    response = tool.execute(
        {
            "positions": [
                {
                    "asset_type": "BOND",
                    "asset_code": "123456",
                    "quantity": 10,
                    "average_cost_cny": 99.5,
                    "current_value_cny": 1005,
                    "unrealized_pnl_cny": 10,
                    "return_pct": 1.0,
                }
            ],
            "risk_preference": "conservative",
        }
    )

    assert response["ok"] is True
    assert response["result"]["advice"]["risk_level"] == "low"


def test_invalid_ai_output_format_returns_error() -> None:
    tool = InvestmentAdvisorTool(ai_client=StubAIClient('{"summary":"x"}'))

    response = tool.execute(
        {
            "positions": [
                {
                    "asset_type": "FOREX",
                    "asset_code": "USD",
                    "quantity": 1000,
                    "average_cost_cny": 7.2,
                    "current_value_cny": 7300,
                    "unrealized_pnl_cny": 100,
                    "return_pct": 1.39,
                }
            ]
        }
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_ai_response"
