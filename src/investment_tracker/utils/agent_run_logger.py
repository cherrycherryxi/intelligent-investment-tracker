"""Readable per-run logging for AI agent workflows."""

from __future__ import annotations

import json
import threading
import uuid
from contextlib import AbstractContextManager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from investment_tracker.settings import get_settings


_ACTIVE_RUN: ContextVar[Optional["AgentRun"]] = ContextVar("agent_run", default=None)
_WRITE_LOCK = threading.Lock()
_SENSITIVE_KEYS = {"authorization", "api_key", "ai_api_key", "x-api-key", "secret", "token", "password"}


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    mode: str
    started_at: datetime
    file_path: Path
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentRunContext(AbstractContextManager["AgentRun"]):
    def __init__(self, run: AgentRun) -> None:
        self.run = run
        self._token: Optional[Token[Optional[AgentRun]]] = None

    def __enter__(self) -> AgentRun:
        self._token = _ACTIVE_RUN.set(self.run)
        _write_run_header(self.run)
        log_agent_event("Run started", data={"mode": self.run.mode, **self.run.metadata})
        return self.run

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        if exc is None:
            log_agent_event("Run completed", data={"status": "ok"})
        else:
            log_agent_event(
                "Run failed",
                data={"status": "error", "error_type": exc_type.__name__ if exc_type else None, "error": str(exc)},
            )
        if self._token is not None:
            _ACTIVE_RUN.reset(self._token)


def start_agent_run(
    *,
    mode: str,
    user_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    log_dir: Optional[str] = None,
) -> AgentRunContext:
    """Create a readable Markdown log context for one agent request."""
    settings = get_settings()
    base_dir = Path(log_dir or settings.log_dir) / "agent_runs"
    started_at = datetime.now(timezone.utc)
    run = AgentRun(
        run_id=uuid.uuid4().hex[:12],
        mode=mode,
        started_at=started_at,
        file_path=base_dir / f"{started_at.date().isoformat()}.md",
        metadata={"user_id": user_id, **(metadata or {})},
    )
    return AgentRunContext(run)


def get_active_agent_run() -> Optional[AgentRun]:
    return _ACTIVE_RUN.get()


def log_agent_event(
    title: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    content: Optional[str] = None,
    language: str = "text",
) -> None:
    """Append one human-readable event to the current run log, if a run is active."""
    run = get_active_agent_run()
    if run is None:
        return

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    parts = [f"\n### {timestamp} | {title}\n"]
    if data:
        parts.append(_code_block(json.dumps(_sanitize(data), ensure_ascii=False, indent=2, default=str), "json"))
    if content is not None:
        parts.append(_code_block(content, language))

    _append(run.file_path, "\n".join(parts))


def _write_run_header(run: AgentRun) -> None:
    heading = (
        f"\n\n---\n\n"
        f"## Agent Run `{run.run_id}`\n\n"
        f"- Started: `{run.started_at.isoformat(timespec='seconds')}`\n"
        f"- Mode: `{run.mode}`\n"
    )
    if run.metadata:
        heading += f"- Metadata:\n{_code_block(json.dumps(_sanitize(run.metadata), ensure_ascii=False, indent=2, default=str), 'json')}"
    _append(run.file_path, heading)


def _append(path: Path, text: str) -> None:
    with _WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")


def _code_block(text: str, language: str) -> str:
    return f"````{language}\n{text}\n````\n"


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = _sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


__all__ = ["get_active_agent_run", "log_agent_event", "start_agent_run"]
