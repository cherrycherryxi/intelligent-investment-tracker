# Memory

> Chronological action log. Hooks and AI append to this file automatically.
> Old sessions are consolidated by the daemon weekly.

- 2026-05-05: Cleaned confirmed duplicate portfolio events after Excel import timestamp normalization issue. Backed up `investment_tracker.db` to `backups/investment_tracker.before-confirmed-duplicate-cleanup-20260505.db`, deleted 56 duplicate `portfolio_events` while preserving one event per full event signature, rebuilt FX funding attribution, and verified duplicate event-signature groups are now 0. Current post-cleanup counts: 503 portfolio events, 302 funding lots, 541 lot consumptions, 316 attributions.
- 2026-05-05: Removed one additional USD cash duplicate not caught by same-second signature matching: duplicate `FX_BUY` USD 50 / CNY 345.34 on 2026-04-02. Backed up to `backups/investment_tracker.before-usd-duplicate-fx-buy-50-cleanup.db`, deleted event 566, rebuilt attribution, and verified USD Cash position is now 814.42 USD.
- 2026-05-05: Fixed Performance overview to ignore stale valuation snapshots for closed assets. `PerformanceService._latest_valuations` now filters valuations to assets with non-zero current ledger quantity, aligning Performance current assets with Positions total value while keeping Total PnL and Unrealized Investment PnL as separate reporting口径.
- 2026-05-06: Implemented frontend/backend usability fixes for AI/Agent surfaces. Performance now renders a table of `realized_closed_positions` so Realized Investment PnL can be audited. Advice API now reuses current Positions ledger口径 and returns a local rule-based fallback by default instead of failing when AI provider access is unavailable. Added `/agent-tools` frontend page plus API helpers for natural-language transaction parsing and local risk assessment.
- 2026-05-06: Fixed amount-valued fund open/closed classification when redemption-share imports make ledger quantity clamp to zero but a latest positive valuation snapshot exists. Positions now keeps those assets visible using snapshot quantity/value while exposing `ledger_quantity=0` for audit; Performance excludes them from `realized_closed_positions` and includes their snapshot market value. Verified affected local DB products `FUND-2B2230827F26` and `FUND-2DC8FAF3476B` now appear in Positions and are no longer in the closed queue.
- 2026-05-06: Reworked Advice into an AI-backed chat surface. Added `/api/advice/chat` with modes `generate_advice`, `position_analysis`, `transaction_analysis`, and free-form chat, all routed through AI skills/AIClient instead of local rule fallback. Frontend Advice page now has a chat transcript, risk-preference selector, and quick action buttons for generating advice, analyzing positions, and analyzing transactions.
- 2026-05-06: Fixed Advice position-analysis timeout path. Stopped the extra Vite dev server on port 4174 and kept the user's existing port 4173 server. Increased frontend API timeout to 120s to match 90s AI requests, compacted Advice AI payloads to the top position/transaction fields, and made chat-mode AI calls use one request attempt instead of multiple long retries.
- 2026-05-06: Improved Advice AI response UX. Updated investment advice, risk assessment, and transaction analysis skill prompts to require Chinese string values in JSON outputs. Frontend Advice chat now post-processes structured AI JSON into readable Chinese sections such as conclusion, risk level, key risks, actions, diversification suggestions, anomalies, and warnings instead of displaying raw JSON.
- 2026-05-06: Hardened AI skill JSON parsing after Advice returned `investment advice skill returned invalid JSON`. Added shared `parse_json_object_response` helper that tolerates markdown code fences, leading prose, and trailing model commentary before extracting a JSON object; investment advice, risk assessment, and transaction analysis skills now use it.
- 2026-05-06: Added Advice/Agent AI logging and graceful parse fallback. `/api/advice/chat` now logs `advice_ai_request_started`, `advice_ai_request_succeeded`, `advice_ai_parse_failed`, and `advice_ai_request_failed` with mode, counts, elapsed time, error code, and raw response excerpts. Invalid structured JSON no longer fails the chat; the UI receives the raw AI text plus parse warnings while logs retain the diagnostic excerpt.
- 2026-05-06: Wired FastAPI startup to initialize structured logging via `configure_logging(get_settings())`, so the application now creates `logs/app.log` and captures Advice/Agent AI log events at runtime.
- 2026-05-06: Added human-readable Agent run logs under `logs/agent_runs/YYYY-MM-DD.md`. `/api/advice/chat` now opens a run context, and AI client, skill, MCP tool, and skills-router boundaries append Markdown events with orchestration context, selected skill/tool, full model payload, raw response, parsed result, and endpoint response. Sensitive header/API-key fields are redacted.
- 2026-05-06: Improved Advice Agent model inputs after DeepSeek reasoning exhausted the previous 1800-token output cap. `/api/advice/chat` now builds a business-oriented `analysis_context` with field glossary, portfolio summary, currency/asset-type exposure, top positions, recent activity summaries, and analysis rules. Advice/Risk/Transaction skills now prompt from that context, constrain output shape, avoid detailed chain-of-thought, and use larger max-token caps for reasoning models.

## Session: 2026-05-07 18:03

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|

## Session: 2026-05-07 18:03

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|

## Session: 2026-05-07 18:12

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|

## Session: 2026-05-07 18:13

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|

## Session: 2026-05-07 18:13

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|

## Session: 2026-05-09

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 10:00 | Step B: API 层切换到 SkillRunner，删除旧 Python Skill 类 | `api/main.py`, `api/routes/advice.py`, `orchestration/container.py`, 5×old skill files, 3×orchestration files | 164 tests passing | ~15k |
| 10:30 | Step C: LLMOrchestrator + generate_with_tools | `utils/ai_client.py`, `orchestration/llm_orchestrator.py`, `tests/test_llm_orchestrator.py` | 171 tests passing | ~8k |
| 11:00 | 创建 PR #1 via GitHub MCP | — | https://github.com/cherrycherryxi/intelligent-investment-tracker/pull/1 | ~1k |
| 11:30 | 修复 OpenWolf + Claude Code 集成 | `CLAUDE.md`, `.wolf/anatomy.md`, `.wolf/cerebrum.md` | CLAUDE.md 内联协议；anatomy.md 从 515 条精简到 ~70 条 | ~5k |

## Session: 2026-05-09 14:16

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
