from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_person_name(row: Mapping[str, Any]) -> str:
    return text_from(row, "person_name", "object_name", "name")


def text_from(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def compact(value: Any, *, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    return text[: limit - 1] + "…" if len(text) > limit else text


def document_issue_tags(doc: Mapping[str, Any]) -> list[str]:
    tags: list[str] = []
    hint = doc.get("source_document_hint") if isinstance(doc.get("source_document_hint"), Mapping) else {}
    locator = text_from(hint, "locator")
    title = text_from(doc, "wikisource_title", "source_title", "title")
    if hint:
        tags.append("hint_document")
    elif "search" in text_from(doc, "why_selected"):
        tags.append("search_document")
    if int(doc.get("text_chars") or 0) <= 0:
        tags.append("empty_text")
    elif int(doc.get("mention_slice_count") or 0) <= 0:
        tags.append("nonempty_no_alias_hit")
    if "四庫全書本" in locator and "四庫全書本" not in title:
        tags.append("fourku_locator_collapsed")
    for subpath in ("/魏志/", "/蜀志/", "/吳志/", "/吴志/"):
        if subpath in locator and subpath not in title:
            tags.append("subpath_locator_collapsed")
    if locator and "/" not in locator and int(doc.get("text_chars") or 0) > 0 and int(doc.get("mention_slice_count") or 0) <= 0:
        tags.append("narrative_locator_no_alias_hit")
    return sorted(set(tags))


def person_classification(coverage: Mapping[str, Any], docs: Sequence[Mapping[str, Any]]) -> str:
    risk = text_from(coverage, "claim_closure_risk")
    all_tags = {tag for doc in docs for tag in document_issue_tags(doc)}
    if "fourku_locator_collapsed" in all_tags or "subpath_locator_collapsed" in all_tags:
        return "title_route_collapse"
    if risk == "mentions_without_biography_source":
        return "mention_without_biography_shape"
    if "empty_text" in all_tags:
        return "empty_text_candidate"
    if "nonempty_no_alias_hit" in all_tags:
        return "nonempty_no_alias_hit"
    return risk or "unknown"


def build_review_audit(cache_root: Path, *, max_docs_per_person: int = 6) -> dict[str, Any]:
    coverage_rows = read_jsonl(cache_root / "person_coverage.jsonl")
    source_documents = read_jsonl(cache_root / "source_documents.jsonl")
    mention_slices = read_jsonl(cache_root / "mention_slices.jsonl")
    docs_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    slices_by_person: Counter[str] = Counter()
    for doc in source_documents:
        docs_by_person[text_from(doc, "person_name")].append(doc)
    for row in mention_slices:
        slices_by_person[text_from(row, "person_name")] += 1

    review_rows: list[dict[str, Any]] = []
    classification_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    issue_tag_counts: Counter[str] = Counter()
    for coverage in coverage_rows:
        if not coverage.get("needs_agent_review"):
            continue
        person_name = text_from(coverage, "person_name")
        docs = docs_by_person.get(person_name, [])
        doc_summaries = []
        person_tags: set[str] = set()
        for doc in docs[:max_docs_per_person]:
            tags = document_issue_tags(doc)
            person_tags.update(tags)
            hint = doc.get("source_document_hint") if isinstance(doc.get("source_document_hint"), Mapping) else {}
            doc_summaries.append(
                {
                    "title": text_from(doc, "wikisource_title", "source_title", "title"),
                    "source_shape": text_from(doc, "source_shape"),
                    "text_chars": int(doc.get("text_chars") or 0),
                    "mention_slice_count": int(doc.get("mention_slice_count") or 0),
                    "why_selected": compact(doc.get("why_selected")),
                    "hint_locator": compact(text_from(hint, "locator")),
                    "hint_title": compact(text_from(hint, "title")),
                    "tags": tags,
                }
            )
        classification = person_classification(coverage, docs)
        classification_counts[classification] += 1
        risk_counts[text_from(coverage, "claim_closure_risk")] += 1
        for tag in person_tags:
            issue_tag_counts[tag] += 1
        review_rows.append(
            {
                "person_name": person_name,
                "person_cache_code": text_from(coverage, "person_cache_code"),
                "claim_closure_risk": text_from(coverage, "claim_closure_risk"),
                "agent_review_reason": text_from(coverage, "agent_review_reason"),
                "classification": classification,
                "issue_tags": sorted(person_tags),
                "source_shapes": coverage.get("source_shapes") or [],
                "source_document_count": int(coverage.get("source_document_count") or 0),
                "mention_slice_count": int(coverage.get("mention_slice_count") or slices_by_person.get(person_name, 0)),
                "documents": doc_summaries,
            }
        )

    return {
        "generated_by": "scripts/dev/retrieval_v3_object_source_cache_audit.py",
        "cache_root": str(cache_root),
        "totals": {
            "coverage_rows": len(coverage_rows),
            "source_documents": len(source_documents),
            "mention_slices": len(mention_slices),
            "review_rows": len(review_rows),
        },
        "risk_counts": dict(sorted(risk_counts.items())),
        "classification_counts": dict(sorted(classification_counts.items())),
        "issue_tag_counts": dict(sorted(issue_tag_counts.items())),
        "review_rows": review_rows,
    }


def render_review_audit_markdown(audit: Mapping[str, Any]) -> str:
    totals = audit.get("totals") if isinstance(audit.get("totals"), Mapping) else {}
    lines = [
        "# retrieval_v3 object source cache review audit",
        "",
        f"- cache_root: `{audit.get('cache_root', '')}`",
        f"- coverage_rows: `{totals.get('coverage_rows', 0)}`",
        f"- source_documents: `{totals.get('source_documents', 0)}`",
        f"- mention_slices: `{totals.get('mention_slices', 0)}`",
        f"- review_rows: `{totals.get('review_rows', 0)}`",
        "",
        "## Classifications",
        "",
    ]
    for key, count in (audit.get("classification_counts") or {}).items():
        lines.append(f"- {key}: `{count}`")
    lines.extend(["", "## Issue Tags", ""])
    for key, count in (audit.get("issue_tag_counts") or {}).items():
        lines.append(f"- {key}: `{count}`")
    lines.extend(["", "## Review Rows", "", "| person | risk | class | tags | first documents |", "| --- | --- | --- | --- | --- |"])
    for row in audit.get("review_rows") or []:
        docs = row.get("documents") or []
        first_docs = "<br>".join(
            f"{doc.get('title')} [{doc.get('source_shape')}, chars={doc.get('text_chars')}, slices={doc.get('mention_slice_count')}]"
            for doc in docs[:3]
        )
        tags = ", ".join(row.get("issue_tags") or [])
        lines.append(
            f"| {row.get('person_name')} | {row.get('claim_closure_risk')} | {row.get('classification')} | {tags} | {first_docs} |"
        )
    return "\n".join(lines) + "\n"


def merged_rows_by_rescue_persons(base_rows: Sequence[Mapping[str, Any]], rescue_rows: Sequence[Mapping[str, Any]], rescue_persons: set[str]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in base_rows if row_person_name(row) not in rescue_persons]
    rows.extend(dict(row) for row in rescue_rows)
    return rows


def render_rescue_merge_report(summary: Mapping[str, Any]) -> str:
    totals = summary.get("totals") if isinstance(summary.get("totals"), Mapping) else {}
    return "\n".join(
        [
            "# retrieval_v3 object source cache rescue merge",
            "",
            f"- base_cache_root: `{summary.get('base_cache_root', '')}`",
            f"- rescue_cache_root: `{summary.get('rescue_cache_root', '')}`",
            f"- output_root: `{summary.get('output_root', '')}`",
            f"- rescue_persons: `{totals.get('rescue_persons', 0)}`",
            f"- persons: `{totals.get('persons', 0)}`",
            f"- source_documents: `{totals.get('source_documents', 0)}`",
            f"- mention_slices: `{totals.get('mention_slices', 0)}`",
            f"- agent_review_queue: `{totals.get('agent_review_queue', 0)}`",
            f"- fetch_errors: `{totals.get('fetch_errors', 0)}`",
            f"- search_hits: `{totals.get('search_hits', 0)}`",
            f"- base_review_rows: `{totals.get('base_review_rows', 0)}`",
            f"- rescue_review_rows: `{totals.get('rescue_review_rows', 0)}`",
            f"- merged_review_rows: `{totals.get('merged_review_rows', 0)}`",
            "",
        ]
    )


def merge_rescue_cache(base_cache_root: Path, rescue_cache_root: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rescue_coverage = read_jsonl(rescue_cache_root / "person_coverage.jsonl")
    rescue_persons = {row_person_name(row) for row in rescue_coverage if row_person_name(row)}
    file_names = [
        "person_coverage.jsonl",
        "source_documents.jsonl",
        "mention_slices.jsonl",
        "agent_review_queue.jsonl",
        "fetch_errors.jsonl",
        "search_hits.jsonl",
    ]
    merged_counts: dict[str, int] = {}
    for file_name in file_names:
        merged = merged_rows_by_rescue_persons(
            read_jsonl(base_cache_root / file_name),
            read_jsonl(rescue_cache_root / file_name),
            rescue_persons,
        )
        write_jsonl(output_root / file_name, merged)
        merged_counts[file_name.removesuffix(".jsonl")] = len(merged)

    base_review_rows = [row for row in read_jsonl(base_cache_root / "person_coverage.jsonl") if row.get("needs_agent_review")]
    rescue_review_rows = [row for row in rescue_coverage if row.get("needs_agent_review")]
    merged_coverage = read_jsonl(output_root / "person_coverage.jsonl")
    merged_review_rows = [row for row in merged_coverage if row.get("needs_agent_review")]
    summary = {
        "generated_by": "scripts/dev/retrieval_v3_object_source_cache_audit.py",
        "mode": "offline_no_agent_rescue_merged",
        "base_cache_root": str(base_cache_root),
        "rescue_cache_root": str(rescue_cache_root),
        "output_root": str(output_root),
        "artifacts": {
            "person_coverage": str(output_root / "person_coverage.jsonl"),
            "source_documents": str(output_root / "source_documents.jsonl"),
            "mention_slices": str(output_root / "mention_slices.jsonl"),
            "agent_review_queue": str(output_root / "agent_review_queue.jsonl"),
            "fetch_errors": str(output_root / "fetch_errors.jsonl"),
            "search_hits": str(output_root / "search_hits.jsonl"),
            "summary_json": str(output_root / "rescue_merge_summary.json"),
            "report": str(output_root / "rescue_merge_report.md"),
        },
        "merged_counts": merged_counts,
        "totals": {
            "rescue_persons": len(rescue_persons),
            "persons": len(merged_coverage),
            "source_documents": merged_counts.get("source_documents", 0),
            "mention_slices": merged_counts.get("mention_slices", 0),
            "agent_review_queue": merged_counts.get("agent_review_queue", 0),
            "fetch_errors": merged_counts.get("fetch_errors", 0),
            "search_hits": merged_counts.get("search_hits", 0),
            "base_review_rows": len(base_review_rows),
            "rescue_review_rows": len(rescue_review_rows),
            "merged_review_rows": len(merged_review_rows),
        },
        "rescue_person_names": sorted(rescue_persons),
    }
    write_json(output_root / "rescue_merge_summary.json", summary)
    (output_root / "rescue_merge_report.md").write_text(render_rescue_merge_report(summary), encoding="utf-8")
    return summary
