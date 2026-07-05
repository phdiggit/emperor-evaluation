from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Sequence

from scripts.dev.retrieval_v2_contracts import unique_strings
from scripts.dev.retrieval_v2_taskgen_preseed import (
    derived_volume_titles_from_root_hit,
    derived_volume_titles_from_source_hit,
    is_allowed_source_document_title,
    is_probable_source_document_title,
    metadata_from_context,
    normalize_title,
    object_seed_name,
    object_seed_search_names,
    source_hints_for_context,
    source_roots_for_hint,
    text_from,
)
from scripts.dev.source_excerpt_pool_lib.wikisource import search_wikisource


SearchFn = Callable[..., list[dict[str, Any]]]
CANDIDATE_GAP_TYPES_WITH_SOURCE_SIGNAL = {"alias_missing", "source_missing"}
JUDGE_GAP_TYPES_WITH_SOURCE_SIGNAL = {
    "alias_missing",
    "source_missing",
    "predicate_missing",
    "civil_undercoverage",
    "negative_undercoverage",
    "weak_alias_noise",
    "fetch_error",
    "needs_primary_source",
}


def clone_json(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(value), ensure_ascii=False, default=str))


def normalized_name(value: Any) -> str:
    return normalize_title(str(value or ""))


def coverage_gap_object_names(payload: Mapping[str, Any], *, gap_types: set[str]) -> list[str]:
    names: list[str] = []
    for raw_gap in payload.get("coverage_gaps") or []:
        if not isinstance(raw_gap, Mapping):
            continue
        if str(raw_gap.get("gap_type") or "") not in gap_types:
            continue
        name = str(raw_gap.get("object_name") or "").strip()
        if name:
            names.append(name)
    return unique_strings(names)


def candidate_gap_object_names(candidates: Mapping[str, Any]) -> list[str]:
    coverage = candidates.get("coverage") if isinstance(candidates.get("coverage"), Mapping) else {}
    names = [str(raw_name or "").strip() for raw_name in coverage.get("objects_without_slices") or []]
    names.extend(coverage_gap_object_names(candidates, gap_types=CANDIDATE_GAP_TYPES_WITH_SOURCE_SIGNAL))
    return unique_strings([name for name in names if name])


def judge_gap_object_names(judge_result: Mapping[str, Any]) -> list[str]:
    return coverage_gap_object_names(judge_result, gap_types=JUDGE_GAP_TYPES_WITH_SOURCE_SIGNAL)


def source_hints_from_task(task: Mapping[str, Any], *, max_hints: int = 2) -> list[str]:
    hints: list[str] = []
    strategy = task.get("source_strategy") if isinstance(task.get("source_strategy"), Mapping) else {}
    if strategy.get("source_hints"):
        hints.extend(strategy.get("source_hints") or [])
    elif isinstance(task.get("target_payload"), Mapping) and any((task.get("target_payload") or {}).values()):
        hints.extend(source_hints_for_context(task))
    for raw_doc in task.get("source_documents") or task.get("documents") or []:
        if not isinstance(raw_doc, Mapping):
            continue
        title = normalize_title(text_from(raw_doc, "wikisource_title", "title"))
        if "/" not in title:
            continue
        root = title.split("/", 1)[0]
        if root and is_probable_source_document_title(title):
            hints.append(root)
    if not hints:
        hints.extend(source_hints_for_context(task))
    return unique_strings(hints)[: max(1, max_hints)]


def filter_object_seeds(task: Mapping[str, Any], names: Sequence[str], *, max_objects: int) -> list[dict[str, Any]]:
    wanted = {normalized_name(name) for name in names if str(name or "").strip()}
    seeds: list[dict[str, Any]] = []
    found: set[str] = set()
    for raw_seed in task.get("object_seeds") or []:
        if not isinstance(raw_seed, Mapping):
            continue
        seed_names = [object_seed_name(raw_seed), *object_seed_search_names(raw_seed)]
        if any(normalized_name(name) in wanted for name in seed_names):
            seeds.append(dict(raw_seed))
            found.update(normalized_name(name) for name in seed_names if normalized_name(name) in wanted)
        if len(seeds) >= max(0, max_objects):
            break
    for name in names:
        normalized = normalized_name(name)
        if normalized and normalized in wanted and normalized not in found and len(seeds) < max(0, max_objects):
            seeds.append({"name": str(name).strip()})
    return seeds


