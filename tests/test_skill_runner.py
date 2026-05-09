"""Tests for SkillRunner: pre_tools, short_circuit, AI call, on_failure."""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from investment_tracker.mcp_tools.base import MCPTool, ToolExecutionError
from investment_tracker.mcp_tools.server import MCPServer
from investment_tracker.skills.loader import parse_spec
from investment_tracker.skills.registry import SkillRegistry
from investment_tracker.skills.runner import SkillRunner
from investment_tracker.utils.ai_client import AIResponse


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class StubAIClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.call_count = 0

    def generate(self, prompt, *, system_prompt=None, temperature=None, max_tokens=None):
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return AIResponse(
            content=self.content,
            model="stub-model",
            provider="stub",
            input_tokens=10,
            output_tokens=10,
            raw_response={},
        )


class FailingAIClient:
    def generate(self, *args, **kwargs):
        raise ToolExecutionError("AI down", code="ai_request_failed", retryable=False)


class EchoTool(MCPTool):
    """Test tool that returns whatever payload it receives."""
    name = "echo"
    description = "echo back"

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"echoed": payload}


class FixedOutputTool(MCPTool):
    """Test tool returning a preset value."""
    name = "fixed_output"
    description = "fixed"

    def __init__(self, output: Dict[str, Any]) -> None:
        self.output = output

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_runner(
    spec_text: str,
    *,
    tools: list = None,
    ai_client=None,
) -> SkillRunner:
    registry = SkillRegistry()
    registry.register(parse_spec(spec_text))
    server = MCPServer()
    if tools:
        server.register_tools(tools)
    return SkillRunner(skill_registry=registry, tool_server=server, ai_client=ai_client)


# ---------------------------------------------------------------------------
# Basic AI flow
# ---------------------------------------------------------------------------

def test_runner_renders_prompt_and_returns_parsed_json() -> None:
    spec = """---
name: greeter
---

# System

You are a greeter.

# Prompt

Hello {{ name }}!
"""
    ai = StubAIClient(json.dumps({"greeting": "hi"}))
    runner = _build_runner(spec, ai_client=ai)

    result = runner.run("greeter", {"name": "world"})

    assert result == {"greeting": "hi"}
    assert ai.last_prompt == "Hello world!"
    assert ai.last_system_prompt == "You are a greeter."


def test_runner_validates_required_fields() -> None:
    spec = """---
name: needs_input
input_schema:
  type: object
  required: [text]
---

# Prompt

Process {{ text }}.
"""
    ai = StubAIClient("{}")
    runner = _build_runner(spec, ai_client=ai)

    with pytest.raises(ToolExecutionError) as exc_info:
        runner.run("needs_input", {})
    assert exc_info.value.code == "skill_input_invalid"


# ---------------------------------------------------------------------------
# Pre-tools
# ---------------------------------------------------------------------------

def test_runner_runs_pre_tool_and_maps_into_context() -> None:
    spec = """---
name: pre_tool_demo
pre_tools:
  - tool: fixed_output
    args: {}
    output_var: tool_result
    map_to_context:
      message: "{{ tool_result.result.text }}"
---

# Prompt

Got: {{ message }}
"""
    ai = StubAIClient('{"ok": true}')
    runner = _build_runner(
        spec,
        tools=[FixedOutputTool({"text": "from-tool"})],
        ai_client=ai,
    )

    runner.run("pre_tool_demo", {})

    assert ai.last_prompt == "Got: from-tool"


def test_runner_skips_pre_tool_when_condition_false() -> None:
    spec = """---
name: conditional
pre_tools:
  - tool: fixed_output
    when: "should_run"
    args: {}
    output_var: tool_result
---

# Prompt

x
"""
    ai = StubAIClient("{}")
    tool = FixedOutputTool({"text": "should-not-be-called"})
    runner = _build_runner(spec, tools=[tool], ai_client=ai)

    # should_run = False → pre_tool skipped, AI still called
    runner.run("conditional", {"should_run": False})
    assert ai.call_count == 1


def test_runner_runs_pre_tool_when_condition_true() -> None:
    spec = """---
name: conditional
pre_tools:
  - tool: fixed_output
    when: "should_run"
    args: {}
    output_var: tool_result
---

# Prompt

x
"""
    ai = StubAIClient("{}")
    runner = _build_runner(spec, tools=[FixedOutputTool({"v": 1})], ai_client=ai)

    runner.run("conditional", {"should_run": True})
    assert ai.call_count == 1


