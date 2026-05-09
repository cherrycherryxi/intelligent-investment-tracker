Prepare and open a pull request for the current branch. Steps:

1. Run the full test suite: `/opt/anaconda3/bin/uv run pytest --tb=short -q`
   - If any tests fail (beyond the known 4 xlsx-fixture skips), stop and report the failures.
2. Run lint: `/opt/anaconda3/bin/uv run ruff check .`
   - Fix any lint errors before proceeding.
3. Summarize all commits on this branch vs main (`git log main..HEAD --oneline`).
4. Create a PR via GitHub MCP server (`mcp__github__create_pull_request`) with:
   - A concise title (under 70 chars)
   - Body: bullet-point summary of changes + test results

Repo: cherrycherryxi/intelligent-investment-tracker
Do NOT use `gh` CLI — use the GitHub MCP server only.
$ARGUMENTS
