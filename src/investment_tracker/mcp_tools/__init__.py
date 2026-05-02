"""MCP tools package."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ExchangeRateTool",
    "InvestmentAdvisorTool",
    "MCPServer",
    "MCPTool",
    "NaturalLanguageTool",
    "OCRTool",
    "PositionCalculatorTool",
    "ToolExecutionError",
    "TransactionParserTool",
]

_EXPORTS = {
    "MCPTool": ("investment_tracker.mcp_tools.base", "MCPTool"),
    "ToolExecutionError": ("investment_tracker.mcp_tools.base", "ToolExecutionError"),
    "MCPServer": ("investment_tracker.mcp_tools.server", "MCPServer"),
    "OCRTool": ("investment_tracker.mcp_tools.ocr_tool", "OCRTool"),
    "TransactionParserTool": ("investment_tracker.mcp_tools.transaction_parser_tool", "TransactionParserTool"),
    "ExchangeRateTool": ("investment_tracker.mcp_tools.exchange_rate_tool", "ExchangeRateTool"),
    "PositionCalculatorTool": ("investment_tracker.mcp_tools.position_calculator_tool", "PositionCalculatorTool"),
    "NaturalLanguageTool": ("investment_tracker.mcp_tools.nlp_tool", "NaturalLanguageTool"),
    "InvestmentAdvisorTool": ("investment_tracker.mcp_tools.investment_advisor_tool", "InvestmentAdvisorTool"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
