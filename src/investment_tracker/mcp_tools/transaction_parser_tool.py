"""Parse OCR text into structured transaction data."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from investment_tracker.data.enums import AssetType, TransactionDirection
from investment_tracker.mcp_tools.base import MCPTool, ToolExecutionError


CURRENCY_ALIASES = {
    "美元": "USD",
    "usd": "USD",
    "美金": "USD",
    "欧元": "EUR",
    "eur": "EUR",
    "英镑": "GBP",
    "gbp": "GBP",
    "日元": "JPY",
    "jpy": "JPY",
    "港币": "HKD",
    "hkd": "HKD",
    "加元": "CAD",
    "cad": "CAD",
    "澳元": "AUD",
    "aud": "AUD",
    "瑞郎": "CHF",
    "chf": "CHF",
    "新元": "SGD",
    "sgd": "SGD",
    "人民币": "CNY",
    "cny": "CNY",
}


class TransactionParserInput(BaseModel):
    ocr_text: str


class TransactionParserTool(MCPTool):
    name = "parse_transaction"
    description = "Parse OCR text into a structured forex or bond transaction."
    input_model = TransactionParserInput

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = payload["ocr_text"].strip()
        normalized = text.replace("\n", " ")
        asset_type = self._detect_asset_type(normalized)
        direction = self._extract_direction(normalized)
        asset_code, asset_name = self._extract_asset(normalized, asset_type)
        quantity = self._extract_quantity(normalized, asset_type)
        unit_price = self._extract_unit_price(normalized, asset_type)
        trade_time = self._extract_datetime(normalized)

        missing_fields: List[str] = []
        if direction is None:
            missing_fields.append("direction")
        if asset_code is None:
            missing_fields.append("asset_code")
        if quantity is None:
            missing_fields.append("quantity")
        if unit_price is None:
            missing_fields.append("unit_price")
        if trade_time is None:
            missing_fields.append("trade_time")

        confidence = max(0.1, 1 - 0.15 * len(missing_fields))

        return {
            "transaction_type": asset_type.value,
            "template_match": any(token in normalized for token in ("招商银行", "招行", "CMB")),
            "parsed_transaction": {
                "asset_type": asset_type.value,
                "asset_code": asset_code,
                "asset_name": asset_name,
                "direction": direction.value if direction else None,
                "quantity": quantity,
                "unit_price": unit_price,
                "trade_time": trade_time,
            },
            "missing_fields": missing_fields,
            "confidence": round(confidence, 4),
        }

    def _detect_asset_type(self, text: str) -> AssetType:
        if re.search(r"(债券|柜台债|国债|债券代码[:：]?\s*\d{6}|交易产品)", text, re.IGNORECASE):
            return AssetType.BOND
        if re.search(r"(美元|欧元|英镑|日元|港币|USD|EUR|GBP|JPY|HKD|外汇)", text, re.IGNORECASE):
            return AssetType.FOREX
        raise ToolExecutionError(
            "could not determine transaction type from OCR text",
            code="transaction_type_not_detected",
        )

    def _extract_direction(self, text: str) -> Optional[TransactionDirection]:
        if re.search(r"(买入|购入|\bbuy\b)", text, re.IGNORECASE):
            return TransactionDirection.BUY
        if re.search(r"(卖出|\bsell\b)", text, re.IGNORECASE):
            return TransactionDirection.SELL
        return None

    def _extract_asset(self, text: str, asset_type: AssetType) -> Tuple[Optional[str], Optional[str]]:
        if asset_type == AssetType.BOND:
            match = re.search(r"(?:债券代码|代码)[:：]?\s*(\d{6})", text)
            if match:
                return match.group(1), None
            name_match = re.search(r"(?:交易产品|产品名称)[:：]?\s*([^\s]+)", text)
            if name_match:
                asset_name = name_match.group(1).strip()
                return asset_name, asset_name
            heading_match = re.search(r"(买入|卖出)\s*([^\s]+国债[^\s]*)", text)
            if heading_match:
                asset_name = heading_match.group(2).strip()
                return asset_name, asset_name
            return None, None

        explicit_code = re.search(r"(?:币种|Currency)[:：]?\s*([A-Z]{3}|美元|欧元|英镑|日元|港币)", text, re.IGNORECASE)
        if explicit_code:
            raw = explicit_code.group(1).lower()
            code = CURRENCY_ALIASES.get(raw, raw.upper())
            return code, explicit_code.group(1)

        for alias, code in CURRENCY_ALIASES.items():
            if alias in text.lower():
                return code, alias
        return None, None

    def _extract_quantity(self, text: str, asset_type: AssetType) -> Optional[float]:
        patterns = [r"数量[:：]?\s*([0-9]+(?:\.[0-9]+)?)", r"(?:买入|卖出)\s*([0-9]+(?:\.[0-9]+)?)"]
        if asset_type == AssetType.BOND:
            patterns = [
                r"(?:买入|卖出)份数[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
                r"份数[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
                *patterns,
            ]
        return self._extract_decimal(text, patterns)

    def _extract_unit_price(self, text: str, asset_type: AssetType) -> Optional[float]:
        patterns = [r"(?:价格|成交价|汇率)[:：]?\s*([0-9]+(?:\.[0-9]+)?)"]
        if asset_type == AssetType.BOND:
            patterns = [
                r"(?:买入全价|卖出全价)[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
                r"(?:买入净价|卖出净价)[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
                *patterns,
            ]
        return self._extract_decimal(text, patterns)

    def _extract_decimal(self, text: str, patterns: List[str]) -> Optional[float]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def _extract_datetime(self, text: str) -> Optional[str]:
        patterns = [
            r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
            r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                raw = match.group(1).replace("/", "-")
                return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").isoformat()
        return None
