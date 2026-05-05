from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.api.routes.positions import _build_asset_positions
from investment_tracker.data.base import Base
from investment_tracker.data.enums import RateSourceType
from investment_tracker.data.models import Attribution, ExchangeRate
from investment_tracker.data.services import PortfolioEventService


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_foreign_asset_purchase_records_attributed_cost_from_funding_lot_not_spot_rate() -> None:
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
    session.commit()

    attribution = session.query(Attribution).filter(Attribution.target_event_id == event.id).one()

    assert Decimal(attribution.native_amount) == Decimal("100.000000")
    assert Decimal(attribution.rmb_basis) == Decimal("720.00")
    assert Decimal(attribution.rmb_basis) != Decimal("710.00")


def test_positions_use_attributed_cost_when_available() -> None:
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
    asset_id = session.query(Attribution.target_asset_id).filter(Attribution.target_event_id == event.id).scalar()
    service.create_valuation(
        user_id=1,
        payload={
            "asset_id": asset_id,
            "valuation_time": datetime(2026, 5, 4, tzinfo=timezone.utc),
            "quantity": 100,
            "price": 1,
            "market_value": 100,
            "currency": "USD",
            "source": "manual",
        },
    )
    session.add(
        ExchangeRate(
            base_currency="USD",
            quote_currency="CNY",
            rate=Decimal("7.30"),
            rate_timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
            is_estimated=False,
            source=RateSourceType.MANUAL,
        )
    )
    session.commit()

    positions = _build_asset_positions(
        session,
        user_id=1,
        cutoff=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )

    fund = next(item for item in positions if item["asset_code"] == "USD-FUND")
    assert fund["cost_basis_cny"] == 720.0
    assert fund["unrealized_pnl_cny"] == 10.0
    assert fund["fx_pnl_cny"] == 10.0


def test_multiple_foreign_asset_purchases_accumulate_attributed_cost() -> None:
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
    asset_payload = {"asset_type": "FUND", "asset_code": "USD-FUND", "currency": "USD"}
    for day, amount, spot in [(2, 100, 7.1), (3, 50, 7.4)]:
        service.create_event(
            user_id=1,
            payload={
                "event_type": "FUND_BUY",
                "event_time": datetime(2026, 5, day, tzinfo=timezone.utc),
                "asset_entries": [
                    {
                        "asset": asset_payload,
                        "quantity_delta": amount,
                        "cash_currency": "USD",
                        "cash_amount": amount,
                        "unit_price": 1,
                        "fx_rate_to_cny": spot,
                    }
                ],
            },
        )
    session.commit()

    total_attributed_cost = sum(
        (Decimal(row.rmb_basis) for row in session.query(Attribution).all()),
        Decimal("0.00"),
    )

    assert total_attributed_cost == Decimal("1080.00")
