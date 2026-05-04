# Intelligent Investment Tracker

English | [简体中文](./README.zh-CN.md)

An intelligent multi-currency investment tracker for cash, FX, funds, wealth products, and bonds, built around a FastAPI API layer, MCP-style tools, import workflows, portfolio ledgers, and AI-assisted analysis.

## Current Status

The project now includes:

- FastAPI routes for transactions, portfolio events, positions, cash balances, performance, performance data audit, advice, and exchange rates
- Excel import preview and confirmed import for FX, cross-currency swaps, funds, wealth products, interest income, and term-deposit style cash income
- Screenshot-based OCR preview workflow for forex and bond trade screenshots
- Natural-language trade parsing for common Chinese trade phrases
- SQLAlchemy persistence, performance audit history, audit logs, and auto-backup on every successful data update
- v0.2 multi-currency ledger tables: `portfolio_events`, `cash_ledger_entries`, `asset_ledger_entries`, and `valuation_snapshots`
- Demo fixtures and a runnable end-to-end demo script
- Alembic migrations, pytest coverage, and Ruff checks

Current limitations:

- screenshot parsing is still rule-based and works best on the supported fixture formats
- AI advice in the demo uses a local stub; the real advice route still depends on configured AI credentials
- background scheduled exchange-rate refresh is not done yet; Excel import now fills historical rates by trade time, and latest rates can still be refreshed manually through the API/UI
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

## Run the Frontend

The frontend lives in `frontend/` and uses Vite, React, and Material UI. It reads the backend base URL from `frontend/.env.development` via `VITE_API_BASE_URL`.

```bash
cd frontend
npm install
npm run dev
```

Then open the local URL printed by Vite, for example:

- `http://127.0.0.1:4173/performance`
- `http://127.0.0.1:4173/performance/audit`

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
- `GET /api/performance/audit`
- `GET /api/performance/audit-history`
- `GET /api/performance/audit/{audit_id}`
- `GET /api/cash-balances`
- `POST /api/portfolio-events`
- `POST /api/valuations`
- `GET /api/advice`
- `POST /api/exchange-rates/refresh`
- `GET /api/exchange-rates/latest`

### Exchange-Rate Fill and Refresh

The default import flow now preserves source-sheet values and does not auto-enrich every row with historical FX during preview/confirm:

- Excel preview / confirm does not automatically fill `fx_rate_to_cny` for `FX_SWAP`, foreign-currency funds, wealth products, interest income, or term-deposit style events.
- If an FX buy/sell row is missing the CNY amount, preview marks it `PENDING` instead of silently persisting an estimated historical rate.
- The Transactions page exposes a per-record `Update Rate` action that queries the trade-date historical rate for one `TRANSACTION` or `EVENT` and writes it back.
- Only same-trade-date `PRIMARY` rates from the live historical provider are written into cost fields. `FALLBACK` or `estimated` rates are not persisted as confirmed cost, so static fallback data cannot silently create wrong cost basis.
- `TRANSACTION` records support historical-rate fill only for CNY-denominated FX trades; `EVENT` records attempt to fill non-CNY cash legs and asset-ledger rows.
- CNY is stored as `1.0`; if trade time is missing or the rate provider cannot return a rate, the field remains empty and is surfaced through Positions / Performance data-quality flags.
- Existing imported rows are not automatically backfilled. Re-import the source file, refresh rows one by one, or add a dedicated backfill migration later, if you need historical CNY cost on old data.

`POST /api/exchange-rates/refresh` is the manual latest-rate refresh route; `POST /api/transactions/{record_type}/{record_id}/historical-rate` refreshes trade-date historical rate for one record. Background scheduling is still not wired up.

### Current Holding Snapshots

Amount-valued assets such as `BOND`, `FUND`, and `WEALTH_PRODUCT` need current holding snapshots because transaction ledger quantity only represents historical cost or subscription/redemption net amount, not daily accrued value.

