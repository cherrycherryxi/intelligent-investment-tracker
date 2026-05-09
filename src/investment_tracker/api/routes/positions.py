"""Position-related API routes."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, HTTPException

from investment_tracker.data.db import get_db_session
from investment_tracker.data.enums import AssetType
from investment_tracker.data.models import Asset, AssetLedgerEntry, Attribution, AttributionGap, CashLedgerEntry, ExchangeRate, FundingLot, PortfolioEvent, ValuationSnapshot
from investment_tracker.data.services import AttributionStatusTracker, AttributionStore


router = APIRouter(prefix="/api/positions", tags=["positions"])

AMOUNT_VALUED_ASSET_TYPES = {AssetType.BOND, AssetType.FUND, AssetType.WEALTH_PRODUCT}


def _to_float(value: Optional[Decimal], pattern: str = "0.01") -> Optional[float]:
    if value is None:
        return None
    return float(value.quantize(Decimal(pattern), rounding=ROUND_HALF_UP))


def _latest_rate(session, currency: str, cutoff: datetime) -> Optional[Decimal]:
    normalized = currency.upper()
    if normalized == "CNY":
        return Decimal("1")
    row = (
        session.query(ExchangeRate)
        .filter(
            ExchangeRate.base_currency == normalized,
            ExchangeRate.quote_currency == "CNY",
            ExchangeRate.rate_timestamp <= cutoff,
        )
        .order_by(ExchangeRate.rate_timestamp.desc(), ExchangeRate.id.desc())
        .first()
    )
    return Decimal(str(row.rate)) if row is not None else None


def _latest_valuations(session, *, user_id: int, cutoff: datetime) -> dict[int, ValuationSnapshot]:
    rows = (
        session.query(ValuationSnapshot)
        .filter(ValuationSnapshot.user_id == user_id, ValuationSnapshot.valuation_time <= cutoff)
        .order_by(ValuationSnapshot.valuation_time.desc(), ValuationSnapshot.id.desc())
        .all()
    )
    latest: dict[int, ValuationSnapshot] = {}
    for row in rows:
        if row.asset_id not in latest:
            latest[row.asset_id] = row
    return latest


def _attribution_summary(session, *, asset_id: int) -> dict:
    rows = (
        session.query(Attribution, FundingLot)
        .join(FundingLot, FundingLot.id == Attribution.source_lot_id)
        .filter(Attribution.target_asset_id == asset_id)
        .all()
    )
    lots = [lot for _, lot in rows]
    gap_count = session.query(AttributionGap).filter(AttributionGap.asset_id == asset_id, AttributionGap.resolved_at.is_(None)).count()
    dates = [lot.created_at for lot in lots if lot.created_at is not None]
    return {
        "total_lots_used": len({lot.id for lot in lots}),
        "oldest_lot_date": min(dates).isoformat() if dates else None,
        "newest_lot_date": max(dates).isoformat() if dates else None,
        "gap_count": gap_count,
    }


def _build_position_totals(positions: list[dict]) -> dict:
    known_costs = [Decimal(str(item["cost_basis_cny"])) for item in positions if item.get("cost_basis_cny") is not None]
    known_values = [Decimal(str(item["current_value_cny"])) for item in positions if item.get("current_value_cny") is not None]
    known_pnls = [Decimal(str(item["unrealized_pnl_cny"])) for item in positions if item.get("unrealized_pnl_cny") is not None]
    known_investment_pnls = [Decimal(str(item["investment_pnl_cny"])) for item in positions if item.get("investment_pnl_cny") is not None]
    known_fx_pnls = [Decimal(str(item["fx_pnl_cny"])) for item in positions if item.get("fx_pnl_cny") is not None]

    total_cost = sum(known_costs, Decimal("0")) if known_costs else None
    total_pnl = sum(known_pnls, Decimal("0")) if known_pnls else None

    return {
        "total_cost_cny": _to_float(total_cost, "0.01"),
        "total_value_cny": _to_float(sum(known_values, Decimal("0")), "0.01") if known_values else None,
        "total_pnl_cny": _to_float(total_pnl, "0.01"),
        "total_investment_pnl_cny": _to_float(sum(known_investment_pnls, Decimal("0")), "0.01") if known_investment_pnls else None,
        "total_fx_pnl_cny": _to_float(sum(known_fx_pnls, Decimal("0")), "0.01") if known_fx_pnls else None,
        "missing_rates": [item["asset_code"] for item in positions if item["valuation_status"] == "RATE_MISSING"],
        "missing_valuations": [item["asset_code"] for item in positions if item["valuation_status"] == "VALUATION_MISSING"],
        "total_return_pct": _to_float((total_pnl / total_cost * Decimal("100")) if total_cost and total_pnl is not None else Decimal("0"), "0.0001"),
    }


def _build_cash_positions(session, *, user_id: int, cutoff: datetime) -> list[dict]:
    balances: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    rows = (
        session.query(CashLedgerEntry)
        .join(PortfolioEvent, PortfolioEvent.id == CashLedgerEntry.event_id)
        .filter(CashLedgerEntry.user_id == user_id)
        .all()
    )
    for row in rows:
        currency = row.currency.upper()
        if currency == "CNY" and row.is_external_flow:
            continue
        balances[currency] += Decimal(str(row.amount_delta))

    remaining_native_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    remaining_basis_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    has_lots_by_currency: dict[str, bool] = defaultdict(bool)
    has_missing_basis_by_currency: dict[str, bool] = defaultdict(bool)
    lots = (
        session.query(FundingLot)
        .filter(
            FundingLot.user_id == user_id,
            FundingLot.remaining_amount > 0,
        )
        .all()
    )
    for lot in lots:
        currency = lot.currency.upper()
        has_lots_by_currency[currency] = True
        remaining_native_by_currency[currency] += Decimal(str(lot.remaining_amount))
        if lot.remaining_rmb_basis is None:
            has_missing_basis_by_currency[currency] = True
        else:
            remaining_basis_by_currency[currency] += Decimal(str(lot.remaining_rmb_basis))

    positions = []
    for currency, balance in sorted(balances.items()):
        if balance == 0:
            continue
        rate = _latest_rate(session, currency, cutoff)
        value_cny = balance * rate if rate is not None else None
        native_cost = remaining_native_by_currency[currency] if has_lots_by_currency[currency] and currency != "CNY" else None
        cost_basis_cny = (
            remaining_basis_by_currency[currency]
            if has_lots_by_currency[currency] and not has_missing_basis_by_currency[currency]
            else None
        )
        pnl = value_cny - cost_basis_cny if value_cny is not None and cost_basis_cny is not None else None
        return_pct = (pnl / cost_basis_cny * Decimal("100")) if pnl is not None and cost_basis_cny else None
        investment_pnl_cny = Decimal("0") if pnl is not None and currency != "CNY" else pnl
        fx_pnl_cny = pnl if pnl is not None and currency != "CNY" else Decimal("0") if pnl is not None else None
        positions.append(
            {
                "asset_code": currency,
                "asset_type": AssetType.CASH.value,
                "asset_name": f"{currency} Cash",
                "currency": currency,
                "quantity": _to_float(balance, "0.000001"),
                "average_cost_cny": None,
                "cost_basis_cny": _to_float(cost_basis_cny, "0.01"),
                "native_cost": _to_float(native_cost, "0.000001") if native_cost is not None else None,
                "current_price": _to_float(rate, "0.000001") if rate is not None else None,
                "current_value_cny": _to_float(value_cny, "0.01"),
                "unrealized_pnl_cny": _to_float(pnl, "0.01"),
                "investment_pnl_cny": _to_float(investment_pnl_cny, "0.01") if investment_pnl_cny is not None else None,
                "fx_pnl_cny": _to_float(fx_pnl_cny, "0.01") if fx_pnl_cny is not None else None,
                "return_pct": _to_float(return_pct, "0.0001") if return_pct is not None else None,
                "valuation_status": "RATE_MISSING" if rate is None else "OK",
            }
        )
    return positions


def _build_asset_positions(session, *, user_id: int, cutoff: datetime) -> list[dict]:
    quantity_by_asset: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    native_cost_by_asset: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    cny_cost_by_asset: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    has_cny_cost: dict[int, bool] = defaultdict(bool)
    attributed_cost_by_asset: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    attributed_native_by_asset: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    has_attributed_cost: dict[int, bool] = defaultdict(bool)
    raw_quantity_by_asset: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))

    assets_by_id = {asset.id: asset for asset in session.query(Asset).all()}
    rows = (
        session.query(AssetLedgerEntry)
        .join(PortfolioEvent, PortfolioEvent.id == AssetLedgerEntry.event_id)
        .filter(AssetLedgerEntry.user_id == user_id)
        .order_by(AssetLedgerEntry.asset_id, PortfolioEvent.event_time.asc(), AssetLedgerEntry.id.asc())
        .all()
    )
    for row in rows:
        asset_id = row.asset_id
        quantity_delta = Decimal(str(row.quantity_delta))
        raw_quantity_by_asset[asset_id] += quantity_delta
        asset = assets_by_id.get(asset_id)
        if asset is not None and asset.asset_type in AMOUNT_VALUED_ASSET_TYPES and quantity_delta < 0:
            quantity_delta = max(quantity_delta, -quantity_by_asset[asset_id])
        quantity_by_asset[asset_id] += quantity_delta
        if row.cash_amount is None:
            continue
        cash_amount = abs(Decimal(str(row.cash_amount)))
        signed_amount = cash_amount if quantity_delta > 0 else -cash_amount
        native_cost_by_asset[asset_id] += signed_amount
        if row.fx_rate_to_cny is not None:
            cny_cost_by_asset[asset_id] += signed_amount * Decimal(str(row.fx_rate_to_cny))
            has_cny_cost[asset_id] = True

    attribution_rows = (
        session.query(Attribution)
        .join(PortfolioEvent, PortfolioEvent.id == Attribution.target_event_id)
        .filter(PortfolioEvent.user_id == user_id)
        .all()
    )
    for row in attribution_rows:
        if row.target_asset_id is None:
            continue
        attributed_cost_by_asset[row.target_asset_id] += Decimal(str(row.rmb_basis))
        attributed_native_by_asset[row.target_asset_id] += Decimal(str(row.native_amount))
        has_attributed_cost[row.target_asset_id] = True

    valuations = _latest_valuations(session, user_id=user_id, cutoff=cutoff)
    valuation_asset_ids = {
        asset_id
        for asset_id, valuation in valuations.items()
        if Decimal(str(valuation.quantity)) > 0 or Decimal(str(valuation.market_value)) > 0
    }
    candidate_asset_ids = set(quantity_by_asset) | valuation_asset_ids
    if not candidate_asset_ids:
        return []
    assets = {asset_id: asset for asset_id, asset in assets_by_id.items() if asset_id in candidate_asset_ids}

    positions = []
    for asset_id in sorted(candidate_asset_ids, key=lambda item: assets.get(item).asset_code if assets.get(item) else ""):
        quantity = quantity_by_asset[asset_id]
        asset = assets.get(asset_id)
        if asset is None:
            continue

        valuation = valuations.get(asset_id)
        has_positive_snapshot = (
            asset.asset_type in AMOUNT_VALUED_ASSET_TYPES
            and valuation is not None
            and (Decimal(str(valuation.quantity)) > 0 or Decimal(str(valuation.market_value)) > 0)
            and raw_quantity_by_asset[asset_id] < 0
        )
        if quantity == 0 and not has_positive_snapshot:
            continue

        rate = None
        market_value = None
        current_value_cny = None
        current_price = None
        status = "OK"
        if valuation is None:
            if asset.asset_type in AMOUNT_VALUED_ASSET_TYPES:
                market_value = quantity
                current_price = Decimal("1")
                rate = _latest_rate(session, asset.currency, cutoff)
                if rate is None:
                    status = "RATE_MISSING"
                else:
                    current_value_cny = market_value * rate
            else:
                status = "VALUATION_MISSING"
        else:
            market_value = Decimal(str(valuation.market_value))
            current_price = Decimal(str(valuation.price)) if valuation.price is not None else (market_value / quantity if quantity else None)
            rate = Decimal(str(valuation.fx_rate_to_cny)) if valuation.fx_rate_to_cny is not None else _latest_rate(session, valuation.currency, cutoff)
            if rate is None:
                status = "RATE_MISSING"
            elif valuation.is_estimated:
                status = "ESTIMATED"
                current_value_cny = market_value * rate
            else:
                current_value_cny = market_value * rate

        cost_basis_cny = (
            attributed_cost_by_asset[asset_id]
            if has_attributed_cost[asset_id]
            else cny_cost_by_asset[asset_id]
            if has_cny_cost[asset_id]
            else None
        )
        native_cost = attributed_native_by_asset[asset_id] if has_attributed_cost[asset_id] else native_cost_by_asset[asset_id]
        attributed_cost_basis_cny = attributed_cost_by_asset[asset_id] if has_attributed_cost[asset_id] else None
        attribution_status = AttributionStatusTracker(session).compute_status(asset_id=asset_id, user_id=user_id)
        investment_pnl_cny = None
        fx_pnl_cny = None
        if (
            asset.asset_type in AMOUNT_VALUED_ASSET_TYPES
            and asset.currency.upper() != "CNY"
            and market_value is not None
            and rate is not None
            and native_cost
        ):
            native_pnl = market_value - native_cost
            investment_pnl_cny = native_pnl * rate
            pnl = current_value_cny - cost_basis_cny if current_value_cny is not None and cost_basis_cny is not None else investment_pnl_cny
            fx_pnl_cny = pnl - investment_pnl_cny if pnl is not None else None
            return_pct = native_pnl / native_cost * Decimal("100")
        else:
            pnl = current_value_cny - cost_basis_cny if current_value_cny is not None and cost_basis_cny is not None else None
            investment_pnl_cny = pnl
            fx_pnl_cny = Decimal("0") if pnl is not None else None
            return_pct = (pnl / cost_basis_cny * Decimal("100")) if pnl is not None and cost_basis_cny else None
        display_quantity = Decimal(str(valuation.quantity)) if valuation is not None else quantity

        positions.append(
            {
                "asset_id": asset.id,
                "asset_code": asset.asset_code,
                "asset_type": asset.asset_type.value,
                "asset_name": asset.asset_name,
                "currency": asset.currency,
                "quantity": _to_float(display_quantity, "0.000001"),
                "ledger_quantity": _to_float(quantity, "0.000001"),
                "average_cost_cny": _to_float(cost_basis_cny / quantity, "0.000001") if cost_basis_cny is not None and quantity else None,
                "cost_basis_cny": _to_float(cost_basis_cny, "0.01"),
                "legacy_cost_basis_cny": _to_float(cny_cost_by_asset[asset_id], "0.01") if has_cny_cost[asset_id] else None,
                "attributed_cost_basis_cny": _to_float(attributed_cost_basis_cny, "0.01"),
                "attribution_status": attribution_status.value,
                "attribution_summary": _attribution_summary(session, asset_id=asset_id),
                "native_cost": _to_float(native_cost, "0.000001"),
                "current_price": _to_float(current_price, "0.000001") if current_price is not None else None,
                "current_value_native": _to_float(market_value, "0.01") if market_value is not None else None,
                "current_value_cny": _to_float(current_value_cny, "0.01"),
                "unrealized_pnl_cny": _to_float(pnl, "0.01"),
                "investment_pnl_cny": _to_float(investment_pnl_cny, "0.01") if investment_pnl_cny is not None else None,
                "fx_pnl_cny": _to_float(fx_pnl_cny, "0.01") if fx_pnl_cny is not None else None,
                "return_pct": _to_float(return_pct, "0.0001") if return_pct is not None else None,
                "valuation_status": status,
            }
        )
    return positions


def _currencies_for_user(session, *, user_id: int) -> set[str]:
    cash_currencies = {
        row[0].upper()
        for row in session.query(CashLedgerEntry.currency).filter(CashLedgerEntry.user_id == user_id).distinct().all()
        if row[0]
    }
    asset_ids = [row[0] for row in session.query(AssetLedgerEntry.asset_id).filter(AssetLedgerEntry.user_id == user_id).distinct().all()]
    asset_currencies = set()
    if asset_ids:
        asset_currencies = {
            row[0].upper()
            for row in session.query(Asset.currency).filter(Asset.id.in_(asset_ids)).distinct().all()
            if row[0]
        }
    return {currency for currency in cash_currencies | asset_currencies if currency != "CNY"}


@router.get("")
async def list_positions(
    user_id: int = 1,
    asset_type: Optional[AssetType] = None,
    sort_by: str = "asset_code",
) -> dict:
    with get_db_session() as session:
        cutoff = datetime.now(timezone.utc)
        positions = [
            *_build_cash_positions(session, user_id=user_id, cutoff=cutoff),
            *_build_asset_positions(session, user_id=user_id, cutoff=cutoff),
        ]

    if asset_type is not None:
        positions = [item for item in positions if item["asset_type"] == asset_type.value]

    if sort_by == "pnl":
        positions.sort(key=lambda item: item["unrealized_pnl_cny"] if item["unrealized_pnl_cny"] is not None else float("-inf"), reverse=True)
    elif sort_by == "return_pct":
        positions.sort(key=lambda item: item["return_pct"] if item["return_pct"] is not None else float("-inf"), reverse=True)
    else:
        positions.sort(key=lambda item: item["asset_code"])

    totals = _build_position_totals(positions)

    return {"positions": positions, "totals": totals}


@router.get("/{asset_id}/attribution")
async def get_position_attribution(asset_id: int, user_id: int = 1) -> dict:
    with get_db_session() as session:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="asset not found")

        tracker = AttributionStatusTracker(session)
        store = AttributionStore(session)
        attributions = store.get_attributions_for_asset(asset_id=asset_id)
        grouped: dict[int, dict] = {}
        for attribution in attributions:
            event = attribution.target_event
            if event is None or event.user_id != user_id:
                continue
            group = grouped.setdefault(
                event.id,
                {
                    "purchase_event_id": event.id,
                    "purchase_date": event.event_time.isoformat(),
                    "purchase_amount": 0.0,
                    "funding_sources": [],
                },
            )
            group["purchase_amount"] += float(attribution.native_amount)
            lot = attribution.source_lot
            source_event = lot.source_event if lot is not None else None
            effective_rate = (
                Decimal(str(attribution.rmb_basis)) / Decimal(str(attribution.native_amount))
                if Decimal(str(attribution.native_amount))
                else None
            )
            try:
                lineage_depth = max(node.depth for node in store.trace_to_origin(attribution_id=attribution.id))
            except ValueError:
                lineage_depth = 0
            group["funding_sources"].append(
                {
                    "attribution_id": attribution.id,
                    "lot_id": attribution.source_lot_id,
                    "source_event_id": lot.source_event_id if lot is not None else None,
                    "source_type": lot.source_type.value if lot is not None else None,
                    "source_date": source_event.event_time.isoformat() if source_event is not None else None,
                    "source_currency": lot.currency if lot is not None else None,
                    "native_amount_allocated": float(attribution.native_amount),
                    "rmb_basis_allocated": float(attribution.rmb_basis),
                    "effective_rate": _to_float(effective_rate, "0.000001") if effective_rate is not None else None,
                    "remaining_amount_on_source_lot": float(lot.remaining_amount) if lot is not None else None,
                    "lineage_depth": lineage_depth,
                }
            )

        gaps = [
            {
                "id": gap.id,
                "event_id": gap.event_id,
                "gap_type": gap.gap_type.value,
                "currency": gap.currency,
                "shortfall_amount": float(gap.shortfall_amount) if gap.shortfall_amount is not None else None,
                "status": gap.status.value,
                "detected_at": gap.detected_at.isoformat(),
                "suggestions": tracker.suggest_corrections(gap=gap),
            }
            for gap in tracker.get_gaps(asset_id=asset_id)
        ]
        total_attributed_cost = sum((Decimal(str(item.rmb_basis)) for item in attributions), Decimal("0.00"))
        return {
            "asset_id": asset.id,
            "asset_code": asset.asset_code,
            "asset_name": asset.asset_name,
            "currency": asset.currency,
            "attribution_status": tracker.compute_status(asset_id=asset.id, user_id=user_id).value,
            "total_attributed_cost_cny": _to_float(total_attributed_cost, "0.01") if attributions else None,
            "attributions": list(grouped.values()),
            "gaps": gaps,
        }
