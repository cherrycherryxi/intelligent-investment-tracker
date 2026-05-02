# Investment Tracker Frontend

独立的 React + TypeScript 单页应用，负责调用现有 FastAPI 后端接口，不直接依赖任何 Python 模块或数据库实现。

## 目录边界

- `frontend/src/services/*`：唯一的 API 访问层
- `frontend/src/features/*`：页面和业务交互
- `src/investment_tracker/*`：现有后端代码，不被前端直接引用

## 本地运行

1. 安装依赖

```bash
cd frontend
npm install
```

2. 启动后端 API

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn investment_tracker.api.main:app --reload
```

3. 启动前端开发服务器

```bash
cd frontend
npm run dev
```

默认会通过 Vite 代理把 `/api` 请求转发到 `http://127.0.0.1:8000`。

## 环境变量

- `.env.development`
  - `VITE_API_BASE_URL=` 留空时走同源代理
- `.env.production`
  - `VITE_API_BASE_URL=http://localhost:8000`

## 功能覆盖

- 交易列表、筛选、前端分页、详情弹窗
- 手动创建交易和组合事件
- Excel 预览导入与确认导入，确认结果会显示写入数量和跳过重复数量
- 截图 OCR 预览、编辑、确认写入
- 持仓总览与筛选
- 投资建议请求与结构化展示
- 汇率查看与刷新

## 页面口径

### Transaction History

交易历史页展示的是合并结果：

- legacy `transactions`
- v0.2 `portfolio_events`

外汇 CNY 买卖可能来自 legacy 交易表；跨币种换汇、基金、理财、结息等来自 portfolio event。`Total Cost` 优先展示人民币成本；没有人民币成本时展示原币金额，例如 `1,000 USD`。

### Manual Entry

手动录入类型当前口径：

- `FOREX`：创建 legacy transaction，适合 CNY 与外币之间的买卖。
- `FX_SWAP`：创建 portfolio event，填写卖出币种/金额和买入币种/金额，不需要人民币汇率。
- `FUND`、`WEALTH_PRODUCT`：创建 portfolio event，按原币现金流和资产流水入账。非 CNY 金额不会被当成 `total_cost_cny`。
- `INTEREST_INCOME`：创建 portfolio event，只增加对应币种现金，用于结息。

### Import

Excel 预览只展示解析结果；真正写库发生在 Confirm Import。确认导入会做语义去重，同一批或已入库的重复记录会被跳过，并通过 `skipped_duplicate_count` 返回。

Excel 表格显示时间可能只显示到分钟，但底层值可能包含秒或浮点精度。两个看起来都是 `2024/6/25 0:55` 的单元格，如果底层分别是 `00:55:00.000001` 和 `00:55:01`，前端会显示成两条不同时间的记录。这通常表示源表里实际有两条不同交易 ID 的行。

## 命令

```bash
npm run dev
npm run build
npm run preview
npm run lint
```