- The `Positions` page shows a `Snapshot` action for amount-valued assets.
- Enter the current holding amount shown by the bank/broker and the snapshot time; the frontend writes a `POST /api/valuations` record.
- For amount-valued assets, both `market_value` and `quantity` are stored as the current holding amount, with `price=1`.
- Positions, Performance, and Performance Audit prefer the latest `valuation_snapshots`; ledger quantity is only a fallback when no snapshot exists.

### Performance Data Audit

Performance Data Audit is the latest iteration for explaining where Performance page numbers come from and for finding mismatches against bank or broker data.

Implemented in this iteration:

- Backend `AuditService`: cash breakdown, asset breakdown, historical input breakdown, calculation trails, discrepancy detection, correction suggestions, audit report generation, and audit history.
- API routes: `GET /api/performance/audit`, `GET /api/performance/audit-history`, and `GET /api/performance/audit/{audit_id}`.
- Frontend page: `/performance/audit`, reachable from the sidebar `Audit` item or the `Audit Data` button on the Performance page.
- Export: the audit page can export the current report as JSON or CSV.

Frontend usage:

1. Start the API, then start the frontend.
2. Open `/performance/audit`.
3. Use `Currency` to audit one currency, or keep `All Currencies` for a full portfolio audit.
4. Enter bank or external-system values in `Expected Cash`, `Expected Assets`, and `Expected Value CNY`, then click `Compare`.
5. Review `Cash Breakdown`, `Asset Breakdown`, `Historical Input`, `Calculation Trail`, `Discrepancies`, and `Correction Suggestions`.
6. Open previous runs in `Audit History`, or export the current report with `JSON` / `CSV`.

Audit semantics:

- `Cash Breakdown` comes from `cash_ledger_entries`, grouped by event type with running balances; external CNY flows are excluded from cash balance.
- `Asset Breakdown` comes from `asset_ledger_entries` and the latest `valuation_snapshots`; amount-valued `BOND`, `FUND`, and `WEALTH_PRODUCT` records prefer the latest snapshot as the real current holding and use ledger quantity only as a fallback.
- `Historical Input` only includes `FX_BUY`, `FX_SELL`, `FX_SWAP`, and `MANUAL_ADJUSTMENT`, and shows whether RMB amount came from a direct field or was calculated from an FX rate.
- `Calculation Trail` shows formulas, input values, results, and exchange-rate source, timestamp, and estimated/missing status for Native Assets, Value CNY, Investment PnL, and FX PnL.
- `Discrepancies` are generated only when expected values are supplied; values beyond the default `0.01` threshold are labeled error/warning/info.
- `Correction Suggestions` point users toward cash ledger records, asset quantities/valuations, or historical input records based on the discrepant metric.

API examples:

```bash
curl "http://127.0.0.1:8000/api/performance/audit?user_id=1&currency=USD&expected_cash=10000&expected_value_cny=70000"
```

```bash
curl "http://127.0.0.1:8000/api/performance/audit-history?user_id=1&limit=20"
```

```bash
curl "http://127.0.0.1:8000/api/performance/audit/1?user_id=1"
```

Each `/api/performance/audit` call creates an `audit_logs` row with `entity_type = performance_audit`; the full report is stored at `details_json.audit_report`.

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
- `GET /api/positions` aggregates asset ledger entries and valuation snapshots; amount-valued assets use ledger entries as historical cost/subscription net amount and the latest valuation snapshot as the real current holding.
- `GET /api/performance` is the source of truth for portfolio-level value, net input, investment PnL, FX PnL, and data-quality flags.
- `GET /api/performance/audit` is the reconciliation surface for Performance numbers, returning source breakdowns, calculation trails, discrepancies, and correction suggestions.

Performance field semantics:

- `Native Assets` is current native cash plus current native value for assets with valuation or amount-based accounting.
- `Value CNY` is native value converted with the current CNY exchange rate.
- `Native Net Input` / `historical_net_invested_native` is the net native amount that entered a currency pool through `FX_BUY`, `FX_SELL`, `FX_SWAP`, and `MANUAL_ADJUSTMENT`. Fund/wealth purchases, redemptions, and dividends do not count as new external input. A negative value means that currency had net FX/manual outflow; it is not an asset loss.
- `Investment PnL` is asset-return PnL such as redemption gains, dividends, and valuation changes.
- `FX PnL` is CNY PnL caused by exchange-rate movement on the same native asset base.

