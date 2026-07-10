from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import (  # noqa: E402
    RetrievalV2BootstrapError,
)
from scripts.dev.retrieval_v2_contracts import SOURCE_HINT_TEXT_ALIASES, alias_script_variants, unique_strings  # noqa: E402
from scripts.dev.retrieval_v2_object_source_cache_seed import (  # noqa: E402
    ObjectSourceCacheSeedError,
    clean_name,
    dedupe_seeds,
    merge_object_pool_alias_rows,
    normalize_seed,
    normalized_name,
    person_cache_code,
    render_seed_audit_markdown,
    rows_from_db,
    seed_aliases,
    seed_audit_report,
    seed_is_emperor,
    seed_name,
    seed_priority,
    source_role_for_seed,
    source_document_title_candidates,
    seed_source_document_hints,
    seed_source_hints,
    stable_hash,
)
from scripts.dev.retrieval_v2_object_source_cache_audit import build_review_audit, merge_rescue_cache, render_review_audit_markdown  # noqa: E402
from scripts.dev.retrieval_v2_object_source_cache_shards import run_build_shards  # noqa: E402
from scripts.dev.retrieval_v2_runtime_paths import default_source_cache_root, load_runtime_paths  # noqa: E402
from scripts.dev.retrieval_v2_source_candidates import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    RetrievalV2CandidateError,
    cache_paths,
    compact_text,
    context_bounds,
    fetch_document_text,
    pretty_json,
    write_cached_text,
)
from scripts.dev.retrieval_v2_taskgen_preseed import (  # noqa: E402
    derived_volume_titles_from_root_hit,
    derived_volume_titles_from_source_hit,
    derived_volume_titles_from_snippet,
    is_allowed_source_document_title,
    is_allowed_source_root_title,
    normalize_title,
    source_root_from_title,
    source_roots_for_hint,
    text_from,
)
from scripts.dev.source_excerpt_pool_lib.cache import (  # noqa: E402
    FetchContext,
    cache_report,
    load_source_excerpt_cache_config,
    make_cache_backends,
)
from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_USER_AGENT,
)
from scripts.dev.source_excerpt_pool_lib.wikisource import fetch_wikisource_plain_text  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.wikisource import search_wikisource  # noqa: E402


SearchFn = Callable[..., list[dict[str, Any]]]
DEFAULT_OUTPUT_ROOT = ROOT / "tmp" / "retrieval_v2_object_source_cache"
SCHEMA_VERSION = 1
OBJECT_BIOGRAPHY_QUERY_SUFFIXES = ("列传", "列傳", "本传", "本傳", "功臣", "奸臣")
SECTION_HEADING_RE = re.compile(r"([A-Za-z0-9_\-\u3400-\u9fff·]+)\s*\[\s*编辑\s*\]")
CHAR_LOCATOR_RE = re.compile(r"chars:(\d+)-(\d+)")
SOURCE_TARGET_REF_SPLIT_RE = re.compile(r"[\s，,。；;：:、/／()（）\[\]【】《》<>〈〉]+")
SUMMARY_LEAD_ALLOWED_SINGLE_CHAR_TERMS = {"诛", "誅"}
SUMMARY_LEAD_LOW_PRIORITY_TERMS = {"诛", "誅", "连坐", "連坐", "大逆", "不轨", "不軌"}
SUMMARY_LEAD_HIGH_PRIORITY_TERMS = {
    "赐死",
    "賜死",
    "被杀",
    "被殺",
    "诛杀",
    "誅殺",
    "自尽",
    "自盡",
    "自刎",
    "赐自尽",
    "賜自盡",
    "处死",
    "處死",
    "坐死",
    "党死",
    "黨死",
    "伏诛",
    "伏誅",
    "诛死",
    "誅死",
    "三族",
    "九族",
    "族诛",
    "族誅",
    "灭族",
    "滅族",
    "妻女弟侄",
    "七十余人",
    "谋反",
    "謀反",
    "谋叛",
    "謀叛",
    "反状",
    "反狀",
    "坐党",
    "坐黨",
    "籍其家",
    "籍没",
    "籍沒",
    "流放",
    "流徙",
}
SUMMARY_LEAD_TERM_EXPANSIONS = {
    "赐死": ("自尽", "自盡", "赐自尽", "賜自盡", "坐死", "党死", "黨死", "伏诛", "伏誅"),
    "被杀": ("被殺", "诛", "誅", "诛死", "誅死", "坐死", "党死", "黨死", "籍其家", "籍没", "籍沒"),
    "被殺": ("被杀", "诛", "誅", "诛死", "誅死", "坐死", "党死", "黨死", "籍其家", "籍没", "籍沒"),
    "诛杀": ("誅殺", "诛", "誅", "诛死", "誅死", "坐死", "党死", "黨死", "籍其家", "籍没", "籍沒"),
    "誅殺": ("诛杀", "诛", "誅", "诛死", "誅死", "坐死", "党死", "黨死", "籍其家", "籍没", "籍沒"),
    "处死": ("處死", "坐死", "党死", "黨死", "伏诛", "伏誅", "诛死", "誅死"),
    "處死": ("处死", "坐死", "党死", "黨死", "伏诛", "伏誅", "诛死", "誅死"),
    "株连": ("株連", "牵连", "牽連", "连坐", "連坐", "坐死", "党死", "黨死", "亲族", "親族", "妻女弟侄", "七十余人"),
    "株連": ("株连", "牵连", "牽連", "连坐", "連坐", "坐死", "党死", "黨死", "亲族", "親族", "妻女弟侄", "七十余人"),
    "三族": ("族诛", "族誅", "灭族", "滅族", "亲族", "親族", "妻女弟侄", "七十余人"),
    "九族": ("灭族", "滅族", "亲族", "親族", "妻女弟侄"),
    "谋反": ("谋叛", "謀叛", "逆谋", "逆謀", "不轨", "不軌", "反状", "反狀", "坐党", "坐黨", "党死", "黨死"),
    "謀反": ("谋叛", "謀叛", "逆谋", "逆謀", "不轨", "不軌", "反状", "反狀", "坐党", "坐黨", "党死", "黨死"),
    "大逆": ("不轨", "不軌", "逆谋", "逆謀", "反状", "反狀", "坐党", "坐黨"),
    "诛": ("伏诛", "伏誅", "诛死", "誅死", "族诛", "族誅", "大诛", "大誅"),
    "誅": ("伏诛", "伏誅", "诛死", "誅死", "族诛", "族誅", "大诛", "大誅"),
    "自尽": ("自盡", "自刎", "赐自尽", "賜自盡", "流放", "流徙"),
    "自盡": ("自尽", "自刎", "赐自尽", "賜自盡", "流放", "流徙"),
    "籍其家": ("籍没", "籍沒", "诛", "誅", "诛死", "誅死", "坐死", "党死", "黨死"),
}

PGSQL_SCHEMA_DRAFT = """
-- retrieval_v2 object source cache draft schema.
-- First rollout writes file artifacts only; this DDL is an explicit slot for a later PG-backed index.

create table if not exists retrieval_v2.object_source_cache_persons (
    person_cache_code text primary key,
    object_code text not null default '',
    person_name text not null,
    normalized_name text not null default '',
    aliases text[] not null default array[]::text[],
    is_emperor boolean not null default false,
    seed_sources text[] not null default array[]::text[],
    priority integer not null default 100,
    cache_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_object_source_cache_person_name_not_blank check (btrim(person_name) <> ''),
    constraint rv2_object_source_cache_person_priority_positive check (priority > 0)
);

create table if not exists retrieval_v2.object_source_cache_documents (
    document_cache_code text primary key,
    person_cache_code text not null references retrieval_v2.object_source_cache_persons(person_cache_code) on delete cascade,
    source_title text not null,
    wikisource_title text not null default '',
    source_role text not null,
    source_shape text not null default 'unknown',
    source_key text not null default '',
    shared_cache_text_path text not null default '',
    text_sha256 text not null default '',
    text_chars integer not null default 0,
    document_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint rv2_object_source_cache_document_title_not_blank check (btrim(source_title) <> '')
);

create table if not exists retrieval_v2.object_source_cache_slices (
    slice_cache_code text primary key,
    document_cache_code text not null references retrieval_v2.object_source_cache_documents(document_cache_code) on delete cascade,
    person_cache_code text not null references retrieval_v2.object_source_cache_persons(person_cache_code) on delete cascade,
    locator text not null,
    matched_aliases text[] not null default array[]::text[],
    raw_text text not null,
    quote_hash text not null,
    slice_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint rv2_object_source_cache_slice_raw_not_blank check (btrim(raw_text) <> '')
);

create table if not exists retrieval_v2.object_source_cache_coverage (
    person_cache_code text primary key references retrieval_v2.object_source_cache_persons(person_cache_code) on delete cascade,
    has_source_document boolean not null default false,
    has_biography_source boolean not null default false,
    has_emperor_context_source boolean not null default false,
    mention_slice_count integer not null default 0,
    claim_closure_risk text not null default '',
    needs_agent_review boolean not null default false,
    agent_review_reason text not null default '',
    agent_review_priority integer not null default 100,
    agent_status text not null default 'not_requested',
    coverage_payload jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    constraint rv2_object_source_cache_coverage_agent_status_ck check (
        agent_status in ('not_requested', 'queued', 'running', 'succeeded', 'failed', 'blocked', 'cancelled')
    )
);

create index if not exists rv2_object_source_cache_person_name_idx
on retrieval_v2.object_source_cache_persons(normalized_name, is_emperor);

create index if not exists rv2_object_source_cache_documents_person_idx
on retrieval_v2.object_source_cache_documents(person_cache_code, source_role, source_shape);

create index if not exists rv2_object_source_cache_slices_person_idx
on retrieval_v2.object_source_cache_slices(person_cache_code, document_cache_code);
""".strip() + "\n"


