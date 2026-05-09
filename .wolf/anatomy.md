# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-05-09T06:51:36.770Z
> Files: 195 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.DS_Store` (~2732 tok)
- `.gitignore` — Git ignore rules (~69 tok)
- `.python-version` (~2 tok)
- `AGENTS.md` — OpenWolf Protocol (~142 tok)
- `alembic.ini` (~146 tok)
- `aud_bank_statement_extracted.csv` (~585 tok)
- `cad_bank_statement_extracted.csv` (~192 tok)
- `CLAUDE.md` — Investment Tracker — Claude Code (~534 tok)
- `gbp_bank_statement_extracted.csv` (~272 tok)
- `jpy_bank_statement_extracted.csv` (~693 tok)
- `pyproject.toml` — Python project configuration (~266 tok)
- `README.md` — Project documentation (~4346 tok)
- `README.zh-CN.md` — Intelligent Investment Tracker (~3018 tok)
- `usd_bank_statement_extracted.csv` (~3028 tok)
- `week7_flagship_project.html` (~5994 tok)

## .claude/

- `settings.json` (~441 tok)

## .claude/commands/

- `explore.md` (~132 tok)
- `map.md` (~145 tok)
- `pr.md` (~178 tok)

## .claude/rules/

- `openwolf.md` (~313 tok)

## .github/workflows/

- `ci.yml` — CI: ci (~116 tok)

## .kiro/specs/fx-funding-attribution/

- `.config.kiro` (~30 tok)
- `design.md` — Design Document: FX Funding Attribution and Cost Penetration (~10125 tok)
- `requirements.md` — Requirements Document: FX Funding Attribution and Cost Penetration (~2922 tok)
- `tasks.md` — Implementation Plan: FX Funding Attribution and Cost Penetration (~7253 tok)

## .kiro/specs/intelligent-investment-tracker/

- `.config.kiro` (~30 tok)
- `design.md` — 技术设计文档：智能外汇与债券投资追踪 Agent (~4964 tok)
- `requirements.md` — 需求文档：智能外汇与债券投资追踪 Agent (~2159 tok)
- `tasks.md` — 实现计划：智能外汇与债券投资追踪 Agent (~2751 tok)

## .kiro/specs/investment-tracker-frontend/

- `.config.kiro` (~30 tok)
- `design.md` — Design Document: Investment Tracker Frontend (~6715 tok)
- `requirements.md` — Requirements Document (~2393 tok)
- `tasks.md` — Implementation Plan: Investment Tracker Frontend (~5574 tok)

## .kiro/specs/performance-data-audit/

- `.config.kiro` (~30 tok)
- `design.md` — Design Document: Performance Data Audit (~7861 tok)
- `requirements.md` — Requirements Document (~3040 tok)
- `tasks.md` — Implementation Plan: Performance Data Audit (~4434 tok)

## alembic/

- `env.py` — run_migrations_offline, run_migrations_online (~446 tok)
- `script.py.mako` (~146 tok)

## alembic/versions/

- `0001_initial_schema.py` — 0001 initial schema (~2383 tok)
- `0002_v02_multi_currency_performance.py` — v0.2 multi-currency performance schema (~2423 tok)
- `0003_fx_funding_attribution.py` — fx funding attribution schema (~2379 tok)

## config/

- `logging.json` (~64 tok)
- `settings.example.toml` (~134 tok)

## demo/

- `__init__.py` — Demo fixtures and runnable showcase for Task 23. (~16 tok)
- `demo.py` — from: generate, build_demo_payloads, create_session, normalize_screenshot_transaction + 5 more (~2746 tok)

## demo/fixtures/

- `bond_buy_detail_ocr.txt` (~48 tok)
- `bond_sell_detail_ocr.txt` (~38 tok)
- `forex_list_ocr.txt` (~43 tok)
- `natural_language_inputs.json` (~34 tok)

## frontend/

- `index.html` — Investment Tracker (~83 tok)
- `package-lock.json` — npm lock file (~28981 tok)
- `package.json` — Node.js package manifest (~261 tok)
- `README.md` — Project documentation (~411 tok)
- `tsconfig.json` — TypeScript configuration (~167 tok)
- `tsconfig.node.json` (~93 tok)
- `tsconfig.node.tsbuildinfo` (~9506 tok)
- `tsconfig.tsbuildinfo` (~300 tok)
- `vite.config.d.ts` — Declares _default (~22 tok)
- `vite.config.js` — Vite build configuration (~130 tok)
- `vite.config.ts` — Vite build configuration (~109 tok)

## frontend/src/

- `App.tsx` — TransactionsPage (~512 tok)
- `main.tsx` — queryClient (~281 tok)
- `styles.css` — Styles: 1 rules (~103 tok)
- `theme.ts` — Exports theme (~168 tok)
- `vite-env.d.ts` — / <reference types="vite/client" /> (~11 tok)

## frontend/src/components/common/

- `DataTable.tsx` — DataTable — renders table (~840 tok)
- `LoadingSpinner.tsx` — LoadingSpinner (~100 tok)
- `SectionCard.tsx` — SectionCard (~134 tok)

## frontend/src/components/layout/

- `AppLayout.tsx` — navItems — renders chart, modal — uses useState, useMemo (~867 tok)

## frontend/src/features/advice/

- `AdvicePage.tsx` — actionButtons — renders form — uses useState, useMutation, useMemo (~2786 tok)

## frontend/src/features/agents/

- `AgentToolsPage.tsx` — AgentToolsPage — renders table — uses useState, useMutation, useQuery (~1256 tok)

## frontend/src/features/exchange-rates/

- `ExchangeRatesPage.tsx` — ExchangeRatesPage — renders table — uses useState, useQuery, useMutation (~1104 tok)

## frontend/src/features/imports/

- `ImportsPage.tsx` — previewKind — renders form, table — uses useState, useMutation, useMemo (~5128 tok)

## frontend/src/features/performance/

- `AuditPage.tsx` — initialExpectedDraft — renders form — uses useQuery, useMemo, useMutation (~6969 tok)
- `PerformancePage.tsx` — PerformancePage — renders table — uses useQuery (~2352 tok)

## frontend/src/features/positions/

- `PositionsPage.tsx` — valueColor — uses useState, useQuery (~4513 tok)

## frontend/src/features/transactions/

- `TransactionsPage.tsx` — MANUAL_ASSET_TYPES — renders form — uses useMutation (~8218 tok)

## frontend/src/hooks/

- `useDebounce.ts` — Exports useDebounce (~98 tok)
- `useNotification.ts` — Exports useNotification (~268 tok)

## frontend/src/services/

- `advice.ts` — Exports getAdvice, sendAdviceChat (~182 tok)
- `agents.ts` — Exports parseNaturalLanguageTransaction, getRiskAssessment (~181 tok)
- `api.ts` — Exports apiClient (~200 tok)
- `audit.ts` — Exports getAudit, getAuditHistory, getAuditDetail (~457 tok)
- `exchangeRates.ts` — Exports getLatestRates, refreshRates (~183 tok)
- `performance.ts` — Exports getPerformance (~96 tok)
- `positions.ts` — API routes: POST (1 endpoints) (~148 tok)
- `transactions.ts` — API routes: DELETE (1 endpoints) (~835 tok)

## frontend/src/types/

- `advice.ts` — Exports RiskPreference, AdviceAction, AdvicePayload, AdviceResponse + 3 more (~406 tok)
- `agents.ts` — Exports NaturalLanguageParseResponse, RiskAssessmentResponse (~244 tok)
- `api.ts` — Exports ApiError (~25 tok)
- `audit.ts` — Exports CashBreakdownEntry, CashBreakdown, AssetBreakdownEntry, AssetBreakdown + 18 more (~1179 tok)
- `exchangeRates.ts` — Exports ExchangeRate, ExchangeRateResponse (~76 tok)
- `performance.ts` — Exports PerformanceOverview, CurrencyPerformance, AssetTypePerformance, PerformanceDataQuality + 2 more (~531 tok)
- `positions.ts` — Exports Position, PositionSummary, PositionResponse, ValuationCreatePayload (~481 tok)
- `transactions.ts` — Exports AssetType, ManualAssetType, TradeDirection, TransactionDirection + 12 more (~1394 tok)

## frontend/src/utils/

- `constants.ts` — Exports API_TIMEOUT_MS, CACHE_MS, FILTER_DEBOUNCE_MS, PAGE_SIZE + 2 more (~70 tok)
- `formatting.ts` — Exports formatDate, formatTime, formatDateTime, formatRelativeTime + 4 more (~457 tok)
- `validation.ts` — Exports trimText, transactionSchema, TransactionFormValues (~535 tok)

## scripts/

- `backfill_fx_funding_attribution.py` — main (~400 tok)
- `backup_cli.py` — main (~392 tok)
- `dedupe_imported_events_by_transaction_id.py` — source_transaction_id, decimal_key, is_quantity_supplement, patch_keep_event + 4 more (~2567 tok)
- `excel_import_cli.py` — Local CLI for previewing, importing, and viewing Excel-derived transactions. (~1328 tok)
- `import_forex_excel.sh` (~114 tok)
- `init_db.py` — Initialize the local database schema. (~158 tok)
- `merge_duplicate_assets.py` — main (~987 tok)

## src/investment_tracker/

- `__init__.py` — Foundation package for the intelligent investment tracker. (~53 tok)
- `settings.py` — Application settings with environment-first configuration. (~1414 tok)

## src/investment_tracker/api/

- `__init__.py` — API layer package. (~33 tok)
- `main.py` — FastAPI application entrypoint. (~507 tok)
- `schemas.py` — Pydantic schemas for API payloads. (~1712 tok)

## src/investment_tracker/api/routes/

- `__init__.py` — API route packages. (~8 tok)
- `advice.py` — Investment advice API routes. (~7022 tok)
- `exchange_rates.py` — Exchange-rate API routes. (~530 tok)
- `performance.py` — Portfolio performance and v0.2 ledger API routes. (~3555 tok)
- `positions.py` — Position-related API routes. (~6336 tok)
- `transactions.py` — Transaction-related API routes. (~6612 tok)

## src/investment_tracker/data/

- `__init__.py` — Data access package. (~8 tok)
- `asset_identity.py` — Asset identity resolution for imported product names. (~639 tok)
- `base.py` — SQLAlchemy base declarations. (~142 tok)
- `db.py` — Database engine and session helpers. (~328 tok)
- `enums.py` — Shared enum types for the persistence layer. (~586 tok)
- `models.py` — ORM models for the Day1 schema. (~4698 tok)
- `repositories.py` — Repository helpers for transactions and related records. (~3916 tok)
- `services.py` — Domain services for portfolio and exchange-rate workflows. (~31965 tok)

## src/investment_tracker/mcp_tools/

- `__init__.py` — MCP tools package. (~429 tok)
- `base.py` — Base abstractions for MCP-style tools. (~1227 tok)
- `exchange_rate_tool.py` — Exchange rate lookup with retry and cache support. (~3384 tok)
- `investment_advisor_tool.py` — Generate structured investment advice from holdings and market context. (~1293 tok)
- `nlp_tool.py` — Rule-based natural language transaction parsing. (~2634 tok)
- `ocr_tool.py` — OCR tool with pluggable engine strategies. (~1655 tok)
- `position_calculator_tool.py` — Position calculator using weighted average cost. (~1132 tok)
- `server.py` — Server-side registry and dispatch for MCP-style tools. (~290 tok)
- `transaction_parser_tool.py` — Parse OCR text into structured transaction data. (~1780 tok)

## src/investment_tracker/orchestration/

- `__init__.py` — Orchestration package. (~114 tok)
- `context_manager.py` — Manage rolling orchestration context and approximate token budgets. (~322 tok)
- `excel_import_service.py` — Excel preview import service for forex transaction sheets. (~12126 tok)
- `screenshot_import_service.py` — Batch screenshot import preview workflow. (~1044 tok)
- `skills_router.py` — Route higher-level tasks to skills and tools. (~470 tok)
- `task_planner.py` — Simple task planner for routing user workflows. (~219 tok)
- `tool_selector.py` — Select tools for a given task and apply simple fallback policy. (~281 tok)

## src/investment_tracker/skills/

- `__init__.py` — Skills package. (~212 tok)
- `base.py` — Base abstractions for reusable AI skills. (~1402 tok)
- `investment_advice_skill.py` — Skill for portfolio-level investment advice. (~526 tok)
- `natural_language_understanding_skill.py` — Skill for extracting transaction parameters from natural language. (~370 tok)
- `ocr_parsing_skill.py` — Skill for extracting structured transaction data from OCR text. (~384 tok)
- `risk_assessment_skill.py` — Skill for assessing portfolio risk. (~444 tok)
- `transaction_analysis_skill.py` — Skill for analyzing transaction patterns and anomalies. (~468 tok)

## src/investment_tracker/utils/

- `__init__.py` — Utility package. (~7 tok)
- `agent_run_logger.py` — Readable per-run logging for AI agent workflows. (~1279 tok)
- `ai_client.py` — Unified AI client for Claude and DeepSeek style providers. (~2919 tok)
- `backup.py` — JSON snapshot backup helpers for persisted data. (~1229 tok)
- `logger.py` — Structured logging configuration. (~826 tok)
- `validators.py` — Validation helpers for transaction and portfolio data. (~344 tok)
- `xlsx_reader.py` — Minimal XLSX reader based on the standard library. (~1333 tok)

## tests/

- `conftest.py` (~76 tok)
- `test_agent_run_logger.py` — Tests: agent_run_logger_writes_readable_markdown (~273 tok)
- `test_ai_client.py` — Tests: claude_generate, deepseek_generate, ai_client_retries_on_retryable_error, ai_client_budget_enforced + 1 more (~1029 tok)
- `test_api_transactions.py` — Tests: import_excel_preview_endpoint, import_excel_preview_rejects_empty_body, import_excel_confirm_persists_ready_rows (~708 tok)
- `test_asset_purchase_attribution.py` — Tests: foreign_asset_purchase_records_attributed_cost_from_funding_lot_not_spot_rate, positions_use_attributed_cost_when_available, multiple_foreig... (~1637 tok)
- `test_asset_redemption_attribution.py` — Tests: redemption_reduces_product_attribution_fifo_and_creates_inherited_basis_lot, redemption_without_attribution_keeps_spot_basis_fallback (~1792 tok)
- `test_attribution_api_and_performance.py` — Tests: product_performance_uses_attributed_cost_and_closes_pnl_decomposition, product_performance_flags_incomplete_attribution_but_keeps_native_pnl... (~2155 tok)
- `test_attribution_rebuild_service.py` — Tests: rebuild_user_attribution_replays_existing_events_without_duplicates, rebuild_marks_incomplete_data_without_fabricating_lineage, valuation_sn... (~1280 tok)
- `test_attribution_status_tracker.py` — Tests: cny_asset_attribution_status_is_not_applicable, foreign_asset_with_attribution_and_no_gaps_is_complete, foreign_asset_with_unresolved_gap_is... (~1326 tok)
- `test_attribution_store.py` — Tests: record_allocation_is_queryable_by_event_and_asset, trace_to_origin_walks_fx_swap_consumption_chain, trace_to_origin_detects_cycles (~1398 tok)
- `test_audit_service.py` — Tests: cash_breakdown_groups_entries_and_tracks_running_balance, cash_breakdown_excludes_cny_external_flows_from_balance, asset_breakdown_uses_late... (~5190 tok)
- `test_backup.py` — Tests: create_backup_snapshot_after_transaction_write, restore_backup_rebuilds_tables (~931 tok)
- `test_checkpoint.py` — Tests: checkpoint_health_and_openapi (~153 tok)
- `test_day5_api_routes.py` — Tests: create_and_list_transactions, transaction_history_includes_v2_events_and_filters_asset_text, delete_event_removes_attribution_dependencies, ... (~9726 tok)
- `test_demo_flow.py` — Tests: demo_flow_runs_end_to_end (~110 tok)
- `test_e2e.py` — Tests: screenshot_to_parse_flow, nlp_to_parse_flow, position_to_advice_flow, eval_fixture_has_ten_cases (~1139 tok)
- `test_excel_import_service.py` — Tests: excel_import_preview_builds_ready_pending_and_failed_groups, excel_import_cross_currency_builds_swap_event_without_cny_estimate, excel_impor... (~4331 tok)
- `test_exchange_rate_tool.py` — Tests: exchange_rate_history_lookup, frankfurter_provider_fetches_exact_historical_rate, frankfurter_provider_accepts_rates_map_response, frankfurt... (~1347 tok)
- `test_funding_lot_manager.py` — Tests: create_lot_sets_available_status_and_basis_fields, create_lot_without_basis_is_excluded_from_available_lots, get_available_lots_uses_fifo_or... (~1949 tok)
- `test_funding_source_events.py` — Tests: fx_buy_event_creates_funding_lot_with_direct_rmb_basis, fx_swap_consumes_source_lot_and_creates_target_lot_with_inherited_basis, fx_sell_con... (~2025 tok)
- `test_investment_advisor_tool.py` — Tests: generate_investment_advice, risk_preference_is_reflected_in_summary, invalid_ai_output_format_returns_error (~992 tok)
- `test_logger.py` — Tests: configure_logging_creates_log_file, get_logger_returns_named_logger (~261 tok)
- `test_lot_allocation_engine.py` — Tests: fifo_allocation_consumes_oldest_lots_first, allocation_creates_gap_when_funding_is_insufficient, multi_lot_allocation_conserves_native_amoun... (~1606 tok)
- `test_mcp_server.py` — Tests: server_registers_and_calls_tool, server_lists_tool_metadata (~222 tok)
- `test_migrations.py` — Tests: alembic_upgrade_head (~296 tok)
- `test_models.py` — Tests: all_tables_are_created, transaction_insert_and_query, position_insert_and_update, exchange_rate_boolean_and_precision + 3 more (~2301 tok)
- `test_nlp_tool.py` — Tests: parse_chinese_trade_input, parse_english_trade_input, parse_missing_fields, parse_relative_date_and_cny_trade + 1 more (~570 tok)
- `test_ocr_tool.py` — Tests: ocr_tool_extracts_text_from_base64, ocr_tool_flags_low_confidence_review (~434 tok)
- `test_orchestration.py` — Tests: task_planner_produces_steps, tool_selector_maps_task_to_tools, context_manager_rolls_events, skills_router_executes_skill_and_tool (~736 tok)
- `test_performance_service.py` — Tests: performance_includes_foreign_cash_and_splits_fx_pnl, fx_swap_changes_currency_pools_without_external_cny_flow, performance_splits_closed_fun... (~2996 tok)
- `test_performance_smoke.py` — Tests: ocr_smoke_performance, exchange_rate_smoke_performance, batch_parse_smoke_performance (~409 tok)
- `test_position_calculator_tool.py` — Tests: weighted_average_cost_for_forex, sell_reduces_position_and_cost_basis, sell_more_than_position_fails (~782 tok)
- `test_screenshot_import_service.py` — Tests: screenshot_import_preview_parses_batch, screenshot_import_limits_batch_size (~290 tok)
- `test_settings.py` — Tests: default_settings_load, environment_variables_override_defaults, invalid_ocr_confidence_threshold_raises, invalid_log_level_raises (~282 tok)
- `test_skills.py` — Tests: skill_registry_tracks_metadata, ocr_parsing_skill, transaction_analysis_skill, investment_advice_skill + 5 more (~1543 tok)
- `test_transaction_parser_tool.py` — Tests: parse_forex_transaction, parse_bond_transaction, parse_bond_detail_screenshot_text, parse_transaction_missing_fields (~530 tok)
- `test_transaction_repository.py` — Tests: repository_bootstraps_user_and_creates_transactions (~389 tok)
- `test_upload_route.py` — Tests: upload_route_returns_review_summary (~200 tok)
- `test_xlsx_reader.py` — Tests: xlsx_reader_extracts_sheet_names_and_rows (~161 tok)

## tests/fixtures/

- `day4_eval_cases.json` (~620 tok)
