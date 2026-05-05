from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import (
    AssetType,
    AttributionStatus,
    FundingSourceType,
    GapType,
    LotStatus,
)
from investment_tracker.data.models import Asset, AttributionGap
from investment_tracker.data.services import (
    AttributionStatusTracker,
    AttributionStore,
    FundingLotManager,
    PortfolioEventService,
)


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _asset(session, *, currency: str = "USD") -> Asset:
    asset = Asset(asset_type=AssetType.FUND, asset_code=f"{currency}-FUND", currency=currency)
    session.add(asset)
    session.flush()
    return asset


def _event(session, *, event_type: str = "FUND_BUY"):
    return PortfolioEventService(session).create_event(
        user_id=1,
        payload={
            "event_type": event_type,
            "event_time": datetime(2026, 5, 4, tzinfo=timezone.utc),
        },
        commit=False,
    )


def test_cny_asset_attribution_status_is_not_applicable() -> None:
    session = _session()
    asset = _asset(session, currency="CNY")
    session.commit()

    status = AttributionStatusTracker(session).compute_status(asset_id=asset.id, user_id=1)

    assert status == AttributionStatus.NOT_APPLICABLE


def test_foreign_asset_with_attribution_and_no_gaps_is_complete() -> None:
    session = _session()
    asset = _asset(session)
    event = _event(session)
    lot = FundingLotManager(session).create_lot(
        user_id=1,
        currency="USD",
        native_amount=Decimal("100.000000"),
        rmb_basis=Decimal("720.00"),
        source_event_id=None,
        source_type=FundingSourceType.CARRYFORWARD,
    )
    AttributionStore(session).record_allocation(
        target_event_id=event.id,
        target_asset_id=asset.id,
        source_lot_id=lot.id,
        native_amount=Decimal("100.000000"),
        rmb_basis=Decimal("720.00"),
    )
    session.commit()

    status = AttributionStatusTracker(session).compute_status(asset_id=asset.id, user_id=1)

    assert status == AttributionStatus.COMPLETE


def test_foreign_asset_with_unresolved_gap_is_incomplete() -> None:
    session = _session()
    asset = _asset(session)
    event = _event(session)
    session.add(
        AttributionGap(
            user_id=1,
            event_id=event.id,
            asset_id=asset.id,
            gap_type=GapType.UNATTRIBUTED_FUNDING,
            currency="USD",
            shortfall_amount=Decimal("50.000000"),
            status=AttributionStatus.INCOMPLETE,
            detected_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        )
    )
    session.commit()

    status = AttributionStatusTracker(session).compute_status(asset_id=asset.id, user_id=1)

    assert status == AttributionStatus.INCOMPLETE


def test_basis_missing_source_lot_takes_status_precedence() -> None:
    session = _session()
    asset = _asset(session)
    event = _event(session)
    lot = FundingLotManager(session).create_lot(
        user_id=1,
        currency="USD",
        native_amount=Decimal("100.000000"),
        rmb_basis=None,
        source_event_id=None,
        source_type=FundingSourceType.CARRYFORWARD,
    )
    AttributionStore(session).record_allocation(
        target_event_id=event.id,
        target_asset_id=asset.id,
        source_lot_id=lot.id,
        native_amount=Decimal("100.000000"),
        rmb_basis=Decimal("0.00"),
    )
    session.commit()

    status = AttributionStatusTracker(session).compute_status(asset_id=asset.id, user_id=1)

    assert lot.status == LotStatus.BASIS_MISSING
    assert status == AttributionStatus.BASIS_MISSING


def test_gap_correction_suggestion_is_actionable() -> None:
    session = _session()
    gap = AttributionGap(
        user_id=1,
        event_id=1,
        asset_id=1,
        gap_type=GapType.UNATTRIBUTED_FUNDING,
        currency="USD",
        shortfall_amount=Decimal("50.000000"),
        status=AttributionStatus.INCOMPLETE,
        detected_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )

    suggestions = AttributionStatusTracker(session).suggest_corrections(gap=gap)

    assert suggestions
    assert suggestions[0]["action"] == "CREATE_MANUAL_ADJUSTMENT"
    assert suggestions[0]["currency"] == "USD"
    assert suggestions[0]["amount"] == 50.0
