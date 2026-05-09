Use a Task sub-agent (subagent_type: Explore) to produce a full codebase map.

Return:
1. Top-level directory structure (exclude .venv, backups, worktrees, __pycache__)
2. For each module under src/: one-line purpose + key public symbols
3. Test coverage overview: which test files cover which source modules
4. External dependencies (from pyproject.toml): purpose of each major package
5. Known gaps: files in anatomy.md marked as large (>500 tok) that may need deeper reading

Search breadth: very thorough. Read-only — no file modifications.
Keep the report under 600 words.
