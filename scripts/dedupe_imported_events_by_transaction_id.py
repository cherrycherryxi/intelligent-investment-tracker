from __future__ import annotations

import argparse
import ast
import json
from decimal import Decimal
from pathlib import Path
import sys
from typing import Any, Optional

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from investment_tracker.data.db import get_db_session  # noqa: E402
from investment_tracker.data.models import (  # noqa: E402
    AssetLedgerEntry,
    Attribution,
    AttributionGap,
    FundingLot,
    LotConsumption,
    PortfolioEvent,
)
from investment_tracker.data.services import AttributionRebuildService  # noqa: E402


def source_transaction_id(raw_text: Any) -> Optional[str]:
    if not raw_text:
        return None
    try:
        raw = ast.literal_eval(str(raw_text))
    except (SyntaxError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    value = raw.get("交易ID")
    return str(value).strip() if value not in (None, "") else None


def decimal_key(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(Decimal(str(value)).quantize(Decimal("0.000001")).normalize())


def is_quantity_supplement(entry: AssetLedgerEntry) -> bool:
    if entry.cash_amount is None or entry.unit_price is None:
        return False
    return decimal_key(abs(Decimal(str(entry.quantity_delta)))) != decimal_key(entry.cash_amount)


def patch_keep_event(keep: PortfolioEvent, duplicate: PortfolioEvent) -> bool:
    patched = False
    keep_entries = list(keep.asset_ledger_entries)
    for dup_entry in duplicate.asset_ledger_entries:
        if not is_quantity_supplement(dup_entry) or dup_entry.asset is None:
            continue
        target = next(
            (
                entry
                for entry in keep_entries
                if entry.asset is not None
                and entry.asset.asset_code == dup_entry.asset.asset_code
                and entry.cash_currency == dup_entry.cash_currency
                and decimal_key(entry.cash_amount) == decimal_key(dup_entry.cash_amount)
            ),
            None,
        )
        if target is None:
            continue
        if decimal_key(target.quantity_delta) != decimal_key(dup_entry.quantity_delta):
            target.quantity_delta = dup_entry.quantity_delta
            patched = True
        if decimal_key(target.unit_price) != decimal_key(dup_entry.unit_price):
            target.unit_price = dup_entry.unit_price
            patched = True
    return patched


def delete_event_dependencies(session, event_id: int) -> None:
    source_lot_ids = [
        lot_id
        for (lot_id,) in session.query(FundingLot.id).filter(FundingLot.source_event_id == event_id).all()
    ]
    if source_lot_ids:
        session.query(Attribution).filter(Attribution.source_lot_id.in_(source_lot_ids)).delete(synchronize_session=False)
        session.query(LotConsumption).filter(LotConsumption.lot_id.in_(source_lot_ids)).delete(synchronize_session=False)
    session.query(Attribution).filter(Attribution.target_event_id == event_id).delete(synchronize_session=False)
    session.query(AttributionGap).filter(AttributionGap.event_id == event_id).delete(synchronize_session=False)
    session.query(LotConsumption).filter(LotConsumption.consuming_event_id == event_id).delete(synchronize_session=False)
    if source_lot_ids:
        session.query(FundingLot).filter(FundingLot.id.in_(source_lot_ids)).delete(synchronize_session=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dedupe imported portfolio events by source transaction id.")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with get_db_session() as session:
        events = session.query(PortfolioEvent).filter(PortfolioEvent.user_id == args.user_id).order_by(PortfolioEvent.id.asc()).all()
        by_source_id: dict[str, list[PortfolioEvent]] = {}
        for event in events:
            transaction_id = source_transaction_id(event.raw_text)
            if transaction_id:
                by_source_id.setdefault(transaction_id, []).append(event)

        duplicate_groups = {key: value for key, value in by_source_id.items() if len(value) > 1}
        patched = 0
        duplicate_ids: list[int] = []
        for group in duplicate_groups.values():
            keep = min(group, key=lambda event: event.id)
            duplicates = [event for event in group if event.id != keep.id]
            for duplicate in duplicates:
                if patch_keep_event_sql(session, keep.id, duplicate.id):
                    patched += 1
                duplicate_ids.append(duplicate.id)

        summary = {
            "dry_run": args.dry_run,
            "duplicate_groups": len(duplicate_groups),
            "events_to_delete": len(duplicate_ids),
            "events_patched": patched,
        }
        if not args.dry_run:
            delete_events_sql(session, duplicate_ids)
            session.commit()
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    if not args.dry_run:
        with get_db_session() as session:
            AttributionRebuildService(session).rebuild_user_attribution(user_id=args.user_id)
            session.commit()


def patch_keep_event_sql(session, keep_event_id: int, duplicate_event_id: int) -> bool:
    duplicate_entries = session.execute(
        text(
            """
            select ale.quantity_delta, ale.cash_currency, ale.cash_amount, ale.unit_price, a.asset_code
            from asset_ledger_entries ale
            join assets a on a.id = ale.asset_id
            where ale.event_id = :event_id
            """
        ),
        {"event_id": duplicate_event_id},
    ).mappings().all()
    patched = False
    for duplicate in duplicate_entries:
        if decimal_key(abs(Decimal(str(duplicate["quantity_delta"])))) == decimal_key(duplicate["cash_amount"]):
            continue
        target = session.execute(
            text(
                """
                select ale.id
                from asset_ledger_entries ale
                join assets a on a.id = ale.asset_id
                where ale.event_id = :keep_event_id
                  and a.asset_code = :asset_code
                  and ale.cash_currency = :cash_currency
                  and round(ale.cash_amount, 6) = round(:cash_amount, 6)
                limit 1
                """
            ),
            {
                "keep_event_id": keep_event_id,
                "asset_code": duplicate["asset_code"],
                "cash_currency": duplicate["cash_currency"],
                "cash_amount": duplicate["cash_amount"],
            },
        ).mappings().first()
        if target is None:
            continue
        session.execute(
            text(
                """
                update asset_ledger_entries
                set quantity_delta = :quantity_delta,
                    unit_price = :unit_price
                where id = :id
                """
            ),
            {
                "quantity_delta": duplicate["quantity_delta"],
                "unit_price": duplicate["unit_price"],
                "id": target["id"],
            },
        )
        patched = True
    return patched


def delete_events_sql(session, event_ids: list[int]) -> None:
    if not event_ids:
        return
    id_params = {f"id_{index}": event_id for index, event_id in enumerate(event_ids)}
    id_clause = ", ".join(f":{key}" for key in id_params)
    source_lot_ids = [
        row[0]
        for row in session.execute(
            text(f"select id from funding_lots where source_event_id in ({id_clause})"),
            id_params,
        ).all()
    ]
    if source_lot_ids:
        lot_params = {f"lot_{index}": lot_id for index, lot_id in enumerate(source_lot_ids)}
        lot_clause = ", ".join(f":{key}" for key in lot_params)
        session.execute(text(f"delete from attributions where source_lot_id in ({lot_clause})"), lot_params)
        session.execute(text(f"delete from lot_consumptions where lot_id in ({lot_clause})"), lot_params)
        session.execute(text(f"delete from funding_lots where id in ({lot_clause})"), lot_params)
    session.execute(text(f"delete from attributions where target_event_id in ({id_clause})"), id_params)
    session.execute(text(f"delete from attribution_gaps where event_id in ({id_clause})"), id_params)
    session.execute(text(f"delete from lot_consumptions where consuming_event_id in ({id_clause})"), id_params)
    session.execute(text(f"delete from cash_ledger_entries where event_id in ({id_clause})"), id_params)
    session.execute(text(f"delete from asset_ledger_entries where event_id in ({id_clause})"), id_params)
    session.execute(text(f"delete from portfolio_events where id in ({id_clause})"), id_params)


if __name__ == "__main__":
    main()
