from __future__ import annotations

from investment_tracker.mcp_tools.base import MCPTool
from investment_tracker.mcp_tools.server import MCPServer


class EchoTool(MCPTool):
    name = "echo"
    description = "Echo payload for testing."

    def _run(self, payload):
        return {"payload": payload}


def test_server_registers_and_calls_tool() -> None:
    server = MCPServer()
    server.register_tool(EchoTool())

    response = server.call_tool("echo", {"value": 1})

    assert response["ok"] is True
    assert response["result"]["payload"]["value"] == 1


def test_server_lists_tool_metadata() -> None:
    server = MCPServer()
    server.register_tool(EchoTool())

    tools = server.list_tools()

    assert len(tools) == 1
    assert tools[0].name == "echo"

