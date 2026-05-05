from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import EventType, FundingSourceType, LotStatus
from investment_tracker.data.models import FundingLot, PortfolioEvent, User
from investment_tracker.data.services import FundingLotManager


def _build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _create_event(session, *, user_id: int, event_type: EventType = EventType.FX_BUY) -> PortfolioEvent:
    event = PortfolioEvent(
        user_id=user_id,
        event_type=event_type,
        event_time=datetime.now(timezone.utc),
    )
    session.add(event)
    session.flush()
    return event


def _create_user(session) -> User:
    user = User(username="funding-user", email="funding-user@example.com")
    session.add(user)
    session.flush()
    return user


def test_create_lot_sets_available_status_and_basis_fields() -> None:
    session = _build_session()
    user = _create_user(session)
    event = _create_event(session, user_id=user.id)

    lot = FundingLotManager(session).create_lot(
        user_id=user.id,
        currency="usd",
        native_amount=Decimal("1000.000000"),
        rmb_basis=Decimal("7200.00"),
        source_event_id=event.id,
        source_type=FundingSourceType.FX_BUY,
        created_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )
    session.commit()

    assert lot.currency == "USD"
    assert lot.status == LotStatus.AVAILABLE
    assert Decimal(lot.original_amount) == Decimal("1000.000000")
    assert Decimal(lot.remaining_amount) == Decimal("1000.000000")
    assert Decimal(lot.original_rmb_basis) == Decimal("7200.00")
    assert Decimal(lot.remaining_rmb_basis) == Decimal("7200.00")


def test_create_lot_without_basis_is_excluded_from_available_lots() -> None:
    session = _build_session()
    user = _create_user(session)
    event = _create_event(session, user_id=user.id)
    manager = FundingLotManager(session)

    lot = manager.create_lot(
        user_id=user.id,
        currency="USD",
        native_amount=Decimal("1000.000000"),
        rmb_basis=None,
        source_event_id=event.id,
        source_type=FundingSourceType.CARRYFORWARD,
    )
    session.commit()

    assert lot.status == LotStatus.BASIS_MISSING
    assert manager.get_available_lots(user_id=user.id, currency="USD") == []


def test_get_available_lots_uses_fifo_order_and_as_of_time() -> None:
    session = _build_session()
    user = _create_user(session)
    event = _create_event(session, user_id=user.id)
    manager = FundingLotManager(session)
    base_time = datetime(2026, 5, 4, tzinfo=timezone.utc)

    newer = manager.create_lot(
        user_id=user.id,
        currency="USD",
        native_amount=Decimal("200.000000"),
        rmb_basis=Decimal("1440.00"),
        source_event_id=event.id,
        source_type=FundingSourceType.FX_BUY,
        created_at=base_time + timedelta(days=1),
    )
    older = manager.create_lot(
        user_id=user.id,
        currency="USD",
        native_amount=Decimal("100.000000"),
        rmb_basis=Decimal("720.00"),
        source_event_id=event.id,
        source_type=FundingSourceType.FX_BUY,
        created_at=base_time,
    )
    session.commit()

    all_lots = manager.get_available_lots(user_id=user.id, currency="USD")
    cutoff_lots = manager.get_available_lots(user_id=user.id, currency="USD", as_of_time=base_time)

    assert [lot.id for lot in all_lots] == [older.id, newer.id]
    assert [lot.id for lot in cutoff_lots] == [older.id]


def test_consume_lot_preserves_cost_ratio_for_partial_consumption() -> None:
    session = _build_session()
    user = _create_user(session)
    source_event = _create_event(session, user_id=user.id)
    consuming_event = _create_event(session, user_id=user.id, event_type=EventType.FUND_BUY)
    manager = FundingLotManager(session)
    lot = manager.create_lot(
        user_id=user.id,
        currency="USD",
        native_amount=Decimal("1000.000000"),
        rmb_basis=Decimal("7200.00"),
        source_event_id=source_event.id,
        source_type=FundingSourceType.FX_BUY,
    )

    consumption = manager.consume_lot(
        lot_id=lot.id,
        amount_consumed=Decimal("250.000000"),
        consuming_event_id=consuming_event.id,
    )
    session.commit()

    stored = session.get(FundingLot, lot.id)
    assert Decimal(consumption.rmb_basis_consumed) == Decimal("1800.00")
    assert Decimal(stored.remaining_amount) == Decimal("750.000000")
    assert Decimal(stored.remaining_rmb_basis) == Decimal("5400.00")
    assert stored.status == LotStatus.AVAILABLE


def test_consume_lot_marks_fully_consumed_without_deleting_lot() -> None:
    session = _build_session()
    user = _create_user(session)
    source_event = _create_event(session, user_id=user.id)
    consuming_event = _create_event(session, user_id=user.id, event_type=EventType.WEALTH_BUY)
    manager = FundingLotManager(session)
    lot = manager.create_lot(
        user_id=user.id,
        currency="USD",
        native_amount=Decimal("1000.000000"),
        rmb_basis=Decimal("7200.00"),
        source_event_id=source_event.id,
        source_type=FundingSourceType.FX_BUY,
    )

    manager.consume_lot(
        lot_id=lot.id,
        amount_consumed=Decimal("1000.000000"),
        consuming_event_id=consuming_event.id,
    )
    session.commit()

    stored = session.get(FundingLot, lot.id)
    assert stored is not None
    assert stored.status == LotStatus.FULLY_CONSUMED
    assert Decimal(stored.remaining_amount) == Decimal("0.000000")
    assert Decimal(stored.remaining_rmb_basis) == Decimal("0.00")
    assert stored.fully_consumed_at is not None


def test_consume_lot_rejects_over_consumption() -> None:
    session = _build_session()
    user = _create_user(session)
    source_event = _create_event(session, user_id=user.id)
    consuming_event = _create_event(session, user_id=user.id, event_type=EventType.FUND_BUY)
    manager = FundingLotManager(session)
    lot = manager.create_lot(
        user_id=user.id,
        currency="USD",
        native_amount=Decimal("1000.000000"),
        rmb_basis=Decimal("7200.00"),
        source_event_id=source_event.id,
        source_type=FundingSourceType.FX_BUY,
    )

    with pytest.raises(ValueError, match="exceeds remaining_amount"):
        manager.consume_lot(
            lot_id=lot.id,
            amount_consumed=Decimal("1000.000001"),
            consuming_event_id=consuming_event.id,
        )
