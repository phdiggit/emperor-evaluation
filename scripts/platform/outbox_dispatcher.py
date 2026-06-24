from __future__ import annotations

from dataclasses import dataclass

from scripts.platform.interfaces import JobRepository, MessagePublisher
from scripts.platform.models import JobMessage, OutboxMessage


@dataclass(frozen=True)
class DispatchReport:
    seen: int = 0
    published: int = 0
    failed: int = 0


class OutboxDispatcher:
    """Publishes light job messages only after publisher confirms."""

    def __init__(self, repository: JobRepository, publisher: MessagePublisher) -> None:
        self.repository = repository
        self.publisher = publisher

    def dispatch_once(self, limit: int = 100) -> DispatchReport:
        seen = published = failed = 0
        for outbox_message in self.repository.get_ready_outbox(limit):
            seen += 1
            job_message = to_job_message(outbox_message)
            try:
                result = self.publisher.publish_job(job_message)
            except Exception as exc:  # pragma: no cover - exact adapter exception varies.
                self.repository.mark_outbox_failed(outbox_message.id, str(exc))
                failed += 1
                continue

            if result.confirmed:
                self.repository.mark_outbox_published(outbox_message.id)
                published += 1
            else:
                self.repository.mark_outbox_failed(
                    outbox_message.id,
                    result.error or "publisher confirm failed",
                )
                failed += 1

        return DispatchReport(seen=seen, published=published, failed=failed)


def to_job_message(outbox_message: OutboxMessage) -> JobMessage:
    payload = outbox_message.payload
    return JobMessage(
        job_id=int(payload.get("job_id", outbox_message.aggregate_id)),
        kind=str(payload.get("kind", outbox_message.event_kind)),
        schema_ver=str(payload.get("schema_ver", "v1")),
        trace_id=payload.get("trace_id"),
    )
