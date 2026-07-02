from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .cache import FetchContext, cache_report, load_source_excerpt_cache_config, make_cache_backends
from .common import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_USER_AGENT,
    RETRY_HTTP_STATUS_CODES,
    ExcerptPoolError,
    TimeBudgetExceeded,
    compact_text,
)
from .profile import (
    build_cache_direct_page_plans,
    build_direct_page_plans,
    build_search_plans,
    iter_candidate_objects,
    limit_search_plans,
    source_title_filters,
)
from .wikisource import fetch_wikisource_plain_text, search_wikisource, wikisource_page_url


def extract_passages(
    text: str,
    terms: Iterable[str],
    *,
    context_chars: int,
    max_passages: int,
) -> list[dict[str, str]]:
    normalized = compact_text(text)
    passages: list[dict[str, str]] = []
    occupied: list[tuple[int, int]] = []

    for term in terms:
        if len(term) < 2:
            continue
        for match in re.finditer(re.escape(term), normalized):
            start = max(0, match.start() - context_chars)
            end = min(len(normalized), match.end() + context_chars)
            if any(not (end < used_start or start > used_end) for used_start, used_end in occupied):
                continue
            occupied.append((start, end))
            passages.append(
                {
                    "matched_term": term,
                    "text": normalized[start:end],
                }
            )
            if len(passages) >= max_passages:
                return passages
    return passages


