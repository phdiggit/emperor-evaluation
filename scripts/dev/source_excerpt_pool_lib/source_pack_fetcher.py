from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .builder import extract_passages
from .cache import FetchContext, cache_report, load_source_excerpt_cache_config, make_cache_backends
from .common import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_USER_AGENT,
    DEFAULT_WORKFLOW_CODE,
    KNOWN_SOURCE_TITLE_VARIANTS,
    RETRY_HTTP_STATUS_CODES,
    ExcerptPoolError,
    TimeBudgetExceeded,
    normalize_workflow_code,
)
from .profile import (
    build_direct_page_plans,
    build_search_plans,
    iter_candidate_objects,
    limit_search_plans,
    source_title_filters,
)
from .source_pack import (
    SOURCE_PACK_DOCS,
    SOURCE_PACK_EXCERPTS,
    SOURCE_PACK_MANIFEST,
    SOURCE_PACK_SCHEMA_VERSION,
    source_key_from_page_title,
    split_page_title,
)
from .wikisource import fetch_wikisource_plain_text, search_wikisource, wikisource_page_url


EXTRA_SOURCE_BIBLIO = {
    "史记": ("司马迁", "西汉"),
    "汉书": ("班固", "东汉"),
    "后汉书": ("范晔", "南朝宋"),
    "旧唐书": ("刘昫等", "后晋"),
    "新唐书": ("欧阳修、宋祁等", "北宋"),
    "宋史": ("脱脱等", "元"),
    "明史": ("张廷玉等", "清"),
    "清史稿": ("赵尔巽等", "民国"),
    "资治通鉴": ("司马光", "北宋"),
    "唐会要": ("王溥", "北宋"),
    "册府元龟": ("王钦若等", "北宋"),
}


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _atomic_write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    _atomic_write_text(path, "\n".join(lines).rstrip() + ("\n" if lines else ""))


def _canonical_source_title(title: str) -> str:
    cleaned = re.sub(r"\s*\(.*?\)\s*$", "", title.strip())
    for simplified, variants in KNOWN_SOURCE_TITLE_VARIANTS.items():
        if cleaned == simplified or cleaned in variants:
            return simplified
    return cleaned


def _source_biblio(title: str) -> tuple[str, str]:
    canonical = _canonical_source_title(title)
    return EXTRA_SOURCE_BIBLIO.get(canonical, ("", ""))


def _safe_page_name(src_key: str) -> str:
    return f"{src_key}.txt"


def _default_pack_id(profile: dict[str, Any], *, workflow_code: str = DEFAULT_WORKFLOW_CODE) -> str:
    person = str(profile.get("person") or "unknown")
    query_profile_id = str(profile.get("query_profile_id") or "no-profile")
    stamp = datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
    return f"{normalize_workflow_code(workflow_code)}-SOURCE-PACK-{query_profile_id}-{person}-{stamp}"


def _is_broad_page(title: str) -> bool:
    return "全覽" in title or "全览" in title


def _add_page_hit(
    page_hits: dict[str, dict[str, Any]],
    *,
    title: str,
    url: str,
    source: str,
    object_name: str,
    layer: str,
    query: str,
    search_terms: Iterable[str],
    snippet: str = "",
) -> None:
    if _is_broad_page(title):
        return
    hit = page_hits.setdefault(
        title,
        {
            "page_title": title,
            "page_url": url or wikisource_page_url(title),
            "matches": [],
        },
    )
    match = {
        "source": source,
        "object_name": object_name,
        "layer": layer,
        "query": query,
        "search_terms": list(search_terms),
        "snippet": snippet,
    }
    if match not in hit["matches"]:
        hit["matches"].append(match)


def _build_source_doc_row(page_title: str, text_path: Path, *, hit: dict[str, Any]) -> dict[str, Any]:
    title, volume = split_page_title(page_title)
    canonical_title = _canonical_source_title(title)
    author, dynasty = _source_biblio(canonical_title)
    src_key = source_key_from_page_title(page_title)
    object_names = sorted({match["object_name"] for match in hit["matches"] if match.get("object_name")})
    queries = sorted({match["query"] for match in hit["matches"] if match.get("query")})
    return {
        "src_key": src_key,
        "page_title": page_title,
        "title": canonical_title,
        "author": author,
        "dynasty": dynasty,
        "volume": volume,
        "locator": page_title,
        "url": hit.get("page_url") or wikisource_page_url(page_title),
        "text_path": str(text_path.as_posix()),
        "fetch_status": "fetched",
        "review_status": "pending",
        "object_names": object_names,
        "queries": queries,
        "note": "离线抓包自动生成；需人工回源裁量后再进入对象池。",
    }


