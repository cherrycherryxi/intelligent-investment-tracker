from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import EventType, RateSourceType
from investment_tracker.data.models import ExchangeRate
from investment_tracker.data.services import AuditService, PortfolioEventService


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def _rate(session, currency: str, rate: str) -> None:
    session.add(
        ExchangeRate(
            base_currency=currency,
            quote_currency="CNY",
            rate=Decimal(rate),
            rate_timestamp=datetime(2026, 4, 29, tzinfo=timezone.utc),
            is_estimated=False,
            source=RateSourceType.MANUAL,
        )
    )
    session.commit()


def test_cash_breakdown_groups_entries_and_tracks_running_balance() -> None:
    session = _session()
    events = PortfolioEventService(session)
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 10000, "rmb_amount": 72000, "fx_rate_to_cny": 7.2},
            ],
        },
    )
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_SWAP.value,
            "event_time": datetime(2026, 2, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": -5000, "rmb_amount": 35000, "fx_rate_to_cny": 7.0},
            ],
        },
    )

    result = AuditService(session).get_cash_breakdown(user_id=1, currency="USD")

    assert result["total_balance"] == 5000.0
    assert result["subtotals"] == {"FX_BUY": 10000.0, "FX_SWAP": -5000.0}
    assert [entry["running_balance"] for entry in result["entries"]] == [10000.0, 5000.0]
    assert result["entries"][0]["event_type"] == "FX_BUY"


def test_cash_breakdown_excludes_cny_external_flows_from_balance() -> None:
    session = _session()
    events = PortfolioEventService(session)
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "CNY", "amount_delta": -72000, "rmb_amount": 72000, "fx_rate_to_cny": 1, "is_external_flow": True},
                {"currency": "CNY", "amount_delta": 1000, "rmb_amount": 1000, "fx_rate_to_cny": 1, "is_external_flow": False},
            ],
        },
    )

    result = AuditService(session).get_cash_breakdown(user_id=1, currency="CNY")

    assert result["total_balance"] == 1000.0
    assert result["subtotals"] == {"FX_BUY": 1000.0}
    assert [entry["included_in_balance"] for entry in result["entries"]] == [False, True]
    assert [entry["running_balance"] for entry in result["entries"]] == [0.0, 1000.0]


def test_asset_breakdown_uses_latest_snapshot_and_flags_estimated_values() -> None:
    session = _session()
    events = PortfolioEventService(session)
    event = events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FUND_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "asset_entries": [
                {
                    "asset": {"asset_type": "FUND", "asset_code": "USD-FUND", "asset_name": "USD Fund", "currency": "USD"},
                    "quantity_delta": 10,
                    "cash_currency": "USD",
                    "cash_amount": -500,
                }
            ],
        },
    )
    asset_id = event.asset_ledger_entries[0].asset_id
    events.create_valuation(
        user_id=1,
        payload={
            "asset_id": asset_id,
            "valuation_time": datetime(2026, 3, 1, tzinfo=timezone.utc).isoformat(),
            "quantity": 10,
            "price": 55,
            "market_value": 550,
            "currency": "USD",
            "source": "manual",
            "is_estimated": True,
        },
    )

    result = AuditService(session).get_asset_breakdown(user_id=1, currency="USD")

    assert result["total_market_value"] == 550.0
    assert result["entries"][0]["asset_code"] == "USD-FUND"
    assert result["entries"][0]["latest_valuation_price"] == 55.0
    assert result["entries"][0]["is_estimated"] is True
    assert result["entries"][0]["valuation_source"] == "manual"


def test_asset_breakdown_uses_quantity_for_amount_valued_asset_without_snapshot() -> None:
    session = _session()
    events = PortfolioEventService(session)
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.BOND_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "asset_entries": [
                {
                    "asset": {"asset_type": "BOND", "asset_code": "US-BOND-1", "asset_name": "USD Bond", "currency": "USD"},
                    "quantity_delta": 100,
                    "cash_currency": "USD",
                    "cash_amount": -10000,
                    "unit_price": 100,
                }
            ],
        },
    )

    result = AuditService(session).get_asset_breakdown(user_id=1, currency="USD")

    assert result["total_market_value"] == 100.0
    assert result["entries"][0]["market_value"] == 100.0
    assert result["entries"][0]["valuation_source"] == "quantity_based"


def test_historical_input_breakdown_filters_investment_pool_events_and_rmb_sources() -> None:
    session = _session()
    _rate(session, "USD", "7.000000")
    events = PortfolioEventService(session)
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 10000, "rmb_amount": 72000, "fx_rate_to_cny": 7.2},
            ],
        },
    )
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_SWAP.value,
            "event_time": datetime(2026, 2, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": -5000, "fx_rate_to_cny": 7.0},
            ],
        },
    )
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.INTEREST_INCOME.value,
            "event_time": datetime(2026, 3, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 10, "rmb_amount": 70, "fx_rate_to_cny": 7.0},
            ],
        },
    )

    result = AuditService(session).get_historical_input_breakdown(user_id=1, currency="USD")

    assert result["total_native_invested"] == 5000.0
    assert result["total_cny_invested"] == 37000.0
    assert [entry["event_type"] for entry in result["entries"]] == ["FX_BUY", "FX_SWAP"]
    assert [entry["rmb_source"] for entry in result["entries"]] == ["direct", "calculated"]
    assert [entry["rmb_amount"] for entry in result["entries"]] == [72000.0, -35000.0]


