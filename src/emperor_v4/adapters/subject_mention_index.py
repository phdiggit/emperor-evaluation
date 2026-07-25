from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
from time import sleep
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from opencc import OpenCC

from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.adapters.wikisource import (
    WikisourcePageSnapshot,
    fetch_wikisource_revision_batch,
    fetch_wikisource_revision_text,
)


MENTION_INDEX_SCHEMA_VERSION = "subject-mention-index-v2"
MENTION_REPORT_SCHEMA_VERSION = "subject-mention-shadow-report-v3"
REVIEW_WORKLIST_SCHEMA_VERSION = "subject-mention-review-worklist-v2"
SHARED_REVIEW_PLAN_SCHEMA_VERSION = "subject-shared-review-plan-v1"
REFETCH_RESULT_SCHEMA_VERSION = "subject-mention-refetch-result-v1"
REVIEW_PROXIMITY_CHARS = 120
_S2T = OpenCC("s2t")
_T2S = OpenCC("t2s")
_HEADING = re.compile(r"(?m)^(={2,5})\s*(.*?)\s*\1\s*$")
_PAGE_VOLUME = re.compile(r"卷\s*0*(\d{1,4})")
_REIGN_YEAR = re.compile(
    r"(?:貞觀|贞观|武德|永徽|顯慶|显庆)\s*(?:元|[一二三四五六七八九十百廿卅]+)\s*年"
)


@dataclass(frozen=True, slots=True)
class _Mention:
    subject_ref: str
    page_title: str
    work_title: str
    source_url: str
    revision_ref: str
    start_offset: int
    end_offset: int
    surface_form: str
    mention_kind: str


def _variants(value: str) -> tuple[str, ...]:
    stripped = str(value).strip()
    return tuple(
        dict.fromkeys(
            candidate
            for candidate in (stripped, _S2T.convert(stripped), _T2S.convert(stripped))
            if candidate
        )
    )


def _positions(text: str, term: str) -> Iterable[int]:
    start = 0
    while (position := text.find(term, start)) >= 0:
        yield position
        start = position + 1


def _inside_heading(text: str, offset: int) -> bool:
    return any(match.start() <= offset < match.end() for match in _HEADING.finditer(text))


def _canonical_payload(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _validated_plan(
    payload: Mapping[str, object], source_index: LocalSourceTextIndex
) -> tuple[dict[str, object], ...]:
    expected_identity = str(payload.get("source_index_identity") or "").strip()
    if expected_identity and expected_identity != source_index.identity:
        raise ValueError("人物提及计划与本地全文索引 identity 不一致")
    raw_subjects = payload.get("subjects")
    if not isinstance(raw_subjects, Sequence) or isinstance(raw_subjects, (str, bytes)):
        raise ValueError("人物提及计划缺少 subjects")
    subjects: list[dict[str, object]] = []
    seen_refs: set[str] = set()
    for raw in raw_subjects:
        if not isinstance(raw, Mapping):
            raise ValueError("人物提及计划 subjects 项必须是 object")
        subject_ref = str(raw.get("subject_ref") or "").strip()
        subject_name = str(raw.get("subject_name") or "").strip()
        works = tuple(str(item).strip() for item in raw.get("works") or () if str(item).strip())
        surface_forms = tuple(
            dict.fromkeys(
                str(item).strip()
                for item in raw.get("surface_forms") or ()
                if len(str(item).strip()) >= 2
            )
        )
        if not subject_ref or not subject_name or not works or not surface_forms:
            raise ValueError("人物提及计划缺少 subject_ref、subject_name、works 或 surface_forms")
        if subject_ref in seen_refs:
            raise ValueError(f"人物提及计划 subject_ref 重复: {subject_ref}")
        seen_refs.add(subject_ref)
        page_ranges = raw.get("page_ranges") or {}
        if not isinstance(page_ranges, Mapping):
            raise ValueError("人物提及计划 page_ranges 必须是 object")
        context_rules = raw.get("context_rules") or ()
        if not isinstance(context_rules, Sequence) or isinstance(context_rules, (str, bytes)):
            raise ValueError("人物提及计划 context_rules 必须是 array")
        review_kind = str(raw.get("review_kind") or "person_governance")
        if review_kind not in {"person_governance", "ruler_policy"}:
            raise ValueError("人物提及计划 review_kind 不支持")
        ruler_reign_page_ranges = raw.get("ruler_reign_page_ranges") or {}
        if not isinstance(ruler_reign_page_ranges, Mapping):
            raise ValueError("人物提及计划 ruler_reign_page_ranges 必须是 object")
        normalized_rules = []
        for rule in context_rules:
            if not isinstance(rule, Mapping):
                raise ValueError("人物提及计划 context_rules 项必须是 object")
            markers = tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in rule.get("markers") or ()
                    if len(str(item).strip()) >= 1
                )
            )
            page_titles = tuple(
                str(item).strip() for item in rule.get("page_titles") or () if str(item).strip()
            )
            page_prefixes = tuple(
                str(item).strip() for item in rule.get("page_prefixes") or () if str(item).strip()
            )
            if not markers or (not page_titles and not page_prefixes):
                raise ValueError("皇帝隐含主语规则缺少 markers 或页面范围")
            normalized_rules.append(
                {
                    "markers": list(markers),
                    "page_titles": list(page_titles),
                    "page_prefixes": list(page_prefixes),
                }
            )
        subjects.append(
            {
                "subject_ref": subject_ref,
                "subject_name": subject_name,
                "works": list(works),
                "surface_forms": list(surface_forms),
                "attribution_terms": list(
                    dict.fromkeys(
                        str(item).strip()
                        for item in raw.get("attribution_terms") or ()
                        if len(str(item).strip()) >= 2
                    )
                ),
                "priority_terms": list(
                    dict.fromkeys(
                        str(item).strip()
                        for item in raw.get("priority_terms") or ()
                        if len(str(item).strip()) >= 2
                    )
                ),
                "page_ranges": {
                    str(work): [int(bound) for bound in bounds]
                    for work, bounds in page_ranges.items()
                },
                "context_rules": normalized_rules,
                "review_kind": review_kind,
                "action_terms": list(
                    dict.fromkeys(
                        str(item).strip()
                        for item in raw.get("action_terms") or ()
                        if str(item).strip()
                    )
                ),
                "implementation_terms": list(
                    dict.fromkeys(
                        str(item).strip()
                        for item in raw.get("implementation_terms") or ()
                        if str(item).strip()
                    )
                ),
                "result_terms": list(
                    dict.fromkeys(
                        str(item).strip()
                        for item in raw.get("result_terms") or ()
                        if str(item).strip()
                    )
                ),
                "ruler_reign_page_ranges": {
                    str(work): [int(bound) for bound in bounds]
                    for work, bounds in ruler_reign_page_ranges.items()
                },
            }
        )
    return tuple(subjects)


def _page_matches_rule(page_title: str, rule: Mapping[str, object]) -> bool:
    return page_title in rule["page_titles"] or any(
        page_title.startswith(prefix) for prefix in rule["page_prefixes"]
    )


def _collect_mentions(
    source_index: LocalSourceTextIndex, subject: Mapping[str, object]
) -> tuple[_Mention, ...]:
    mentions: dict[tuple[object, ...], _Mention] = {}
    for page in source_index.iter_pages(
        works=subject["works"], page_ranges=subject["page_ranges"]
    ):
        for configured_form in subject["surface_forms"]:
            for surface_form in _variants(str(configured_form)):
                for start in _positions(page.raw_text, surface_form):
                    if _inside_heading(page.raw_text, start):
                        continue
                    mention = _Mention(
                        subject_ref=str(subject["subject_ref"]),
                        page_title=page.page_title,
                        work_title=page.work_title,
                        source_url=page.source_url,
                        revision_ref=page.revision_ref,
                        start_offset=start,
                        end_offset=start + len(surface_form),
                        surface_form=surface_form,
                        mention_kind="subject_surface",
                    )
                    key = (page.page_title, start, mention.end_offset, "subject_surface")
                    mentions[key] = mention
        for rule in subject["context_rules"]:
            if not _page_matches_rule(page.page_title, rule):
                continue
            for configured_marker in rule["markers"]:
                for marker in _variants(str(configured_marker)):
                    for start in _positions(page.raw_text, marker):
                        mention = _Mention(
                            subject_ref=str(subject["subject_ref"]),
                            page_title=page.page_title,
                            work_title=page.work_title,
                            source_url=page.source_url,
                            revision_ref=page.revision_ref,
                            start_offset=start,
                            end_offset=start + len(marker),
                            surface_form=marker,
                            mention_kind="ruler_context",
                        )
                        key = (page.page_title, start, mention.end_offset, "ruler_context")
                        mentions[key] = mention
    return tuple(
        sorted(
            mentions.values(),
            key=lambda item: (item.page_title, item.start_offset, item.end_offset, item.mention_kind),
        )
    )