def build_source_pack(
    profile: dict[str, Any],
    *,
    output_dir: Path,
    pack_id: str | None = None,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
    source_scope: str | None = None,
    generated_by: str = "scripts/dev/source_excerpt_pool_lib/source_pack_fetcher.py",
    extraction_method: str = "source_pack_fetcher",
    include_adjacent: bool = False,
    max_queries: int | None = None,
    max_queries_per_object: int | None = None,
    pages_per_query: int = 3,
    context_chars: int = 220,
    max_passages_per_page: int = 2,
    timeout: int = 20,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    max_retry_wait_seconds: float | None = None,
    max_wall_seconds: float | None = None,
    max_consecutive_errors: int | None = None,
    cache_only: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
    cache_dir: Path | None = None,
    cache_enabled: bool | None = None,
    cache_refresh: bool = False,
    cache_backend: str | None = None,
    cache_dsn_env: str | None = None,
    cache_schema: str | None = None,
    refresh_pack_pages: bool = False,
    progress_path: Path | None = None,
) -> dict[str, Any]:
    if pages_per_query <= 0:
        raise ExcerptPoolError("pages_per_query must be > 0")
    if request_delay_seconds < 0:
        raise ExcerptPoolError("request_delay_seconds must be >= 0")
    if max_retries < 0:
        raise ExcerptPoolError("max_retries must be >= 0")
    if retry_backoff_seconds < 0:
        raise ExcerptPoolError("retry_backoff_seconds must be >= 0")
    if max_retry_wait_seconds is not None and max_retry_wait_seconds < 0:
        raise ExcerptPoolError("max_retry_wait_seconds must be >= 0")
    if max_wall_seconds is not None and max_wall_seconds < 0:
        raise ExcerptPoolError("max_wall_seconds must be >= 0")
    if max_consecutive_errors is not None and max_consecutive_errors <= 0:
        raise ExcerptPoolError("max_consecutive_errors must be > 0")

    person = str(profile.get("person") or "").strip()
    if not person:
        raise ExcerptPoolError("profile.person: expected non-empty string")

    output_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = output_dir / "pages"
    workflow_code = normalize_workflow_code(workflow_code)
    pack_id = pack_id or _default_pack_id(profile, workflow_code=workflow_code)
    source_scope = source_scope or f"{workflow_code} offline source pack for {person}"
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    def progress(event: str, **payload: Any) -> None:
        if progress_path is None:
            return
        row = {
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "event": event,
            **payload,
        }
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with progress_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    cache_config = load_source_excerpt_cache_config()
    api_cache, page_text_cache, cache_store, cache_report_config = make_cache_backends(
        cache_config=cache_config,
        cache_dir=cache_dir,
        cache_enabled=cache_enabled,
        cache_refresh=cache_refresh,
        cache_backend=cache_backend,
        cache_dsn_env=cache_dsn_env,
        cache_schema=cache_schema,
    )
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "started_at": generated_at,
        "pack_id": pack_id,
        "pack_path": str(output_dir),
        "workflow_code": workflow_code,
        "person": person,
        "query_profile_id": profile.get("query_profile_id"),
        "status": "complete",
        "errors": [],
        "retry_events": [],
        "query_limits": {
            "max_queries": max_queries,
            "max_queries_per_object": max_queries_per_object,
        },
        "throttle": {
            "request_delay_seconds": request_delay_seconds,
            "max_retries": max_retries,
            "retry_backoff_seconds": retry_backoff_seconds,
            "max_retry_wait_seconds": max_retry_wait_seconds,
            "retry_http_status_codes": sorted(RETRY_HTTP_STATUS_CODES),
            "user_agent": user_agent,
        },
        "execution_budget": {
            "max_wall_seconds": max_wall_seconds,
            "max_consecutive_errors": max_consecutive_errors,
            "cache_only": cache_only,
        },
    }

    started_at = time.monotonic()
    deadline_at = started_at + max_wall_seconds if max_wall_seconds is not None else None

    def budget_exceeded() -> bool:
        return deadline_at is not None and time.monotonic() >= deadline_at

    title_filters = source_title_filters(profile)
    candidates = iter_candidate_objects(profile, include_adjacent=include_adjacent)
    direct_page_plans = build_direct_page_plans(profile, include_adjacent=include_adjacent)
    all_search_plans = build_search_plans(profile, include_adjacent=include_adjacent, max_queries_per_object=None)
    search_plans, skipped_search_plans = limit_search_plans(
        all_search_plans,
        max_queries=max_queries,
        max_queries_per_object=max_queries_per_object,
    )
    page_hits: dict[str, dict[str, Any]] = {}
    for plan in direct_page_plans:
        _add_page_hit(
            page_hits,
            title=plan.page_title,
            url=wikisource_page_url(plan.page_title),
            source="direct_page",
            object_name=plan.object_name,
            layer=plan.layer,
            query=f"direct_page:{plan.page_title}",
            search_terms=plan.search_terms,
        )

    fetch_context = FetchContext(
        request_delay_seconds=request_delay_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        retry_events=report["retry_events"],
        user_agent=user_agent,
        api_cache=api_cache,
        page_text_cache=page_text_cache,
        max_retry_wait_seconds=max_retry_wait_seconds,
        cache_only=cache_only,
        deadline_at=deadline_at,
    )
    consecutive_errors = 0
    processed_searches = 0
    progress(
        "start",
        person=person,
        query_profile_id=profile.get("query_profile_id"),
        direct_page_plans=len(direct_page_plans),
        candidate_search_plans=len(all_search_plans),
        search_plans=len(search_plans),
        skipped_search_plans=len(skipped_search_plans),
    )
    try:
        for plan_index, plan in enumerate(search_plans):
            if budget_exceeded():
                report["status"] = "partial"
                for skipped in search_plans[plan_index:]:
                    skipped_search_plans.append(
                        {
                            "object_name": skipped.object_name,
                            "layer": skipped.layer,
                            "query": skipped.query,
                            "reason": "max_wall_seconds",
                        }
                )
                break
            try:
                progress(
                    "search_start",
                    index=plan_index + 1,
                    total=len(search_plans),
                    object_name=plan.object_name,
                    query=plan.query,
                )
                pages = search_wikisource(
                    plan.query,
                    limit=pages_per_query,
                    timeout=timeout,
                    title_filters=title_filters,
                    fetch_context=fetch_context,
                )
            except TimeBudgetExceeded as exc:
                report["status"] = "partial"
                report["errors"].append({"stage": "search", "query": plan.query, "error": repr(exc)})
                progress("search_error", query=plan.query, error=repr(exc))
                break
            except Exception as exc:  # pragma: no cover - live network path.
                report["errors"].append({"stage": "search", "query": plan.query, "error": repr(exc)})
                progress("search_error", query=plan.query, error=repr(exc))
                consecutive_errors += 1
                if max_consecutive_errors is not None and consecutive_errors >= max_consecutive_errors:
                    report["status"] = "partial"
                    for skipped in search_plans[plan_index + 1 :]:
                        skipped_search_plans.append(
                            {
                                "object_name": skipped.object_name,
                                "layer": skipped.layer,
                                "query": skipped.query,
                                "reason": "max_consecutive_errors",
                            }
                        )
                    break
                continue
            consecutive_errors = 0
            processed_searches += 1
            progress("search_done", query=plan.query, page_count=len(pages), unique_pages=len(page_hits))
            for page in pages:
                _add_page_hit(
                    page_hits,
                    title=page["title"],
                    url=page["url"],
                    source="search",
                    object_name=plan.object_name,
                    layer=plan.layer,
                    query=plan.query,
                    search_terms=plan.search_terms,
                    snippet=page.get("snippet", ""),
                )

        src_doc_rows: list[dict[str, Any]] = []
        excerpt_rows: list[dict[str, Any]] = []
        fetched_pages = 0
        reused_pack_pages = 0
        for page_title, hit in sorted(page_hits.items()):
            src_key = source_key_from_page_title(page_title)
            relative_text_path = Path("pages") / _safe_page_name(src_key)
            text_path = output_dir / relative_text_path
            try:
                if text_path.exists() and not refresh_pack_pages:
                    text = text_path.read_text(encoding="utf-8")
                    reused_pack_pages += 1
                    progress("fetch_reuse", page_title=page_title, src_key=src_key)
                else:
                    if budget_exceeded():
                        report["status"] = "partial"
                        report["errors"].append({"stage": "fetch_page", "page_title": page_title, "error": "max_wall_seconds"})
                        progress("fetch_skip", page_title=page_title, src_key=src_key, reason="max_wall_seconds")
                        continue
                    progress("fetch_start", page_title=page_title, src_key=src_key)
                    text = fetch_wikisource_plain_text(page_title, timeout=timeout, fetch_context=fetch_context)
                    _atomic_write_text(text_path, text)
                    fetched_pages += 1
                    progress("fetch_done", page_title=page_title, src_key=src_key, chars=len(text))
            except TimeBudgetExceeded as exc:
                report["status"] = "partial"
                report["errors"].append({"stage": "fetch_page", "page_title": page_title, "error": repr(exc)})
                progress("fetch_error", page_title=page_title, src_key=src_key, error=repr(exc))
                continue
            except Exception as exc:  # pragma: no cover - live network path.
                report["errors"].append({"stage": "fetch_page", "page_title": page_title, "error": repr(exc)})
                progress("fetch_error", page_title=page_title, src_key=src_key, error=repr(exc))
                continue
            if not text.strip():
                report["errors"].append({"stage": "fetch_page", "page_title": page_title, "error": "empty page text"})
                progress("fetch_error", page_title=page_title, src_key=src_key, error="empty page text")
                continue
            src_doc_rows.append(_build_source_doc_row(page_title, relative_text_path, hit=hit))

            for match_index, match in enumerate(hit["matches"], start=1):
                passages = extract_passages(
                    text,
                    match.get("search_terms", []),
                    context_chars=context_chars,
                    max_passages=max_passages_per_page,
                )
                if not passages and match.get("snippet"):
                    passages = [{"matched_term": "search_snippet", "text": match["snippet"]}]
                for passage_index, passage in enumerate(passages, start=1):
                    excerpt_rows.append(
                        {
                            "excerpt_id": f"{src_key}-M{match_index:03d}-P{passage_index:02d}",
                            "src_key": src_key,
                            "page_title": page_title,
                            "page_url": hit.get("page_url") or wikisource_page_url(page_title),
                            "object_name": match.get("object_name", ""),
                            "layer": match.get("layer", ""),
                            "query": match.get("query", ""),
                            "matched_term": passage.get("matched_term", ""),
                            "quote": passage.get("text", ""),
                            "review_status": "pending",
                            "extraction_method": extraction_method,
                        }
                    )

        manifest = {
            "schema_version": SOURCE_PACK_SCHEMA_VERSION,
            "pack_id": pack_id,
            "created_at": generated_at,
            "workflow_code": workflow_code,
            "source_scope": source_scope,
            "status": report["status"],
            "person": person,
            "query_profile_id": profile.get("query_profile_id"),
            "profile_batch_id": profile.get("batch_id"),
            "generated_by": generated_by,
            "files": {
                "src_docs": SOURCE_PACK_DOCS,
                "excerpts": SOURCE_PACK_EXCERPTS,
                "pages_dir": "pages",
                "fetch_report": "fetch_report.json",
            },
        }
        _atomic_write_json(output_dir / SOURCE_PACK_MANIFEST, manifest)
        _atomic_write_jsonl(output_dir / SOURCE_PACK_DOCS, src_doc_rows)
        _atomic_write_jsonl(output_dir / SOURCE_PACK_EXCERPTS, excerpt_rows)

        candidate_names = {candidate.raw_name for candidate in candidates}
        page_hit_objects = {
            match.get("object_name", "")
            for hit in page_hits.values()
            for match in hit["matches"]
            if match.get("object_name")
        }
        excerpt_objects = {row["object_name"] for row in excerpt_rows if row.get("object_name")}
        report.update(
            {
                "direct_page_plans": len(direct_page_plans),
                "candidate_search_plans": len(all_search_plans),
                "active_search_plans": len(search_plans),
                "planned_searches": len(search_plans),
                "processed_searches": processed_searches,
                "skipped_search_plan_count": len(skipped_search_plans),
                "skipped_search_plans": skipped_search_plans,
                "planned_pages": len(page_hits),
                "written_pages": len(src_doc_rows),
                "fetched_pages": fetched_pages,
                "reused_pack_pages": reused_pack_pages,
                "excerpts": len(excerpt_rows),
                "object_coverage": {
                    "candidate_count": len(candidate_names),
                    "page_hit_count": len(page_hit_objects),
                    "excerpt_count": len(excerpt_objects),
                    "objects_without_page_hits": sorted(candidate_names - page_hit_objects),
                    "objects_without_excerpts": sorted(candidate_names - excerpt_objects),
                },
            }
        )
    finally:
        if cache_store is not None:
            cache_store.close()

    report["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    report["cache"] = cache_report(report_config=cache_report_config, api_cache=api_cache, page_text_cache=page_text_cache)
    report["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
    _atomic_write_json(output_dir / "fetch_report.json", report)
    progress(
        "complete",
        status=report["status"],
        written_pages=report.get("written_pages", 0),
        excerpts=report.get("excerpts", 0),
        errors=len(report.get("errors", [])),
    )
    return report
