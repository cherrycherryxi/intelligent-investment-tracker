from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect


alembic_command = pytest.importorskip("alembic.command")
alembic_config = pytest.importorskip("alembic.config")


def test_alembic_upgrade_head(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = alembic_config.Config("alembic.ini")
    config.set_main_option("script_location", str(Path("alembic").resolve()))
    config.set_main_option("sqlalchemy.url", database_url)

    alembic_command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    tables = set(inspect(engine).get_table_names())
    assert "transactions" in tables
    assert "positions" in tables
    assert "funding_lots" in tables
    assert "attributions" in tables
    assert "attribution_gaps" in tables
    assert "lot_consumptions" in tables
