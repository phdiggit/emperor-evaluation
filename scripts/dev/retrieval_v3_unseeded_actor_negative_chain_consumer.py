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

from scripts.dev.retrieval_v2_claim_cache import claim_key  # noqa: E402
from scripts.dev.retrieval_v3_candidate_review_worklist import stable_code as candidate_review_code  # noqa: E402
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


def claim_key_lookup(workitem: Mapping[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for claim in workitem.get("accepted_claims") or []:
        if not isinstance(claim, Mapping):
            continue
        code = text(claim.get("claim_code"))
        if not code:
            continue
        key = claim_key(claim)
        if code in lookup and lookup[code] != key:
            raise NegativeChainConsumerError(f"{text(workitem.get('actor_name'))}: ambiguous claim code {code}")
        lookup[code] = key
    return lookup


def accepted_claim_lookup(workitem: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        text(claim.get("claim_code")): claim
        for claim in workitem.get("accepted_claims") or []
        if isinstance(claim, Mapping) and text(claim.get("claim_code"))
    }


def claim_action_type(claim: Mapping[str, Any]) -> str:
    fact = claim.get("fact_payload")
    return text(fact.get("action_type") if isinstance(fact, Mapping) else claim.get("action_type"))


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
    key_by_code = claim_key_lookup(workitem)
    claim_keys = {
        field.replace("_codes", "_keys"): [key_by_code[code] for code in values[field] if code in key_by_code]
        for field in ("appointment_claim_codes", "harm_claim_codes", "supporting_claim_codes")
    }
    claim_by_code = accepted_claim_lookup(workitem)
    harm_action_types = [claim_action_type(claim_by_code[code]) for code in values["harm_claim_codes"]]
    harm_claim_material_ready = any(action_type != "处置" for action_type in harm_action_types)
    return {
        "actor_name": actor,
        "target_emperor": text(row.get("target_emperor")),
        "review_verdict": verdict,
        **{field: bool(row[field]) for field in BOOLEAN_FIELDS},
        **values,
        **claim_keys,
        "harm_claim_action_types": harm_action_types,
        "harm_claim_material_ready": harm_claim_material_ready,
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
    candidates = []
    for row in reviewed:
        if row["review_verdict"] != "negative_chain_ready":
            continue
        refinement_reasons = []
        if not row["appointment_claim_keys"]:
            refinement_reasons.append("appointment_claim_missing")
        if not row["harm_claim_keys"]:
            refinement_reasons.append("harm_claim_missing")
        elif not row["harm_claim_material_ready"]:
            refinement_reasons.append("harm_is_only_disposition_claim")
        claim_refinement_required = bool(refinement_reasons)
        native_claim_keys = list(
            dict.fromkeys(row["appointment_claim_keys"] + row["harm_claim_keys"] + row["supporting_claim_keys"])
        )
        candidates.append({
            "candidate_code": stable_code("UANC-", row["target_emperor"], row["actor_name"], row["source_slice_refs"]),
            "emperor_name": row["target_emperor"],
            "object_name": row["actor_name"],
            "rule_code": "appointment_delegation",
            "direction": "negative",
            "appointment_claim_codes": row["appointment_claim_codes"],
            "harm_claim_codes": row["harm_claim_codes"],
            "supporting_claim_codes": row["supporting_claim_codes"],
            "appointment_claim_keys": row["appointment_claim_keys"],
            "harm_claim_keys": row["harm_claim_keys"],
            "supporting_claim_keys": row["supporting_claim_keys"],
            "native_claim_keys": native_claim_keys,
            "source_slice_refs": row["source_slice_refs"],
            "appointment_discovery_window_hashes": row["appointment_discovery_window_hashes"],
            "chain_summary": row["review_note"],
            "review_status": "candidate_only",
            "claim_refinement_required": claim_refinement_required,
            "claim_refinement_reasons": refinement_reasons,
            "native_candidate_ready": not claim_refinement_required,
            "next_action": (
                "refine_claims_before_native_candidate_binding"
                if claim_refinement_required
                else "prepare_v3_native_material_candidate"
            ),
            "write_db": False,
            "binding_allowed": False,
            "scoring_allowed": False,
        })
    return reviewed, candidates


def cached_claim_key(row: Mapping[str, Any]) -> str:
    payload = row.get("claim_payload")
    if not isinstance(payload, Mapping):
        return ""
    return text(payload.get("cached_claim_key") or payload.get("claim_key"))


def build_material_candidate_plan(
    candidates: Sequence[Mapping[str, Any]],
    material_claims: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    material_by_key: dict[str, dict[str, Any]] = {}
    for row in material_claims:
        key = cached_claim_key(row)
        if not key:
            continue
        if key in material_by_key:
            raise NegativeChainConsumerError(f"duplicate material claim cache key: {key}")
        material_by_key[key] = dict(row)

    planned: list[dict[str, Any]] = []
    review_patches: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for candidate in candidates:
        actor = text(candidate.get("object_name"))
        if candidate.get("native_candidate_ready") is not True or candidate.get("claim_refinement_required") is True:
            blocked.append({
                "negative_candidate_code": text(candidate.get("candidate_code")),
                "object_name": actor,
                "reason": "claim_refinement_required",
            })
            continue
        appointment_keys = list_texts(candidate.get("appointment_claim_keys"))
        harm_keys = list_texts(candidate.get("harm_claim_keys"))
        required_keys = list(dict.fromkeys(appointment_keys + harm_keys))
        missing_keys = [key for key in required_keys if key not in material_by_key]
        if missing_keys:
            blocked.append({
                "negative_candidate_code": text(candidate.get("candidate_code")),
                "object_name": actor,
                "reason": "native_material_claim_missing",
                "missing_claim_keys": missing_keys,
            })
            continue
        if not appointment_keys or not harm_keys:
            raise NegativeChainConsumerError(f"{actor}: native-ready candidate lacks appointment or harm claim keys")
        evidence_passage_codes = list(dict.fromkeys(
            text(code)
            for key in required_keys
            for code in material_by_key[key].get("source_passage_refs") or []
            if text(code)
        ))
        facts = {
            "has_appointment_or_authorization": True,
            "has_named_actor": True,
            "has_task_or_responsibility": True,
            "has_result_or_feedback": True,
            "has_continuity_or_reuse": False,
        }
        for harm_key in harm_keys:
            material = material_by_key[harm_key]
            if text(material.get("emperor_name")) != text(candidate.get("emperor_name")):
                raise NegativeChainConsumerError(f"{actor}: material emperor does not match negative candidate")
            if text(material.get("object_name")) != actor:
                raise NegativeChainConsumerError(f"{actor}: material object does not match negative candidate")
            claim_code = text(material.get("claim_code"))
            standard_candidate_code = f"{claim_code}::CANDIDATE::appointment_delegation"
            planned.append({
                "candidate_code": standard_candidate_code,
                "source_material_claim_code": claim_code,
                "source_pack_code": text(material.get("source_pack_code")),
                "emperor_name": text(candidate.get("emperor_name")),
                "object_name": actor,
                "claim_summary": text(material.get("claim_summary")),
                "candidate_item_code": "I5B",
                "candidate_rule_code": "appointment_delegation",
                "candidate_lane": "I5B.appointment_delegation",
                "hint_status": "current_rule_candidate",
                "formal_binding_allowed": False,
                "candidate_reason": text(candidate.get("chain_summary")),
                "matched_signals": ["reviewed_negative_appointment_harm_chain"],
                "matched_terms": [],
                "candidate_direction": "negative",
                "candidate_object_role": "misappointed_actor",
                "required_facts_present": facts,
                "candidate_payload": {
                    "created_from": "retrieval_v3_unseeded_actor_negative_chain_consumer",
                    "formal_binding_allowed": False,
                    "object_identity_gate": "required_before_formal_binding",
                    "negative_chain": {
                        "negative_candidate_code": text(candidate.get("candidate_code")),
                        "appointment_claim_keys": appointment_keys,
                        "harm_claim_keys": harm_keys,
                        "evidence_passage_codes": evidence_passage_codes,
                        "reviewed_complete_chain": True,
                    },
                },
            })
            review_patches.append({
                "review_code": candidate_review_code(standard_candidate_code),
                "review_verdict": "accepted_candidate",
                "review_note": text(candidate.get("chain_summary")),
                "required_facts": facts,
                "candidate_role": "misappointed_actor",
                "direction": "negative",
                "scoring_candidate": True,
                "usable_for_scoring_cluster": True,
                "identity_gate": "identity_pending",
                "evidence_passage_codes": evidence_passage_codes,
            })
    plan = {
        "ok": not blocked,
        "generated_by": "scripts/dev/retrieval_v3_unseeded_actor_negative_chain_consumer.py",
        "item_code": "I5B",
        "rule_code": "appointment_delegation",
        "material_scope": "rule_neutral",
        "write_db": False,
        "input_negative_candidates": len(candidates),
        "input_material_claims": len(material_claims),
        "candidate_count": len(planned),
        "blocked_count": len(blocked),
        "candidates": planned,
        "blocked": blocked,
    }
    return plan, review_patches


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate negative-chain review patches and emit file-only candidates.")
    parser.add_argument("--workitems-jsonl", type=Path, required=True)
    parser.add_argument("--patch-jsonl", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-candidates-jsonl", type=Path, required=True)
    parser.add_argument("--input-material-claims-jsonl", type=Path)
    parser.add_argument("--output-material-candidate-plan", type=Path)
    parser.add_argument("--output-candidate-review-patch-jsonl", type=Path)
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
    material_paths = (
        args.input_material_claims_jsonl,
        args.output_material_candidate_plan,
        args.output_candidate_review_patch_jsonl,
    )
    if any(material_paths) and not all(material_paths):
        raise NegativeChainConsumerError("material candidate conversion requires all three material paths")
    if all(material_paths):
        material_plan, review_patches = build_material_candidate_plan(
            candidates,
            read_jsonl(args.input_material_claims_jsonl),
        )
        write_text(
            args.output_material_candidate_plan,
            json.dumps(material_plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        write_jsonl(args.output_candidate_review_patch_jsonl, review_patches)
        report["material_candidate_plan"] = {
            "ok": material_plan["ok"],
            "candidate_count": material_plan["candidate_count"],
            "blocked_count": material_plan["blocked_count"],
            "candidate_review_patch_count": len(review_patches),
        }
        write_text(args.output_json, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "reviewed_actors"}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
