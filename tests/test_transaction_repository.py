from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.repositories import TransactionRepository


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_repository_bootstraps_user_and_creates_transactions() -> None:
    session = _session()
    repo = TransactionRepository(session)

    created = repo.create_transactions(
        user_id=1,
        transactions=[
            {
                "asset_type": "FOREX",
                "asset_code": "USD",
                "asset_name": "USD",
                "direction": "BUY",
                "quantity": 1000,
                "unit_price": 7.23,
                "trade_currency": "CNY",
                "trade_time": "2025-09-18T09:54:35",
                "exchange_rate_to_cny": 1.0,
                "total_cost_cny": 5784.0,
                "source": "excel_import",
                "status": "CONFIRMED",
                "raw_text": "sample",
                "notes": "sample",
            }
        ],
    )

    assert len(created) == 1
    assert created[0].id is not None
    assert created[0].user_id == 1
