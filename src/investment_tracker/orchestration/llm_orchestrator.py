"""LLM-as-Orchestrator: lets the LLM dynamically route to Skills via tool_use."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class LLMOrchestrator:
    """Run a tool_use loop where the LLM selects which Skills to invoke.

    Each SkillSpec is exposed as a tool_use schema. The LLM keeps calling
    skills until it produces a final text response. Results are returned as
    {message, trace} — no HTTP routes are attached in this iteration.
    """

    MAX_ITERATIONS = 8

    def __init__(
        self,
        *,
        skill_registry,
        skill_runner,
        ai_client,
    ) -> None:
        self.skill_runner = skill_runner
        self.ai_client = ai_client
        self._tool_schemas = self._build_tool_schemas(skill_registry)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(
        self,
        user_message: str,
        context: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run tool_use loop for user_message. Returns {message, trace}."""
        messages: List[Dict[str, Any]] = list(context or [])
        messages.append({"role": "user", "content": user_message})
        trace: List[Dict[str, Any]] = []

        for _ in range(self.MAX_ITERATIONS):
            response = self.ai_client.generate_with_tools(
                messages,
                tools=self._tool_schemas,
            )

            messages.append({"role": "assistant", "content": response.content_blocks})

            if not response.tool_use_blocks:
                final_text = " ".join(
                    block["text"]
                    for block in response.content_blocks
                    if block.get("type") == "text"
                )
                return {"message": final_text, "trace": trace}

            tool_results = []
            for tool_call in response.tool_use_blocks:
                skill_name = tool_call["name"]
                args = tool_call["input"]
                try:
                    result = self.skill_runner.run(skill_name, args)
                    result_content = json.dumps(result, ensure_ascii=False)
                    status = "success"
                except Exception as exc:
                    result_content = str(exc)
                    status = "error"

                trace.append({
                    "skill": skill_name,
                    "args": args,
                    "status": status,
                    "result_summary": result_content[:300],
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": result_content,
                })

            messages.append({"role": "user", "content": tool_results})

        return {"message": "", "trace": trace, "error": "max_iterations_reached"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_tool_schemas(skill_registry) -> List[Dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema or {"type": "object"},
            }
            for spec in skill_registry.list()
        ]
