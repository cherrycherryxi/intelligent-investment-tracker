from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import FundingSourceType, LotStatus
from investment_tracker.data.models import AttributionGap, FundingLot
from investment_tracker.data.services import PortfolioEventService


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_fx_buy_event_creates_funding_lot_with_direct_rmb_basis() -> None:
    session = _session()

    PortfolioEventService(session).create_event(
        user_id=1,
        payload={
            "event_type": "FX_BUY",
            "event_time": datetime(2026, 5, 4, tzinfo=timezone.utc),
            "cash_entries": [
                {"currency": "CNY", "amount_delta": -7200, "rmb_amount": 7200, "is_external_flow": True},
                {"currency": "USD", "amount_delta": 1000, "rmb_amount": 7200, "fx_rate_to_cny": 7.2},
            ],
        },
    )

    lot = session.query(FundingLot).one()
    assert lot.currency == "USD"
    assert lot.source_type == FundingSourceType.FX_BUY
    assert lot.status == LotStatus.AVAILABLE
    assert Decimal(lot.original_amount) == Decimal("1000.000000")
    assert Decimal(lot.original_rmb_basis) == Decimal("7200.00")


def test_fx_swap_consumes_source_lot_and_creates_target_lot_with_inherited_basis() -> None:
    session = _session()
    service = PortfolioEventService(session)
    service.create_event(
        user_id=1,
        payload={
            "event_type": "FX_BUY",
            "event_time": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 1000, "rmb_amount": 7200, "fx_rate_to_cny": 7.2},
            ],
        },
    )

    service.create_event(
        user_id=1,
        payload={
            "event_type": "FX_SWAP",
            "event_time": datetime(2026, 5, 2, tzinfo=timezone.utc),
            "cash_entries": [
                {"currency": "USD", "amount_delta": -400, "is_external_flow": False},
                {"currency": "EUR", "amount_delta": 350, "is_external_flow": False},
            ],
        },
    )

    lots = session.query(FundingLot).order_by(FundingLot.id.asc()).all()
    usd_lot, eur_lot = lots
    assert Decimal(usd_lot.remaining_amount) == Decimal("600.000000")
    assert Decimal(usd_lot.remaining_rmb_basis) == Decimal("4320.00")
    assert eur_lot.source_type == FundingSourceType.FX_SWAP
    assert Decimal(eur_lot.original_amount) == Decimal("350.000000")
    assert Decimal(eur_lot.original_rmb_basis) == Decimal("2880.00")
    assert session.query(AttributionGap).count() == 0


def test_fx_sell_consumes_sold_currency_lots() -> None:
    session = _session()
    service = PortfolioEventService(session)
    service.create_event(
        user_id=1,
        payload={
            "event_type": "FX_BUY",
            "event_time": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 1000, "rmb_amount": 7200, "fx_rate_to_cny": 7.2},
            ],
        },
    )

    service.create_event(
        user_id=1,
        payload={
            "event_type": "FX_SELL",
            "event_time": datetime(2026, 5, 2, tzinfo=timezone.utc),
            "cash_entries": [
                {"currency": "USD", "amount_delta": -250, "rmb_amount": 1800, "fx_rate_to_cny": 7.2},
                {"currency": "CNY", "amount_delta": 1800, "rmb_amount": 1800, "fx_rate_to_cny": 1},
            ],
        },
    )

    lot = session.query(FundingLot).one()
    assert Decimal(lot.remaining_amount) == Decimal("750.000000")
    assert Decimal(lot.remaining_rmb_basis) == Decimal("5400.00")
    assert session.query(AttributionGap).count() == 0


def test_fx_swap_with_insufficient_source_lots_marks_target_basis_missing() -> None:
    session = _session()
    service = PortfolioEventService(session)
    service.create_event(
        user_id=1,
        payload={
            "event_type": "FX_SWAP",
            "event_time": datetime(2026, 5, 2, tzinfo=timezone.utc),
            "cash_entries": [
                {"currency": "USD", "amount_delta": -400, "is_external_flow": False},
                {"currency": "EUR", "amount_delta": 350, "is_external_flow": False},
            ],
        },
    )

    lot = session.query(FundingLot).one()
    assert lot.currency == "EUR"
    assert lot.status == LotStatus.BASIS_MISSING
    assert lot.original_rmb_basis is None
    assert Decimal(session.query(AttributionGap).one().shortfall_amount) == Decimal("400.000000")


def test_redemption_event_creates_lot_from_asset_carrying_value_fallback() -> None:
    session = _session()
    service = PortfolioEventService(session)

    service.create_event(
        user_id=1,
        payload={
            "event_type": "FUND_SELL",
            "event_time": datetime(2026, 5, 4, tzinfo=timezone.utc),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 100, "fx_rate_to_cny": 7.1},
            ],
            "asset_entries": [
                {
                    "asset": {"asset_type": "FUND", "asset_code": "USD-FUND", "currency": "USD"},
                    "quantity_delta": -100,
                    "cash_currency": "USD",
                    "cash_amount": 100,
                    "unit_price": 1,
                    "fx_rate_to_cny": 7.1,
                }
            ],
        },
    )

    lot = session.query(FundingLot).one()
    assert lot.source_type == FundingSourceType.REDEMPTION
    assert Decimal(lot.original_amount) == Decimal("100.000000")
    assert Decimal(lot.original_rmb_basis) == Decimal("710.00")


def test_manual_adjustment_requires_explicit_basis_for_foreign_inflow() -> None:
    session = _session()
    service = PortfolioEventService(session)

    with pytest.raises(ValueError, match="MANUAL_ADJUSTMENT foreign inflow requires"):
        service.create_event(
            user_id=1,
            payload={
                "event_type": "MANUAL_ADJUSTMENT",
                "event_time": datetime(2026, 5, 4, tzinfo=timezone.utc),
                "cash_entries": [{"currency": "USD", "amount_delta": 100}],
            },
        )


def test_manual_adjustment_creates_basis_missing_lot_when_unknown_is_explicit() -> None:
    session = _session()

    PortfolioEventService(session).create_event(
        user_id=1,
        payload={
            "event_type": "MANUAL_ADJUSTMENT",
            "event_time": datetime(2026, 5, 4, tzinfo=timezone.utc),
            "cash_entries": [{"currency": "USD", "amount_delta": 100, "unknown_basis": True}],
        },
    )

    lot = session.query(FundingLot).one()
    assert lot.source_type == FundingSourceType.MANUAL_ADJUSTMENT
    assert lot.status == LotStatus.BASIS_MISSING
