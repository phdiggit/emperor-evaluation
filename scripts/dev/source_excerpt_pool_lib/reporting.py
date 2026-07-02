from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report.get('person', '')} source excerpt pool",
        "",
        f"- query_profile_id: `{report.get('query_profile_id', '')}`",
        f"- offline: `{report.get('offline')}`",
        f"- status: `{report.get('status', '')}`",
        f"- objects: `{len(report.get('objects', []))}`",
        f"- excerpts: `{len(report.get('excerpts', []))}`",
        "",
        "## Objects",
        "",
    ]
    for obj in report.get("objects", []):
        terms = ", ".join(f"`{term}`" for term in obj.get("search_terms", []))
        lines.append(f"- `{obj.get('name')}` ({obj.get('layer')}): {terms}")

    direct_plans = report.get("direct_page_plans", [])
    if direct_plans:
        lines.extend(["", "## Direct Page Plans", ""])
        for plan in direct_plans:
            source_target = plan.get("source_target")
            suffix = f" ({source_target})" if source_target else ""
            lines.append(f"- `{plan.get('object_name')}`: {plan.get('page_title')}{suffix}")

    lines.extend(["", "## Search Plans", ""])
    for plan in report.get("search_plans", []):
        lines.append(f"- `{plan.get('object_name')}`: {plan.get('query')}")

    progress = report.get("progress", {})
    if progress:
        lines.extend(["", "## Progress", ""])
        if "planned_direct_pages" in progress:
            lines.append(f"- planned_direct_pages: `{progress.get('planned_direct_pages')}`")
        if "processed_direct_pages" in progress:
            lines.append(f"- processed_direct_pages: `{progress.get('processed_direct_pages')}`")
        lines.append(f"- planned_searches: `{progress.get('planned_searches')}`")
        lines.append(f"- processed_searches: `{progress.get('processed_searches')}`")
        if "elapsed_seconds" in progress:
            lines.append(f"- elapsed_seconds: `{progress.get('elapsed_seconds')}`")

    direct_page_cache = report.get("direct_page_cache", {})
    if direct_page_cache and direct_page_cache.get("enabled"):
        lines.extend(["", "## Direct Page Cache", ""])
        lines.append(f"- considered_pages: `{direct_page_cache.get('considered_pages')}`")
        lines.append(f"- excluded_broad_pages: `{direct_page_cache.get('excluded_broad_pages')}`")
        lines.append(f"- excluded_auxiliary_pages: `{direct_page_cache.get('excluded_auxiliary_pages')}`")
        lines.append(f"- source_matched_pages: `{direct_page_cache.get('source_matched_pages')}`")
        lines.append(f"- matched_plans: `{direct_page_cache.get('matched_plans')}`")

    budget = report.get("execution_budget", {})
    if budget:
        lines.extend(["", "## Execution Budget", ""])
        lines.append(f"- max_wall_seconds: `{budget.get('max_wall_seconds')}`")
        lines.append(f"- max_consecutive_errors: `{budget.get('max_consecutive_errors')}`")
        lines.append(f"- cache_only: `{budget.get('cache_only')}`")

    skipped_direct = report.get("skipped_direct_page_plans", [])
    if skipped_direct:
        lines.extend(["", "## Skipped Direct Page Plans", ""])
        for item in skipped_direct:
            lines.append(f"- `{item.get('object_name')}`: {item.get('page_title')} ({item.get('reason')})")

    skipped = report.get("skipped_search_plans", [])
    if skipped:
        lines.extend(["", "## Skipped Search Plans", ""])
        for item in skipped:
            lines.append(f"- `{item.get('object_name')}`: {item.get('query')} ({item.get('reason')})")

    retry_events = report.get("retry_events", [])
    if retry_events:
        lines.extend(["", "## Retry Events", ""])
        for event in retry_events:
            lines.append(
                f"- `{event.get('stage')}` `{event.get('label')}`: "
                f"attempt {event.get('attempt')}, wait {event.get('wait_seconds')}s"
            )

    cache = report.get("cache", {})
    if cache:
        lines.extend(["", "## Cache", ""])
        lines.append(f"- enabled: `{cache.get('enabled')}`")
        lines.append(f"- backend: `{cache.get('backend')}`")
        if cache.get("directory") or cache.get("cache_dir"):
            lines.append(f"- directory: `{cache.get('directory') or cache.get('cache_dir')}`")
        if cache.get("dsn_env"):
            lines.append(f"- dsn_env: `{cache.get('dsn_env')}`")
        if cache.get("schema"):
            lines.append(f"- schema: `{cache.get('schema')}`")
        lines.append(f"- refresh: `{cache.get('refresh')}`")
        for cache_name in ("api", "page_text"):
            cache_summary = cache.get(cache_name, {})
            if cache_summary:
                lines.append(
                    f"- {cache_name}: hits `{cache_summary.get('hits')}`, "
                    f"misses `{cache_summary.get('misses')}`, writes `{cache_summary.get('writes')}`"
                )
                cache_errors = cache_summary.get("errors", [])
                if cache_errors:
                    lines.append(f"- {cache_name}_errors: `{len(cache_errors)}`")

    errors = report.get("errors", [])
    if errors:
        lines.extend(["", "## Errors", ""])
        for item in errors:
            label = item.get("query") or item.get("page_title") or item.get("stage")
            lines.append(f"- `{item.get('stage')}` `{label}`: {item.get('error')}")

    lines.extend(["", "## Excerpts", ""])
    for item in report.get("excerpts", []):
        lines.append(f"### {item.get('object_name')} / {item.get('page_title')}")
        lines.append("")
        lines.append(f"- layer: `{item.get('layer')}`")
        lines.append(f"- query: `{item.get('query')}`")
        lines.append(f"- page: {item.get('page_url')}")
        for passage in item.get("passages", []):
            lines.append("")
            lines.append(f"> [{passage.get('matched_term')}] {passage.get('text')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_markdown(report), encoding="utf-8")
        return
    raise ExcerptPoolError(f"unknown output format: {output_format}")
