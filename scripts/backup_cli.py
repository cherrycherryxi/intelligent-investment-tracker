from __future__ import annotations

import argparse
import json
from pathlib import Path

from investment_tracker.data.db import get_db_session
from investment_tracker.utils.backup import BackupService


def main() -> None:
    parser = argparse.ArgumentParser(description="Create, list, and restore JSON backups.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a backup snapshot")
    create_parser.add_argument("--reason", default="manual_backup")

    subparsers.add_parser("list", help="List available backups")

    restore_parser = subparsers.add_parser("restore", help="Restore from a backup file")
    restore_parser.add_argument("file", type=Path)

    args = parser.parse_args()

    with get_db_session() as session:
        service = BackupService(session)
        if args.command == "create":
            file_path = service.create_backup(reason=args.reason)
            print(file_path)
            return
        if args.command == "list":
            for file_path in service.list_backups():
                print(file_path)
            return
        if args.command == "restore":
            restored = service.restore_backup(args.file)
            print(json.dumps(restored, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
