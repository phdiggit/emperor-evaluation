from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class ClaimedSourceCacheJob:
    job_id: str
    run_id: str
    idempotency_key: str
    input_fingerprint: str
    request_payload: Mapping[str, Any]
    attempt_number: int
    max_attempts: int


class SourceCacheJobRepository(Protocol):
    def recover_expired(self) -> int: ...

    def claim(self, *, worker_id: str, lease_seconds: int) -> ClaimedSourceCacheJob | None: ...

    def succeed(
        self,
        job: ClaimedSourceCacheJob,
        *,
        worker_id: str,
        output_fingerprint: str,
        result_payload: Mapping[str, Any],
    ) -> None: ...

    def fail(
        self,
        job: ClaimedSourceCacheJob,
        *,
        worker_id: str,
        error: Exception,
        retry_delay_seconds: int,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class SourceCacheWorkerTick:
    status: str
    job_id: str | None = None
    run_id: str | None = None
    recovered_lease_count: int = 0


def run_source_cache_worker_once(
    repository: SourceCacheJobRepository,
    *,
    worker_id: str,
    handler: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    lease_seconds: int = 300,
    retry_delay_seconds: int = 60,
) -> SourceCacheWorkerTick:
    if not worker_id or lease_seconds <= 0 or retry_delay_seconds < 0:
        raise ValueError("Source Cache worker 参数无效")
    recovered = repository.recover_expired()
    job = repository.claim(worker_id=worker_id, lease_seconds=lease_seconds)
    if job is None:
        return SourceCacheWorkerTick(status="idle", recovered_lease_count=recovered)
    try:
        result = handler(job.request_payload)
        output_fingerprint = str(result.get("output_fingerprint") or "")
        if not output_fingerprint:
            raise ValueError("Source Cache worker handler 缺少 output_fingerprint")
        repository.succeed(
            job,
            worker_id=worker_id,
            output_fingerprint=output_fingerprint,
            result_payload=result,
        )
        status = "succeeded"
    except Exception as exc:
        status = repository.fail(
            job,
            worker_id=worker_id,
            error=exc,
            retry_delay_seconds=retry_delay_seconds,
        )
    return SourceCacheWorkerTick(
        status=status,
        job_id=job.job_id,
        run_id=job.run_id,
        recovered_lease_count=recovered,
    )
