"""Domain services for portfolio and exchange-rate workflows."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple

from investment_tracker.data.enums import AssetType, EventType, RateSourceType, RecordStatus
from investment_tracker.data.models import (
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
        query = self.session.query(ExchangeRate).order_by(ExchangeRate.rate_timestamp.desc(), ExchangeRate.id.desc())
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
        row = query.order_by(ExchangeRate.rate_timestamp.desc(), ExchangeRate.id.desc()).first()
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
