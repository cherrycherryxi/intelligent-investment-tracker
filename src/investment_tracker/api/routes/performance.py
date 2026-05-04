"""Portfolio performance and v0.2 ledger API routes."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from investment_tracker.api.schemas import PortfolioEventCreateRequest, ScreenshotUploadRequest, ValuationCreateRequest, WealthPositionSnapshotRequest
from investment_tracker.data.db import get_db_session
from investment_tracker.data.enums import AssetType
from investment_tracker.data.models import Asset, AuditLog, CashLedgerEntry
from investment_tracker.data.services import AuditService, PerformanceService, PortfolioEventService
from investment_tracker.mcp_tools.ocr_tool import OCRTool


router = APIRouter(tags=["performance"])


def _currencies_for_user(session, *, user_id: int) -> set[str]:
    cash_currencies = {
        row[0].upper()
        for row in session.query(CashLedgerEntry.currency).filter(CashLedgerEntry.user_id == user_id).distinct().all()
        if row[0]
    }
    asset_currencies = {
        row[0].upper()
        for row in session.query(Asset.currency).distinct().all()
        if row[0]
    }
    return {currency for currency in cash_currencies | asset_currencies if currency != "CNY"}


def _parse_wealth_position_text(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    holdings = []
    code_pattern = re.compile(r"([A-Z]{3}\d{4}A)")
    number_pattern = re.compile(r"-?\d[\d,]*\.\d+|-?\d[\d,]*")
    for index, line in enumerate(lines):
        match = code_pattern.search(line)
        if not match:
            continue
        code = match.group(1)
        name = line[: match.start()].strip(" -")
        window = " ".join(lines[index + 1 : index + 5])
        numbers = [float(item.replace(",", "")) for item in number_pattern.findall(window)]
        if not numbers:
            continue
        currency = "USD"
        currency_text = f"{line} {window}"
        if "欧元" in currency_text:
            currency = "EUR"
        elif "美元" in currency_text:
            currency = "USD"
        holdings.append(
            {
                "asset_code": code,
                "asset_name": name or code,
                "currency": currency,
                "market_value": numbers[0],
                "holding_income": numbers[1] if len(numbers) > 1 else None,
                "income_as_of": None,
                "redeemable_frequency": "每日可申赎" if "每日" in currency_text else None,
            }
        )
    return holdings


@router.get("/api/performance")
async def get_performance(user_id: int = 1, valuation_time: Optional[str] = None) -> dict:
    cutoff = datetime.fromisoformat(valuation_time.replace("Z", "+00:00")) if valuation_time else None
    with get_db_session() as session:
        service = PerformanceService(session)
        return service.performance(user_id=user_id, valuation_time=cutoff)


@router.get("/api/performance/audit")
async def get_performance_audit(
    user_id: int = 1,
    currency: Optional[str] = None,
    valuation_time: Optional[str] = None,
    expected_cash: Optional[float] = None,
    expected_assets: Optional[float] = None,
    expected_value_cny: Optional[float] = None,
) -> dict:
    try:
        cutoff = datetime.fromisoformat(valuation_time.replace("Z", "+00:00")) if valuation_time else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid valuation_time: {valuation_time}") from exc

    expected_values = {
        key: value
        for key, value in {
            "expected_cash": expected_cash,
            "expected_assets": expected_assets,
            "expected_value_cny": expected_value_cny,
        }.items()
        if value is not None
    }

    try:
        with get_db_session() as session:
            service = AuditService(session)
            audit = service.generate_audit(
                user_id=user_id,
                currency=currency,
                valuation_time=cutoff,
                expected_values=expected_values,
            )
            log = service.create_audit_log(
                user_id=user_id,
                currencies_audited=audit["currencies_audited"],
                discrepancies_found=audit["summary"]["total_discrepancies"],
                audit_details=audit,
            )
            audit["audit_log_id"] = log.id
            return audit
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/performance/audit-history")
async def get_performance_audit_history(user_id: int = 1, limit: int = 50) -> dict:
    with get_db_session() as session:
        service = AuditService(session)
        return {"audit_logs": service.get_audit_history(user_id=user_id, limit=limit)}


@router.get("/api/performance/audit/{audit_id}")
async def get_performance_audit_detail(audit_id: int, user_id: int = 1) -> dict:
    with get_db_session() as session:
        log = (
            session.query(AuditLog)
            .filter(
                AuditLog.id == audit_id,
                AuditLog.user_id == user_id,
                AuditLog.entity_type == "performance_audit",
            )
            .one_or_none()
        )
        if log is None:
            raise HTTPException(status_code=404, detail="audit not found")
        details = log.details_json or {}
        return details.get("audit_report", details)


@router.get("/api/cash-balances")
async def get_cash_balances(user_id: int = 1, valuation_time: Optional[str] = None) -> dict:
    cutoff = datetime.fromisoformat(valuation_time.replace("Z", "+00:00")) if valuation_time else None
    with get_db_session() as session:
        service = PerformanceService(session)
        return service.cash_balances(user_id=user_id, valuation_time=cutoff)


@router.post("/api/portfolio-events")
async def create_portfolio_event(payload: PortfolioEventCreateRequest) -> dict:
    try:
        with get_db_session() as session:
            service = PortfolioEventService(session)
            event = service.create_event(user_id=payload.user_id, payload=payload.model_dump(mode="json"))
            return {
                "event": {
                    "id": event.id,
                    "user_id": event.user_id,
                    "event_type": event.event_type.value,
                    "event_time": event.event_time.isoformat(),
                    "status": event.status.value,
                    "source": event.source,
                }
            }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/valuations")
async def create_valuation(payload: ValuationCreateRequest) -> dict:
    try:
        with get_db_session() as session:
            service = PortfolioEventService(session)
            valuation = service.create_valuation(user_id=payload.user_id, payload=payload.model_dump(mode="json"))
            return {
                "valuation": {
                    "id": valuation.id,
                    "user_id": valuation.user_id,
                    "asset_id": valuation.asset_id,
                    "valuation_time": valuation.valuation_time.isoformat(),
                    "quantity": float(valuation.quantity),
                    "price": float(valuation.price) if valuation.price is not None else None,
                    "market_value": float(valuation.market_value),
                    "currency": valuation.currency,
                    "fx_rate_to_cny": float(valuation.fx_rate_to_cny) if valuation.fx_rate_to_cny is not None else None,
                    "source": valuation.source,
                    "is_estimated": valuation.is_estimated,
                }
            }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/wealth-position-snapshots")
async def import_wealth_position_snapshot(payload: WealthPositionSnapshotRequest) -> dict:
    created = []
    try:
        with get_db_session() as session:
            service = PortfolioEventService(session)
            for holding in payload.holdings:
                currency = holding.currency.upper()
                asset = (
                    session.query(Asset)
                    .filter(
                        Asset.asset_type == AssetType.WEALTH_PRODUCT,
                        Asset.asset_code == holding.asset_code,
                        Asset.currency == currency,
                    )
                    .one_or_none()
                )
                if asset is None:
                    asset = (
                        session.query(Asset)
                        .filter(
                            Asset.asset_type == AssetType.WEALTH_PRODUCT,
                            Asset.asset_name == holding.asset_name,
                            Asset.currency == currency,
                        )
                        .one_or_none()
                    )
                    if asset is not None and asset.asset_code.startswith("WEAL-"):
                        asset.asset_code = holding.asset_code
                        session.flush()
                asset_payload = (
                    {"asset_id": asset.id}
                    if asset is not None
                    else {
                        "asset": {
                            "asset_type": AssetType.WEALTH_PRODUCT.value,
                            "asset_code": holding.asset_code,
                            "asset_name": holding.asset_name,
                            "currency": currency,
                            "metadata_json": {
                                "holding_income": holding.holding_income,
                                "income_as_of": holding.income_as_of,
                                "redeemable_frequency": holding.redeemable_frequency,
                                "raw_text": payload.raw_text,
                            },
                        }
                    }
                )
                valuation = service.create_valuation(
                    user_id=payload.user_id,
                    payload={
                        **asset_payload,
                        "valuation_time": payload.valuation_time.isoformat(),
                        "quantity": holding.market_value,
                        "price": 1,
                        "market_value": holding.market_value,
                        "currency": currency,
                        "source": payload.source,
                        "is_estimated": False,
                    },
                )
                created.append(
                    {
                        "id": valuation.id,
                        "asset_id": valuation.asset_id,
                        "asset_code": holding.asset_code,
                        "asset_name": holding.asset_name,
                        "currency": valuation.currency,
                        "market_value": float(valuation.market_value),
                        "holding_income": holding.holding_income,
                    }
                )
        return {"imported_count": len(created), "valuations": created}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/wealth-position-snapshots/upload")
async def preview_wealth_position_snapshot_upload(payload: ScreenshotUploadRequest) -> dict:
    parsed = []
    failed = []
    ocr_tool = OCRTool()
    for item in payload.files:
        response = ocr_tool.execute(
            {
                "image_base64": item.content_base64,
                "language": item.language,
                "provider": item.provider,
            }
        )
        if not response["ok"]:
            failed.append({"filename": item.filename, "errors": [response["error"]["message"]]})
            continue
        text = response["result"]["text"]
        parsed.append(
            {
                "filename": item.filename,
                "ocr": response["result"],
                "holdings": _parse_wealth_position_text(text),
            }
        )
    return {
        "summary": {
            "total_files": len(payload.files),
            "parsed_count": sum(1 for item in parsed if item["holdings"]),
            "failed_count": len(failed),
        },
        "parsed": parsed,
        "failed": failed,
    }
