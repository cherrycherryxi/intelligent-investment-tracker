"""Unified AI client for Claude and DeepSeek style providers."""

from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol
from urllib import error, request

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.settings import AppSettings, get_settings


@dataclass
class AIResponse:
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    raw_response: Dict[str, Any]


class Transport(Protocol):
    def post_json(self, *, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        ...


class UrllibTransport:
    """Minimal JSON HTTP client using the standard library."""

    def post_json(self, *, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=timeout) as response:  # pragma: no cover - network path
            return json.loads(response.read().decode("utf-8"))


class AIClient:
    """Provider-agnostic AI client with token budget and retry support."""

    def __init__(
        self,
        settings: Optional[AppSettings] = None,
        transport: Optional[Transport] = None,
        *,
        max_retries: int = 3,
        retry_delay_seconds: float = 0.0,
        token_budget: int = 12000,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport or UrllibTransport()
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.token_budget = token_budget

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        resolved_provider = provider or self.settings.ai_provider
        resolved_model = model or self.settings.ai_model_name
        resolved_temperature = self.settings.ai_temperature if temperature is None else temperature
        resolved_max_tokens = self.settings.ai_max_tokens if max_tokens is None else max_tokens
        request_timeout = self.settings.ai_request_timeout_seconds

        input_tokens = self.estimate_tokens(prompt) + self.estimate_tokens(system_prompt or "")
        if input_tokens + resolved_max_tokens > self.token_budget:
            raise ToolExecutionError(
                "token budget exceeded",
                code="token_budget_exceeded",
                details={
                    "input_tokens": input_tokens,
                    "requested_max_tokens": resolved_max_tokens,
                    "token_budget": self.token_budget,
                },
            )

        url, headers, payload = self._build_request(
            provider=resolved_provider,
            model=resolved_model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=resolved_temperature,
            max_tokens=resolved_max_tokens,
        )

        last_error: Optional[ToolExecutionError] = None
        for attempt in range(self.max_retries):
            try:
                raw_response = self.transport.post_json(url=url, headers=headers, payload=payload, timeout=request_timeout)
                return self._parse_response(
                    provider=resolved_provider,
                    model=resolved_model,
                    raw_response=raw_response,
                    input_tokens=input_tokens,
                )
            except ToolExecutionError as exc:
                last_error = exc
            except error.URLError as exc:  # pragma: no cover - network path
                last_error = ToolExecutionError(
                    "AI provider request failed",
                    code="ai_request_failed",
                    details={"reason": str(exc.reason)},
                    retryable=True,
                )
            except (socket.timeout, TimeoutError) as exc:  # pragma: no cover - network path
                last_error = ToolExecutionError(
                    "AI provider request timed out",
                    code="ai_request_timeout",
                    details={"timeout_seconds": request_timeout, "reason": str(exc)},
                    retryable=True,
                )

            if last_error and (not last_error.retryable or attempt == self.max_retries - 1):
                break
            if self.retry_delay_seconds:
                time.sleep(self.retry_delay_seconds)

        raise last_error or ToolExecutionError("unknown AI client error", code="ai_unknown_error")

    def estimate_tokens(self, text: str) -> int:
        stripped = text.strip()
        if not stripped:
            return 0
        return max(1, len(stripped) // 4)

    def _build_request(
        self,
        *,
        provider: str,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, Dict[str, str], Dict[str, Any]]:
        api_key = self.settings.ai_api_key or "test-key"
        if provider == "claude":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            payload = {
                "model": model,
                "system": system_prompt or "",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            return url, headers, payload

        if provider == "deepseek":
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            return url, headers, payload

        raise ToolExecutionError(
            f"unsupported AI provider: {provider}",
            code="unsupported_ai_provider",
        )

    def _parse_response(
        self,
        *,
        provider: str,
        model: str,
        raw_response: Dict[str, Any],
        input_tokens: int,
    ) -> AIResponse:
        if provider == "claude":
            parts = raw_response.get("content", [])
            content = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
            usage = raw_response.get("usage", {})
            return AIResponse(
                content=content,
                model=raw_response.get("model", model),
                provider=provider,
                input_tokens=usage.get("input_tokens", input_tokens),
                output_tokens=usage.get("output_tokens", self.estimate_tokens(content)),
                raw_response=raw_response,
            )

        if provider == "deepseek":
            choices = raw_response.get("choices", [])
            content = choices[0]["message"]["content"] if choices else ""
            usage = raw_response.get("usage", {})
            return AIResponse(
                content=content,
                model=raw_response.get("model", model),
                provider=provider,
                input_tokens=usage.get("prompt_tokens", input_tokens),
                output_tokens=usage.get("completion_tokens", self.estimate_tokens(content)),
                raw_response=raw_response,
            )

        raise ToolExecutionError("unsupported AI provider response", code="unsupported_ai_provider")