# ---------------------------------------------------------------------------
# Short-circuit
# ---------------------------------------------------------------------------

def test_runner_short_circuits_and_skips_ai() -> None:
    spec = """---
name: rule_first
pre_tools:
  - tool: fixed_output
    args: {}
    output_var: rule_result
    short_circuit_if: "rule_result.result.complete"
    short_circuit_return: "{{ rule_result.result }}"
---

# Prompt

needed only when rules incomplete
"""
    ai = StubAIClient('{"never_called": true}')
    tool_output = {"complete": True, "value": 42}
    runner = _build_runner(spec, tools=[FixedOutputTool(tool_output)], ai_client=ai)

    result = runner.run("rule_first", {})

    assert result == tool_output
    assert ai.call_count == 0


def test_runner_falls_through_when_short_circuit_false() -> None:
    spec = """---
name: rule_first
pre_tools:
  - tool: fixed_output
    args: {}
    output_var: rule_result
    short_circuit_if: "rule_result.result.complete"
    short_circuit_return: "{{ rule_result.result }}"
---

# Prompt

x
"""
    ai = StubAIClient('{"from": "ai"}')
    runner = _build_runner(spec, tools=[FixedOutputTool({"complete": False})], ai_client=ai)

    result = runner.run("rule_first", {})

    assert result == {"from": "ai"}
    assert ai.call_count == 1


# ---------------------------------------------------------------------------
# AI failure handling
# ---------------------------------------------------------------------------

def test_runner_returns_var_on_ai_failure_when_configured() -> None:
    spec = """---
name: with_fallback
pre_tools:
  - tool: fixed_output
    args: {}
    output_var: rule_result
ai:
  on_failure: return_var
  on_failure_var: rule_result.result
---

# Prompt

x
"""
    runner = _build_runner(
        spec,
        tools=[FixedOutputTool({"fallback_value": "yes"})],
        ai_client=FailingAIClient(),
    )

    result = runner.run("with_fallback", {})

    assert result == {"fallback_value": "yes"}


def test_runner_raises_on_ai_failure_by_default() -> None:
    spec = """---
name: no_fallback
---

# Prompt

x
"""
    runner = _build_runner(spec, ai_client=FailingAIClient())

    with pytest.raises(ToolExecutionError):
        runner.run("no_fallback", {})


def test_runner_raises_on_invalid_json_when_no_fallback() -> None:
    spec = """---
name: strict
---

# Prompt

x
"""
    runner = _build_runner(spec, ai_client=StubAIClient("not-json"))

    with pytest.raises(ToolExecutionError) as exc_info:
        runner.run("strict", {})
    assert exc_info.value.code == "invalid_skill_response"


# ---------------------------------------------------------------------------
# Args templating preserves types
# ---------------------------------------------------------------------------

def test_runner_passes_typed_args_to_pre_tool() -> None:
    spec = """---
name: typed_args
pre_tools:
  - tool: echo
    args:
      number: "{{ count }}"
      list_value: "{{ items }}"
    output_var: echo_result
---

# Prompt

x
"""
    ai = StubAIClient("{}")
    runner = _build_runner(spec, tools=[EchoTool()], ai_client=ai)

    runner.run("typed_args", {"count": 7, "items": ["a", "b"]})
    # If templating preserved types, the EchoTool received a dict whose
    # number value is the int 7 (not the string "7"). We verify by re-running
    # and inspecting through a custom tool.

    # Use a recording tool to inspect args
    recorded: Dict[str, Any] = {}

    class RecordingTool(MCPTool):
        name = "recorder"
        description = "records args"

        def _run(self, payload):
            recorded.update(payload)
            return {"ok": True}

    spec2 = """---
name: typed_args2
pre_tools:
  - tool: recorder
    args:
      number: "{{ count }}"
      list_value: "{{ items }}"
    output_var: r
---

# Prompt

x
"""
    runner2 = _build_runner(spec2, tools=[RecordingTool()], ai_client=ai)
    runner2.run("typed_args2", {"count": 7, "items": ["a", "b"]})

    assert recorded["number"] == 7
    assert recorded["list_value"] == ["a", "b"]
