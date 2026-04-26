from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import AssetType, RateSourceType, RecordStatus, TransactionDirection
from investment_tracker.data.models import ExchangeRate, Position, Transaction, User


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