class ObjectSourceCacheError(RuntimeError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ObjectSourceCacheError(f"{path}:{line_no}: expected JSON object")
        rows.append(payload)
    return rows


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    write_text(path, pretty_json(dict(payload)))


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    text = "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows)
    write_text(path, text)


def document_cache_code(seed: Mapping[str, Any], title: str, source_role: str) -> str:
    return f"OSD-{stable_hash([person_cache_code(seed), source_role, normalize_title(title)], length=18)}"


def slice_cache_code(document_code: str, person_code: str, start: int, end: int, aliases: Sequence[str]) -> str:
    return f"OSS-{stable_hash([document_code, person_code, start, end, list(aliases)], length=18)}"


def search_names_for_seed(seed: Mapping[str, Any], *, max_search_names: int) -> list[str]:
    aliases = seed_aliases(seed)
    if seed_is_emperor(seed):
        preferred = [
            text_from(seed, "title", "temple_name", "posthumous_name"),
            seed_name(seed),
            *[alias for alias in aliases if len(alias) >= 2],
        ]
    else:
        preferred = [seed_name(seed), *[alias for alias in aliases if len(alias) >= 2]]
    return unique_strings(preferred)[: max(1, max_search_names)]


def search_query_name_variants(search_name: str, *, max_variants: int = 2) -> list[str]:
    name = clean_name(search_name)
    if not name:
        return []
    same_length = [variant for variant in alias_script_variants(name) if len(variant) == len(name)]
    return unique_strings([name, *same_length])[: max(1, max_variants)]


def seed_source_target_refs(seed: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("source_target_refs", "source_targets"):
        raw = seed.get(key)
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            values.extend(str(value or "") for value in raw)
    return unique_strings(clean_name(value) for value in values if clean_name(value))


def source_hint_text_aliases(source_hint: str) -> list[str]:
    normalized = normalize_title(source_hint)
    aliases = [normalized]
    aliases.extend(SOURCE_HINT_TEXT_ALIASES.get(normalized, ()))
    return unique_strings(alias for alias in aliases if alias)


def source_target_ref_matches_hint(source_target_ref: str, source_hint: str) -> bool:
    normalized_ref = normalize_title(source_target_ref)
    return any(alias and alias in normalized_ref for alias in source_hint_text_aliases(source_hint))


def source_target_ref_terms(source_target_ref: str, seed: Mapping[str, Any], source_hint: str) -> list[str]:
    source_aliases = set(source_hint_text_aliases(source_hint))
    seed_alias_values = {normalize_title(alias) for alias in seed_aliases(seed) if alias}
    terms: list[str] = []
    for raw_token in SOURCE_TARGET_REF_SPLIT_RE.split(source_target_ref):
        token = normalize_title(raw_token)
        if not token or token in source_aliases or token in seed_alias_values:
            continue
        if token in {"传", "傳", "列传", "列傳", "本传", "本傳"}:
            continue
        terms.append(token)
    return unique_strings(terms)[:2]


def source_target_ref_query_rows(
    seed: Mapping[str, Any],
    *,
    source_hints: Sequence[str],
    max_search_names: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    search_names = search_names_for_seed(seed, max_search_names=max_search_names)
    for source_target_ref in seed_source_target_refs(seed):
        matched_hints = [hint for hint in source_hints if source_target_ref_matches_hint(source_target_ref, hint)]
        for source_hint in matched_hints or list(source_hints):
            terms = source_target_ref_terms(source_target_ref, seed, source_hint)
            for search_name in search_names:
                for query_name in search_query_name_variants(search_name):
                    query_parts = [query_name, source_hint, *terms]
                    query = " ".join(part for part in query_parts if part).strip()
                    if not query:
                        continue
                    rows.append(
                        {
                            "query": query,
                            "base_query": query,
                            "query_name": query_name,
                            "search_name": search_name,
                            "source_hint": source_hint,
                            "source_target_ref": source_target_ref,
                            "query_kind": "source_target_ref",
                        }
                    )
    return rows


def source_target_ref_directory_documents(
    seed: Mapping[str, Any],
    *,
    source_hints: Sequence[str],
    timeout: int,
    fetch_context: FetchContext | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if fetch_context is None:
        return [], []
    source_role = source_role_for_seed(seed)
    documents: dict[str, dict[str, Any]] = {}
    hits: list[dict[str, Any]] = []
    search_names = search_names_for_seed(seed, max_search_names=4)
    for source_target_ref in seed_source_target_refs(seed):
        matched_hints = [hint for hint in source_hints if source_target_ref_matches_hint(source_target_ref, hint)]
        for source_hint in matched_hints or list(source_hints):
            allowed_roots = source_roots_for_hint(source_hint, emp_metadata=dict(seed))
            for root_title in allowed_roots:
                if not is_allowed_source_root_title(root_title, allowed_roots):
                    continue
                try:
                    directory_text = fetch_wikisource_plain_text(root_title, timeout=timeout, fetch_context=fetch_context)
                except Exception as exc:
                    hits.append(
                        {
                            "query": root_title,
                            "person_name": seed_name(seed),
                            "source_hint": source_hint,
                            "source_target_ref": source_target_ref,
                            "query_kind": "source_target_ref_directory",
                            "error": repr(exc),
                        }
                    )
                    continue
                source_titles = derived_volume_titles_from_directory_text(
                    title=root_title,
                    directory_text=directory_text,
                    allowed_roots=allowed_roots,
                    search_names=[*search_names, seed_name(seed)],
                )
                hit = {
                    "query": root_title,
                    "person_name": seed_name(seed),
                    "source_hint": source_hint,
                    "source_target_ref": source_target_ref,
                    "query_kind": "source_target_ref_directory",
                    "title": root_title,
                }
                if source_titles:
                    hit["derived_source_titles"] = source_titles
                else:
                    hit["rejected_reason"] = "directory_no_matching_volume"
                hits.append(hit)
                for source_title in source_titles:
                    key = normalize_title(source_title)
                    documents.setdefault(
                        key,
                        {
                            "document_cache_code": document_cache_code(seed, source_title, source_role),
                            "person_cache_code": person_cache_code(seed),
                            "person_name": seed_name(seed),
                            "source_title": source_title,
                            "title": source_title,
                            "wikisource_title": source_title,
                            "url": "",
                            "source_role": source_role,
                            "source_kind": "wikisource_page",
                            "why_selected": f"object source cache source_target_ref directory for {seed_name(seed)}",
                            "search_query": root_title,
                            "search_snippet": "",
                            "source_hint": source_hint,
                            "source_target_ref": source_target_ref,
                            "wikisource_title_candidates": source_document_title_candidates(source_title) or [source_title],
                        },
                    )
    return list(documents.values()), hits


def generic_object_source_query_rows(
    seed: Mapping[str, Any],
    *,
    source_hints: Sequence[str],
    max_search_names: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for search_name in search_names_for_seed(seed, max_search_names=max_search_names):
        for query_name in search_query_name_variants(search_name):
            for source_hint in source_hints:
                base_query = f"{query_name} {source_hint}".strip()
                queries = [base_query]
                if not seed_is_emperor(seed):
                    queries.extend(f"{base_query} {suffix}".strip() for suffix in OBJECT_BIOGRAPHY_QUERY_SUFFIXES)
                for query in unique_strings(queries):
                    rows.append(
                        {
                            "query": query,
                            "base_query": base_query,
                            "query_name": query_name,
                            "search_name": search_name,
                            "source_hint": source_hint,
                            "query_kind": "generic_object_source",
                        }
                    )
    return rows


def cached_search_wikisource(
    search_fn: SearchFn,
    query: str,
    *,
    limit: int,
    timeout: int,
    fetch_context: FetchContext | None,
) -> list[dict[str, Any]]:
    if fetch_context is None:
        return search_fn(query, limit=limit, timeout=timeout)
    try:
        return search_fn(query, limit=limit, timeout=timeout, fetch_context=fetch_context)
    except TypeError:
        return search_fn(query, limit=limit, timeout=timeout)


def derived_volume_titles_from_directory_text(
    *,
    title: str,
    directory_text: str,
    allowed_roots: Sequence[str],
    search_names: Sequence[str],
) -> list[str]:
    if not is_allowed_source_root_title(title, allowed_roots):
        return []
    return derived_volume_titles_from_snippet(
        source_root=source_root_from_title(title),
        snippet=directory_text,
        search_names=search_names,
    )


def derived_volume_titles_from_directory_hit(
    *,
    title: str,
    allowed_roots: Sequence[str],
    search_names: Sequence[str],
    timeout: int,
    fetch_context: FetchContext | None,
) -> tuple[list[str], dict[str, Any]]:
    if fetch_context is None or not is_allowed_source_root_title(title, allowed_roots):
        return [], {}
    try:
        directory_text = fetch_wikisource_plain_text(title, timeout=timeout, fetch_context=fetch_context)
    except Exception as exc:
        return [], {"directory_index_error": repr(exc)}
    source_titles = derived_volume_titles_from_directory_text(
        title=title,
        directory_text=directory_text,
        allowed_roots=allowed_roots,
        search_names=search_names,
    )
    meta: dict[str, Any] = {
        "directory_index_checked": True,
        "directory_index_title": title,
    }
    if source_titles:
        meta["directory_index_source_titles"] = source_titles
    return source_titles, meta


def has_biography_signal(seed: Mapping[str, Any], document: Mapping[str, Any], full_text: str) -> bool:
    title = normalize_title(text_from(document, "wikisource_title", "title", "source_title"))
    aliases = seed_aliases(seed)
    if any(alias and normalize_title(alias) in title for alias in aliases):
        return True
    hint = document.get("source_document_hint") if isinstance(document.get("source_document_hint"), Mapping) else {}
    hint_text = normalize_title(" ".join(text_from(hint, key) for key in ("title", "volume", "locator") if text_from(hint, key)))
    if hint_text and any(alias and normalize_title(alias) in hint_text for alias in aliases) and any(term in hint_text for term in ("傳", "传")):
        return True
    head = full_text[:800]
    normalized_head = normalize_title(head)
    has_name_in_head = any(alias and normalize_title(alias) in normalized_head for alias in aliases)
    has_bio_heading = any(term in head for term in ("列传", "列傳", "傳第", "传第", "本傳", "本传", "傳", "传"))
    return has_name_in_head and has_bio_heading


def discover_source_documents(
    seed: Mapping[str, Any],
    *,
    search_fn: SearchFn,
    pages_per_query: int,
    timeout: int,
    source_hint_limit: int,
    max_search_names: int,
    include_emperor_annals: bool,
    fetch_context: FetchContext | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_hints = seed_source_hints(seed, source_hint_limit=source_hint_limit)
    source_role = source_role_for_seed(seed)
    if source_role == "emperor_context" and not include_emperor_annals:
        return [], []

    documents: dict[str, dict[str, Any]] = {}
    hits: list[dict[str, Any]] = []
    for hint in seed_source_document_hints(seed):
        source_title = text_from(hint, "wikisource_title")
        if not source_title:
            continue
        key = normalize_title(source_title)
        documents.setdefault(
            key,
            {
                "document_cache_code": document_cache_code(seed, source_title, source_role),
                "person_cache_code": person_cache_code(seed),
                "person_name": seed_name(seed),
                "source_title": source_title,
                "title": source_title,
                "wikisource_title": source_title,
                "url": hint.get("url") or "",
                "source_role": source_role,
                "source_kind": "wikisource_page",
                "why_selected": f"object source cache source_document_hint for {seed_name(seed)}",
                "search_query": "",
                "search_snippet": "",
                "source_hint": hint.get("title") or "",
                "wikisource_title_candidates": hint.get("wikisource_title_candidates") or [source_title],
                "source_document_hint": hint,
            },
        )
    if pages_per_query <= 0:
        return list(documents.values()), hits
    direct_documents, direct_hits = source_target_ref_directory_documents(
        seed,
        source_hints=source_hints,
        timeout=timeout,
        fetch_context=fetch_context,
    )
    hits.extend(direct_hits)
    for document in direct_documents:
        key = normalize_title(text_from(document, "source_title", "wikisource_title", "title"))
        if key:
            documents.setdefault(key, document)
    query_rows = [
        *source_target_ref_query_rows(seed, source_hints=source_hints, max_search_names=max_search_names),
        *generic_object_source_query_rows(seed, source_hints=source_hints, max_search_names=max_search_names),
    ]
    seen_query_keys: set[tuple[str, str]] = set()
    seen_titles_for_base: dict[str, set[str]] = {}
    for query_row in query_rows:
        query = query_row["query"]
        source_hint = query_row["source_hint"]
        query_key = (query, source_hint)
        if query_key in seen_query_keys:
            continue
        seen_query_keys.add(query_key)
        base_query = query_row.get("base_query") or query
        query_name = query_row.get("query_name") or seed_name(seed)
        search_name = query_row.get("search_name") or query_name
        allowed_roots = source_roots_for_hint(source_hint, emp_metadata=dict(seed))
        base_seen = seen_titles_for_base.setdefault(base_query, set())
        try:
            pages = cached_search_wikisource(
                search_fn,
                query,
                limit=pages_per_query,
                timeout=timeout,
                fetch_context=fetch_context,
            )
        except Exception as exc:
            hit_error = {"query": query, "person_name": seed_name(seed), "source_hint": source_hint, "error": repr(exc)}
            if query_row.get("source_target_ref"):
                hit_error["source_target_ref"] = query_row["source_target_ref"]
                hit_error["query_kind"] = query_row.get("query_kind") or ""
            hits.append(hit_error)
            continue
        for page in pages:
            title = normalize_title(clean_name(page.get("title")))
            if title in base_seen:
                continue
            base_seen.add(title)
            snippet = clean_name(page.get("snippet"))
            hit = {
                "query": query,
                "person_name": seed_name(seed),
                "source_hint": source_hint,
                "title": title,
                "url": page.get("url") or "",
                "snippet": snippet,
            }
            if query_row.get("source_target_ref"):
                hit["source_target_ref"] = query_row["source_target_ref"]
                hit["query_kind"] = query_row.get("query_kind") or ""
            if query_name != search_name:
                hit["script_variant_query"] = True
                hit["base_search_name"] = search_name
            if query != base_query:
                hit["expanded_query"] = True
            hits.append(hit)
            source_titles = [title] if title and is_allowed_source_document_title(title, allowed_roots) else []
            if not source_titles:
                source_titles = derived_volume_titles_from_source_hit(
                    title=title,
                    snippet=snippet,
                    allowed_roots=allowed_roots,
                    search_names=[query_name, search_name, seed_name(seed)],
                )
                if source_titles:
                    hit["derived_source_titles"] = source_titles
            if not source_titles:
                source_titles = derived_volume_titles_from_root_hit(
                    title=title,
                    snippet=snippet,
                    allowed_roots=allowed_roots,
                    search_names=[query_name, search_name, seed_name(seed)],
                )
                if source_titles:
                    hit["derived_source_titles"] = source_titles
            if not source_titles:
                source_titles, directory_meta = derived_volume_titles_from_directory_hit(
                    title=title,
                    allowed_roots=allowed_roots,
                    search_names=[query_name, search_name, seed_name(seed)],
                    timeout=timeout,
                    fetch_context=fetch_context,
                )
                hit.update(directory_meta)
            if not source_titles:
                hit["rejected_reason"] = "source_root_mismatch_or_not_volume"
                hit["allowed_source_roots"] = allowed_roots
                continue
            for source_title in source_titles:
                key = normalize_title(source_title)
                why_selected = f"object source cache search for {seed_name(seed)}"
                if query_row.get("source_target_ref"):
                    why_selected = f"object source cache source_target_ref search for {seed_name(seed)}"
                documents.setdefault(
                    key,
                    {
                        "document_cache_code": document_cache_code(seed, source_title, source_role),
                        "person_cache_code": person_cache_code(seed),
                        "person_name": seed_name(seed),
                        "source_title": source_title,
                        "title": source_title,
                        "wikisource_title": source_title,
                        "url": page.get("url") or "" if source_title == title else "",
                        "source_role": source_role,
                        "source_kind": "wikisource_page",
                        "why_selected": why_selected,
                        "search_query": query,
                        "search_snippet": snippet,
                        "source_hint": source_hint,
                        "source_target_ref": query_row.get("source_target_ref") or "",
                        "wikisource_title_candidates": source_document_title_candidates(source_title) or [source_title],
                    },
                )
    return list(documents.values()), hits


def source_shape(seed: Mapping[str, Any], document: Mapping[str, Any], full_text: str, mention_count: int) -> str:
    if seed_is_emperor(seed):
        return "emperor_annals_or_context_candidate"
    title = normalize_title(text_from(document, "wikisource_title", "title", "source_title"))
    if has_biography_signal(seed, document, full_text):
        return "object_biography_candidate"
    if mention_count > 0 and isinstance(document.get("source_document_hint"), Mapping):
        return "object_existing_source_candidate"
    if mention_count > 0:
        return "object_mention_candidate"
    if seed_name(seed) and seed_name(seed) in title:
        return "title_name_candidate"
    return "unmatched_fetched_source"


def nearest_section_heading(full_text: str, index: int) -> str:
    heading = ""
    for match in SECTION_HEADING_RE.finditer(full_text):
        if match.start() > index:
            break
        heading = match.group(1).strip()
    return heading


def whitespace_insensitive_text_index(full_text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    positions: list[int] = []
    for index, char in enumerate(full_text):
        if char.isspace():
            continue
        chars.append(char)
        positions.append(index)
    return "".join(chars), positions


def alias_positions(full_text: str, alias: str) -> list[int]:
    clean_alias = text_from({"alias": alias}, "alias")
    if not clean_alias:
        return []
    positions: list[int] = []
    seen: set[int] = set()
    start = 0
    while True:
        index = full_text.find(clean_alias, start)
        if index < 0:
            break
        if index not in seen:
            positions.append(index)
            seen.add(index)
        start = index + max(1, len(clean_alias))
    normalized_alias = normalize_title(clean_alias)
    if len(normalized_alias) >= 2:
        compact_text_value, index_map = whitespace_insensitive_text_index(full_text)
        start = 0
        while True:
            compact_index = compact_text_value.find(normalized_alias, start)
            if compact_index < 0:
                break
            if compact_index < len(index_map):
                original_index = index_map[compact_index]
                if original_index not in seen:
                    positions.append(original_index)
                    seen.add(original_index)
            start = compact_index + max(1, len(normalized_alias))
    return positions


def seed_summary_lead_terms(seed: Mapping[str, Any]) -> list[str]:
    raw_leads = seed.get("summary_leads")
    if isinstance(raw_leads, Mapping):
        lead_rows: Sequence[Any] = [raw_leads]
    elif isinstance(raw_leads, Sequence) and not isinstance(raw_leads, (str, bytes)):
        lead_rows = raw_leads
    else:
        lead_rows = []
    terms: list[str] = []
    for lead in lead_rows:
        if not isinstance(lead, Mapping):
            continue
        raw_terms = lead.get("lead_terms")
        if isinstance(raw_terms, str):
            terms.append(raw_terms)
        elif isinstance(raw_terms, Sequence) and not isinstance(raw_terms, (str, bytes)):
            terms.extend(str(term or "") for term in raw_terms)
    expanded_terms = list(terms)
    normalized_terms = {normalize_title(term) for term in terms if term}
    for trigger, expansions in SUMMARY_LEAD_TERM_EXPANSIONS.items():
        if normalize_title(trigger) in normalized_terms:
            expanded_terms.extend(expansions)
    return unique_strings(
        term
        for term in expanded_terms
        if len(normalize_title(term)) >= 2 or normalize_title(term) in SUMMARY_LEAD_ALLOWED_SINGLE_CHAR_TERMS
    )


def seed_summary_lead_anchor_aliases(seed: Mapping[str, Any]) -> list[str]:
    aliases = seed_aliases(seed)
    name = seed_name(seed)
    normalized = normalize_title(name)
    if len(normalized) == 3 and all("\u3400" <= char <= "\u9fff" for char in normalized):
        aliases.append(normalized[1:])
    return unique_strings(alias for alias in aliases if alias)


def matched_aliases_in_text(text: str, aliases: Sequence[str]) -> list[str]:
    normalized_text = normalize_title(text)
    return unique_strings(alias for alias in aliases if alias and normalize_title(alias) in normalized_text)


def matched_lead_terms_in_text(text: str, lead_terms: Sequence[str]) -> list[str]:
    normalized_text = normalize_title(text)
    return unique_strings(term for term in lead_terms if term and normalize_title(term) in normalized_text)


def summary_lead_term_priority(term: str) -> int:
    normalized = normalize_title(term)
    if normalized in SUMMARY_LEAD_HIGH_PRIORITY_TERMS:
        return 0
    if normalized in SUMMARY_LEAD_LOW_PRIORITY_TERMS:
        return 2
    return 1


def build_mention_slices(
    seed: Mapping[str, Any],
    document: Mapping[str, Any],
    full_text: str,
    *,
    context_chars: int,
    max_slices_per_document: int,
) -> list[dict[str, Any]]:
    aliases = seed_aliases(seed)
    lead_anchor_aliases = seed_summary_lead_anchor_aliases(seed)
    lead_terms = seed_summary_lead_terms(seed)
    anchors: list[dict[str, Any]] = []
    for term in lead_terms:
        for index in alias_positions(full_text, term):
            start, end = context_bounds(full_text, index, context_chars=context_chars)
            term_section_heading = nearest_section_heading(full_text, index)
            matched_aliases = []
            for alias in lead_anchor_aliases:
                alias_in_same_section = any(
                    start <= alias_index < end
                    and (
                        not term_section_heading
                        or nearest_section_heading(full_text, alias_index) == term_section_heading
                    )
                    for alias_index in alias_positions(full_text, alias)
                )
                if alias_in_same_section:
                    matched_aliases.append(alias)
            if not matched_aliases:
                continue
            anchors.append(
                {
                    "index": index,
                    "matched_aliases": matched_aliases,
                    "matched_lead_terms": [term],
                    "priority": summary_lead_term_priority(term),
                    "slice_kind": "summary_lead_term_anchor",
                }
            )
    for alias in aliases:
        if not alias:
            continue
        for index in alias_positions(full_text, alias):
            start, end = context_bounds(full_text, index, context_chars=context_chars)
            anchors.append(
                {
                    "index": index,
                    "matched_aliases": [alias],
                    "matched_lead_terms": matched_lead_terms_in_text(full_text[start:end], lead_terms),
                    "priority": 10,
                    "slice_kind": "person_alias_anchor",
                }
            )
    if not anchors:
        return []
    windows: list[dict[str, Any]] = []
    for anchor in sorted(anchors, key=lambda item: (int(item["priority"]), int(item["index"]))):
        index = int(anchor["index"])
        start, end = context_bounds(full_text, index, context_chars=context_chars)
        merged = False
        for window in windows:
            if start <= int(window["end"]) + 20 and end >= int(window["start"]) - 20:
                window["start"] = min(int(window["start"]), start)
                window["end"] = max(int(window["end"]), end)
                window["matched_aliases"] = unique_strings([*window["matched_aliases"], *anchor["matched_aliases"]])
                window["matched_lead_terms"] = unique_strings([*window["matched_lead_terms"], *anchor["matched_lead_terms"]])
                if int(anchor["priority"]) < int(window["priority"]):
                    window["priority"] = anchor["priority"]
                    window["anchor_index"] = index
                    window["slice_kind"] = anchor["slice_kind"]
                merged = True
                break
        if merged:
            continue
        if len(windows) >= max_slices_per_document:
            continue
        windows.append(
            {
                "start": start,
                "end": end,
                "matched_aliases": list(anchor["matched_aliases"]),
                "matched_lead_terms": list(anchor["matched_lead_terms"]),
                "anchor_index": index,
                "priority": anchor["priority"],
                "slice_kind": anchor["slice_kind"],
            }
        )

    rows: list[dict[str, Any]] = []
    for window in windows:
        start = int(window["start"])
        end = int(window["end"])
        matched_aliases = list(window["matched_aliases"])
        anchor_index = int(window["anchor_index"])
        text = compact_text(full_text[start:end])
        doc_code = text_from(document, "document_cache_code")
        person_code = person_cache_code(seed)
        section_heading = nearest_section_heading(full_text, anchor_index)
        row = {
            "slice_cache_code": slice_cache_code(doc_code, person_code, start, end, matched_aliases),
            "document_cache_code": doc_code,
            "person_cache_code": person_code,
            "person_name": seed_name(seed),
            "source_title": text_from(document, "source_title", "title", "wikisource_title"),
            "source_role": document.get("source_role") or source_role_for_seed(seed),
            "locator": f"chars:{start}-{end}",
            "section_heading": section_heading,
            "matched_aliases": matched_aliases,
            "raw_text": text,
            "quote_hash": sha256_text(text),
        }
        matched_lead_terms = list(window["matched_lead_terms"])
        if matched_lead_terms:
            row["lead_terms"] = matched_lead_terms
            row["slice_kind"] = window["slice_kind"]
        rows.append(row)
    return rows


def build_locator_backed_slice(
    seed: Mapping[str, Any],
    document: Mapping[str, Any],
    full_text: str,
    *,
    context_chars: int,
) -> list[dict[str, Any]]:
    if not full_text.strip() or not isinstance(document.get("source_document_hint"), Mapping):
        return []
    hint = document.get("source_document_hint")
    hint_text = normalize_title(" ".join(text_from(hint, key) for key in ("locator", "title", "volume") if text_from(hint, key)))
    matched_aliases = unique_strings(alias for alias in seed_aliases(seed) if alias and normalize_title(alias) in hint_text)
    if not matched_aliases:
        matched_aliases = [seed_name(seed)]
    end = min(len(full_text), max(600, context_chars * 3))
    text = compact_text(full_text[:end])
    if not text:
        return []
    doc_code = text_from(document, "document_cache_code")
    person_code = person_cache_code(seed)
    return [
        {
            "slice_cache_code": slice_cache_code(doc_code, person_code, 0, end, matched_aliases),
            "document_cache_code": doc_code,
            "person_cache_code": person_code,
            "person_name": seed_name(seed),
            "source_title": text_from(document, "source_title", "title", "wikisource_title"),
            "source_role": document.get("source_role") or source_role_for_seed(seed),
            "locator": f"source_document_hint:chars:0-{end}",
            "matched_aliases": matched_aliases,
            "raw_text": text,
            "quote_hash": sha256_text(text),
            "slice_kind": "source_document_hint_locator",
        }
    ]


def document_wikisource_titles(document: Mapping[str, Any]) -> list[str]:
    candidates = [text_from(document, "wikisource_title", "title")]
    raw_candidates = document.get("wikisource_title_candidates")
    if isinstance(raw_candidates, Sequence) and not isinstance(raw_candidates, (str, bytes)):
        candidates.extend(text_from({"value": value}, "value") for value in raw_candidates)
    return unique_strings(candidate for candidate in candidates if candidate)


def fetch_managed_wikisource_text(
    document: Mapping[str, Any],
    *,
    cache_dir: Path,
    timeout: int,
    fetch_context: FetchContext,
) -> tuple[str, dict[str, Any]]:
    last_error: Exception | None = None
    titles = document_wikisource_titles(document)
    for index, candidate_title in enumerate(titles):
        try:
            full_text = fetch_wikisource_plain_text(candidate_title, timeout=timeout, fetch_context=fetch_context)
        except Exception as exc:
            last_error = exc
            continue
        source_key = f"wikisource:{candidate_title}"
        fetch_meta = {
            "cache_status": "managed_cache",
            "source_kind": "wikisource",
            "source_key": source_key,
            "wikisource_title": candidate_title,
        }
        if full_text.strip() or index == len(titles) - 1:
            write_cached_text(cache_dir, source_key, full_text, fetch_meta)
            return full_text, fetch_meta
    if last_error is not None:
        raise last_error
    return "", {"cache_status": "managed_cache", "source_kind": "wikisource", "source_key": ""}


def fetch_and_slice_document(
    seed: Mapping[str, Any],
    document: Mapping[str, Any],
    *,
    cache_dir: Path,
    timeout: int,
    context_chars: int,
    max_slices_per_document: int,
    fetch_context: FetchContext | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    title = text_from(document, "wikisource_title", "title")
    if fetch_context is not None and title:
        full_text, fetch_meta = fetch_managed_wikisource_text(
            document,
            cache_dir=cache_dir,
            timeout=timeout,
            fetch_context=fetch_context,
        )
    else:
        full_text, fetch_meta = fetch_document_text(document, cache_dir=cache_dir, timeout=timeout)
    slices = build_mention_slices(
        seed,
        document,
        full_text,
        context_chars=context_chars,
        max_slices_per_document=max_slices_per_document,
    )
    shape = source_shape(seed, document, full_text, len(slices))
    if not slices and shape == "object_biography_candidate":
        slices = build_locator_backed_slice(seed, document, full_text, context_chars=context_chars)
    source_key = clean_name(fetch_meta.get("source_key"))
    text_path, meta_path = cache_paths(cache_dir, source_key) if source_key else (Path(), Path())
    row = dict(document)
    fetched_title = text_from(fetch_meta, "wikisource_title")
    row.update(
        {
            "source_shape": shape,
            "source_key": source_key,
            "source_title": fetched_title or text_from(document, "source_title", "title", "wikisource_title"),
            "title": fetched_title or text_from(document, "title", "wikisource_title"),
            "wikisource_title": fetched_title or text_from(document, "wikisource_title", "title"),
            "shared_cache_text_path": str(text_path) if text_path else "",
            "shared_cache_meta_path": str(meta_path) if meta_path else "",
            "cache_status": fetch_meta.get("cache_status"),
            "fetch_meta": fetch_meta,
            "text_sha256": sha256_text(full_text),
            "text_chars": len(full_text),
            "mention_slice_count": len(slices),
        }
    )
    return row, slices


def coverage_for_seed(seed: Mapping[str, Any], documents: Sequence[Mapping[str, Any]], slices: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    has_source_document = bool(documents)
    source_shapes = unique_strings(doc.get("source_shape") for doc in documents)
    source_roles = unique_strings(doc.get("source_role") for doc in documents)
    mention_count = len(slices)
    is_emperor = seed_is_emperor(seed)
    has_biography_source = any(shape in {"object_biography_candidate", "object_existing_source_candidate", "title_name_candidate"} for shape in source_shapes)
    has_emperor_context_source = any(role == "emperor_context" for role in source_roles)
    if not has_source_document:
        risk = "no_source_document"
        agent_reason = "source_discovery_empty"
    elif is_emperor and not has_emperor_context_source:
        risk = "no_emperor_context_source"
        agent_reason = "emperor_context_discovery_uncertain"
    elif is_emperor:
        risk = ""
        agent_reason = ""
    elif mention_count == 0:
        risk = "source_fetched_but_no_person_mention"
        agent_reason = "source_shape_or_alias_conflict"
    elif not is_emperor and not has_biography_source:
        risk = "mentions_without_biography_source"
        agent_reason = "biography_shape_uncertain"
    else:
        risk = ""
        agent_reason = ""
    needs_agent_review = bool(risk)
    priority = 50 if needs_agent_review and seed_priority(seed) <= 50 else 80 if needs_agent_review else 100
    return {
        "person_cache_code": person_cache_code(seed),
        "person_name": seed_name(seed),
        "is_emperor": is_emperor,
        "has_source_document": has_source_document,
        "has_biography_source": has_biography_source,
        "has_emperor_context_source": has_emperor_context_source,
        "mention_slice_count": mention_count,
        "source_document_count": len(documents),
        "source_roles": source_roles,
        "source_shapes": source_shapes,
        "claim_closure_risk": risk,
        "needs_agent_review": needs_agent_review,
        "agent_review_reason": agent_reason,
        "agent_review_priority": priority,
        "agent_input_bundle_path": "",
        "agent_expected_output_schema": "object_source_cache_agent_review_v1",
        "agent_status": "not_requested",
    }


def build_agent_review_row(seed: Mapping[str, Any], coverage: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "agent_task_code": f"OSA-{stable_hash([coverage.get('person_cache_code'), coverage.get('agent_review_reason')], length=18)}",
        "person_cache_code": coverage.get("person_cache_code"),
        "person_name": coverage.get("person_name"),
        "needs_agent_review": bool(coverage.get("needs_agent_review")),
        "claim_closure_risk": coverage.get("claim_closure_risk") or "",
        "agent_review_reason": coverage.get("agent_review_reason") or "",
        "agent_review_priority": coverage.get("agent_review_priority") or 100,
        "agent_input_bundle_path": coverage.get("agent_input_bundle_path") or "",
        "agent_expected_output_schema": coverage.get("agent_expected_output_schema") or "object_source_cache_agent_review_v1",
        "agent_status": "not_requested",
        "seed_sources": seed.get("seed_sources") or [],
    }


def cache_document_usable_for_overlay(row: Mapping[str, Any]) -> bool:
    role = clean_name(row.get("source_role"))
    if role == "emperor_context":
        return int(row.get("text_chars") or 0) > 0
    if int(row.get("mention_slice_count") or 0) > 0:
        return True
    return clean_name(row.get("source_shape")) in {
        "object_biography_candidate",
        "object_existing_source_candidate",
        "object_mention_candidate",
        "object_biography_or_direct_mention_candidate",
        "object_alias_mention_candidate",
        "title_name_candidate",
    }


def task_object_names(task: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    for raw_seed in task.get("object_seeds") or []:
        if not isinstance(raw_seed, Mapping):
            continue
        names.extend(seed_aliases(raw_seed))
    return unique_strings(names)


def task_target_names(task: Mapping[str, Any]) -> list[str]:
    profile = task.get("target_profile") if isinstance(task.get("target_profile"), Mapping) else {}
    payload = task.get("target_payload") if isinstance(task.get("target_payload"), Mapping) else {}
    values = [
        task.get("emperor_name"),
        profile.get("primary_name"),
        *(profile.get("aliases") or []),
        *(profile.get("must_check_titles") or []),
        payload.get("title"),
        payload.get("temple_name"),
        payload.get("posthumous_name"),
    ]
    expanded: list[str] = []
    for value in values:
        text = clean_name(value)
        if not text:
            continue
        expanded.append(text)
        expanded.extend(alias_script_variants(text))
    return unique_strings(expanded)


def overlay_document_row(row: Mapping[str, Any], *, object_name: str, index: int) -> dict[str, Any]:
    title = text_from(row, "wikisource_title", "source_title", "title")
    return {
        "document_code": f"DOC-CACHE-{stable_hash([row.get('document_cache_code'), title, index], length=12)}",
        "title": title,
        "wikisource_title": title,
        "url": row.get("url") or "",
        "source_kind": row.get("source_kind") or "wikisource_page",
        "why_selected": f"object source cache hit for {object_name}",
        "cache_source_role": row.get("source_role") or "",
        "object_source_cache": {
            "document_cache_code": row.get("document_cache_code") or "",
            "person_cache_code": row.get("person_cache_code") or "",
            "person_name": row.get("person_name") or object_name,
            "source_shape": row.get("source_shape") or "",
            "source_key": row.get("source_key") or "",
            "shared_cache_text_path": row.get("shared_cache_text_path") or "",
            "mention_slice_count": row.get("mention_slice_count") or 0,
        },
    }


def overlay_task_from_cache(
    task: Mapping[str, Any],
    *,
    cache_root: Path,
    max_documents_per_person: int = 3,
    include_emperor_context: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    docs_path = cache_root / "source_documents.jsonl"
    if not docs_path.exists():
        raise ObjectSourceCacheError(f"missing cache source_documents.jsonl: {docs_path}")
    cache_documents = read_jsonl(docs_path)
    object_names = task_object_names(task)
    target_names = task_target_names(task) if include_emperor_context else []
    object_keys = {normalized_name(name) for name in object_names}
    target_keys = {normalized_name(name) for name in target_names}

    existing_docs = [dict(row) for row in task.get("source_documents") or task.get("documents") or [] if isinstance(row, Mapping)]
    selected_document_keys: set[tuple[str, str]] = set()
    for doc in existing_docs:
        title = normalized_name(text_from(doc, "wikisource_title", "title"))
        cache_payload = doc.get("object_source_cache") if isinstance(doc.get("object_source_cache"), Mapping) else {}
        owner = normalized_name(text_from(cache_payload, "person_name")) if cache_payload else ""
        if title:
            selected_document_keys.add((title, owner))

    selected_by_person: dict[str, int] = {}
    added_docs: list[dict[str, Any]] = []
    for row in cache_documents:
        person_name = clean_name(row.get("person_name"))
        person_key = normalized_name(person_name)
        role = clean_name(row.get("source_role"))
        if role == "emperor_context":
            matched = include_emperor_context and person_key in target_keys
        else:
            matched = person_key in object_keys
        if not matched or not cache_document_usable_for_overlay(row):
            continue
        if selected_by_person.get(person_name, 0) >= max(1, max_documents_per_person):
            continue
        title_key = normalized_name(text_from(row, "wikisource_title", "source_title", "title"))
        document_key = (title_key, person_key)
        if not title_key or document_key in selected_document_keys:
            continue
        selected_by_person[person_name] = selected_by_person.get(person_name, 0) + 1
        doc = overlay_document_row(row, object_name=person_name, index=len(added_docs) + 1)
        selected_document_keys.add(document_key)
        added_docs.append(doc)

    result = json.loads(json.dumps(dict(task), ensure_ascii=False, default=str))
    result["source_documents"] = [*existing_docs, *added_docs]
    search_plan = dict(result.get("search_plan") or {})
    search_plan["object_source_cache_overlay"] = {
        "generated_by": "scripts/dev/retrieval_v2_object_source_cache.py",
        "cache_root": str(cache_root),
        "include_emperor_context": include_emperor_context,
        "max_documents_per_person": max_documents_per_person,
        "matched_object_names": sorted(name for name in selected_by_person if name),
        "added_source_document_count": len(added_docs),
    }
    result["search_plan"] = search_plan
    notes = list(result.get("generation_notes") or [])
    notes.append("offline object source cache overlay merged source_documents before candidate slicing")
    result["generation_notes"] = unique_strings(notes)
    clean_audit = dict(result.get("clean_audit") or {})
    clean_audit["object_source_cache_overlay"] = True
    clean_audit["object_source_cache_overlay_old_source_pack_read"] = False
    clean_audit["object_source_cache_overlay_agent_invoked"] = False
    result["clean_audit"] = clean_audit
    stats = {
        "cache_root": str(cache_root),
        "input_source_document_count": len(existing_docs),
        "added_source_document_count": len(added_docs),
        "source_document_count": len(result["source_documents"]),
        "matched_object_names": sorted(name for name in selected_by_person if name),
        "agent_invocation_enabled": False,
        "write_db": False,
    }
    return result, stats


def build_cache(
    seeds: Sequence[Mapping[str, Any]],
    *,
    output_root: Path,
    cache_dir: Path,
    search_fn: SearchFn = search_wikisource,
    pages_per_query: int = 2,
    search_timeout: int = 8,
    fetch_timeout: int = 15,
    source_hint_limit: int = 2,
    max_search_names: int = 3,
    max_people: int = 0,
    context_chars: int = 220,
    max_slices_per_document: int = 8,
    include_emperor_annals: bool = True,
    skip_fetch_errors: bool = True,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    max_retry_wait_seconds: float | None = 30.0,
    cache_backend: str | None = "filesystem",
    cache_refresh: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Any]:
    started = time.perf_counter()
    output_root.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    normalized_seeds = dedupe_seeds(normalize_seed(seed, seed_source="input") for seed in seeds)
    if max_people > 0:
        normalized_seeds = normalized_seeds[:max_people]

    source_documents: list[dict[str, Any]] = []
    mention_slices: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    search_hits: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, Any]] = []
    agent_rows: list[dict[str, Any]] = []
    cache_store = None
    retry_events: list[dict[str, Any]] = []
    try:
        cache_config = load_source_excerpt_cache_config()
        api_cache, page_text_cache, cache_store, cache_report_config = make_cache_backends(
            cache_config=cache_config,
            cache_dir=cache_dir / "managed_wikisource",
            cache_enabled=True,
            cache_refresh=cache_refresh,
            cache_backend=cache_backend,
        )
        fetch_context = FetchContext(
            request_delay_seconds=request_delay_seconds,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
            retry_events=retry_events,
            user_agent=user_agent,
            api_cache=api_cache,
            page_text_cache=page_text_cache,
            max_retry_wait_seconds=max_retry_wait_seconds,
        )
    except Exception:
        api_cache = None
        page_text_cache = None
        cache_report_config = {"enabled": False, "backend": "unavailable"}
        fetch_context = None
    if search_fn is not search_wikisource:
        fetch_context = None

    try:
        for seed in normalized_seeds:
            discovered, hits = discover_source_documents(
                seed,
                search_fn=search_fn,
                pages_per_query=pages_per_query,
                timeout=search_timeout,
                source_hint_limit=source_hint_limit,
                max_search_names=max_search_names,
                include_emperor_annals=include_emperor_annals,
                fetch_context=fetch_context,
            )
            search_hits.extend(hits)
            seed_documents: list[dict[str, Any]] = []
            seed_slices: list[dict[str, Any]] = []
            for document in discovered:
                try:
                    fetched_doc, slices = fetch_and_slice_document(
                        seed,
                        document,
                        cache_dir=cache_dir,
                        timeout=fetch_timeout,
                        context_chars=context_chars,
                        max_slices_per_document=max_slices_per_document,
                        fetch_context=fetch_context,
                    )
                except Exception as exc:
                    error = {
                        "person_cache_code": person_cache_code(seed),
                        "person_name": seed_name(seed),
                        "source_title": document.get("source_title") or document.get("title"),
                        "error": repr(exc),
                    }
                    fetch_errors.append(error)
                    if not skip_fetch_errors:
                        raise
                    continue
                seed_documents.append(fetched_doc)
                seed_slices.extend(slices)
            coverage = coverage_for_seed(seed, seed_documents, seed_slices)
            bundle_path = output_root / "bundles" / f"{coverage['person_cache_code']}.json"
            coverage["agent_input_bundle_path"] = str(bundle_path) if coverage["needs_agent_review"] else ""
            bundle = {
                "schema_version": SCHEMA_VERSION,
                "person": seed,
                "source_documents": seed_documents,
                "mention_slices": seed_slices,
                "coverage": coverage,
            }
            write_json(bundle_path, bundle)
            source_documents.extend(seed_documents)
            mention_slices.extend(seed_slices)
            coverage_rows.append(coverage)
            if coverage["needs_agent_review"]:
                agent_rows.append(build_agent_review_row(seed, coverage))
    finally:
        if cache_store is not None:
            cache_store.close()

    artifacts = {
        "person_seeds": output_root / "person_seeds.jsonl",
        "source_documents": output_root / "source_documents.jsonl",
        "mention_slices": output_root / "mention_slices.jsonl",
        "person_coverage": output_root / "person_coverage.jsonl",
        "search_hits": output_root / "search_hits.jsonl",
        "fetch_errors": output_root / "fetch_errors.jsonl",
        "agent_review_queue": output_root / "agent_review_queue.jsonl",
        "pgsql_schema_draft": output_root / "pgsql_schema_draft.sql",
        "manifest": output_root / "manifest.json",
        "report": output_root / "report.md",
    }
    write_jsonl(artifacts["person_seeds"], normalized_seeds)
    write_jsonl(artifacts["source_documents"], source_documents)
    write_jsonl(artifacts["mention_slices"], mention_slices)
    write_jsonl(artifacts["person_coverage"], coverage_rows)
    write_jsonl(artifacts["search_hits"], search_hits)
    write_jsonl(artifacts["fetch_errors"], fetch_errors)
    write_jsonl(artifacts["agent_review_queue"], agent_rows)
    write_text(artifacts["pgsql_schema_draft"], PGSQL_SCHEMA_DRAFT)

    elapsed = round(time.perf_counter() - started, 3)
    manifest = {
        "generated_by": "scripts/dev/retrieval_v2_object_source_cache.py",
        "schema_version": SCHEMA_VERSION,
        "mode": "offline_no_agent",
        "write_db": False,
        "agent_invocation_enabled": False,
        "output_root": str(output_root),
        "source_cache_root": str(cache_dir),
        "artifacts": {key: str(path) for key, path in artifacts.items() if key not in {"manifest", "report"}},
        "totals": {
            "persons": len(normalized_seeds),
            "source_documents": len(source_documents),
            "mention_slices": len(mention_slices),
            "coverage_needs_agent_review": len(agent_rows),
            "search_hits": len(search_hits),
            "fetch_errors": len(fetch_errors),
            "elapsed_seconds": elapsed,
        },
        "throttle": {
            "request_delay_seconds": request_delay_seconds,
            "max_retries": max_retries,
            "retry_backoff_seconds": retry_backoff_seconds,
            "max_retry_wait_seconds": max_retry_wait_seconds,
            "retry_events": retry_events,
        },
        "managed_wikisource_cache": cache_report(
            report_config=cache_report_config,
            api_cache=api_cache,
            page_text_cache=page_text_cache,
        )
        if api_cache is not None and page_text_cache is not None
        else cache_report_config,
        "coverage_summary": {
            "with_source_document": sum(1 for row in coverage_rows if row["has_source_document"]),
            "with_biography_source": sum(1 for row in coverage_rows if row["has_biography_source"]),
            "with_emperor_context_source": sum(1 for row in coverage_rows if row["has_emperor_context_source"]),
            "with_claim_closure_risk": sum(1 for row in coverage_rows if row["claim_closure_risk"]),
        },
    }
    write_json(artifacts["manifest"], manifest)
    write_text(artifacts["report"], markdown_report(manifest, coverage_rows))
    return manifest


def local_runtime_path(path_text: str) -> Path:
    raw = str(path_text or "").strip()
    if not raw:
        return Path()
    normalized = raw.replace("\\", "/")
    prefix = "//192.168.1.37/data1/"
    if normalized.startswith(prefix):
        return Path("/data1") / normalized[len(prefix) :]
    return Path(raw)


def reslice_cache(
    *,
    input_root: Path,
    output_root: Path,
    context_chars: int = 220,
    max_slices_per_document: int = 8,
) -> dict[str, Any]:
    started = time.perf_counter()
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "bundles").mkdir(parents=True, exist_ok=True)
    seeds = [normalize_seed(row, seed_source="reslice") for row in read_jsonl(input_root / "person_seeds.jsonl")]
    seeds_by_code = {person_cache_code(seed): seed for seed in seeds}
    seeds_by_name = {seed_name(seed): seed for seed in seeds}
    source_documents = read_jsonl(input_root / "source_documents.jsonl")
    old_slices = read_jsonl(input_root / "mention_slices.jsonl") if (input_root / "mention_slices.jsonl").exists() else []
    old_slice_codes = {
        (
            text_from(row, "person_name"),
            text_from(row, "document_cache_code"),
            text_from(row, "quote_hash"),
        ): text_from(row, "slice_cache_code")
        for row in old_slices
        if text_from(row, "person_name") and text_from(row, "document_cache_code") and text_from(row, "quote_hash") and text_from(row, "slice_cache_code")
    }
    search_hits = read_jsonl(input_root / "search_hits.jsonl") if (input_root / "search_hits.jsonl").exists() else []
    source_documents_out: list[dict[str, Any]] = []
    mention_slices: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, Any]] = []
    docs_by_person: dict[str, list[dict[str, Any]]] = {}
    slices_by_person: dict[str, list[dict[str, Any]]] = {}
    for document in source_documents:
        doc = dict(document)
        person_code = text_from(doc, "person_cache_code")
        person_name = text_from(doc, "person_name")
        seed = seeds_by_code.get(person_code) or seeds_by_name.get(person_name) or normalize_seed({"name": person_name}, seed_source="reslice_document")
        raw_text_path = text_from(doc, "shared_cache_text_path")
        text_path = local_runtime_path(raw_text_path)
        full_text = ""
        if raw_text_path and text_path.exists():
            full_text = text_path.read_text(encoding="utf-8", errors="replace")
        else:
            fetch_errors.append(
                {
                    "person_cache_code": person_cache_code(seed),
                    "person_name": seed_name(seed),
                    "source_title": doc.get("source_title") or doc.get("title"),
                    "error": f"cached text not found: {text_path}",
                }
            )
        slices = build_mention_slices(
            seed,
            doc,
            full_text,
            context_chars=context_chars,
            max_slices_per_document=max_slices_per_document,
        )
        if not slices:
            slices = build_locator_backed_slice(seed, doc, full_text, context_chars=context_chars)
        for row in slices:
            stable_code = old_slice_codes.get((text_from(row, "person_name"), text_from(row, "document_cache_code"), text_from(row, "quote_hash")))
            if stable_code:
                row["slice_cache_code"] = stable_code
        doc["mention_slice_count"] = len(slices)
        doc["source_shape"] = source_shape(seed, doc, full_text, len(slices))
        source_documents_out.append(doc)
        docs_by_person.setdefault(person_cache_code(seed), []).append(doc)
        slices_by_person.setdefault(person_cache_code(seed), []).extend(slices)
        mention_slices.extend(slices)

    agent_rows: list[dict[str, Any]] = []
    for seed in seeds:
        code = person_cache_code(seed)
        seed_docs = docs_by_person.get(code, [])
        seed_slices = slices_by_person.get(code, [])
        coverage = coverage_for_seed(seed, seed_docs, seed_slices)
        bundle_path = output_root / "bundles" / f"{coverage['person_cache_code']}.json"
        coverage["agent_input_bundle_path"] = str(bundle_path) if coverage["needs_agent_review"] else ""
        write_json(
            bundle_path,
            {
                "schema_version": SCHEMA_VERSION,
                "person": seed,
                "source_documents": seed_docs,
                "mention_slices": seed_slices,
                "coverage": coverage,
            },
        )
        coverage_rows.append(coverage)
        if coverage["needs_agent_review"]:
            agent_rows.append(build_agent_review_row(seed, coverage))

    artifacts = {
        "person_seeds": output_root / "person_seeds.jsonl",
        "source_documents": output_root / "source_documents.jsonl",
        "mention_slices": output_root / "mention_slices.jsonl",
        "person_coverage": output_root / "person_coverage.jsonl",
        "search_hits": output_root / "search_hits.jsonl",
        "fetch_errors": output_root / "fetch_errors.jsonl",
        "agent_review_queue": output_root / "agent_review_queue.jsonl",
        "pgsql_schema_draft": output_root / "pgsql_schema_draft.sql",
        "manifest": output_root / "manifest.json",
        "report": output_root / "report.md",
    }
    write_jsonl(artifacts["person_seeds"], seeds)
    write_jsonl(artifacts["source_documents"], source_documents_out)
    write_jsonl(artifacts["mention_slices"], mention_slices)
    write_jsonl(artifacts["person_coverage"], coverage_rows)
    write_jsonl(artifacts["search_hits"], search_hits)
    write_jsonl(artifacts["fetch_errors"], fetch_errors)
    write_jsonl(artifacts["agent_review_queue"], agent_rows)
    write_text(artifacts["pgsql_schema_draft"], PGSQL_SCHEMA_DRAFT)
    elapsed = round(time.perf_counter() - started, 3)
    manifest = {
        "generated_by": "scripts/dev/retrieval_v2_object_source_cache.py reslice",
        "schema_version": SCHEMA_VERSION,
        "mode": "offline_reslice_existing_cache",
        "write_db": False,
        "agent_invocation_enabled": False,
        "input_root": str(input_root),
        "output_root": str(output_root),
        "artifacts": {key: str(path) for key, path in artifacts.items() if key not in {"manifest", "report"}},
        "totals": {
            "persons": len(seeds),
            "source_documents": len(source_documents_out),
            "mention_slices": len(mention_slices),
            "coverage_needs_agent_review": len(agent_rows),
            "search_hits": len(search_hits),
            "fetch_errors": len(fetch_errors),
            "elapsed_seconds": elapsed,
        },
        "coverage_summary": {
            "with_source_document": sum(1 for row in coverage_rows if row["has_source_document"]),
            "with_biography_source": sum(1 for row in coverage_rows if row["has_biography_source"]),
            "with_emperor_context_source": sum(1 for row in coverage_rows if row["has_emperor_context_source"]),
            "with_claim_closure_risk": sum(1 for row in coverage_rows if row["claim_closure_risk"]),
        },
    }
    write_json(artifacts["manifest"], manifest)
    write_text(artifacts["report"], markdown_report(manifest, coverage_rows))
    return manifest


def annotate_cache_slices(*, input_root: Path, output_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    output_root.mkdir(parents=True, exist_ok=True)
    source_documents = read_jsonl(input_root / "source_documents.jsonl")
    docs_by_code = {text_from(row, "document_cache_code"): row for row in source_documents if text_from(row, "document_cache_code")}
    page_text_by_doc: dict[str, str] = {}
    fetch_errors: list[dict[str, Any]] = []
    annotated_slices: list[dict[str, Any]] = []
    for source_slice in read_jsonl(input_root / "mention_slices.jsonl"):
        row = dict(source_slice)
        doc_code = text_from(row, "document_cache_code")
        document = docs_by_code.get(doc_code, {})
        full_text = page_text_by_doc.get(doc_code)
        if full_text is None:
            raw_path = text_from(document, "shared_cache_text_path")
            text_path = local_runtime_path(raw_path)
            if raw_path and text_path.exists():
                full_text = text_path.read_text(encoding="utf-8", errors="replace")
            else:
                full_text = ""
                fetch_errors.append(
                    {
                        "person_cache_code": text_from(row, "person_cache_code"),
                        "person_name": text_from(row, "person_name"),
                        "source_title": document.get("source_title") or document.get("title") or row.get("source_title"),
                        "error": f"cached text not found: {text_path}",
                    }
                )
            page_text_by_doc[doc_code] = full_text
        locator = text_from(row, "locator")
        match = CHAR_LOCATOR_RE.search(locator)
        anchor = int(match.group(1)) if match else 0
        if match and full_text:
            start = int(match.group(1))
            end = int(match.group(2))
            for alias in row.get("matched_aliases") or [row.get("person_name")]:
                alias_text = text_from({"alias": alias}, "alias")
                if not alias_text:
                    continue
                found = full_text.find(alias_text, start, min(end, len(full_text)))
                if found >= 0:
                    anchor = found
                    break
        row["section_heading"] = nearest_section_heading(full_text, anchor) if full_text else ""
        annotated_slices.append(row)

    for file_name in ["person_seeds.jsonl", "source_documents.jsonl", "person_coverage.jsonl", "search_hits.jsonl", "agent_review_queue.jsonl"]:
        source = input_root / file_name
        if source.exists():
            (output_root / file_name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    write_jsonl(output_root / "mention_slices.jsonl", annotated_slices)
    write_jsonl(output_root / "fetch_errors.jsonl", fetch_errors)
    write_text(output_root / "pgsql_schema_draft.sql", PGSQL_SCHEMA_DRAFT)
    coverage_rows = read_jsonl(input_root / "person_coverage.jsonl") if (input_root / "person_coverage.jsonl").exists() else []
    search_hits = read_jsonl(input_root / "search_hits.jsonl") if (input_root / "search_hits.jsonl").exists() else []
    seeds = read_jsonl(input_root / "person_seeds.jsonl") if (input_root / "person_seeds.jsonl").exists() else []
    manifest = {
        "generated_by": "scripts/dev/retrieval_v2_object_source_cache.py annotate-slices",
        "schema_version": SCHEMA_VERSION,
        "mode": "offline_annotate_existing_slices",
        "write_db": False,
        "agent_invocation_enabled": False,
        "input_root": str(input_root),
        "output_root": str(output_root),
        "artifacts": {
            "person_seeds": str(output_root / "person_seeds.jsonl"),
            "source_documents": str(output_root / "source_documents.jsonl"),
            "mention_slices": str(output_root / "mention_slices.jsonl"),
            "person_coverage": str(output_root / "person_coverage.jsonl"),
            "search_hits": str(output_root / "search_hits.jsonl"),
            "fetch_errors": str(output_root / "fetch_errors.jsonl"),
            "agent_review_queue": str(output_root / "agent_review_queue.jsonl"),
            "pgsql_schema_draft": str(output_root / "pgsql_schema_draft.sql"),
        },
        "totals": {
            "persons": len(seeds),
            "source_documents": len(source_documents),
            "mention_slices": len(annotated_slices),
            "coverage_needs_agent_review": sum(1 for row in coverage_rows if row.get("needs_agent_review")),
            "search_hits": len(search_hits),
            "fetch_errors": len(fetch_errors),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        },
        "coverage_summary": {
            "with_source_document": sum(1 for row in coverage_rows if row.get("has_source_document")),
            "with_biography_source": sum(1 for row in coverage_rows if row.get("has_biography_source")),
            "with_emperor_context_source": sum(1 for row in coverage_rows if row.get("has_emperor_context_source")),
            "with_claim_closure_risk": sum(1 for row in coverage_rows if row.get("claim_closure_risk")),
        },
    }
    write_json(output_root / "manifest.json", manifest)
    write_text(output_root / "report.md", markdown_report(manifest, coverage_rows))
    return manifest


def markdown_report(manifest: Mapping[str, Any], coverage_rows: Sequence[Mapping[str, Any]]) -> str:
    totals = manifest.get("totals") or {}
    summary = manifest.get("coverage_summary") or {}
    lines = [
        "# retrieval_v2 object source cache report",
        "",
        f"- mode: `{manifest.get('mode')}`",
        f"- write_db: `{str(manifest.get('write_db')).lower()}`",
        f"- agent_invocation_enabled: `{str(manifest.get('agent_invocation_enabled')).lower()}`",
        f"- persons: `{totals.get('persons', 0)}`",
        f"- source_documents: `{totals.get('source_documents', 0)}`",
        f"- mention_slices: `{totals.get('mention_slices', 0)}`",
        f"- coverage_needs_agent_review: `{totals.get('coverage_needs_agent_review', 0)}`",
        f"- fetch_errors: `{totals.get('fetch_errors', 0)}`",
        "",
        "## Coverage",
        "",
        f"- with_source_document: `{summary.get('with_source_document', 0)}`",
        f"- with_biography_source: `{summary.get('with_biography_source', 0)}`",
        f"- with_emperor_context_source: `{summary.get('with_emperor_context_source', 0)}`",
        f"- with_claim_closure_risk: `{summary.get('with_claim_closure_risk', 0)}`",
    ]
    risky = [row for row in coverage_rows if row.get("claim_closure_risk")]
    if risky:
        lines.extend(["", "## Agent Review Slots", "", "| person | risk | reason |", "| --- | --- | --- |"])
        for row in risky[:50]:
            lines.append(f"| {row.get('person_name')} | {row.get('claim_closure_risk')} | {row.get('agent_review_reason')} |")
    return "\n".join(lines) + "\n"


def extract_seed_rows_from_runs(run_roots: Sequence[Path]) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for root in run_roots:
        if not root.exists():
            raise ObjectSourceCacheError(f"run root does not exist: {root}")
        for path in sorted(root.rglob("task*.json")):
            try:
                payload = read_json(path)
            except Exception:
                continue
            if not isinstance(payload, Mapping):
                continue
            source_hints = []
            strategy = payload.get("source_strategy") if isinstance(payload.get("source_strategy"), Mapping) else {}
            if isinstance(strategy, Mapping):
                source_hints = list(strategy.get("source_hints") or [])
            emperor_name = text_from(payload, "emperor_name")
            if emperor_name:
                target_payload = payload.get("target_payload") if isinstance(payload.get("target_payload"), Mapping) else {}
                seeds.append(
                    normalize_seed(
                        {
                            "name": emperor_name,
                            "is_emperor": True,
                            "source_hints": source_hints,
                            "seed_sources": [f"run_target:{path.name}"],
                            "priority": 20,
                            **dict(target_payload),
                        },
                        seed_source="run_target",
                    )
                )
            for raw_seed in payload.get("object_seeds") or []:
                if not isinstance(raw_seed, Mapping):
                    continue
                row = dict(raw_seed)
                target_payload = payload.get("target_payload") if isinstance(payload.get("target_payload"), Mapping) else {}
                for key, value in target_payload.items():
                    row.setdefault(key, value)
                row.setdefault("source_hints", source_hints)
                row.setdefault("seed_sources", [])
                row["seed_sources"] = unique_strings([*row["seed_sources"], f"run_task:{path.name}"])
                row.setdefault("priority", 70)
                seeds.append(normalize_seed(row, seed_source="run_task"))
        for path in sorted(root.rglob("judge_result*.json")):
            try:
                payload = read_json(path)
            except Exception:
                continue
            if not isinstance(payload, Mapping):
                continue
            for gap in payload.get("coverage_gaps") or []:
                if not isinstance(gap, Mapping):
                    continue
                name = text_from(gap, "object_name")
                if not name:
                    continue
                seed = {
                    "name": name,
                    "seed_sources": [f"run_gap:{path.name}", text_from(gap, "gap_type")],
                    "priority": 50 if text_from(gap, "gap_type") == "object_claim_undercoverage" else 80,
                }
                seeds.append(normalize_seed(seed, seed_source="run_gap"))
    return dedupe_seeds(seeds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build retrieval_v2 object-level source cache artifacts without invoking agents.")
    parser.add_argument("--use-local-runtime", action="store_true", help="Use repo-local runtime paths for default source cache.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build offline object source cache from seed JSONL.")
    build.add_argument("--seed-jsonl", type=Path, required=True)
    build.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    build.add_argument("--cache-dir", type=Path)
    build.add_argument("--max-people", type=int, default=0)
    build.add_argument("--pages-per-query", type=int, default=2)
    build.add_argument("--source-hint-limit", type=int, default=2)
    build.add_argument("--max-search-names", type=int, default=3)
    build.add_argument("--search-timeout", type=int, default=8)
    build.add_argument("--fetch-timeout", type=int, default=15)
    build.add_argument("--context-chars", type=int, default=220)
    build.add_argument("--max-slices-per-document", type=int, default=8)
    build.add_argument("--skip-fetch-errors", action="store_true")
    build.add_argument("--exclude-emperor-annals", action="store_true")
    build.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY_SECONDS)
    build.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    build.add_argument("--retry-backoff", type=float, default=DEFAULT_RETRY_BACKOFF_SECONDS)
    build.add_argument("--max-retry-wait", type=float, default=30.0)
    build.add_argument("--cache-backend", choices=("filesystem", "postgres"), default="filesystem")
    build.add_argument("--cache-refresh", action="store_true")
    build.add_argument("--user-agent", default=DEFAULT_USER_AGENT)

    build_shards = subparsers.add_parser("build-shards", help="Build object source cache in resumable seed shards with per-shard watchdog.")
    build_shards.add_argument("--seed-jsonl", type=Path, required=True)
    build_shards.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT / "sharded")
    build_shards.add_argument("--cache-dir", type=Path)
    build_shards.add_argument("--shard-size", type=int, default=20)
    build_shards.add_argument("--shard-timeout", type=float, default=120.0)
    build_shards.add_argument("--max-shards", type=int, default=0)
    build_shards.add_argument("--rerun-completed", action="store_true")
    build_shards.add_argument("--pages-per-query", type=int, default=1)
    build_shards.add_argument("--source-hint-limit", type=int, default=1)
    build_shards.add_argument("--max-search-names", type=int, default=1)
    build_shards.add_argument("--search-timeout", type=int, default=5)
    build_shards.add_argument("--fetch-timeout", type=int, default=6)
    build_shards.add_argument("--context-chars", type=int, default=220)
    build_shards.add_argument("--max-slices-per-document", type=int, default=8)
    build_shards.add_argument("--stop-on-fetch-errors", action="store_true")
    build_shards.add_argument("--exclude-emperor-annals", action="store_true")
    build_shards.add_argument("--request-delay", type=float, default=0.05)
    build_shards.add_argument("--max-retries", type=int, default=1)
    build_shards.add_argument("--retry-backoff", type=float, default=0.2)
    build_shards.add_argument("--max-retry-wait", type=float, default=2.0)
    build_shards.add_argument("--cache-backend", choices=("filesystem", "postgres"), default="filesystem")
    build_shards.add_argument("--cache-refresh", action="store_true")
    build_shards.add_argument("--user-agent", default=DEFAULT_USER_AGENT)

    seed_db = subparsers.add_parser("seed-from-db", help="Read current retrieval_v2 person objects into seed JSONL.")
    seed_db.add_argument("--output-jsonl", type=Path, required=True)
    seed_db.add_argument("--env-file", type=Path)
    seed_db.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V2_DSN")
    seed_db.add_argument("--limit", type=int, default=0)
    seed_db.add_argument(
        "--source",
        choices=("auto", "retrieval-v2", "object-pool"),
        default="auto",
        help="Seed source table family. auto uses retrieval_v2.objects when present, otherwise raw_objs.",
    )
    seed_db.add_argument(
        "--include-object-pool-aliases",
        action="store_true",
        help="Read raw_obj_aliases/raw_objs as a read-only alias expansion layer when available.",
    )

    seed_runs = subparsers.add_parser("seed-from-runs", help="Extract person seeds from existing clean run task and judge artifacts.")
    seed_runs.add_argument("--run-root", type=Path, action="append", required=True)
    seed_runs.add_argument("--output-jsonl", type=Path, required=True)

    seed_audit = subparsers.add_parser("seed-audit", help="Audit seed JSONL readiness before offline fetching.")
    seed_audit.add_argument("--seed-jsonl", type=Path, required=True)
    seed_audit.add_argument("--output-json", type=Path)
    seed_audit.add_argument("--output-md", type=Path)
    seed_audit.add_argument("--max-issue-rows", type=int, default=100)

    review_audit = subparsers.add_parser("review-audit", help="Classify remaining agent review slots in a built object source cache.")
    review_audit.add_argument("--cache-root", type=Path, required=True)
    review_audit.add_argument("--output-json", type=Path)
    review_audit.add_argument("--output-md", type=Path)
    review_audit.add_argument("--max-docs-per-person", type=int, default=6)

    merge_rescue = subparsers.add_parser("merge-rescue", help="Merge a residual rescue cache back into a full object source cache by person_name.")
    merge_rescue.add_argument("--base-cache-root", type=Path, required=True)
    merge_rescue.add_argument("--rescue-cache-root", type=Path, required=True)
    merge_rescue.add_argument("--output-root", type=Path, required=True)

    reslice = subparsers.add_parser("reslice", help="Rebuild mention_slices from an existing object source cache without search/fetch.")
    reslice.add_argument("--input-root", type=Path, required=True)
    reslice.add_argument("--output-root", type=Path, required=True)
    reslice.add_argument("--context-chars", type=int, default=220)
    reslice.add_argument("--max-slices-per-document", type=int, default=8)

    annotate = subparsers.add_parser("annotate-slices", help="Copy an existing cache and annotate mention_slices with section headings without changing slice codes.")
    annotate.add_argument("--input-root", type=Path, required=True)
    annotate.add_argument("--output-root", type=Path, required=True)

    schema = subparsers.add_parser("schema-draft", help="Write the optional PG schema draft for this cache index.")
    schema.add_argument("--output-sql", type=Path, required=True)

    overlay = subparsers.add_parser("overlay-task", help="Merge cached object source documents into a retrieval_v2 task JSON.")
    overlay.add_argument("--task", type=Path, required=True)
    overlay.add_argument("--cache-root", type=Path, required=True)
    overlay.add_argument("--output-task", type=Path, required=True)
    overlay.add_argument("--output-report-json", type=Path)
    overlay.add_argument("--max-documents-per-person", type=int, default=3)
    overlay.add_argument("--exclude-emperor-context", action="store_true")
    return parser


def default_cache_dir(*, use_local_runtime: bool) -> Path:
    try:
        paths = load_runtime_paths(use_local=use_local_runtime)
        return default_source_cache_root(paths)
    except Exception:
        return DEFAULT_CACHE_DIR


def build_shard_cli_args(args: argparse.Namespace) -> list[str]:
    values = [
        "--pages-per-query",
        str(args.pages_per_query),
        "--source-hint-limit",
        str(args.source_hint_limit),
        "--max-search-names",
        str(args.max_search_names),
        "--search-timeout",
        str(args.search_timeout),
        "--fetch-timeout",
        str(args.fetch_timeout),
        "--context-chars",
        str(args.context_chars),
        "--max-slices-per-document",
        str(args.max_slices_per_document),
        "--request-delay",
        str(args.request_delay),
        "--max-retries",
        str(args.max_retries),
        "--retry-backoff",
        str(args.retry_backoff),
        "--max-retry-wait",
        str(args.max_retry_wait),
        "--cache-backend",
        args.cache_backend,
        "--user-agent",
        args.user_agent,
    ]
    if not args.stop_on_fetch_errors:
        values.append("--skip-fetch-errors")
    if args.exclude_emperor_annals:
        values.append("--exclude-emperor-annals")
    if args.cache_refresh:
        values.append("--cache-refresh")
    return values


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "seed-from-db":
        rows = rows_from_db(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            limit=args.limit,
            include_object_pool_aliases=args.include_object_pool_aliases,
            source=args.source,
        )
        write_jsonl(args.output_jsonl, rows)
        print(json.dumps({"ok": True, "output_jsonl": str(args.output_jsonl), "rows": len(rows)}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "seed-from-runs":
        rows = extract_seed_rows_from_runs(args.run_root)
        write_jsonl(args.output_jsonl, rows)
        print(json.dumps({"ok": True, "output_jsonl": str(args.output_jsonl), "rows": len(rows)}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "seed-audit":
        rows = read_jsonl(args.seed_jsonl)
        report = seed_audit_report(rows, max_issue_rows=args.max_issue_rows)
        if args.output_json is not None:
            write_json(args.output_json, report)
        if args.output_md is not None:
            write_text(args.output_md, render_seed_audit_markdown(report))
        print(
            json.dumps(
                {
                    "ok": True,
                    "seed_jsonl": str(args.seed_jsonl),
                    "output_json": str(args.output_json) if args.output_json is not None else "",
                    "output_md": str(args.output_md) if args.output_md is not None else "",
                    "totals": report.get("totals", {}),
                    "issue_counts": report.get("issue_counts", {}),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "review-audit":
        audit = build_review_audit(args.cache_root, max_docs_per_person=args.max_docs_per_person)
        if args.output_json is not None:
            write_json(args.output_json, audit)
        if args.output_md is not None:
            write_text(args.output_md, render_review_audit_markdown(audit))
        print(
            json.dumps(
                {
                    "ok": True,
                    "cache_root": str(args.cache_root),
                    "output_json": str(args.output_json) if args.output_json is not None else "",
                    "output_md": str(args.output_md) if args.output_md is not None else "",
                    "totals": audit.get("totals", {}),
                    "classification_counts": audit.get("classification_counts", {}),
                    "issue_tag_counts": audit.get("issue_tag_counts", {}),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "merge-rescue":
        summary = merge_rescue_cache(args.base_cache_root, args.rescue_cache_root, args.output_root)
        print(
            json.dumps(
                {
                    "ok": True,
                    "output_root": summary.get("output_root", ""),
                    "summary_json": summary.get("artifacts", {}).get("summary_json", ""),
                    "report": summary.get("artifacts", {}).get("report", ""),
                    "totals": summary.get("totals", {}),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "reslice":
        manifest = reslice_cache(
            input_root=args.input_root,
            output_root=args.output_root,
            context_chars=args.context_chars,
            max_slices_per_document=args.max_slices_per_document,
        )
        print(json.dumps({"ok": True, "manifest": manifest}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "annotate-slices":
        manifest = annotate_cache_slices(input_root=args.input_root, output_root=args.output_root)
        print(json.dumps({"ok": True, "manifest": manifest}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "build-shards":
        seeds = read_jsonl(args.seed_jsonl)
        summary = run_build_shards(
            seeds,
            output_root=args.output_root,
            cache_dir=args.cache_dir or default_cache_dir(use_local_runtime=args.use_local_runtime),
            build_cli_args=build_shard_cli_args(args),
            shard_size=args.shard_size,
            shard_timeout=args.shard_timeout,
            max_shards=args.max_shards,
            skip_completed=not args.rerun_completed,
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "output_root": summary.get("output_root", ""),
                    "summary_json": summary.get("artifacts", {}).get("summary_json", ""),
                    "report": summary.get("artifacts", {}).get("report", ""),
                    "totals": summary.get("totals", {}),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "schema-draft":
        write_text(args.output_sql, PGSQL_SCHEMA_DRAFT)
        print(json.dumps({"ok": True, "output_sql": str(args.output_sql)}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "overlay-task":
        task = read_json(args.task)
        if not isinstance(task, Mapping):
            raise ObjectSourceCacheError(f"{args.task}: expected JSON object")
        overlaid_task, stats = overlay_task_from_cache(
            task,
            cache_root=args.cache_root,
            max_documents_per_person=args.max_documents_per_person,
            include_emperor_context=not args.exclude_emperor_context,
        )
        write_json(args.output_task, overlaid_task)
        if args.output_report_json is not None:
            write_json(args.output_report_json, {"generated_by": "scripts/dev/retrieval_v2_object_source_cache.py", "stats": stats})
        print(json.dumps({"ok": True, "output_task": str(args.output_task), "stats": stats}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "build":
        seeds = read_jsonl(args.seed_jsonl)
        manifest = build_cache(
            seeds,
            output_root=args.output_root,
            cache_dir=args.cache_dir or default_cache_dir(use_local_runtime=args.use_local_runtime),
            pages_per_query=args.pages_per_query,
            search_timeout=args.search_timeout,
            fetch_timeout=args.fetch_timeout,
            source_hint_limit=args.source_hint_limit,
            max_search_names=args.max_search_names,
            max_people=args.max_people,
            context_chars=args.context_chars,
            max_slices_per_document=args.max_slices_per_document,
            include_emperor_annals=not args.exclude_emperor_annals,
            skip_fetch_errors=args.skip_fetch_errors,
            request_delay_seconds=args.request_delay,
            max_retries=args.max_retries,
            retry_backoff_seconds=args.retry_backoff,
            max_retry_wait_seconds=args.max_retry_wait,
            cache_backend=args.cache_backend,
            cache_refresh=args.cache_refresh,
            user_agent=args.user_agent,
        )
        print(json.dumps({"ok": True, "manifest": manifest}, ensure_ascii=False, sort_keys=True))
        return 0
    raise ObjectSourceCacheError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ObjectSourceCacheError, ObjectSourceCacheSeedError, RetrievalV2BootstrapError, RetrievalV2CandidateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
