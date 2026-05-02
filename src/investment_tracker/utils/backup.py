"""JSON snapshot backup helpers for persisted data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Sequence, Type

from sqlalchemy import DateTime, Enum as SqlEnum, Numeric, select
from sqlalchemy.orm import Session

from investment_tracker.data.models import AuditLog, ExchangeRate, InvestmentAdvice, Position, Transaction, User
from investment_tracker.settings import AppSettings, get_settings

MODEL_ORDER: Sequence[Type[Any]] = (
    User,
    Transaction,
    Position,
    ExchangeRate,
    InvestmentAdvice,
    AuditLog,
)


class BackupService:
    """Create and restore JSON snapshots for core database tables."""

    def __init__(self, session: Session, settings: AppSettings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def create_backup(self, *, reason: str = "data_update") -> Path | None:
        if not self.settings.backup_enabled:
            return None

        backup_dir = Path(self.settings.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc)
        safe_reason = reason.replace(" ", "_").replace("/", "_")
        file_path = backup_dir / f"{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}_{safe_reason}.json"
        payload = {
            "metadata": {
                "created_at": timestamp.isoformat(),
                "reason": reason,
                "database_url": self.settings.database_url,
            },
            "tables": {
                model.__tablename__: [self._serialize_row(row) for row in self.session.execute(select(model)).scalars().all()]
                for model in MODEL_ORDER
            },
        }
        file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return file_path

    def list_backups(self) -> List[Path]:
        backup_dir = Path(self.settings.backup_dir)
        if not backup_dir.exists():
            return []
        return sorted(backup_dir.glob("*.json"), reverse=True)

    def restore_backup(self, file_path: str | Path) -> Dict[str, int]:
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        tables = payload.get("tables", {})

        for model in reversed(MODEL_ORDER):
            self.session.query(model).delete()
        self.session.flush()

        restored_counts: Dict[str, int] = {}
        for model in MODEL_ORDER:
            table_name = model.__tablename__
            rows = tables.get(table_name, [])
            for row in rows:
                self.session.add(model(**self._deserialize_row(model, row)))
            restored_counts[table_name] = len(rows)

        self.session.commit()
        return restored_counts

    def _serialize_row(self, row: Any) -> Dict[str, Any]:
        serialized: Dict[str, Any] = {}
        for column in row.__table__.columns:
            serialized[column.name] = self._serialize_value(getattr(row, column.name))
        return serialized

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        return value

    def _deserialize_row(self, model: Type[Any], row: Dict[str, Any]) -> Dict[str, Any]:
        restored: Dict[str, Any] = {}
        for column in model.__table__.columns:
            value = row.get(column.name)
            if value is None:
                restored[column.name] = None
                continue
            if isinstance(column.type, SqlEnum) and getattr(column.type, "enum_class", None):
                restored[column.name] = column.type.enum_class(value)
                continue
            if isinstance(column.type, Numeric):
                restored[column.name] = Decimal(str(value))
                continue
            if isinstance(column.type, DateTime):
                restored[column.name] = datetime.fromisoformat(value)
                continue
            restored[column.name] = value
        return restored


__all__ = ["BackupService"]