def test_generate_calculation_trail_includes_formulas_values_and_exchange_rate_notes() -> None:
    session = _session()
    trail = AuditService(session).generate_calculation_trail(
        currency="USD",
        exchange_rate=Decimal("7.000000"),
        currency_data={
            "cash_balance": 5000,
            "asset_market_value_native": 2000,
            "historical_net_invested_native": 6000,
            "historical_cny_invested": 42000,
        },
    )

    assert trail["native_assets"][0]["formula"] == "cash_balance + asset_market_value_native"
    assert trail["native_assets"][0]["result"] == 7000.0
    assert trail["value_cny"][0]["result"] == 49000.0
    assert trail["investment_pnl"][0]["result"] == 7000.0
    assert trail["fx_pnl"][0]["result"] == 0.0
    assert trail["value_cny"][0]["inputs"]["current_fx_rate_to_cny"] == 7.0
    assert "USD/CNY=7.000000" in trail["value_cny"][0]["notes"][0]


def test_generate_calculation_trail_includes_exchange_rate_source_timestamp_and_estimated_flag() -> None:
    session = _session()
    trail = AuditService(session).generate_calculation_trail(
        currency="USD",
        exchange_rate=Decimal("7.000000"),
        exchange_rate_details={
            "base_currency": "USD",
            "quote_currency": "CNY",
            "rate": 7.0,
            "rate_timestamp": "2026-04-29T00:00:00+00:00",
            "source": "MANUAL",
            "is_estimated": True,
        },
        currency_data={"cash_balance": 1000, "asset_market_value_native": 0},
    )

    note = trail["value_cny"][0]["notes"][0]
    assert "source=MANUAL" in note
    assert "timestamp=2026-04-29T00:00:00+00:00" in note
    assert "ESTIMATED" in note


def test_generate_calculation_trail_marks_rate_dependent_steps_incomplete_when_rate_missing() -> None:
    session = _session()
    trail = AuditService(session).generate_calculation_trail(
        currency="USD",
        exchange_rate=None,
        currency_data={"cash_balance": 5000, "asset_market_value_native": 2000},
    )

    assert trail["native_assets"][0]["result"] == 7000.0
    assert trail["value_cny"][0]["formula"] == "MISSING_RATE"
    assert trail["investment_pnl"][0]["result"] is None
    assert "Missing USD/CNY exchange rate" in trail["fx_pnl"][0]["notes"][0]


def test_detect_discrepancies_filters_values_within_threshold() -> None:
    session = _session()
    result = AuditService(session).detect_discrepancies(
        calculated={"cash_balance": 100.004},
        expected={"cash_balance": 100.0},
        threshold=Decimal("0.01"),
    )

    assert result == []


def test_detect_discrepancies_reports_difference_percentage_and_severity() -> None:
    session = _session()
    result = AuditService(session).detect_discrepancies(
        calculated={"cash_balance": 102, "asset_market_value_native": 1000.5},
        expected={"cash_balance": 100, "asset_market_value_native": 1000},
        threshold=Decimal("0.01"),
    )

    by_metric = {item["metric"]: item for item in result}
    assert by_metric["cash_balance"]["absolute_difference"] == 2.0
    assert by_metric["cash_balance"]["percentage_difference"] == 2.0
    assert by_metric["cash_balance"]["severity"] == "error"
    assert by_metric["asset_market_value_native"]["absolute_difference"] == 0.5
    assert by_metric["asset_market_value_native"]["percentage_difference"] == 0.05
    assert by_metric["asset_market_value_native"]["severity"] == "info"


def test_generate_correction_suggestions_for_cash_asset_and_historical_input() -> None:
    session = _session()
    events = PortfolioEventService(session)
    fx_event = events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 10000, "rmb_amount": 72000, "fx_rate_to_cny": 7.2},
            ],
        },
    )
    asset_event = events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FUND_BUY.value,
            "event_time": datetime(2026, 2, 1, tzinfo=timezone.utc).isoformat(),
            "asset_entries": [
                {
                    "asset": {"asset_type": "FUND", "asset_code": "USD-FUND", "asset_name": "USD Fund", "currency": "USD"},
                    "quantity_delta": 10,
                    "cash_currency": "USD",
                    "cash_amount": -500,
                }
            ],
        },
    )
    asset_id = asset_event.asset_ledger_entries[0].asset_id
    valuation = events.create_valuation(
        user_id=1,
        payload={
            "asset_id": asset_id,
            "valuation_time": datetime(2026, 3, 1, tzinfo=timezone.utc).isoformat(),
            "quantity": 10,
            "price": 55,
            "market_value": 550,
            "currency": "USD",
        },
    )

    suggestions = AuditService(session).generate_correction_suggestions(
        user_id=1,
        currency="USD",
        discrepancies=[
            {"metric": "cash_balance"},
            {"metric": "asset_market_value_native"},
            {"metric": "historical_cny_invested"},
        ],
    )

    by_metric = {item["discrepancy_metric"]: item for item in suggestions}
    assert by_metric["cash_balance"]["likelihood"] == "high"
    assert f"cash_ledger_entries:{fx_event.cash_ledger_entries[0].id}" in by_metric["cash_balance"]["affected_records"]
    assert by_metric["asset_market_value_native"]["likelihood"] == "high"
    assert f"asset_ledger_entries:{asset_event.asset_ledger_entries[0].id}" in by_metric["asset_market_value_native"]["affected_records"]
    assert f"valuation_snapshots:{valuation.id}" in by_metric["asset_market_value_native"]["affected_records"]
    assert by_metric["historical_cny_invested"]["likelihood"] == "medium"
    assert f"portfolio_events:{fx_event.id}" in by_metric["historical_cny_invested"]["affected_records"]


