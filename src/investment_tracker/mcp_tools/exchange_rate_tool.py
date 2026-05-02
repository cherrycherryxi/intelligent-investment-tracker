"""Exchange rate lookup with retry and cache support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from time import sleep
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel

from investment_tracker.mcp_tools.base import MCPTool, ToolExecutionError


@dataclass
class ExchangeRateRecord:
    rate: float
    rate_timestamp: datetime
    is_estimated: bool
    source: str


class ExchangeRateProvider:
    provider_name = "base"

    def fetch(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        target_timestamp: Optional[datetime],
    ) -> ExchangeRateRecord:
        raise NotImplementedError


class StaticExchangeRateProvider(ExchangeRateProvider):
    provider_name = "static"

    def __init__(self, data: Dict[Tuple[str, str], Dict[date, float]], source_label: str) -> None:
        self.data = data
        self.source_label = source_label

    def fetch(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        target_timestamp: Optional[datetime],
    ) -> ExchangeRateRecord:
        key = (base_currency.upper(), quote_currency.upper())
        if key not in self.data:
            raise ToolExecutionError(
                "currency pair not available in provider",
                code="currency_pair_not_found",
                retryable=False,
            )

        series = self.data[key]
        target_day = (target_timestamp or datetime.utcnow()).date()
        if target_day in series:
            return ExchangeRateRecord(
                rate=series[target_day],
                rate_timestamp=datetime.combine(target_day, datetime.min.time()),
                is_estimated=False,
                source=self.source_label,
            )

        prior_days = [day for day in series if day <= target_day]
        if prior_days:
            nearest = max(prior_days)
            return ExchangeRateRecord(
                rate=series[nearest],
                rate_timestamp=datetime.combine(nearest, datetime.min.time()),
                is_estimated=True,
                source=self.source_label,
            )

        latest_day = max(series)
        return ExchangeRateRecord(
            rate=series[latest_day],
            rate_timestamp=datetime.combine(latest_day, datetime.min.time()),
            is_estimated=True,
            source=self.source_label,
        )


class ExchangeRateToolInput(BaseModel):
    base_currency: str
    quote_currency: str = "CNY"
    timestamp: Optional[str] = None


class ExchangeRateTool(MCPTool):
    name = "get_exchange_rate"
    description = "Query historical or latest exchange rates with retry and cache."
    input_model = ExchangeRateToolInput

    def __init__(
        self,
        *,
        primary_provider: Optional[ExchangeRateProvider] = None,
        fallback_provider: Optional[ExchangeRateProvider] = None,
        max_retries: int = 3,
        retry_interval_seconds: float = 0.0,
    ) -> None:
        default_primary = StaticExchangeRateProvider(
            {
                ("USD", "CNY"): {
                    date(2022, 1, 1): 6.36,
                    date(2024, 1, 1): 7.10,
                    date(2025, 9, 18): 7.13,
                    date(2026, 4, 25): 7.21,
                    date(2026, 4, 26): 7.23,
                },
                ("EUR", "CNY"): {
                    date(2022, 1, 1): 7.20,
                    date(2024, 1, 1): 7.83,
                    date(2025, 9, 18): 7.92,
                    date(2026, 4, 25): 8.02,
                    date(2026, 4, 26): 8.05,
                },
                ("JPY", "CNY"): {
                    date(2022, 1, 1): 0.055,
                    date(2024, 1, 1): 0.050,
                    date(2025, 9, 18): 0.048,
                    date(2026, 4, 26): 0.047,
                },
                ("GBP", "CNY"): {
                    date(2022, 1, 1): 8.62,
                    date(2024, 1, 1): 9.06,
                    date(2025, 9, 18): 9.45,
                    date(2026, 4, 26): 9.38,
                },
                ("AUD", "CNY"): {
                    date(2022, 1, 1): 4.61,
                    date(2024, 1, 1): 4.75,
                    date(2025, 9, 18): 4.62,
                    date(2026, 4, 26): 4.68,
                },
                ("CAD", "CNY"): {
                    date(2022, 1, 1): 5.01,
                    date(2024, 1, 1): 5.29,
                    date(2025, 9, 18): 5.20,
                    date(2026, 4, 26): 5.25,
                },
                ("CHF", "CNY"): {
                    date(2022, 1, 1): 6.92,
                    date(2024, 1, 1): 8.45,
                    date(2025, 9, 18): 8.53,
                    date(2026, 4, 26): 8.49,
                },
                ("HKD", "CNY"): {
                    date(2022, 1, 1): 0.81,
                    date(2024, 1, 1): 0.91,
                    date(2025, 9, 18): 0.91,
                    date(2026, 4, 26): 0.92,
                },
                ("NZD", "CNY"): {
                    date(2022, 1, 1): 4.34,
                    date(2024, 1, 1): 4.46,
                    date(2025, 9, 18): 4.28,
                    date(2026, 4, 26): 4.33,
                },
                ("SGD", "CNY"): {
                    date(2022, 1, 1): 4.72,
                    date(2024, 1, 1): 5.37,
                    date(2025, 9, 18): 5.56,
                    date(2026, 4, 26): 5.57,
                },
            },
            "PRIMARY",
        )
        default_fallback = StaticExchangeRateProvider(
            {
                ("USD", "CNY"): {
                    date(2026, 4, 24): 7.19,
                    date(2026, 4, 25): 7.20,
                }
            },
            "FALLBACK",
        )
        self.primary_provider = primary_provider or default_primary
        self.fallback_provider = fallback_provider or default_fallback
        self.max_retries = max_retries
        self.retry_interval_seconds = retry_interval_seconds
        self.cache: Dict[Tuple[str, str, Optional[str]], Dict[str, Any]] = {}

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = payload.get("timestamp")
        cache_key = (
            payload["base_currency"].upper(),
            payload["quote_currency"].upper(),
            timestamp,
        )
        if cache_key in self.cache:
            return self.cache[cache_key]

        parsed_timestamp = datetime.fromisoformat(timestamp) if timestamp else None
        for provider in (self.primary_provider, self.fallback_provider):
            last_error: Optional[ToolExecutionError] = None
            for attempt in range(self.max_retries):
                try:
                    record = provider.fetch(
                        base_currency=payload["base_currency"],
                        quote_currency=payload["quote_currency"],
                        target_timestamp=parsed_timestamp,
                    )
                    result = {
                        "base_currency": payload["base_currency"].upper(),
                        "quote_currency": payload["quote_currency"].upper(),
                        "rate": record.rate,
                        "rate_timestamp": record.rate_timestamp.isoformat(),
                        "is_estimated": record.is_estimated,
                        "source": record.source,
                        "cache_hit": False,
                    }
                    self.cache[cache_key] = result
                    return result
                except ToolExecutionError as exc:
                    last_error = exc
                    if not exc.retryable or attempt == self.max_retries - 1:
                        break
                    if self.retry_interval_seconds:
                        sleep(self.retry_interval_seconds)
            if last_error and last_error.code != "currency_pair_not_found":
                continue

        raise ToolExecutionError(
            "failed to fetch exchange rate from all configured providers",
            code="exchange_rate_unavailable",
            retryable=True,
        )
