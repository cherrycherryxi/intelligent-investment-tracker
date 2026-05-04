from __future__ import annotations

from datetime import date, datetime
import json

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.mcp_tools.exchange_rate_tool import (
    ExchangeRateProvider,
    ExchangeRateRecord,
    ExchangeRateTool,
    FrankfurterExchangeRateProvider,
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


def _static_usd_tool() -> ExchangeRateTool:
    return ExchangeRateTool(
        primary_provider=StaticExchangeRateProvider(
            {("USD", "CNY"): {date(2026, 4, 26): 7.23}},
            "PRIMARY",
        )
    )


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_exchange_rate_history_lookup() -> None:
    tool = _static_usd_tool()

    response = tool.execute({"base_currency": "USD", "quote_currency": "CNY", "timestamp": "2026-04-26T10:00:00"})

    assert response["ok"] is True
    assert response["result"]["rate"] == 7.23
    assert response["result"]["is_estimated"] is False


def test_frankfurter_provider_fetches_exact_historical_rate() -> None:
    requested_urls = []

    def fake_opener(url, timeout):
        requested_urls.append((url.full_url, timeout, url.headers))
        return FakeHTTPResponse([{"date": "2026-04-02", "base": "USD", "quote": "CNY", "rate": 7.0776}])

    provider = FrankfurterExchangeRateProvider(opener=fake_opener)

    record = provider.fetch(
        base_currency="USD",
        quote_currency="CNY",
        target_timestamp=datetime(2026, 4, 2, 12, 15, 30),
    )

    assert record.rate == 7.0776
    assert record.rate_timestamp == datetime(2026, 4, 2)
    assert record.is_estimated is False
    assert "date=2026-04-02" in requested_urls[0][0]
    assert "base=USD" in requested_urls[0][0]
    assert "quotes=CNY" in requested_urls[0][0]
    assert requested_urls[0][2]["User-agent"] == "investment-assistant/0.1"


def test_frankfurter_provider_accepts_rates_map_response() -> None:
    def fake_opener(url, timeout):
        return FakeHTTPResponse({"date": "2026-04-30", "base": "CAD", "rates": {"CNY": 4.9962}})

    provider = FrankfurterExchangeRateProvider(opener=fake_opener)

    record = provider.fetch(
        base_currency="CAD",
        quote_currency="CNY",
        target_timestamp=None,
    )

    assert record.rate == 4.9962
    assert record.rate_timestamp == datetime(2026, 4, 30)
    assert record.is_estimated is False


def test_frankfurter_provider_marks_non_matching_date_as_estimated() -> None:
    def fake_opener(url, timeout):
        return FakeHTTPResponse({"date": "2026-04-01", "base": "USD", "rates": {"CNY": 7.08}})

    provider = FrankfurterExchangeRateProvider(opener=fake_opener)

    record = provider.fetch(
        base_currency="USD",
        quote_currency="CNY",
        target_timestamp=datetime(2026, 4, 2, 12, 15, 30),
    )

    assert record.is_estimated is True


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
    tool = _static_usd_tool()

    first = tool.execute({"base_currency": "USD", "quote_currency": "CNY"})
    second = tool.execute({"base_currency": "USD", "quote_currency": "CNY"})

    assert first["ok"] is True
    assert second["ok"] is True
    assert tool.cache