def merge_source_documents(
    task: Mapping[str, Any],
    *,
    documents: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    docs_by_title: dict[str, dict[str, Any]] = {}
    for raw_doc in task.get("source_documents") or task.get("documents") or []:
        if not isinstance(raw_doc, Mapping):
            continue
        title = normalize_title(text_from(raw_doc, "wikisource_title", "title"))
        if title:
            docs_by_title.setdefault(title, dict(raw_doc))
    before_count = len(docs_by_title)
    for raw_doc in documents:
        title = normalize_title(text_from(raw_doc, "wikisource_title", "title"))
        if title:
            docs_by_title.setdefault(title, dict(raw_doc))
    return list(docs_by_title.values()), len(docs_by_title) - before_count


def refine_task_sources_for_candidate_gaps(
    task: Mapping[str, Any],
    candidates: Mapping[str, Any],
    *,
    object_names: Sequence[str] = (),
    stage: str = "candidate",
    max_objects: int = 8,
    pages_per_object: int = 2,
    timeout: int = 8,
    source_hint_limit: int = 2,
    search_fn: SearchFn | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    search = search_fn or search_wikisource
    result = clone_json(task)
    stage_key = "judge" if stage == "judge" else "candidate"
    payload_gap_names = judge_gap_object_names(candidates) if stage_key == "judge" else candidate_gap_object_names(candidates)
    gap_names = unique_strings(
        [*payload_gap_names, *[str(name or "").strip() for name in object_names]]
    )
    seeds = filter_object_seeds(result, gap_names, max_objects=max_objects)
    source_hints = source_hints_from_task(result, max_hints=source_hint_limit)
    target_code = text_from(result, "target_code") or "target"
    hits: list[dict[str, Any]] = []
    new_documents: list[dict[str, Any]] = []
    for seed in seeds:
        object_name = object_seed_name(seed)
        for search_name in object_seed_search_names(seed):
            for source_hint in source_hints:
                query = f"{search_name} {source_hint}".strip()
                allowed_roots = source_roots_for_hint(source_hint, emp_metadata=metadata_from_context(result))
                try:
                    pages = search(query, limit=pages_per_object, timeout=timeout)
                except Exception as exc:
                    hits.append({"object_name": object_name, "query": query, "error": repr(exc)})
                    continue
                for page in pages:
                    title = normalize_title(str(page.get("title") or ""))
                    snippet = page.get("snippet") or ""
                    hits.append(
                        {
                            "object_name": object_name,
                            "query": query,
                            "title": title,
                            "url": page.get("url") or "",
                            "snippet": snippet,
                        }
                    )
                    source_titles = [title] if title and is_allowed_source_document_title(title, allowed_roots) else []
                    if not source_titles:
                        source_titles = derived_volume_titles_from_source_hit(
                            title=title,
                            snippet=snippet,
                            allowed_roots=allowed_roots,
                            search_names=[search_name, object_name],
                        )
                        if source_titles:
                            hits[-1]["derived_source_titles"] = source_titles
                    if not source_titles:
                        source_titles = derived_volume_titles_from_root_hit(
                            title=title,
                            snippet=snippet,
                            allowed_roots=allowed_roots,
                            search_names=[search_name, object_name],
                        )
                        if source_titles:
                            hits[-1]["derived_source_titles"] = source_titles
                    if not source_titles:
                        hits[-1]["rejected_reason"] = "source_root_mismatch"
                        hits[-1]["allowed_source_roots"] = allowed_roots
                        continue
                    for source_title in source_titles:
                        doc = {
                            "document_code": f"DOC-GAP-{target_code}-{len(new_documents) + 1:02d}",
                            "title": source_title,
                            "wikisource_title": source_title,
                            "url": page.get("url") or "" if source_title == title else "",
                            "source_kind": "wikisource_page",
                            "why_selected": f"{stage_key} gap source presearch for {object_name}",
                            "search_snippet": snippet,
                        }
                        if source_title == title and isinstance(page.get("text"), str) and str(page.get("text")).strip():
                            doc["text"] = str(page["text"])
                        new_documents.append(doc)

    merged_docs, added_count = merge_source_documents(result, documents=new_documents)
    result["source_documents"] = merged_docs
    search_plan = dict(result.get("search_plan") or {})
    plan_key = f"{stage_key}_gap_source_presearch"
    search_plan[plan_key] = {
        "generated_by": "scripts/dev/retrieval_v2_candidate_source_refiner.py",
        "stage": stage_key,
        "gap_object_names": gap_names,
        "searched_object_names": [object_seed_name(seed) for seed in seeds],
        "source_hints": source_hints,
        "max_objects": max_objects,
        "pages_per_object": pages_per_object,
        "hits": hits,
    }
    result["search_plan"] = search_plan
    notes = list(result.get("generation_notes") or [])
    notes.append(f"script {stage_key} gap source presearch expanded source_documents for gap objects")
    result["generation_notes"] = unique_strings(notes)
    clean_audit = dict(result.get("clean_audit") or {})
    clean_audit[plan_key] = True
    clean_audit[f"{plan_key}_hit_count"] = len([hit for hit in hits if not hit.get("error")])
    result["clean_audit"] = clean_audit
    stats = {
        "stage": stage_key,
        "gap_object_names": gap_names,
        "searched_object_names": [object_seed_name(seed) for seed in seeds],
        "source_hints": source_hints,
        "hit_count": len([hit for hit in hits if not hit.get("error")]),
        "error_count": len([hit for hit in hits if hit.get("error")]),
        "added_source_document_count": added_count,
        "source_document_count": len(merged_docs),
    }
    return result, stats
