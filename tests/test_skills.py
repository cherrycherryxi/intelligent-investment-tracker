"""Integration tests: real MD skill specs via SkillRunner with stub AI."""

from __future__ import annotations

import json
from pathlib import Path

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.mcp_tools.nlp_tool import NaturalLanguageTool
from investment_tracker.mcp_tools.portfolio_summary_tool import PortfolioSummaryTool
from investment_tracker.mcp_tools.server import MCPServer
from investment_tracker.mcp_tools.transaction_parser_tool import TransactionParserTool
from investment_tracker.skills.registry import SkillRegistry
from investment_tracker.skills.runner import SkillRunner
from investment_tracker.utils.ai_client import AIResponse

SPECS_DIR = Path(__file__).parent.parent / "src" / "investment_tracker" / "skills" / "specs"


class StubAIClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.call_count = 0

    def generate(self, prompt, *, system_prompt=None, temperature=None, max_tokens=None):
        self.call_count += 1
        return AIResponse(
            content=self.content,
            model="stub",
            provider="stub",
            input_tokens=10,
            output_tokens=10,
            raw_response={},
        )


class FailingAIClient:
    def generate(self, *args, **kwargs):
        raise ToolExecutionError("AI unavailable", code="ai_request_failed", retryable=False)


def _build_runner(ai_client, extra_tools=None):
    server = MCPServer()
    server.register_tools([
        PortfolioSummaryTool(),
        TransactionParserTool(),
        NaturalLanguageTool(),
    ])
    if extra_tools:
        server.register_tools(extra_tools)
    registry = SkillRegistry.from_dir(SPECS_DIR)
    return SkillRunner(skill_registry=registry, tool_server=server, ai_client=ai_client)


# ---------------------------------------------------------------------------
# investment_advice_skill
# ---------------------------------------------------------------------------

def test_investment_advice_skill_returns_advice_and_portfolio_summary() -> None:
    ai_payload = {
        "advice": {
            "summary": "hold USD",
            "risk_level": "medium",
            "actions": [{"asset_code": "USD", "action": "HOLD", "rationale": "stable"}],
            "reasoning": "stable exposure",
            "warnings": ["monitor volatility"],
        },
        "portfolio_summary": {
            "positions_count": 1,
            "total_value_cny": 7300.0,
        },
    }
    ai = StubAIClient(json.dumps(ai_payload))
    runner = _build_runner(ai)

    result = runner.run("investment_advice_skill", {
        "positions": [{
            "asset_type": "FOREX",
            "asset_code": "USD",
            "quantity": 1000,
            "average_cost_cny": 7.2,
            "current_value_cny": 7300,
            "unrealized_pnl_cny": 100,
            "return_pct": 1.39,
        }],
        "risk_preference": "balanced",
    })

    assert result["advice"]["summary"] == "hold USD"
    assert "portfolio_summary" in result


# ---------------------------------------------------------------------------
# transaction_analysis_skill
# ---------------------------------------------------------------------------

def test_transaction_analysis_skill() -> None:
    ai_payload = {
        "frequency_summary": "low",
        "anomalies": [],
        "concentration_risk": "medium",
        "recommendations": ["watch concentration"],
    }
    runner = _build_runner(StubAIClient(json.dumps(ai_payload)))

    result = runner.run("transaction_analysis_skill", {
        "transactions": [{"asset_code": "USD", "quantity": 1000}],
    })

    assert result["concentration_risk"] == "medium"


# ---------------------------------------------------------------------------
# risk_assessment_skill
# ---------------------------------------------------------------------------

def test_risk_assessment_skill() -> None:
    ai_payload = {
        "risk_level": "medium",
        "factors": ["currency concentration"],
        "diversification_suggestions": ["add bonds"],
    }
    runner = _build_runner(StubAIClient(json.dumps(ai_payload)))

    result = runner.run("risk_assessment_skill", {
        "positions": [{"asset_code": "USD"}],
        "volatility_data": {"USD": 0.12},
    })

    assert result["risk_level"] == "medium"


# ---------------------------------------------------------------------------
# natural_language_understanding_skill: rule short-circuit
# ---------------------------------------------------------------------------

def test_nlu_skill_skips_ai_when_rule_succeeds() -> None:
    ai = StubAIClient("{}")
    runner = _build_runner(ai)

    # Full input → rule tool finds all fields → short-circuit (AI not called)
    result = runner.run("natural_language_understanding_skill", {
        "text": "买入1000美元，汇率7.23，时间2026-04-26 10:30:00",
    })

    assert ai.call_count == 0
    assert result["parameters"]["asset_code"] == "USD"


def test_nlu_skill_calls_ai_when_rule_has_missing_fields() -> None:
    ai_result = {
        "parameters": {"asset_code": "USD", "direction": "BUY", "quantity": 1000,
                       "unit_price": 7.23, "trade_time": "2026-04-26T10:30:00",
                       "asset_type": "FOREX", "trade_currency": "CNY"},
        "missing_fields": [],
        "ok": True,
    }
    ai = StubAIClient(json.dumps(ai_result))
    runner = _build_runner(ai)

    # Incomplete input → rule has missing fields → AI called
    result = runner.run("natural_language_understanding_skill", {
        "text": "买入1000美元",
    })

    assert ai.call_count == 1
    assert result["parameters"]["asset_code"] == "USD"


def test_nlu_skill_falls_back_to_rule_on_ai_failure() -> None:
    runner = _build_runner(FailingAIClient())

    # "买入1000美元" → rule has missing fields → AI fails → return_var fallback
    result = runner.run("natural_language_understanding_skill", {
        "text": "买入1000美元",
    })

    assert result["parameters"]["asset_code"] == "USD"
    assert "unit_price" in result["missing_fields"]
