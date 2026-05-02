"""Simple task planner for routing user workflows."""

from __future__ import annotations

from typing import Dict, List


class TaskPlanner:
    """Break user intents into ordered subtasks."""

    def plan(self, task_type: str) -> List[str]:
        mapping = {
            "screenshot_import": ["ocr_extract", "parse_transaction", "store_transactions"],
            "natural_language_trade": ["parse_natural_language", "store_transactions"],
            "position_analysis": ["calculate_position", "generate_advice"],
        }
        return mapping.get(task_type, [task_type])

    def describe(self, task_type: str) -> Dict[str, object]:
        steps = self.plan(task_type)
        return {"task_type": task_type, "steps": steps, "step_count": len(steps)}

