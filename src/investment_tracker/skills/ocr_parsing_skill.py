"""Skill for extracting structured transaction data from OCR text."""

from __future__ import annotations

import json
from typing import Any, Dict

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.skills.base import BaseSkill


class OCRParsingSkill(BaseSkill):
    name = "ocr_parsing_skill"
    description = "Convert OCR text into structured transaction data."

    def build_system_prompt(self, payload: Dict[str, Any]) -> str:
        return "You are a financial OCR parsing assistant. Return JSON only."

    def build_prompt(self, payload: Dict[str, Any]) -> str:
        return (
            "Extract a structured transaction from the OCR text.\n"
            f"Transaction type hint: {payload.get('transaction_type', 'unknown')}\n"
            f"OCR text: {payload['ocr_text']}\n"
            "Return JSON with keys asset_code, asset_name, quantity, unit_price, trade_time, direction."
        )

    def parse_response(self, content: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ToolExecutionError(
                "OCR parsing skill returned invalid JSON",
                code="invalid_skill_response",
                details={"content": content},
            ) from exc

