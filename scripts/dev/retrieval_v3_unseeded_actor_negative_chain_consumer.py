from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_unseeded_actor_discovery import stable_code, text, write_jsonl, write_text  # noqa: E402
from scripts.dev.retrieval_v3_unseeded_actor_review_tasks import read_jsonl  # noqa: E402


VERDICT_ACTIONS = {
    "negative_chain_ready": "emit_negative_candidate",
    "supporting_only": "retain_supporting_only",
    "disposition_only": "retain_disposition_only",
    "needs_source_refine": "run_object_source_refiner",
    "source_identity_mismatch": "refine_identity_specific_sources",
}
BOOLEAN_FIELDS = (
    "has_appointment_or_authorization",
    "has_task_or_responsibility",
    "has_same_chain_harm_or_failure",
    "has_disposition_only",
)
LIST_FIELDS = (
    "appointment_claim_codes",
    "harm_claim_codes",
    "supporting_claim_codes",
    "source_slice_refs",
)


class NegativeChainConsumerError(ValueError):
    pass


def list_texts(value: Any) -> list[str]:
    return list(dict.fromkeys(text(item) for item in value or [] if text(item)))


def validate_patch(row: Mapping[str, Any], workitem: Mapping[str, Any]) -> dict[str, Any]:
    actor = text(row.get("actor_name"))
    if actor != text(workitem.get("actor_name")):
        raise NegativeChainConsumerError(f"{actor or '(blank)'}: actor_name does not match workitem")
    if text(row.get("target_emperor")) != text(workitem.get("target_emperor")):
        raise NegativeChainConsumerError(f"{actor}: target_emperor does not match workitem")
    verdict = text(row.get("review_verdict"))
    if verdict not in VERDICT_ACTIONS:
        raise NegativeChainConsumerError(f"{actor}: unsupported review_verdict={verdict!r}")
    if text(row.get("recommended_action")) != VERDICT_ACTIONS[verdict]:
        raise NegativeChainConsumerError(f"{actor}: recommended_action mismatch")
    for field in BOOLEAN_FIELDS:
        if not isinstance(row.get(field), bool):
            raise NegativeChainConsumerError(f"{actor}: {field} must be boolean")
    values = {field: list_texts(row.get(field)) for field in LIST_FIELDS}
    allowed_claims = set(list_texts(workitem.get("allowed_claim_codes")))
    allowed_cross_target = set(list_texts(workitem.get("allowed_cross_target_claim_codes")))
    allowed_refs = set(list_texts(workitem.get("allowed_source_slice_refs")))
    allowed_discovery_windows = list_texts(
        evidence.get("window_hash")
        for evidence in workitem.get("discovery_evidence") or []
        if isinstance(evidence, Mapping)
    )
    if not set(values["appointment_claim_codes"] + values["harm_claim_codes"] + values["supporting_claim_codes"]).issubset(
        allowed_claims | allowed_cross_target
    ):
        raise NegativeChainConsumerError(f"{actor}: unknown claim code")
    if not set(values["source_slice_refs"]).issubset(allowed_refs):
        raise NegativeChainConsumerError(f"{actor}: unknown source slice ref")
    if verdict == "negative_chain_ready":
        if not all(bool(row[field]) for field in BOOLEAN_FIELDS[:3]) or bool(row["has_disposition_only"]):
            raise NegativeChainConsumerError(f"{actor}: negative_chain_ready requires complete non-disposition chain")
        if not (values["appointment_claim_codes"] or allowed_discovery_windows):
            raise NegativeChainConsumerError(f"{actor}: negative_chain_ready requires appointment claim or discovery window")
        if not values["harm_claim_codes"] or not values["source_slice_refs"]:
            raise NegativeChainConsumerError(f"{actor}: negative_chain_ready requires harm claim codes and source refs")
        if set(values["appointment_claim_codes"] + values["harm_claim_codes"]) & allowed_cross_target:
            raise NegativeChainConsumerError(f"{actor}: negative chain cannot use cross-target claims")
    if verdict == "disposition_only" and (not row["has_disposition_only"] or row["has_same_chain_harm_or_failure"]):
        raise NegativeChainConsumerError(f"{actor}: disposition_only flags are inconsistent")
    if verdict == "source_identity_mismatch" and not allowed_cross_target:
        raise NegativeChainConsumerError(f"{actor}: identity mismatch requires cross-target evidence")
    note = text(row.get("review_note"))
    if not note:
        raise NegativeChainConsumerError(f"{actor}: review_note is required")
    return {
        "actor_name": actor,
        "target_emperor": text(row.get("target_emperor")),
        "review_verdict": verdict,
        **{field: bool(row[field]) for field in BOOLEAN_FIELDS},
        **values,
        "appointment_discovery_window_hashes": (
            allowed_discovery_windows if verdict == "negative_chain_ready" and not values["appointment_claim_codes"] else []
        ),
        "recommended_action": VERDICT_ACTIONS[verdict],
        "review_note": note,
        "write_db": False,
        "scoring_allowed": False,
    }


