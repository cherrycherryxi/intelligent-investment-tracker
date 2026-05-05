from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import FundingSourceType
from investment_tracker.data.models import Attribution, FundingLot
from investment_tracker.data.services import PortfolioEventService


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_redemption_reduces_product_attribution_fifo_and_creates_inherited_basis_lot() -> None:
    session = _session()
    service = PortfolioEventService(session)
    service.create_event(
        user_id=1,
        payload={
            "event_type": "FX_BUY",
            "event_time": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 200, "rmb_amount": 1440, "fx_rate_to_cny": 7.2},
            ],
        },
    )
    asset_payload = {"asset_type": "FUND", "asset_code": "USD-FUND", "currency": "USD"}
    service.create_event(
        user_id=1,
        payload={
            "event_type": "FUND_BUY",
            "event_time": datetime(2026, 5, 2, tzinfo=timezone.utc),
            "asset_entries": [
                {
                    "asset": asset_payload,
                    "quantity_delta": 100,
                    "cash_currency": "USD",
                    "cash_amount": 100,
                    "unit_price": 1,
                    "fx_rate_to_cny": 7.1,
                }
            ],
        },
    )
    buy_event = service.create_event(
        user_id=1,
        payload={
            "event_type": "FUND_BUY",
            "event_time": datetime(2026, 5, 3, tzinfo=timezone.utc),
            "asset_entries": [
                {
                    "asset": asset_payload,
                    "quantity_delta": 100,
                    "cash_currency": "USD",
                    "cash_amount": 100,
                    "unit_price": 1,
                    "fx_rate_to_cny": 7.4,
                }
            ],
        },
    )
    asset_id = session.query(Attribution.target_asset_id).filter(Attribution.target_event_id == buy_event.id).scalar()

    service.create_event(
        user_id=1,
        payload={
            "event_type": "FUND_SELL",
            "event_time": datetime(2026, 5, 4, tzinfo=timezone.utc),
            "cash_entries": [{"currency": "USD", "amount_delta": 150, "fx_rate_to_cny": 7.5}],
            "asset_entries": [
                {
                    "asset_id": asset_id,
                    "quantity_delta": -150,
                    "cash_currency": "USD",
                    "cash_amount": 150,
                    "unit_price": 1,
                    "fx_rate_to_cny": 7.5,
                }
            ],
        },
    )
    session.commit()

    remaining_attributions = session.query(Attribution).order_by(Attribution.id.asc()).all()
    redemption_lot = (
        session.query(FundingLot)
        .filter(FundingLot.source_type == FundingSourceType.REDEMPTION)
        .one()
    )

    assert Decimal(remaining_attributions[0].native_amount) == Decimal("0.000000")
    assert Decimal(remaining_attributions[0].rmb_basis) == Decimal("0.00")
    assert Decimal(remaining_attributions[1].native_amount) == Decimal("50.000000")
    assert Decimal(remaining_attributions[1].rmb_basis) == Decimal("360.00")
    assert Decimal(redemption_lot.original_amount) == Decimal("150.000000")
    assert Decimal(redemption_lot.original_rmb_basis) == Decimal("1080.00")

    downstream_event = service.create_event(
        user_id=1,
        payload={
            "event_type": "WEALTH_BUY",
            "event_time": datetime(2026, 5, 5, tzinfo=timezone.utc),
            "asset_entries": [
                {
                    "asset": {"asset_type": "WEALTH_PRODUCT", "asset_code": "USD-WEALTH", "currency": "USD"},
                    "quantity_delta": 150,
                    "cash_currency": "USD",
                    "cash_amount": 150,
                    "unit_price": 1,
                    "fx_rate_to_cny": 8.0,
                }
            ],
        },
    )
    downstream_attribution = (
        session.query(Attribution)
        .filter(Attribution.target_event_id == downstream_event.id)
        .one()
    )

    assert Decimal(downstream_attribution.rmb_basis) == Decimal("1080.00")
    assert Decimal(downstream_attribution.rmb_basis) != Decimal("1200.00")


def test_redemption_without_attribution_keeps_spot_basis_fallback() -> None:
    session = _session()
    service = PortfolioEventService(session)
    event = service.create_event(
        user_id=1,
        payload={
            "event_type": "FUND_BUY",
            "event_time": datetime(2026, 5, 2, tzinfo=timezone.utc),
            "asset_entries": [
                {
                    "asset": {"asset_type": "FUND", "asset_code": "LEGACY-FUND", "currency": "USD"},
                    "quantity_delta": 100,
                    "cash_currency": "USD",
                    "cash_amount": 100,
                    "unit_price": 1,
                    "fx_rate_to_cny": 7.1,
                }
            ],
        },
    )
    asset_id = event.asset_ledger_entries[0].asset_id

    service.create_event(
        user_id=1,
        payload={
            "event_type": "FUND_SELL",
            "event_time": datetime(2026, 5, 4, tzinfo=timezone.utc),
            "cash_entries": [{"currency": "USD", "amount_delta": 100, "fx_rate_to_cny": 7.5}],
            "asset_entries": [
                {
                    "asset_id": asset_id,
                    "quantity_delta": -100,
                    "cash_currency": "USD",
                    "cash_amount": 100,
                    "unit_price": 1,
                    "fx_rate_to_cny": 7.5,
                }
            ],
        },
    )
    session.commit()

    redemption_lot = session.query(FundingLot).filter(FundingLot.source_type == FundingSourceType.REDEMPTION).one()

    assert Decimal(redemption_lot.original_rmb_basis) == Decimal("750.00")