Current Positions page semantics:

- The `Portfolio Overview` cards reuse `/api/performance`, so `Total PnL = Total Value - Total Cost = Investment PnL + FX PnL` is closed by definition.
- For non-CNY `CASH`, `FUND`, `WEALTH_PRODUCT`, and `BOND` rows, `Cost` now prefers native cost such as `1045 USD` instead of always showing CNY cost.
- Row-level foreign amount-valued asset attribution is:
  - `Investment PnL = (current native holding amount - native cost) × current FX rate`
  - `FX PnL = Total PnL - Investment PnL`
- Foreign `Cash` rows are still currency pools rather than per-account balances, so `Investment PnL` is fixed at `0` and `FX PnL` equals the full CNY PnL of that currency cash pool.
- The `Price/Rate` column shows the latest FX rate for cash rows and `1` for amount-valued snapshot rows because the snapshot currently stores current holding amount, not fund NAV/share quantity.

Current limitation:

- `GET /api/positions` still computes `cost_basis_cny` by summing each asset-ledger row's native amount times that row's own historical FX rate. It does not yet trace whether the foreign currency originally came from RMB FX, another foreign currency swap, or redemption from another foreign-currency asset.
- As a result, per-product `Investment PnL / FX PnL` is useful today, but per-product `cumulative invested RMB` is still a product-ledger accounting basis, not a provenance-aware funding basis. A dedicated funding-source allocation model is the next planned iteration.

Excel confirmed import is idempotent. It builds a semantic duplicate key from user, asset/event type, timestamp, currencies, quantities, prices, cash entries, and asset entries. Re-importing the same workbook skips existing records and returns `skipped_duplicate_count`.

Excel display formatting may hide seconds. The importer uses the underlying cell value, so rows that both display as `2024/6/25 0:55` can still be imported as distinct records when their raw serial timestamps differ, for example `00:55:00.000001` and `00:55:01`.

Manual entry semantics:

- `FOREX` creates a legacy transaction for CNY-vs-FX buy/sell records.
- `FX_SWAP` creates a portfolio event with two native cash legs.
- `FUND` and `WEALTH_PRODUCT` create portfolio events with native cash and asset ledger entries; non-CNY amounts are not written as `total_cost_cny`.
- `INTEREST_INCOME` creates a portfolio event that increases native cash only.

For amount-valued assets, ledger `quantity` is an audit trail for historical cost/subscription net amount. Use the `Snapshot` action on the `Positions` page, or call `POST /api/valuations`, to record the actual current holding used for current value and PnL.

For a full local re-import, keep the schema and clear only business data:

```bash
sqlite3 investment_tracker.db "PRAGMA foreign_keys=OFF; BEGIN; DELETE FROM asset_ledger_entries; DELETE FROM cash_ledger_entries; DELETE FROM valuation_snapshots; DELETE FROM portfolio_events; DELETE FROM transactions; DELETE FROM positions; DELETE FROM exchange_rates; DELETE FROM investment_advice; DELETE FROM audit_logs; DELETE FROM assets; DELETE FROM users; COMMIT; PRAGMA foreign_keys=ON;"
```

After re-importing, use `Transaction History -> Cash Balances -> Positions -> Performance -> Performance Audit` to reconcile the data lineage before manually adjusting records.

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

## Verification Commands

This Performance Data Audit iteration was verified with:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
cd frontend && npm run lint
```

## Day 2-7 Roadmap

- Day2: MCP tool abstractions and core tool implementations
- Day3: AI model client and investment advice engine
- Day4: reusable skills and evaluation harness
- Day5: API endpoints and orchestration workflows
- Day6: dashboard, export, and portfolio analysis
- Day7: hardening, demos, and documentation polish
