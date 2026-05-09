"""Orchestration container: wires SkillRegistry, MCPServer, and SkillRunner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from investment_tracker.mcp_tools.exchange_rate_tool import ExchangeRateTool
from investment_tracker.mcp_tools.nlp_tool import NaturalLanguageTool
from investment_tracker.mcp_tools.ocr_tool import OCRTool
from investment_tracker.mcp_tools.portfolio_summary_tool import PortfolioSummaryTool
from investment_tracker.mcp_tools.position_calculator_tool import PositionCalculatorTool
from investment_tracker.mcp_tools.server import MCPServer
from investment_tracker.mcp_tools.transaction_parser_tool import TransactionParserTool
from investment_tracker.skills.registry import SkillRegistry
from investment_tracker.skills.runner import SkillRunner

_SPECS_DIR = Path(__file__).parent.parent / "skills" / "specs"


@dataclass
class OrchestrationContainer:
    skill_registry: SkillRegistry
    tool_server: MCPServer
    skill_runner: SkillRunner

    @classmethod
    def build(cls, *, ai_client: Any) -> "OrchestrationContainer":
        tool_server = MCPServer()
        tool_server.register_tools([
            OCRTool(),
            NaturalLanguageTool(),
            PortfolioSummaryTool(),
            TransactionParserTool(),
            ExchangeRateTool(),
            PositionCalculatorTool(),
        ])
        skill_registry = SkillRegistry.from_dir(_SPECS_DIR)
        skill_runner = SkillRunner(
            skill_registry=skill_registry,
            tool_server=tool_server,
            ai_client=ai_client,
        )
        return cls(
            skill_registry=skill_registry,
            tool_server=tool_server,
            skill_runner=skill_runner,
        )
