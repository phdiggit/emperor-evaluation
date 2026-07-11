from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping, Sequence

from scripts.dev.retrieval_v2_contracts import (
    alias_script_variants,
    source_root_aliases_for_hint,
    source_hints_from_source_targets,
    source_hints_for_metadata,
    unique_strings,
)
from scripts.dev.source_excerpt_pool_lib.wikisource import search_wikisource


SearchFn = Callable[..., list[dict[str, str]]]

AMBIGUOUS_PRESEARCH_TITLE_ANCHORS = {
    "承天太后",
    "齐天后",
    "齊天后",
}


RULE_QUERY_TERMS = {
    "appointment_delegation": ["任", "命", "授", "拜", "委", "信", "將軍", "總督", "經略", "留守"],
    "i5b_item_wide": ["任", "薦", "舉", "結黨", "納賄", "授", "拜", "將軍", "赦", "誅"],
    "team_building": ["任", "相", "將", "大臣", "用"],
    "talent_discovery": ["薦", "舉", "用", "拔"],
}
BLOCKED_DOCUMENT_TITLE_FRAGMENTS = (
    "四部叢刊本",
    "四部丛刊本",
    "演義",
    "演义",
    "志傳",
    "志传",
    "全覽",
    "全览",
    "附錄",
    "附録",
    "附录",
    "提要",
    "跋",
    "進元史表",
    "进元史表",
    "進續資治通鑑長編表",
)
BLOCKED_ROOT_TITLE_FRAGMENTS = (
    "四庫全書本",
    "四库全书本",
    *BLOCKED_DOCUMENT_TITLE_FRAGMENTS,
)
CHINESE_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def text_from(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", "", value)


def chinese_volume_number(value: str) -> int | None:
    text = normalize_title(value)
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "百" in text:
        left, _, right = text.partition("百")
        prefix = CHINESE_DIGITS.get(left, 1 if not left else -1)
        suffix = chinese_volume_number(right) or 0
        return prefix * 100 + suffix if prefix >= 0 else None
    if "十" in text:
        left, _, right = text.partition("十")
        prefix = CHINESE_DIGITS.get(left, 1 if not left else -1)
        suffix = CHINESE_DIGITS.get(right, 0 if not right else -1)
        return prefix * 10 + suffix if prefix >= 0 and suffix >= 0 else None
    if len(text) == 1:
        return CHINESE_DIGITS.get(text)
    return None


def is_probable_source_document_title(title: str) -> bool:
    normalized = normalize_title(title)
    return "/" in normalized and not any(fragment in normalized for fragment in BLOCKED_DOCUMENT_TITLE_FRAGMENTS)


def source_root_from_title(title: str) -> str:
    root = normalize_title(title).split("/", 1)[0]
    return re.sub(r"[（(].*?[）)]", "", root)


def canonical_volume_title(source_root: str, volume_number: int) -> str:
    root = normalize_title(source_root)
    if root in {"史記", "資治通鑑"}:
        return f"{root}/卷{volume_number:03d}"
    return f"{root}/卷{volume_number}"


def source_roots_for_hint(source_hint: str, *, emp_metadata: Mapping[str, Any] | None = None) -> list[str]:
    canonical = source_hints_from_source_targets([source_hint])
    hint = normalize_title(canonical[0] if canonical else source_hint)
    return source_root_aliases_for_hint(hint, dict(emp_metadata or {})) if hint else []


def source_root_allowed(title: str, allowed_roots: Sequence[str]) -> bool:
    root = source_root_from_title(title)
    normalized_title = normalize_title(title)
    normalized_roots = {normalize_title(value) for value in allowed_roots if value}
    return bool(
        root
        and (
            root in normalized_roots
            or any(normalized_title == allowed or normalized_title.startswith(f"{allowed}/") for allowed in normalized_roots)
        )
    )


def source_hints_in_query(query: str, source_hints: Sequence[str]) -> list[str]:
    normalized_query = normalize_title(query)
    matches = [
        hint
        for hint in source_hints
        if normalize_title(hint) and normalize_title(hint) in normalized_query
    ]
    selected: list[str] = []
    selected_normalized: list[str] = []
    for hint in sorted(matches, key=lambda value: len(normalize_title(value)), reverse=True):
        normalized_hint = normalize_title(hint)
        if any(normalized_hint in existing for existing in selected_normalized):
            continue
        selected.append(hint)
        selected_normalized.append(normalized_hint)
    return selected


def allowed_source_roots_for_query(
    query: str,
    context: Mapping[str, Any],
    *,
    emp_metadata: Mapping[str, Any] | None = None,
) -> list[str]:
    period_hints = source_hints_for_context(context, emp_metadata=emp_metadata)
    query_hints = source_hints_in_query(query, period_hints)
    hints = query_hints or period_hints
    metadata = metadata_from_context(context, emp_metadata)
    return unique_strings(root for hint in hints for root in source_roots_for_hint(hint, emp_metadata=metadata))


def is_allowed_source_document_title(title: str, allowed_roots: Sequence[str]) -> bool:
    return is_probable_source_document_title(title) and source_root_allowed(title, allowed_roots)


def is_allowed_source_root_title(title: str, allowed_roots: Sequence[str]) -> bool:
    normalized = normalize_title(title)
    return (
        bool(normalized)
        and "/" not in normalized
        and not any(fragment in normalized for fragment in BLOCKED_ROOT_TITLE_FRAGMENTS)
        and source_root_allowed(normalized, allowed_roots)
    )


def derived_volume_titles_from_root_hit(
    *,
    title: str,
    snippet: str,
    allowed_roots: Sequence[str],
    search_names: Sequence[str],
) -> list[str]:
    if not is_allowed_source_root_title(title, allowed_roots):
        return []
    compact_snippet = normalize_title(snippet)
    return derived_volume_titles_from_snippet(
        source_root=source_root_from_title(title),
        snippet=compact_snippet,
        search_names=search_names,
    )


def source_root_for_snippet_derivation(title: str, allowed_roots: Sequence[str]) -> str:
    normalized_title = normalize_title(title)
    title_root = source_root_from_title(title)
    allowed = [normalize_title(value) for value in allowed_roots if normalize_title(value)]
    if title_root in allowed:
        return title_root
    for root in sorted(allowed, key=len, reverse=True):
        if normalized_title == root or normalized_title.startswith(f"{root}/") or title_root.startswith(root):
            return root
    return ""


def derived_volume_titles_from_source_hit(
    *,
    title: str,
    snippet: str,
    allowed_roots: Sequence[str],
    search_names: Sequence[str],
) -> list[str]:
    if any(fragment in normalize_title(title) for fragment in BLOCKED_DOCUMENT_TITLE_FRAGMENTS):
        return []
    source_root = source_root_for_snippet_derivation(title, allowed_roots)
    if not source_root:
        return []
    return derived_volume_titles_from_snippet(
        source_root=source_root,
        snippet=snippet,
        search_names=search_names,
    )


def derived_volume_titles_from_snippet(
    *,
    source_root: str,
    snippet: str,
    search_names: Sequence[str],
) -> list[str]:
    compact_snippet = normalize_title(snippet)
    if not compact_snippet:
        return []
    positions: list[int] = []
    for name in search_names:
        for variant in alias_script_variants(name):
            needle = normalize_title(variant)
            if not needle:
                continue
            position = compact_snippet.find(needle)
            if position >= 0:
                positions.append(position)
    if not positions:
        return []
    position = min(positions)
    volume_matches = list(re.finditer(r"卷([零〇一二两兩三四五六七八九十百\d]{1,6})", compact_snippet[: position + 1]))
    if not volume_matches:
        return []
    volume_number = chinese_volume_number(volume_matches[-1].group(1))
    if not volume_number:
        return []
    return [canonical_volume_title(source_root, volume_number)]


def object_seed_name(seed: Mapping[str, Any]) -> str:
    return text_from(seed, "name", "object_name", "primary_name")


def object_seed_search_names(seed: Mapping[str, Any]) -> list[str]:
    names = [object_seed_name(seed)]
    for raw_alias in seed.get("aliases") or []:
        if not isinstance(raw_alias, Mapping):
            continue
        strength = text_from(raw_alias, "strength")
        alias = text_from(raw_alias, "alias", "text", "name")
        if strength in {"", "strong"}:
            names.append(alias)
    expanded = [variant for name in names for variant in alias_script_variants(name)]
    return unique_strings([*names, *expanded])[:4]


def object_source_query(object_name: str, context: Mapping[str, Any], emp_metadata: Mapping[str, Any] | None = None) -> str:
    source = source_hints_for_context(context, emp_metadata=emp_metadata, max_hints=1)[0]
    return f"{object_name} {source}"


def metadata_from_context(context: Mapping[str, Any], emp_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = context.get("target_payload")
    if isinstance(payload, Mapping):
        result = dict(payload)
    else:
        result = {}
    result.update(emp_metadata or {})
    return result


def source_hints_for_context(
    context: Mapping[str, Any],
    *,
    emp_metadata: Mapping[str, Any] | None = None,
    max_hints: int | None = None,
) -> list[str]:
    return source_hints_for_metadata(metadata_from_context(context, emp_metadata), max_hints=max_hints)


def title_is_ambiguous_presearch_anchor(title: str) -> bool:
    return title in AMBIGUOUS_PRESEARCH_TITLE_ANCHORS


def presearch_anchor_terms(name: str, title: str) -> list[str]:
    if title and name and title_is_ambiguous_presearch_anchor(title):
        return unique_strings([name, f"{name} {title}"])
    return unique_strings([title, name])


def preseed_target_title_aliases(name: str, title: str) -> list[str]:
    if title and title_is_ambiguous_presearch_anchor(title):
        return []
    return [title] if title else []


def direct_source_titles_from_source_targets(
    source_targets: Any,
    context: Mapping[str, Any],
    *,
    emp_metadata: Mapping[str, Any] | None = None,
) -> list[str]:
    if isinstance(source_targets, str):
        values = [source_targets]
    elif isinstance(source_targets, list):
        values = [str(value or "") for value in source_targets]
    else:
        values = []
    allowed_roots = unique_strings(
        root
        for hint in source_hints_for_context(context, emp_metadata=emp_metadata)
        for root in source_roots_for_hint(hint, emp_metadata=metadata_from_context(context, emp_metadata))
    )
    titles: list[str] = []
    for value in values:
        normalized = normalize_title(value)
        for match in re.finditer(r"([^\s，,；;]+?/卷[0-9零〇一二两兩三四五六七八九十百]+)", normalized):
            title = match.group(1)
            if is_probable_source_document_title(title) and source_root_allowed(title, allowed_roots):
                titles.append(title)
    return unique_strings(titles)


def object_source_queries(
    object_name: str,
    context: Mapping[str, Any],
    emp_metadata: Mapping[str, Any] | None = None,
    *,
    source_hint_limit: int = 2,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_hint in source_hints_for_context(context, emp_metadata=emp_metadata, max_hints=source_hint_limit):
        rows.append({"source_hint": source_hint, "query": f"{object_name} {source_hint}".strip()})
    return rows


def build_presearch_queries(
    context: Mapping[str, Any],
    *,
    emp_metadata: Mapping[str, Any] | None = None,
    max_queries: int = 4,
) -> list[str]:
    meta = metadata_from_context(context, emp_metadata)
    name = text_from(context, "emperor_name")
    title = text_from(meta, "title", "temple_name", "posthumous_name")
    anchors = presearch_anchor_terms(name, title)
    source_hints = source_hints_for_context(context, emp_metadata=emp_metadata)
    queries: list[str] = []
    for anchor in anchors:
        for source in source_hints:
            queries.append(f"{anchor} {source}")
    rule_code = text_from(context, "rule_code")
    rule_terms = " ".join(RULE_QUERY_TERMS.get(rule_code, RULE_QUERY_TERMS["appointment_delegation"])[:4])
    for anchor in anchors:
        if rule_terms:
            queries.append(f"{anchor} {rule_terms}")
    return unique_strings(queries)[: max(1, max_queries)]


def build_taskgen_preseed(
    context: Mapping[str, Any],
    *,
    emp_metadata: Mapping[str, Any] | None = None,
    max_queries: int = 4,
    pages_per_query: int = 3,
    timeout: int = 8,
    search_fn: SearchFn = search_wikisource,
) -> dict[str, Any]:
    queries = build_presearch_queries(context, emp_metadata=emp_metadata, max_queries=max_queries)
    hits: list[dict[str, Any]] = []
    documents_by_title: dict[str, dict[str, Any]] = {}
    root_documents_by_title: dict[str, dict[str, Any]] = {}
    target_code = text_from(context, "target_code") or "target"
    name = text_from(context, "emperor_name")
    meta = metadata_from_context(context, emp_metadata)
    title_alias = text_from(meta, "title", "temple_name", "posthumous_name")
    title_aliases = preseed_target_title_aliases(name, title_alias)
    search_names = unique_strings([name, title_alias])
    direct_titles = direct_source_titles_from_source_targets(meta.get("source_targets"), context, emp_metadata=emp_metadata)
    for direct_title in direct_titles:
        documents_by_title.setdefault(
            direct_title,
            {
                "document_code": f"DOC-META-{target_code}-{len(documents_by_title) + 1:02d}",
                "title": direct_title,
                "wikisource_title": direct_title,
                "url": "",
                "source_kind": "wikisource_page",
                "why_selected": "metadata direct source target",
            },
        )
    for query in queries:
        allowed_roots = allowed_source_roots_for_query(query, context, emp_metadata=emp_metadata)
        try:
            pages = search_fn(query, limit=pages_per_query, timeout=timeout)
        except Exception as exc:
            hits.append({"query": query, "error": repr(exc)})
            continue
        for page in pages:
            title = normalize_title(str(page.get("title") or ""))
            if not title:
                continue
            hit = {
                "query": query,
                "title": title,
                "url": page.get("url") or "",
                "snippet": page.get("snippet") or "",
            }
            hits.append(hit)
            if is_allowed_source_document_title(title, allowed_roots):
                documents_by_title.setdefault(
                    title,
                    {
                        "document_code": f"DOC-PRE-{target_code}-{len(documents_by_title) + 1:02d}",
                        "title": title,
                        "wikisource_title": title,
                        "url": page.get("url") or "",
                        "source_kind": "wikisource_page",
                        "why_selected": f"script presearch hit for {query}",
                        "search_snippet": page.get("snippet") or "",
                    },
                )
                continue
            if is_allowed_source_root_title(title, allowed_roots):
                hit["root_fallback_candidate"] = True
                root_documents_by_title.setdefault(
                    title,
                    {
                        "document_code": f"DOC-PRE-{target_code}-ROOT-{len(root_documents_by_title) + 1:02d}",
                        "title": title,
                        "wikisource_title": title,
                        "url": page.get("url") or "",
                        "source_kind": "wikisource_root_page",
                        "why_selected": f"script presearch root fallback for {query}",
                        "search_snippet": page.get("snippet") or "",
                    },
                )
                continue
            derived_titles = derived_volume_titles_from_source_hit(
                title=title,
                snippet=page.get("snippet") or "",
                allowed_roots=allowed_roots,
                search_names=search_names,
            )
            if derived_titles:
                hit["derived_source_titles"] = derived_titles
                for derived_title in derived_titles:
                    documents_by_title.setdefault(
                        derived_title,
                        {
                            "document_code": f"DOC-PRE-{target_code}-{len(documents_by_title) + 1:02d}",
                            "title": derived_title,
                            "wikisource_title": derived_title,
                            "url": "",
                            "source_kind": "wikisource_page",
                            "why_selected": f"script presearch snippet-derived canonical page for {query}",
                            "search_snippet": page.get("snippet") or "",
                        },
                    )
                continue
            if not is_allowed_source_document_title(title, allowed_roots):
                hit["rejected_reason"] = "source_root_mismatch"
                hit["allowed_source_roots"] = allowed_roots
                continue
    if not documents_by_title:
        documents_by_title.update(root_documents_by_title)
    return {
        "target_profile": {
            "aliases": title_aliases,
            "must_check_titles": title_aliases,
        },
        "source_documents": list(documents_by_title.values()),
        "search_plan": {
            "generated_by": "scripts/dev/retrieval_v2_taskgen_preseed.py",
            "needs_cli_discovery": True,
            "discovery_scope": "object_seeds_from_presearch_and_gap_source_documents",
            "presearch_queries": queries,
            "presearch_hits": hits,
            "direct_source_target_count": len(direct_titles),
            "codex_search_recommended": False,
        },
        "generation_notes": [
            "script presearch supplied candidate Wikisource pages; taskgen should prefer these hits and only add source_documents for clear gaps"
        ],
        "clean_audit": {
            "taskgen_presearch": True,
            "presearch_hit_count": len([hit for hit in hits if not hit.get("error")]),
            "presearch_old_object_pool_read": False,
            "presearch_old_source_pack_read": False,
        },
    }


def expand_task_sources_for_objects(
    task: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    emp_metadata: Mapping[str, Any] | None = None,
    max_objects: int = 12,
    pages_per_object: int = 1,
    timeout: int = 8,
    source_hint_limit: int = 2,
    search_fn: SearchFn = search_wikisource,
) -> dict[str, Any]:
    result = json.loads(json.dumps(dict(task), ensure_ascii=False, default=str))
    existing_docs = list(result.get("source_documents") or result.get("documents") or [])
    docs_by_title: dict[str, dict[str, Any]] = {}
    for doc in existing_docs:
        if not isinstance(doc, Mapping):
            continue
        title = normalize_title(text_from(doc, "wikisource_title", "title"))
        if title:
            docs_by_title.setdefault(title, dict(doc))

    hits: list[dict[str, Any]] = []
    target_code = text_from(context, "target_code") or text_from(result, "target_code") or "target"
    object_seeds = [seed for seed in (result.get("object_seeds") or []) if isinstance(seed, Mapping)][: max(0, max_objects)]
    for seed in object_seeds:
        object_name = object_seed_name(seed)
        for search_name in object_seed_search_names(seed):
            for query_row in object_source_queries(
                search_name,
                context,
                emp_metadata=emp_metadata,
                source_hint_limit=source_hint_limit,
            ):
                query = query_row["query"]
                source_hint = query_row["source_hint"]
                allowed_roots = allowed_source_roots_for_query(query, context, emp_metadata=emp_metadata)
                try:
                    pages = search_fn(query, limit=pages_per_object, timeout=timeout)
                except Exception as exc:
                    hits.append({"object_name": object_name, "source_hint": source_hint, "query": query, "error": repr(exc)})
                    continue
                for page in pages:
                    title = normalize_title(str(page.get("title") or ""))
                    snippet = page.get("snippet") or ""
                    hit = {
                        "object_name": object_name,
                        "source_hint": source_hint,
                        "query": query,
                        "title": title,
                        "url": page.get("url") or "",
                        "snippet": snippet,
                    }
                    hits.append(hit)
                    if title and is_allowed_source_document_title(title, allowed_roots):
                        docs_by_title.setdefault(
                            title,
                            {
                                "document_code": f"DOC-OBJ-{target_code}-{len(docs_by_title) + 1:02d}",
                                "title": title,
                                "wikisource_title": title,
                                "url": page.get("url") or "",
                                "source_kind": "wikisource_page",
                                "why_selected": f"object source presearch for {object_name}",
                                "search_snippet": snippet,
                            },
                        )
                        continue
                    derived_titles = derived_volume_titles_from_root_hit(
                        title=title,
                        snippet=snippet,
                        allowed_roots=allowed_roots,
                        search_names=[search_name, object_name],
                    )
                    if derived_titles:
                        hit["derived_source_titles"] = derived_titles
                        for derived_title in derived_titles:
                            docs_by_title.setdefault(
                                derived_title,
                                {
                                    "document_code": f"DOC-OBJ-{target_code}-{len(docs_by_title) + 1:02d}",
                                    "title": derived_title,
                                    "wikisource_title": derived_title,
                                    "url": "",
                                    "source_kind": "wikisource_page",
                                    "why_selected": f"object source presearch root-derived for {object_name}",
                                    "search_snippet": snippet,
                                },
                            )
                        continue
                    if not title or not is_allowed_source_document_title(title, allowed_roots):
                        hit["rejected_reason"] = "source_root_mismatch"
                        hit["allowed_source_roots"] = allowed_roots
                        continue

    result["source_documents"] = list(docs_by_title.values())
    search_plan = dict(result.get("search_plan") or {})
    search_plan["object_source_presearch"] = {
        "generated_by": "scripts/dev/retrieval_v2_taskgen_preseed.py",
        "max_objects": max_objects,
        "pages_per_object": pages_per_object,
        "source_hint_limit": source_hint_limit,
        "hits": hits,
    }
    result["search_plan"] = search_plan
    notes = list(result.get("generation_notes") or [])
    notes.append("script object source presearch expanded source_documents from discovered object seeds")
    result["generation_notes"] = unique_strings(notes)
    clean_audit = dict(result.get("clean_audit") or {})
    clean_audit["object_source_presearch"] = True
    clean_audit["object_source_presearch_hit_count"] = len([hit for hit in hits if not hit.get("error")])
    result["clean_audit"] = clean_audit
    return result
