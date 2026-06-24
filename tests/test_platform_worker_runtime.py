import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.fake_runtime import FakeAckableMessage, FakeRepository
from scripts.platform.models import JobMessage, JobRecord
from scripts.platform.worker_runtime import WorkerRuntime


def job(status: str, *, attempt_count: int = 0, max_attempts: int = 3) -> JobRecord:
    return JobRecord(
        id=101,
        kind="fetch",
        schema_ver="v1",
        status=status,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        payload={"source": "repository-only payload"},
    )


def delivery() -> FakeAckableMessage:
    return FakeAckableMessage(JobMessage(job_id=101, kind="fetch", schema_ver="v1"))


@pytest.mark.parametrize("status", ["succeeded", "dead_lettered", "cancelled"])
def test_terminal_job_redelivery_acks_without_running_handler(status: str) -> None:
    repository = FakeRepository(jobs=[job(status)])
    handler_calls: list[int] = []

    def handler(job_id: int) -> dict[str, object]:
        handler_calls.append(job_id)
        return {"ok": True}

    message = delivery()
    WorkerRuntime(repository, handler, worker_id="worker-1").process(message)

    assert handler_calls == []
    assert message.actions == [("ack", None)]
    assert repository.events == []


@pytest.mark.parametrize("status", ["ready", "retry_wait", "running"])
def test_runnable_job_success_commits_succeeded_before_ack(status: str) -> None:
    repository = FakeRepository(jobs=[job(status)])

    def handler(job_id: int) -> dict[str, object]:
        assert repository.get_job_for_update(job_id).payload["source"] == "repository-only payload"
        return {"created": repository.record_side_effect_once(job_id)}

    message = delivery()
    WorkerRuntime(repository, handler, worker_id="worker-1").process(message)

    assert repository.jobs[101].status == "succeeded"
    assert repository.results[101] == {"created": True}
    assert repository.events == [
        "job:101:running",
        "job:101:run:running",
        "job:101:succeeded",
    ]
    assert message.actions == [("ack", None)]


def test_handler_failure_below_max_attempts_commits_retry_wait_before_ack() -> None:
    repository = FakeRepository(jobs=[job("ready", attempt_count=0, max_attempts=3)])

    def handler(job_id: int) -> dict[str, object]:
        raise RuntimeError(f"job {job_id} transient failure")

    message = delivery()
    WorkerRuntime(repository, handler, worker_id="worker-1").process(message)

    assert repository.jobs[101].status == "retry_wait"
    assert repository.retry_errors[101] == "job 101 transient failure"
    assert repository.events[-1] == "job:101:retry_wait"
    assert message.actions == [("ack", None)]


def test_handler_failure_at_max_attempts_commits_dead_lettered_before_ack() -> None:
    repository = FakeRepository(jobs=[job("ready", attempt_count=2, max_attempts=3)])

    def handler(job_id: int) -> dict[str, object]:
        raise RuntimeError(f"job {job_id} permanent failure")

    message = delivery()
    WorkerRuntime(repository, handler, worker_id="worker-1").process(message)

    assert repository.jobs[101].status == "dead_lettered"
    assert repository.dead_letter_errors[101] == "job 101 permanent failure"
    assert repository.events[-1] == "job:101:dead_lettered"
    assert message.actions == [("ack", None)]


def test_db_commit_failure_does_not_ack_and_nacks_for_upper_layer_handling() -> None:
    repository = FakeRepository(
        jobs=[job("ready")],
        fail_on={"mark_job_succeeded"},
    )

    def handler(job_id: int) -> dict[str, object]:
        return {"job_id": job_id}

    message = delivery()
    with pytest.raises(RuntimeError, match="mark_job_succeeded failed"):
        WorkerRuntime(repository, handler, worker_id="worker-1").process(message)

    assert ("ack", None) not in message.actions
    assert message.actions == [("nack", False)]


def test_same_job_delivered_twice_has_only_one_side_effect() -> None:
    repository = FakeRepository(jobs=[job("ready")])

    def handler(job_id: int) -> dict[str, object]:
        return {"created": repository.record_side_effect_once(job_id)}

    runtime = WorkerRuntime(repository, handler, worker_id="worker-1")
    first = delivery()
    second = delivery()

    runtime.process(first)
    runtime.process(second)

    assert repository.side_effect_job_ids == {101}
    assert repository.results[101] == {"created": True}
    assert first.actions == [("ack", None)]
    assert second.actions == [("ack", None)]
