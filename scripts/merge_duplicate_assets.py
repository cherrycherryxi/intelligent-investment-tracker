from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from investment_tracker.data.db import get_db_session  # noqa: E402
from investment_tracker.data.models import Asset, AssetLedgerEntry, Attribution, ValuationSnapshot  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge duplicate assets into a canonical asset.")
    parser.add_argument("--target-id", type=int, required=True)
    parser.add_argument("--source-id", type=int, action="append", required=True)
    parser.add_argument("--asset-code", required=True)
    parser.add_argument("--asset-name", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with get_db_session() as session:
        target = session.get(Asset, args.target_id)
        if target is None:
            raise SystemExit(f"target asset {args.target_id} not found")
        sources = [session.get(Asset, source_id) for source_id in args.source_id]
        missing = [source_id for source_id, source in zip(args.source_id, sources) if source is None]
        if missing:
            raise SystemExit(f"source assets not found: {missing}")

        summary = {
            "dry_run": args.dry_run,
            "target_id": target.id,
            "source_ids": args.source_id,
            "asset_ledger_entries": 0,
            "valuation_snapshots": 0,
            "attributions": 0,
        }

        for source_id in args.source_id:
            summary["asset_ledger_entries"] += session.query(AssetLedgerEntry).filter(AssetLedgerEntry.asset_id == source_id).count()
            summary["valuation_snapshots"] += session.query(ValuationSnapshot).filter(ValuationSnapshot.asset_id == source_id).count()
            summary["attributions"] += session.query(Attribution).filter(Attribution.target_asset_id == source_id).count()

        if not args.dry_run:
            for source_id in args.source_id:
                session.query(AssetLedgerEntry).filter(AssetLedgerEntry.asset_id == source_id).update(
                    {AssetLedgerEntry.asset_id: target.id},
                    synchronize_session=False,
                )
                session.query(ValuationSnapshot).filter(ValuationSnapshot.asset_id == source_id).update(
                    {ValuationSnapshot.asset_id: target.id},
                    synchronize_session=False,
                )
                session.query(Attribution).filter(Attribution.target_asset_id == source_id).update(
                    {Attribution.target_asset_id: target.id},
                    synchronize_session=False,
                )
                source = session.get(Asset, source_id)
                if source is not None:
                    session.delete(source)
            target.asset_code = args.asset_code.upper()
            target.asset_name = args.asset_name
            target.metadata_json = {
                **(target.metadata_json or {}),
                "canonical_merge": {
                    "source_asset_ids": args.source_id,
                    "canonical_asset_code": args.asset_code.upper(),
                },
            }
            session.commit()

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
