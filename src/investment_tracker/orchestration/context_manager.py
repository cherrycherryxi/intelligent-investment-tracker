"""Manage rolling orchestration context and approximate token budgets."""

from __future__ import annotations

from typing import Any, Dict, List


class ContextManager:
    def __init__(self, *, max_items: int = 10, token_budget: int = 4000) -> None:
        self.max_items = max_items
        self.token_budget = token_budget
        self._events: List[Dict[str, Any]] = []

    def add_event(self, event: Dict[str, Any]) -> None:
        self._events.append(event)
        if len(self._events) > self.max_items:
            self._events = self._events[-self.max_items :]

    def recent_events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def summarize(self) -> Dict[str, Any]:
        return {
            "events_count": len(self._events),
            "events": self._events[-3:],
            "estimated_tokens": self._estimate_tokens(),
            "within_budget": self._estimate_tokens() <= self.token_budget,
        }

    def _estimate_tokens(self) -> int:
        total_chars = sum(len(str(event)) for event in self._events)
        return max(1, total_chars // 4) if self._events else 0

