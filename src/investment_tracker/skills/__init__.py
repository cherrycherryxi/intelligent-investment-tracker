"""Skills package."""

from investment_tracker.skills.base import BaseSkill, SkillRegistry
from investment_tracker.skills.investment_advice_skill import InvestmentAdviceSkill
from investment_tracker.skills.natural_language_understanding_skill import (
    NaturalLanguageUnderstandingSkill,
)
from investment_tracker.skills.ocr_parsing_skill import OCRParsingSkill
from investment_tracker.skills.risk_assessment_skill import RiskAssessmentSkill
from investment_tracker.skills.transaction_analysis_skill import TransactionAnalysisSkill

__all__ = [
    "BaseSkill",
    "InvestmentAdviceSkill",
    "NaturalLanguageUnderstandingSkill",
    "OCRParsingSkill",
    "RiskAssessmentSkill",
    "SkillRegistry",
    "TransactionAnalysisSkill",
]
