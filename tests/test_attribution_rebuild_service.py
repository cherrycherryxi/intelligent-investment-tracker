from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import LotStatus
from investment_tracker.data.models import Attribution, FundingLot, ValuationSnapshot
from investment_tracker.data.services import AttributionRebuildService, PortfolioEventService


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_rebuild_user_attribution_replays_existing_events_without_duplicates() -> None:
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
            "event_type": "FUND_BUY",
            "event_time": datetime(2026, 5, 2, tzinfo=timezone.utc),
            "asset_entries": [
                {
                    "asset": {"asset_type": "FUND", "asset_code": "USD-FUND", "currency": "USD"},
                    "quantity_delta": 100,
                    "cash_currency": "USD",
                    "cash_amount": 100,
                    "unit_price": 1,
                    "fx_rate_to_cny": 7.1,
                }
            ],
        },
    )
    first_count = session.query(Attribution).count()

    summary = AttributionRebuildService(session).rebuild_user_attribution(user_id=1)
    session.commit()

    assert first_count == 1
    assert summary["events_replayed"] == 2
    assert session.query(Attribution).count() == 1
    assert Decimal(session.query(Attribution).one().rmb_basis) == Decimal("720.00")


def test_rebuild_marks_incomplete_data_without_fabricating_lineage() -> None:
    session = _session()
    PortfolioEventService(session).create_event(
        user_id=1,
        payload={
            "event_type": "MANUAL_ADJUSTMENT",
            "event_time": datetime(2026, 5, 1, tzinfo=timezone.utc),
            "cash_entries": [{"currency": "USD", "amount_delta": 100, "unknown_basis": True}],
        },
    )

    summary = AttributionRebuildService(session).rebuild_user_attribution(user_id=1)
    session.commit()

    lot = session.query(FundingLot).one()
    assert summary["created_records"]["funding_lots"] == 1
    assert lot.status == LotStatus.BASIS_MISSING
    assert lot.original_rmb_basis is None


def test_valuation_snapshot_changes_do_not_rebuild_attribution_records() -> None:
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
    event = service.create_event(
        user_id=1,
        payload={
            "event_type": "FUND_BUY",
            "event_time": datetime(2026, 5, 2, tzinfo=timezone.utc),
            "asset_entries": [
                {
                    "asset": {"asset_type": "FUND", "asset_code": "USD-FUND", "currency": "USD"},
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
    before = (session.query(FundingLot).count(), session.query(Attribution).count())

    session.add(
        ValuationSnapshot(
            user_id=1,
            asset_id=asset_id,
            valuation_time=datetime(2026, 5, 3, tzinfo=timezone.utc),
            quantity=Decimal("120"),
            price=Decimal("1"),
            market_value=Decimal("120"),
            currency="USD",
        )
    )
    session.commit()

    after = (session.query(FundingLot).count(), session.query(Attribution).count())
    assert after == before
