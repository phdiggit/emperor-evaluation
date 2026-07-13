from __future__ import annotations

from pathlib import Path
from emperor_v4.adapters.wikisource import read_wikisource_snapshot
from emperor_v4.adapters.source_cache_plan import (
    load_source_plan,
    prepared_sections,
)
from emperor_v4.application.source_cache_service import (
    SourceMaterialBatch,
)
from emperor_v4.contracts.source import SourceCacheRequest, SourceRevisionContent


class FrozenSourceMaterialProvider:
    def __init__(self, *, plan_path: Path, repo_root: Path) -> None:
        self.plan_path = plan_path
        self.repo_root = repo_root

    def load(self, request: SourceCacheRequest) -> SourceMaterialBatch:
        plan = load_source_plan(
            self.plan_path,
            expected_provider="wikisource_revision_plan",
        )
        if plan.get("subject_ref") != request.subject.person_or_ruler_ref:
            raise ValueError("fixture plan subject 与请求不一致")
        revisions = {}
        for row in plan.get("sections") or ():
            snapshot_path = self.repo_root / str(row["snapshot"])
            snapshot = read_wikisource_snapshot(snapshot_path)
            page_code = str(row.get("page_code") or "")
            if page_code != snapshot.page_code:
                raise ValueError("fixture plan page_code 与 snapshot 不一致")
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
            provider_code="frozen_wikisource_snapshot:v1",
            network_request_count=0,
        )
