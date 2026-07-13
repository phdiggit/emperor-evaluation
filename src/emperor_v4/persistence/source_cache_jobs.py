from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from uuid import uuid4

from emperor_v4.application.source_cache_worker import ClaimedSourceCacheJob


RUNNABLE_SOURCE_CACHE_JOB_STATUSES = frozenset({"ready", "retry_wait"})
TERMINAL_SOURCE_CACHE_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


@dataclass(slots=True)
class _MemoryJob:
    job_id: str
    idempotency_key: str
    input_fingerprint: str
    policy_version: str
    request_payload: Mapping[str, Any]
    max_attempts: int
    priority: int
    status: str = "ready"
    attempt_count: int = 0
    next_attempt_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    active_run_id: str | None = None


class InMemorySourceCacheJobRepository:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.jobs: dict[str, _MemoryJob] = {}
        self.results: dict[str, Mapping[str, Any]] = {}

    def enqueue(
        self,
        *,
        job_id: str,
        idempotency_key: str,
        input_fingerprint: str,
        policy_version: str,
        request_payload: Mapping[str, Any],
        max_attempts: int = 3,
        priority: int = 0,
    ) -> int:
        existing = self.jobs.get(idempotency_key)
        if existing is not None:
            if existing.input_fingerprint != input_fingerprint or existing.request_payload != request_payload:
                raise ValueError("Source Cache job 幂等键已绑定不同输入")
            return 0
        self.jobs[idempotency_key] = _MemoryJob(
            job_id=job_id,
            idempotency_key=idempotency_key,
            input_fingerprint=input_fingerprint,
            policy_version=policy_version,
            request_payload=request_payload,
            max_attempts=max_attempts,
            priority=priority,
            next_attempt_at=self._clock(),
        )
        return 1

    def recover_expired(self) -> int:
        now = self._clock()
        recovered = 0
        for job in self.jobs.values():
            if job.status == "running" and job.lease_expires_at and job.lease_expires_at <= now:
                job.status = "retry_wait"
                job.next_attempt_at = now
                job.lease_owner = None
                job.lease_expires_at = None
                job.active_run_id = None
                recovered += 1
        return recovered

    def claim(self, *, worker_id: str, lease_seconds: int) -> ClaimedSourceCacheJob | None:
        now = self._clock()
        candidates = [
            job for job in self.jobs.values()
            if job.status in RUNNABLE_SOURCE_CACHE_JOB_STATUSES and job.next_attempt_at <= now
        ]
        if not candidates:
            return None
        job = sorted(candidates, key=lambda item: (-item.priority, item.next_attempt_at, item.job_id))[0]
        job.status = "running"
        job.attempt_count += 1
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.active_run_id = f"SCJR-{uuid4().hex}"
        return ClaimedSourceCacheJob(
            job_id=job.job_id,
            run_id=job.active_run_id,
            idempotency_key=job.idempotency_key,
            input_fingerprint=job.input_fingerprint,
            request_payload=job.request_payload,
            attempt_number=job.attempt_count,
            max_attempts=job.max_attempts,
        )

    def _owned(self, job: ClaimedSourceCacheJob, worker_id: str) -> _MemoryJob:
        current = self.jobs[job.idempotency_key]
        if current.status != "running" or current.lease_owner != worker_id or current.active_run_id != job.run_id:
            raise RuntimeError("Source Cache job lease 已失效或不属于当前 worker")
        if current.lease_expires_at is None or current.lease_expires_at <= self._clock():
            raise RuntimeError("Source Cache job lease 已过期")
        return current

    def succeed(self, job: ClaimedSourceCacheJob, *, worker_id: str, output_fingerprint: str, result_payload: Mapping[str, Any]) -> None:
        current = self._owned(job, worker_id)
        current.status = "succeeded"
        current.lease_owner = None
        current.lease_expires_at = None
        current.active_run_id = None
        self.results[current.job_id] = dict(result_payload)

    def fail(self, job: ClaimedSourceCacheJob, *, worker_id: str, error: Exception, retry_delay_seconds: int) -> str:
        current = self._owned(job, worker_id)
        status = "failed" if current.attempt_count >= current.max_attempts else "retry_wait"
        current.status = status
        current.next_attempt_at = self._clock() + timedelta(seconds=retry_delay_seconds)
        current.lease_owner = None
        current.lease_expires_at = None
        current.active_run_id = None
        return status


def _psycopg() -> tuple[Any, Any]:
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError("V4 Source Cache job repository 需要 psycopg") from exc
    return psycopg, Jsonb


