"""Initialize the local database schema."""

from __future__ import annotations

from investment_tracker.data.base import Base
from investment_tracker.data.db import create_engine_from_settings
from investment_tracker.data import models  # noqa: F401
from investment_tracker.settings import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    print(f"Initialized database at {settings.database_url}")


if __name__ == "__main__":
    main()
