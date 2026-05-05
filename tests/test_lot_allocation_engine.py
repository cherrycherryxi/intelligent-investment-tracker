from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import (
    AttributionStatus,
    EventType,
    FundingSourceType,
    GapType,
    LotStatus,
)
from investment_tracker.data.models import AttributionGap, FundingLot, PortfolioEvent, User
from investment_tracker.data.services import FundingLotManager, LotAllocationEngine


def _build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _create_user_and_events(session):
    user = User(username="allocation-user", email="allocation-user@example.com")
    session.add(user)
    session.flush()
    source_event = PortfolioEvent(
        user_id=user.id,
        event_type=EventType.FX_BUY,
        event_time=datetime.now(timezone.utc),
    )
    consuming_event = PortfolioEvent(
        user_id=user.id,
        event_type=EventType.FUND_BUY,
        event_time=datetime.now(timezone.utc),
    )
    session.add_all([source_event, consuming_event])
    session.flush()
    return user, source_event, consuming_event


def test_fifo_allocation_consumes_oldest_lots_first() -> None:
    session = _build_session()
    user, source_event, consuming_event = _create_user_and_events(session)
    manager = FundingLotManager(session)
    allocation_time = datetime(2026, 5, 4, tzinfo=timezone.utc)
    newer = manager.create_lot(
        user_id=user.id,
        currency="USD",
        native_amount=Decimal("500.000000"),
        rmb_basis=Decimal("3650.00"),
        source_event_id=source_event.id,
        source_type=FundingSourceType.FX_BUY,
        created_at=allocation_time - timedelta(days=1),
    )
    older = manager.create_lot(
        user_id=user.id,
        currency="USD",
        native_amount=Decimal("300.000000"),
        rmb_basis=Decimal("2100.00"),
        source_event_id=source_event.id,
        source_type=FundingSourceType.FX_BUY,
        created_at=allocation_time - timedelta(days=2),
    )

    result = LotAllocationEngine(session, lot_manager=manager).allocate(
        user_id=user.id,
        currency="USD",
        amount_needed=Decimal("400.000000"),
        consuming_event_id=consuming_event.id,
        allocation_time=allocation_time,
    )
    session.commit()

    assert [allocation.lot_id for allocation in result.allocations] == [older.id, newer.id]
    assert [allocation.native_amount for allocation in result.allocations] == [
        Decimal("300.000000"),
        Decimal("100.000000"),
    ]
    assert result.rmb_cost == Decimal("2830.00")
    assert result.shortfall_amount == Decimal("0.000000")
    assert session.get(FundingLot, older.id).status == LotStatus.FULLY_CONSUMED
    assert Decimal(session.get(FundingLot, newer.id).remaining_amount) == Decimal("400.000000")


def test_allocation_creates_gap_when_funding_is_insufficient() -> None:
    session = _build_session()
    user, source_event, consuming_event = _create_user_and_events(session)
    manager = FundingLotManager(session)
    allocation_time = datetime(2026, 5, 4, tzinfo=timezone.utc)
    manager.create_lot(
        user_id=user.id,
        currency="USD",
        native_amount=Decimal("300.000000"),
        rmb_basis=Decimal("2100.00"),
        source_event_id=source_event.id,
        source_type=FundingSourceType.FX_BUY,
        created_at=allocation_time - timedelta(days=1),
    )

    result = LotAllocationEngine(session, lot_manager=manager).allocate(
        user_id=user.id,
        currency="USD",
        amount_needed=Decimal("500.000000"),
        consuming_event_id=consuming_event.id,
        allocation_time=allocation_time,
    )
    session.commit()

    gap = session.query(AttributionGap).one()
    assert result.shortfall_amount == Decimal("200.000000")
    assert result.gap.id == gap.id
    assert gap.gap_type == GapType.UNATTRIBUTED_FUNDING
    assert gap.status == AttributionStatus.INCOMPLETE
    assert Decimal(gap.shortfall_amount) == Decimal("200.000000")


def test_multi_lot_allocation_conserves_native_amount_and_rmb_basis() -> None:
    session = _build_session()
    user, source_event, consuming_event = _create_user_and_events(session)
    manager = FundingLotManager(session)
    allocation_time = datetime(2026, 5, 4, tzinfo=timezone.utc)
    for idx, (amount, basis) in enumerate(
        [
            (Decimal("100.000000"), Decimal("700.00")),
            (Decimal("200.000000"), Decimal("1420.00")),
            (Decimal("300.000000"), Decimal("2190.00")),
        ]
    ):
        manager.create_lot(
            user_id=user.id,
            currency="USD",
            native_amount=amount,
            rmb_basis=basis,
            source_event_id=source_event.id,
            source_type=FundingSourceType.FX_BUY,
            created_at=allocation_time - timedelta(days=3 - idx),
        )

    result = LotAllocationEngine(session, lot_manager=manager).allocate(
        user_id=user.id,
        currency="USD",
        amount_needed=Decimal("450.000000"),
        consuming_event_id=consuming_event.id,
        allocation_time=allocation_time,
    )
    session.commit()

    assert sum((item.native_amount for item in result.allocations), Decimal("0.000000")) == Decimal(
        "450.000000"
    )
    assert result.rmb_cost == Decimal("3215.00")
    assert result.shortfall_amount == Decimal("0.000000")
