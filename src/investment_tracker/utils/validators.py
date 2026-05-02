"""Validation helpers for transaction and portfolio data."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from investment_tracker.mcp_tools.base import ToolExecutionError


def validate_positive_decimal(value: Decimal, field_name: str) -> None:
    if value <= 0:
        raise ToolExecutionError(
            f"{field_name} must be greater than zero",
            code="validation_error",
            details={"field": field_name},
        )


def validate_trade_time_not_future(trade_time: datetime) -> None:
    if trade_time.tzinfo is None:
        trade_time = trade_time.replace(tzinfo=timezone.utc)
    if trade_time > datetime.now(timezone.utc):
        raise ToolExecutionError(
            "trade_time cannot be in the future",
            code="validation_error",
            details={"field": "trade_time"},
        )


def validate_sell_quantity(position_quantity: Decimal, sell_quantity: Decimal) -> None:
    if sell_quantity > position_quantity:
        raise ToolExecutionError(
            "sell quantity exceeds current position",
            code="validation_error",
            details={"field": "quantity"},
        )
