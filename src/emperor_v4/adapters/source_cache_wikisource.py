from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

from emperor_v4.adapters.source_cache_plan import (
    load_source_plan,
    prepared_sections,
)
from emperor_v4.adapters.wikisource import (
    WikisourcePageSnapshot,
    fetch_wikisource_plaintext,
)
from emperor_v4.application.source_cache_service import SourceMaterialBatch
from emperor_v4.contracts.source import (
    SourceCacheRequest,
    SourceRevisionContent,
)


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

    def _plan_for(
        self,
        request: SourceCacheRequest,
    ) -> Mapping[str, object]:
        if self.plan_path.is_file():
            candidates = (self.plan_path,)
        elif self.plan_path.is_dir():
            candidates = tuple(
                sorted(
                    (
                        *self.plan_path.glob("*.yml"),
                        *self.plan_path.glob("*.yaml"),
                    )
                )
            )
        else:
            raise ValueError(
                f"Wikisource plan 路径不存在: {self.plan_path}"
            )

        matches = []
        for path in candidates:
            plan = load_source_plan(
                path,
                expected_provider="wikisource_revision_plan",
            )
            if (
                plan.get("subject_ref")
                == request.subject.person_or_ruler_ref
            ):
                matches.append(plan)
        if len(matches) != 1:
            raise ValueError(
                "Wikisource plan 必须按 subject 唯一匹配: "
                f"subject={request.subject.person_or_ruler_ref} "
                f"matches={len(matches)}"
            )
        return matches[0]

    def load(
        self,
        request: SourceCacheRequest,
    ) -> SourceMaterialBatch:
        plan = self._plan_for(request)
        revisions = {}
        fetch_specs: dict[str, tuple[str, int | None]] = {}
        network_request_count = 0
        for row in plan.get("sections") or ():
            page_code = str(row.get("page_code") or "")
            page_title = str(row.get("page_title") or "")
            expected_revision = (
                int(row["expected_revision_id"])
                if row.get("expected_revision_id") is not None
                else None
            )
            if page_title not in request.source_hints:
                raise ValueError(
                    "Wikisource plan page_title 未获请求 source_hints 授权"
                )
            signature = (page_title, expected_revision)
            previous_signature = fetch_specs.setdefault(
                page_code,
                signature,
            )
            if previous_signature != signature:
                raise ValueError(
                    "同一 page_code 对应冲突的页面或 revision: "
                    f"{page_code}"
                )
            if page_code in revisions:
                continue

            snapshot = self.fetch(
                page_code=page_code,
                page_title=page_title,
                expected_revision_id=expected_revision,
            )
            network_request_count += 1
            if (
                expected_revision is not None
                and snapshot.revision_id != expected_revision
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
            network_request_count=network_request_count,
        )
