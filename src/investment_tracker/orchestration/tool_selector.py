"""Select tools for a given task and apply simple fallback policy."""

from __future__ import annotations

from typing import List

from investment_tracker.mcp_tools.server import MCPServer


class ToolSelector:
    def __init__(self, server: MCPServer) -> None:
        self.server = server

    def select(self, task_type: str) -> List[str]:
        mapping = {
            "screenshot_import": ["ocr_extract", "parse_transaction"],
            "natural_language_trade": ["parse_natural_language"],
            "position_analysis": ["calculate_position", "generate_advice"],
            "exchange_rate_lookup": ["get_exchange_rate"],
        }
        return mapping.get(task_type, [])

    def fallback_chain(self, tool_name: str) -> List[str]:
        mapping = {
            "ocr_extract": ["ocr_extract"],
            "get_exchange_rate": ["get_exchange_rate"],
            "generate_advice": ["generate_advice"],
        }
        return mapping.get(tool_name, [tool_name])
