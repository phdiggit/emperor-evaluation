from __future__ import annotations

from datetime import timedelta

from scripts.platform.interfaces import AckableMessage, JobHandler, JobRepository
from scripts.platform.models import RUNNABLE_JOB_STATUSES, TERMINAL_ACK_STATUSES, utc_now


class WorkerRuntime:
    """Runs one delivered job and ACKs only after repository state is committed."""

    def __init__(
        self,
        repository: JobRepository,
        handler: JobHandler,
        *,
        worker_id: str,
        lease_seconds: int = 300,
        retry_delay_seconds: int = 60,
    ) -> None:
        self.repository = repository
        self.handler = handler
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.retry_delay_seconds = retry_delay_seconds

    def process(self, delivery: AckableMessage) -> None:
        message = delivery.message
        try:
            job = self.repository.get_job_for_update(message.job_id)
            if job.status in TERMINAL_ACK_STATUSES:
                delivery.ack()
                return
            if job.status not in RUNNABLE_JOB_STATUSES:
                delivery.nack(requeue=False)
                return

            self.repository.mark_job_running(job.id, self.worker_id, self.lease_seconds)
            self.repository.append_job_run(
                job.id,
                self.worker_id,
                "running",
                trace_id=message.trace_id or job.trace_id,
            )
            try:
                result = self.handler(job.id)
            except Exception as exc:
                self._commit_failure(job.id, str(exc), can_retry=job.can_retry_after_current_attempt())
                delivery.ack()
                return

            self.repository.mark_job_succeeded(job.id, result)
            delivery.ack()
        except Exception:
            delivery.nack(requeue=False)
            raise

    def _commit_failure(self, job_id: int, error: str, *, can_retry: bool) -> None:
        if can_retry:
            next_run_at = utc_now() + timedelta(seconds=self.retry_delay_seconds)
            self.repository.mark_job_retry(job_id, error, next_run_at)
        else:
            self.repository.mark_job_dead_lettered(job_id, error)