def _read_metadata(path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    try:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            return dict(connection.execute("SELECT key, value FROM metadata"))
        finally:
            connection.close()
    except sqlite3.Error:
        return None


def build_subject_mention_index(
    source_index: LocalSourceTextIndex,
    payload: Mapping[str, object],
    output_path: Path,
) -> dict[str, object]:
    subjects = _validated_plan(payload, source_index)
    normalized_plan = {
        "schema_version": "subject-mention-plan-v2",
        "source_index_identity": source_index.identity,
        "subjects": list(subjects),
    }
    input_fingerprint = sha256(_canonical_payload(normalized_plan)).hexdigest()
    existing = _read_metadata(output_path)
    if existing and existing.get("schema_version") == MENTION_INDEX_SCHEMA_VERSION:
        if (
            existing.get("source_index_identity") == source_index.identity
            and existing.get("input_fingerprint") == input_fingerprint
        ):
            return {
                "schema_version": MENTION_INDEX_SCHEMA_VERSION,
                "source_index_identity": source_index.identity,
                "input_fingerprint": input_fingerprint,
                "subject_count": int(existing["subject_count"]),
                "mention_count": int(existing["mention_count"]),
                "changed": False,
                "output": str(output_path),
            }

    all_mentions = [
        mention
        for subject in subjects
        for mention in _collect_mentions(source_index, subject)
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{uuid4().hex}.tmp")
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE subjects (
                subject_ref TEXT PRIMARY KEY,
                subject_name TEXT NOT NULL,
                config_json TEXT NOT NULL
            );
            CREATE TABLE mentions (
                mention_id INTEGER PRIMARY KEY,
                subject_ref TEXT NOT NULL,
                page_title TEXT NOT NULL,
                work_title TEXT NOT NULL,
                source_url TEXT NOT NULL,
                revision_ref TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                surface_form TEXT NOT NULL,
                mention_kind TEXT NOT NULL,
                UNIQUE(subject_ref, page_title, start_offset, end_offset, mention_kind)
            );
            CREATE INDEX mentions_subject_idx
                ON mentions(subject_ref, page_title, start_offset);
            CREATE INDEX mentions_page_idx ON mentions(page_title);
            """
        )
        connection.executemany(
            "INSERT INTO subjects(subject_ref, subject_name, config_json) VALUES (?, ?, ?)",
            (
                (
                    subject["subject_ref"],
                    subject["subject_name"],
                    _canonical_payload(subject).decode("utf-8"),
                )
                for subject in subjects
            ),
        )
        connection.executemany(
            """
            INSERT INTO mentions(
                subject_ref, page_title, work_title, source_url, revision_ref,
                start_offset, end_offset, surface_form, mention_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    item.subject_ref,
                    item.page_title,
                    item.work_title,
                    item.source_url,
                    item.revision_ref,
                    item.start_offset,
                    item.end_offset,
                    item.surface_form,
                    item.mention_kind,
                )
                for item in all_mentions
            ),
        )
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            (
                ("schema_version", MENTION_INDEX_SCHEMA_VERSION),
                ("source_index_identity", source_index.identity),
                ("input_fingerprint", input_fingerprint),
                ("subject_count", str(len(subjects))),
                ("mention_count", str(len(all_mentions))),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    os.replace(temporary, output_path)
    return {
        "schema_version": MENTION_INDEX_SCHEMA_VERSION,
        "source_index_identity": source_index.identity,
        "input_fingerprint": input_fingerprint,
        "subject_count": len(subjects),
        "mention_count": len(all_mentions),
        "changed": True,
        "output": str(output_path),
    }


def _matched_terms(text: str, terms: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        term
        for term in terms
        if any(variant in text for variant in _variants(term))
    )


def _heading_context(text: str, offset: int) -> tuple[str, int] | None:
    headings = tuple(match for match in _HEADING.finditer(text) if match.start() <= offset)
    if not headings:
        return None
    nearest = headings[-1]
    return nearest.group(2).strip(), len(nearest.group(1))


def _title_matches_context_rule(
    page_title: str, context_rules: Sequence[Mapping[str, object]]
) -> bool:
    return any(_page_matches_rule(page_title, rule) for rule in context_rules)


def _title_in_work_range(
    page_title: str,
    work_title: str,
    ranges: Mapping[str, Sequence[int]],
) -> bool:
    bounds = next(
        (
            tuple(int(bound) for bound in configured)
            for work, configured in ranges.items()
            if _T2S.convert(str(work)).replace(" ", "")
            == _T2S.convert(work_title).replace(" ", "")
        ),
        None,
    )
    if bounds is None:
        return False
    match = _PAGE_VOLUME.search(page_title)
    return (
        len(bounds) == 2
        and match is not None
        and bounds[0] <= int(match.group(1)) <= bounds[1]
    )


def _review_tier(
    *,
    review_kind: str,
    attribution_mode: str,
    structure_context: str,
    priority_terms: Sequence[str],
    action_terms: Sequence[str],
    implementation_terms: Sequence[str],
    result_terms: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    strong_attribution = attribution_mode in {
        "explicit_name",
        "biography_section",
        "ruler_context",
    }
    has_priority = bool(priority_terms)
    has_action = bool(action_terms)
    has_implementation = bool(implementation_terms)
    has_result = bool(result_terms)
    reasons = [attribution_mode, structure_context]
    if has_priority:
        reasons.append("topic_anchor")
    if has_action:
        reasons.append("action_anchor")
    if has_implementation:
        reasons.append("implementation_anchor")
    if has_result:
        reasons.append("result_anchor")

    if review_kind == "ruler_policy":
        core_context = structure_context in {
            "ruler_core_text",
            "ruler_reign_chronicle",
        }
        policy_context = core_context or has_priority
        if (
            strong_attribution
            and policy_context
            and has_action
            and has_implementation
            and has_result
        ):
            return "A", tuple(reasons)
        if strong_attribution and (
            (core_context and (has_action or has_priority))
            or (has_priority and has_action)
        ):
            return "B", tuple(reasons)
        if strong_attribution or has_priority:
            return "C", tuple(reasons)
        return "D", tuple(reasons)

    if (
        strong_attribution
        and has_action
        and has_implementation
        and has_result
    ):
        return "A", tuple(reasons)
    if strong_attribution and (has_action or has_priority):
        return "B", tuple(reasons)
    if strong_attribution or has_action or has_priority:
        return "C", tuple(reasons)
    return "D", tuple(reasons)


def _period_markers(text: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(_T2S.convert(match.group(0)).replace(" ", "") for match in _REIGN_YEAR.finditer(text))
    )


def _window_ref(subject_ref: str, window: Mapping[str, object]) -> str:
    digest = sha256()
    for value in (
        subject_ref,
        window["page_title"],
        window["revision_ref"],
        window["start_offset"],
        window["end_offset"],
    ):
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\0")
    return "MENTIONWIN-" + digest.hexdigest()[:16].upper()


def cluster_first_review_windows(
    subject_ref: str,
    windows: Sequence[Mapping[str, object]],
    *,
    same_page_max_gap_chars: int = 800,
) -> tuple[dict[str, object], ...]:
    """Conservatively cluster A-tier windows without deleting their provenance."""
    candidates = [window for window in windows if window.get("review_tier") == "A"]
    if not candidates:
        return ()
    parents = list(range(len(candidates)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    def terms(window: Mapping[str, object], field: str) -> set[str]:
        return {
            str(item)
            for item in window.get(field) or ()
            if str(item) != "ruler_context_marker"
        }

    for left_index, left in enumerate(candidates):
        for right_index in range(left_index + 1, len(candidates)):
            right = candidates[right_index]
            shared_priority = terms(left, "matched_nearby_priority_terms") & terms(
                right, "matched_nearby_priority_terms"
            )
            shared_action = terms(left, "matched_action_terms") & terms(
                right, "matched_action_terms"
            )
            shared_implementation = terms(
                left, "matched_implementation_terms"
            ) & terms(right, "matched_implementation_terms")
            shared_result = terms(left, "matched_result_terms") & terms(
                right, "matched_result_terms"
            )
            same_page = left["page_title"] == right["page_title"]
            page_gap = max(
                0,
                int(right["start_offset"]) - int(left["end_offset"]),
                int(left["start_offset"]) - int(right["end_offset"]),
            )
            if same_page and page_gap <= same_page_max_gap_chars and (
                shared_priority
                or shared_action
                or shared_implementation
                or shared_result
            ):
                union(left_index, right_index)
                continue
            shared_period = set(left.get("period_markers") or ()) & set(
                right.get("period_markers") or ()
            )
            if (
                not same_page
                and shared_period
                and shared_priority
                and (shared_action or shared_implementation)
                and (shared_implementation or shared_result)
            ):
                union(left_index, right_index)

    grouped: dict[int, list[Mapping[str, object]]] = {}
    for index, window in enumerate(candidates):
        grouped.setdefault(find(index), []).append(window)
    clusters = []
    for grouped_windows in grouped.values():
        grouped_windows.sort(
            key=lambda item: (str(item["page_title"]), int(item["start_offset"]))
        )
        window_refs = [str(item["window_ref"]) for item in grouped_windows]
        digest = sha256((subject_ref + "\0" + "\0".join(window_refs)).encode("utf-8"))
        page_titles = sorted({str(item["page_title"]) for item in grouped_windows})
        clusters.append(
            {
                "cluster_ref": "MENTIONCLUSTER-" + digest.hexdigest()[:16].upper(),
                "review_tier": "A",
                "representative_window_ref": window_refs[0],
                "window_refs": window_refs,
                "window_count": len(grouped_windows),
                "page_titles": page_titles,
                "work_titles": sorted(
                    {str(item["work_title"]) for item in grouped_windows}
                ),
                "period_markers": sorted(
                    {
                        str(marker)
                        for item in grouped_windows
                        for marker in item.get("period_markers") or ()
                    }
                ),
                "priority_terms": sorted(
                    {
                        str(term)
                        for item in grouped_windows
                        for term in item.get("matched_nearby_priority_terms") or ()
                    }
                ),
                "action_terms": sorted(
                    {
                        str(term)
                        for item in grouped_windows
                        for term in item.get("matched_action_terms") or ()
                        if str(term) != "ruler_context_marker"
                    }
                ),
                "merge_basis": (
                    "singleton"
                    if len(grouped_windows) == 1
                    else "same_page_proximity_and_shared_anchor"
                    if len(page_titles) == 1
                    else "cross_source_period_and_signature"
                ),
            }
        )
    return tuple(
        sorted(
            clusters,
            key=lambda item: (
                -int(item["window_count"]),
                str(item["cluster_ref"]),
            ),
        )
    )


def _merge_shared_page_windows(
    page_title: str,
    revision_ref: str,
    windows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Merge only overlapping exact slices; disjoint slices remain separate segments."""
    ordered = sorted(
        windows,
        key=lambda item: (
            int(item["start_offset"]),
            int(item["end_offset"]),
            str(item["subject_ref"]),
            str(item["window_ref"]),
        ),
    )
    merged: list[dict[str, object]] = []
    for window in ordered:
        start = int(window["start_offset"])
        end = int(window["end_offset"])
        text = str(window["text"])
        if start < 0 or end <= start or len(text) != end - start:
            raise ValueError("共享审阅窗口偏移与文本长度不一致")
        member = {
            "subject_ref": str(window["subject_ref"]),
            "subject_name": str(window["subject_name"]),
            "window_ref": str(window["window_ref"]),
            "review_tier": str(window["review_tier"]),
            "surface_forms": sorted(str(item) for item in window.get("surface_forms") or ()),
            "mention_offsets": sorted(int(item) for item in window.get("mention_offsets") or ()),
        }
        if not merged or start > int(merged[-1]["end_offset"]):
            merged.append(
                {
                    "start_offset": start,
                    "end_offset": end,
                    "text": text,
                    "members": [member],
                }
            )
            continue
        current = merged[-1]
        current_start = int(current["start_offset"])
        current_end = int(current["end_offset"])
        current_text = str(current["text"])
        overlap_start = max(current_start, start)
        overlap_end = min(current_end, end)
        if overlap_end > overlap_start:
            current_slice = current_text[
                overlap_start - current_start : overlap_end - current_start
            ]
            incoming_slice = text[overlap_start - start : overlap_end - start]
            if current_slice != incoming_slice:
                raise ValueError("共享审阅窗口的重叠原文不一致")
        if end > current_end:
            current["text"] = current_text + text[max(0, current_end - start) :]
            current["end_offset"] = end
        current["members"].append(member)

    segments = []
    for segment in merged:
        members = sorted(
            segment["members"],
            key=lambda item: (item["subject_ref"], item["window_ref"]),
        )
        text = str(segment["text"])
        digest = sha256()
        for value in (
            page_title,
            revision_ref,
            segment["start_offset"],
            segment["end_offset"],
            sha256(text.encode("utf-8")).hexdigest(),
        ):
            digest.update(str(value).encode("utf-8"))
            digest.update(b"\0")
        segments.append(
            {
                "segment_ref": "SHAREDSEG-" + digest.hexdigest()[:16].upper(),
                "start_offset": int(segment["start_offset"]),
                "end_offset": int(segment["end_offset"]),
                "text": text,
                "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
                "subject_refs": sorted({item["subject_ref"] for item in members}),
                "window_refs": sorted({item["window_ref"] for item in members}),
                "members": members,
            }
        )
    return tuple(segments)


def build_shared_review_plan(
    report: Mapping[str, object],
    *,
    review_tiers: Sequence[str] = ("A", "B"),
) -> dict[str, object]:
    """Build one neutral-extraction model batch per source page across subjects."""
    if report.get("schema_version") != MENTION_REPORT_SCHEMA_VERSION:
        raise ValueError("共享审阅计划仅支持当前 v3 人物提及报告")
    tiers = tuple(dict.fromkeys(str(item).strip().upper() for item in review_tiers))
    if not tiers or any(item not in {"A", "B", "C", "D"} for item in tiers):
        raise ValueError("共享审阅层级必须从 A/B/C/D 中选择")
    raw_subjects = report.get("subjects")
    if not isinstance(raw_subjects, Sequence) or isinstance(raw_subjects, (str, bytes)):
        raise ValueError("人物提及审阅报告缺少 subjects")

    pages: dict[tuple[str, str], dict[str, object]] = {}
    scheduled_window_count = 0
    scheduled_subject_refs: set[str] = set()
    for subject in raw_subjects:
        if not isinstance(subject, Mapping):
            raise ValueError("人物提及审阅报告 subjects 项必须是 object")
        subject_ref = str(subject.get("subject_ref") or "")
        subject_name = str(subject.get("subject_name") or "")
        if not subject_ref or not subject_name:
            raise ValueError("共享审阅主体必须具有 subject_ref 和 subject_name")
        for raw_window in subject.get("windows") or ():
            if not isinstance(raw_window, Mapping):
                raise ValueError("共享审阅窗口必须是 object")
            tier = str(raw_window.get("review_tier") or "").upper()
            if tier not in tiers:
                continue
            page_title = str(raw_window.get("page_title") or "")
            revision_ref = str(raw_window.get("revision_ref") or "")
            if not page_title or not revision_ref:
                raise ValueError("共享审阅窗口缺少页面或 revision")
            page = pages.setdefault(
                (page_title, revision_ref),
                {
                    "page_title": page_title,
                    "work_title": str(raw_window.get("work_title") or ""),
                    "source_url": str(raw_window.get("source_url") or ""),
                    "revision_ref": revision_ref,
                    "windows": [],
                },
            )
            if page["work_title"] != str(raw_window.get("work_title") or ""):
                raise ValueError("共享审阅同一页面的书名不一致")
            page["windows"].append(
                {
                    **raw_window,
                    "subject_ref": subject_ref,
                    "subject_name": subject_name,
                    "review_tier": tier,
                }
            )
            scheduled_window_count += 1
            scheduled_subject_refs.add(subject_ref)

    batches = []
    for (_, _), page in sorted(pages.items()):
        segments = _merge_shared_page_windows(
            str(page["page_title"]),
            str(page["revision_ref"]),
            page["windows"],
        )
        subject_refs = sorted(
            {
                str(member["subject_ref"])
                for segment in segments
                for member in segment["members"]
            }
        )
        window_refs = sorted(
            {
                str(window_ref)
                for segment in segments
                for window_ref in segment["window_refs"]
            }
        )
        digest = sha256()
        for value in (
            page["page_title"],
            page["revision_ref"],
            *[segment["segment_ref"] for segment in segments],
        ):
            digest.update(str(value).encode("utf-8"))
            digest.update(b"\0")
        batches.append(
            {
                "batch_ref": "SHAREDBATCH-" + digest.hexdigest()[:16].upper(),
                "page_title": page["page_title"],
                "work_title": page["work_title"],
                "source_url": page["source_url"],
                "revision_ref": page["revision_ref"],
                "subject_refs": subject_refs,
                "subject_count": len(subject_refs),
                "window_refs": window_refs,
                "window_count": len(window_refs),
                "segments": list(segments),
                "segment_count": len(segments),
                "review_status": "not_started",
                "extraction_scope": "neutral_facts_for_all_matched_subjects",
            }
        )
    return {
        "schema_version": SHARED_REVIEW_PLAN_SCHEMA_VERSION,
        "status": "shadow_only",
        "source_report_schema_version": MENTION_REPORT_SCHEMA_VERSION,
        "source_index_identity": report.get("source_index_identity"),
        "mention_index_fingerprint": report.get("mention_index_fingerprint"),
        "review_tiers": list(tiers),
        "subject_count": len(scheduled_subject_refs),
        "scheduled_window_count": scheduled_window_count,
        "source_page_count": len(batches),
        "shared_segment_count": sum(batch["segment_count"] for batch in batches),
        "model_call_budget": len(batches),
        "page_batches": batches,
        "network_requests": 0,
        "database_writes": 0,
        "formal_writes": 0,
        "model_calls": 0,
    }


def build_first_review_worklist(report: Mapping[str, object]) -> dict[str, object]:
    """Materialize review cards and a deduplicated, not-started refetch plan."""
    if report.get("schema_version") != MENTION_REPORT_SCHEMA_VERSION:
        raise ValueError("人物提及审阅待办仅支持当前 v3 影子报告")
    raw_subjects = report.get("subjects")
    if not isinstance(raw_subjects, Sequence) or isinstance(raw_subjects, (str, bytes)):
        raise ValueError("人物提及审阅报告缺少 subjects")
    cards = []
    source_pages: dict[tuple[str, str], dict[str, object]] = {}
    subject_summaries = []
    for subject in raw_subjects:
        if not isinstance(subject, Mapping):
            raise ValueError("人物提及审阅报告 subjects 项必须是 object")
        subject_ref = str(subject.get("subject_ref") or "")
        subject_name = str(subject.get("subject_name") or "")
        windows = {
            str(window["window_ref"]): window
            for window in subject.get("windows") or ()
            if isinstance(window, Mapping)
        }
        subject_cards = []
        for cluster in subject.get("first_review_clusters") or ():
            if not isinstance(cluster, Mapping):
                raise ValueError("人物提及审阅报告 cluster 必须是 object")
            window_refs = tuple(str(item) for item in cluster.get("window_refs") or ())
            if not window_refs or any(ref not in windows for ref in window_refs):
                raise ValueError("人物提及审阅 cluster 引用了不存在的窗口")
            members = [windows[ref] for ref in window_refs]
            representative_ref = str(cluster["representative_window_ref"])
            representative = windows[representative_ref]
            periods = sorted(
                {
                    str(marker)
                    for member in members
                    for marker in member.get("period_markers") or ()
                }
            )
            priorities = sorted(
                {
                    str(term)
                    for member in members
                    for term in member.get("matched_nearby_priority_terms") or ()
                }
            )
            actions = sorted(
                {
                    str(term)
                    for member in members
                    for term in member.get("matched_action_terms") or ()
                    if str(term) != "ruler_context_marker"
                }
            )
            implementations = sorted(
                {
                    str(term)
                    for member in members
                    for term in member.get("matched_implementation_terms") or ()
                }
            )
            results = sorted(
                {
                    str(term)
                    for member in members
                    for term in member.get("matched_result_terms") or ()
                }
            )
            pages = {}
            for member in members:
                page_key = (str(member["page_title"]), str(member["revision_ref"]))
                page = pages.setdefault(
                    page_key,
                    {
                        "page_title": page_key[0],
                        "work_title": str(member["work_title"]),
                        "source_url": str(member["source_url"]),
                        "revision_ref": page_key[1],
                        "window_refs": [],
                        "window_spans": [],
                    },
                )
                page["window_refs"].append(str(member["window_ref"]))
                page["window_spans"].append(
                    {
                        "window_ref": str(member["window_ref"]),
                        "start_offset": int(member["start_offset"]),
                        "end_offset": int(member["end_offset"]),
                        "expected_text_hash": sha256(
                            str(member["text"]).encode("utf-8")
                        ).hexdigest(),
                    }
                )
            flags = []
            if not periods:
                flags.append("missing_period_marker")
            if len(periods) > 1:
                flags.append("multiple_period_markers")
            if len(pages) == 1:
                flags.append("single_page_only")
            if len({page["work_title"] for page in pages.values()}) == 1:
                flags.append("single_work_only")
            if any(
                member.get("attribution_mode") == "short_form_only"
                for member in members
            ):
                flags.append("short_form_attribution_present")
            if all(
                member.get("attribution_mode") == "ruler_context"
                for member in members
            ):
                flags.append("ruler_context_only")
            if not priorities:
                flags.append("no_priority_anchor")
            if len({page["work_title"] for page in pages.values()}) > 1:
                flags.append("cross_source_merge_requires_confirmation")
            label_parts = [*(periods[:1] or ["纪年待核"]), *(priorities[:2] or actions[:2])]
            card = {
                "cluster_ref": str(cluster["cluster_ref"]),
                "subject_ref": subject_ref,
                "subject_name": subject_name,
                "review_tier": "A",
                "review_label": "｜".join(label_parts),
                "representative_window_ref": representative_ref,
                "representative_text": str(representative["text"]),
                "window_refs": list(window_refs),
                "period_markers": periods,
                "priority_terms": priorities,
                "action_terms": actions,
                "implementation_terms": implementations,
                "result_terms": results,
                "source_pages": sorted(
                    pages.values(), key=lambda item: (item["work_title"], item["page_title"])
                ),
                "review_flags": flags,
                "review_status": "not_started",
                "refetch_status": "not_started",
            }
            cards.append(card)
            subject_cards.append(card)
            for page_key, page in pages.items():
                global_page = source_pages.setdefault(
                    page_key,
                    {
                        "page_title": page["page_title"],
                        "work_title": page["work_title"],
                        "source_url": page["source_url"],
                        "revision_ref": page["revision_ref"],
                        "subject_refs": set(),
                        "cluster_refs": set(),
                        "window_refs": set(),
                        "refetch_status": "not_started",
                    },
                )
                global_page["subject_refs"].add(subject_ref)
                global_page["cluster_refs"].add(card["cluster_ref"])
                global_page["window_refs"].update(page["window_refs"])
        subject_summaries.append(
            {
                "subject_ref": subject_ref,
                "subject_name": subject_name,
                "review_card_count": len(subject_cards),
                "single_work_card_count": sum(
                    "single_work_only" in card["review_flags"] for card in subject_cards
                ),
                "missing_period_card_count": sum(
                    "missing_period_marker" in card["review_flags"] for card in subject_cards
                ),
                "unique_refetch_page_count": len(
                    {
                        (page["page_title"], page["revision_ref"])
                        for card in subject_cards
                        for page in card["source_pages"]
                    }
                ),
                "review_flag_counts": {
                    flag: sum(flag in card["review_flags"] for card in subject_cards)
                    for flag in sorted(
                        {
                            flag
                            for card in subject_cards
                            for flag in card["review_flags"]
                        }
                    )
                },
            }
        )
    serialized_pages = []
    for page in source_pages.values():
        serialized_pages.append(
            {
                **{
                    key: value
                    for key, value in page.items()
                    if key not in {"subject_refs", "cluster_refs", "window_refs"}
                },
                "subject_refs": sorted(page["subject_refs"]),
                "cluster_refs": sorted(page["cluster_refs"]),
                "window_refs": sorted(page["window_refs"]),
            }
        )
    return {
        "schema_version": REVIEW_WORKLIST_SCHEMA_VERSION,
        "status": "shadow_only",
        "source_report_schema_version": MENTION_REPORT_SCHEMA_VERSION,
        "source_index_identity": report.get("source_index_identity"),
        "mention_index_fingerprint": report.get("mention_index_fingerprint"),
        "review_card_count": len(cards),
        "unique_refetch_page_count": len(serialized_pages),
        "subject_summaries": subject_summaries,
        "review_cards": sorted(
            cards, key=lambda item: (item["subject_ref"], item["cluster_ref"])
        ),
        "refetch_pages": sorted(
            serialized_pages, key=lambda item: (item["work_title"], item["page_title"])
        ),
        "network_requests": 0,
        "database_writes": 0,
        "formal_writes": 0,
        "model_calls": 0,
    }


def _snapshot_cache_path(state_dir: Path, page_title: str, revision_ref: str) -> Path:
    digest = sha256((page_title + "\0" + revision_ref).encode("utf-8")).hexdigest()
    return state_dir / f"SOURCEPAGE-{digest[:20].upper()}.json"


def _read_cached_snapshot(path: Path) -> WikisourcePageSnapshot | None:
    if not path.is_file():
        return None
    try:
        return WikisourcePageSnapshot(**json.loads(path.read_text(encoding="utf-8")))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def refetch_first_review_worklist(
    worklist: Mapping[str, object],
    *,
    state_dir: Path,
    max_workers: int = 6,
    timeout_seconds: float = 30.0,
    max_attempts: int = 2,
    fetch=fetch_wikisource_revision_text,
    batch_fetch=None,
) -> tuple[dict[str, object], dict[str, int]]:
    if worklist.get("schema_version") != REVIEW_WORKLIST_SCHEMA_VERSION:
        raise ValueError("人物提及回源仅支持当前审阅待办")
    if max_workers <= 0 or timeout_seconds <= 0 or max_attempts <= 0:
        raise ValueError("人物提及回源并发、超时和尝试次数必须为正数")
    raw_pages = worklist.get("refetch_pages")
    raw_cards = worklist.get("review_cards")
    if (
        not isinstance(raw_pages, Sequence)
        or isinstance(raw_pages, (str, bytes))
        or not isinstance(raw_cards, Sequence)
        or isinstance(raw_cards, (str, bytes))
    ):
        raise ValueError("人物提及回源待办缺少 refetch_pages 或 review_cards")
    state_dir.mkdir(parents=True, exist_ok=True)

    def load_page(page: Mapping[str, object]) -> dict[str, object]:
        page_title = str(page["page_title"])
        revision_ref = str(page["revision_ref"])
        cache_path = _snapshot_cache_path(state_dir, page_title, revision_ref)
        cached = _read_cached_snapshot(cache_path)
        if (
            cached is not None
            and cached.requested_title == page_title
            and str(cached.revision_id) == revision_ref
        ):
            return {
                "status": "succeeded",
                "cache_hit": True,
                "network_requests": 0,
                "state_writes": 0,
                "snapshot": cached,
                "cache_path": str(cache_path),
            }
        errors = []
        network_requests = 0
        for _attempt in range(1, max_attempts + 1):
            network_requests += 1
            try:
                snapshot = fetch(
                    page_code=cache_path.stem,
                    page_title=page_title,
                    expected_revision_id=int(revision_ref),
                    timeout_seconds=timeout_seconds,
                )
                changed = _atomic_json(cache_path, asdict(snapshot))
                return {
                    "status": "succeeded",
                    "cache_hit": False,
                    "network_requests": network_requests,
                    "state_writes": int(changed),
                    "snapshot": snapshot,
                    "cache_path": str(cache_path),
                }
            except ValueError as error:
                errors.append(f"{type(error).__name__}: {error}")
                break
            except Exception as error:  # network errors remain page-local
                errors.append(f"{type(error).__name__}: {error}")
        return {
            "status": "failed",
            "cache_hit": False,
            "network_requests": network_requests,
            "state_writes": 0,
            "errors": errors,
            "cache_path": str(cache_path),
        }

    fetched: dict[tuple[str, str], dict[str, object]] = {}
    batch_network_requests = 0
    if batch_fetch is not None:
        missing_pages = []
        for page in raw_pages:
            if not isinstance(page, Mapping):
                raise ValueError("人物提及回源 refetch_pages 项必须是 object")
            page_title = str(page["page_title"])
            revision_ref = str(page["revision_ref"])
            cache_path = _snapshot_cache_path(state_dir, page_title, revision_ref)
            cached = _read_cached_snapshot(cache_path)
            key = (page_title, revision_ref)
            if (
                cached is not None
                and cached.requested_title == page_title
                and str(cached.revision_id) == revision_ref
            ):
                fetched[key] = {
                    "status": "succeeded",
                    "cache_hit": True,
                    "network_requests": 0,
                    "state_writes": 0,
                    "snapshot": cached,
                    "cache_path": str(cache_path),
                }
            else:
                missing_pages.append(page)
        for chunk_start in range(0, len(missing_pages), 20):
            chunk = missing_pages[chunk_start:chunk_start + 20]
            errors = []
            snapshots = None
            for attempt in range(1, max_attempts + 1):
                batch_network_requests += 1
                try:
                    snapshots = batch_fetch(
                        page_titles=[str(page["page_title"]) for page in chunk],
                        timeout_seconds=max(timeout_seconds, 60.0),
                    )
                    break
                except Exception as error:
                    errors.append(f"{type(error).__name__}: {error}")
                    if attempt < max_attempts:
                        sleep(min(10 * attempt, 30))
            if snapshots is None:
                for page in chunk:
                    key = (str(page["page_title"]), str(page["revision_ref"]))
                    fetched[key] = {
                        "status": "failed",
                        "cache_hit": False,
                        "network_requests": 0,
                        "state_writes": 0,
                        "errors": errors,
                        "cache_path": str(
                            _snapshot_cache_path(state_dir, key[0], key[1])
                        ),
                    }
                continue
            for page in chunk:
                page_title = str(page["page_title"])
                revision_ref = str(page["revision_ref"])
                cache_path = _snapshot_cache_path(state_dir, page_title, revision_ref)
                snapshot = snapshots.get(page_title)
                key = (page_title, revision_ref)
                if snapshot is None:
                    fetched[key] = {
                        "status": "failed",
                        "cache_hit": False,
                        "network_requests": 0,
                        "state_writes": 0,
                        "errors": ["batch_response_missing_page"],
                        "cache_path": str(cache_path),
                    }
                elif str(snapshot.revision_id) != revision_ref:
                    fetched[key] = {
                        "status": "failed",
                        "cache_hit": False,
                        "network_requests": 0,
                        "state_writes": 0,
                        "errors": [
                            f"revision_drift expected={revision_ref} actual={snapshot.revision_id}"
                        ],
                        "cache_path": str(cache_path),
                    }
                else:
                    changed = _atomic_json(cache_path, asdict(snapshot))
                    fetched[key] = {
                        "status": "succeeded",
                        "cache_hit": False,
                        "network_requests": 0,
                        "state_writes": int(changed),
                        "snapshot": snapshot,
                        "cache_path": str(cache_path),
                    }
            if chunk_start + 20 < len(missing_pages):
                sleep(1)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(load_page, page): page
                for page in raw_pages
                if isinstance(page, Mapping)
            }
            for future in as_completed(futures):
                page = futures[future]
                fetched[(str(page["page_title"]), str(page["revision_ref"]))] = future.result()

    page_results = []
    for raw_page in raw_pages:
        if not isinstance(raw_page, Mapping):
            raise ValueError("人物提及回源 refetch_pages 项必须是 object")
        key = (str(raw_page["page_title"]), str(raw_page["revision_ref"]))
        fetched_page = fetched[key]
        snapshot = fetched_page.get("snapshot")
        page_results.append(
            {
                **{key: value for key, value in raw_page.items() if key != "refetch_status"},
                "status": fetched_page["status"],
                "cache_path": fetched_page["cache_path"],
                "revision_timestamp": (
                    snapshot.revision_timestamp
                    if isinstance(snapshot, WikisourcePageSnapshot)
                    else ""
                ),
                "content_hash": (
                    snapshot.content_hash
                    if isinstance(snapshot, WikisourcePageSnapshot)
                    else ""
                ),
                "failure_reasons": list(fetched_page.get("errors") or ()),
            }
        )

    passages = []
    cluster_results = []
    for raw_card in raw_cards:
        if not isinstance(raw_card, Mapping):
            raise ValueError("人物提及回源 review_cards 项必须是 object")
        card_failures = []
        card_passage_refs = []
        for page in raw_card.get("source_pages") or ():
            key = (str(page["page_title"]), str(page["revision_ref"]))
            fetched_page = fetched[key]
            snapshot = fetched_page.get("snapshot")
            if not isinstance(snapshot, WikisourcePageSnapshot):
                card_failures.append(
                    {
                        "page_title": key[0],
                        "reason": "source_page_fetch_failed",
                        "details": list(fetched_page.get("errors") or ()),
                    }
                )
                continue
            for span in page.get("window_spans") or ():
                start = int(span["start_offset"])
                end = int(span["end_offset"])
                raw_text = snapshot.raw_text[start:end]
                actual_hash = sha256(raw_text.encode("utf-8")).hexdigest()
                if actual_hash != str(span["expected_text_hash"]):
                    card_failures.append(
                        {
                            "page_title": key[0],
                            "window_ref": str(span["window_ref"]),
                            "reason": "window_text_drift",
                            "expected_text_hash": str(span["expected_text_hash"]),
                            "actual_text_hash": actual_hash,
                        }
                    )
                    continue
                passage_digest = sha256(
                    (
                        str(raw_card["cluster_ref"])
                        + "\0"
                        + str(span["window_ref"])
                        + "\0"
                        + str(snapshot.revision_id)
                    ).encode("utf-8")
                ).hexdigest()
                passage_ref = "MENTIONPASSAGE-" + passage_digest[:16].upper()
                passages.append(
                    {
                        "passage_ref": passage_ref,
                        "cluster_ref": str(raw_card["cluster_ref"]),
                        "window_ref": str(span["window_ref"]),
                        "subject_ref": str(raw_card["subject_ref"]),
                        "subject_name": str(raw_card["subject_name"]),
                        "page_title": snapshot.canonical_title,
                        "source_url": snapshot.canonical_url,
                        "revision_ref": str(snapshot.revision_id),
                        "revision_timestamp": snapshot.revision_timestamp,
                        "content_hash": snapshot.content_hash,
                        "start_offset": start,
                        "end_offset": end,
                        "raw_text": raw_text,
                        "lineage_status": "exact_revision_offset_match",
                        "status": "shadow_source_passage",
                    }
                )
                card_passage_refs.append(passage_ref)
        expected_windows = len(raw_card.get("window_refs") or ())
        cluster_results.append(
            {
                "cluster_ref": str(raw_card["cluster_ref"]),
                "subject_ref": str(raw_card["subject_ref"]),
                "expected_window_count": expected_windows,
                "passage_count": len(card_passage_refs),
                "passage_refs": card_passage_refs,
                "status": (
                    "complete"
                    if len(card_passage_refs) == expected_windows
                    else "partial"
                    if card_passage_refs
                    else "failed"
                ),
                "failure_reasons": card_failures,
            }
        )

    runtime_audit = {
        "network_request_count": batch_network_requests
        + sum(int(item["network_requests"]) for item in fetched.values()),
        "cache_hit_count": sum(bool(item["cache_hit"]) for item in fetched.values()),
        "state_write_count": sum(int(item["state_writes"]) for item in fetched.values()),
    }
    stable_result = {
        "schema_version": REFETCH_RESULT_SCHEMA_VERSION,
        "status": "shadow_only",
        "source_worklist_schema_version": REVIEW_WORKLIST_SCHEMA_VERSION,
        "source_index_identity": worklist.get("source_index_identity"),
        "mention_index_fingerprint": worklist.get("mention_index_fingerprint"),
        "source_page_count": len(page_results),
        "succeeded_page_count": sum(item["status"] == "succeeded" for item in page_results),
        "failed_page_count": sum(item["status"] == "failed" for item in page_results),
        "cluster_count": len(cluster_results),
        "complete_cluster_count": sum(item["status"] == "complete" for item in cluster_results),
        "partial_cluster_count": sum(item["status"] == "partial" for item in cluster_results),
        "failed_cluster_count": sum(item["status"] == "failed" for item in cluster_results),
        "passage_count": len(passages),
        "source_pages": sorted(page_results, key=lambda item: (item["work_title"], item["page_title"])),
        "cluster_results": sorted(cluster_results, key=lambda item: item["cluster_ref"]),
        "passages": sorted(passages, key=lambda item: item["passage_ref"]),
        "database_writes": 0,
        "formal_writes": 0,
        "model_calls": 0,
    }
    return stable_result, runtime_audit


def build_subject_mention_report(
    source_index: LocalSourceTextIndex,
    mention_index_path: Path,
    *,
    window_chars: int = 440,
    merge_gap_chars: int = 80,
) -> dict[str, object]:
    if window_chars <= 0 or merge_gap_chars < 0:
        raise ValueError("段落窗口必须为正数，合并间距不得为负数")
    metadata = _read_metadata(mention_index_path)
    if not metadata or metadata.get("schema_version") != MENTION_INDEX_SCHEMA_VERSION:
        raise ValueError("人物提及旁路索引不存在或版本不支持")
    if metadata.get("source_index_identity") != source_index.identity:
        raise ValueError("人物提及旁路索引与本地全文索引 identity 不一致")

    connection = sqlite3.connect(
        f"file:{mention_index_path.resolve()}?mode=ro", uri=True
    )
    connection.row_factory = sqlite3.Row
    try:
        subject_rows = tuple(
            connection.execute(
                "SELECT subject_ref, subject_name, config_json FROM subjects ORDER BY subject_ref"
            )
        )
        mention_rows = tuple(
            connection.execute(
                "SELECT * FROM mentions ORDER BY subject_ref, page_title, start_offset, end_offset"
            )
        )
    finally:
        connection.close()

    pages_by_title = {
        page.page_title: page
        for subject_row in subject_rows
        for page in source_index.iter_pages(
            works=json.loads(subject_row["config_json"])["works"],
            page_ranges=json.loads(subject_row["config_json"])["page_ranges"],
        )
    }
    mentions_by_subject: dict[str, list[sqlite3.Row]] = {}
    for row in mention_rows:
        mentions_by_subject.setdefault(str(row["subject_ref"]), []).append(row)

    radius_before = window_chars // 2
    radius_after = window_chars - radius_before
    subjects = []
    for subject_row in subject_rows:
        subject_ref = str(subject_row["subject_ref"])
        config = json.loads(subject_row["config_json"])
        raw_mentions = mentions_by_subject.get(subject_ref, [])
        windows: list[dict[str, object]] = []
        for mention in raw_mentions:
            page = pages_by_title.get(str(mention["page_title"]))
            if page is None or page.revision_ref != str(mention["revision_ref"]):
                raise ValueError("人物提及旁路索引的页面或 revision 已漂移")
            start = max(0, int(mention["start_offset"]) - radius_before)
            end = min(len(page.raw_text), int(mention["end_offset"]) + radius_after)
            if (
                windows
                and windows[-1]["page_title"] == page.page_title
                and start <= int(windows[-1]["end_offset"]) + merge_gap_chars
                and max(int(windows[-1]["end_offset"]), end)
                - int(windows[-1]["start_offset"])
                <= window_chars + merge_gap_chars
            ):
                windows[-1]["end_offset"] = max(int(windows[-1]["end_offset"]), end)
                windows[-1]["surface_forms"].add(str(mention["surface_form"]))
                windows[-1]["mention_kinds"].add(str(mention["mention_kind"]))
                windows[-1]["mention_offsets"].add(int(mention["start_offset"]))
                windows[-1]["mention_count"] = int(windows[-1]["mention_count"]) + 1
            else:
                windows.append(
                    {
                        "page_title": page.page_title,
                        "work_title": page.work_title,
                        "source_url": page.source_url,
                        "revision_ref": page.revision_ref,
                        "start_offset": start,
                        "end_offset": end,
                        "surface_forms": {str(mention["surface_form"])},
                        "mention_kinds": {str(mention["mention_kind"])},
                        "mention_offsets": {int(mention["start_offset"])},
                        "mention_count": 1,
                    }
                )
        report_windows = []
        for window in windows:
            page = pages_by_title[str(window["page_title"])]
            text = page.raw_text[int(window["start_offset"]):int(window["end_offset"])]
            focus_text = "\n".join(
                page.raw_text[
                    max(int(window["start_offset"]), offset - REVIEW_PROXIMITY_CHARS):
                    min(int(window["end_offset"]), offset + REVIEW_PROXIMITY_CHARS)
                ]
                for offset in sorted(window["mention_offsets"])
            )
            attribution = _matched_terms(focus_text, config["attribution_terms"])
            priority = _matched_terms(text, config["priority_terms"])
            nearby_priority = _matched_terms(focus_text, config["priority_terms"])
            kinds = tuple(sorted(window["mention_kinds"]))
            actions = _matched_terms(focus_text, config["action_terms"])
            if "ruler_context" in kinds:
                actions = tuple(dict.fromkeys((*actions, "ruler_context_marker")))
            implementations = _matched_terms(
                focus_text, config["implementation_terms"]
            )
            results = _matched_terms(focus_text, config["result_terms"])
            first_mention_offset = min(window["mention_offsets"])
            heading = _heading_context(page.raw_text, first_mention_offset)
            section_title = heading[0] if heading else ""
            section_attributed = bool(
                section_title
                and _matched_terms(section_title, config["attribution_terms"])
            )
            ruler_core_text = _title_matches_context_rule(
                page.page_title, config["context_rules"]
            )
            ruler_reign_chronicle = _title_in_work_range(
                page.page_title,
                page.work_title,
                config["ruler_reign_page_ranges"],
            )
            structure_context = (
                "ruler_core_text"
                if ruler_core_text
                else "ruler_reign_chronicle"
                if ruler_reign_chronicle
                else "subject_biography_section"
                if section_attributed
                else "general_text"
            )
            attribution_mode = (
                "explicit_name"
                if attribution
                else "biography_section"
                if section_attributed
                else "ruler_context"
                if "ruler_context" in kinds
                else "short_form_only"
            )
            review_tier, reason_codes = _review_tier(
                review_kind=config["review_kind"],
                attribution_mode=attribution_mode,
                structure_context=structure_context,
                priority_terms=nearby_priority,
                action_terms=actions,
                implementation_terms=implementations,
                result_terms=results,
            )
            report_windows.append(
                {
                    **{
                        key: value
                        for key, value in window.items()
                        if key
                        not in {"surface_forms", "mention_kinds", "mention_offsets"}
                    },
                    "surface_forms": sorted(window["surface_forms"]),
                    "mention_kinds": list(kinds),
                    "mention_offsets": sorted(window["mention_offsets"]),
                    "section_title": section_title,
                    "structure_context": structure_context,
                    "matched_attribution_terms": list(attribution),
                    "matched_priority_terms": list(priority),
                    "matched_nearby_priority_terms": list(nearby_priority),
                    "matched_action_terms": list(actions),
                    "matched_implementation_terms": list(implementations),
                    "matched_result_terms": list(results),
                    "attribution_mode": attribution_mode,
                    "review_tier": review_tier,
                    "review_reason_codes": list(reason_codes),
                    "period_markers": list(_period_markers(text)),
                    "text": text,
                }
            )
            report_windows[-1]["window_ref"] = _window_ref(
                subject_ref, report_windows[-1]
            )
        report_windows.sort(
            key=lambda item: (
                {"A": 0, "B": 1, "C": 2, "D": 3}[item["review_tier"]],
                -len(item["matched_priority_terms"]),
                -len(item["matched_action_terms"]),
                item["page_title"],
                item["start_offset"],
            )
        )
        first_review_clusters = cluster_first_review_windows(
            subject_ref, report_windows
        )
        subjects.append(
            {
                "subject_ref": subject_ref,
                "subject_name": str(subject_row["subject_name"]),
                "mention_count": len(raw_mentions),
                "merged_window_count": len(report_windows),
                "explicit_attribution_window_count": sum(
                    item["attribution_mode"] == "explicit_name" for item in report_windows
                ),
                "ruler_context_window_count": sum(
                    item["attribution_mode"] == "ruler_context" for item in report_windows
                ),
                "short_form_only_window_count": sum(
                    item["attribution_mode"] == "short_form_only" for item in report_windows
                ),
                "review_tier_counts": {
                    tier: sum(item["review_tier"] == tier for item in report_windows)
                    for tier in ("A", "B", "C", "D")
                },
                "first_review_window_count": sum(
                    item["review_tier"] == "A" for item in report_windows
                ),
                "first_review_cluster_count": len(first_review_clusters),
                "first_review_clusters": list(first_review_clusters),
                "second_review_window_count": sum(
                    item["review_tier"] == "B" for item in report_windows
                ),
                "retained_not_scheduled_count": sum(
                    item["review_tier"] in {"C", "D"} for item in report_windows
                ),
                "prioritized_window_count": sum(
                    bool(item["matched_priority_terms"]) for item in report_windows
                ),
                "unprioritized_retained_count": sum(
                    not item["matched_priority_terms"] for item in report_windows
                ),
                "windows": report_windows,
            }
        )
    return {
        "schema_version": MENTION_REPORT_SCHEMA_VERSION,
        "status": "shadow_only",
        "source_index_identity": source_index.identity,
        "mention_index_fingerprint": metadata["input_fingerprint"],
        "window_chars": window_chars,
        "merge_gap_chars": merge_gap_chars,
        "review_proximity_chars": REVIEW_PROXIMITY_CHARS,
        "subjects": subjects,
        "network_requests": 0,
        "formal_writes": 0,
        "database_writes": 0,
        "model_calls": 0,
        "review_policy": {
            "A": "主体归责、行动、实施和结果锚点均在主体偏移邻域内；进入首轮人工复核",
            "B": "主体归责成立且有部分政策链锚点；仅在 A 层不足时复核",
            "C": "与主体相关但政策链不足；完整保留，不进入当前回源",
            "D": "短称或结构归责不足且无足够行动锚点；完整保留供查漏",
        },
    }


def _atomic_json(path: Path, payload: Mapping[str, object]) -> bool:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def build_identity_verified_passage_worklist(
    subject_plan: Mapping[str, Any], refetch: Mapping[str, Any]
) -> dict[str, Any]:
    if refetch.get("schema_version") != REFETCH_RESULT_SCHEMA_VERSION:
        raise ValueError("身份核验待办只接受精确回源结果")
    raw_people = list(subject_plan.get("people") or ())
    if not raw_people or len(raw_people) > 12:
        raise ValueError("身份核验待办要求1至12个人物入口")
    passages = [
        row
        for row in refetch.get("passages") or ()
        if row.get("status") in {"succeeded", "shadow_source_passage"}
        and row.get("lineage_status") == "exact_revision_offset_match"
        and str(row.get("subject_ref") or "").strip()
    ]
    people = []
    seen_refs: set[str] = set()
    for raw_person in raw_people:
        if not isinstance(raw_person, Mapping):
            raise ValueError("人物入口必须是 object")
        person_ref = str(raw_person.get("person_ref") or "").strip()
        person_name = str(raw_person.get("subject_name") or "").strip()
        if not person_ref or not person_name or person_ref in seen_refs:
            raise ValueError("人物入口缺少或重复 person_ref/subject_name")
        seen_refs.add(person_ref)
        source_forms = {
            str(value).strip()
            for value in (person_name, *(raw_person.get("recall_terms") or ()))
            if len(str(value).strip()) >= 2
        }
        surface_forms = sorted(
            source_forms
            | {_T2S.convert(value) for value in source_forms}
            | {_S2T.convert(value) for value in source_forms},
            key=lambda value: (-len(value), value),
        )
        normalized_forms = {_T2S.convert(value).replace(" ", "") for value in surface_forms}
        candidates: dict[tuple[object, ...], dict[str, Any]] = {}
        for passage in passages:
            raw_text = str(passage.get("raw_text") or "")
            normalized_text = _T2S.convert(raw_text).replace(" ", "")
            matched = sorted(value for value in normalized_forms if value in normalized_text)
            if not matched:
                continue
            locator = (
                str(passage.get("page_title") or ""),
                str(passage.get("revision_ref") or ""),
                int(passage.get("start_offset") or 0),
                int(passage.get("end_offset") or 0),
                sha256(raw_text.encode("utf-8")).hexdigest(),
            )
            candidate = {
                "passage_ref": str(passage["passage_ref"]),
                "page_title": str(passage.get("page_title") or ""),
                "revision_ref": str(passage.get("revision_ref") or ""),
                "start_offset": passage.get("start_offset"),
                "end_offset": passage.get("end_offset"),
                "raw_text": raw_text,
                "matched_surface_forms": matched,
                "retrieval_subject_ref": passage.get("subject_ref"),
                "retrieval_subject_match": passage.get("subject_ref") == person_ref,
            }
            current = candidates.get(locator)
            if current is None or (
                candidate["retrieval_subject_match"]
                and not current["retrieval_subject_match"]
            ):
                candidates[locator] = candidate
        ordered = sorted(
            candidates.values(),
            key=lambda row: (
                not row["retrieval_subject_match"],
                row["page_title"],
                int(row["start_offset"] or 0),
                row["passage_ref"],
            ),
        )
        overlap_clusters: list[list[dict[str, Any]]] = []
        for candidate in sorted(
            ordered,
            key=lambda row: (
                row["page_title"],
                row["revision_ref"],
                int(row["start_offset"] or 0),
                int(row["end_offset"] or 0),
            ),
        ):
            if not overlap_clusters:
                overlap_clusters.append([candidate])
                continue
            previous = overlap_clusters[-1][-1]
            same_page = (
                candidate["page_title"], candidate["revision_ref"]
            ) == (previous["page_title"], previous["revision_ref"])
            start = int(candidate["start_offset"] or 0)
            end = int(candidate["end_offset"] or 0)
            previous_start = int(previous["start_offset"] or 0)
            previous_end = int(previous["end_offset"] or 0)
            intersection = max(0, min(end, previous_end) - max(start, previous_start))
            shorter = min(max(1, end - start), max(1, previous_end - previous_start))
            if same_page and intersection / shorter >= 0.5:
                overlap_clusters[-1].append(candidate)
            else:
                overlap_clusters.append([candidate])
        ordered = [
            sorted(
                cluster,
                key=lambda row: (
                    not row["retrieval_subject_match"],
                    -len(row["matched_surface_forms"]),
                    len(row["raw_text"]),
                    row["passage_ref"],
                ),
            )[0]
            for cluster in overlap_clusters
        ]
        ordered.sort(
            key=lambda row: (
                not row["retrieval_subject_match"],
                row["page_title"],
                int(row["start_offset"] or 0),
                row["passage_ref"],
            )
        )
        people.append(
            {
                "person_ref": person_ref,
                "person": person_name,
                "surface_forms": surface_forms,
                "passage_count": len(ordered),
                "passages": ordered,
                "primary_passages": [
                    row for row in ordered if row["retrieval_subject_match"]
                ],
                "boundary_passages": [
                    row for row in ordered if not row["retrieval_subject_match"]
                ],
            }
        )
    return {
        "schema_version": "i5b-identity-verified-passage-worklist-v1",
        "status": "shadow_only",
        "person_count": len(people),
        "people": people,
        "network_requests": 0,
        "model_calls": 0,
        "database_writes": 0,
        "formal_writes": 0,
        "selection_policy": "先读本人检索入口的正文命中段；只有可能改变计分边界时才读其他入口中命中本人的边界段。排除旧投影段；同页重叠过半窗口只保留一个代表段，不设材料数量上限。",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建人物提及偏移旁路库和段落级影子报告")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--source-index", type=Path, required=True)
    build.add_argument("--input", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    report = subparsers.add_parser("report")
    report.add_argument("--source-index", type=Path, required=True)
    report.add_argument("--mention-index", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    report.add_argument("--window-chars", type=int, default=440)
    report.add_argument("--merge-gap-chars", type=int, default=80)
    review_worklist = subparsers.add_parser("review-worklist")
    review_worklist.add_argument("--report", type=Path, required=True)
    review_worklist.add_argument("--output", type=Path, required=True)
    shared_review = subparsers.add_parser("shared-review-plan")
    shared_review.add_argument("--report", type=Path, required=True)
    shared_review.add_argument("--output", type=Path, required=True)
    shared_review.add_argument("--review-tiers", nargs="+", default=["A", "B"])
    refetch = subparsers.add_parser("refetch")
    refetch.add_argument("--worklist", type=Path, required=True)
    refetch.add_argument("--state-dir", type=Path, required=True)
    refetch.add_argument("--output", type=Path, required=True)
    refetch.add_argument("--max-workers", type=int, default=6)
    refetch.add_argument("--timeout-seconds", type=float, default=30.0)
    refetch.add_argument("--max-attempts", type=int, default=2)
    identity_worklist = subparsers.add_parser("identity-worklist")
    identity_worklist.add_argument("--subject-plan", type=Path, required=True)
    identity_worklist.add_argument("--refetch-result", type=Path, required=True)
    identity_worklist.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "shared-review-plan":
        payload = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("人物提及审阅报告必须是 object")
        full_result = build_shared_review_plan(
            payload,
            review_tiers=args.review_tiers,
        )
        changed = _atomic_json(args.output, full_result)
        result = {
            key: full_result[key]
            for key in (
                "schema_version",
                "status",
                "review_tiers",
                "subject_count",
                "scheduled_window_count",
                "source_page_count",
                "shared_segment_count",
                "model_call_budget",
                "network_requests",
                "database_writes",
                "formal_writes",
                "model_calls",
            )
        } | {"changed": changed}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "identity-worklist":
        subject_plan = json.loads(args.subject_plan.read_text(encoding="utf-8"))
        refetch_result = json.loads(args.refetch_result.read_text(encoding="utf-8"))
        full_result = build_identity_verified_passage_worklist(subject_plan, refetch_result)
        changed = _atomic_json(args.output, full_result)
        print(
            json.dumps(
                {
                    "schema_version": full_result["schema_version"],
                    "person_count": full_result["person_count"],
                    "passage_counts": {
                        row["person"]: {
                            "primary": len(row["primary_passages"]),
                            "boundary": len(row["boundary_passages"]),
                        }
                        for row in full_result["people"]
                    },
                    "changed": changed,
                    "network_requests": 0,
                    "model_calls": 0,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "refetch":
        payload = json.loads(args.worklist.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("人物提及回源待办必须是 object")
        full_result, runtime_audit = refetch_first_review_worklist(
            payload,
            state_dir=args.state_dir,
            max_workers=args.max_workers,
            timeout_seconds=args.timeout_seconds,
            max_attempts=args.max_attempts,
            batch_fetch=fetch_wikisource_revision_batch,
        )
        changed = _atomic_json(args.output, full_result)
        result = {
            key: full_result[key]
            for key in (
                "schema_version",
                "status",
                "source_page_count",
                "succeeded_page_count",
                "failed_page_count",
                "cluster_count",
                "complete_cluster_count",
                "partial_cluster_count",
                "failed_cluster_count",
                "passage_count",
            )
        } | {"changed": changed, "runtime_audit": runtime_audit}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "review-worklist":
        payload = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("人物提及审阅报告必须是 object")
        full_result = build_first_review_worklist(payload)
        changed = _atomic_json(args.output, full_result)
        result = {
            "schema_version": full_result["schema_version"],
            "status": full_result["status"],
            "review_card_count": full_result["review_card_count"],
            "unique_refetch_page_count": full_result["unique_refetch_page_count"],
            "subject_summaries": full_result["subject_summaries"],
            "changed": changed,
            "network_requests": 0,
            "database_writes": 0,
            "formal_writes": 0,
            "model_calls": 0,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    source_index = LocalSourceTextIndex(args.source_index)
    if args.command == "build":
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("人物提及计划必须是 object")
        result = build_subject_mention_index(source_index, payload, args.output)
    else:
        result = build_subject_mention_report(
            source_index,
            args.mention_index,
            window_chars=args.window_chars,
            merge_gap_chars=args.merge_gap_chars,
        )
        result["changed"] = _atomic_json(args.output, result)
        full_result = result
        result = {
            key: full_result[key]
            for key in (
                "schema_version",
                "status",
                "source_index_identity",
                "mention_index_fingerprint",
                "window_chars",
                "merge_gap_chars",
                "review_proximity_chars",
                "changed",
                "network_requests",
                "formal_writes",
                "database_writes",
                "model_calls",
            )
        } | {
            "subjects": [
                {
                    key: subject[key]
                    for key in (
                        "subject_ref",
                        "subject_name",
                        "mention_count",
                        "merged_window_count",
                        "explicit_attribution_window_count",
                        "ruler_context_window_count",
                        "short_form_only_window_count",
                        "review_tier_counts",
                        "first_review_window_count",
                        "first_review_cluster_count",
                        "second_review_window_count",
                        "retained_not_scheduled_count",
                        "prioritized_window_count",
                        "unprioritized_retained_count",
                    )
                }
                for subject in full_result["subjects"]
            ]
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