class PostgresSourceCacheJobRepository:
    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("PostgresSourceCacheJobRepository 需要显式 V4 DSN")
        self.dsn = dsn

    def enqueue(
        self,
        *,
        job_id: str,
        idempotency_key: str,
        input_fingerprint: str,
        policy_version: str,
        request_payload: Mapping[str, Any],
        max_attempts: int = 3,
        priority: int = 0,
    ) -> int:
        psycopg, Jsonb = _psycopg()
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO v4_source_cache.jobs (
                        job_id, idempotency_key, input_fingerprint, policy_version,
                        request_payload, status, max_attempts, priority
                    ) VALUES (%s, %s, %s, %s, %s, 'ready', %s, %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING 1
                    """,
                    (job_id, idempotency_key, input_fingerprint, policy_version,
                     Jsonb(request_payload), max_attempts, priority),
                )
                if cursor.fetchone() is not None:
                    return 1
                cursor.execute(
                    """
                    SELECT input_fingerprint, policy_version, request_payload
                    FROM v4_source_cache.jobs WHERE idempotency_key = %s
                    """,
                    (idempotency_key,),
                )
                existing = cursor.fetchone()
                if existing is None or (
                    str(existing[0]) != input_fingerprint
                    or str(existing[1]) != policy_version
                    or existing[2] != request_payload
                ):
                    raise ValueError("Source Cache job 幂等键已绑定不同输入")
                return 0

    def recover_expired(self) -> int:
        psycopg, _ = _psycopg()
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH recovered AS (
                        UPDATE v4_source_cache.jobs
                        SET status = 'retry_wait', next_attempt_at = CURRENT_TIMESTAMP,
                            lease_owner = NULL, lease_expires_at = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE status = 'running' AND lease_expires_at <= CURRENT_TIMESTAMP
                        RETURNING job_id, attempt_count
                    )
                    UPDATE v4_source_cache.job_runs AS run
                    SET status = 'lease_expired', finished_at = CURRENT_TIMESTAMP,
                        error_type = 'LeaseExpired', error_message = 'worker lease expired'
                    FROM recovered
                    WHERE run.job_id = recovered.job_id
                      AND run.attempt_number = recovered.attempt_count
                      AND run.status = 'running'
                    RETURNING run.job_id
                    """
                )
                return len(cursor.fetchall())

    def claim(self, *, worker_id: str, lease_seconds: int) -> ClaimedSourceCacheJob | None:
        psycopg, _ = _psycopg()
        run_id = f"SCJR-{uuid4().hex}"
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH candidate AS (
                        SELECT job_id
                        FROM v4_source_cache.jobs
                        WHERE status IN ('ready', 'retry_wait')
                          AND next_attempt_at <= CURRENT_TIMESTAMP
                        ORDER BY priority DESC, next_attempt_at, created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE v4_source_cache.jobs AS job
                    SET status = 'running', attempt_count = attempt_count + 1,
                        lease_owner = %s,
                        lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                        updated_at = CURRENT_TIMESTAMP
                    FROM candidate
                    WHERE job.job_id = candidate.job_id
                    RETURNING job.job_id, job.idempotency_key, job.input_fingerprint,
                              job.request_payload, job.attempt_count, job.max_attempts
                    """,
                    (worker_id, lease_seconds),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    """
                    INSERT INTO v4_source_cache.job_runs (
                        run_id, job_id, attempt_number, worker_id,
                        input_fingerprint, status
                    ) VALUES (%s, %s, %s, %s, %s, 'running')
                    """,
                    (run_id, row[0], row[4], worker_id, row[2]),
                )
        return ClaimedSourceCacheJob(
            job_id=str(row[0]), run_id=run_id, idempotency_key=str(row[1]),
            input_fingerprint=str(row[2]), request_payload=row[3],
            attempt_number=int(row[4]), max_attempts=int(row[5]),
        )

    def _finish(
        self,
        job: ClaimedSourceCacheJob,
        *,
        worker_id: str,
        status: str,
        output_fingerprint: str | None = None,
        result_payload: Mapping[str, Any] | None = None,
        error: Exception | None = None,
        retry_delay_seconds: int = 0,
    ) -> str:
        psycopg, Jsonb = _psycopg()
        terminal = status == "succeeded" or job.attempt_number >= job.max_attempts
        job_status = "succeeded" if status == "succeeded" else ("failed" if terminal else "retry_wait")
        run_status = "succeeded" if status == "succeeded" else "failed"
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE v4_source_cache.jobs
                    SET status = %s, lease_owner = NULL, lease_expires_at = NULL,
                        next_attempt_at = CASE WHEN %s = 'retry_wait'
                            THEN CURRENT_TIMESTAMP + (%s * INTERVAL '1 second')
                            ELSE next_attempt_at END,
                        output_fingerprint = %s, result_payload = %s,
                        error_type = %s, error_message = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = %s AND status = 'running' AND lease_owner = %s
                      AND lease_expires_at > CURRENT_TIMESTAMP
                    RETURNING 1
                    """,
                    (job_status, job_status, retry_delay_seconds, output_fingerprint,
                     Jsonb(result_payload) if result_payload is not None else None,
                     type(error).__name__ if error else None, str(error) if error else None,
                     job.job_id, worker_id),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("Source Cache job lease 已失效或不属于当前 worker")
                cursor.execute(
                    """
                    UPDATE v4_source_cache.job_runs
                    SET status = %s, finished_at = CURRENT_TIMESTAMP,
                        output_fingerprint = %s, result_payload = %s,
                        error_type = %s, error_message = %s
                    WHERE run_id = %s AND job_id = %s AND worker_id = %s
                      AND status = 'running'
                    RETURNING 1
                    """,
                    (run_status, output_fingerprint,
                     Jsonb(result_payload) if result_payload is not None else None,
                     type(error).__name__ if error else None, str(error) if error else None,
                     job.run_id, job.job_id, worker_id),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("Source Cache job run 状态冲突")
        return job_status

    def succeed(self, job: ClaimedSourceCacheJob, *, worker_id: str, output_fingerprint: str, result_payload: Mapping[str, Any]) -> None:
        self._finish(job, worker_id=worker_id, status="succeeded",
                     output_fingerprint=output_fingerprint, result_payload=result_payload)

    def fail(self, job: ClaimedSourceCacheJob, *, worker_id: str, error: Exception, retry_delay_seconds: int) -> str:
        return self._finish(job, worker_id=worker_id, status="failed", error=error,
                            retry_delay_seconds=retry_delay_seconds)
