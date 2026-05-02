# Intelligent Investment Tracker

[English](./README.md) | 简体中文

一个面向多币种现金、外汇、基金、理财与债券投资场景的智能投资跟踪系统，围绕 FastAPI API、MCP 风格工具、导入工作流、组合级 ledger 和 AI 辅助分析构建。

## 当前状态

当前项目已经包含：

- 交易、组合事件、持仓、现金余额、Performance、投资建议、汇率的 FastAPI 接口
- Excel 交易表的预览导入与确认导入，支持外汇、跨币种换汇、基金、理财、结息和定期类现金收入
- 面向外汇和债券截图的 OCR 预览工作流
- 面向常见中文交易表达的自然语言解析
- SQLAlchemy 持久化、审计日志，以及每次成功数据更新后的自动备份
- v0.2 多币种 ledger：`portfolio_events`、`cash_ledger_entries`、`asset_ledger_entries`、`valuation_snapshots`
- Demo 素材与可直接运行的端到端演示脚本
- Alembic 迁移、pytest 测试和 Ruff 静态检查

当前限制：

- 截图解析仍然是规则驱动，更适合当前已支持的截图/文本格式
- Demo 中的投资建议使用本地 stub；真实建议接口仍依赖已配置的 AI 凭证
- 实时定时汇率刷新功能尚未完成
- 组合级口径以 v0.2 ledger 为准；旧 `transactions` 表主要保留给 legacy 外汇交易与兼容展示

## 架构概览

项目分为四层：

1. API 层：FastAPI 接口与请求处理
2. 编排层：导入流程与工作流协调
3. 工具层：OCR、解析、定价与建议工具
4. 数据层：配置、日志、持久化、备份与迁移

## 技术栈

- Python 3.9+
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic Settings
- Pytest
- Ruff

## 目录结构

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

## 本地开发

### 1. 安装依赖

```bash
uv sync
```

如果当前环境里 `uv` 不能写默认缓存目录，可以这样运行：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，再按需要修改。

### 3. 运行测试

```bash
uv run pytest
```

### 4. 运行静态检查

```bash
uv run ruff check .
```

## 启动 API

FastAPI 应用对象在 `investment_tracker.api.main:app`。

