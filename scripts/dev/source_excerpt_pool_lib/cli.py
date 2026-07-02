from __future__ import annotations

import argparse
import json
import os

from .builder import build_excerpt_pool, migrate_configured_cache_to_postgres
from .common import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_PROFILE,
    DEFAULT_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_USER_AGENT,
)
from .profile import load_profile
from .reporting import write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a review-first source excerpt pool from an I5B query profile.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="Query-profile JSONL path.")
    parser.add_argument("--person", help="Profile person name.")
    parser.add_argument("--output", type=Path, help="Output report path.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Output format.")
    parser.add_argument("--include-adjacent", action="store_true", help="Include adjacent_split_objects.")
    parser.add_argument("--offline", action="store_true", help="Only build object/query plans; do not call Wikisource.")
    parser.add_argument("--max-queries", type=int, default=None, help="Global maximum query count.")
    parser.add_argument(
        "--max-queries-per-object",
        type=int,
        default=None,
        help="Maximum queries per object; omit to keep every generated query.",
    )
    parser.add_argument("--pages-per-query", type=int, default=2, help="Wikisource pages to inspect per query.")
    parser.add_argument("--context-chars", type=int, default=220, help="Characters before/after each hit.")
    parser.add_argument("--max-passages-per-page", type=int, default=2, help="Passages to keep per page.")
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
    parser.add_argument(
        "--max-retry-wait",
        type=float,
        default=None,
        help="Maximum seconds to wait for one retry, including Retry-After.",
    )
    parser.add_argument(
        "--max-wall-seconds",
        type=float,
        default=None,
        help="Maximum wall-clock seconds for one person before writing a partial report.",
    )
    parser.add_argument(
        "--max-consecutive-errors",
        type=int,
        default=None,
        help="Stop after this many consecutive search/page errors and mark remaining plans skipped.",
    )
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
    parser.add_argument(
        "--migrate-cache-to-postgres",
        action="store_true",
        help="Import existing filesystem Wikisource cache into the configured PostgreSQL cache tables.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.migrate_cache_to_postgres:
        report = migrate_configured_cache_to_postgres(
            cache_dir=args.cache_dir,
            cache_backend=args.cache_backend or "postgres",
            cache_dsn_env=args.cache_dsn_env,
            cache_schema=args.cache_schema,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not args.person:
        parser.error("--person is required unless --migrate-cache-to-postgres is used")
    if args.output is None:
        parser.error("--output is required unless --migrate-cache-to-postgres is used")
    profile = load_profile(args.profile, args.person)
    report = build_excerpt_pool(
        profile,
        include_adjacent=args.include_adjacent,
        max_queries=args.max_queries,
        max_queries_per_object=args.max_queries_per_object,
        pages_per_query=args.pages_per_query,
        context_chars=args.context_chars,
        max_passages_per_page=args.max_passages_per_page,
        timeout=args.timeout,
        offline=args.offline,
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
    )
    write_report(args.output, report, output_format=args.format)
    print(json.dumps({"output": str(args.output), "objects": len(report["objects"]), "excerpts": len(report["excerpts"])}, ensure_ascii=False))
    return 0


