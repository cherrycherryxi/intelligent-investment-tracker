"""Excel preview import service for forex transaction sheets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from investment_tracker.data.enums import AssetType, EventType, RecordStatus, TransactionDirection
from investment_tracker.data.models import PortfolioEvent, Transaction
from investment_tracker.data.repositories import TransactionRepository
from investment_tracker.data.services import PortfolioEventService
from investment_tracker.mcp_tools.exchange_rate_tool import ExchangeRateTool
from investment_tracker.utils.backup import BackupService
from investment_tracker.utils.xlsx_reader import WorkbookSheet, XlsxReader


@dataclass
class RowComputation:
    transaction: Optional[Dict[str, Any]]
    portfolio_event: Optional[Dict[str, Any]]
    warnings: List[str]
    errors: List[str]


class ExcelImportPreviewService:
    """Parse forex transaction workbooks and compute CNY equivalents."""

    REQUIRED_FOREX_HEADERS = {"交易ID", "交易时间", "卖出货币", "卖出金额", "买入货币", "买入金额"}

    def __init__(
        self,
        *,
        workbook_reader: Optional[XlsxReader] = None,
        exchange_rate_tool: Optional[ExchangeRateTool] = None,
    ) -> None:
        self.workbook_reader = workbook_reader or XlsxReader()
        self.exchange_rate_tool = exchange_rate_tool or ExchangeRateTool()

    def preview_forex_transactions(self, workbook_bytes: bytes, *, source_name: str = "uploaded.xlsx") -> Dict[str, Any]:
        sheets = self.workbook_reader.read(workbook_bytes)
        forex_sheet = self._find_sheet(sheets, "外汇交易记录") or self._find_sheet_by_headers(sheets)
        if forex_sheet is None:
            return {
                "source_name": source_name,
                "summary": {"total_rows": 0, "ready_count": 0, "pending_count": 0, "failed_count": 1},
                "ready_to_import": [],
                "pending_review": [],
                "failed": [{"row_number": 0, "errors": ["未找到工作表: 外汇交易记录"]}],
            }

        rows = self._sheet_to_dicts(forex_sheet)
        ready, pending, failed = [], [], []
        for row_number, row in rows:
            if self._is_empty_row(row):
                continue
            computation = self._build_row_preview(row_number=row_number, row=row)
            if computation.errors:
                failed.append(
                    {
                        "row_number": row_number,
                        "row": row,
                        "errors": computation.errors,
                        "warnings": computation.warnings,
                    }
                )
                continue

            result_row = {
                "row_number": row_number,
                "source_transaction_id": row.get("交易ID"),
                "warnings": computation.warnings,
                "transaction": computation.transaction,
                "portfolio_event": computation.portfolio_event,
            }
            if computation.warnings:
                pending.append(result_row)
            else:
                ready.append(result_row)

        return {
            "source_name": source_name,
            "summary": {
                "total_rows": len(rows),
                "ready_count": len(ready),
                "pending_count": len(pending),
                "failed_count": len(failed),
            },
            "ready_to_import": ready,
            "pending_review": pending,
            "failed": failed,
        }

    def import_forex_transactions(
        self,
        workbook_bytes: bytes,
        *,
        source_name: str,
        user_id: int,
        repository: TransactionRepository,
        include_pending: bool = False,
    ) -> Dict[str, Any]:
        preview = self.preview_forex_transactions(workbook_bytes, source_name=source_name)
        selected_rows = list(preview["ready_to_import"])
        if include_pending:
            selected_rows.extend(preview["pending_review"])

        # Preserve chronological import order across ready/pending buckets.
        selected_rows.sort(
            key=lambda item: (
                str((item.get("transaction") or item.get("portfolio_event") or {}).get("trade_time") or ""),
                str((item.get("portfolio_event") or {}).get("event_time") or ""),
                int(item.get("row_number") or 0),
            )
        )
        selected_transactions: List[Dict[str, Any]] = []
        selected_events: List[Dict[str, Any]] = []
        skipped_duplicate_count = 0
        seen_transaction_keys: set[Tuple[Any, ...]] = set()
        seen_event_keys: set[Tuple[Any, ...]] = set()
        for item in selected_rows:
            transaction = item.get("transaction")
            if transaction:
                key = self._transaction_duplicate_key(user_id=user_id, payload=transaction)
                if key in seen_transaction_keys or self._transaction_exists(user_id=user_id, payload=transaction, key=key, repository=repository):
                    skipped_duplicate_count += 1
                    continue
                seen_transaction_keys.add(key)
                selected_transactions.append(transaction)
                continue

            event = item.get("portfolio_event")
            if event:
                key = self._event_duplicate_key(user_id=user_id, payload=event)
                if key in seen_event_keys or self._event_exists(user_id=user_id, payload=event, key=key, repository=repository):
                    skipped_duplicate_count += 1
                    continue
                seen_event_keys.add(key)
                selected_events.append(event)

        created = repository.create_transactions(user_id=user_id, transactions=selected_transactions) if selected_transactions else []
        created_events = []
        if selected_events:
            repository.ensure_user(user_id)
            event_service = PortfolioEventService(repository.session)
            for event_payload in selected_events:
                created_events.append(event_service.create_event(user_id=user_id, payload=event_payload, commit=False))
            repository.session.commit()
            BackupService(repository.session).create_backup(reason="portfolio_events_imported")
            for event in created_events:
                repository.session.refresh(event)

        return {
            "source_name": source_name,
            "imported_count": len(created),
            "imported_event_count": len(created_events),
            "skipped_pending_count": 0 if include_pending else len(preview["pending_review"]),
            "skipped_duplicate_count": skipped_duplicate_count,
            "failed_count": len(preview["failed"]),
            "created_transaction_ids": [transaction.id for transaction in created],
            "created_event_ids": [event.id for event in created_events],
            "preview_summary": preview["summary"],
        }

    def _transaction_duplicate_key(self, *, user_id: int, payload: Dict[str, Any]) -> Tuple[Any, ...]:
        return (
            user_id,
            str(payload.get("asset_type") or "").upper(),
            str(payload.get("asset_code") or "").upper(),
            str(payload.get("direction") or "").upper(),
            self._datetime_key(payload.get("trade_time")),
            self._decimal_key(payload.get("quantity")),
            self._decimal_key(payload.get("unit_price")),
            str(payload.get("trade_currency") or "").upper(),
            self._decimal_key(payload.get("total_cost_cny")),
        )

    def _transaction_exists(
        self,
        *,
        user_id: int,
        payload: Dict[str, Any],
        key: Tuple[Any, ...],
        repository: TransactionRepository,
    ) -> bool:
        candidates = (
            repository.session.query(Transaction)
            .filter(
                Transaction.user_id == user_id,
                Transaction.asset_code == str(payload.get("asset_code") or "").upper(),
            )
            .all()
        )
        return any(self._transaction_duplicate_key(user_id=user_id, payload=self._transaction_payload_from_model(row)) == key for row in candidates)

    def _transaction_payload_from_model(self, row: Transaction) -> Dict[str, Any]:
        return {
            "asset_type": row.asset_type.value,
            "asset_code": row.asset_code,
            "direction": row.direction.value,
            "quantity": row.quantity,
            "unit_price": row.unit_price,
            "trade_currency": row.trade_currency,
            "trade_time": row.trade_time,
            "total_cost_cny": row.total_cost_cny,
        }

    def _event_duplicate_key(self, *, user_id: int, payload: Dict[str, Any]) -> Tuple[Any, ...]:
        cash_entries = tuple(
            sorted(
                (
                    str(item.get("currency") or "").upper(),
                    self._decimal_key(item.get("amount_delta")),
                    bool(item.get("is_external_flow", False)),
                    self._decimal_key(item.get("rmb_amount")),
                )
                for item in payload.get("cash_entries", [])
            )
        )
        asset_entries = tuple(
            sorted(
                (
                    str((item.get("asset") or {}).get("asset_type") or item.get("asset_type") or "").upper(),
                    str((item.get("asset") or {}).get("asset_code") or item.get("asset_code") or item.get("asset_id") or "").upper(),
                    str((item.get("asset") or {}).get("currency") or item.get("currency") or item.get("cash_currency") or "").upper(),
                    self._decimal_key(item.get("quantity_delta")),
                    str(item.get("cash_currency") or "").upper(),
                    self._decimal_key(item.get("cash_amount")),
                    self._decimal_key(item.get("unit_price")),
                )
                for item in payload.get("asset_entries", [])
            )
        )
        return (
            user_id,
            str(payload.get("event_type") or "").upper(),
            self._datetime_key(payload.get("event_time")),
            cash_entries,
            asset_entries,
        )

    def _event_exists(
        self,
        *,
        user_id: int,
        payload: Dict[str, Any],
        key: Tuple[Any, ...],
        repository: TransactionRepository,
    ) -> bool:
        candidates = (
            repository.session.query(PortfolioEvent)
            .filter(
                PortfolioEvent.user_id == user_id,
                PortfolioEvent.event_type == EventType[str(payload.get("event_type"))],
            )
            .all()
        )
        return any(self._event_duplicate_key(user_id=user_id, payload=self._event_payload_from_model(row)) == key for row in candidates)

    def _event_payload_from_model(self, row: PortfolioEvent) -> Dict[str, Any]:
        return {
            "event_type": row.event_type.value,
            "event_time": row.event_time,
            "cash_entries": [
                {
                    "currency": item.currency,
                    "amount_delta": item.amount_delta,
                    "rmb_amount": item.rmb_amount,
                    "is_external_flow": item.is_external_flow,
                }
                for item in row.cash_ledger_entries
            ],
            "asset_entries": [
                {
                    "asset": {
                        "asset_type": item.asset.asset_type.value if item.asset else "",
                        "asset_code": item.asset.asset_code if item.asset else str(item.asset_id),
                        "currency": item.asset.currency if item.asset else item.cash_currency,
                    },
                    "quantity_delta": item.quantity_delta,
                    "cash_currency": item.cash_currency,
                    "cash_amount": item.cash_amount,
                    "unit_price": item.unit_price,
                }
                for item in row.asset_ledger_entries
            ],
        }

    def _datetime_key(self, value: Any) -> str:
        parsed = self._parse_trade_time(value)
        if parsed is None:
            return ""
        return parsed.replace(tzinfo=None).isoformat(timespec="seconds")

    def _decimal_key(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        return str(Decimal(str(value)).quantize(Decimal("0.000001")).normalize())

    def _find_sheet(self, sheets: List[WorkbookSheet], target_name: str) -> Optional[WorkbookSheet]:
        for sheet in sheets:
            if sheet.name == target_name:
                return sheet
        return None

    def _find_sheet_by_headers(self, sheets: List[WorkbookSheet]) -> Optional[WorkbookSheet]:
        for sheet in sheets:
            if not sheet.rows:
                continue
            headers = {str(cell).strip() for cell in sheet.rows[0] if cell not in (None, "")}
            if self.REQUIRED_FOREX_HEADERS.issubset(headers):
                return sheet
        return None

    def _sheet_to_dicts(self, sheet: WorkbookSheet) -> List[Tuple[int, Dict[str, Any]]]:
        if not sheet.rows:
            return []
        headers = [str(cell).strip() if cell is not None else "" for cell in sheet.rows[0]]
        rows: List[Tuple[int, Dict[str, Any]]] = []
        for index, values in enumerate(sheet.rows[1:], start=2):
            row_dict: Dict[str, Any] = {}
            for position, header in enumerate(headers):
                if not header:
                    continue
                row_dict[header] = values[position] if position < len(values) else None
            rows.append((index, row_dict))
        return rows

    def _is_empty_row(self, row: Dict[str, Any]) -> bool:
        return not any(value not in (None, "") for value in row.values())

    def _build_row_preview(self, *, row_number: int, row: Dict[str, Any]) -> RowComputation:
        category = str(row.get("类别") or "").strip()
        if category == "外汇" or (not category and ("卖出货币" in row or "买入货币" in row)):
            return self._build_forex_transaction_preview(row_number=row_number, row=row)
        if category == "基金":
            return self._build_asset_event_preview(row=row, asset_type=AssetType.FUND)
        if category == "理财":
            return self._build_asset_event_preview(row=row, asset_type=AssetType.WEALTH_PRODUCT)
        if category == "结息":
            return self._build_cash_income_event_preview(row=row, event_type=EventType.INTEREST_INCOME)
        if category == "定期":
            return self._build_cash_income_event_preview(row=row, event_type=EventType.WEALTH_INCOME)
        return RowComputation(transaction=None, portfolio_event=None, warnings=[], errors=[f"不支持的交易类别: {category or '空'}"])

    def _build_forex_transaction_preview(self, *, row_number: int, row: Dict[str, Any]) -> RowComputation:
        warnings: List[str] = []
        errors: List[str] = []

        trade_time = self._parse_trade_time(row.get("交易时间"))
        if trade_time is None:
            errors.append("交易时间无法解析")

        sell_currency = self._normalize_currency(row.get("卖出货币"))
        buy_currency = self._normalize_currency(row.get("买入货币"))
        sell_amount = self._to_float(row.get("卖出金额"))
        buy_amount = self._to_float(row.get("买入金额"))
        note = str(row.get("备注") or "")

        transaction = {
            "asset_type": AssetType.FOREX.value,
            "asset_code": None,
            "asset_name": None,
            "direction": None,
            "quantity": None,
            "unit_price": None,
            "trade_currency": None,
            "trade_time": trade_time.isoformat() if trade_time else None,
            "exchange_rate_to_cny": None,
            "total_cost_cny": None,
            "source": "excel_import",
            "status": RecordStatus.CONFIRMED.value,
            "raw_text": note,
            "notes": note,
        }

        mode = self._detect_transaction_mode(sell_currency=sell_currency, buy_currency=buy_currency)
        if mode is None:
            errors.append("无法从买入/卖出货币判断交易方向")
            return RowComputation(transaction=transaction, portfolio_event=None, warnings=warnings, errors=errors)

        if mode == "buy_non_cny":
            if not buy_currency or buy_amount in (None, 0):
                errors.append("买入货币或买入金额缺失")
                return RowComputation(transaction=transaction, portfolio_event=None, warnings=warnings, errors=errors)
            transaction["asset_code"] = buy_currency
            transaction["asset_name"] = buy_currency
            transaction["direction"] = TransactionDirection.BUY.value
            transaction["quantity"] = buy_amount

            if sell_currency == "CNY":
                if sell_amount is None:
                    warnings.append("源表缺少 CNY 卖出金额，已用历史汇率估算")
                    cny_rate = self._lookup_rate(base_currency=buy_currency, timestamp=trade_time, warnings=warnings, errors=errors)
                    if cny_rate is not None:
                        transaction["unit_price"] = cny_rate
                        transaction["trade_currency"] = "CNY"
                        transaction["exchange_rate_to_cny"] = 1.0
                        transaction["total_cost_cny"] = round(buy_amount * cny_rate, 2)
                else:
                    transaction["unit_price"] = round(sell_amount / buy_amount, 6)
                    transaction["trade_currency"] = "CNY"
                    transaction["exchange_rate_to_cny"] = 1.0
                    transaction["total_cost_cny"] = round(sell_amount, 2)
            else:
                if sell_currency is None or sell_amount is None:
                    errors.append("跨币种买入缺少卖出货币或卖出金额")
                    return RowComputation(transaction=transaction, portfolio_event=None, warnings=warnings, errors=errors)
                event = self._build_fx_swap_event(
                    trade_time=trade_time,
                    row=row,
                    sell_currency=sell_currency,
                    sell_amount=sell_amount,
                    buy_currency=buy_currency,
                    buy_amount=buy_amount,
                )
                return RowComputation(transaction=None, portfolio_event=event, warnings=warnings, errors=errors)

        if mode == "sell_non_cny":
            if not sell_currency or sell_amount in (None, 0):
                errors.append("卖出货币或卖出金额缺失")
                return RowComputation(transaction=transaction, portfolio_event=None, warnings=warnings, errors=errors)
            transaction["asset_code"] = sell_currency
            transaction["asset_name"] = sell_currency
            transaction["direction"] = TransactionDirection.SELL.value
            transaction["quantity"] = sell_amount

            if buy_currency == "CNY":
                if buy_amount is not None:
                    transaction["unit_price"] = round(buy_amount / sell_amount, 6)
                    transaction["trade_currency"] = "CNY"
                    transaction["exchange_rate_to_cny"] = 1.0
                    transaction["total_cost_cny"] = round(buy_amount, 2)
                else:
                    cny_rate = self._lookup_rate(base_currency=sell_currency, timestamp=trade_time, warnings=warnings, errors=errors)
                    if cny_rate is not None:
                        transaction["unit_price"] = cny_rate
                        transaction["trade_currency"] = "CNY"
                        transaction["exchange_rate_to_cny"] = 1.0
                        transaction["total_cost_cny"] = round(sell_amount * cny_rate, 2)
                        warnings.append("源表缺少 CNY 买入金额，已用历史汇率估算")
            else:
                if buy_currency is None or buy_amount is None:
                    errors.append("跨币种卖出缺少买入货币或买入金额")
                    return RowComputation(transaction=transaction, portfolio_event=None, warnings=warnings, errors=errors)
                event = self._build_fx_swap_event(
                    trade_time=trade_time,
                    row=row,
                    sell_currency=sell_currency,
                    sell_amount=sell_amount,
                    buy_currency=buy_currency,
                    buy_amount=buy_amount,
                )
                return RowComputation(transaction=None, portfolio_event=event, warnings=warnings, errors=errors)

        required_fields = ["asset_code", "direction", "quantity", "unit_price", "trade_currency", "total_cost_cny"]
        for field_name in required_fields:
            if transaction[field_name] in (None, ""):
                errors.append(f"缺少必要字段: {field_name}")

        if warnings:
            transaction["status"] = RecordStatus.PENDING.value
        return RowComputation(transaction=transaction, portfolio_event=None, warnings=warnings, errors=errors)

    def _build_fx_swap_event(
        self,
        *,
        trade_time: Optional[datetime],
        row: Dict[str, Any],
        sell_currency: str,
        sell_amount: float,
        buy_currency: str,
        buy_amount: float,
    ) -> Dict[str, Any]:
        note = str(row.get("备注") or "")
        buy_per_sell = round(buy_amount / sell_amount, 8) if sell_amount else None
        sell_per_buy = round(sell_amount / buy_amount, 8) if buy_amount else None
        return self._event_payload(
            event_type=EventType.FX_SWAP,
            trade_time=trade_time,
            row=row,
            cash_entries=[
                {
                    "currency": sell_currency,
                    "amount_delta": -sell_amount,
                    "rmb_amount": None,
                    "fx_rate_to_cny": None,
                    "is_external_flow": False,
                    "description": f"FX swap out; {buy_currency}/{sell_currency}={buy_per_sell}",
                },
                {
                    "currency": buy_currency,
                    "amount_delta": buy_amount,
                    "rmb_amount": None,
                    "fx_rate_to_cny": None,
                    "is_external_flow": False,
                    "description": f"FX swap in; {sell_currency}/{buy_currency}={sell_per_buy}",
                },
            ],
            asset_entries=[],
        ) | {"notes": note}

    def _build_asset_event_preview(self, *, row: Dict[str, Any], asset_type: AssetType) -> RowComputation:
        warnings: List[str] = []
        errors: List[str] = []
        trade_time = self._parse_trade_time(row.get("交易时间"))
        if trade_time is None:
            errors.append("交易时间无法解析")

        sell_currency = self._normalize_currency(row.get("卖出货币"))
        buy_currency = self._normalize_currency(row.get("买入货币"))
        sell_amount = self._to_float(row.get("卖出金额"))
        buy_amount = self._to_float(row.get("买入金额"))
        name = str(row.get("名称") or asset_type.value)
        note = str(row.get("备注") or "")
        asset = self._asset_payload(asset_type=asset_type, name=name, currency=sell_currency or buy_currency)

        if sell_currency and sell_amount not in (None, 0):
            event_type = EventType.FUND_BUY if asset_type == AssetType.FUND else EventType.WEALTH_BUY
            event = self._event_payload(
                event_type=event_type,
                trade_time=trade_time,
                row=row,
                cash_entries=[
                    {
                        "currency": sell_currency,
                        "amount_delta": -sell_amount,
                        "rmb_amount": None,
                        "fx_rate_to_cny": None,
                        "is_external_flow": False,
                        "description": f"{asset_type.value} purchase cash outflow",
                    }
                ],
                asset_entries=[
                    {
                        "asset": asset,
                        "quantity_delta": sell_amount,
                        "cash_currency": sell_currency,
                        "cash_amount": sell_amount,
                        "unit_price": 1,
                        "fx_rate_to_cny": None,
                        "description": note or f"{asset_type.value} purchase",
                    }
                ],
            )
            return RowComputation(transaction=None, portfolio_event=event, warnings=warnings, errors=errors)

        if buy_currency and buy_amount not in (None, 0):
            if asset_type == AssetType.FUND and "分红" in note:
                event_type = EventType.FUND_DIVIDEND
                asset_entries: List[Dict[str, Any]] = []
            else:
                event_type = EventType.FUND_SELL if asset_type == AssetType.FUND else EventType.WEALTH_REDEEM
                asset_entries = [
                    {
                        "asset": asset,
                        "quantity_delta": -buy_amount,
                        "cash_currency": buy_currency,
                        "cash_amount": buy_amount,
                        "unit_price": 1,
                        "fx_rate_to_cny": None,
                        "description": note or f"{asset_type.value} redemption",
                    }
                ]
            event = self._event_payload(
                event_type=event_type,
                trade_time=trade_time,
                row=row,
                cash_entries=[
                    {
                        "currency": buy_currency,
                        "amount_delta": buy_amount,
                        "rmb_amount": None,
                        "fx_rate_to_cny": None,
                        "is_external_flow": False,
                        "description": note or f"{asset_type.value} cash inflow",
                    }
                ],
                asset_entries=asset_entries,
            )
            return RowComputation(transaction=None, portfolio_event=event, warnings=warnings, errors=errors)

        errors.append(f"{asset_type.value} 记录缺少可用的现金流金额")
        return RowComputation(transaction=None, portfolio_event=None, warnings=warnings, errors=errors)

    def _build_cash_income_event_preview(self, *, row: Dict[str, Any], event_type: EventType) -> RowComputation:
        warnings: List[str] = []
        errors: List[str] = []
        trade_time = self._parse_trade_time(row.get("交易时间"))
        if trade_time is None:
            errors.append("交易时间无法解析")
        buy_currency = self._normalize_currency(row.get("买入货币"))
        buy_amount = self._to_float(row.get("买入金额"))
        if not buy_currency or buy_amount in (None, 0):
            errors.append("现金收入记录缺少买入货币或买入金额")
            return RowComputation(transaction=None, portfolio_event=None, warnings=warnings, errors=errors)
        event = self._event_payload(
            event_type=event_type,
            trade_time=trade_time,
            row=row,
            cash_entries=[
                {
                    "currency": buy_currency,
                    "amount_delta": buy_amount,
                    "rmb_amount": None,
                    "fx_rate_to_cny": None,
                    "is_external_flow": False,
                    "description": str(row.get("备注") or row.get("名称") or "cash income"),
                }
            ],
            asset_entries=[],
        )
        return RowComputation(transaction=None, portfolio_event=event, warnings=warnings, errors=errors)

    def _event_payload(
        self,
        *,
        event_type: EventType,
        trade_time: Optional[datetime],
        row: Dict[str, Any],
        cash_entries: List[Dict[str, Any]],
        asset_entries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "event_type": event_type.value,
            "event_time": trade_time.isoformat() if trade_time else None,
            "source": "excel_import",
            "status": RecordStatus.CONFIRMED.value,
            "raw_text": str(row),
            "notes": str(row.get("备注") or ""),
            "cash_entries": cash_entries,
            "asset_entries": asset_entries,
        }

    def _asset_payload(self, *, asset_type: AssetType, name: str, currency: Optional[str]) -> Dict[str, Any]:
        normalized_currency = currency or "UNKNOWN"
        digest = hashlib.sha1(f"{asset_type.value}|{normalized_currency}|{name}".encode("utf-8")).hexdigest()[:12]
        return {
            "asset_type": asset_type.value,
            "asset_code": f"{asset_type.value[:4]}-{digest}",
            "asset_name": name,
            "currency": normalized_currency,
            "metadata_json": {"source_name": name},
        }

    def _detect_transaction_mode(self, *, sell_currency: Optional[str], buy_currency: Optional[str]) -> Optional[str]:
        if buy_currency and buy_currency != "CNY":
            return "buy_non_cny"
        if sell_currency and sell_currency != "CNY":
            return "sell_non_cny"
        return None

    def _lookup_rate(
        self,
        *,
        base_currency: str,
        timestamp: Optional[datetime],
        warnings: List[str],
        errors: List[str],
    ) -> Optional[float]:
        if timestamp is None:
            errors.append("缺少交易时间，无法补历史汇率")
            return None

        response = self.exchange_rate_tool.execute(
            {
                "base_currency": base_currency,
                "quote_currency": "CNY",
                "timestamp": timestamp.isoformat(),
            }
        )
        if not response["ok"]:
            errors.append(f"历史汇率查询失败: {base_currency}/CNY")
            return None

        result = response["result"]
        if result["is_estimated"]:
            warnings.append(f"{base_currency}/CNY 历史汇率使用估算值")
        return float(result["rate"])

    def _normalize_currency(self, value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        return str(value).strip().upper()

    def _parse_trade_time(self, value: Any) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime(1899, 12, 30) + timedelta(days=float(value))
        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        return None

    def _to_float(self, value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
