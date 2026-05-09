from __future__ import annotations

from investment_tracker.utils.agent_run_logger import get_active_agent_run, log_agent_event, start_agent_run


def test_agent_run_logger_writes_readable_markdown(tmp_path) -> None:
    with start_agent_run(mode="chat", user_id=7, metadata={"message": "hello"}, log_dir=str(tmp_path)) as run:
        log_agent_event(
            "AI request prepared",
            data={
                "payload": {"messages": [{"role": "user", "content": "prompt"}]},
                "authorization": "secret",
            },
            content="response text",
        )

    content = run.file_path.read_text(encoding="utf-8")

    assert "Agent Run" in content
    assert "Run started" in content
    assert "AI request prepared" in content
    assert "prompt" in content
    assert "response text" in content
    assert "***REDACTED***" in content
    assert "Run completed" in content
    assert get_active_agent_run() is None
