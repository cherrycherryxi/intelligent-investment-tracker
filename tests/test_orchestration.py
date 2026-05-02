from __future__ import annotations

import json

from investment_tracker.mcp_tools import MCPServer, NaturalLanguageTool
from investment_tracker.orchestration import ContextManager, SkillsRouter, TaskPlanner, ToolSelector
from investment_tracker.skills import NaturalLanguageUnderstandingSkill, SkillRegistry
from investment_tracker.utils.ai_client import AIResponse


class StubAIClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def generate(self, prompt, *, system_prompt=None, temperature=None, max_tokens=None):
        return AIResponse(
            content=self.content,
            model="deepseek-reasoner",
            provider="deepseek",
            input_tokens=100,
            output_tokens=20,
            raw_response={},
        )


def test_task_planner_produces_steps() -> None:
    planner = TaskPlanner()
    plan = planner.describe("screenshot_import")

    assert plan["step_count"] == 3
    assert plan["steps"][0] == "ocr_extract"


def test_tool_selector_maps_task_to_tools() -> None:
    server = MCPServer()
    selector = ToolSelector(server)

    tools = selector.select("position_analysis")

    assert tools == ["calculate_position", "generate_advice"]


def test_context_manager_rolls_events() -> None:
    manager = ContextManager(max_items=2, token_budget=100)
    manager.add_event({"event": 1})
    manager.add_event({"event": 2})
    manager.add_event({"event": 3})

    summary = manager.summarize()

    assert summary["events_count"] == 2
    assert summary["within_budget"] is True


def test_skills_router_executes_skill_and_tool() -> None:
    registry = SkillRegistry()
    registry.register(
        NaturalLanguageUnderstandingSkill(
            ai_client=StubAIClient(
                json.dumps(
                    {
                        "asset_code": "USD",
                        "direction": "BUY",
                        "quantity": 1000,
                        "unit_price": 7.23,
                        "trade_time": "2026-04-26T10:30:00",
                        "missing_fields": [],
                    }
                )
            )
        )
    )
    server = MCPServer()
    server.register_tool(NaturalLanguageTool())
    router = SkillsRouter(skill_registry=registry, tool_server=server)

    skill_result = router.execute_skill("natural_language_understanding", {"text": "买入1000美元"})
    tool_result = router.execute_tool("parse_natural_language", {"text": "买入1000美元"})

    assert skill_result["asset_code"] == "USD"
    assert tool_result["ok"] is True

