"""Tests for LLMOrchestrator: tool_use loop, skill dispatch, trace recording."""

from __future__ import annotations

from typing import Any, Dict, List

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.orchestration.llm_orchestrator import LLMOrchestrator
from investment_tracker.skills.loader import parse_spec
from investment_tracker.skills.registry import SkillRegistry
from investment_tracker.utils.ai_client import AIToolResponse


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class SequenceAIClient:
    """Returns a preset sequence of AIToolResponse objects on each call."""

    def __init__(self, responses: List[AIToolResponse]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    def generate_with_tools(self, messages, *, tools, **kwargs) -> AIToolResponse:
        if self.call_count >= len(self._responses):
            raise AssertionError("generate_with_tools called more times than expected")
        resp = self._responses[self.call_count]
        self.call_count += 1
        return resp


class EchoSkillRunner:
    """Stub SkillRunner that echoes back args as the result."""

    def run(self, skill_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"echoed_skill": skill_name, "echoed_args": args}


class FailingSkillRunner:
    """Stub SkillRunner that always raises."""

    def run(self, skill_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        raise ToolExecutionError("skill failed", code="skill_error", retryable=False)


def _make_registry(*skill_names: str) -> SkillRegistry:
    registry = SkillRegistry()
    for name in skill_names:
        registry.register(parse_spec(
            f"---\nname: {name}\ndescription: {name} skill\n---\n\n# Prompt\n\nhello\n"
        ))
    return registry


def _build_orchestrator(ai_client, *, skill_runner=None, skill_names=("test_skill",)):
    registry = _make_registry(*skill_names)
    if skill_runner is None:
        skill_runner = EchoSkillRunner()
    return LLMOrchestrator(
        skill_registry=registry,
        skill_runner=skill_runner,
        ai_client=ai_client,
    )


def _tool_use_block(skill_name: str, args: dict, call_id: str = "call_1") -> dict:
    return {"type": "tool_use", "id": call_id, "name": skill_name, "input": args}


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


# ---------------------------------------------------------------------------
# Tool schema generation
# ---------------------------------------------------------------------------

def test_orchestrator_exposes_skill_specs_as_tool_schemas() -> None:
    registry = _make_registry("alpha_skill", "beta_skill")
    orch = LLMOrchestrator(
        skill_registry=registry,
        skill_runner=EchoSkillRunner(),
        ai_client=SequenceAIClient([]),
    )

    schemas = orch._tool_schemas

    assert len(schemas) == 2
    names = {s["name"] for s in schemas}
    assert "alpha_skill" in names
    assert "beta_skill" in names
    for s in schemas:
        assert "description" in s
        assert "input_schema" in s


# ---------------------------------------------------------------------------
# Single tool_use + text response
# ---------------------------------------------------------------------------

def test_orchestrator_runs_one_skill_and_returns_final_text() -> None:
    ai = SequenceAIClient([
        AIToolResponse(
            stop_reason="tool_use",
            content_blocks=[_tool_use_block("test_skill", {"x": 1})],
            tool_use_blocks=[_tool_use_block("test_skill", {"x": 1})],
            input_tokens=10,
            output_tokens=5,
        ),
        AIToolResponse(
            stop_reason="end_turn",
            content_blocks=[_text_block("Here is the answer.")],
            tool_use_blocks=[],
            input_tokens=20,
            output_tokens=10,
        ),
    ])
    orch = _build_orchestrator(ai)

    result = orch.handle("run test_skill with x=1")

    assert result["message"] == "Here is the answer."
    assert len(result["trace"]) == 1
    assert result["trace"][0]["skill"] == "test_skill"
    assert result["trace"][0]["status"] == "success"
    assert ai.call_count == 2


# ---------------------------------------------------------------------------
# Immediate text response (no tool_use)
# ---------------------------------------------------------------------------

def test_orchestrator_returns_immediately_when_no_tool_use() -> None:
    ai = SequenceAIClient([
        AIToolResponse(
            stop_reason="end_turn",
            content_blocks=[_text_block("Direct answer, no tools needed.")],
            tool_use_blocks=[],
            input_tokens=5,
            output_tokens=5,
        ),
    ])
    orch = _build_orchestrator(ai)

    result = orch.handle("hello")

    assert result["message"] == "Direct answer, no tools needed."
    assert result["trace"] == []
    assert ai.call_count == 1


# ---------------------------------------------------------------------------
# Multiple tool_use calls in one response
# ---------------------------------------------------------------------------

def test_orchestrator_handles_multiple_tool_calls_in_one_turn() -> None:
    tool_a = _tool_use_block("test_skill", {"a": 1}, call_id="id_a")
    tool_b = _tool_use_block("test_skill", {"b": 2}, call_id="id_b")
    ai = SequenceAIClient([
        AIToolResponse(
            stop_reason="tool_use",
            content_blocks=[tool_a, tool_b],
            tool_use_blocks=[tool_a, tool_b],
            input_tokens=10,
            output_tokens=10,
        ),
        AIToolResponse(
            stop_reason="end_turn",
            content_blocks=[_text_block("done")],
            tool_use_blocks=[],
            input_tokens=30,
            output_tokens=5,
        ),
    ])
    orch = _build_orchestrator(ai)

    result = orch.handle("run both")

    assert len(result["trace"]) == 2
    assert result["message"] == "done"


# ---------------------------------------------------------------------------
# Skill failure recorded in trace
# ---------------------------------------------------------------------------

def test_orchestrator_records_skill_failure_in_trace() -> None:
    ai = SequenceAIClient([
        AIToolResponse(
            stop_reason="tool_use",
            content_blocks=[_tool_use_block("test_skill", {})],
            tool_use_blocks=[_tool_use_block("test_skill", {})],
            input_tokens=10,
            output_tokens=5,
        ),
        AIToolResponse(
            stop_reason="end_turn",
            content_blocks=[_text_block("handled the error")],
            tool_use_blocks=[],
            input_tokens=20,
            output_tokens=5,
        ),
    ])
    orch = _build_orchestrator(ai, skill_runner=FailingSkillRunner())

    result = orch.handle("try it")

    assert result["trace"][0]["status"] == "error"
    assert result["message"] == "handled the error"


# ---------------------------------------------------------------------------
# Max iterations guard
# ---------------------------------------------------------------------------

def test_orchestrator_stops_after_max_iterations() -> None:
    tool_block = _tool_use_block("test_skill", {})
    always_tool = AIToolResponse(
        stop_reason="tool_use",
        content_blocks=[tool_block],
        tool_use_blocks=[tool_block],
        input_tokens=5,
        output_tokens=5,
    )
    ai = SequenceAIClient([always_tool] * (LLMOrchestrator.MAX_ITERATIONS + 1))
    orch = _build_orchestrator(ai)

    result = orch.handle("keep going forever")

    assert result.get("error") == "max_iterations_reached"
    assert len(result["trace"]) == LLMOrchestrator.MAX_ITERATIONS


# ---------------------------------------------------------------------------
# Context (prior conversation) is forwarded
# ---------------------------------------------------------------------------

def test_orchestrator_prepends_context_to_messages() -> None:
    captured_messages: list = []

    class CapturingAIClient:
        call_count = 0

        def generate_with_tools(self, messages, *, tools, **kwargs):
            captured_messages.extend(messages)
            return AIToolResponse(
                stop_reason="end_turn",
                content_blocks=[_text_block("ok")],
                tool_use_blocks=[],
                input_tokens=5,
                output_tokens=2,
            )

    orch = _build_orchestrator(CapturingAIClient())
    prior = [{"role": "user", "content": "earlier message"}]

    orch.handle("new message", context=prior)

    assert captured_messages[0]["content"] == "earlier message"
    assert captured_messages[1]["content"] == "new message"
