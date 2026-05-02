"""Server-side registry and dispatch for MCP-style tools."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from investment_tracker.mcp_tools.base import MCPTool, ToolMetadata, ToolRegistry


class MCPServer:
    """Dispatches payloads to registered tools."""

    def __init__(self) -> None:
        self.registry = ToolRegistry()

    def register_tool(self, tool: MCPTool) -> None:
        self.registry.register(tool)

    def register_tools(self, tools: Iterable[MCPTool]) -> None:
        for tool in tools:
            self.register_tool(tool)

    def list_tools(self) -> List[ToolMetadata]:
        return list(self.registry.list_metadata())

    def call_tool(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.registry.get(tool_name)
        return tool.execute(payload)

