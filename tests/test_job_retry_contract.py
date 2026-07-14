from __future__ import annotations

from emperor_v4.application.source_cache_worker import (
    run_source_cache_worker_once,
)
from emperor_v4.persistence.source_cache_jobs import (
    InMemorySourceCacheJobRepository,
)


def _repository() -> InMemorySourceCacheJobRepository:
    repository = InMemorySourceCacheJobRepository()
    repository.enqueue(
        job_id="JOB-1",
        idempotency_key="job:1",
        input_fingerprint="input-v1",
        policy_version="policy-v1",
        request_payload={"request_id": "REQ-1"},
        max_attempts=3,
    )
    return repository


def test_deterministic_contract_error_fails_after_one_attempt() -> None:
    repository = _repository()

    def handler(payload):
        raise ValueError("unknown extraction profile")

    first = run_source_cache_worker_once(
        repository,
        worker_id="worker-1",
        handler=handler,
        retry_delay_seconds=0,
    )
    second = run_source_cache_worker_once(
        repository,
        worker_id="worker-1",
        handler=handler,
        retry_delay_seconds=0,
    )

    assert first.status == "failed"
    assert second.status == "idle"
    assert repository.jobs["job:1"].attempt_count == 1


def test_runtime_provider_error_remains_retryable() -> None:
    repository = _repository()

    def handler(payload):
        raise RuntimeError("provider temporarily unavailable")

    tick = run_source_cache_worker_once(
        repository,
        worker_id="worker-1",
        handler=handler,
        retry_delay_seconds=0,
    )

    assert tick.status == "retry_wait"
    assert repository.jobs["job:1"].attempt_count == 1
