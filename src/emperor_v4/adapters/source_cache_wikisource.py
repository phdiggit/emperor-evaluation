from __future__ import annotations

from pathlib import Path
from typing import Callable

from emperor_v4.adapters.source_cache_plan import (
    load_source_plan,
    prepared_sections,
)
from emperor_v4.adapters.wikisource import (
    WikisourcePageSnapshot,
    fetch_wikisource_plaintext,
)
from emperor_v4.application.source_cache_service import SourceMaterialBatch
from emperor_v4.contracts.source import SourceCacheRequest, SourceRevisionContent


FetchWikisource = Callable[..., WikisourcePageSnapshot]


class WikisourceSourceMaterialProvider:
    def __init__(
        self,
        *,
        plan_path: Path,
        fetch: FetchWikisource = fetch_wikisource_plaintext,
    ) -> None:
        self.plan_path = plan_path
        self.fetch = fetch

    def load(self, request: SourceCacheRequest) -> SourceMaterialBatch:
        plan = load_source_plan(
            self.plan_path,
            expected_provider="wikisource_revision_plan",
        )
        if plan.get("subject_ref") != request.subject.person_or_ruler_ref:
            raise ValueError("Wikisource plan subject 与请求不一致")
        revisions = {}
        for row in plan.get("sections") or ():
            page_code = str(row.get("page_code") or "")
            page_title = str(row.get("page_title") or "")
            if page_title not in request.source_hints:
                raise ValueError("Wikisource plan page_title 未获请求 source_hints 授权")
            snapshot = self.fetch(
                page_code=page_code,
                page_title=page_title,
                expected_revision_id=(
                    int(row["expected_revision_id"])
                    if row.get("expected_revision_id") is not None
                    else None
                ),
            )
            expected_revision = row.get("expected_revision_id")
            if (
                expected_revision is not None
                and snapshot.revision_id != int(expected_revision)
            ):
                raise ValueError(
                    f"Wikisource revision 与 plan 不一致: {page_code}"
                )
            revisions[page_code] = SourceRevisionContent(
                source_host="wikisource",
                source_document_ref=snapshot.page_code,
                title=snapshot.canonical_title,
                url=snapshot.canonical_url,
                revision_ref=str(snapshot.revision_id),
                revision_timestamp=snapshot.revision_timestamp,
                retrieved_at=snapshot.retrieved_at,
                raw_text=snapshot.raw_text,
                content_hash=snapshot.content_hash,
            )
        return SourceMaterialBatch(
            sections=prepared_sections(plan, revisions),
            provider_code="wikisource_api_plaintext:v1",
            network_request_count=len(revisions),
        )