def test_generate_audit_for_single_currency_with_expected_values_and_data_quality() -> None:
    session = _session()
    _rate(session, "USD", "7.000000")
    events = PortfolioEventService(session)
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "CNY", "amount_delta": -72000, "rmb_amount": 72000, "fx_rate_to_cny": 1, "is_external_flow": True},
                {"currency": "USD", "amount_delta": 10000, "rmb_amount": 72000, "fx_rate_to_cny": 7.2},
            ],
        },
    )

    result = AuditService(session).generate_audit(
        user_id=1,
        currency="USD",
        expected_values={"expected_cash": 9000, "expected_value_cny": 63000},
    )

    assert result["currencies_audited"] == ["USD"]
    assert result["summary"]["total_discrepancies"] == 2
    assert result["summary"]["currencies_with_issues"] == ["USD"]
    currency_audit = result["by_currency"][0]
    assert currency_audit["status"] == "COMPLETE"
    assert currency_audit["cash_breakdown"]["total_balance"] == 10000.0
    assert currency_audit["calculation_trail"]["value_cny"][0]["result"] == 70000.0
    assert {item["metric"] for item in currency_audit["discrepancies"]} == {"cash_balance", "current_total_assets_cny"}


def test_generate_audit_without_currency_audits_all_performance_currencies() -> None:
    session = _session()
    _rate(session, "USD", "7.000000")
    _rate(session, "EUR", "8.000000")
    events = PortfolioEventService(session)
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 1000, "rmb_amount": 7200, "fx_rate_to_cny": 7.2},
            ],
        },
    )
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_SWAP.value,
            "event_time": datetime(2026, 2, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": -500, "rmb_amount": 3500, "fx_rate_to_cny": 7.0},
                {"currency": "EUR", "amount_delta": 437.5, "rmb_amount": 3500, "fx_rate_to_cny": 8.0},
            ],
        },
    )

    result = AuditService(session).generate_audit(user_id=1)

    assert result["currencies_audited"] == ["EUR", "USD"]
    assert [item["currency"] for item in result["by_currency"]] == ["EUR", "USD"]
    assert result["summary"]["total_discrepancies"] == 0


def test_generate_audit_reports_missing_rate_in_data_quality_and_currency_errors() -> None:
    session = _session()
    events = PortfolioEventService(session)
    events.create_event(
        user_id=1,
        payload={
            "event_type": EventType.FX_BUY.value,
            "event_time": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "cash_entries": [
                {"currency": "USD", "amount_delta": 1000, "rmb_amount": 7200, "fx_rate_to_cny": 7.2},
            ],
        },
    )

    result = AuditService(session).generate_audit(user_id=1, currency="USD")

    assert result["data_quality"]["missing_rates"] == ["USD"]
    assert result["by_currency"][0]["status"] == "INCOMPLETE"
    assert result["by_currency"][0]["errors"][0]["code"] == "MISSING_EXCHANGE_RATE"
    assert result["by_currency"][0]["calculation_trail"]["value_cny"][0]["formula"] == "MISSING_RATE"


def test_create_audit_log_and_get_audit_history() -> None:
    session = _session()
    audit = {
        "audit_id": "audit-1",
        "summary": {"total_discrepancies": 2, "currencies_with_issues": ["USD"], "data_quality_score": 90.0},
        "by_currency": [],
        "data_quality": {},
    }

    log = AuditService(session).create_audit_log(
        user_id=1,
        currencies_audited=["USD"],
        discrepancies_found=2,
        audit_details=audit,
    )
    history = AuditService(session).get_audit_history(user_id=1)

    assert log.entity_type == "performance_audit"
    assert log.entity_id == "audit-1"
    assert log.details_json["audit_report"]["audit_id"] == "audit-1"
    assert history == [
        {
            "id": log.id,
            "audit_id": "audit-1",
            "audit_time": log.created_at.isoformat(),
            "currencies_audited": ["USD"],
            "discrepancies_found": 2,
            "summary": audit["summary"],
        }
    ]
