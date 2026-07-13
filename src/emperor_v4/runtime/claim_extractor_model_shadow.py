from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Sequence

from emperor_v4.adapters.claim_extraction_profile import load_claim_extraction_profile
from emperor_v4.adapters.claim_extractor_codex import CodexCliClaimExtractionProvider
from emperor_v4.adapters.claim_extractor_frozen import FrozenClaimExtractionProvider
from emperor_v4.application.claim_extractor_service import ensure_claim_extraction
from emperor_v4.persistence.claim_extractor import InMemoryClaimExtractionRepository
from emperor_v4.runtime.claim_extractor import request_from_frozen_snapshot


def _keys(assertions):
    return {
        (row.source_passage_ref, row.subject, row.predicate, row.object)
        for row in assertions
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V4 Claim Extractor real-model isolated shadow")
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-schema", type=Path, required=True)
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--service-release-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    request = request_from_frozen_snapshot(
        snapshot, profile_code=args.profile, request_id="CLX-V4-MODEL-SHADOW-001",
        idempotency_key="claim-extraction:v4:model-shadow:weizheng:talent:v1",
        requested_at="2026-07-14T21:00:00+08:00",
    )
    profile = load_claim_extraction_profile(args.profiles, args.profile)
    frozen = FrozenClaimExtractionProvider(args.snapshot).extract({"passages": list(request.passages)})
    run = ensure_claim_extraction(
        request, profile=profile,
        provider=CodexCliClaimExtractionProvider(
            codex_bin=args.codex_bin, model=args.model,
            reasoning_effort=args.reasoning_effort,
            output_schema_path=args.output_schema,
            timeout_seconds=args.timeout_seconds,
        ),
        repository=InMemoryClaimExtractionRepository(),
        service_release_sha=args.service_release_sha,
    )
    model_assertions = run.response["assertions"]
    frozen_keys = _keys(frozen.assertions)
    model_keys = {
        (row["source_passage_ref"], row["subject"], row["predicate"], row["object"])
        for row in model_assertions
    }
    report = {
        "schema_version": 1,
        "status": "claim_extractor_model_shadow_complete",
        "formal_acceptance": False,
        "human_review_required": True,
        "profile_code": profile.code,
        "service_release_sha": args.service_release_sha,
        "provider": run.response["provenance"]["provider"],
        "frozen_assertion_count": len(frozen.assertions),
        "model_assertion_count": len(model_assertions),
        "exact_semantic_key_overlap_count": len(frozen_keys & model_keys),
        "frozen_only_keys": [list(item) for item in sorted(frozen_keys - model_keys)],
        "model_only_keys": [list(item) for item in sorted(model_keys - frozen_keys)],
        "model_assertions": model_assertions,
        "runtime_audit": {
            "model_call_count": run.model_call_count,
            "database_write_count": 0,
            "server_unit_change_count": 0,
            "formal_assertion_write_count": 0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
