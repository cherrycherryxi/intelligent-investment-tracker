"""Tests for OrchestrationContainer and ContextManager."""

from __future__ import annotations

from investment_tracker.orchestration.container import OrchestrationContainer
from investment_tracker.orchestration.context_manager import ContextManager
from investment_tracker.utils.ai_client import AIResponse


class StubAIClient:
    def generate(self, prompt, *, system_prompt=None, temperature=None, max_tokens=None):
        return AIResponse(
            content="{}",
            model="stub",
            provider="stub",
            input_tokens=10,
            output_tokens=10,
            raw_response={},
        )


# ---------------------------------------------------------------------------
# ContextManager
# ---------------------------------------------------------------------------

def test_context_manager_rolls_events() -> None:
    manager = ContextManager(max_items=2, token_budget=100)
    manager.add_event({"event": 1})
    manager.add_event({"event": 2})
    manager.add_event({"event": 3})

    summary = manager.summarize()

    assert summary["events_count"] == 2
    assert summary["within_budget"] is True


# ---------------------------------------------------------------------------
# OrchestrationContainer
# ---------------------------------------------------------------------------

def test_container_builds_and_exposes_skill_registry() -> None:
    container = OrchestrationContainer.build(ai_client=StubAIClient())

    assert container.skill_registry.has("investment_advice_skill")
    assert container.skill_registry.has("ocr_parsing_skill")
    assert container.skill_registry.has("natural_language_understanding_skill")
    assert len(container.skill_registry) == 5


def test_container_tool_server_has_expected_tools() -> None:
    container = OrchestrationContainer.build(ai_client=StubAIClient())

    result = container.tool_server.call_tool(
        "parse_natural_language",
        {"text": "买入1000美元，汇率7.23，时间2026-04-26 10:30:00"},
    )

    assert result["ok"] is True
    assert result["result"]["parameters"]["asset_code"] == "USD"
