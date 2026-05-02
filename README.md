# Intelligent Investment Tracker

English | [简体中文](./README.zh-CN.md)

An intelligent multi-currency investment tracker for cash, FX, funds, wealth products, and bonds, built around a FastAPI API layer, MCP-style tools, import workflows, portfolio ledgers, and AI-assisted analysis.

## Current Status

The project now includes:

- FastAPI routes for transactions, portfolio events, positions, cash balances, performance, advice, and exchange rates
- Excel import preview and confirmed import for FX, cross-currency swaps, funds, wealth products, interest income, and term-deposit style cash income
- Screenshot-based OCR preview workflow for forex and bond trade screenshots
- Natural-language trade parsing for common Chinese trade phrases
- SQLAlchemy persistence, audit logs, and auto-backup on every successful data update
- v0.2 multi-currency ledger tables: `portfolio_events`, `cash_ledger_entries`, `asset_ledger_entries`, and `valuation_snapshots`
- Demo fixtures and a runnable end-to-end demo script
- Alembic migrations, pytest coverage, and Ruff checks

Current limitations:

- screenshot parsing is still rule-based and works best on the supported fixture formats
- AI advice in the demo uses a local stub; the real advice route still depends on configured AI credentials
- realtime scheduled exchange-rate refresh is not done yet
- portfolio-level calculations use the v0.2 ledger as the source of truth; the legacy `transactions` table remains for compatible FX transaction storage and display

## Architecture Overview

The project is organized in four layers:

1. API layer: FastAPI endpoints and request handling
2. Orchestration layer: import and workflow coordination
3. Tool layer: OCR, parsing, pricing, and advice tools
4. Data layer: settings, logging, persistence, backups, and migrations

## Tech Stack

- Python 3.9+
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic Settings
- Pytest
- Ruff

## Repository Layout

```text
src/investment_tracker/
  api/
  orchestration/
  mcp_tools/
  skills/
  data/
  utils/
tests/
config/
alembic/
demo/
```

## Local Development

### 1. Create the environment

```bash
uv sync
```

If `uv` cannot write its default cache in your environment, use:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync
```

### 2. Configure environment variables

Copy `.env.example` into `.env` and adjust values as needed.

### 3. Run tests

```bash
uv run pytest
```

### 4. Run linting

```bash
uv run ruff check .
```

## Run the API

The FastAPI app object lives at `investment_tracker.api.main:app`.

After syncing dependencies, start the API with:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn investment_tracker.api.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

## Database Migrations

Upgrade to the latest schema:

```bash
uv run python -m alembic upgrade head
```

Create a new migration later:

```bash
uv run python -m alembic revision -m "describe change"
```

Initialize the database directly from ORM metadata:

```bash
uv run python scripts/init_db.py
```

## API Overview

Main routes:

- `POST /api/transactions`
- `GET /api/transactions`
- `POST /api/transactions/upload`
- `POST /api/transactions/import-excel-preview`
- `POST /api/transactions/import-excel-confirm`
- `GET /api/positions`
- `GET /api/performance`
- `GET /api/cash-balances`
- `POST /api/portfolio-events`
- `POST /api/valuations`
- `GET /api/advice`
- `POST /api/exchange-rates/refresh`
- `GET /api/exchange-rates/latest`

## Data Lineage and Accounting Semantics

Use this chain when debugging numbers:

```text
source file/screenshot -> import preview/parser -> transactions or portfolio_events
-> cash_ledger_entries / asset_ledger_entries / valuation_snapshots / exchange_rates
-> aggregation service -> API response -> UI display
```

Authoritative surfaces:

- `GET /api/transactions` is a history view that merges legacy `transactions` and v0.2 `portfolio_events`.
- `GET /api/cash-balances` is the source of truth for native-currency cash balances.
- `GET /api/positions` aggregates asset ledger entries and valuation snapshots.
- `GET /api/performance` is the source of truth for portfolio-level value, net input, investment PnL, FX PnL, and data-quality flags.

Excel confirmed import is idempotent. It builds a semantic duplicate key from user, asset/event type, timestamp, currencies, quantities, prices, cash entries, and asset entries. Re-importing the same workbook skips existing records and returns `skipped_duplicate_count`.

Excel display formatting may hide seconds. The importer uses the underlying cell value, so rows that both display as `2024/6/25 0:55` can still be imported as distinct records when their raw serial timestamps differ, for example `00:55:00.000001` and `00:55:01`.

Manual entry semantics:

- `FOREX` creates a legacy transaction for CNY-vs-FX buy/sell records.
- `FX_SWAP` creates a portfolio event with two native cash legs.
- `FUND` and `WEALTH_PRODUCT` create portfolio events with native cash and asset ledger entries; non-CNY amounts are not written as `total_cost_cny`.
- `INTEREST_INCOME` creates a portfolio event that increases native cash only.

For a full local re-import, keep the schema and clear only business data:

```bash
sqlite3 investment_tracker.db "PRAGMA foreign_keys=OFF; BEGIN; DELETE FROM asset_ledger_entries; DELETE FROM cash_ledger_entries; DELETE FROM valuation_snapshots; DELETE FROM portfolio_events; DELETE FROM transactions; DELETE FROM positions; DELETE FROM exchange_rates; DELETE FROM investment_advice; DELETE FROM audit_logs; DELETE FROM assets; DELETE FROM users; COMMIT; PRAGMA foreign_keys=ON;"
```

Example: create one transaction

```bash
curl -X POST http://127.0.0.1:8000/api/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "asset_type": "FOREX",
    "asset_code": "USD",
    "direction": "BUY",
    "quantity": 100,
    "unit_price": 6.8136,
    "trade_currency": "CNY",
    "trade_time": "2026-04-27T10:00:00",
    "exchange_rate_to_cny": 1.0,
    "total_cost_cny": 681.36
  }'
```

## Quick Excel Import

Preview the transaction sheet in your workbook:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/excel_import_cli.py preview investment_tracker_v5.xlsx
```

Import confirmed rows into the local database:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/excel_import_cli.py import investment_tracker_v5.xlsx --user-id 1
```

View recently imported transactions:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/excel_import_cli.py show --user-id 1 --limit 20
```

There is also a shell wrapper:

```bash
./scripts/import_forex_excel.sh preview investment_tracker_v5.xlsx
```

## Backup and Restore

Each successful data update now creates a JSON snapshot under `backups/` by default. This applies to transaction writes, persisted position snapshots, and exchange-rate refreshes.

Create a manual backup:

```bash
uv run python scripts/backup_cli.py create --reason manual_snapshot
```

List available backups:

```bash
uv run python scripts/backup_cli.py list
```

Restore from a backup file:

```bash
uv run python scripts/backup_cli.py restore backups/<backup-file>.json
```

## Demo

Run the Day5/Day6 demo flow with local fixtures derived from real screenshot formats and natural-language samples:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python demo/demo.py
```

The demo covers:

- bond detail screenshot -> OCR fallback -> parsing -> transaction storage
- forex list screenshot -> OCR preview -> pending review example
- natural-language trade input -> parsing -> transaction storage
- position aggregation -> investment advice generation with a local demo stub

Demo artifacts:

- fixtures: `demo/fixtures/`
- generated sqlite DB: `demo/artifacts/demo.db`

## Day 2-7 Roadmap

- Day2: MCP tool abstractions and core tool implementations
- Day3: AI model client and investment advice engine
- Day4: reusable skills and evaluation harness
- Day5: API endpoints and orchestration workflows
- Day6: dashboard, export, and portfolio analysis
- Day7: hardening, demos, and documentation polish
