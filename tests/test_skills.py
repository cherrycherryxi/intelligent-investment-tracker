from __future__ import annotations

import json

from investment_tracker.skills import (
    InvestmentAdviceSkill,
    NaturalLanguageUnderstandingSkill,
    OCRParsingSkill,
    RiskAssessmentSkill,
    SkillRegistry,
    TransactionAnalysisSkill,
)
from investment_tracker.utils.ai_client import AIResponse


class StubAIClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def generate(self, prompt, *, system_prompt=None, temperature=None, max_tokens=None):
        return AIResponse(
            content=self.content,
            model="deepseek-reasoner",
            provider="deepseek",
            input_tokens=100,
            output_tokens=40,
            raw_response={},
        )


def test_skill_registry_tracks_metadata() -> None:
    registry = SkillRegistry()
    skill = OCRParsingSkill(ai_client=StubAIClient("{}"))
    registry.register(skill)

    metadata = list(registry.list_metadata())

    assert len(metadata) == 1
    assert metadata[0].name == "ocr_parsing_skill"


def test_ocr_parsing_skill() -> None:
    skill = OCRParsingSkill(
        ai_client=StubAIClient(
            json.dumps(
                {
                    "asset_code": "USD",
                    "asset_name": "美元",
                    "quantity": 1000,
                    "unit_price": 7.23,
                    "trade_time": "2026-04-26T10:30:00",
                    "direction": "BUY",
                }
            )
        )
    )

    result = skill.execute({"ocr_text": "招商银行 外汇买入", "transaction_type": "FOREX"})

    assert result["asset_code"] == "USD"


def test_transaction_analysis_skill() -> None:
    skill = TransactionAnalysisSkill(
        ai_client=StubAIClient(
            json.dumps(
                {
                    "frequency_summary": "low",
                    "anomalies": [],
                    "concentration_risk": "medium",
                    "recommendations": ["watch concentration"],
                }
            )
        )
    )

    result = skill.execute({"transactions": [{"asset_code": "USD", "quantity": 1000}]})

    assert result["concentration_risk"] == "medium"


def test_investment_advice_skill() -> None:
    skill = InvestmentAdviceSkill(
        ai_client=StubAIClient(
            json.dumps(
                {
                    "summary": "hold USD",
                    "actions": [{"asset_code": "USD", "action": "HOLD"}],
                    "reasoning": "stable exposure",
                    "warnings": ["monitor volatility"],
                }
            )
        )
    )

    result = skill.execute({"positions": [{"asset_code": "USD"}], "risk_preference": "balanced"})

    assert result["summary"] == "hold USD"


def test_risk_assessment_skill() -> None:
    skill = RiskAssessmentSkill(
        ai_client=StubAIClient(
            json.dumps(
                {
                    "risk_level": "medium",
                    "factors": ["currency concentration"],
                    "diversification_suggestions": ["add bonds"],
                }
            )
        )
    )

    result = skill.execute({"positions": [{"asset_code": "USD"}], "volatility_data": {"USD": 0.12}})

    assert result["risk_level"] == "medium"


def test_nlu_skill() -> None:
    skill = NaturalLanguageUnderstandingSkill(
        ai_client=StubAIClient(
            json.dumps(
                {
                    "asset_code": "USD",
                    "direction": "BUY",
                    "quantity": 1000,
                    "unit_price": 7.23,
                    "trade_time": "2026-04-26T10:30:00",
                    "missing_fields": [],
                }
            )
        )
    )

    result = skill.execute({"text": "买入1000美元"})

    assert result["asset_code"] == "USD"

