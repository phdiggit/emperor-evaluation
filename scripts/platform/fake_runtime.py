from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from scripts.platform.models import JobMessage, JobRecord, OutboxMessage, PublishResult


class FakeRepository:
    def __init__(
        self,
        *,
        outbox: list[OutboxMessage] | None = None,
        jobs: list[JobRecord] | None = None,
        fail_on: set[str] | None = None,
    ) -> None:
        self.outbox = {message.id: message for message in outbox or []}
        self.jobs = {job.id: job for job in jobs or []}
        self.fail_on = fail_on or set()
        self.published_outbox_ids: list[int] = []
        self.failed_outbox: list[tuple[int, str]] = []
        self.job_runs: list[tuple[int, str, str, str | None]] = []
        self.events: list[str] = []
        self.side_effect_job_ids: set[int] = set()
        self.results: dict[int, dict[str, Any]] = {}
        self.retry_errors: dict[int, str] = {}
        self.dead_letter_errors: dict[int, str] = {}

    def get_ready_outbox(self, limit: int) -> list[OutboxMessage]:
        return [
            message
            for message in self.outbox.values()
            if message.id not in self.published_outbox_ids
        ][:limit]

    def mark_outbox_published(self, outbox_id: int) -> None:
        self._raise_if_requested("mark_outbox_published")
        self.published_outbox_ids.append(outbox_id)
        self.events.append(f"outbox:{outbox_id}:published")

    def mark_outbox_failed(self, outbox_id: int, error: str) -> None:
        self._raise_if_requested("mark_outbox_failed")
        message = self.outbox[outbox_id]
        self.outbox[outbox_id] = replace(message, attempts=message.attempts + 1)
        self.failed_outbox.append((outbox_id, error))
        self.events.append(f"outbox:{outbox_id}:failed")

    def get_job_for_update(self, job_id: int) -> JobRecord:
        self._raise_if_requested("get_job_for_update")
        return self.jobs[job_id]

    def mark_job_running(self, job_id: int, worker_id: str, lease_seconds: int) -> None:
        self._raise_if_requested("mark_job_running")
        job = self.jobs[job_id]
        self.jobs[job_id] = replace(
            job,
            status="running",
            attempt_count=job.attempt_count + 1,
        )
        self.events.append(f"job:{job_id}:running")

    def mark_job_succeeded(self, job_id: int, result: dict[str, Any]) -> None:
        self._raise_if_requested("mark_job_succeeded")
        self.jobs[job_id] = replace(self.jobs[job_id], status="succeeded")
        self.results[job_id] = result
        self.events.append(f"job:{job_id}:succeeded")

    def mark_job_retry(self, job_id: int, error: str, next_run_at: datetime) -> None:
        self._raise_if_requested("mark_job_retry")
        self.jobs[job_id] = replace(self.jobs[job_id], status="retry_wait")
        self.retry_errors[job_id] = error
        self.events.append(f"job:{job_id}:retry_wait")

    def mark_job_dead_lettered(self, job_id: int, error: str) -> None:
        self._raise_if_requested("mark_job_dead_lettered")
        self.jobs[job_id] = replace(self.jobs[job_id], status="dead_lettered")
        self.dead_letter_errors[job_id] = error
        self.events.append(f"job:{job_id}:dead_lettered")

    def append_job_run(
        self,
        job_id: int,
        worker_id: str,
        status: str,
        trace_id: str | None = None,
    ) -> None:
        self._raise_if_requested("append_job_run")
        self.job_runs.append((job_id, worker_id, status, trace_id))
        self.events.append(f"job:{job_id}:run:{status}")

    def record_side_effect_once(self, job_id: int) -> bool:
        if job_id in self.side_effect_job_ids:
            return False
        self.side_effect_job_ids.add(job_id)
        return True

    def _raise_if_requested(self, method_name: str) -> None:
        if method_name in self.fail_on:
            raise RuntimeError(f"{method_name} failed")


class FakePublisher:
    def __init__(
        self,
        *,
        results: list[PublishResult] | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.exception = exception
        self.published_messages: list[JobMessage] = []

    def publish_job(self, message: JobMessage) -> PublishResult:
        if self.exception is not None:
            raise self.exception
        self.published_messages.append(message)
        if self.results:
            return self.results.pop(0)
        return PublishResult(confirmed=True)


class FakeAckableMessage:
    def __init__(self, message: JobMessage) -> None:
        self.message = message
        self.actions: list[tuple[str, bool | None]] = []

    def ack(self) -> None:
        self.actions.append(("ack", None))

    def nack(self, requeue: bool = False) -> None:
        self.actions.append(("nack", requeue))
