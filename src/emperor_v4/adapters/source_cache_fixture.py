from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.adapters.wikisource import read_wikisource_snapshot
from emperor_v4.application.source_cache_service import (
    PreparedSourceSection,
    SourceMaterialBatch,
)
from emperor_v4.contracts.source import SourceCacheRequest, SourceRevisionContent
from emperor_v4.domain.source_segmentation import (
    PassageLinkSeed,
    PassageSeed,
    WindowPolicy,
)


class FrozenSourceMaterialProvider:
    def __init__(self, *, plan_path: Path, repo_root: Path) -> None:
        self.plan_path = plan_path
        self.repo_root = repo_root

    def _load_plan(self) -> Mapping[str, Any]:
        payload = yaml.safe_load(self.plan_path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping) or payload.get("schema_version") != 1:
            raise ValueError("frozen source material plan schema 无效")
        if payload.get("provider") != "frozen_wikisource_snapshot":
            raise ValueError("fixture provider 禁止非冻结来源")
        return payload

    @staticmethod
    def _unique_anchor(text: str, anchor: str, *, after: int = 0) -> int:
        first = text.find(anchor, after)
        if first < 0:
            raise ValueError(f"fixture anchor 未找到: {anchor}")
        if text.find(anchor, first + len(anchor)) >= 0:
            raise ValueError(f"fixture anchor 不唯一: {anchor}")
        return first

    def load(self, request: SourceCacheRequest) -> SourceMaterialBatch:
        plan = self._load_plan()
        if plan.get("subject_ref") != request.subject.person_or_ruler_ref:
            raise ValueError("fixture plan subject 与请求不一致")
        sections = []
        for row in plan.get("sections") or ():
            snapshot_path = self.repo_root / str(row["snapshot"])
            snapshot = read_wikisource_snapshot(snapshot_path)
            seeds = []
            for seed in row.get("passages") or ():
                start = self._unique_anchor(snapshot.raw_text, str(seed["anchor_start"]))
                end_start = self._unique_anchor(
                    snapshot.raw_text,
                    str(seed["anchor_end"]),
                    after=start,
                )
                seeds.append(
                    PassageSeed(
                        seed_code=str(seed["seed_code"]),
                        anchor_start=start,
                        anchor_end=end_start + len(str(seed["anchor_end"])),
                        passage_kind=str(seed.get("passage_kind") or "atomic"),
                        selection_reason=tuple(seed.get("selection_reason") or ()),
                        links=tuple(
                            PassageLinkSeed(
                                target_seed_code=str(link["target_seed_code"]),
                                relation=str(link["relation"]),
                            )
                            for link in seed.get("links") or ()
                        ),
                    )
                )
            policy_row = row.get("window_policy") or {}
            sections.append(
                PreparedSourceSection(
                    revision=SourceRevisionContent(
                        source_host="wikisource",
                        source_document_ref=snapshot.page_code,
                        title=snapshot.canonical_title,
                        url=snapshot.canonical_url,
                        revision_ref=str(snapshot.revision_id),
                        revision_timestamp=snapshot.revision_timestamp,
                        retrieved_at=snapshot.retrieved_at,
                        raw_text=snapshot.raw_text,
                        content_hash=snapshot.content_hash,
                    ),
                    work_identity=str(row["work_identity"]),
                    edition_identity=str(row["edition_identity"]),
                    source_role=str(row["source_role"]),
                    license_or_access_note=str(row["license_or_access_note"]),
                    section_id=str(row["section_id"]),
                    section_heading=str(row["section_heading"]),
                    document_span_start=int(row.get("document_span_start") or 0),
                    seeds=tuple(seeds),
                    window_policy=WindowPolicy(
                        version=str(policy_row["version"]),
                        sentence_radius_before=int(
                            policy_row.get("sentence_radius_before") or 0
                        ),
                        sentence_radius_after=int(
                            policy_row.get("sentence_radius_after") or 0
                        ),
                        context_chars_before=int(
                            policy_row.get("context_chars_before") or 0
                        ),
                        context_chars_after=int(
                            policy_row.get("context_chars_after") or 0
                        ),
                    ),
                )
            )
        if not sections:
            raise ValueError("fixture plan 未提供 source sections")
        return SourceMaterialBatch(
            sections=tuple(sections),
            provider_code="frozen_wikisource_snapshot:v1",
            network_request_count=0,
        )
