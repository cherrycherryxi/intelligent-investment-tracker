"""Domain services for portfolio and exchange-rate workflows."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from investment_tracker.data.enums import AssetType, EventType, RateSourceType, RecordStatus
from investment_tracker.data.models import (
    AuditLog,
    Asset,
    AssetLedgerEntry,
    CashLedgerEntry,
    ExchangeRate,
    PortfolioEvent,
    Position,
    Transaction,
    ValuationSnapshot,
)
from investment_tracker.mcp_tools.exchange_rate_tool import ExchangeRateTool
from investment_tracker.mcp_tools.position_calculator_tool import PositionCalculatorTool
from investment_tracker.utils.backup import BackupService
from sqlalchemy import case
from sqlalchemy.orm import Session


class PortfolioService:
    """Aggregate transactions into position views and optional persisted snapshots."""

    def __init__(
        self,
        session: Session,
        *,
        exchange_rate_tool: Optional[ExchangeRateTool] = None,
        position_calculator: Optional[PositionCalculatorTool] = None,
    ) -> None:
        self.session = session
        self.exchange_rate_tool = exchange_rate_tool or ExchangeRateTool()
        self.position_calculator = position_calculator or PositionCalculatorTool()

    def build_positions(self, *, user_id: int) -> List[Dict[str, Any]]:
        transactions = (
            self.session.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.trade_time.asc(), Transaction.id.asc())
            .all()
        )
        grouped: Dict[Tuple[str, str], List[Transaction]] = defaultdict(list)
        for transaction in transactions:
            grouped[(transaction.asset_type.value, transaction.asset_code)].append(transaction)

        positions: List[Dict[str, Any]] = []
        for (asset_type, asset_code), items in grouped.items():
            current_price = self._current_price_for_asset(asset_type=asset_type, asset_code=asset_code)
            payload = {
                "transactions": [
                    {
                        "asset_type": item.asset_type.value,
                        "asset_code": item.asset_code,
                        "direction": item.direction.value,
                        "quantity": str(item.quantity),
                        "unit_price": str(item.unit_price),
                        "trade_currency": item.trade_currency,
                        "exchange_rate_to_cny": str(item.exchange_rate_to_cny) if item.exchange_rate_to_cny is not None else None,
                    }
                    for item in items
                ],
                "current_price": str(current_price),
            }
            response = self.position_calculator.execute(payload)
            if response["ok"]:
                position = response["result"]
                position["asset_name"] = items[-1].asset_name or asset_code
                positions.append(position)
        return positions

    def sync_positions(self, *, user_id: int) -> List[Position]:
        computed = self.build_positions(user_id=user_id)
        self.session.query(Position).filter(Position.user_id == user_id).delete()
        created: List[Position] = []
        for item in computed:
            position = Position(
                user_id=user_id,
                asset_type=item["asset_type"],
                asset_code=item["asset_code"],
                asset_name=item.get("asset_name"),
                quantity=Decimal(str(item["quantity"])),
                average_cost_cny=Decimal(str(item["average_cost_cny"])),
                cost_basis_cny=Decimal(str(item["cost_basis_cny"])),
                current_price=Decimal(str(self._current_price_for_asset(asset_type=item["asset_type"], asset_code=item["asset_code"]))),
                current_value_cny=Decimal(str(item["current_value_cny"])),
                unrealized_pnl_cny=Decimal(str(item["unrealized_pnl_cny"])),
                return_pct=Decimal(str(item["return_pct"])),
                last_valued_at=datetime.now(timezone.utc),
            )
            self.session.add(position)
            created.append(position)
        self.session.commit()
        BackupService(self.session).create_backup(reason="positions_synced")
        for position in created:
            self.session.refresh(position)
        return created

    def _current_price_for_asset(self, *, asset_type: str, asset_code: str) -> Decimal:
        if asset_type == AssetType.FOREX.value:
            response = self.exchange_rate_tool.execute({"base_currency": asset_code, "quote_currency": "CNY"})
            if response["ok"]:
                return Decimal(str(response["result"]["rate"]))
        return Decimal("100")


class ExchangeRateService:
    """Fetch and persist exchange-rate snapshots."""

    def __init__(self, session: Session, *, exchange_rate_tool: Optional[ExchangeRateTool] = None) -> None:
        self.session = session
        self.exchange_rate_tool = exchange_rate_tool or ExchangeRateTool()

    def refresh_rates(self, *, currencies: Iterable[str], create_backup: bool = True) -> List[ExchangeRate]:
        created: List[ExchangeRate] = []
        for currency in sorted({currency.upper() for currency in currencies if currency and currency.upper() != "CNY"}):
            response = self.exchange_rate_tool.execute({"base_currency": currency, "quote_currency": "CNY"})
            if not response["ok"]:
                continue
            result = response["result"]
            rate = ExchangeRate(
                base_currency=currency,
                quote_currency="CNY",
                rate=Decimal(str(result["rate"])),
                rate_timestamp=datetime.fromisoformat(result["rate_timestamp"]),
                is_estimated=bool(result["is_estimated"]),
                source=RateSourceType[result["source"]],
            )
            self.session.add(rate)
            created.append(rate)
        self.session.commit()
        if create_backup and created:
            BackupService(self.session).create_backup(reason="exchange_rates_refreshed")
        for item in created:
            self.session.refresh(item)
        return created

    def latest_rates(self, *, currencies: Optional[Iterable[str]] = None) -> List[ExchangeRate]:
        source_priority = case(
            (ExchangeRate.source == RateSourceType.MANUAL, 0),
            (ExchangeRate.source == RateSourceType.PRIMARY, 1),
            else_=2,
        )
        query = self.session.query(ExchangeRate).order_by(
            ExchangeRate.rate_timestamp.desc(),
            ExchangeRate.is_estimated.asc(),
            source_priority.asc(),
            ExchangeRate.id.desc(),
        )
        rows = query.all()
        latest: Dict[str, ExchangeRate] = {}
        allowed = {currency.upper() for currency in currencies} if currencies else None
        for row in rows:
            if allowed and row.base_currency not in allowed:
                continue
            if row.base_currency not in latest:
                latest[row.base_currency] = row
        return list(latest.values())


class PortfolioEventService:
    """Persist v0.2 portfolio events, cash ledger entries, asset ledger entries, and valuations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_asset(self, payload: Dict[str, Any]) -> Asset:
        asset_id = payload.get("id") or payload.get("asset_id")
        if asset_id:
            asset = self.session.get(Asset, int(asset_id))
            if asset is None:
                raise ValueError(f"asset {asset_id} not found")
            return asset

        asset_type = self._asset_type(payload["asset_type"])
        asset_code = str(payload["asset_code"]).upper()
        currency = str(payload["currency"]).upper()
        asset = (
            self.session.query(Asset)
            .filter(Asset.asset_type == asset_type, Asset.asset_code == asset_code, Asset.currency == currency)
            .one_or_none()
        )
        if asset is not None:
            return asset

        asset = Asset(
            asset_type=asset_type,
            asset_code=asset_code,
            asset_name=payload.get("asset_name"),
            currency=currency,
            issuer=payload.get("issuer"),
            metadata_json=payload.get("metadata_json"),
        )
        self.session.add(asset)
        self.session.flush()
        return asset

    def create_event(self, *, user_id: int, payload: Dict[str, Any], commit: bool = True) -> PortfolioEvent:
        event = PortfolioEvent(
            user_id=user_id,
            event_type=self._event_type(payload["event_type"]),
            event_time=self._parse_datetime(payload["event_time"]),
            source=payload.get("source", "manual"),
            status=self._status(payload.get("status", "CONFIRMED")),
            raw_text=payload.get("raw_text"),
            notes=payload.get("notes"),
        )
        self.session.add(event)
        self.session.flush()

        for item in payload.get("cash_entries", []):
            self.session.add(
                CashLedgerEntry(
                    event_id=event.id,
                    user_id=user_id,
                    currency=str(item["currency"]).upper(),
                    amount_delta=Decimal(str(item["amount_delta"])),
                    rmb_amount=self._optional_decimal(item.get("rmb_amount")),
                    fx_rate_to_cny=self._optional_decimal(item.get("fx_rate_to_cny")),
                    is_external_flow=bool(item.get("is_external_flow", False)),
                    description=item.get("description"),
                )
            )

        for item in payload.get("asset_entries", []):
            asset = self.session.get(Asset, int(item["asset_id"])) if item.get("asset_id") else None
            if asset is None and item.get("asset"):
                asset = self.ensure_asset(item["asset"])
            if asset is None:
                raise ValueError("asset_entries require asset_id or asset")
            self.session.add(
                AssetLedgerEntry(
                    event_id=event.id,
                    user_id=user_id,
                    asset_id=asset.id,
                    quantity_delta=Decimal(str(item["quantity_delta"])),
                    cash_currency=str(item["cash_currency"]).upper(),
                    cash_amount=self._optional_decimal(item.get("cash_amount")),
                    unit_price=self._optional_decimal(item.get("unit_price")),
                    fx_rate_to_cny=self._optional_decimal(item.get("fx_rate_to_cny")),
                    description=item.get("description"),
                )
            )

        if commit:
            self.session.commit()
            self.session.refresh(event)
        return event

    def create_valuation(self, *, user_id: int, payload: Dict[str, Any]) -> ValuationSnapshot:
        asset = self.session.get(Asset, int(payload["asset_id"])) if payload.get("asset_id") else None
        if asset is None and payload.get("asset"):
            asset = self.ensure_asset(payload["asset"])
        if asset is None:
            raise ValueError("valuation requires asset_id or asset")

        valuation = ValuationSnapshot(
            user_id=user_id,
            asset_id=asset.id,
            valuation_time=self._parse_datetime(payload["valuation_time"]),
            quantity=Decimal(str(payload["quantity"])),
            price=self._optional_decimal(payload.get("price")),
            market_value=Decimal(str(payload["market_value"])),
            currency=str(payload.get("currency") or asset.currency).upper(),
            fx_rate_to_cny=self._optional_decimal(payload.get("fx_rate_to_cny")),
            source=payload.get("source", "manual"),
            is_estimated=bool(payload.get("is_estimated", False)),
        )
        self.session.add(valuation)
        self.session.commit()
        self.session.refresh(valuation)
        return valuation

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    def _optional_decimal(self, value: Any) -> Optional[Decimal]:
        if value in (None, ""):
            return None
        return Decimal(str(value))

    def _asset_type(self, value: Any) -> AssetType:
        return value if isinstance(value, AssetType) else AssetType[str(value)]

    def _event_type(self, value: Any) -> EventType:
        return value if isinstance(value, EventType) else EventType[str(value)]

    def _status(self, value: Any) -> RecordStatus:
        return value if isinstance(value, RecordStatus) else RecordStatus[str(value)]


