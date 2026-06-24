from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


JOB_STATUSES = {
    "queued",
    "ready",
    "running",
    "retry_wait",
    "succeeded",
    "failed",
    "dead_lettered",
    "blocked",
    "cancelled",
}

RUNNABLE_JOB_STATUSES = {"ready", "retry_wait"}
TERMINAL_ACK_STATUSES = {"succeeded", "dead_lettered", "cancelled"}


@dataclass(frozen=True)
class OutboxMessage:
    id: int
    code: str
    event_kind: str
    aggregate_type: str
    aggregate_id: int
    payload: dict[str, Any]
    attempts: int


@dataclass(frozen=True)
class JobMessage:
    job_id: int
    kind: str
    schema_ver: str
    trace_id: str | None = None


@dataclass(frozen=True)
class PublishResult:
    confirmed: bool
    error: str | None = None


@dataclass(frozen=True)
class JobRecord:
    id: int
    kind: str
    schema_ver: str
    status: str
    attempt_count: int = 0
    max_attempts: int = 3
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None

    def can_retry_after_current_attempt(self) -> bool:
        return self.attempt_count + 1 < self.max_attempts


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
