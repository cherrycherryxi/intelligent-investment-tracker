from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import EventType, RateSourceType
from investment_tracker.data.models import ExchangeRate
from investment_tracker.data.services import PerformanceService, PortfolioEventService


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def _rate(session, currency: str, rate: str) -> None:
    session.add(
        ExchangeRate(
            base_currency=currency,
            quote_currency="CNY",
            rate=Decimal(rate),
            rate_timestamp=datetime(2026, 4, 29, tzinfo=timezone.utc),
            is_estimated=False,
            source=RateSourceType.MANUAL,
        )
    )
    session.commit()


def test_performance_includes_foreign_cash_and_splits_fx_pnl() -> None:
    session = _session()
    _rate(session, "USD", "7.000000")
    events = PortfolioEventService(session)
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "CNY", "amount_delta": -72000, "rmb_amount": 72000, "fx_rate_to_cny": 1, "is_external_flow": True},
                {"currency": "USD", "amount_delta": 10000, "rmb_amount": 72000, "fx_rate_to_cny": 7.2},
            ],
        },
    )

    result = PerformanceService(session).performance(user_id=1)

    assert result["overview"]["current_total_assets_cny"] == 70000.0
    assert result["overview"]["net_invested_cny"] == 72000.0
    assert result["overview"]["total_pnl_cny"] == -2000.0
    assert result["overview"]["investment_pnl_cny"] == 0.0
    assert result["overview"]["fx_pnl_cny"] == -2000.0


def test_fx_swap_changes_currency_pools_without_external_cny_flow() -> None:
    session = _session()
    _rate(session, "USD", "7.000000")
    _rate(session, "EUR", "8.000000")
    events = PortfolioEventService(session)
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "CNY", "amount_delta": -72000, "rmb_amount": 72000, "fx_rate_to_cny": 1, "is_external_flow": True},
                {"currency": "USD", "amount_delta": 10000, "rmb_amount": 72000, "fx_rate_to_cny": 7.2},
            ],
        },
    )
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_SWAP.value,
            "event_time": datetime(2026, 2, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": -5000, "rmb_amount": 35000, "fx_rate_to_cny": 7.0},
                {"currency": "EUR", "amount_delta": 4375, "rmb_amount": 35000, "fx_rate_to_cny": 8.0},
            ],
        },
    )

    result = PerformanceService(session).performance(user_id=1)
    by_currency = {item["currency"]: item for item in result["by_currency"]}

    assert result["overview"]["net_invested_cny"] == 72000.0
    assert by_currency["USD"]["cash_balance"] == 5000.0
    assert by_currency["EUR"]["cash_balance"] == 4375.0


def test_amount_valued_assets_do_not_require_extra_valuation_snapshot() -> None:
    session = _session()
    events = PortfolioEventService(session)
    event = events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.BOND_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "asset_entries": [
                {
                    "asset": {"asset_type": "BOND", "asset_code": "US-BOND-1", "asset_name": "USD Bond", "currency": "USD"},
                    "quantity_delta": 100,
                    "cash_currency": "USD",
                    "cash_amount": 10000,
                    "unit_price": 100,
                }
            ],
        },
    )

    result = PerformanceService(session).performance(user_id=1)

    assert result["data_quality"]["missing_rates"] == ["USD"]
    assert result["data_quality"]["missing_valuations"] == []
    assert result["by_currency"][0]["asset_market_value_native"] == 100.0
    assert event.id is not None
