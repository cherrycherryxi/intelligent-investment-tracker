from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from investment_tracker.data.base import Base
from investment_tracker.data.models import Transaction
from investment_tracker.data.repositories import TransactionRepository
from investment_tracker.settings import AppSettings
import investment_tracker.utils.backup as backup_module
from investment_tracker.utils.backup import BackupService


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_create_backup_snapshot_after_transaction_write(tmp_path: Path, monkeypatch) -> None:
    session = _session()
    repo = TransactionRepository(session)

    settings = AppSettings(database_url="sqlite:///:memory:", backup_dir=str(tmp_path))
    monkeypatch.setattr(backup_module, "get_settings", lambda: settings)
    repo.create_transactions(
        user_id=1,
        transactions=[
            {
                "asset_type": "FOREX",
                "asset_code": "USD",
                "asset_name": "USD",
                "direction": "BUY",
                "quantity": 1000,
                "unit_price": 7.23,
                "trade_currency": "CNY",
                "trade_time": "2025-09-18T09:54:35",
                "exchange_rate_to_cny": 1.0,
                "total_cost_cny": 7230.0,
                "source": "manual",
                "status": "CONFIRMED",
            }
        ],
    )

    backups = BackupService(session, settings).list_backups()
    assert len(backups) == 1
    payload = json.loads(backups[0].read_text(encoding="utf-8"))
    assert payload["metadata"]["reason"] == "transactions_updated"
    assert len(payload["tables"]["transactions"]) == 1


def test_restore_backup_rebuilds_tables(tmp_path: Path, monkeypatch) -> None:
    session = _session()
    settings = AppSettings(database_url="sqlite:///:memory:", backup_dir=str(tmp_path))
    monkeypatch.setattr(backup_module, "get_settings", lambda: settings)
    repo = TransactionRepository(session)
    repo.create_transactions(
        user_id=7,
        transactions=[
            {
                "asset_type": "FOREX",
                "asset_code": "EUR",
                "asset_name": "EUR",
                "direction": "BUY",
                "quantity": 50,
                "unit_price": 7.8,
                "trade_currency": "CNY",
                "trade_time": "2025-09-18T09:54:35",
                "exchange_rate_to_cny": 1.0,
                "total_cost_cny": 390.0,
                "source": "excel_import",
                "status": "CONFIRMED",
            }
        ],
    )
    backup = BackupService(session, settings).create_backup(reason="restore_fixture")
    assert backup is not None

    session.query(Transaction).delete()
    session.commit()
    assert session.query(Transaction).count() == 0

    restored = BackupService(session, settings).restore_backup(backup)
    assert restored["transactions"] == 1
    row = session.query(Transaction).one()
    assert row.asset_code == "EUR"
    assert float(row.total_cost_cny) == 390.0
