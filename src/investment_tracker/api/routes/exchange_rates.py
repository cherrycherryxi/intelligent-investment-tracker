"""Exchange-rate API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from investment_tracker.api.schemas import ExchangeRateRefreshRequest
from investment_tracker.data.db import get_db_session
from investment_tracker.data.services import ExchangeRateService


router = APIRouter(prefix="/api/exchange-rates", tags=["exchange-rates"])


@router.post("/refresh")
async def refresh_exchange_rates(payload: ExchangeRateRefreshRequest) -> dict:
    with get_db_session() as session:
        service = ExchangeRateService(session)
        rows = service.refresh_rates(currencies=payload.currencies)
    return {
        "refreshed_count": len(rows),
        "rates": [
            {
                "base_currency": row.base_currency,
                "quote_currency": row.quote_currency,
                "rate": float(row.rate),
                "rate_timestamp": row.rate_timestamp.isoformat(),
                "is_estimated": row.is_estimated,
                "source": row.source.value,
            }
            for row in rows
        ],
    }


@router.get("/latest")
async def latest_exchange_rates(currencies: Optional[str] = None) -> dict:
    requested = [item.strip().upper() for item in currencies.split(",")] if currencies else None
    with get_db_session() as session:
        service = ExchangeRateService(session)
        rows = service.latest_rates(currencies=requested)
    return {
        "rates": [
            {
                "base_currency": row.base_currency,
                "quote_currency": row.quote_currency,
                "rate": float(row.rate),
                "rate_timestamp": row.rate_timestamp.isoformat(),
                "is_estimated": row.is_estimated,
                "source": row.source.value,
            }
            for row in rows
        ]
    }
