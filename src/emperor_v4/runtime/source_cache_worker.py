from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.adapters.source_cache_fixture import FrozenSourceMaterialProvider
from emperor_v4.adapters.source_cache_wikisource import WikisourceSourceMaterialProvider
from emperor_v4.application.source_cache_service import ensure_source_cache
from emperor_v4.application.source_cache_worker import run_source_cache_worker_once
from emperor_v4.persistence.postgres_source_cache import PostgresSourceCacheRepository
from emperor_v4.persistence.source_cache_jobs import PostgresSourceCacheJobRepository
from emperor_v4.runtime.source_cache import source_cache_request_from_mapping


def build_handler(
    *, dsn: str, provider_code: str, plan_path: Path,
    repo_root: Path, service_release_sha: str,
):
    provider = (
        FrozenSourceMaterialProvider(plan_path=plan_path, repo_root=repo_root)
        if provider_code == "fixture"
        else WikisourceSourceMaterialProvider(plan_path=plan_path)
    )
    cache = PostgresSourceCacheRepository(dsn)

    def handle(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        run = ensure_source_cache(
            source_cache_request_from_mapping(payload), provider=provider,
            repository=cache, service_release_sha=service_release_sha,
        )
        return run.response

    return handle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V4 Source Cache 单次 lease worker")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_V4_SOURCE_CACHE_DSN")
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--provider", choices=("fixture", "wikisource"), required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--service-release-sha", required=True)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--retry-delay-seconds", type=int, default=60)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dsn = os.environ.get(args.dsn_env, "")
    if not dsn:
        raise SystemExit(f"未设置 DSN 环境变量: {args.dsn_env}")
    tick = run_source_cache_worker_once(
        PostgresSourceCacheJobRepository(dsn), worker_id=args.worker_id,
        handler=build_handler(
            dsn=dsn, provider_code=args.provider, plan_path=args.plan,
            repo_root=args.repo_root, service_release_sha=args.service_release_sha,
        ),
        lease_seconds=args.lease_seconds,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    print(json.dumps({
        "status": tick.status, "job_id": tick.job_id, "run_id": tick.run_id,
        "recovered_lease_count": tick.recovered_lease_count,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
