from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import investment_tracker.api.routes.positions as positions_routes
from investment_tracker.api.routes.positions import get_position_attribution, list_positions
from investment_tracker.data.base import Base
from investment_tracker.data.enums import AttributionStatus, RateSourceType
from investment_tracker.data.models import Asset, Attribution, ExchangeRate
from investment_tracker.data.services import AuditService, PerformanceCalculator, PortfolioEventService


class SessionContext:
    def __init__(self, SessionLocal):
        self.SessionLocal = SessionLocal

    def __call__(self):
        outer = self

        class _Ctx:
            def __enter__(self):
                self.session = outer.SessionLocal()
                return self.session

            def __exit__(self, exc_type, exc, tb):
                self.session.close()

        return _Ctx()


def _session_local():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed_attributed_fund(session):
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
            "quantity": 120,
            "price": 1,
            "market_value": 120,
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
    return asset_id


def test_product_performance_uses_attributed_cost_and_closes_pnl_decomposition() -> None:
    SessionLocal = _session_local()
    with SessionLocal() as session:
        asset_id = _seed_attributed_fund(session)
        performance = PerformanceCalculator(session).compute_product_performance(
            asset_id=asset_id,
            user_id=1,
            current_native_value=Decimal("120"),
            current_fx_rate=Decimal("7.30"),
        )

    assert performance["attributed_cost_basis_cny"] == 720.0
    assert performance["total_pnl_cny"] == 156.0
    assert performance["investment_pnl_cny"] == 146.0
    assert performance["fx_pnl_cny"] == 10.0
    assert performance["investment_pnl_cny"] + performance["fx_pnl_cny"] == performance["total_pnl_cny"]
    assert performance["return_pct"] == 20.0


def test_product_performance_flags_incomplete_attribution_but_keeps_native_pnl() -> None:
    SessionLocal = _session_local()
    with SessionLocal() as session:
        asset = Asset(asset_type="FUND", asset_code="MISSING-FUND", currency="USD")
        session.add(asset)
        session.flush()
        PortfolioEventService(session).create_event(
            user_id=1,
            payload={
                "event_type": "FUND_BUY",
                "event_time": datetime(2026, 5, 2, tzinfo=timezone.utc),
                "asset_entries": [
                    {
                        "asset_id": asset.id,
                        "quantity_delta": 100,
                        "cash_currency": "USD",
                        "cash_amount": 100,
                        "unit_price": 1,
                        "fx_rate_to_cny": 7.1,
                    }
                ],
            },
        )
        performance = PerformanceCalculator(session).compute_product_performance(
            asset_id=asset.id,
            user_id=1,
            current_native_value=Decimal("120"),
            current_fx_rate=Decimal("7.30"),
        )

    assert performance["attribution_status"] == AttributionStatus.INCOMPLETE.value
    assert performance["attributed_cost_basis_cny"] is None
    assert performance["total_pnl_cny"] is None
    assert performance["fx_pnl_cny"] is None
    assert performance["investment_pnl_cny"] == 146.0


def test_positions_response_exposes_attribution_fields_and_detail_endpoint(monkeypatch) -> None:
    SessionLocal = _session_local()
    monkeypatch.setattr(positions_routes, "get_db_session", SessionContext(SessionLocal))
    with SessionLocal() as session:
        asset_id = _seed_attributed_fund(session)

    positions = asyncio.run(list_positions(user_id=1))
    fund = next(item for item in positions["positions"] if item.get("asset_id") == asset_id)
    detail = asyncio.run(get_position_attribution(asset_id=asset_id, user_id=1))

    assert fund["cost_basis_cny"] == 720.0
    assert fund["legacy_cost_basis_cny"] == 710.0
    assert fund["attributed_cost_basis_cny"] == 720.0
    assert fund["attribution_status"] == "COMPLETE"
    assert fund["attribution_summary"]["total_lots_used"] == 1
    assert detail["asset_code"] == "USD-FUND"
    assert detail["total_attributed_cost_cny"] == 720.0
    assert detail["attributions"][0]["funding_sources"][0]["source_type"] == "FX_BUY"


def test_positions_totals_sum_attribution_aware_rows(monkeypatch) -> None:
    SessionLocal = _session_local()
    monkeypatch.setattr(positions_routes, "get_db_session", SessionContext(SessionLocal))
    with SessionLocal() as session:
        _seed_attributed_fund(session)

    response = asyncio.run(list_positions(user_id=1, asset_type=positions_routes.AssetType.FUND))
    fund = response["positions"][0]

    assert fund["legacy_cost_basis_cny"] == 710.0
    assert fund["attributed_cost_basis_cny"] == 720.0
    assert fund["unrealized_pnl_cny"] == 156.0
    assert response["totals"]["total_cost_cny"] == 720.0
    assert response["totals"]["total_pnl_cny"] == 156.0
    assert response["totals"]["total_investment_pnl_cny"] == 146.0
    assert response["totals"]["total_fx_pnl_cny"] == 10.0


def test_audit_includes_attribution_diagnostics() -> None:
    SessionLocal = _session_local()
    with SessionLocal() as session:
        _seed_attributed_fund(session)
        audit = AuditService(session).generate_audit(user_id=1)

    diagnostics = audit["attribution_diagnostics"]
    assert diagnostics["total_products"] == 1
    assert diagnostics["complete_attribution"] == 1
    assert diagnostics["total_gaps"] == 0
