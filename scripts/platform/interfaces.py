from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from scripts.platform.models import JobMessage, JobRecord, OutboxMessage, PublishResult


class JobRepository(Protocol):
    def get_ready_outbox(self, limit: int) -> list[OutboxMessage]: ...

    def mark_outbox_published(self, outbox_id: int) -> None: ...

    def mark_outbox_failed(self, outbox_id: int, error: str) -> None: ...

    def get_job_for_update(self, job_id: int) -> JobRecord: ...

    def mark_job_running(self, job_id: int, worker_id: str, lease_seconds: int) -> None: ...

    def mark_job_succeeded(self, job_id: int, result: dict[str, Any]) -> None: ...

    def mark_job_retry(self, job_id: int, error: str, next_run_at: datetime) -> None: ...

    def mark_job_dead_lettered(self, job_id: int, error: str) -> None: ...

    def append_job_run(
        self,
        job_id: int,
        worker_id: str,
        status: str,
        trace_id: str | None = None,
    ) -> None: ...


class MessagePublisher(Protocol):
    def publish_job(self, message: JobMessage) -> PublishResult: ...


class AckableMessage(Protocol):
    message: JobMessage

    def ack(self) -> None: ...

    def nack(self, requeue: bool = False) -> None: ...


class JobHandler(Protocol):
    def __call__(self, job_id: int) -> dict[str, Any]: ...
