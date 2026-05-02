"""Position-related API routes."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter

from investment_tracker.data.db import get_db_session
from investment_tracker.data.enums import AssetType
from investment_tracker.data.models import Asset, AssetLedgerEntry, CashLedgerEntry, ExchangeRate, PortfolioEvent, ValuationSnapshot
from investment_tracker.data.services import ExchangeRateService


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


def _build_cash_positions(session, *, user_id: int, cutoff: datetime) -> list[dict]:
    balances: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    rows = session.query(CashLedgerEntry).filter(CashLedgerEntry.user_id == user_id).all()
    for row in rows:
        currency = row.currency.upper()
        if currency == "CNY" and row.is_external_flow:
            continue
        balances[currency] += Decimal(str(row.amount_delta))

    positions = []
    for currency, balance in sorted(balances.items()):
        if balance == 0:
            continue
        rate = _latest_rate(session, currency, cutoff)
        value_cny = balance * rate if rate is not None else None
        positions.append(
            {
                "asset_code": currency,
                "asset_type": AssetType.CASH.value,
                "asset_name": f"{currency} Cash",
                "currency": currency,
                "quantity": _to_float(balance, "0.000001"),
                "average_cost_cny": None,
                "cost_basis_cny": None,
                "current_price": _to_float(rate, "0.000001") if rate is not None else None,
                "current_value_cny": _to_float(value_cny, "0.01"),
                "unrealized_pnl_cny": None,
                "return_pct": None,
                "valuation_status": "RATE_MISSING" if rate is None else "OK",
            }
        )
    return positions


def _build_asset_positions(session, *, user_id: int, cutoff: datetime) -> list[dict]:
    quantity_by_asset: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    native_cost_by_asset: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    cny_cost_by_asset: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    has_cny_cost: dict[int, bool] = defaultdict(bool)

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
        asset = assets_by_id.get(asset_id)
        if asset is not None and asset.asset_type in AMOUNT_VALUED_ASSET_TYPES and quantity_delta < 0:
            quantity_delta = max(quantity_delta, -quantity_by_asset[asset_id])
        quantity_by_asset[asset_id] += quantity_delta
        if row.cash_amount is None:
            continue
        cash_amount = abs(Decimal(str(row.cash_amount)))
        signed_amount = cash_amount if quantity_delta > 0 else -abs(quantity_delta)
        native_cost_by_asset[asset_id] += signed_amount
        if row.fx_rate_to_cny is not None:
            cny_cost_by_asset[asset_id] += signed_amount * Decimal(str(row.fx_rate_to_cny))
            has_cny_cost[asset_id] = True

    if not quantity_by_asset:
        return []

    assets = {asset_id: asset for asset_id, asset in assets_by_id.items() if asset_id in quantity_by_asset}
    valuations = _latest_valuations(session, user_id=user_id, cutoff=cutoff)

    positions = []
    for asset_id, quantity in sorted(quantity_by_asset.items(), key=lambda item: assets.get(item[0]).asset_code if assets.get(item[0]) else ""):
        if quantity == 0:
            continue
        asset = assets.get(asset_id)
        if asset is None:
            continue

        valuation = valuations.get(asset_id)
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

        cost_basis_cny = cny_cost_by_asset[asset_id] if has_cny_cost[asset_id] else None
        pnl = current_value_cny - cost_basis_cny if current_value_cny is not None and cost_basis_cny is not None else None
        return_pct = (pnl / cost_basis_cny * Decimal("100")) if pnl is not None and cost_basis_cny else None
        display_quantity = market_value if valuation is not None and asset.asset_type in AMOUNT_VALUED_ASSET_TYPES else quantity

        positions.append(
            {
                "asset_code": asset.asset_code,
                "asset_type": asset.asset_type.value,
                "asset_name": asset.asset_name,
                "currency": asset.currency,
                "quantity": _to_float(display_quantity, "0.000001"),
                "ledger_quantity": _to_float(quantity, "0.000001"),
                "average_cost_cny": _to_float(cost_basis_cny / quantity, "0.000001") if cost_basis_cny is not None and quantity else None,
                "cost_basis_cny": _to_float(cost_basis_cny, "0.01"),
                "native_cost": _to_float(native_cost_by_asset[asset_id], "0.000001"),
                "current_price": _to_float(current_price, "0.000001") if current_price is not None else None,
                "current_value_native": _to_float(market_value, "0.01") if market_value is not None else None,
                "current_value_cny": _to_float(current_value_cny, "0.01"),
                "unrealized_pnl_cny": _to_float(pnl, "0.01"),
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
        ExchangeRateService(session).refresh_rates(currencies=_currencies_for_user(session, user_id=user_id), create_backup=False)
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

    known_costs = [item["cost_basis_cny"] for item in positions if item["cost_basis_cny"] is not None]
    known_values = [item["current_value_cny"] for item in positions if item["current_value_cny"] is not None]
    known_pnls = [item["unrealized_pnl_cny"] for item in positions if item["unrealized_pnl_cny"] is not None]
    total_cost = round(sum(known_costs), 2) if known_costs else None
    total_pnl = round(sum(known_pnls), 2) if known_pnls else None
    totals = {
        "total_cost_cny": total_cost,
        "total_value_cny": round(sum(known_values), 2) if known_values else None,
        "total_pnl_cny": total_pnl,
        "missing_rates": [item["asset_code"] for item in positions if item["valuation_status"] == "RATE_MISSING"],
        "missing_valuations": [item["asset_code"] for item in positions if item["valuation_status"] == "VALUATION_MISSING"],
    }
    totals["total_return_pct"] = round((total_pnl / total_cost * 100) if total_cost and total_pnl is not None else 0.0, 4)

    return {"positions": positions, "totals": totals}
