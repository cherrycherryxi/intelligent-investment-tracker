from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import investment_tracker.api.routes.advice as advice_routes
import investment_tracker.api.routes.exchange_rates as exchange_rate_routes
import investment_tracker.api.routes.positions as positions_routes
import investment_tracker.api.routes.performance as performance_routes
import investment_tracker.api.routes.transactions as transaction_routes
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from investment_tracker.api.routes.advice import get_advice
from investment_tracker.api.routes.exchange_rates import latest_exchange_rates, refresh_exchange_rates
from investment_tracker.api.routes.positions import list_positions
from investment_tracker.api.routes.performance import get_cash_balances, get_performance
from investment_tracker.api.routes.transactions import create_transaction, list_transactions
from investment_tracker.api.schemas import ExchangeRateRefreshRequest, TransactionCreateRequest
from investment_tracker.data.base import Base
from investment_tracker.data.services import PortfolioEventService


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


def _patch_sessions(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    ctx = SessionContext(SessionLocal)
    monkeypatch.setattr(transaction_routes, "get_db_session", ctx)
    monkeypatch.setattr(positions_routes, "get_db_session", ctx)
    monkeypatch.setattr(performance_routes, "get_db_session", ctx)
    monkeypatch.setattr(advice_routes, "get_db_session", ctx)
    monkeypatch.setattr(exchange_rate_routes, "get_db_session", ctx)
    return SessionLocal


class StubAdvisorTool:
    def execute(self, payload):
        asset_code = payload["positions"][0]["asset_code"] if payload["positions"] else "UNKNOWN"
        return {
            "ok": True,
            "result": {
                "portfolio_summary": {"positions_count": len(payload["positions"])},
                "advice": {
                    "summary": "stub advice",
                    "risk_level": "medium",
                    "actions": [{"asset_code": asset_code, "action": "HOLD"}],
                    "reasoning": "stub reasoning",
                    "warnings": [],
                },
                "ai_provider": "stub",
                "model": "stub-model",
                "token_usage": {"input_tokens": 1, "output_tokens": 1},
            },
        }


def test_create_and_list_transactions(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sessions(monkeypatch)
    payload = TransactionCreateRequest(
        user_id=1,
        asset_type="FOREX",
        asset_code="USD",
        direction="BUY",
        quantity=1000,
        unit_price=7.2,
        trade_currency="CNY",
        trade_time=datetime(2025, 9, 18, 9, 54, 35),
        exchange_rate_to_cny=1.0,
        total_cost_cny=7200,
    )

    created = asyncio.run(create_transaction(payload))
    listed = asyncio.run(list_transactions(user_id=1))

    assert created["transaction"]["asset_code"] == "USD"
    assert len(listed["transactions"]) == 1


def test_transaction_history_includes_v2_events_and_filters_asset_text(monkeypatch: pytest.MonkeyPatch) -> None:
    SessionLocal = _patch_sessions(monkeypatch)
    buy_payload = TransactionCreateRequest(
        user_id=1,
        asset_type="FOREX",
        asset_code="USD",
        direction="BUY",
        quantity=200,
        unit_price=7.2,
        trade_currency="CNY",
        trade_time=datetime(2025, 9, 18, 9, 54, 35),
        exchange_rate_to_cny=1.0,
        total_cost_cny=1440,
    )
    sell_payload = TransactionCreateRequest(
        user_id=1,
        asset_type="FOREX",
        asset_code="USD",
        direction="SELL",
        quantity=50,
        unit_price=7.3,
        trade_currency="CNY",
        trade_time=datetime(2025, 9, 19, 9, 54, 35),
        exchange_rate_to_cny=1.0,
        total_cost_cny=365,
    )
    asyncio.run(create_transaction(buy_payload))
    asyncio.run(create_transaction(sell_payload))

    with SessionLocal() as session:
        PortfolioEventService(session).create_event(
            user_id=1,
            payload={
                "event_type": "FX_SWAP",
                "event_time": datetime(2025, 9, 20, 9, 54, 35),
                "source": "excel_import",
                "status": "CONFIRMED",
                "cash_entries": [
                    {"currency": "EUR", "amount_delta": -100, "is_external_flow": False},
                    {"currency": "AUD", "amount_delta": 162.75, "is_external_flow": False},
                ],
            },
        )
        PortfolioEventService(session).create_event(
            user_id=1,
            payload={
                "event_type": "FUND_BUY",
                "event_time": datetime(2025, 9, 21, 9, 54, 35),
                "source": "excel_import",
                "status": "CONFIRMED",
                "asset_entries": [
                    {
                        "asset": {
                            "asset_type": "FUND",
                            "asset_code": "USD-FUND-1",
                            "asset_name": "USD Fund",
                            "currency": "USD",
                        },
                        "quantity_delta": 10,
                        "cash_currency": "USD",
                        "cash_amount": 100,
                        "unit_price": 10,
                    }
                ],
            },
        )

    listed = asyncio.run(list_transactions(user_id=1, asset_code=" usd "))
    rows = listed["transactions"]

    assert {row["asset_type"] for row in rows} == {"FOREX", "FUND"}
    assert any(
        row["asset_code"] == "USD-FUND-1"
        and row["record_type"] == "EVENT"
        and row["trade_amount"] == 100.0
        and row["trade_amount_currency"] == "USD"
        for row in rows
    )
    assert any(row["direction"] == "SELL" and row["signed_total_cost_cny"] == -365.0 for row in rows)

    swaps = asyncio.run(list_transactions(user_id=1, direction="SWAP"))
    assert swaps["transactions"][0]["asset_code"] == "EUR->AUD"
    assert swaps["transactions"][0]["unit_price"] == 1.6275
    assert swaps["transactions"][0]["trade_amount"] == 100.0
    assert swaps["transactions"][0]["trade_amount_currency"] == "EUR"


def test_positions_and_advice(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sessions(monkeypatch)
    monkeypatch.setattr(advice_routes, "InvestmentAdvisorTool", StubAdvisorTool)
    payload = TransactionCreateRequest(
        user_id=1,
        asset_type="FOREX",
        asset_code="USD",
        direction="BUY",
        quantity=1000,
        unit_price=7.2,
        trade_currency="CNY",
        trade_time=datetime(2025, 9, 18, 9, 54, 35),
        exchange_rate_to_cny=1.0,
        total_cost_cny=7200,
    )
    asyncio.run(create_transaction(payload))

    positions = asyncio.run(list_positions(user_id=1))
    advice = asyncio.run(get_advice(user_id=1, risk_preference="balanced"))

    assert positions["positions"]
    assert advice["ok"] is True


def test_refresh_and_latest_exchange_rates(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sessions(monkeypatch)
    refreshed = asyncio.run(refresh_exchange_rates(ExchangeRateRefreshRequest(currencies=["USD", "JPY"])))
    latest = asyncio.run(latest_exchange_rates(currencies="USD,JPY"))

    assert refreshed["refreshed_count"] >= 1
    assert latest["rates"]


def test_performance_endpoint_reads_compat_transaction_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sessions(monkeypatch)
    asyncio.run(refresh_exchange_rates(ExchangeRateRefreshRequest(currencies=["USD"])))
    payload = TransactionCreateRequest(
        user_id=1,
        asset_type="FOREX",
        asset_code="USD",
        direction="BUY",
        quantity=1000,
        unit_price=7.2,
        trade_currency="CNY",
        trade_time=datetime(2025, 9, 18, 9, 54, 35),
        exchange_rate_to_cny=1.0,
        total_cost_cny=7200,
    )
    asyncio.run(create_transaction(payload))

    performance = asyncio.run(get_performance(user_id=1))
    cash = asyncio.run(get_cash_balances(user_id=1))

    assert performance["overview"]["net_invested_cny"] == 7200.0
    assert performance["by_currency"]
    assert any(row["currency"] == "USD" and row["cash_balance"] == 1000.0 for row in cash["cash_balances"])


def test_create_transaction_rejects_future_trade(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_sessions(monkeypatch)
    payload = TransactionCreateRequest(
        user_id=1,
        asset_type="FOREX",
        asset_code="USD",
        direction="BUY",
        quantity=1000,
        unit_price=7.2,
        trade_currency="CNY",
        trade_time=datetime.now() + timedelta(days=1),
        exchange_rate_to_cny=1.0,
        total_cost_cny=7200,
    )

    with pytest.raises(Exception):
        asyncio.run(create_transaction(payload))