def consume(workitems: Sequence[Mapping[str, Any]], patches: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    work_by_actor = {text(row.get("actor_name")): dict(row) for row in workitems if text(row.get("actor_name"))}
    patch_by_actor: dict[str, Mapping[str, Any]] = {}
    for patch in patches:
        actor = text(patch.get("actor_name"))
        if actor in patch_by_actor:
            raise NegativeChainConsumerError(f"duplicate actor patch: {actor}")
        patch_by_actor[actor] = patch
    if set(work_by_actor) != set(patch_by_actor):
        raise NegativeChainConsumerError(
            f"patch actor set mismatch; missing={sorted(set(work_by_actor) - set(patch_by_actor))}, "
            f"unknown={sorted(set(patch_by_actor) - set(work_by_actor))}"
        )
    reviewed = [validate_patch(patch_by_actor[actor], work_by_actor[actor]) for actor in work_by_actor]
    candidates = [
        {
            "candidate_code": stable_code("UANC-", row["target_emperor"], row["actor_name"], row["source_slice_refs"]),
            "emperor_name": row["target_emperor"],
            "object_name": row["actor_name"],
            "rule_code": "appointment_delegation",
            "direction": "negative",
            "appointment_claim_codes": row["appointment_claim_codes"],
            "harm_claim_codes": row["harm_claim_codes"],
            "supporting_claim_codes": row["supporting_claim_codes"],
            "source_slice_refs": row["source_slice_refs"],
            "appointment_discovery_window_hashes": row["appointment_discovery_window_hashes"],
            "chain_summary": row["review_note"],
            "review_status": "candidate_only",
            "claim_refinement_required": True,
            "next_action": "refine_claims_before_native_candidate_binding",
            "write_db": False,
            "binding_allowed": False,
            "scoring_allowed": False,
        }
        for row in reviewed
        if row["review_verdict"] == "negative_chain_ready"
    ]
    return reviewed, candidates


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate negative-chain review patches and emit file-only candidates.")
    parser.add_argument("--workitems-jsonl", type=Path, required=True)
    parser.add_argument("--patch-jsonl", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-candidates-jsonl", type=Path, required=True)
    args = parser.parse_args(argv)
    reviewed, candidates = consume(read_jsonl(args.workitems_jsonl), read_jsonl(args.patch_jsonl))
    verdicts = Counter(row["review_verdict"] for row in reviewed)
    report = {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_unseeded_actor_negative_chain_consumer.py",
        "write_db": False,
        "scoring_allowed": False,
        "counts_by_verdict": dict(sorted(verdicts.items())),
        "negative_candidate_count": len(candidates),
        "reviewed_actors": reviewed,
        "execute_effect": "validated file-only negative-chain candidates; no object, claim, binding, factor, or score writes",
    }
    write_text(args.output_json, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    write_jsonl(args.output_candidates_jsonl, candidates)
    print(json.dumps({key: value for key, value in report.items() if key != "reviewed_actors"}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