class PerformanceService:
    """Compute v0.2 portfolio-level performance from cash ledgers and valuation snapshots."""

    INVESTMENT_POOL_EVENTS = {EventType.FX_BUY, EventType.FX_SELL, EventType.FX_SWAP, EventType.MANUAL_ADJUSTMENT}
    AMOUNT_VALUED_ASSET_TYPES = {AssetType.BOND, AssetType.FUND, AssetType.WEALTH_PRODUCT}

    def __init__(self, session: Session) -> None:
        self.session = session

    def cash_balances(self, *, user_id: int, valuation_time: Optional[datetime] = None) -> Dict[str, Any]:
        rows = self.session.query(CashLedgerEntry).filter(CashLedgerEntry.user_id == user_id).all()
        balances: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for row in rows:
            if row.currency.upper() == "CNY" and row.is_external_flow:
                continue
            balances[row.currency.upper()] += Decimal(str(row.amount_delta))

        missing_rates: List[str] = []
        response = []
        for currency in sorted(balances):
            rate = self._rate_for_currency(currency, valuation_time=valuation_time)
            value_cny = None
            if rate is None:
                missing_rates.append(currency)
            else:
                value_cny = balances[currency] * rate
            response.append(
                {
                    "currency": currency,
                    "cash_balance": self._to_float(balances[currency], "0.000001"),
                    "current_fx_rate_to_cny": self._to_float(rate, "0.000001") if rate is not None else None,
                    "cash_value_cny": self._to_float(value_cny, "0.01") if value_cny is not None else None,
                }
            )
        return {"cash_balances": response, "data_quality": {"missing_rates": missing_rates}}

    def performance(self, *, user_id: int, valuation_time: Optional[datetime] = None) -> Dict[str, Any]:
        cutoff = valuation_time or datetime.now(timezone.utc)
        cash_rows = self.session.query(CashLedgerEntry).filter(CashLedgerEntry.user_id == user_id).all()
        events = {row.id: row for row in self.session.query(PortfolioEvent).filter(PortfolioEvent.user_id == user_id).all()}

        cash_balances: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        historical_native: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        historical_cny: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        net_invested_cny = Decimal("0")
        for row in cash_rows:
            currency = row.currency.upper()
            amount = Decimal(str(row.amount_delta))
            if not (currency == "CNY" and row.is_external_flow):
                cash_balances[currency] += amount
            event = events.get(row.event_id)
            if event and event.event_type in self.INVESTMENT_POOL_EVENTS and currency != "CNY":
                historical_native[currency] += amount
                if row.rmb_amount is not None:
                    historical_cny[currency] += Decimal("1" if amount >= 0 else "-1") * Decimal(str(row.rmb_amount))
                elif row.fx_rate_to_cny is not None:
                    historical_cny[currency] += amount * Decimal(str(row.fx_rate_to_cny))
            if row.is_external_flow and currency == "CNY":
                net_invested_cny -= amount

        asset_quantities = self._asset_quantities(user_id=user_id)
        assets_by_id = {asset.id: asset for asset in self.session.query(Asset).all()}
        valuations, missing_valuations = self._latest_valuations(
            user_id=user_id,
            cutoff=cutoff,
            asset_quantities=asset_quantities,
            assets_by_id=assets_by_id,
        )
        open_asset_currencies = {
            assets_by_id[asset_id].currency.upper()
            for asset_id, quantity in asset_quantities.items()
            if quantity != 0 and asset_id in assets_by_id
        }
        currencies = set(cash_balances) | {item.currency.upper() for item in valuations.values()} | set(historical_native) | open_asset_currencies
        by_currency: List[Dict[str, Any]] = []
        missing_rates: List[str] = []
        estimated_values: List[Dict[str, Any]] = []
        total_assets_cny = Decimal("0")
        investment_pnl_cny = Decimal("0")
        asset_type_totals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

        asset_value_by_currency: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for asset_id, valuation in valuations.items():
            currency = valuation.currency.upper()
            market_value = Decimal(str(valuation.market_value))
            asset_value_by_currency[currency] += market_value
            asset = assets_by_id.get(asset_id)
            if asset:
                rate = self._valuation_rate(valuation, cutoff)
                if rate is not None:
                    asset_type_totals[asset.asset_type.value] += market_value * rate
            if valuation.is_estimated:
                estimated_values.append({"asset_id": asset_id, "currency": currency, "market_value": self._to_float(market_value, "0.01")})

        for asset_id, quantity in asset_quantities.items():
            if quantity == 0 or asset_id in valuations:
                continue
            asset = assets_by_id.get(asset_id)
            if asset is None or asset.asset_type not in self.AMOUNT_VALUED_ASSET_TYPES:
                continue
            currency = asset.currency.upper()
            market_value = quantity
            asset_value_by_currency[currency] += market_value
            rate = self._rate_for_currency(currency, valuation_time=cutoff)
            if rate is not None:
                asset_type_totals[asset.asset_type.value] += market_value * rate

        for currency in sorted(currencies):
            rate = self._rate_for_currency(currency, valuation_time=cutoff)
            cash_balance = cash_balances[currency]
            native_asset_value = asset_value_by_currency[currency]
            current_total_native = cash_balance + native_asset_value
            historical_native_amount = historical_native[currency]

            if rate is None:
                missing_rates.append(currency)
                by_currency.append(
                    self._currency_row(
                        currency=currency,
                        cash_balance=cash_balance,
                        cash_value_cny=None,
                        asset_market_value_native=native_asset_value,
                        asset_market_value_cny=None,
                        current_total_assets_native=current_total_native,
                        current_total_assets_cny=None,
                        historical_net_invested_native=historical_native_amount,
                        investment_pnl_native=None,
                        investment_pnl_cny=None,
                        fx_pnl_cny=None,
                        rate=None,
                    )
                )
                continue

            cash_value_cny = cash_balance * rate
            asset_value_cny = native_asset_value * rate
            current_total_cny = current_total_native * rate
            investment_native = current_total_native - historical_native_amount if currency != "CNY" else Decimal("0")
            investment_cny = investment_native * rate
            currency_total_pnl_cny = current_total_cny - historical_cny[currency] if currency != "CNY" else Decimal("0")
            currency_fx_pnl_cny = currency_total_pnl_cny - investment_cny if currency != "CNY" else Decimal("0")
            total_assets_cny += current_total_cny
            investment_pnl_cny += investment_cny
            if cash_balance and currency != "CNY":
                asset_type_totals[AssetType.CASH.value] += cash_value_cny
            by_currency.append(
                self._currency_row(
                    currency=currency,
                    cash_balance=cash_balance,
                    cash_value_cny=cash_value_cny,
                    asset_market_value_native=native_asset_value,
                    asset_market_value_cny=asset_value_cny,
                    current_total_assets_native=current_total_native,
                    current_total_assets_cny=current_total_cny,
                    historical_net_invested_native=historical_native_amount,
                    investment_pnl_native=investment_native,
                    investment_pnl_cny=investment_cny,
                    fx_pnl_cny=currency_fx_pnl_cny,
                    rate=rate,
                )
            )

        total_pnl_cny = total_assets_cny - net_invested_cny
        fx_pnl_cny = total_pnl_cny - investment_pnl_cny

        by_asset_type = []
        for asset_type, value in sorted(asset_type_totals.items()):
            by_asset_type.append(
                {
                    "asset_type": asset_type,
                    "current_value_cny": self._to_float(value, "0.01"),
                    "investment_pnl_cny": None,
                    "fx_pnl_cny": None,
                    "weight_pct": self._to_float((value / total_assets_cny * 100) if total_assets_cny else Decimal("0"), "0.0001"),
                }
            )

        return {
            "overview": {
                "current_total_assets_cny": self._to_float(total_assets_cny, "0.01"),
                "net_invested_cny": self._to_float(net_invested_cny, "0.01"),
                "total_pnl_cny": self._to_float(total_pnl_cny, "0.01"),
                "total_return_pct": self._to_float((total_pnl_cny / net_invested_cny * 100) if net_invested_cny else Decimal("0"), "0.0001"),
                "investment_pnl_cny": self._to_float(investment_pnl_cny, "0.01"),
                "fx_pnl_cny": self._to_float(fx_pnl_cny, "0.01"),
                "investment_pnl_ratio": self._to_float((investment_pnl_cny / total_pnl_cny * 100) if total_pnl_cny else Decimal("0"), "0.0001"),
                "fx_pnl_ratio": self._to_float((fx_pnl_cny / total_pnl_cny * 100) if total_pnl_cny else Decimal("0"), "0.0001"),
            },
            "by_currency": by_currency,
            "by_asset_type": by_asset_type,
            "data_quality": {
                "missing_rates": sorted(set(missing_rates)),
                "missing_valuations": missing_valuations,
                "estimated_values": estimated_values,
            },
        }

    def _asset_quantities(self, *, user_id: int) -> Dict[int, Decimal]:
        quantities: Dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        rows = (
            self.session.query(AssetLedgerEntry)
            .join(PortfolioEvent, PortfolioEvent.id == AssetLedgerEntry.event_id)
            .join(Asset, Asset.id == AssetLedgerEntry.asset_id)
            .filter(AssetLedgerEntry.user_id == user_id)
            .order_by(AssetLedgerEntry.asset_id, PortfolioEvent.event_time.asc(), AssetLedgerEntry.id.asc())
            .all()
        )
        assets_by_id = {asset.id: asset for asset in self.session.query(Asset).all()}
        for row in rows:
            delta = Decimal(str(row.quantity_delta))
            asset = assets_by_id.get(row.asset_id)
            if asset is not None and asset.asset_type in self.AMOUNT_VALUED_ASSET_TYPES and delta < 0:
                delta = max(delta, -quantities[row.asset_id])
            quantities[row.asset_id] += delta
        return quantities

    def _latest_valuations(
        self,
        *,
        user_id: int,
        cutoff: datetime,
        asset_quantities: Dict[int, Decimal],
        assets_by_id: Optional[Dict[int, Asset]] = None,
    ) -> Tuple[Dict[int, ValuationSnapshot], List[Dict[str, Any]]]:
        rows = (
            self.session.query(ValuationSnapshot)
            .filter(ValuationSnapshot.user_id == user_id, ValuationSnapshot.valuation_time <= cutoff)
            .order_by(ValuationSnapshot.valuation_time.desc(), ValuationSnapshot.id.desc())
            .all()
        )
        latest: Dict[int, ValuationSnapshot] = {}
        for row in rows:
            if row.asset_id not in latest:
                latest[row.asset_id] = row

        assets_by_id = assets_by_id or {asset.id: asset for asset in self.session.query(Asset).all()}
        missing = []
        for asset_id, quantity in asset_quantities.items():
            if quantity == 0 or asset_id in latest:
                continue
            asset = assets_by_id.get(asset_id)
            if asset and asset.asset_type in self.AMOUNT_VALUED_ASSET_TYPES:
                continue
            missing.append(
                {
                    "asset_id": asset_id,
                    "asset_code": asset.asset_code if asset else None,
                    "asset_type": asset.asset_type.value if asset else None,
                    "quantity": self._to_float(quantity, "0.000001"),
                }
            )
        return latest, missing

    def _valuation_rate(self, valuation: ValuationSnapshot, cutoff: datetime) -> Optional[Decimal]:
        if valuation.fx_rate_to_cny is not None:
            return Decimal(str(valuation.fx_rate_to_cny))
        return self._rate_for_currency(valuation.currency, valuation_time=cutoff)

    def _rate_for_currency(self, currency: str, *, valuation_time: Optional[datetime]) -> Optional[Decimal]:
        normalized = currency.upper()
        if normalized == "CNY":
            return Decimal("1")
        query = self.session.query(ExchangeRate).filter(
            ExchangeRate.base_currency == normalized,
            ExchangeRate.quote_currency == "CNY",
        )
        if valuation_time is not None:
            query = query.filter(ExchangeRate.rate_timestamp <= valuation_time)
        source_priority = case(
            (ExchangeRate.source == RateSourceType.MANUAL, 0),
            (ExchangeRate.source == RateSourceType.PRIMARY, 1),
            else_=2,
        )
        row = query.order_by(
            ExchangeRate.rate_timestamp.desc(),
            ExchangeRate.is_estimated.asc(),
            source_priority.asc(),
            ExchangeRate.id.desc(),
        ).first()
        if row is None:
            return None
        return Decimal(str(row.rate))

    def _currency_row(
        self,
        *,
        currency: str,
        cash_balance: Decimal,
        cash_value_cny: Optional[Decimal],
        asset_market_value_native: Decimal,
        asset_market_value_cny: Optional[Decimal],
        current_total_assets_native: Decimal,
        current_total_assets_cny: Optional[Decimal],
        historical_net_invested_native: Decimal,
        investment_pnl_native: Optional[Decimal],
        investment_pnl_cny: Optional[Decimal],
        fx_pnl_cny: Optional[Decimal],
        rate: Optional[Decimal],
    ) -> Dict[str, Any]:
        return {
            "currency": currency,
            "cash_balance": self._to_float(cash_balance, "0.000001"),
            "cash_value_cny": self._to_float(cash_value_cny, "0.01") if cash_value_cny is not None else None,
            "asset_market_value_native": self._to_float(asset_market_value_native, "0.01"),
            "asset_market_value_cny": self._to_float(asset_market_value_cny, "0.01") if asset_market_value_cny is not None else None,
            "current_total_assets_native": self._to_float(current_total_assets_native, "0.000001"),
            "current_total_assets_cny": self._to_float(current_total_assets_cny, "0.01") if current_total_assets_cny is not None else None,
            "historical_net_invested_native": self._to_float(historical_net_invested_native, "0.000001"),
            "investment_pnl_native": self._to_float(investment_pnl_native, "0.000001") if investment_pnl_native is not None else None,
            "investment_pnl_cny": self._to_float(investment_pnl_cny, "0.01") if investment_pnl_cny is not None else None,
            "fx_pnl_cny": self._to_float(fx_pnl_cny, "0.01") if fx_pnl_cny is not None else None,
            "current_fx_rate_to_cny": self._to_float(rate, "0.000001") if rate is not None else None,
        }

    def _to_float(self, value: Optional[Decimal], pattern: str) -> float:
        if value is None:
            return 0.0
        return float(value.quantize(Decimal(pattern), rounding=ROUND_HALF_UP))


