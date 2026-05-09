"""Base abstractions for MCP-style tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Type

from pydantic import BaseModel, ValidationError

from investment_tracker.utils.agent_run_logger import log_agent_event


class ToolExecutionError(Exception):
    """Structured exception for tool execution failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "tool_execution_error",
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.retryable = retryable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": self.details,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    description: str
    version: str = "0.1.0"


class ToolRegistry:
    """Simple in-memory tool registry."""

    def __init__(self) -> None:
        self._tools: Dict[str, MCPTool] = {}

    def register(self, tool: "MCPTool") -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> "MCPTool":
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolExecutionError(
                f"tool '{name}' is not registered",
                code="tool_not_found",
                details={"tool_name": name},
            ) from exc

    def list_metadata(self) -> Iterable[ToolMetadata]:
        return [tool.metadata() for tool in self._tools.values()]


class MCPTool(ABC):
    """Abstract base class for all MCP-compatible tools."""

    name = "unnamed_tool"
    description = "No description provided."
    version = "0.1.0"
    input_model: Optional[Type[BaseModel]] = None

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.name,
            description=self.description,
            version=self.version,
        )

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        log_agent_event(
            "Tool selected",
            data={"tool": self.name, "description": self.description, "version": self.version, "payload": payload},
        )
        try:
            validated_payload = self._validate_payload(payload)
            log_agent_event("Tool input validated", data={"tool": self.name, "validated_payload": validated_payload})
            result = self._run(validated_payload)
            log_agent_event("Tool completed", data={"tool": self.name, "result": result})
            return {
                "tool": self.name,
                "ok": True,
                "result": result,
                "error": None,
            }
        except ToolExecutionError as exc:
            log_agent_event(
                "Tool failed",
                data={"tool": self.name, "code": exc.code, "message": str(exc), "details": exc.details},
            )
            return {
                "tool": self.name,
                "ok": False,
                "result": None,
                "error": exc.to_dict(),
            }
        except ValidationError as exc:
            error = ToolExecutionError(
                "tool input validation failed",
                code="validation_error",
                details={"errors": exc.errors()},
            )
            log_agent_event("Tool validation failed", data={"tool": self.name, "error": error.to_dict()})
            return {
                "tool": self.name,
                "ok": False,
                "result": None,
                "error": error.to_dict(),
            }

    def _validate_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.input_model is None:
            return payload

        model = self.input_model.model_validate(payload)
        return model.model_dump()

    @abstractmethod
    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool implementation."""
