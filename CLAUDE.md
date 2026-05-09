# Investment Tracker — Claude Code

This project uses OpenWolf for context management.

## OpenWolf Protocol (applied every session)

### Before reading files
Check `.wolf/anatomy.md` first — it has a 2-3 line description and token estimate for every project file.
If the description is sufficient, do NOT read the full file.

### Before generating code
Read `.wolf/cerebrum.md` and respect every entry:
- `## Do-Not-Repeat` — past mistakes that must not recur
- `## Key Learnings` — project conventions and patterns
- `## User Preferences` — how the user wants things done

### After significant actions
Append a one-line entry to `.wolf/memory.md`:
`| HH:MM | description | file(s) | outcome | ~tokens |`

### After fixing bugs
Log to `.wolf/buglog.json`. Read it first before fixing — the fix may already be known.

### Learning (mandatory)
Update `.wolf/cerebrum.md` whenever you learn something from this session:
- User corrections → `## User Preferences`
- Project conventions → `## Key Learnings`
- Mistakes made → `## Do-Not-Repeat` (with date)
- Architecture decisions → `## Decision Log`

---

## Project Commands

- **Run tests:** `/opt/anaconda3/bin/uv run pytest --tb=short -q`
- **Lint:** `/opt/anaconda3/bin/uv run ruff check .`
- **PR creation:** use GitHub MCP server (`gh` CLI is not installed)

## Worktree Checklist (before starting any worktree session)

This project uses git worktrees. `git status` only shows the **current** worktree's state.
Always check **both** working directories before starting:

```bash
git status                                                    # current worktree
git -C ~/CursorProjects/investment-assistant status          # main working directory
```

If the main directory is dirty, resolve it first (commit or stash) to avoid merge conflicts when pulling the PR.

## Project Structure

- `src/investment_tracker/` — main source code
  - `api/` — FastAPI routes; `app.state.orchestration` holds SkillRunner
  - `skills/specs/` — declarative Skill definitions (Markdown)
  - `skills/` — SkillSpec, SkillRegistry, SkillRunner, loader
  - `mcp_tools/` — deterministic tools (OCR, NLP, portfolio summary, etc.)
  - `orchestration/` — OrchestrationContainer, LLMOrchestrator, ContextManager
  - `data/` — SQLAlchemy models, repositories, services
  - `utils/` — AIClient (supports Claude + DeepSeek), settings
- `tests/` — pytest test suite
- `demo/` — end-to-end demo script

## Token Discipline

- Never re-read a file already read this session unless it was modified.
- Prefer `anatomy.md` descriptions over full file reads.
- Prefer targeted grep over full file reads when searching.
