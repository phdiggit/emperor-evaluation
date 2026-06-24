import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.fake_runtime import FakePublisher, FakeRepository
from scripts.platform.models import OutboxMessage, PublishResult
from scripts.platform.outbox_dispatcher import OutboxDispatcher


def outbox_message(payload: dict[str, object] | None = None) -> OutboxMessage:
    return OutboxMessage(
        id=1,
        code="outbox-1",
        event_kind="fetch",
        aggregate_type="jobs",
        aggregate_id=101,
        payload=payload or {"job_id": 101, "kind": "fetch", "schema_ver": "v1"},
        attempts=0,
    )


def test_dispatcher_marks_outbox_published_after_confirm() -> None:
    repository = FakeRepository(outbox=[outbox_message()])
    publisher = FakePublisher()

    report = OutboxDispatcher(repository, publisher).dispatch_once()

    assert report.seen == 1
    assert report.published == 1
    assert report.failed == 0
    assert repository.published_outbox_ids == [1]
    assert repository.failed_outbox == []


def test_dispatcher_records_error_when_publish_confirm_fails() -> None:
    repository = FakeRepository(outbox=[outbox_message()])
    publisher = FakePublisher(results=[PublishResult(confirmed=False, error="nack")])

    report = OutboxDispatcher(repository, publisher).dispatch_once()

    assert report.seen == 1
    assert report.published == 0
    assert report.failed == 1
    assert repository.published_outbox_ids == []
    assert repository.failed_outbox == [(1, "nack")]
    assert repository.outbox[1].attempts == 1


def test_dispatcher_publishes_only_light_job_message_fields() -> None:
    repository = FakeRepository(
        outbox=[
            outbox_message(
                {
                    "job_id": 202,
                    "kind": "parse",
                    "schema_ver": "v1",
                    "trace_id": "trace-202",
                    "raw_text": "large source text must stay in PostgreSQL",
                    "html": "<main>large snapshot</main>",
                }
            )
        ]
    )
    publisher = FakePublisher()

    OutboxDispatcher(repository, publisher).dispatch_once()

    # The fake publisher records dataclasses, proving no large payload fields cross the boundary.
    published = publisher.published_messages
    assert len(published) == 1
    assert published[0].job_id == 202
    assert published[0].kind == "parse"
    assert published[0].schema_ver == "v1"
    assert published[0].trace_id == "trace-202"
    assert not hasattr(published[0], "raw_text")
    assert not hasattr(published[0], "html")
