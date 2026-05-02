"""Route higher-level tasks to skills and tools."""

from __future__ import annotations

from typing import Any, Dict

from investment_tracker.mcp_tools.server import MCPServer
from investment_tracker.skills.base import SkillRegistry


class SkillsRouter:
    def __init__(self, *, skill_registry: SkillRegistry, tool_server: MCPServer) -> None:
        self.skill_registry = skill_registry
        self.tool_server = tool_server

    def route_skill(self, task_type: str) -> str:
        mapping = {
            "ocr_review": "ocr_parsing_skill",
            "transaction_analysis": "transaction_analysis_skill",
            "investment_advice": "investment_advice_skill",
            "risk_assessment": "risk_assessment_skill",
            "natural_language_understanding": "natural_language_understanding_skill",
        }
        return mapping[task_type]

    def execute_skill(self, task_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        skill_name = self.route_skill(task_type)
        skill = self.skill_registry.get(skill_name)
        return skill.execute(payload)

    def execute_tool(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.tool_server.call_tool(tool_name, payload)

