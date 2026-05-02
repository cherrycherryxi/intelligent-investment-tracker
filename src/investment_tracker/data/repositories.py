"""Repository helpers for transactions and related records."""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from investment_tracker.data.enums import AssetType, EventType, RecordStatus, TransactionDirection
from investment_tracker.data.models import AuditLog, Position, Transaction, User
from investment_tracker.data.services import PortfolioEventService
from investment_tracker.utils.backup import BackupService
from investment_tracker.utils.validators import (
    validate_positive_decimal,
    validate_sell_quantity,
    validate_trade_time_not_future,
)


class TransactionRepository:
    """Persist transaction records with minimal user bootstrapping."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_user(self, user_id: int) -> User:
        user = self.session.get(User, user_id)
        if user is not None:
            return user

        user = User(
            id=user_id,
            username=f"user-{user_id}",
            email=f"user-{user_id}@local.invalid",
            risk_preference="balanced",
        )
        self.session.add(user)
        self.session.flush()
        return user

    def create_transactions(self, *, user_id: int, transactions: List[Dict[str, Any]]) -> List[Transaction]:
        self.ensure_user(user_id)
        created: List[Transaction] = []
        for item in transactions:
            self._validate_transaction(user_id=user_id, item=item)
            transaction = Transaction(
                user_id=user_id,
                asset_type=self._asset_type(item["asset_type"]),
                asset_code=item["asset_code"],
                asset_name=item.get("asset_name"),
                direction=self._direction(item["direction"]),
                quantity=Decimal(str(item["quantity"])),
                unit_price=Decimal(str(item["unit_price"])),
                trade_currency=item["trade_currency"],
                trade_time=self._parse_trade_time(item["trade_time"]),
                exchange_rate_to_cny=self._optional_decimal(item.get("exchange_rate_to_cny")),
                total_cost_cny=self._optional_decimal(item.get("total_cost_cny")),
                source=item.get("source", "excel_import"),
                status=self._status(item.get("status", "CONFIRMED")),
                raw_text=item.get("raw_text"),
                notes=item.get("notes"),
            )
            self.session.add(transaction)
            created.append(transaction)
            self._create_compat_portfolio_event(user_id=user_id, item=item)
            self._log_audit(
                user_id=user_id,
                entity_type="transaction",
                entity_id=item.get("asset_code", "unknown"),
                action="create",
                status="success",
                details={"source": item.get("source", "manual")},
            )

        self.session.commit()
        BackupService(self.session).create_backup(reason="transactions_updated")
        for transaction in created:
            self.session.refresh(transaction)
        return created

    def list_transactions(self, *, user_id: int, limit: int = 20) -> List[Transaction]:
        return (
            self.session.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.trade_time.desc(), Transaction.id.desc())
            .limit(limit)
            .all()
        )

    def list_transactions_filtered(
        self,
        *,
        user_id: int,
        asset_code: Optional[str] = None,
        direction: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
    ) -> List[Transaction]:
        query = self.session.query(Transaction).filter(Transaction.user_id == user_id)
        if asset_code:
            query = query.filter(Transaction.asset_code == asset_code.upper())
        if direction:
            query = query.filter(Transaction.direction == self._direction(direction))
        if start_time:
            query = query.filter(Transaction.trade_time >= self._parse_trade_time(start_time))
        if end_time:
            query = query.filter(Transaction.trade_time <= self._parse_trade_time(end_time))
        return query.order_by(Transaction.trade_time.desc(), Transaction.id.desc()).limit(limit).all()

    def get_position_quantity(self, *, user_id: int, asset_code: str) -> Decimal:
        transactions = (
            self.session.query(Transaction)
            .filter(Transaction.user_id == user_id, Transaction.asset_code == asset_code.upper())
            .all()
        )
        quantity = Decimal("0")
        for item in transactions:
            if item.direction == TransactionDirection.BUY:
                quantity += Decimal(str(item.quantity))
            else:
                quantity -= Decimal(str(item.quantity))
        return quantity

    def list_positions_snapshot(self, *, user_id: int) -> List[Position]:
        return self.session.query(Position).filter(Position.user_id == user_id).order_by(Position.asset_code).all()

    def _parse_trade_time(self, value: str) -> datetime:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    def _optional_decimal(self, value: Any):
        if value in (None, ""):
            return None
        return Decimal(str(value))

    def _asset_type(self, value: Any) -> AssetType:
        return value if isinstance(value, AssetType) else AssetType[str(value)]

    def _direction(self, value: Any) -> TransactionDirection:
        return value if isinstance(value, TransactionDirection) else TransactionDirection[str(value)]

    def _status(self, value: Any) -> RecordStatus:
        return value if isinstance(value, RecordStatus) else RecordStatus[str(value)]

    def _validate_transaction(self, *, user_id: int, item: Dict[str, Any]) -> None:
        quantity = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unit_price"]))
        trade_time = self._parse_trade_time(item["trade_time"])
        validate_positive_decimal(quantity, "quantity")
        validate_positive_decimal(unit_price, "unit_price")
        validate_trade_time_not_future(trade_time)

        direction = self._direction(item["direction"])
        if direction == TransactionDirection.SELL:
            # Make earlier pending inserts in the same batch visible to the position query.
            self.session.flush()
            current_quantity = self.get_position_quantity(user_id=user_id, asset_code=item["asset_code"])
            if quantity > current_quantity and os.getenv("INVESTMENT_TRACKER_DEBUG_SELL_BREAKPOINT") == "1":
                debug_context = {
                    "user_id": user_id,
                    "asset_code": item["asset_code"],
                    "asset_type": item.get("asset_type"),
                    "direction": item["direction"],
                    "sell_quantity": str(quantity),
                    "current_quantity": str(current_quantity),
                    "trade_time": item["trade_time"],
                    "trade_currency": item.get("trade_currency"),
                    "unit_price": item.get("unit_price"),
                    "source": item.get("source"),
                    "notes": item.get("notes"),
                }
                if debug_context:
                    breakpoint()
            validate_sell_quantity(current_quantity, quantity)

    def _create_compat_portfolio_event(self, *, user_id: int, item: Dict[str, Any]) -> None:
        asset_type = self._asset_type(item["asset_type"])
        if asset_type != AssetType.FOREX:
            return

        direction = self._direction(item["direction"])
        asset_code = str(item["asset_code"]).upper()
        trade_currency = str(item["trade_currency"]).upper()
        quantity = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unit_price"]))
        total_cost_cny = self._optional_decimal(item.get("total_cost_cny"))
        fx_rate_to_cny = self._optional_decimal(item.get("exchange_rate_to_cny"))
        if total_cost_cny is None:
            total_cost_cny = quantity * unit_price * (fx_rate_to_cny or Decimal("1"))

        cash_entries: List[Dict[str, Any]] = []
        event_type = EventType.FX_BUY if direction == TransactionDirection.BUY else EventType.FX_SELL
        if direction == TransactionDirection.BUY:
            if trade_currency == "CNY":
                cash_entries.append(
                    {
                        "currency": "CNY",
                        "amount_delta": str(-total_cost_cny),
                        "rmb_amount": str(total_cost_cny),
                        "fx_rate_to_cny": "1",
                        "is_external_flow": True,
                        "description": f"External CNY paid to buy {asset_code}",
                    }
                )
                cash_entries.append(
                    {
                        "currency": asset_code,
                        "amount_delta": str(quantity),
                        "rmb_amount": str(total_cost_cny),
                        "fx_rate_to_cny": str(total_cost_cny / quantity) if quantity else None,
                        "is_external_flow": False,
                        "description": f"Bought {asset_code}",
                    }
                )
            else:
                event_type = EventType.FX_SWAP
                spent_amount = quantity * unit_price
                cash_entries.append(
                    {
                        "currency": trade_currency,
                        "amount_delta": str(-spent_amount),
                        "rmb_amount": str(total_cost_cny),
                        "fx_rate_to_cny": str(fx_rate_to_cny) if fx_rate_to_cny is not None else None,
                        "is_external_flow": False,
                        "description": f"Swapped out {trade_currency}",
                    }
                )
                cash_entries.append(
                    {
                        "currency": asset_code,
                        "amount_delta": str(quantity),
                        "rmb_amount": str(total_cost_cny),
                        "fx_rate_to_cny": str(total_cost_cny / quantity) if quantity else None,
                        "is_external_flow": False,
                        "description": f"Swapped into {asset_code}",
                    }
                )
        else:
            if trade_currency == "CNY":
                cash_entries.append(
                    {
                        "currency": asset_code,
                        "amount_delta": str(-quantity),
                        "rmb_amount": str(total_cost_cny),
                        "fx_rate_to_cny": str(total_cost_cny / quantity) if quantity else None,
                        "is_external_flow": False,
                        "description": f"Sold {asset_code}",
                    }
                )
                cash_entries.append(
                    {
                        "currency": "CNY",
                        "amount_delta": str(total_cost_cny),
                        "rmb_amount": str(total_cost_cny),
                        "fx_rate_to_cny": "1",
                        "is_external_flow": True,
                        "description": f"External CNY recovered from selling {asset_code}",
                    }
                )
            else:
                event_type = EventType.FX_SWAP
                received_amount = quantity * unit_price
                cash_entries.append(
                    {
                        "currency": asset_code,
                        "amount_delta": str(-quantity),
                        "rmb_amount": str(total_cost_cny),
                        "fx_rate_to_cny": str(total_cost_cny / quantity) if quantity else None,
                        "is_external_flow": False,
                        "description": f"Swapped out {asset_code}",
                    }
                )
                cash_entries.append(
                    {
                        "currency": trade_currency,
                        "amount_delta": str(received_amount),
                        "rmb_amount": str(total_cost_cny),
                        "fx_rate_to_cny": str(fx_rate_to_cny) if fx_rate_to_cny is not None else None,
                        "is_external_flow": False,
                        "description": f"Swapped into {trade_currency}",
                    }
                )

        PortfolioEventService(self.session).create_event(
            user_id=user_id,
            payload={
                "event_type": event_type.value,
                "event_time": item["trade_time"],
                "source": item.get("source", "manual"),
                "status": item.get("status", "CONFIRMED"),
                "raw_text": item.get("raw_text"),
                "notes": item.get("notes"),
                "cash_entries": cash_entries,
            },
            commit=False,
        )

    def _log_audit(
        self,
        *,
        user_id: int,
        entity_type: str,
        entity_id: str,
        action: str,
        status: str,
        details: Dict[str, Any],
    ) -> None:
        self.session.add(
            AuditLog(
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                status=status,
                details_json=details,
            )
        )
