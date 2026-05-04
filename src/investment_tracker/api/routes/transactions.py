"""Transaction-related API routes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.orm import selectinload

from investment_tracker.api.schemas import ScreenshotUploadRequest, TransactionCreateRequest, TransactionHistoryUpdateRequest
from investment_tracker.data.db import get_db_session
from investment_tracker.data.enums import AssetType, EventType, TransactionDirection
from investment_tracker.data.models import AssetLedgerEntry, CashLedgerEntry, PortfolioEvent, Transaction
from investment_tracker.data.repositories import TransactionRepository
from investment_tracker.mcp_tools.exchange_rate_tool import ExchangeRateTool
from investment_tracker.orchestration.excel_import_service import ExcelImportPreviewService
from investment_tracker.orchestration.screenshot_import_service import ScreenshotImportService


router = APIRouter(prefix="/api/transactions", tags=["transactions"])

LEGACY_EVENT_TYPES = {EventType.FX_BUY, EventType.FX_SELL}


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _signed_transaction_cost(row: Transaction) -> Optional[float]:
    if row.total_cost_cny is None:
        return None
    value = Decimal(str(row.total_cost_cny))
    if row.direction == TransactionDirection.SELL:
        value = -abs(value)
    return float(value)


def _transaction_history_row(row: Transaction) -> Dict[str, Any]:
    native_amount = Decimal(str(row.quantity)) * Decimal(str(row.unit_price))
    signed_native_amount = -abs(native_amount) if row.direction == TransactionDirection.SELL else native_amount
    return {
        "id": row.id,
        "record_type": "TRANSACTION",
        "user_id": row.user_id,
        "asset_type": row.asset_type.value,
        "asset_code": row.asset_code,
        "asset_name": row.asset_name,
        "direction": row.direction.value,
        "quantity": float(row.quantity),
        "unit_price": float(row.unit_price),
        "trade_currency": row.trade_currency,
        "trade_time": row.trade_time.isoformat(),
        "exchange_rate_to_cny": _float_or_none(row.exchange_rate_to_cny),
        "total_cost_cny": _float_or_none(row.total_cost_cny),
        "signed_total_cost_cny": _signed_transaction_cost(row),
        "trade_amount": float(native_amount),
        "signed_trade_amount": float(signed_native_amount),
        "trade_amount_currency": row.trade_currency,
        "status": row.status.value,
        "source": row.source,
        "notes": row.notes,
        "search_text": " ".join(
            item
            for item in [
                row.asset_type.value,
                row.asset_code,
                row.asset_name or "",
                row.trade_currency,
                row.direction.value,
                row.notes or "",
            ]
            if item
        ),
    }


def _event_direction(event_type: EventType) -> str:
    if event_type in {EventType.FX_SWAP}:
        return "SWAP"
    if event_type in {EventType.BOND_BUY, EventType.FUND_BUY, EventType.WEALTH_BUY}:
        return "BUY"
    if event_type in {EventType.BOND_SELL, EventType.BOND_REDEMPTION, EventType.FUND_SELL, EventType.WEALTH_REDEEM}:
        return "SELL"
    if event_type in {EventType.INTEREST_INCOME, EventType.FUND_DIVIDEND, EventType.WEALTH_INCOME}:
        return "INCOME"
    if event_type == EventType.FUND_DIVIDEND_REINVEST:
        return "REINVEST"
    return event_type.value


def _event_asset_type(event: PortfolioEvent) -> str:
    asset_entry = next(iter(event.asset_ledger_entries), None)
    if asset_entry is not None and asset_entry.asset is not None:
        return asset_entry.asset.asset_type.value
    if event.event_type in {EventType.FX_SWAP}:
        return AssetType.FOREX.value
    if event.event_type == EventType.INTEREST_INCOME:
        return AssetType.CASH.value
    return AssetType.CASH.value


def _event_asset_code(event: PortfolioEvent) -> str:
    asset_entry = next(iter(event.asset_ledger_entries), None)
    if asset_entry is not None and asset_entry.asset is not None:
        return asset_entry.asset.asset_code

    negative = [item for item in event.cash_ledger_entries if Decimal(str(item.amount_delta)) < 0]
    positive = [item for item in event.cash_ledger_entries if Decimal(str(item.amount_delta)) > 0]
    if event.event_type == EventType.FX_SWAP and negative and positive:
        return f"{negative[0].currency}->{positive[0].currency}"
    if positive:
        return positive[0].currency
    if negative:
        return negative[0].currency
    return event.event_type.value


def _event_quantity(event: PortfolioEvent) -> float:
    asset_entry = next(iter(event.asset_ledger_entries), None)
    if asset_entry is not None:
        return float(abs(Decimal(str(asset_entry.quantity_delta))))
    positive = [item for item in event.cash_ledger_entries if Decimal(str(item.amount_delta)) > 0]
    if positive:
        return float(positive[0].amount_delta)
    first = next(iter(event.cash_ledger_entries), None)
    return float(abs(Decimal(str(first.amount_delta)))) if first is not None else 0.0


def _event_unit_price(event: PortfolioEvent) -> Optional[float]:
    asset_entry = next(iter(event.asset_ledger_entries), None)
    if asset_entry is not None:
        return _float_or_none(asset_entry.unit_price)
    negative = [item for item in event.cash_ledger_entries if Decimal(str(item.amount_delta)) < 0]
    positive = [item for item in event.cash_ledger_entries if Decimal(str(item.amount_delta)) > 0]
    if event.event_type == EventType.FX_SWAP and negative and positive:
        sold = abs(Decimal(str(negative[0].amount_delta)))
        bought = Decimal(str(positive[0].amount_delta))
        if sold:
            return float(bought / sold)
    return None


def _event_trade_currency(event: PortfolioEvent) -> str:
    asset_entry = next(iter(event.asset_ledger_entries), None)
    if asset_entry is not None:
        return asset_entry.cash_currency
    positive = [item for item in event.cash_ledger_entries if Decimal(str(item.amount_delta)) > 0]
    if positive:
        return positive[0].currency
    first = next(iter(event.cash_ledger_entries), None)
    return first.currency if first is not None else "CNY"


def _event_signed_cost(event: PortfolioEvent) -> Optional[float]:
    values = [
        Decimal(str(item.rmb_amount))
        for item in event.cash_ledger_entries
        if item.rmb_amount is not None and item.is_external_flow
    ]
    if not values:
        values = [
            Decimal(str(item.rmb_amount))
            for item in event.cash_ledger_entries
            if item.rmb_amount is not None
        ]
    if not values:
        return None
    total = sum(values, Decimal("0"))
    direction = _event_direction(event.event_type)
    if direction in {"SELL", "INCOME"}:
        total = -abs(total)
    return float(total)


def _event_native_amount(event: PortfolioEvent) -> tuple[Optional[float], Optional[float], Optional[str]]:
    asset_entry = next(iter(event.asset_ledger_entries), None)
    if asset_entry is not None and asset_entry.cash_amount is not None:
        amount = abs(Decimal(str(asset_entry.cash_amount)))
        currency = asset_entry.cash_currency
    else:
        cash_entries = list(event.cash_ledger_entries)
        if not cash_entries:
            return None, None, None
        if event.event_type == EventType.FX_SWAP:
            spent = next((item for item in cash_entries if Decimal(str(item.amount_delta)) < 0), None)
            if spent is not None:
                amount = abs(Decimal(str(spent.amount_delta)))
                return float(amount), float(amount), spent.currency
        preferred = next((item for item in cash_entries if Decimal(str(item.amount_delta)) > 0), cash_entries[0])
        amount = abs(Decimal(str(preferred.amount_delta)))
        currency = preferred.currency

    signed_amount = amount
    if _event_direction(event.event_type) in {"SELL", "INCOME"}:
        signed_amount = -abs(amount)
    return float(amount), float(signed_amount), currency


def _event_history_row(event: PortfolioEvent) -> Dict[str, Any]:
    asset_entry = next(iter(event.asset_ledger_entries), None)
    asset_name = asset_entry.asset.asset_name if asset_entry is not None and asset_entry.asset is not None else None
    signed_cost = _event_signed_cost(event)
    native_amount, signed_native_amount, native_currency = _event_native_amount(event)
    search_parts = [
        event.event_type.value,
        _event_asset_type(event),
        _event_asset_code(event),
        asset_name or "",
        _event_trade_currency(event),
        event.notes or "",
        event.raw_text or "",
    ]
    search_parts.extend(item.currency for item in event.cash_ledger_entries)
    return {
        "id": event.id,
        "record_type": "EVENT",
        "event_type": event.event_type.value,
        "user_id": event.user_id,
        "asset_type": _event_asset_type(event),
        "asset_code": _event_asset_code(event),
        "asset_name": asset_name,
        "direction": _event_direction(event.event_type),
        "quantity": _event_quantity(event),
        "unit_price": _event_unit_price(event),
        "trade_currency": _event_trade_currency(event),
        "trade_time": event.event_time.isoformat(),
        "exchange_rate_to_cny": _event_rate_to_cny(event),
        "total_cost_cny": abs(signed_cost) if signed_cost is not None else None,
        "signed_total_cost_cny": signed_cost,
        "trade_amount": native_amount,
        "signed_trade_amount": signed_native_amount,
        "trade_amount_currency": native_currency,
        "status": event.status.value,
        "source": event.source,
        "notes": event.notes,
        "search_text": " ".join(item for item in search_parts if item),
    }


def _event_rate_to_cny(event: PortfolioEvent) -> Optional[float]:
    asset_entry = next(iter(event.asset_ledger_entries), None)
    if asset_entry is not None and asset_entry.fx_rate_to_cny is not None:
        return float(asset_entry.fx_rate_to_cny)
    values = [
        Decimal(str(item.fx_rate_to_cny))
        for item in event.cash_ledger_entries
        if item.fx_rate_to_cny is not None and item.currency != "CNY"
    ]
    if not values:
        return None
    return float(values[0])


def _matches_history_filters(row: Dict[str, Any], *, asset_code: Optional[str], direction: Optional[str]) -> bool:
    if asset_code:
        needle = asset_code.strip().upper()
        if needle and needle not in str(row.get("search_text", "")).upper():
            return False
    if direction:
        if row.get("direction") != direction.strip().upper():
            return False
    return True


@router.post("/upload")
async def upload_transaction_screenshots(payload: ScreenshotUploadRequest) -> dict:
    service = ScreenshotImportService()
    return service.preview_batch([item.model_dump() for item in payload.files])


@router.post("")
async def create_transaction(payload: TransactionCreateRequest) -> dict:
    with get_db_session() as session:
        repository = TransactionRepository(session)
        created = repository.create_transactions(
            user_id=payload.user_id,
            transactions=[payload.model_dump(mode="json")],
        )

    row = created[0]
    return {
        "transaction": {
            "id": row.id,
            "user_id": row.user_id,
            "asset_type": row.asset_type.value,
            "asset_code": row.asset_code,
            "direction": row.direction.value,
            "quantity": float(row.quantity),
            "unit_price": float(row.unit_price),
            "trade_currency": row.trade_currency,
            "trade_time": row.trade_time.isoformat(),
            "total_cost_cny": float(row.total_cost_cny) if row.total_cost_cny is not None else None,
            "status": row.status.value,
        }
    }


@router.get("")
async def list_transactions(
    user_id: int = 1,
    asset_code: Optional[str] = None,
    direction: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
) -> dict:
    with get_db_session() as session:
        start_dt = _parse_time(start_time)
        end_dt = _parse_time(end_time)

        transaction_query = session.query(Transaction).filter(Transaction.user_id == user_id)
        if start_dt is not None:
            transaction_query = transaction_query.filter(Transaction.trade_time >= start_dt)
        if end_dt is not None:
            transaction_query = transaction_query.filter(Transaction.trade_time <= end_dt)
        transaction_rows = transaction_query.order_by(Transaction.trade_time.desc(), Transaction.id.desc()).limit(limit * 2).all()

        event_query = session.query(PortfolioEvent).filter(
            PortfolioEvent.user_id == user_id,
            PortfolioEvent.event_type.notin_(LEGACY_EVENT_TYPES),
        ).options(
            selectinload(PortfolioEvent.cash_ledger_entries),
            selectinload(PortfolioEvent.asset_ledger_entries).selectinload(AssetLedgerEntry.asset),
        )
        if start_dt is not None:
            event_query = event_query.filter(PortfolioEvent.event_time >= start_dt)
        if end_dt is not None:
            event_query = event_query.filter(PortfolioEvent.event_time <= end_dt)
        event_rows = event_query.order_by(PortfolioEvent.event_time.desc(), PortfolioEvent.id.desc()).limit(limit * 2).all()

        history_rows: List[Dict[str, Any]] = [
            *[_transaction_history_row(row) for row in transaction_rows],
            *[_event_history_row(event) for event in event_rows],
        ]
        history_rows = [
            row for row in history_rows if _matches_history_filters(row, asset_code=asset_code, direction=direction)
        ]
        history_rows.sort(key=lambda row: (row["trade_time"], row["id"]), reverse=True)
        history_rows = history_rows[:limit]
        for row in history_rows:
            row.pop("search_text", None)

    return {
        "transactions": history_rows
    }


@router.patch("/{record_type}/{record_id}")
async def update_transaction_history_record(record_type: str, record_id: int, payload: TransactionHistoryUpdateRequest) -> dict:
    normalized_type = record_type.upper()
    with get_db_session() as session:
        if normalized_type == "EVENT":
            row = session.get(PortfolioEvent, record_id)
            if row is None:
                raise HTTPException(status_code=404, detail="event not found")
            if payload.trade_time is not None:
                row.event_time = payload.trade_time
            if payload.notes is not None:
                row.notes = payload.notes
            session.commit()
            session.refresh(row)
            return {"record": _event_history_row(row)}

        if normalized_type == "TRANSACTION":
            row = session.get(Transaction, record_id)
            if row is None:
                raise HTTPException(status_code=404, detail="transaction not found")
            if payload.trade_time is not None:
                row.trade_time = payload.trade_time
            if payload.notes is not None:
                row.notes = payload.notes
            session.commit()
            session.refresh(row)
            return {"record": _transaction_history_row(row)}

    raise HTTPException(status_code=400, detail="record_type must be EVENT or TRANSACTION")


@router.delete("/{record_type}/{record_id}")
async def delete_transaction_history_record(record_type: str, record_id: int) -> dict:
    normalized_type = record_type.upper()
    with get_db_session() as session:
        if normalized_type == "EVENT":
            row = session.get(PortfolioEvent, record_id)
            if row is None:
                raise HTTPException(status_code=404, detail="event not found")
            session.query(CashLedgerEntry).filter(CashLedgerEntry.event_id == record_id).delete()
            session.query(AssetLedgerEntry).filter(AssetLedgerEntry.event_id == record_id).delete()
            session.delete(row)
            session.commit()
            return {"deleted": True, "record_type": "EVENT", "id": record_id}

        if normalized_type == "TRANSACTION":
            row = session.get(Transaction, record_id)
            if row is None:
                raise HTTPException(status_code=404, detail="transaction not found")
            session.delete(row)
            session.commit()
            return {"deleted": True, "record_type": "TRANSACTION", "id": record_id}

    raise HTTPException(status_code=400, detail="record_type must be EVENT or TRANSACTION")


@router.post("/{record_type}/{record_id}/historical-rate")
async def update_historical_rate(record_type: str, record_id: int) -> dict:
    normalized_type = record_type.upper()
    tool = ExchangeRateTool()
    with get_db_session() as session:
        if normalized_type == "TRANSACTION":
            row = session.get(Transaction, record_id)
            if row is None:
                raise HTTPException(status_code=404, detail="transaction not found")
            if row.trade_currency.upper() != "CNY":
                raise HTTPException(status_code=400, detail="only CNY-denominated FX transactions are supported")
            response = tool.execute(
                {
                    "base_currency": row.asset_code,
                    "quote_currency": "CNY",
                    "timestamp": row.trade_time.isoformat(),
                }
            )
            if not response["ok"]:
                raise HTTPException(status_code=502, detail=response.get("error", {}).get("message", "historical rate query failed"))
            result = response["result"]
            if result["is_estimated"] or result.get("source") != "PRIMARY":
                raise HTTPException(status_code=409, detail="只查到估算或兜底汇率，未写入。请手动填写真实成交金额。")

            rate = Decimal(str(result["rate"]))
            quantity = Decimal(str(row.quantity))
            row.unit_price = rate
            row.exchange_rate_to_cny = Decimal("1")
            row.total_cost_cny = quantity * rate
            session.commit()
            session.refresh(row)
            return {"record": _transaction_history_row(row), "rate": result}

        if normalized_type == "EVENT":
            event = session.get(PortfolioEvent, record_id)
            if event is None:
                raise HTTPException(status_code=404, detail="event not found")
            changed = _apply_event_historical_rate(event, tool)
            if not changed:
                raise HTTPException(status_code=400, detail="这条记录没有可更新的非人民币现金流或资产流水。")
            session.commit()
            session.refresh(event)
            return {"record": _event_history_row(event), "updated_count": changed}

    raise HTTPException(status_code=400, detail="record_type must be EVENT or TRANSACTION")


def _apply_event_historical_rate(event: PortfolioEvent, tool: ExchangeRateTool) -> int:
    updated = 0
    currencies = {
        item.currency.upper()
        for item in event.cash_ledger_entries
        if item.currency and item.currency.upper() != "CNY"
    }
    currencies.update(
        item.cash_currency.upper()
        for item in event.asset_ledger_entries
        if item.cash_currency and item.cash_currency.upper() != "CNY"
    )
    rates: Dict[str, Decimal] = {}
    for currency in currencies:
        response = tool.execute(
            {
                "base_currency": currency,
                "quote_currency": "CNY",
                "timestamp": event.event_time.isoformat(),
            }
        )
        if not response["ok"]:
            continue
        result = response["result"]
        if result["is_estimated"] or result.get("source") != "PRIMARY":
            continue
        rates[currency] = Decimal(str(result["rate"]))

    for item in event.cash_ledger_entries:
        rate = rates.get(item.currency.upper())
        if rate is None:
            continue
        item.fx_rate_to_cny = rate
        updated += 1
    for item in event.asset_ledger_entries:
        rate = rates.get(item.cash_currency.upper())
        if rate is None:
            continue
        item.fx_rate_to_cny = rate
        updated += 1
    return updated


@router.post("/import-excel-preview")
async def import_excel_preview(
    request: Request,
    filename: str = Query(default="uploaded.xlsx"),
) -> dict:
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="request body is empty")
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="only .xlsx files are supported")

    service = ExcelImportPreviewService()
    return service.preview_forex_transactions(body, source_name=filename)


@router.post("/import-excel-confirm")
async def import_excel_confirm(
    request: Request,
    filename: str = Query(default="uploaded.xlsx"),
    user_id: int = Query(default=1, ge=1),
    include_pending: bool = Query(default=False),
) -> dict:
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="request body is empty")
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="only .xlsx files are supported")

    service = ExcelImportPreviewService()
    with get_db_session() as session:
        repository = TransactionRepository(session)
        return service.import_forex_transactions(
            body,
            source_name=filename,
            user_id=user_id,
            repository=repository,
            include_pending=include_pending,
        )
