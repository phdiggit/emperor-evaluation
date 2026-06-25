from __future__ import annotations

from collections.abc import Callable
from typing import Any

from scripts.platform.core.redaction import redact_text


def blocked_report_fields(
    *,
    started_at_utc: str,
    ended_at_utc: Callable[[], str],
    failure_stage: str,
    blocked_reason: str,
    exc: BaseException | None = None,
    dsn: str | None = None,
) -> dict[str, Any]:
    stderr_summary: list[str] = []
    if exc is not None:
        stderr_summary.append(redact_text(f"{type(exc).__name__}: {exc}", dsn))
    return {
        "started_at_utc": started_at_utc,
        "ended_at_utc": ended_at_utc(),
        "redacted_stdout_summary": [],
        "redacted_stderr_summary": stderr_summary,
        "failure_stage": failure_stage,
        "blocked_reason": blocked_reason,
        "blocking_failures": [blocked_reason],
    }
