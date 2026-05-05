from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import (
    AllocationPolicy,
    AssetType,
    EventType,
    FundingSourceType,
    LotStatus,
    RateSourceType,
    RecordStatus,
    TransactionDirection,
)
from investment_tracker.data.models import (
    Attribution,
    FundingLot,
    LotConsumption,
    PortfolioEvent,
    ExchangeRate,
    Position,
    Transaction,
    User,
)


def _build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)(), engine


def test_all_tables_are_created() -> None:
    _, engine = _build_session()
    tables = set(inspect(engine).get_table_names())
    assert {
        "users",
        "transactions",
        "positions",
        "exchange_rates",
        "investment_advice",
        "audit_logs",
        "funding_lots",
        "attributions",
        "attribution_gaps",
        "lot_consumptions",
    }.issubset(tables)


def test_transaction_insert_and_query() -> None:
    session, _ = _build_session()
    user = User(username="alice", email="alice@example.com", risk_preference="balanced")
    session.add(user)
    session.commit()

    transaction = Transaction(
        user_id=user.id,
        asset_type=AssetType.FOREX,
        asset_code="USD",
        asset_name="US Dollar",
        direction=TransactionDirection.BUY,
        quantity=Decimal("1000.000000"),
        unit_price=Decimal("7.200000"),
        trade_currency="CNY",
        trade_time=datetime.now(timezone.utc),
        exchange_rate_to_cny=Decimal("7.200000"),
        total_cost_cny=Decimal("7200.00"),
        source="manual",
        status=RecordStatus.CONFIRMED,
    )
    session.add(transaction)
    session.commit()

    stored = session.query(Transaction).filter_by(asset_code="USD").one()
    assert stored.direction == TransactionDirection.BUY
    assert Decimal(stored.total_cost_cny) == Decimal("7200.00")


def test_position_insert_and_update() -> None:
    session, _ = _build_session()
    user = User(username="bob", email="bob@example.com", risk_preference="low")
    session.add(user)
    session.commit()

    position = Position(
        user_id=user.id,
        asset_type=AssetType.BOND,
        asset_code="123456",
        asset_name="Sample Bond",
        quantity=Decimal("10.000000"),
        average_cost_cny=Decimal("99.500000"),
        cost_basis_cny=Decimal("995.00"),
    )
    session.add(position)
    session.commit()

    position.current_value_cny = Decimal("1005.00")
    session.commit()

    stored = session.query(Position).filter_by(asset_code="123456").one()
    assert Decimal(stored.current_value_cny) == Decimal("1005.00")


def test_exchange_rate_boolean_and_precision() -> None:
    session, _ = _build_session()
    rate = ExchangeRate(
        base_currency="USD",
        quote_currency="CNY",
        rate=Decimal("7.123456"),
        rate_timestamp=datetime.now(timezone.utc),
        is_estimated=True,
        source=RateSourceType.PRIMARY,
    )
    session.add(rate)
    session.commit()

    stored = session.query(ExchangeRate).one()
    assert stored.is_estimated is True
    assert Decimal(stored.rate) == Decimal("7.123456")


def test_funding_lot_creation_persists_complete_basis_data() -> None:
    session, _ = _build_session()
    user = User(username="carol", email="carol@example.com")
    session.add(user)
    session.flush()
    event = PortfolioEvent(
        user_id=user.id,
        event_type=EventType.FX_BUY,
        event_time=datetime.now(timezone.utc),
    )
    session.add(event)
    session.flush()

    lot = FundingLot(
        user_id=user.id,
        currency="USD",
        source_event_id=event.id,
        source_type=FundingSourceType.FX_BUY,
        original_amount=Decimal("1000.000000"),
        remaining_amount=Decimal("1000.000000"),
        original_rmb_basis=Decimal("7200.00"),
        remaining_rmb_basis=Decimal("7200.00"),
        status=LotStatus.AVAILABLE,
    )
    session.add(lot)
    session.commit()

    stored = session.query(FundingLot).one()
    assert stored.source_event.event_type == EventType.FX_BUY
    assert stored.currency == "USD"
    assert Decimal(stored.original_amount) == Decimal("1000.000000")
    assert Decimal(stored.remaining_amount) == Decimal("1000.000000")
    assert Decimal(stored.original_rmb_basis) == Decimal("7200.00")
    assert Decimal(stored.remaining_rmb_basis) == Decimal("7200.00")
    assert stored.status == LotStatus.AVAILABLE


def test_funding_lot_lifecycle_preserves_consumed_lot_record() -> None:
    session, _ = _build_session()
    user = User(username="dave", email="dave@example.com")
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
    lot = FundingLot(
        user_id=user.id,
        currency="USD",
        source_event_id=source_event.id,
        source_type=FundingSourceType.FX_BUY,
        original_amount=Decimal("1000.000000"),
        remaining_amount=Decimal("0.000000"),
        original_rmb_basis=Decimal("7200.00"),
        remaining_rmb_basis=Decimal("0.00"),
        status=LotStatus.FULLY_CONSUMED,
        fully_consumed_at=datetime.now(timezone.utc),
    )
    session.add(lot)
    session.flush()
    consumption = LotConsumption(
        lot_id=lot.id,
        consuming_event_id=consuming_event.id,
        amount_consumed=Decimal("1000.000000"),
        rmb_basis_consumed=Decimal("7200.00"),
        remaining_after=Decimal("0.000000"),
    )
    session.add(consumption)
    session.commit()

    stored = session.query(FundingLot).one()
    assert stored.status == LotStatus.FULLY_CONSUMED
    assert Decimal(stored.remaining_amount) == Decimal("0.000000")
    assert len(stored.consumptions) == 1
    assert stored.consumptions[0].consuming_event.event_type == EventType.FUND_BUY


def test_attribution_links_purchase_to_source_lot() -> None:
    session, _ = _build_session()
    user = User(username="erin", email="erin@example.com")
    session.add(user)
    session.flush()
    source_event = PortfolioEvent(
        user_id=user.id,
        event_type=EventType.FX_BUY,
        event_time=datetime.now(timezone.utc),
    )
    target_event = PortfolioEvent(
        user_id=user.id,
        event_type=EventType.WEALTH_BUY,
        event_time=datetime.now(timezone.utc),
    )
    session.add_all([source_event, target_event])
    session.flush()
    lot = FundingLot(
        user_id=user.id,
        currency="USD",
        source_event_id=source_event.id,
        source_type=FundingSourceType.FX_BUY,
        original_amount=Decimal("1000.000000"),
        remaining_amount=Decimal("500.000000"),
        original_rmb_basis=Decimal("7200.00"),
        remaining_rmb_basis=Decimal("3600.00"),
        status=LotStatus.AVAILABLE,
    )
    session.add(lot)
    session.flush()
    attribution = Attribution(
        target_event_id=target_event.id,
        source_lot_id=lot.id,
        native_amount=Decimal("500.000000"),
        rmb_basis=Decimal("3600.00"),
        allocation_policy=AllocationPolicy.FIFO,
    )
    session.add(attribution)
    session.commit()

    stored = session.query(Attribution).one()
    assert stored.target_event.event_type == EventType.WEALTH_BUY
    assert stored.source_lot.source_event.event_type == EventType.FX_BUY
    assert Decimal(stored.native_amount) == Decimal("500.000000")
    assert Decimal(stored.rmb_basis) == Decimal("3600.00")
