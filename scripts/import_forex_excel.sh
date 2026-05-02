#!/usr/bin/env zsh
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage:"
  echo "  ./scripts/import_forex_excel.sh preview <xlsx_path>"
  echo "  ./scripts/import_forex_excel.sh import <xlsx_path> [--user-id 1] [--include-pending]"
  echo "  ./scripts/import_forex_excel.sh show [--user-id 1] [--limit 20]"
  exit 1
fi

UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/excel_import_cli.py "$@"
