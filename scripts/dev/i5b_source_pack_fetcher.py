from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_MAX_RETRIES,
    DEFAULT_PROFILE,
    DEFAULT_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_USER_AGENT,
    DEFAULT_WORKFLOW_CODE,
    load_source_excerpt_pool_runtime,
    normalize_workflow_code,
    workflow_slug,
)
from scripts.dev.source_excerpt_pool_lib.profile import load_profile  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.source_pack_fetcher import build_source_pack  # noqa: E402


DEFAULT_GENERATED_BY = "scripts/dev/i5b_source_pack_fetcher.py"
DEFAULT_EXTRACTION_METHOD = "i5b_source_pack_fetcher"


def _default_output_dir(person: str, *, workflow_code: str = DEFAULT_WORKFLOW_CODE) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    prefix = workflow_slug(workflow_code)
    return ROOT / ".tmp" / "source-packs" / f"{prefix}_source_pack_{stamp}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch an offline I5B source pack from a query profile.")
    parser.add_argument("--profile", type=Path, default=None, help="Query-profile JSONL path.")
    parser.add_argument("--person", required=True, help="Profile person name.")
    parser.add_argument("--output-dir", type=Path, help="Output source pack directory; defaults under .tmp/source-packs/.")
    parser.add_argument("--pack-id", help="Stable source pack id; default includes query_profile_id, person, and timestamp.")
    parser.add_argument(
        "--workflow-code",
        default=DEFAULT_WORKFLOW_CODE,
        help="Stable workflow/subitem code for source-pack metadata; defaults to I5B.",
    )
    parser.add_argument(
        "--source-scope",
        default=None,
        help="Human-readable source scope for manifest.json; default is '<workflow-code> offline source pack for <person>'.",
    )
    parser.add_argument("--include-adjacent", action="store_true", help="Include adjacent_split_objects.")
    parser.add_argument("--max-queries", type=int, default=None, help="Global maximum query count.")
    parser.add_argument(
        "--max-queries-per-object",
        type=int,
        default=4,
        help="Maximum queries per object; default keeps every object but caps redundant fallback plans.",
    )
    parser.add_argument("--pages-per-query", type=int, default=3, help="Wikisource pages to keep per query.")
    parser.add_argument("--context-chars", type=int, default=220, help="Characters before/after each excerpt hit.")
    parser.add_argument("--max-passages-per-page", type=int, default=2, help="Passages to keep per page/object match.")
    parser.add_argument("--timeout", type=int, default=20, help="Network timeout in seconds.")
    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SECONDS,
        help="Minimum seconds between Wikisource API request starts.",
    )
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Retries for HTTP 429/5xx or URL errors.")
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=DEFAULT_RETRY_BACKOFF_SECONDS,
        help="Base seconds for exponential retry backoff when Retry-After is absent.",
    )
    parser.add_argument("--max-retry-wait", type=float, default=None, help="Maximum seconds to wait for one retry.")
    parser.add_argument("--max-wall-seconds", type=float, default=None, help="Maximum wall-clock seconds before partial pack.")
    parser.add_argument("--max-consecutive-errors", type=int, default=None, help="Stop search after consecutive errors.")
    parser.add_argument("--cache-only", action="store_true", help="Use persistent cache only; do not call Wikisource.")
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("WIKISOURCE_USER_AGENT", DEFAULT_USER_AGENT),
        help="Wikimedia-compliant User-Agent. Can also be set by WIKISOURCE_USER_AGENT.",
    )
    parser.add_argument("--cache-dir", type=Path, default=None, help="Persistent Wikisource cache root directory.")
    parser.add_argument("--cache-backend", choices=("filesystem", "postgres"), default=None, help="Override configured cache backend.")
    parser.add_argument("--cache-dsn-env", default=None, help="Override PostgreSQL cache DSN environment variable name.")
    parser.add_argument("--cache-schema", default=None, help="Override PostgreSQL cache schema.")
    parser.add_argument("--no-cache", action="store_true", help="Disable persistent Wikisource cache.")
    parser.add_argument("--cache-refresh", action="store_true", help="Ignore existing cache entries and overwrite them.")
    parser.add_argument("--refresh-pack-pages", action="store_true", help="Refetch page text even if pack pages already exist.")
    parser.add_argument("--progress-log", type=Path, help="JSONL progress log path; defaults to output_dir/progress.jsonl.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workflow_code = normalize_workflow_code(args.workflow_code)
    runtime = load_source_excerpt_pool_runtime(workflow_code=workflow_code)
    source_paths = runtime.get("paths") if isinstance(runtime.get("paths"), dict) else {}
    profile_path = args.profile or source_paths.get("query_profile") or DEFAULT_PROFILE
    source_scope = args.source_scope or runtime.get("source_scope")
    started_monotonic = time.monotonic()
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    profile = load_profile(profile_path, args.person, workflow_code=workflow_code)
    output_dir = args.output_dir or _default_output_dir(args.person, workflow_code=workflow_code)
    progress_path = args.progress_log or output_dir / "progress.jsonl"
    report = build_source_pack(
        profile,
        output_dir=output_dir,
        pack_id=args.pack_id,
        workflow_code=workflow_code,
        source_scope=source_scope,
        generated_by=DEFAULT_GENERATED_BY,
        extraction_method=DEFAULT_EXTRACTION_METHOD,
        include_adjacent=args.include_adjacent,
        max_queries=args.max_queries,
        max_queries_per_object=args.max_queries_per_object,
        pages_per_query=args.pages_per_query,
        context_chars=args.context_chars,
        max_passages_per_page=args.max_passages_per_page,
        timeout=args.timeout,
        request_delay_seconds=args.request_delay,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff,
        max_retry_wait_seconds=args.max_retry_wait,
        max_wall_seconds=args.max_wall_seconds,
        max_consecutive_errors=args.max_consecutive_errors,
        cache_only=args.cache_only,
        user_agent=args.user_agent,
        cache_dir=args.cache_dir,
        cache_enabled=False if args.no_cache else None,
        cache_refresh=args.cache_refresh,
        cache_backend=args.cache_backend,
        cache_dsn_env=args.cache_dsn_env,
        cache_schema=args.cache_schema,
        refresh_pack_pages=args.refresh_pack_pages,
        progress_path=progress_path,
    )
    finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
    print(
        json.dumps(
            {
                "at": finished_at,
                "started_at": started_at,
                "finished_at": finished_at,
                "elapsed_seconds": report.get("elapsed_seconds", round(time.monotonic() - started_monotonic, 3)),
                "output_dir": str(output_dir),
                "status": report["status"],
                "pages": report["written_pages"],
                "excerpts": report["excerpts"],
                "errors": len(report["errors"]),
                "objects_without_excerpts": report["object_coverage"]["objects_without_excerpts"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
