from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.enums import AssetType, EventType
from investment_tracker.data.repositories import TransactionRepository
from investment_tracker.orchestration.excel_import_service import ExcelImportPreviewService
from investment_tracker.utils.xlsx_reader import WorkbookSheet


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


class StubWorkbookReader:
    def read(self, workbook_bytes):
        return [
            WorkbookSheet(
                name="外汇交易记录",
                rows=[
                    ["交易ID", "交易时间", "类别", "名称", "卖出货币", "卖出金额", "买入货币", "买入金额", "备注"],
                    ["FX001", "2024-06-21 11:44:00", "外汇", "外汇", "CNY", 7282.4, "USD", 1000, "买USD"],
                    ["WM001", "2024-06-25 00:55:00", "理财", "美元理财", "USD", 1000, None, None, "买理财"],
                ],
            )
        ]


def test_excel_import_preview_builds_ready_pending_and_failed_groups() -> None:
    workbook_bytes = Path("investment_tracker_v5.xlsx").read_bytes()

    result = ExcelImportPreviewService().preview_forex_transactions(
        workbook_bytes,
        source_name="investment_tracker_v5.xlsx",
    )

    assert result["summary"]["total_rows"] > 100
    assert result["summary"]["ready_count"] >= 1
    assert result["summary"]["pending_count"] >= 1
    first_ready = result["ready_to_import"][0]
    assert first_ready.get("transaction") or first_ready.get("portfolio_event")


class StubExchangeRateTool:
    def execute(self, payload):
        base_currency = payload["base_currency"]
        if base_currency == "USD":
            return {
                "ok": True,
                "result": {
                    "rate": 7.23,
                    "rate_timestamp": "2026-04-30T00:00:00+00:00",
                    "is_estimated": False,
                    "source": "PRIMARY",
                },
            }
        return {"ok": False, "error": {"message": "missing"}}


def test_excel_import_cross_currency_builds_swap_event_without_cny_estimate() -> None:
    service = ExcelImportPreviewService(exchange_rate_tool=StubExchangeRateTool())

    result = service._build_row_preview(
        row_number=2,
        row={
            "交易ID": "FX999",
            "交易时间": 45700.5,
            "类别": "外汇",
            "名称": "外汇",
            "卖出货币": "AUD",
            "卖出金额": 506.90,
            "买入货币": "USD",
            "买入金额": 336.58,
            "备注": "卖AUD买USD",
        },
    )

    assert result.errors == []
    assert result.warnings == []
    assert result.transaction is None
    assert result.portfolio_event is not None
    assert result.portfolio_event["event_type"] == EventType.FX_SWAP.value
    assert result.portfolio_event["cash_entries"][0]["currency"] == "AUD"
    assert result.portfolio_event["cash_entries"][0]["amount_delta"] == -506.90
    assert result.portfolio_event["cash_entries"][1]["currency"] == "USD"
    assert result.portfolio_event["cash_entries"][1]["amount_delta"] == 336.58
    assert result.portfolio_event["cash_entries"][0]["rmb_amount"] is None


def test_excel_import_builds_v02_events_for_fund_wealth_interest_and_term_rows() -> None:
    service = ExcelImportPreviewService()

    fund = service._build_row_preview(
        row_number=1,
        row={
            "交易ID": "FUND001",
            "交易时间": 45700.5,
            "类别": "基金",
            "名称": "美元基金",
            "卖出货币": "USD",
            "卖出金额": 100,
            "买入货币": None,
            "买入金额": None,
            "备注": "基金支出",
        },
    )
    wealth = service._build_row_preview(
        row_number=2,
        row={
            "交易ID": "WM001",
            "交易时间": 45700.5,
            "类别": "理财",
            "名称": "美元理财",
            "卖出货币": None,
            "卖出金额": None,
            "买入货币": "USD",
            "买入金额": 101,
            "备注": "理财收入",
        },
    )
    interest = service._build_row_preview(
        row_number=3,
        row={
            "交易ID": "INT001",
            "交易时间": 45700.5,
            "类别": "结息",
            "名称": "结息：0.01扣税：0",
            "卖出货币": None,
            "卖出金额": None,
            "买入货币": "USD",
            "买入金额": 0.01,
            "备注": "结息收入",
        },
    )
    term = service._build_row_preview(
        row_number=4,
        row={
            "交易ID": "TD001",
            "交易时间": 45700.5,
            "类别": "定期",
            "名称": "定期",
            "卖出货币": None,
            "卖出金额": None,
            "买入货币": "CAD",
            "买入金额": 2000.02,
            "备注": "定期收入",
        },
    )

    assert fund.portfolio_event["event_type"] == EventType.FUND_BUY.value
    assert fund.portfolio_event["asset_entries"][0]["asset"]["asset_type"] == AssetType.FUND.value
    assert wealth.portfolio_event["event_type"] == EventType.WEALTH_REDEEM.value
    assert wealth.portfolio_event["asset_entries"][0]["asset"]["asset_type"] == AssetType.WEALTH_PRODUCT.value
    assert interest.portfolio_event["event_type"] == EventType.INTEREST_INCOME.value
    assert interest.portfolio_event["cash_entries"][0]["amount_delta"] == 0.01
    assert term.portfolio_event["event_type"] == EventType.WEALTH_INCOME.value
    assert term.portfolio_event["cash_entries"][0]["currency"] == "CAD"


def test_excel_confirm_import_skips_existing_semantic_duplicates() -> None:
    session = _session()
    repo = TransactionRepository(session)
    service = ExcelImportPreviewService(workbook_reader=StubWorkbookReader())

    first = service.import_forex_transactions(
        b"stub",
        source_name="stub.xlsx",
        user_id=1,
        repository=repo,
    )
    second = service.import_forex_transactions(
        b"stub",
        source_name="stub.xlsx",
        user_id=1,
        repository=repo,
    )

    assert first["imported_count"] == 1
    assert first["imported_event_count"] == 1
    assert first["skipped_duplicate_count"] == 0
    assert second["imported_count"] == 0
    assert second["imported_event_count"] == 0
    assert second["skipped_duplicate_count"] == 2
