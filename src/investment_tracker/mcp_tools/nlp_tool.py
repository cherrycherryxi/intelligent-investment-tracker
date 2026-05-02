"""Rule-based natural language transaction parsing."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from investment_tracker.data.enums import AssetType, TransactionDirection
from investment_tracker.mcp_tools.base import MCPTool
from investment_tracker.mcp_tools.transaction_parser_tool import CURRENCY_ALIASES


class NLPToolInput(BaseModel):
    text: str


class NaturalLanguageTool(MCPTool):
    name = "parse_natural_language"
    description = "Parse Chinese or English trade instructions into structured parameters."
    input_model = NLPToolInput

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = payload["text"].strip()
        normalized = text.replace("\n", " ")

        direction = self._extract_direction(normalized)
        asset_type = self._detect_asset_type(normalized)
        pair_context = self._extract_forex_pair(normalized) if asset_type == AssetType.FOREX else None
        asset_code = self._extract_asset_code(
            normalized,
            asset_type,
            direction=direction,
            pair_context=pair_context,
        )
        quantity = self._extract_quantity(
            normalized,
            direction=direction,
            pair_context=pair_context,
        )
        price = self._extract_price(normalized, direction=direction, pair_context=pair_context)
        trade_time = self._extract_time(normalized)
        trade_currency = self._extract_trade_currency(
            normalized,
            asset_type=asset_type,
            direction=direction,
            pair_context=pair_context,
            price=price,
        )

        missing_fields: List[str] = []
        for field_name, value in (
            ("direction", direction),
            ("asset_code", asset_code),
            ("quantity", quantity),
        ):
            if value is None:
                missing_fields.append(field_name)
        if price is None:
            missing_fields.append("unit_price")

        return {
            "intent": "create_transaction",
            "language": "zh" if re.search(r"[\u4e00-\u9fff]", normalized) else "en",
            "transaction_type": asset_type.value,
            "parameters": {
                "asset_type": asset_type.value,
                "asset_code": asset_code,
                "direction": direction.value if direction else None,
                "quantity": quantity,
                "unit_price": price,
                "trade_currency": trade_currency,
                "trade_time": trade_time,
            },
            "missing_fields": missing_fields,
        }

    def _detect_asset_type(self, text: str) -> AssetType:
        if re.search(r"(债券|bond|\d{6})", text, re.IGNORECASE):
            return AssetType.BOND
        return AssetType.FOREX

    def _extract_direction(self, text: str) -> Optional[TransactionDirection]:
        if re.search(r"(买入|购入|购买|\bbuy\b|\bpurchase\b)", text, re.IGNORECASE):
            return TransactionDirection.BUY
        if re.search(r"(卖出|\bsell\b)", text, re.IGNORECASE):
            return TransactionDirection.SELL
        return None

    def _extract_asset_code(
        self,
        text: str,
        asset_type: AssetType,
        *,
        direction: Optional[TransactionDirection],
        pair_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if asset_type == AssetType.BOND:
            match = re.search(r"(\d{6})", text)
            return match.group(1) if match else None

        if pair_context:
            return self._pair_primary_currency(pair_context, direction)

        for alias, code in CURRENCY_ALIASES.items():
            if alias in text.lower():
                return code
        match = re.search(r"\b(USD|EUR|GBP|JPY|HKD|AUD|CAD|CHF|SGD|CNY)\b", text, re.IGNORECASE)
        return match.group(1).upper() if match else None

    def _extract_quantity(
        self,
        text: str,
        *,
        direction: Optional[TransactionDirection],
        pair_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[float]:
        if pair_context:
            return self._pair_primary_amount(pair_context, direction)
        patterns = [
            r"(?:买入|卖出|buy|sell|purchase|购买)\s*(?:了)?\s*([0-9]+(?:\.[0-9]+)?)",
            r"([0-9]+(?:\.[0-9]+)?)\s*(?:刀|美元|美金|欧元|英镑|日元|港币|加元|澳元|瑞郎|新元)",
            r"数量[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def _extract_price(
        self,
        text: str,
        *,
        direction: Optional[TransactionDirection],
        pair_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[float]:
        patterns = [
            r"(?:汇率|价格|price|rate|@)\s*(?:是|为|[:：])?\s*([0-9]+(?:\.[0-9]+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        if pair_context and direction is not None:
            primary_amount = self._pair_primary_amount(pair_context, direction)
            counter_amount = self._pair_counter_amount(pair_context, direction)
            if primary_amount:
                return round(counter_amount / primary_amount, 6)
        return None

    def _extract_time(self, text: str) -> Optional[str]:
        match = re.search(r"(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)", text)
        if match:
            raw = match.group(1)
            fmt = "%Y-%m-%d %H:%M:%S" if len(raw) == 19 else "%Y-%m-%d %H:%M" if len(raw) == 16 else "%Y-%m-%d"
            return datetime.strptime(raw, fmt).isoformat()
        if "昨天" in text:
            return (datetime.now() - timedelta(days=1)).replace(microsecond=0).isoformat()
        chinese_match = re.search(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})[号日]?", text)
        if chinese_match:
            year = int(chinese_match.group(1) or datetime.now().year)
            month = int(chinese_match.group(2))
            day = int(chinese_match.group(3))
            return datetime(year, month, day).isoformat()
        return None

    def _extract_forex_pair(self, text: str) -> Optional[Dict[str, Any]]:
        sell_match = re.search(
            r"卖出\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z\u4e00-\u9fff]{1,8})",
            text,
            re.IGNORECASE,
        )
        buy_match = re.search(
            r"买入\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z\u4e00-\u9fff]{1,8})",
            text,
            re.IGNORECASE,
        )
        if not sell_match or not buy_match:
            return None

        sell_currency = self._normalize_currency_token(sell_match.group(2))
        buy_currency = self._normalize_currency_token(buy_match.group(2))
        if sell_currency is None or buy_currency is None:
            return None

        return {
            "sell_currency": sell_currency,
            "sell_amount": float(sell_match.group(1)),
            "buy_currency": buy_currency,
            "buy_amount": float(buy_match.group(1)),
        }

    def _extract_trade_currency(
        self,
        text: str,
        *,
        asset_type: AssetType,
        direction: Optional[TransactionDirection],
        pair_context: Optional[Dict[str, Any]] = None,
        price: Optional[float],
    ) -> Optional[str]:
        if asset_type == AssetType.BOND:
            return "CNY"
        if pair_context:
            return self._pair_counter_currency(pair_context, direction)
        if price is not None and re.search(r"(汇率|rate|刀|美元|美金)", text, re.IGNORECASE):
            return "CNY"
        return None

    def _normalize_currency_token(self, token: str) -> Optional[str]:
        normalized = token.strip().lower()
        return CURRENCY_ALIASES.get(normalized, normalized.upper() if normalized.upper() in CURRENCY_ALIASES.values() else None)

    def _pair_primary_currency(
        self,
        pair_context: Dict[str, Any],
        direction: Optional[TransactionDirection],
    ) -> str:
        if direction == TransactionDirection.SELL:
            return pair_context["sell_currency"]
        return pair_context["buy_currency"]

    def _pair_primary_amount(
        self,
        pair_context: Dict[str, Any],
        direction: Optional[TransactionDirection],
    ) -> float:
        if direction == TransactionDirection.SELL:
            return pair_context["sell_amount"]
        return pair_context["buy_amount"]

    def _pair_counter_currency(
        self,
        pair_context: Dict[str, Any],
        direction: Optional[TransactionDirection],
    ) -> str:
        if direction == TransactionDirection.SELL:
            return pair_context["buy_currency"]
        return pair_context["sell_currency"]

    def _pair_counter_amount(
        self,
        pair_context: Dict[str, Any],
        direction: Optional[TransactionDirection],
    ) -> float:
        if direction == TransactionDirection.SELL:
            return pair_context["buy_amount"]
        return pair_context["sell_amount"]
