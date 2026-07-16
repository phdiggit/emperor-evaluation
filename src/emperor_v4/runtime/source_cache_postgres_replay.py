from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from emperor_v4.adapters.source_cache_fixture import FrozenSourceMaterialProvider
from emperor_v4.application.source_cache_service import ensure_source_cache
from emperor_v4.persistence.postgres_source_cache import PostgresSourceCacheRepository
from emperor_v4.runtime.source_cache import load_source_cache_request


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist frozen Source Cache jobs and verify zero-write replay")
    parser.add_argument("--job", nargs=2, action="append", metavar=("REQUEST", "PLAN"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_V4_SOURCE_CACHE_DSN")
    parser.add_argument("--service-release-sha", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    load_dotenv()
    dsn = os.environ.get(args.dsn_env, "")
    if not dsn:
        raise ValueError(f"missing DSN environment variable: {args.dsn_env}")
    repository = PostgresSourceCacheRepository(dsn)
    rows = []
    for request_value, plan_value in args.job:
        request_path = Path(request_value)
        plan_path = Path(plan_value)
        request = load_source_cache_request(request_path)
        provider = FrozenSourceMaterialProvider(plan_path=plan_path, repo_root=args.repo_root)
        first = ensure_source_cache(request, provider=provider, repository=repository, service_release_sha=args.service_release_sha)
        second = ensure_source_cache(request, provider=provider, repository=repository, service_release_sha=args.service_release_sha)
        if second.repository_write_count != 0 or second.provider_call_count != 0 or not second.cache_hit:
            raise ValueError("Source Cache idempotent replay performed business work")
        rows.append({
            "request_id": request.request_id,
            "request_ref": request_value,
            "plan_ref": plan_value,
            "input_fingerprint": first.response.get("input_fingerprint"),
            "output_fingerprint": first.response.get("output_fingerprint"),
            "document_count": len(first.response.get("documents") or ()),
            "passage_count": len(first.response.get("passages") or ()),
            "first_run": {"cache_hit": first.cache_hit, "provider_call_count": first.provider_call_count, "repository_write_count": first.repository_write_count, "network_request_count": first.network_request_count},
            "idempotent_rerun": {"cache_hit": second.cache_hit, "provider_call_count": second.provider_call_count, "repository_write_count": second.repository_write_count, "network_request_count": second.network_request_count},
        })
    payload = {
        "schema_version": "i5b-source-cache-postgres-replay-audit-v1",
        "status": "source_cache_persisted_idempotent",
        "jobs": rows,
        "summary": {
            "job_count": len(rows),
            "first_run_business_write_count": sum(row["first_run"]["repository_write_count"] for row in rows),
            "idempotent_rerun_business_write_count": sum(row["idempotent_rerun"]["repository_write_count"] for row in rows),
            "model_call_count": 0,
            "formal_score_write": False,
            "v3_database_write": False,
            "migration_executed": False,
        },
    }
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["report_sha256"] = sha256(rendered.encode("utf-8")).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
