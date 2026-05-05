from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from investment_tracker.data.db import get_db_session  # noqa: E402
from investment_tracker.data.services import AttributionRebuildService  # noqa: E402


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild FX funding attribution records.")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with get_db_session() as session:
        summary = AttributionRebuildService(session).rebuild_user_attribution(
            user_id=args.user_id,
            start_date=_parse_datetime(args.start_date),
            end_date=_parse_datetime(args.end_date),
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            session.commit()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
