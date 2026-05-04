"""Exchange rate lookup with retry and cache support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from time import sleep
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


class FrankfurterExchangeRateProvider(ExchangeRateProvider):
    """Fetch latest or historical FX rates from the public Frankfurter API."""

    provider_name = "frankfurter"

    def __init__(
        self,
        *,
        base_url: str = "https://api.frankfurter.dev/v2/rates",
        timeout_seconds: float = 5.0,
        opener=urlopen,
        source_label: str = "PRIMARY",
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.opener = opener
        self.source_label = source_label

    def fetch(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        target_timestamp: Optional[datetime],
    ) -> ExchangeRateRecord:
        target_day = target_timestamp.date() if target_timestamp else None
        query = {
            "base": base_currency.upper(),
            "quotes": quote_currency.upper(),
        }
        if target_day is not None:
            query["date"] = target_day.isoformat()
        url = f"{self.base_url}?{urlencode(query)}"

        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "investment-assistant/0.1",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ToolExecutionError(
                f"exchange-rate provider rejected request: {exc.code}",
                code="exchange_rate_http_error",
                retryable=500 <= exc.code < 600,
            ) from exc
        except (OSError, URLError, TimeoutError, ValueError) as exc:
            raise ToolExecutionError(
                "exchange-rate provider request failed",
                code="exchange_rate_provider_unavailable",
                retryable=True,
            ) from exc

        quote = quote_currency.upper()
        parsed_rate, response_day_text = self._parse_payload(payload, quote_currency=quote)
        if parsed_rate is None:
            raise ToolExecutionError(
                "currency pair not available in provider",
                code="currency_pair_not_found",
                retryable=False,
            )

        try:
            response_day = date.fromisoformat(response_day_text) if response_day_text else (target_day or datetime.utcnow().date())
        except ValueError as exc:
            raise ToolExecutionError(
                "exchange-rate provider returned invalid date",
                code="exchange_rate_invalid_response",
                retryable=True,
            ) from exc

        return ExchangeRateRecord(
            rate=parsed_rate,
            rate_timestamp=datetime.combine(response_day, datetime.min.time()),
            is_estimated=target_day is not None and response_day != target_day,
            source=self.source_label,
        )

    def _parse_payload(self, payload: Any, *, quote_currency: str) -> tuple[Optional[float], Optional[str]]:
        if isinstance(payload, dict):
            rates = payload.get("rates") or {}
            rate = rates.get(quote_currency)
            return (float(rate), payload.get("date")) if rate is not None else (None, payload.get("date"))

        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                if str(item.get("quote", "")).upper() != quote_currency:
                    continue
                rate = item.get("rate")
                return (float(rate), item.get("date")) if rate is not None else (None, item.get("date"))

        return None, None


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
        default_fallback = StaticExchangeRateProvider(
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
            "FALLBACK",
        )
        self.primary_provider = primary_provider or FrankfurterExchangeRateProvider()
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
