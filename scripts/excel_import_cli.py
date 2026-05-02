"""Local CLI for previewing, importing, and viewing Excel-derived transactions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from investment_tracker.data.base import Base
from investment_tracker.data.db import create_engine_from_settings, get_db_session
from investment_tracker.data.repositories import TransactionRepository
from investment_tracker.orchestration.excel_import_service import ExcelImportPreviewService
from investment_tracker.settings import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Excel import helper for forex transactions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview = subparsers.add_parser("preview", help="Preview import result without writing to DB.")
    preview.add_argument("xlsx_path", type=Path)
    preview.add_argument("--json", action="store_true", help="Print full JSON payload.")

    run_import = subparsers.add_parser("import", help="Import ready rows into the database.")
    run_import.add_argument("xlsx_path", type=Path)
    run_import.add_argument("--user-id", type=int, default=1)
    run_import.add_argument("--include-pending", action="store_true")

    show = subparsers.add_parser("show", help="Show imported transactions from the database.")
    show.add_argument("--user-id", type=int, default=1)
    show.add_argument("--limit", type=int, default=20)

    return parser


def ensure_db_initialized() -> None:
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)


def preview_command(path: Path, *, output_json: bool) -> int:
    service = ExcelImportPreviewService()
    payload = service.preview_forex_transactions(path.read_bytes(), source_name=path.name)
    if output_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    summary = payload["summary"]
    print(f"文件: {path.name}")
    print(
        f"总行数: {summary['total_rows']} | ready: {summary['ready_count']} | "
        f"pending: {summary['pending_count']} | failed: {summary['failed_count']}"
    )
    _print_sample("ready_to_import", payload["ready_to_import"])
    _print_sample("pending_review", payload["pending_review"])
    _print_sample("failed", payload["failed"])
    return 0


def import_command(path: Path, *, user_id: int, include_pending: bool) -> int:
    ensure_db_initialized()
    service = ExcelImportPreviewService()
    with get_db_session() as session:
        repository = TransactionRepository(session)
        payload = service.import_forex_transactions(
            path.read_bytes(),
            source_name=path.name,
            user_id=user_id,
            repository=repository,
            include_pending=include_pending,
        )

    print(f"文件: {path.name}")
    print(
        f"已导入交易: {payload['imported_count']} | 已导入事件: {payload.get('imported_event_count', 0)} | "
        f"跳过 pending: {payload['skipped_pending_count']} | "
        f"失败: {payload['failed_count']}"
    )
    print(f"创建的 transaction ids: {payload['created_transaction_ids']}")
    if payload.get("created_event_ids"):
        print(f"创建的 portfolio event ids: {payload['created_event_ids']}")
    return 0


def show_command(*, user_id: int, limit: int) -> int:
    ensure_db_initialized()
    with get_db_session() as session:
        repository = TransactionRepository(session)
        rows = repository.list_transactions(user_id=user_id, limit=limit)

    if not rows:
        print("数据库中还没有交易记录。")
        return 0

    print(f"user_id={user_id} 最近 {len(rows)} 条交易:")
    for row in rows:
        print(
            f"[{row.id}] {row.trade_time.isoformat()} {row.direction.value} {row.asset_code} "
            f"qty={row.quantity} cost_cny={row.total_cost_cny} status={row.status.value} source={row.source}"
        )
    return 0


def _print_sample(label: str, rows: list[Dict[str, Any]]) -> None:
    print(f"\n{label}: {len(rows)}")
    for item in rows[:3]:
        print(json.dumps(item, ensure_ascii=False, default=str))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "preview":
        return preview_command(args.xlsx_path, output_json=args.json)
    if args.command == "import":
        return import_command(args.xlsx_path, user_id=args.user_id, include_pending=args.include_pending)
    if args.command == "show":
        return show_command(user_id=args.user_id, limit=args.limit)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
