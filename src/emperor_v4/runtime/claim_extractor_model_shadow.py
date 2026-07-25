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
from emperor_v4.contracts.extraction import ClaimExtractionRequest
from emperor_v4.persistence.claim_extractor import InMemoryClaimExtractionRepository


def _keys(assertions):
    return {
        (row.subject, row.predicate, row.object)
        for row in assertions
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V4 Claim Extractor real-model isolated shadow")
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--source-cache-report", type=Path, required=True)
    parser.add_argument("--output-schema", type=Path, required=True)
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--service-release-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    source_cache = json.loads(args.source_cache_report.read_text(encoding="utf-8"))
    request = ClaimExtractionRequest(
        request_id="CLX-V4-MODEL-SHADOW-002",
        idempotency_key="claim-extraction:v4:model-shadow:weizheng:talent:source-v2",
        profile_code=args.profile,
        subject={"person_ref": "PER-WEIZHENG", "ruler": "李世民"},
        passages=tuple(source_cache["response"]["passages"]),
        requested_at="2026-07-14T21:30:00+08:00",
    )
    profile = load_claim_extraction_profile(args.profiles, args.profile)
    frozen_person = snapshot["people"][0]
    frozen = FrozenClaimExtractionProvider(args.snapshot).extract(
        {"passages": frozen_person["payload"]["passages"]}
    )
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
    model_keys = {(row["subject"], row["predicate"], row["object"]) for row in model_assertions}
    frozen_quote = "\n".join(str(row.get("quote") or "") for row in frozen_person["payload"]["passages"])
    unsupported_frozen = []
    for assertion in frozen.assertions:
        spans = assertion.qualifiers.get("evidence_spans") or ()
        if spans and any(str(span.get("text") or "") not in frozen_quote for span in spans):
            unsupported_frozen.append(assertion.assertion_code)
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
        "input_audit": {
            "source_cache_contract": source_cache["response"]["contract"],
            "source_cache_passage_count": len(request.passages),
            "frozen_assertions_with_span_outside_frozen_quote": unsupported_frozen,
        },
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
