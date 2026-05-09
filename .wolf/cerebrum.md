# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-05-09

## User Preferences

- **Language**: 用中文和用户交流，代码和注释用英文
- **Response style**: 简洁，不需要在回复末尾总结"刚才做了什么"——用户可以自己看代码差异
- **Autonomy**: 高信任、低打断风格。委托完整的工作单元，期望 Claude 自主执行到完成再汇报，不需要每步确认
- **Staged refactoring**: 偏好把大改动拆成独立步骤（Step A/B/C），每步独立通过测试后再推进

## Key Learnings

### 工具链
- **uv 路径**: `/opt/anaconda3/bin/uv`（不在系统 PATH，需要写全路径）
- **运行测试**: `/opt/anaconda3/bin/uv run pytest --tb=short -q`
- **Lint**: `/opt/anaconda3/bin/uv run ruff check .`
- **Python**: 系统有 `/usr/bin/python3`（3.9.6）但项目用 venv 里的，通过 `uv run` 调用

### 已知的测试失败（与代码无关）
以下 4 个测试因缺少 `investment_tracker_v5.xlsx` fixture 文件而持续失败，不是代码问题：
- `tests/test_api_transactions.py::test_import_excel_preview_endpoint`
- `tests/test_api_transactions.py::test_import_excel_confirm_persists_ready_rows`
- `tests/test_excel_import_service.py::test_excel_import_preview_builds_ready_pending_and_failed_groups`
- `tests/test_xlsx_reader.py::test_xlsx_reader_extracts_sheet_names_and_rows`

### 架构约定（LLM-as-Orchestration 迭代后）
- **Skills** = 声明式 MD 文件（`src/investment_tracker/skills/specs/*.md`），不是 Python 类
- **SkillSpec** = 数据类（noun），只描述；**SkillRunner** = 执行器（verb），只运行
- **OrchestrationContainer** 在 FastAPI lifespan 里构建，挂到 `app.state.orchestration`
- **`/api/advice`** 调用 `request.app.state.orchestration.skill_runner.run("investment_advice_skill", payload)`
- **investment_advice_skill** 的 AI 输出格式是 `{advice: {...}, portfolio_summary: {...}}`（两层，非扁平）
- **LLMOrchestrator** 框架已就位，但未挂 HTTP 路由——是 `/api/advice` 接入自然语言的未来归宿

### Jinja2 双环境（SkillRunner 关键细节）
- `NativeEnvironment`：用于 args 渲染和条件表达式，**保留 Python 类型**（int/list/dict 不变成字符串）
- 普通 `Environment`：用于 prompt 渲染，返回字符串
- 混用是故意的，不要"统一"成一种

### OpenWolf + Claude Code
- CLAUDE.md 的 `@file` 语法是 Cursor/Kiro 特有的，Claude Code 不会 auto-include
- Claude Code 在 worktree 路径（`.claude/worktrees/`）下运行时，项目根目录的 CLAUDE.md 不一定被自动加载
- `anatomy.md` 应排除 `.venv/`、`.pytest_cache/`、`.ruff_cache/`，否则 token 浪费严重

## Do-Not-Repeat

- **[2026-05-09]** 在 worktree 里开发前，必须同时检查 **两个**工作目录的状态，仅检查 worktree 是不够的：
  ```bash
  git status                                                        # worktree（当前目录）
  git -C ~/CursorProjects/investment-assistant status              # 主工作目录（main 分支）
  ```
  原因：worktree 和主目录各自独立，`git status` 只显示当前所在目录的状态，主目录的未提交修改不可见。主目录有脏状态时 PR merge 后 `git pull` 会触发冲突。

- **[2026-05-09]** 不要在 CLAUDE.md 里用 `@file` 引用——Claude Code 不解析此语法，必须内联内容
- **[2026-05-09]** 不要把 SkillSpec 设计成有 `execute()` 方法——Skill 是数据（noun），Runner 才执行（verb）
- **[2026-05-09]** `anatomy.md` 扫描时要排除 `.venv/` 等构建产物目录，否则 515 个文件里大多数是包内部文件，没有价值

## Decision Log

- **[2026-05-09] Skills 改为 MD 声明式文件**：替代 Python Skill 类，原因是把"什么"（spec）和"怎么执行"（runner）分离，让 pre_tools/short_circuit/on_failure 等逻辑在 frontmatter 里声明而非代码里硬写，方便非工程师修改 prompt 和组合逻辑
- **[2026-05-09] LLMOrchestrator 只做框架，不挂路由**：当前 `/api/advice` 仍是固定调 SkillRunner（知道要用哪个 Skill），LLMOrchestrator 留给未来自然语言入口，让 LLM 自主选择 Skill
- **[2026-05-09] PortfolioSummaryTool 从 InvestmentAdvisorTool 重命名**：原名暗示包含 AI，实际是纯确定性计算（FIFO cost basis + summary），重命名让工具层（确定性）和 Skill 层（AI）的边界更清晰
- **[2026-05-09] generate_with_tools 用 Anthropic 格式作为 canonical messages 格式**：Claude 原生支持，DeepSeek 调用时在内部转为 OpenAI function calling 格式，调用方不感知差异
