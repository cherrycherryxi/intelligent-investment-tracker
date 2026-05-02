from __future__ import annotations

import json
from pathlib import Path

from investment_tracker.mcp_tools import (
    InvestmentAdvisorTool,
    MCPServer,
    NaturalLanguageTool,
    OCRTool,
    PositionCalculatorTool,
    TransactionParserTool,
)
from investment_tracker.mcp_tools.ocr_tool import OCRExtraction, OCREngine
from investment_tracker.utils.ai_client import AIResponse


class StubEngine(OCREngine):
    name = "stub"

    def extract(self, *, image_bytes, image_path, language):
        return OCRExtraction(
            text="招商银行 外汇买入 币种: 美元 数量: 1000 价格: 7.23 交易时间: 2026-04-26 10:30:00",
            confidence=0.95,
            engine=self.name,
            metadata={"language": language},
        )


class StubAIClient:
    def generate(self, prompt, *, system_prompt=None, provider=None, model=None, temperature=None, max_tokens=None):
        return AIResponse(
            content=json.dumps(
                {
                    "summary": "Hold USD position.",
                    "risk_level": "medium",
                    "actions": [{"asset_code": "USD", "action": "HOLD", "rationale": "stable trend"}],
                    "reasoning": "Portfolio has moderate concentration.",
                    "warnings": ["Watch exchange rate volatility."],
                }
            ),
            model="deepseek-reasoner",
            provider="deepseek",
            input_tokens=100,
            output_tokens=30,
            raw_response={},
        )


def test_screenshot_to_parse_flow() -> None:
    server = MCPServer()
    server.register_tool(OCRTool(engines={"tesseract": StubEngine()}))
    server.register_tool(TransactionParserTool())

    ocr_result = server.call_tool("ocr_extract", {"image_base64": "aWdub3JlZA=="})
    parse_result = server.call_tool("parse_transaction", {"ocr_text": ocr_result["result"]["text"]})

    assert ocr_result["ok"] is True
    assert parse_result["ok"] is True
    assert parse_result["result"]["parsed_transaction"]["asset_code"] == "USD"


def test_nlp_to_parse_flow() -> None:
    server = MCPServer()
    server.register_tool(NaturalLanguageTool())

    result = server.call_tool(
        "parse_natural_language",
        {"text": "买入1000美元，汇率7.23，时间2026-04-26 10:30:00"},
    )

    assert result["ok"] is True
    assert result["result"]["parameters"]["asset_code"] == "USD"


def test_position_to_advice_flow() -> None:
    calc = PositionCalculatorTool()
    advice = InvestmentAdvisorTool(ai_client=StubAIClient())

    position_result = calc.execute(
        {
            "transactions": [
                {
                    "asset_type": "FOREX",
                    "asset_code": "USD",
                    "direction": "BUY",
                    "quantity": "1000",
                    "unit_price": "7.20",
                    "trade_currency": "CNY",
                }
            ],
            "current_price": "7.30",
        }
    )
    advice_result = advice.execute(
        {
            "positions": [
                {
                    "asset_type": "FOREX",
                    "asset_code": "USD",
                    "quantity": position_result["result"]["quantity"],
                    "average_cost_cny": position_result["result"]["average_cost_cny"],
                    "current_value_cny": position_result["result"]["current_value_cny"],
                    "unrealized_pnl_cny": position_result["result"]["unrealized_pnl_cny"],
                    "return_pct": position_result["result"]["return_pct"],
                }
            ],
            "risk_preference": "balanced",
        }
    )

    assert position_result["ok"] is True
    assert advice_result["ok"] is True
    assert advice_result["result"]["advice"]["actions"][0]["asset_code"] == "USD"


def test_eval_fixture_has_ten_cases() -> None:
    fixture_path = Path("tests/fixtures/day4_eval_cases.json")
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert len(cases) >= 10

