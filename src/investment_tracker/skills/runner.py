"""SkillRunner: executes a SkillSpec by running pre_tools, calling the AI, and parsing output."""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, Optional

from jinja2 import Environment
from jinja2.nativetypes import NativeEnvironment

from investment_tracker.mcp_tools.base import ToolExecutionError
from investment_tracker.mcp_tools.server import MCPServer
from investment_tracker.skills.registry import SkillRegistry
from investment_tracker.skills.spec import PreToolStep, SkillSpec
from investment_tracker.utils.ai_client import AIClient


class SkillRunner:
    """Executes a SkillSpec deterministically.

    Pipeline:
      1. validate payload (light: required keys via input_schema.required)
      2. context = payload copy
      3. for each pre_tool:
         - if `when` evaluates false → skip
         - render `args` and call the registered tool
         - store output under `output_var`
         - apply `map_to_context`
         - if `short_circuit_if` evaluates true → return rendered `short_circuit_return`
      4. render system prompt and user prompt
      5. call ai_client.generate()
      6. json.loads → return
      7. on AI failure: honor ai.on_failure
    """

    def __init__(
        self,
        *,
        skill_registry: SkillRegistry,
        tool_server: MCPServer,
        ai_client: Optional[AIClient] = None,
    ) -> None:
        self.skill_registry = skill_registry
        self.tool_server = tool_server
        self.ai_client = ai_client or AIClient()
        self._native_env = NativeEnvironment()
        self._string_env = Environment(autoescape=False)

    def run(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        spec = self.skill_registry.get(name)
        self._validate_required(spec, payload)
        context: Dict[str, Any] = copy.deepcopy(payload)

        for step in spec.pre_tools:
            if not self._should_run(step, context):
                continue
            tool_args = self._render_value(step.args, context)
            tool_response = self.tool_server.call_tool(step.tool, tool_args)
            if step.output_var:
                context[step.output_var] = tool_response
            for target_key, template in step.map_to_context.items():
                context[target_key] = self._render_value(template, context)
            if self._evaluate_bool(step.short_circuit_if, context):
                return self._render_value(step.short_circuit_return, context)

        system_prompt = self._render_string(spec.system_prompt, context) if spec.system_prompt else None
        user_prompt = self._render_string(spec.user_prompt, context)

        try:
            response = self.ai_client.generate(
                user_prompt,
                system_prompt=system_prompt,
                temperature=spec.ai.temperature,
                max_tokens=spec.ai.max_tokens,
            )
        except Exception:
            fallback = self._handle_ai_failure(spec, context)
            if fallback is not None:
                return fallback
            raise

        return self._parse_ai_content(spec, response.content, context)

    def _validate_required(self, spec: SkillSpec, payload: Dict[str, Any]) -> None:
        required = spec.input_schema.get("required") or []
        missing = [field for field in required if field not in payload]
        if missing:
            raise ToolExecutionError(
                f"skill '{spec.name}' is missing required input fields: {missing}",
                code="skill_input_invalid",
                details={"missing": missing, "skill": spec.name},
            )

    def _should_run(self, step: PreToolStep, context: Dict[str, Any]) -> bool:
        if step.when is None:
            return True
        return self._evaluate_bool(step.when, context)

    def _evaluate_bool(self, expr: Optional[str], context: Dict[str, Any]) -> bool:
        if expr is None:
            return False
        if not isinstance(expr, str):
            return bool(expr)
        text = expr.strip()
        if not text:
            return False
        if not (text.startswith("{{") and text.endswith("}}")):
            text = "{{ " + text + " }}"
        rendered = self._native_env.from_string(text).render(**context)
        return bool(rendered)

    def _render_value(self, value: Any, context: Dict[str, Any]) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("{{") and stripped.endswith("}}"):
                return self._native_env.from_string(value).render(**context)
            if "{{" in value and "}}" in value:
                return self._string_env.from_string(value).render(**context)
            return value
        if isinstance(value, dict):
            return {k: self._render_value(v, context) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render_value(item, context) for item in value]
        return value

    def _render_string(self, template: str, context: Dict[str, Any]) -> str:
        if "{{" not in template:
            return template
        return self._string_env.from_string(template).render(**context)

    def _parse_ai_content(
        self,
        spec: SkillSpec,
        content: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            fallback = self._handle_ai_failure(spec, context)
            if fallback is not None:
                return fallback
            raise ToolExecutionError(
                f"skill '{spec.name}' returned invalid JSON",
                code="invalid_skill_response",
                details={"content": content},
            ) from exc
        return parsed

    def _handle_ai_failure(self, spec: SkillSpec, context: Dict[str, Any]) -> Optional[Any]:
        if spec.ai.on_failure != "return_var":
            return None
        if not spec.ai.on_failure_var:
            return None
        return self._lookup_dotted(context, spec.ai.on_failure_var)

    @staticmethod
    def _lookup_dotted(source: Any, dotted: str) -> Optional[Any]:
        current: Any = source
        for part in dotted.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