先同步依赖，再启动 API：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn investment_tracker.api.main:app --reload
```

启动后可访问：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

## 数据库迁移

升级到最新 schema：

```bash
uv run python -m alembic upgrade head
```

后续创建新的迁移：

```bash
uv run python -m alembic revision -m "describe change"
```

直接通过 ORM metadata 初始化数据库：

```bash
uv run python scripts/init_db.py
```

## API 概览

主要接口：

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

v0.2 起，组合级真实盈亏以 `/api/performance` 为准。该接口基于现金流水、资产流水、当前估值和最新汇率计算：

- 当前总资产 RMB
- 累计净投入 RMB
- 真实总盈亏 RMB
- 投资收益 RMB
- 汇率收益 RMB
- 按币种拆分
- 按资产类别拆分
- 缺失汇率、缺失估值、估算值等数据质量提示

## 数据链路与计算口径

排查任何页面数字时，按以下链路定位，不直接以页面数字为准：

```text
源数据文件/截图 -> import preview/parser -> transactions 或 portfolio_events
-> cash_ledger_entries / asset_ledger_entries / valuation_snapshots / exchange_rates
-> aggregation service -> API response -> UI display
```

当前权威口径：

- `GET /api/transactions` 是历史展示接口，会合并 legacy `transactions` 和 v0.2 `portfolio_events`。外汇 CNY 买卖仍可能来自 `transactions`；基金、理财、结息、定期、跨币种换汇优先来自 `portfolio_events`。
- `GET /api/positions` 对金额型资产（`BOND`、`FUND`、`WEALTH_PRODUCT`）按资产 ledger 聚合历史数量/金额；是否有当前市值取决于估值快照。
- `GET /api/cash-balances` 只看现金 ledger，排除外部 CNY 注入类现金流，适合核对银行账户原币余额。
- `GET /api/performance` 是组合级真实盈亏权威接口，使用现金流水、资产流水、估值和汇率，不以单个 Transaction History 的 Total Cost 展示为准。

Performance 字段口径：

- `Native Assets`：按币种汇总当前现金余额和有估值/金额口径资产的原币价值。
- `Value CNY`：原币资产价值乘以对应汇率后的人民币价值；缺汇率时会产生数据质量提示。
- `Native Net Input`：按币种统计外部净投入，不把组合内部换汇、买基金、买理财当成新增本金。
- `Investment PnL`：资产投资本身带来的收益，例如理财赎回、基金分红、估值变化。
- `FX PnL`：同一原币资产因汇率变化带来的人民币盈亏。
- `FX Rate`：用于当前估值折算的最新汇率或估算汇率。

## 导入与去重口径

Excel 工作簿支持的核心字段包括：`交易ID`、`交易时间`、`类别`、`名称`、`卖出货币`、`卖出金额`、`买入货币`、`买入金额`、`备注`。

类别映射：

- `外汇`：CNY 与外币买卖写入 legacy `transactions`，同时生成兼容现金 ledger；外币和外币之间写入 `FX_SWAP` 事件。
- `基金`：写入 `FUND_BUY`、`FUND_SELL` 或 `FUND_DIVIDEND` 事件。
- `理财`：写入 `WEALTH_BUY` 或 `WEALTH_REDEEM` 事件。
- `结息`：写入 `INTEREST_INCOME` 事件。
- `定期`：写入 `WEALTH_INCOME` 事件。

确认导入是幂等的：同一文件重复导入时，服务会基于用户、资产/事件类型、时间、币种、金额、数量、单价、现金流水和资产流水生成语义 key，并跳过已存在的记录。确认结果会返回 `skipped_duplicate_count`。

注意：Excel 单元格显示时间可能隐藏秒和浮点精度。系统按单元格底层值解析时间。例如 `2024/6/25 0:55` 可能分别对应 `2024-06-25 00:55:00.000001` 和 `2024-06-25 00:55:01`。如果两行交易 ID 不同、底层时间不同，即使界面显示到分钟相同，也会被视为两条来源记录。此前核对过的例子：

- 第 26 行 `WM045`：`2024-06-25 00:55:00.000001`，`1000 USD`
- 第 463 行 `WM055`：`2024-06-25 00:55:01`，`1000 USD`

如果业务上确认其中一条是误补重复，应删除源 Excel 行或删除对应 `portfolio_events` 记录，而不是依赖导入器把不同交易 ID 的记录自动合并。

## 手动录入口径

前端 Manual Entry 当前支持：

- `FOREX`：仍走 `POST /api/transactions`，适合 CNY 和外币之间的买卖记录。
- `FX_SWAP`：走 `POST /api/portfolio-events`，记录卖出币种现金减少和买入币种现金增加，不填写人民币成本。
- `FUND`、`WEALTH_PRODUCT`：走 `POST /api/portfolio-events`，按原币现金流和资产 ledger 入账。非 CNY 金额不会写入 `total_cost_cny`，Transaction History 会显示 `1,000 USD` 这类原币金额。
- `INTEREST_INCOME`：走 `POST /api/portfolio-events`，只增加对应币种现金，用于结息。

金额型资产的 `quantity` 在当前系统里是审计用历史金额/份额，不等同于最终展示的“当前市值”。当前持仓价值需要结合估值快照或赎回/收入事件计算。

## 清库重导

如果需要重新梳理全量数据链路，可以清空业务表后重新导入。清库时保留 schema 和 `alembic_version`，只清空：

```text
users
assets
transactions
portfolio_events
cash_ledger_entries
asset_ledger_entries
positions
exchange_rates
valuation_snapshots
investment_advice
audit_logs
```

清库后从 Excel 重新导入，再按 `Transaction History -> Cash Balances -> Positions -> Performance` 的顺序核对。不要在未核对源数据前手动修页面数字。

本地 SQLite 清库命令：

```bash
sqlite3 investment_tracker.db "PRAGMA foreign_keys=OFF; BEGIN; DELETE FROM asset_ledger_entries; DELETE FROM cash_ledger_entries; DELETE FROM valuation_snapshots; DELETE FROM portfolio_events; DELETE FROM transactions; DELETE FROM positions; DELETE FROM exchange_rates; DELETE FROM investment_advice; DELETE FROM audit_logs; DELETE FROM assets; DELETE FROM users; COMMIT; PRAGMA foreign_keys=ON;"
```

示例：创建一笔交易

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

## Excel 快速导入

预览工作簿中的交易工作表：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/excel_import_cli.py preview investment_tracker_v5.xlsx
```

把可确认记录导入本地数据库：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/excel_import_cli.py import investment_tracker_v5.xlsx --user-id 1
```

查看最近导入的交易：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/excel_import_cli.py show --user-id 1 --limit 20
```

也可以使用 shell 包装脚本：

```bash
./scripts/import_forex_excel.sh preview investment_tracker_v5.xlsx
```

## 备份与恢复

每次成功的数据更新后，系统默认会在 `backups/` 下生成一个 JSON 快照。当前会覆盖这些写路径：

- 交易写入
- 持仓快照持久化
- 汇率刷新

手动创建备份：

```bash
uv run python scripts/backup_cli.py create --reason manual_snapshot
```

查看备份列表：

```bash
uv run python scripts/backup_cli.py list
```

从备份文件恢复：

```bash
uv run python scripts/backup_cli.py restore backups/<backup-file>.json
```

## Demo

运行当前的 Day5/Day6 demo 流程：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python demo/demo.py
```

Demo 覆盖：

- 债券详情截图 -> OCR fallback -> 解析 -> 交易入库
- 外汇列表截图 -> OCR 预览 -> 待人工确认示例
- 自然语言交易输入 -> 解析 -> 交易入库
- 持仓聚合 -> 本地 stub 投资建议生成

Demo 产物：

- 素材目录：`demo/fixtures/`
- 生成的 sqlite 数据库：`demo/artifacts/demo.db`

## Day 2-7 路线图

- Day2：MCP 工具抽象与核心工具实现
- Day3：AI 模型客户端与投资建议引擎
- Day4：可复用 skills 与评测框架
- Day5：API 端点与编排工作流
- Day6：看板、导出与组合分析
- Day7：加固、演示与文档整理
