from __future__ import annotations

import socket

import pytest

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.settings import AppSettings
from investment_tracker.utils.ai_client import AIClient


class StubTransport:
    def __init__(self, responses=None, side_effects=None):
        self.responses = responses or []
        self.side_effects = side_effects or []
        self.calls = []

    def post_json(self, *, url, headers, payload, timeout):
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        if self.side_effects:
            effect = self.side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
        return self.responses.pop(0)


def test_claude_generate() -> None:
    transport = StubTransport(
        responses=[
            {
                "model": "claude-3-5-sonnet",
                "content": [{"type": "text", "text": "hello"}],
                "usage": {"input_tokens": 10, "output_tokens": 2},
            }
        ]
    )
    client = AIClient(
        settings=AppSettings(ai_provider="claude", ai_model_name="claude-3-5-sonnet", ai_api_key="k"),
        transport=transport,
    )

    response = client.generate("test prompt")

    assert response.provider == "claude"
    assert response.content == "hello"
    assert transport.calls[0]["url"] == "https://api.anthropic.com/v1/messages"
    assert transport.calls[0]


def test_deepseek_generate() -> None:
    transport = StubTransport(
        responses=[
            {
                "model": "deepseek-reasoner",
                "choices": [{"message": {"content": "world"}}],
                "usage": {"prompt_tokens": 8, "completion_tokens": 2},
            }
        ]
    )
    client = AIClient(
        settings=AppSettings(ai_provider="deepseek", ai_model_name="deepseek-reasoner", ai_api_key="k"),
        transport=transport,
    )

    response = client.generate("test prompt")

    assert response.provider == "deepseek"
    assert response.content == "world"
    assert transport.calls[0]["url"] == "https://api.deepseek.com/chat/completions"


def test_ai_client_retries_on_retryable_error() -> None:
    transport = StubTransport(
        responses=[
            {
                "model": "deepseek-reasoner",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 8, "completion_tokens": 1},
            }
        ],
        side_effects=[ToolExecutionError("temporary", code="tmp", retryable=True)],
    )
    client = AIClient(transport=transport, retry_delay_seconds=0)

    response = client.generate("prompt")

    assert response.content == "ok"
    assert len(transport.calls) == 2


def test_ai_client_budget_enforced() -> None:
    client = AIClient(token_budget=10)

    with pytest.raises(ToolExecutionError, match="token budget exceeded"):
        client.generate("x" * 60, max_tokens=20)


def test_ai_client_converts_socket_timeout_to_tool_error() -> None:
    transport = StubTransport(side_effects=[socket.timeout("timed out")])
    client = AIClient(
        settings=AppSettings(
            ai_provider="deepseek",
            ai_model_name="deepseek-reasoner",
            ai_api_key="k",
            ai_request_timeout_seconds=12,
        ),
        transport=transport,
        max_retries=1,
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        client.generate("prompt")

    assert exc_info.value.code == "ai_request_timeout"
    assert exc_info.value.details["timeout_seconds"] == 12
