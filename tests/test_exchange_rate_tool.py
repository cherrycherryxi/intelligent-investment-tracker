from __future__ import annotations

from datetime import date, datetime

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.mcp_tools.exchange_rate_tool import (
    ExchangeRateProvider,
    ExchangeRateRecord,
    ExchangeRateTool,
    StaticExchangeRateProvider,
)


class FlakyProvider(ExchangeRateProvider):
    provider_name = "flaky"

    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, *, base_currency, quote_currency, target_timestamp):
        self.calls += 1
        if self.calls < 3:
            raise ToolExecutionError("temporary error", retryable=True, code="temporary")
        return ExchangeRateRecord(
            rate=7.25,
            rate_timestamp=datetime(2026, 4, 26),
            is_estimated=False,
            source="PRIMARY",
        )


def test_exchange_rate_history_lookup() -> None:
    tool = ExchangeRateTool()

    response = tool.execute({"base_currency": "USD", "quote_currency": "CNY", "timestamp": "2026-04-26T10:00:00"})

    assert response["ok"] is True
    assert response["result"]["rate"] == 7.23
    assert response["result"]["is_estimated"] is False


def test_exchange_rate_falls_back_to_nearest_rate() -> None:
    primary = StaticExchangeRateProvider(
        {("USD", "CNY"): {date(2026, 4, 25): 7.2}},
        "PRIMARY",
    )
    tool = ExchangeRateTool(primary_provider=primary)

    response = tool.execute({"base_currency": "USD", "quote_currency": "CNY", "timestamp": "2026-04-26T10:00:00"})

    assert response["ok"] is True
    assert response["result"]["is_estimated"] is True


def test_exchange_rate_retries_before_success() -> None:
    flaky = FlakyProvider()
    tool = ExchangeRateTool(primary_provider=flaky, fallback_provider=flaky, retry_interval_seconds=0)

    response = tool.execute({"base_currency": "USD", "quote_currency": "CNY"})

    assert response["ok"] is True
    assert flaky.calls == 3


def test_exchange_rate_cache_reuses_previous_response() -> None:
    tool = ExchangeRateTool()

    first = tool.execute({"base_currency": "USD", "quote_currency": "CNY"})
    second = tool.execute({"base_currency": "USD", "quote_currency": "CNY"})

    assert first["ok"] is True
    assert second["ok"] is True
    assert tool.cache