class AuditService:
    """Generate source-data breakdowns for performance audit reports."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.performance_service = PerformanceService(session)
        self.exchange_rate_service = ExchangeRateService(session)

    def generate_audit(
        self,
        *,
        user_id: int,
        currency: Optional[str] = None,
        valuation_time: Optional[datetime] = None,
        expected_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a complete performance audit report for one or more currencies."""
        cutoff = valuation_time or datetime.now(timezone.utc)
        performance = self.performance_service.performance(user_id=user_id, valuation_time=cutoff)
        performance_by_currency = {item["currency"]: item for item in performance["by_currency"]}
        currencies = [currency.upper()] if currency else sorted(performance_by_currency)
        expected = self._normalise_expected_values(expected_values or {})

        by_currency = []
        currencies_with_issues = []
        total_discrepancies = 0
        for item_currency in currencies:
            performance_row = performance_by_currency.get(item_currency, {"currency": item_currency})
            cash_breakdown = self.get_cash_breakdown(user_id=user_id, currency=item_currency, valuation_time=cutoff)
            asset_breakdown = self.get_asset_breakdown(user_id=user_id, currency=item_currency, valuation_time=cutoff)
            historical_breakdown = self.get_historical_input_breakdown(user_id=user_id, currency=item_currency)
            rate = self.performance_service._rate_for_currency(item_currency, valuation_time=cutoff)
            rate_details = self._exchange_rate_details(item_currency, valuation_time=cutoff)

            calculated = {
                "cash_balance": performance_row.get("cash_balance", cash_breakdown["total_balance"]),
                "asset_market_value_native": performance_row.get(
                    "asset_market_value_native", asset_breakdown["total_market_value"]
                ),
                "current_total_assets_native": performance_row.get(
                    "current_total_assets_native",
                    cash_breakdown["total_balance"] + asset_breakdown["total_market_value"],
                ),
                "current_total_assets_cny": performance_row.get("current_total_assets_cny"),
                "historical_net_invested_native": performance_row.get(
                    "historical_net_invested_native", historical_breakdown["total_native_invested"]
                ),
                "historical_cny_invested": historical_breakdown["total_cny_invested"],
            }
            currency_data = {
                **calculated,
                "total_cny_invested": historical_breakdown["total_cny_invested"],
                "total_native_invested": historical_breakdown["total_native_invested"],
            }
            discrepancies = self.detect_discrepancies(calculated=calculated, expected=expected) if expected else []
            suggestions = self.generate_correction_suggestions(
                discrepancies=discrepancies,
                currency=item_currency,
                user_id=user_id,
            )
            if discrepancies:
                currencies_with_issues.append(item_currency)
            total_discrepancies += len(discrepancies)

            errors = []
            if rate is None:
                errors.append(
                    {
                        "code": "MISSING_EXCHANGE_RATE",
                        "message": f"Cannot calculate CNY metrics: {item_currency}/CNY rate is missing",
                        "affected_metrics": ["value_cny", "investment_pnl_cny", "fx_pnl_cny"],
                    }
                )

            by_currency.append(
                {
                    "currency": item_currency,
                    "status": "INCOMPLETE" if errors else "COMPLETE",
                    "errors": errors,
                    "cash_breakdown": cash_breakdown,
                    "asset_breakdown": asset_breakdown,
                    "historical_input_breakdown": historical_breakdown,
                    "calculation_trail": self.generate_calculation_trail(
                        currency_data=currency_data,
                        exchange_rate=rate,
                        exchange_rate_details=rate_details,
                        currency=item_currency,
                    ),
                    "discrepancies": discrepancies,
                    "correction_suggestions": suggestions,
                    "performance_metrics": performance_row,
                }
            )

        data_quality = performance["data_quality"]
        data_quality_issue_count = (
            len(data_quality.get("missing_rates", []))
            + len(data_quality.get("missing_valuations", []))
            + len(data_quality.get("estimated_values", []))
        )
        summary = {
            "total_discrepancies": total_discrepancies,
            "currencies_with_issues": currencies_with_issues,
            "data_quality_score": self._to_float(
                max(Decimal("0"), Decimal("100") - Decimal(total_discrepancies * 5) - Decimal(data_quality_issue_count * 2)),
                "0.01",
            ),
        }
        return {
            "audit_id": str(uuid4()),
            "audit_time": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "currencies_audited": currencies,
            "summary": summary,
            "overview": performance["overview"],
            "by_currency": by_currency,
            "data_quality": data_quality,
        }

    def create_audit_log(
        self,
        *,
        user_id: int,
        currencies_audited: List[str],
        discrepancies_found: int,
        audit_details: Dict[str, Any],
    ) -> AuditLog:
        """Persist audit report metadata and details."""
        audit_id = str(audit_details.get("audit_id") or uuid4())
        if not audit_details.get("audit_id"):
            audit_details["audit_id"] = audit_id
        log = AuditLog(
            user_id=user_id,
            entity_type="performance_audit",
            entity_id=audit_id,
            action="audit_generated",
            status="completed",
            details_json={
                "currencies_audited": currencies_audited,
                "discrepancies_found": discrepancies_found,
                "summary": audit_details.get("summary", {}),
                "audit_report": audit_details,
            },
        )
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log

    def get_audit_history(
        self,
        *,
        user_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return recent performance audit logs for a user."""
        rows = (
            self.session.query(AuditLog)
            .filter(AuditLog.user_id == user_id, AuditLog.entity_type == "performance_audit")
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .all()
        )
        history = []
        for row in rows:
            details = row.details_json or {}
            history.append(
                {
                    "id": row.id,
                    "audit_id": row.entity_id,
                    "audit_time": row.created_at.isoformat(),
                    "currencies_audited": details.get("currencies_audited", []),
                    "discrepancies_found": details.get("discrepancies_found", 0),
                    "summary": details.get("summary", {}),
                }
            )
        return history

    def get_cash_breakdown(
        self,
        *,
        user_id: int,
        currency: str,
        valuation_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return cash ledger entries, event subtotals, and running balance."""
        normalized_currency = currency.upper()
        query = (
            self.session.query(CashLedgerEntry)
            .join(PortfolioEvent, PortfolioEvent.id == CashLedgerEntry.event_id)
            .filter(CashLedgerEntry.user_id == user_id, CashLedgerEntry.currency == normalized_currency)
        )
        if valuation_time is not None:
            query = query.filter(PortfolioEvent.event_time <= valuation_time)
        rows = query.order_by(PortfolioEvent.event_time.asc(), CashLedgerEntry.id.asc()).all()

        running_balance = Decimal("0")
        subtotals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        entries = []
        for row in rows:
            event = row.event
            event_type = event.event_type.value if event else None
            amount = Decimal(str(row.amount_delta))
            included_in_balance = not (normalized_currency == "CNY" and row.is_external_flow)
            if included_in_balance:
                running_balance += amount
                if event_type is not None:
                    subtotals[event_type] += amount

            entries.append(
                {
                    "id": row.id,
                    "event_id": row.event_id,
                    "event_time": event.event_time.isoformat() if event else None,
                    "event_type": event_type,
                    "amount_delta": self._to_float(amount, "0.000001"),
                    "running_balance": self._to_float(running_balance, "0.000001"),
                    "included_in_balance": included_in_balance,
                    "is_external_flow": bool(row.is_external_flow),
                    "fx_rate_to_cny": self._to_float(Decimal(str(row.fx_rate_to_cny)), "0.000001") if row.fx_rate_to_cny is not None else None,
                    "rmb_amount": self._to_float(Decimal(str(row.rmb_amount)), "0.01") if row.rmb_amount is not None else None,
                    "description": row.description,
                }
            )

        return {
            "currency": normalized_currency,
            "entries": entries,
            "subtotals": {key: self._to_float(value, "0.000001") for key, value in sorted(subtotals.items())},
            "total_balance": self._to_float(running_balance, "0.000001"),
        }

    def get_asset_breakdown(
        self,
        *,
        user_id: int,
        currency: str,
        valuation_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return open asset quantities and their latest valuation source."""
        normalized_currency = currency.upper()
        cutoff = valuation_time or datetime.now(timezone.utc)
        asset_quantities = self._asset_quantities(user_id=user_id, valuation_time=valuation_time)
        assets_by_id = {
            asset.id: asset
            for asset in self.session.query(Asset).filter(Asset.currency == normalized_currency).all()
        }
        valuations, _ = self.performance_service._latest_valuations(
            user_id=user_id,
            cutoff=cutoff,
            asset_quantities=asset_quantities,
            assets_by_id=assets_by_id,
        )

        entries = []
        total_market_value = Decimal("0")
        for asset_id, quantity in sorted(asset_quantities.items()):
            if quantity == 0:
                continue
            asset = assets_by_id.get(asset_id)
            if asset is None:
                continue

            valuation = valuations.get(asset_id)
            market_value: Optional[Decimal] = None
            price: Optional[Decimal] = None
            valuation_time_value: Optional[str] = None
            valuation_source = "missing_valuation"
            is_estimated = False

            if valuation is not None:
                market_value = Decimal(str(valuation.market_value))
                price = Decimal(str(valuation.price)) if valuation.price is not None else None
                valuation_time_value = valuation.valuation_time.isoformat()
                valuation_source = valuation.source
                is_estimated = bool(valuation.is_estimated)
            elif asset.asset_type in PerformanceService.AMOUNT_VALUED_ASSET_TYPES:
                market_value = quantity
                valuation_source = "quantity_based"

            if market_value is not None:
                total_market_value += market_value

            entries.append(
                {
                    "asset_id": asset.id,
                    "asset_code": asset.asset_code,
                    "asset_name": asset.asset_name,
                    "asset_type": asset.asset_type.value,
                    "current_quantity": self._to_float(quantity, "0.000001"),
                    "latest_valuation_price": self._to_float(price, "0.000001") if price is not None else None,
                    "market_value": self._to_float(market_value, "0.01") if market_value is not None else None,
                    "valuation_time": valuation_time_value,
                    "valuation_source": valuation_source,
                    "is_estimated": is_estimated,
                }
            )

        return {
            "currency": normalized_currency,
            "entries": entries,
            "total_market_value": self._to_float(total_market_value, "0.01"),
        }

    def get_historical_input_breakdown(
        self,
        *,
        user_id: int,
        currency: str,
    ) -> Dict[str, Any]:
        """Return entries contributing to historical net input for a currency pool."""
        normalized_currency = currency.upper()
        rows = (
            self.session.query(CashLedgerEntry)
            .join(PortfolioEvent, PortfolioEvent.id == CashLedgerEntry.event_id)
            .filter(CashLedgerEntry.user_id == user_id, CashLedgerEntry.currency == normalized_currency)
            .filter(PortfolioEvent.event_type.in_(PerformanceService.INVESTMENT_POOL_EVENTS))
            .order_by(PortfolioEvent.event_time.asc(), CashLedgerEntry.id.asc())
            .all()
        )

        total_native = Decimal("0")
        total_cny = Decimal("0")
        entries = []
        for row in rows:
            amount = Decimal(str(row.amount_delta))
            event = row.event
            rmb_amount: Optional[Decimal] = None
            rmb_source = "missing"
            if row.rmb_amount is not None:
                rmb_amount = Decimal("1" if amount >= 0 else "-1") * Decimal(str(row.rmb_amount))
                rmb_source = "direct"
            elif row.fx_rate_to_cny is not None:
                rmb_amount = amount * Decimal(str(row.fx_rate_to_cny))
                rmb_source = "calculated"

            total_native += amount
            if rmb_amount is not None:
                total_cny += rmb_amount

            entries.append(
                {
                    "event_id": row.event_id,
                    "cash_ledger_entry_id": row.id,
                    "event_time": event.event_time.isoformat() if event else None,
                    "event_type": event.event_type.value if event else None,
                    "native_amount_delta": self._to_float(amount, "0.000001"),
                    "rmb_amount": self._to_float(rmb_amount, "0.01") if rmb_amount is not None else None,
                    "rmb_source": rmb_source,
                    "fx_rate_used": self._to_float(Decimal(str(row.fx_rate_to_cny)), "0.000001") if row.fx_rate_to_cny is not None else None,
                }
            )

        return {
            "currency": normalized_currency,
            "entries": entries,
            "total_native_invested": self._to_float(total_native, "0.000001"),
            "total_cny_invested": self._to_float(total_cny, "0.01"),
        }

    def generate_calculation_trail(
        self,
        *,
        currency_data: Dict[str, Any],
        exchange_rate: Optional[Decimal],
        currency: str,
        exchange_rate_details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build auditable formulas for the core performance metrics."""
        cash_balance = self._decimal_value(currency_data, "cash_balance", "total_balance")
        asset_value = self._decimal_value(currency_data, "asset_market_value_native", "total_market_value")
        historical_native = self._decimal_value(currency_data, "historical_net_invested_native", "total_native_invested")
        historical_cny = self._decimal_value(currency_data, "historical_cny_invested", "total_cny_invested")
        rate = exchange_rate
        native_assets = cash_balance + asset_value

        trail: Dict[str, List[Dict[str, Any]]] = {
            "native_assets": [
                self._calculation_step(
                    step_number=1,
                    description="Native assets",
                    formula="cash_balance + asset_market_value_native",
                    inputs={"cash_balance": cash_balance, "asset_market_value_native": asset_value},
                    result=native_assets,
                    notes=[f"Currency: {currency.upper()}"],
                    result_pattern="0.000001",
                )
            ],
            "value_cny": [],
            "investment_pnl": [],
            "fx_pnl": [],
        }

        if rate is None:
            missing_note = f"Missing {currency.upper()}/CNY exchange rate"
            for key in ("value_cny", "investment_pnl", "fx_pnl"):
                trail[key].append(
                    {
                        "step_number": 1,
                        "description": "Calculation incomplete",
                        "formula": "MISSING_RATE",
                        "inputs": {"current_fx_rate_to_cny": None},
                        "result": None,
                        "notes": [missing_note],
                    }
                )
            return trail

        value_cny = native_assets * rate
        investment_native = native_assets - historical_native if currency.upper() != "CNY" else Decimal("0")
        investment_pnl_cny = investment_native * rate
        fx_pnl_cny = (native_assets * rate - historical_cny) - investment_pnl_cny if currency.upper() != "CNY" else Decimal("0")
        rate_note = self._exchange_rate_note(currency=currency, rate=rate, details=exchange_rate_details)

        trail["value_cny"].append(
            self._calculation_step(
                step_number=1,
                description="Value CNY",
                formula="native_assets * current_fx_rate_to_cny",
                inputs={"native_assets": native_assets, "current_fx_rate_to_cny": rate},
                result=value_cny,
                notes=[rate_note],
                result_pattern="0.01",
            )
        )
        trail["investment_pnl"].append(
            self._calculation_step(
                step_number=1,
                description="Investment PnL",
                formula="(current_total_native - historical_net_invested_native) * current_fx_rate_to_cny",
                inputs={
                    "current_total_native": native_assets,
                    "historical_net_invested_native": historical_native,
                    "current_fx_rate_to_cny": rate,
                },
                result=investment_pnl_cny,
                notes=[f"Investment PnL native: {investment_native}", rate_note],
                result_pattern="0.01",
            )
        )
        trail["fx_pnl"].append(
            self._calculation_step(
                step_number=1,
                description="FX PnL",
                formula="(current_total_native * current_fx_rate_to_cny - historical_cny_invested) - investment_pnl_cny",
                inputs={
                    "current_total_native": native_assets,
                    "current_fx_rate_to_cny": rate,
                    "historical_cny_invested": historical_cny,
                    "investment_pnl_cny": investment_pnl_cny,
                },
                result=fx_pnl_cny,
                notes=[rate_note],
                result_pattern="0.01",
            )
        )
        return trail

    def detect_discrepancies(
        self,
        *,
        calculated: Dict[str, Any],
        expected: Dict[str, Any],
        threshold: Decimal = Decimal("0.01"),
    ) -> List[Dict[str, Any]]:
        """Compare calculated and expected metric values."""
        discrepancies = []
        for metric, expected_value in expected.items():
            if expected_value in (None, "") or metric not in calculated or calculated[metric] is None:
                continue
            calculated_decimal = Decimal(str(calculated[metric]))
            expected_decimal = Decimal(str(expected_value))
            absolute_difference = calculated_decimal - expected_decimal
            if abs(absolute_difference) <= threshold:
                continue
            percentage_difference: Optional[Decimal] = None
            if expected_decimal != 0:
                percentage_difference = absolute_difference / expected_decimal * Decimal("100")
            severity = self._discrepancy_severity(abs(absolute_difference), percentage_difference)
            discrepancies.append(
                {
                    "metric": metric,
                    "calculated_value": self._to_float(calculated_decimal, "0.000001"),
                    "expected_value": self._to_float(expected_decimal, "0.000001"),
                    "absolute_difference": self._to_float(absolute_difference, "0.000001"),
                    "percentage_difference": self._to_float(percentage_difference, "0.0001") if percentage_difference is not None else None,
                    "severity": severity,
                }
            )
        return discrepancies

    def generate_correction_suggestions(
        self,
        *,
        discrepancies: List[Dict[str, Any]],
        currency: str,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """Suggest likely source records to review for each discrepancy."""
        suggestions = []
        normalized_currency = currency.upper()
        for index, discrepancy in enumerate(discrepancies, start=1):
            metric = str(discrepancy.get("metric", ""))
            if metric in {"cash_balance", "total_balance"}:
                suggestions.append(
                    {
                        "suggestion_id": f"{normalized_currency}-cash-{index}",
                        "discrepancy_metric": metric,
                        "suggested_action": "Review missing or duplicate cash ledger entries for this currency.",
                        "likelihood": "high",
                        "details": "Cash balance discrepancies usually come from omitted imports, duplicate imports, or external-flow flags.",
                        "affected_records": self._cash_record_ids(user_id=user_id, currency=normalized_currency),
                    }
                )
            elif metric in {"asset_market_value_native", "asset_market_value", "total_market_value", "assets"}:
                suggestions.append(
                    {
                        "suggestion_id": f"{normalized_currency}-assets-{index}",
                        "discrepancy_metric": metric,
                        "suggested_action": "Review asset ledger quantities and latest valuation snapshots.",
                        "likelihood": "high",
                        "details": "Asset value discrepancies usually come from stale valuations, missing snapshots, or incorrect quantity deltas.",
                        "affected_records": self._asset_record_ids(user_id=user_id, currency=normalized_currency),
                    }
                )
            elif metric in {"historical_net_invested_native", "historical_cny_invested", "historical_input"}:
                suggestions.append(
                    {
                        "suggestion_id": f"{normalized_currency}-historical-input-{index}",
                        "discrepancy_metric": metric,
                        "suggested_action": "Review FX pool events and RMB amount fields used for historical input.",
                        "likelihood": "medium",
                        "details": "Historical input discrepancies usually come from FX_BUY, FX_SELL, FX_SWAP, or MANUAL_ADJUSTMENT records.",
                        "affected_records": self._historical_input_record_ids(user_id=user_id, currency=normalized_currency),
                    }
                )
            else:
                suggestions.append(
                    {
                        "suggestion_id": f"{normalized_currency}-general-{index}",
                        "discrepancy_metric": metric,
                        "suggested_action": "Review source ledger entries, valuations, and exchange rates for this metric.",
                        "likelihood": "low",
                        "details": "The metric does not map to one specific audit section yet.",
                        "affected_records": [],
                    }
                )
        return suggestions

    def _asset_quantities(self, *, user_id: int, valuation_time: Optional[datetime] = None) -> Dict[int, Decimal]:
        quantities: Dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        query = (
            self.session.query(AssetLedgerEntry)
            .join(PortfolioEvent, PortfolioEvent.id == AssetLedgerEntry.event_id)
            .join(Asset, Asset.id == AssetLedgerEntry.asset_id)
            .filter(AssetLedgerEntry.user_id == user_id)
        )
        if valuation_time is not None:
            query = query.filter(PortfolioEvent.event_time <= valuation_time)
        rows = query.order_by(AssetLedgerEntry.asset_id, PortfolioEvent.event_time.asc(), AssetLedgerEntry.id.asc()).all()
        assets_by_id = {asset.id: asset for asset in self.session.query(Asset).all()}
        for row in rows:
            delta = Decimal(str(row.quantity_delta))
            asset = assets_by_id.get(row.asset_id)
            if asset is not None and asset.asset_type in PerformanceService.AMOUNT_VALUED_ASSET_TYPES and delta < 0:
                delta = max(delta, -quantities[row.asset_id])
            quantities[row.asset_id] += delta
        return quantities

    def _calculation_step(
        self,
        *,
        step_number: int,
        description: str,
        formula: str,
        inputs: Dict[str, Decimal],
        result: Decimal,
        notes: List[str],
        result_pattern: str,
    ) -> Dict[str, Any]:
        return {
            "step_number": step_number,
            "description": description,
            "formula": formula,
            "inputs": {key: self._to_float(value, "0.000001") for key, value in inputs.items()},
            "result": self._to_float(result, result_pattern),
            "notes": notes,
        }

    def _decimal_value(self, values: Dict[str, Any], *keys: str) -> Decimal:
        for key in keys:
            value = values.get(key)
            if value is not None:
                return Decimal(str(value))
        return Decimal("0")

    def _discrepancy_severity(self, absolute_difference: Decimal, percentage_difference: Optional[Decimal]) -> str:
        if percentage_difference is None:
            return "error" if absolute_difference >= Decimal("1") else "warning"
        percentage = abs(percentage_difference)
        if percentage >= Decimal("1"):
            return "error"
        if percentage >= Decimal("0.1"):
            return "warning"
        return "info"

    def _cash_record_ids(self, *, user_id: int, currency: str) -> List[str]:
        rows = (
            self.session.query(CashLedgerEntry.id)
            .filter(CashLedgerEntry.user_id == user_id, CashLedgerEntry.currency == currency)
            .order_by(CashLedgerEntry.id.asc())
            .all()
        )
        return [f"cash_ledger_entries:{row[0]}" for row in rows]

    def _asset_record_ids(self, *, user_id: int, currency: str) -> List[str]:
        rows = (
            self.session.query(AssetLedgerEntry.id, ValuationSnapshot.id)
            .join(Asset, Asset.id == AssetLedgerEntry.asset_id)
            .outerjoin(
                ValuationSnapshot,
                (ValuationSnapshot.asset_id == AssetLedgerEntry.asset_id)
                & (ValuationSnapshot.user_id == AssetLedgerEntry.user_id),
            )
            .filter(AssetLedgerEntry.user_id == user_id, Asset.currency == currency)
            .order_by(AssetLedgerEntry.id.asc(), ValuationSnapshot.id.asc())
            .all()
        )
        record_ids = []
        seen = set()
        for asset_entry_id, valuation_id in rows:
            asset_key = f"asset_ledger_entries:{asset_entry_id}"
            if asset_key not in seen:
                record_ids.append(asset_key)
                seen.add(asset_key)
            if valuation_id is not None:
                valuation_key = f"valuation_snapshots:{valuation_id}"
                if valuation_key not in seen:
                    record_ids.append(valuation_key)
                    seen.add(valuation_key)
        return record_ids

    def _historical_input_record_ids(self, *, user_id: int, currency: str) -> List[str]:
        rows = (
            self.session.query(CashLedgerEntry.id, CashLedgerEntry.event_id)
            .join(PortfolioEvent, PortfolioEvent.id == CashLedgerEntry.event_id)
            .filter(CashLedgerEntry.user_id == user_id, CashLedgerEntry.currency == currency)
            .filter(PortfolioEvent.event_type.in_(PerformanceService.INVESTMENT_POOL_EVENTS))
            .order_by(PortfolioEvent.event_time.asc(), CashLedgerEntry.id.asc())
            .all()
        )
        record_ids = []
        seen = set()
        for cash_entry_id, event_id in rows:
            for record_id in (f"portfolio_events:{event_id}", f"cash_ledger_entries:{cash_entry_id}"):
                if record_id not in seen:
                    record_ids.append(record_id)
                    seen.add(record_id)
        return record_ids

    def _exchange_rate_details(self, currency: str, *, valuation_time: Optional[datetime]) -> Optional[Dict[str, Any]]:
        normalized = currency.upper()
        if normalized == "CNY":
            return {
                "base_currency": "CNY",
                "quote_currency": "CNY",
                "rate": 1.0,
                "rate_timestamp": None,
                "source": "IDENTITY",
                "is_estimated": False,
            }
        query = self.session.query(ExchangeRate).filter(
            ExchangeRate.base_currency == normalized,
            ExchangeRate.quote_currency == "CNY",
        )
        if valuation_time is not None:
            query = query.filter(ExchangeRate.rate_timestamp <= valuation_time)
        source_priority = case(
            (ExchangeRate.source == RateSourceType.MANUAL, 0),
            (ExchangeRate.source == RateSourceType.PRIMARY, 1),
            else_=2,
        )
        row = query.order_by(
            ExchangeRate.rate_timestamp.desc(),
            ExchangeRate.is_estimated.asc(),
            source_priority.asc(),
            ExchangeRate.id.desc(),
        ).first()
        if row is None:
            return None
        return {
            "base_currency": row.base_currency,
            "quote_currency": row.quote_currency,
            "rate": self._to_float(Decimal(str(row.rate)), "0.000001"),
            "rate_timestamp": row.rate_timestamp.isoformat(),
            "source": row.source.value,
            "is_estimated": bool(row.is_estimated),
        }

    def _exchange_rate_note(
        self,
        *,
        currency: str,
        rate: Decimal,
        details: Optional[Dict[str, Any]],
    ) -> str:
        if details is None:
            return f"Exchange rate used: {currency.upper()}/CNY={rate}"
        parts = [
            f"Exchange rate used: {details['base_currency']}/{details['quote_currency']}={rate}",
            f"source={details['source']}",
        ]
        if details.get("rate_timestamp"):
            parts.append(f"timestamp={details['rate_timestamp']}")
        if details.get("is_estimated"):
            parts.append("ESTIMATED")
        return " | ".join(parts)

    def _normalise_expected_values(self, expected_values: Dict[str, Any]) -> Dict[str, Any]:
        aliases = {
            "expected_cash": "cash_balance",
            "cash": "cash_balance",
            "expected_assets": "asset_market_value_native",
            "assets": "asset_market_value_native",
            "expected_value_cny": "current_total_assets_cny",
            "value_cny": "current_total_assets_cny",
        }
        expected = {}
        for key, value in expected_values.items():
            expected[aliases.get(key, key)] = value
        return expected

    def _to_float(self, value: Optional[Decimal], pattern: str) -> float:
        if value is None:
            return 0.0
        return float(value.quantize(Decimal(pattern), rounding=ROUND_HALF_UP))
