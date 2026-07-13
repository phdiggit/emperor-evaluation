from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.adapters.claim_extraction_profile import load_claim_extraction_profile
from emperor_v4.adapters.claim_extractor_frozen import FrozenClaimExtractionProvider
from emperor_v4.application.claim_extractor_service import ensure_claim_extraction
from emperor_v4.application.source_cache_worker import run_source_cache_worker_once
from emperor_v4.contracts.extraction import ClaimExtractionRequest
from emperor_v4.persistence.claim_extractor import ShadowJsonClaimExtractionRepository
from emperor_v4.persistence.postgres_claim_extractor import PostgresClaimExtractionRepository
from emperor_v4.persistence.source_cache_jobs import PostgresSourceCacheJobRepository


def request_from_mapping(payload: Mapping[str, Any]) -> ClaimExtractionRequest:
    return ClaimExtractionRequest(
        request_id=str(payload.get("request_id") or ""),
        idempotency_key=str(payload.get("idempotency_key") or ""),
        profile_code=str(payload.get("profile_code") or ""),
        subject=payload.get("subject") or {},
        passages=tuple(payload.get("passages") or ()),
        requested_at=str(payload.get("requested_at") or ""),
    )


def request_from_frozen_snapshot(snapshot: Mapping[str, Any], *, profile_code: str, request_id: str, idempotency_key: str, requested_at: str) -> ClaimExtractionRequest:
    person = snapshot["people"][0]
    return ClaimExtractionRequest(
        request_id=request_id, idempotency_key=idempotency_key,
        profile_code=profile_code,
        subject={"ruler": person.get("ruler"), "claim_run": person.get("claim_run")},
        passages=tuple(person["payload"].get("passages") or ()),
        requested_at=requested_at,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V4 Claim Extractor frozen/provider runtime")
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--requested-at", required=True)
    parser.add_argument("--service-release-sha", required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_V4_CLAIM_EXTRACTOR_DSN")
    parser.add_argument("--worker-id")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    request = request_from_frozen_snapshot(
        snapshot, profile_code=args.profile, request_id=args.request_id,
        idempotency_key=args.idempotency_key, requested_at=args.requested_at,
    )
    profile = load_claim_extraction_profile(args.profiles, args.profile)
    provider = FrozenClaimExtractionProvider(args.snapshot)
    if args.worker_id:
        dsn = os.environ.get(args.dsn_env, "")
        if not dsn:
            raise SystemExit(f"未设置 DSN 环境变量: {args.dsn_env}")
        repository = PostgresClaimExtractionRepository(dsn)
        jobs = PostgresSourceCacheJobRepository(dsn, schema="v4_claim_extractor")

        def handler(payload: Mapping[str, Any]) -> Mapping[str, Any]:
            return ensure_claim_extraction(
                request_from_mapping(payload), profile=profile, provider=provider,
                repository=repository, service_release_sha=args.service_release_sha,
            ).response

        tick = run_source_cache_worker_once(jobs, worker_id=args.worker_id, handler=handler)
        report = asdict(tick)
    else:
        if args.state is None:
            raise SystemExit("非 worker 模式必须提供 --state")
        run = ensure_claim_extraction(
            request, profile=profile, provider=provider,
            repository=ShadowJsonClaimExtractionRepository(args.state),
            service_release_sha=args.service_release_sha,
        )
        report = {
            "status": "claim_extraction_fixture_complete",
            "request": asdict(request), "response": run.response,
            "runtime_audit": {
                "cache_hit": run.cache_hit,
                "provider_call_count": run.provider_call_count,
                "model_call_count": run.model_call_count,
                "repository_write_count": run.repository_write_count,
                "database_write_count": 0,
            },
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