def build_excerpt_pool(
    profile: dict[str, Any],
    *,
    include_adjacent: bool = False,
    max_queries: int | None = None,
    max_queries_per_object: int | None = None,
    pages_per_query: int = 2,
    context_chars: int = 220,
    max_passages_per_page: int = 2,
    timeout: int = 20,
    offline: bool = False,
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
) -> dict[str, Any]:
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

    all_plans = build_search_plans(
        profile,
        include_adjacent=include_adjacent,
        max_queries_per_object=None,
    )
    explicit_direct_page_plans = build_direct_page_plans(profile, include_adjacent=include_adjacent)
    cache_direct_page_plans, direct_page_seed_texts, direct_page_cache_report = build_cache_direct_page_plans(
        profile,
        page_text_cache if not offline else None,
        include_adjacent=include_adjacent,
        explicit_page_titles=(plan.page_title for plan in explicit_direct_page_plans),
    )
    direct_page_plans = [*explicit_direct_page_plans, *cache_direct_page_plans]
    plans, skipped_plans = limit_search_plans(
        all_plans,
        max_queries=max_queries,
        max_queries_per_object=max_queries_per_object,
    )

    objects = [
        {
            "name": candidate.raw_name,
            "layer": candidate.layer,
            "search_terms": list(candidate.search_terms),
        }
        for candidate in iter_candidate_objects(profile, include_adjacent=include_adjacent)
    ]
    report: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "person": profile.get("person"),
        "query_profile_id": profile.get("query_profile_id"),
        "offline": offline,
        "status": "offline" if offline else "complete",
        "objects": objects,
        "title_filters": list(source_title_filters(profile)),
        "errors": [],
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
        "progress": {
            "planned_direct_pages": len(direct_page_plans),
            "processed_direct_pages": 0,
            "planned_searches": len(plans),
            "processed_searches": 0,
        },
        "cache": cache_report(report_config=cache_report_config, api_cache=api_cache, page_text_cache=page_text_cache),
        "retry_events": [],
        "direct_page_cache": direct_page_cache_report,
        "direct_page_plans": [
            {
                "object_name": plan.object_name,
                "layer": plan.layer,
                "page_title": plan.page_title,
                "source_target": plan.source_target,
                "search_terms": list(plan.search_terms),
            }
            for plan in direct_page_plans
        ],
        "skipped_direct_page_plans": [],
        "search_plans": [
            {
                "object_name": plan.object_name,
                "layer": plan.layer,
                "query": plan.query,
                "search_terms": list(plan.search_terms),
            }
            for plan in plans
        ],
        "skipped_search_plans": skipped_plans,
        "excerpts": [],
    }
    if offline:
        return report

    started_at = time.monotonic()
    deadline_at = started_at + max_wall_seconds if max_wall_seconds is not None else None

    def budget_exceeded() -> bool:
        return deadline_at is not None and time.monotonic() >= deadline_at

    def skip_remaining(start_index: int, *, reason: str) -> None:
        if start_index >= len(plans):
            return
        report["status"] = "partial"
        for skipped_plan in plans[start_index:]:
            report["skipped_search_plans"].append(
                {
                    "object_name": skipped_plan.object_name,
                    "layer": skipped_plan.layer,
                    "query": skipped_plan.query,
                    "reason": reason,
                }
            )

    page_cache: dict[str, str] = {}
    excerpts: list[dict[str, Any]] = []
    title_filters = source_title_filters(profile)
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
    stop_after_current_plan = False
    stop_before_search = False
    direct_hit_objects: set[str] = set()
    try:
        for plan_index, direct_plan in enumerate(direct_page_plans):
            if budget_exceeded():
                report["status"] = "partial"
                for skipped_plan in direct_page_plans[plan_index:]:
                    report["skipped_direct_page_plans"].append(
                        {
                            "object_name": skipped_plan.object_name,
                            "layer": skipped_plan.layer,
                            "page_title": skipped_plan.page_title,
                            "reason": "max_wall_seconds",
                        }
                    )
                skip_remaining(0, reason="max_wall_seconds")
                stop_before_search = True
                break
            title = direct_plan.page_title
            if title in direct_page_seed_texts:
                page_cache[title] = direct_page_seed_texts[title]
            elif title not in page_cache:
                try:
                    page_cache[title] = fetch_wikisource_plain_text(
                        title,
                        timeout=timeout,
                        fetch_context=fetch_context,
                    )
                except TimeBudgetExceeded as exc:
                    report["errors"].append(
                        {
                            "stage": "direct_page",
                            "page_title": title,
                            "object_name": direct_plan.object_name,
                            "error": repr(exc),
                        }
                    )
                    report["status"] = "partial"
                    skip_remaining(0, reason="max_wall_seconds")
                    stop_before_search = True
                    break
                except Exception as exc:  # pragma: no cover - exercised by live network only.
                    report["errors"].append(
                        {
                            "stage": "direct_page",
                            "page_title": title,
                            "object_name": direct_plan.object_name,
                            "error": repr(exc),
                        }
                    )
                    continue
            report["progress"]["processed_direct_pages"] += 1
            passages = extract_passages(
                page_cache[title],
                direct_plan.search_terms,
                context_chars=context_chars,
                max_passages=max_passages_per_page,
            )
            if not passages:
                continue
            direct_hit_objects.add(direct_plan.object_name)
            excerpts.append(
                {
                    "object_name": direct_plan.object_name,
                    "layer": direct_plan.layer,
                    "query": f"direct_page:{title}",
                    "page_title": title,
                    "page_url": wikisource_page_url(title),
                    "search_snippet": "",
                    "passages": passages,
                    "source": "direct_page",
                    "source_target": direct_plan.source_target,
                }
            )
        if stop_before_search:
            plans = []
        for plan_index, plan in enumerate(plans):
            if plan.object_name in direct_hit_objects:
                report["skipped_search_plans"].append(
                    {
                        "object_name": plan.object_name,
                        "layer": plan.layer,
                        "query": plan.query,
                        "reason": "direct_page_hit",
                    }
                )
                continue
            if budget_exceeded():
                skip_remaining(plan_index, reason="max_wall_seconds")
                break
            try:
                pages = search_wikisource(
                    plan.query,
                    limit=pages_per_query,
                    timeout=timeout,
                    title_filters=title_filters,
                    fetch_context=fetch_context,
                )
            except TimeBudgetExceeded as exc:
                report["errors"].append({"stage": "search", "query": plan.query, "error": repr(exc)})
                skip_remaining(plan_index, reason="max_wall_seconds")
                break
            except Exception as exc:  # pragma: no cover - exercised by live network only.
                report["errors"].append({"stage": "search", "query": plan.query, "error": repr(exc)})
                consecutive_errors += 1
                if max_consecutive_errors is not None and consecutive_errors >= max_consecutive_errors:
                    skip_remaining(plan_index + 1, reason="max_consecutive_errors")
                    break
                continue
            consecutive_errors = 0
            report["progress"]["processed_searches"] += 1
            for page in pages:
                if budget_exceeded():
                    stop_after_current_plan = True
                    skip_remaining(plan_index + 1, reason="max_wall_seconds")
                    break
                title = page["title"]
                if title not in page_cache:
                    try:
                        page_cache[title] = fetch_wikisource_plain_text(
                            title,
                            timeout=timeout,
                            fetch_context=fetch_context,
                        )
                    except TimeBudgetExceeded as exc:
                        report["errors"].append(
                            {
                                "stage": "fetch_page",
                                "query": plan.query,
                                "page_title": title,
                                "error": repr(exc),
                            }
                        )
                        stop_after_current_plan = True
                        skip_remaining(plan_index + 1, reason="max_wall_seconds")
                        break
                    except Exception as exc:  # pragma: no cover - exercised by live network only.
                        report["errors"].append(
                            {
                                "stage": "fetch_page",
                                "query": plan.query,
                                "page_title": title,
                                "error": repr(exc),
                            }
                        )
                        consecutive_errors += 1
                        if max_consecutive_errors is not None and consecutive_errors >= max_consecutive_errors:
                            stop_after_current_plan = True
                            skip_remaining(plan_index + 1, reason="max_consecutive_errors")
                            break
                        continue
                consecutive_errors = 0
                passages = extract_passages(
                    page_cache[title],
                    plan.search_terms,
                    context_chars=context_chars,
                    max_passages=max_passages_per_page,
                )
                if not passages and page["snippet"]:
                    passages = [{"matched_term": "search_snippet", "text": page["snippet"]}]
                if not passages:
                    continue
                excerpts.append(
                    {
                        "object_name": plan.object_name,
                        "layer": plan.layer,
                        "query": plan.query,
                        "page_title": title,
                        "page_url": page["url"],
                        "search_snippet": page["snippet"],
                        "passages": passages,
                    }
                )
            if stop_after_current_plan:
                break
    finally:
        if cache_store is not None:
            cache_store.close()

    report["excerpts"] = excerpts
    report["cache"] = cache_report(report_config=cache_report_config, api_cache=api_cache, page_text_cache=page_text_cache)
    report["progress"]["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
    return report


def migrate_filesystem_cache_to_cache(
    source_dir: Path,
    *,
    api_cache: Any,
    page_text_cache: Any,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "source_dir": str(source_dir),
        "api": {"scanned": 0, "imported": 0, "errors": []},
        "page_text": {"scanned": 0, "imported": 0, "errors": []},
    }
    api_root = source_dir / "api"
    if api_root.exists():
        for path in sorted(api_root.glob("*/*.json")):
            report["api"]["scanned"] += 1
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(envelope, dict):
                    raise ExcerptPoolError("cache envelope is not an object")
                payload = envelope.get("payload")
                if not isinstance(payload, dict):
                    raise ExcerptPoolError("cache payload is not an object")
                stage = str(envelope.get("stage") or path.parent.name)
                label = str(envelope.get("label") or "")
                url = str(envelope.get("url") or "")
                if not url:
                    raise ExcerptPoolError("cache envelope url is empty")
                before = api_cache.writes
                api_cache.write(stage=stage, label=label, url=url, payload=payload)
                if api_cache.writes > before:
                    report["api"]["imported"] += 1
            except Exception as exc:
                report["api"]["errors"].append({"path": str(path), "error": repr(exc)})

    page_root = source_dir / "pages"
    if page_root.exists():
        for meta_path in sorted(page_root.glob("*.json")):
            report["page_text"]["scanned"] += 1
            try:
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                if not isinstance(metadata, dict):
                    raise ExcerptPoolError("page cache metadata is not an object")
                title = str(metadata.get("title") or "")
                page_url = str(metadata.get("page_url") or "")
                text_name = str(metadata.get("text_path") or meta_path.with_suffix(".txt").name)
                text_path = page_root / text_name
                if not title:
                    raise ExcerptPoolError("page cache title is empty")
                if not text_path.exists():
                    raise ExcerptPoolError(f"page cache text missing: {text_path.name}")
                before = page_text_cache.writes
                page_text_cache.write(title=title, page_url=page_url, text=text_path.read_text(encoding="utf-8"))
                if page_text_cache.writes > before:
                    report["page_text"]["imported"] += 1
            except Exception as exc:
                report["page_text"]["errors"].append({"path": str(meta_path), "error": repr(exc)})
    return report


def migrate_configured_cache_to_postgres(
    *,
    cache_dir: Path | None = None,
    cache_backend: str | None = None,
    cache_dsn_env: str | None = None,
    cache_schema: str | None = None,
) -> dict[str, Any]:
    cache_config = load_source_excerpt_cache_config()
    backend = cache_backend or str(cache_config.get("backend") or DEFAULT_CACHE_BACKEND)
    if backend != "postgres":
        raise ExcerptPoolError("cache migration target backend must be postgres")
    api_cache, page_text_cache, store, report_config = make_cache_backends(
        cache_config=cache_config,
        cache_dir=cache_dir,
        cache_enabled=True,
        cache_refresh=False,
        cache_backend="postgres",
        cache_dsn_env=cache_dsn_env,
        cache_schema=cache_schema,
    )
    source_dir = cache_dir or cache_config.get("directory")
    if source_dir is None:
        raise ExcerptPoolError("cache migration requires --cache-dir after filesystem cache directory config removal")
    try:
        migration = migrate_filesystem_cache_to_cache(
            source_dir,
            api_cache=api_cache,
            page_text_cache=page_text_cache,
        )
    finally:
        if store is not None:
            store.close()
    return {
        "cache": cache_report(report_config=report_config, api_cache=api_cache, page_text_cache=page_text_cache),
        "migration": migration,
    }
