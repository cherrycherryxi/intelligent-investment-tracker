from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import AssetType, FundingSourceType
from investment_tracker.data.models import Asset
from investment_tracker.data.services import AttributionStore, FundingLotManager


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _event(service, event_type: str, entries: list[dict]):
    return service.create_event(
        user_id=1,
        payload={
            "event_type": event_type,
            "event_time": datetime(2026, 5, 4, tzinfo=timezone.utc),
            "cash_entries": entries,
        },
    )


def test_record_allocation_is_queryable_by_event_and_asset() -> None:
    from investment_tracker.data.services import PortfolioEventService

    session = _session()
    service = PortfolioEventService(session)
    source_event = _event(
        service,
        "FX_BUY",
        [{"currency": "USD", "amount_delta": 1000, "rmb_amount": 7200, "fx_rate_to_cny": 7.2}],
    )
    target_event = service.create_event(
        user_id=1,
        payload={
            "event_type": "FUND_BUY",
            "event_time": datetime(2026, 5, 5, tzinfo=timezone.utc),
        },
    )
    asset = Asset(asset_type=AssetType.FUND, asset_code="USD-FUND", currency="USD")
    session.add(asset)
    session.flush()
    lot = source_event.source_funding_lots[0]

    attribution = AttributionStore(session).record_allocation(
        target_event_id=target_event.id,
        target_asset_id=asset.id,
        source_lot_id=lot.id,
        native_amount=Decimal("250.000000"),
        rmb_basis=Decimal("1800.00"),
    )
    session.commit()

    store = AttributionStore(session)
    assert store.get_attributions_for_event(event_id=target_event.id)[0].id == attribution.id
    assert store.get_attributions_for_asset(asset_id=asset.id)[0].id == attribution.id


def test_trace_to_origin_walks_fx_swap_consumption_chain() -> None:
    from investment_tracker.data.services import PortfolioEventService

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
    swap_event = service.create_event(
        user_id=1,
        payload={
            "event_type": "FX_SWAP",
            "event_time": datetime(2026, 5, 2, tzinfo=timezone.utc),
            "cash_entries": [
                {"currency": "USD", "amount_delta": -500},
                {"currency": "EUR", "amount_delta": 450},
            ],
        },
    )
    target_event = service.create_event(
        user_id=1,
        payload={
            "event_type": "FUND_BUY",
            "event_time": datetime(2026, 5, 3, tzinfo=timezone.utc),
        },
    )
    eur_lot = swap_event.source_funding_lots[0]
    attribution = AttributionStore(session).record_allocation(
        target_event_id=target_event.id,
        target_asset_id=None,
        source_lot_id=eur_lot.id,
        native_amount=Decimal("450.000000"),
        rmb_basis=Decimal("3600.00"),
    )
    session.commit()

    trace = AttributionStore(session).trace_to_origin(attribution_id=attribution.id)

    assert [node.source_currency for node in trace] == ["EUR", "USD"]
    assert [node.source_type for node in trace] == [FundingSourceType.FX_SWAP, FundingSourceType.FX_BUY]
    assert [node.depth for node in trace] == [0, 1]
    assert trace[1].rmb_basis == Decimal("3600.00")


def test_trace_to_origin_detects_cycles() -> None:
    session = _session()
    manager = FundingLotManager(session)
    first = manager.create_lot(
        user_id=1,
        currency="USD",
        native_amount=Decimal("100.000000"),
        rmb_basis=Decimal("720.00"),
        source_event_id=None,
        source_type=FundingSourceType.CARRYFORWARD,
    )
    attribution = AttributionStore(session).record_allocation(
        target_event_id=1,
        target_asset_id=None,
        source_lot_id=first.id,
        native_amount=Decimal("100.000000"),
        rmb_basis=Decimal("720.00"),
    )
    first.source_event_id = 999
    manager.consume_lot(lot_id=first.id, amount_consumed=Decimal("1.000000"), consuming_event_id=999)
    session.commit()

    with pytest.raises(ValueError, match="cycle detected"):
        AttributionStore(session).trace_to_origin(attribution_id=attribution.id)
