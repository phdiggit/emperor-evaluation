from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.application.source_cache_service import PreparedSourceSection
from emperor_v4.contracts.source import SourceRevisionContent
from emperor_v4.domain.source_segmentation import (
    PassageLinkSeed,
    PassageSeed,
    WindowPolicy,
)


def load_source_plan(path: Path, *, expected_provider: str) -> Mapping[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema_version") != 1:
        raise ValueError("source material plan schema 无效")
    if payload.get("provider") != expected_provider:
        raise ValueError(
            f"source material plan provider 不匹配: {payload.get('provider')}"
        )
    if not payload.get("subject_ref") or not payload.get("sections"):
        raise ValueError("source material plan 缺少 subject 或 sections")
    return payload


def _unique_anchor(text: str, anchor: str, *, after: int = 0) -> int:
    first = text.find(anchor, after)
    if first < 0:
        raise ValueError(f"source plan anchor 未找到: {anchor}")
    if text.find(anchor, first + len(anchor)) >= 0:
        raise ValueError(f"source plan anchor 不唯一: {anchor}")
    return first


def prepared_sections(
    plan: Mapping[str, Any],
    revisions: Mapping[str, SourceRevisionContent],
) -> tuple[PreparedSourceSection, ...]:
    sections = []
    for row in plan.get("sections") or ():
        page_code = str(row.get("page_code") or "")
        revision = revisions.get(page_code)
        if revision is None:
            raise ValueError(f"source plan 缺少 revision: {page_code}")
        seeds = []
        for seed in row.get("passages") or ():
            start_anchor = str(seed.get("anchor_start") or "")
            end_anchor = str(seed.get("anchor_end") or "")
            start = _unique_anchor(revision.raw_text, start_anchor)
            end_start = _unique_anchor(revision.raw_text, end_anchor, after=start)
            seeds.append(
                PassageSeed(
                    seed_code=str(seed["seed_code"]),
                    anchor_start=start,
                    anchor_end=end_start + len(end_anchor),
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
        policy = row.get("window_policy") or {}
        sections.append(
            PreparedSourceSection(
                revision=revision,
                work_identity=str(row["work_identity"]),
                edition_identity=str(row["edition_identity"]),
                source_role=str(row["source_role"]),
                license_or_access_note=str(row["license_or_access_note"]),
                section_id=str(row["section_id"]),
                section_heading=str(row["section_heading"]),
                document_span_start=int(row.get("document_span_start") or 0),
                seeds=tuple(seeds),
                window_policy=WindowPolicy(
                    version=str(policy["version"]),
                    sentence_radius_before=int(
                        policy.get("sentence_radius_before") or 0
                    ),
                    sentence_radius_after=int(
                        policy.get("sentence_radius_after") or 0
                    ),
                    context_chars_before=int(
                        policy.get("context_chars_before") or 0
                    ),
                    context_chars_after=int(
                        policy.get("context_chars_after") or 0
                    ),
                ),
            )
        )
    return tuple(sections)
