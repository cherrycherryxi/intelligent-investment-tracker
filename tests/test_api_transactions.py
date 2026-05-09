from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
import investment_tracker.api.routes.transactions as transaction_routes
from investment_tracker.api.routes.transactions import import_excel_preview

_FIXTURE = Path("investment_tracker_v5.xlsx")


def _build_request(body: bytes) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/transactions/import-excel-preview",
        "headers": [],
        "query_string": b"",
    }
    return Request(scope, receive)


@pytest.mark.skipif(not _FIXTURE.exists(), reason="requires local fixture investment_tracker_v5.xlsx")
def test_import_excel_preview_endpoint() -> None:
    workbook_bytes = Path("investment_tracker_v5.xlsx").read_bytes()
    payload = asyncio.run(
        import_excel_preview(
            _build_request(workbook_bytes),
            filename="investment_tracker_v5.xlsx",
        )
    )
    assert payload["summary"]["total_rows"] > 100
    assert "ready_to_import" in payload


def test_import_excel_preview_rejects_empty_body() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(import_excel_preview(_build_request(b""), filename="empty.xlsx"))

    assert exc_info.value.status_code == 400


@pytest.mark.skipif(not _FIXTURE.exists(), reason="requires local fixture investment_tracker_v5.xlsx")
def test_import_excel_confirm_persists_ready_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    workbook_bytes = Path("investment_tracker_v5.xlsx").read_bytes()
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    class SessionContext:
        def __enter__(self):
            self.session = SessionLocal()
            return self.session

        def __exit__(self, exc_type, exc, tb):
            self.session.close()

    monkeypatch.setattr(transaction_routes, "get_db_session", lambda: SessionContext())

    payload = asyncio.run(
        transaction_routes.import_excel_confirm(
            _build_request(workbook_bytes),
            filename="investment_tracker_v5.xlsx",
            user_id=1,
            include_pending=False,
        )
    )

    assert payload["imported_count"] + payload["imported_event_count"] >= 1
    assert payload["created_transaction_ids"] or payload["created_event_ids"]
