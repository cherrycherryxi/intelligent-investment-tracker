from __future__ import annotations

from demo.demo import run_demo


def test_demo_flow_runs_end_to_end() -> None:
    result = run_demo()

    assert result.screenshot_preview["summary"]["parsed_count"] >= 2
    assert result.imported_screenshot_transactions
    assert result.imported_natural_language_transactions
    assert result.positions
    assert result.advice["ok"] is True
