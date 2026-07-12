from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from emperor_v4.application.reconcile_episode import reconcile_episode_candidates
from emperor_v4.contracts.assertion import AssertionDraft


FORBIDDEN_KERNEL_KEYS = frozenset(
    {
        "episode_code",
        "gold_boundary",
        "must_merge",
        "must_not_merge",
        "expected_participants",
        "acceptance_decision",
        "gold_linkage",
        "expected_event_repair",
        "candidate_boundary_key",
        "candidate_episode_key",
    }
)


def _walk_keys(value: Any, path: str = "$"):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield path, str(key)
            yield from _walk_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_keys(item, f"{path}[{index}]")


def validate_blind_kernel_input(payload: Mapping[str, Any]) -> None:
    violations = [
        f"{path}.{key}"
        for path, key in _walk_keys(payload)
        if key.casefold() in FORBIDDEN_KERNEL_KEYS
    ]
    if violations:
        raise ValueError(f"blind kernel 输入包含 Gold/oracle 字段: {violations}")
    if not payload.get("assertions"):
        raise ValueError("blind kernel 输入缺少 assertions")


def _assertion_from_row(row: Mapping[str, Any]) -> AssertionDraft:
    return AssertionDraft(
        assertion_code=row["assertion_code"],
        source_passage_ref=row["source_passage_ref"],
        assertion_type=row["assertion_type"],
        subject=row["subject"],
        predicate=row["predicate"],
        object=row["object"],
        time_expression=row.get("time_expression"),
        location_expression=row.get("location_expression"),
        qualifiers=row.get("qualifiers") or {},
        polarity=row["polarity"],
        source_attribution=row.get("source_attribution") or {},
        candidate_episode_key=None,
        confidence=float(row["confidence"]),
        ambiguity_flags=tuple(row.get("ambiguity_flags") or ()),
        extraction_provenance=row.get("extraction_provenance") or {},
    )


def run_blind_holdout(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Kernel-only entrypoint. It has no parameter through which Gold can enter."""

    validate_blind_kernel_input(payload)
    assertions = tuple(_assertion_from_row(row) for row in payload["assertions"])
    packets = reconcile_episode_candidates(assertions)
    canonical_names = {
        item["canonical_name"]: item["person_id"]
        for item in payload.get("canonical_people", [])
    }
    packet_rows = []
    for packet in packets:
        unresolved = sorted(
            {
                participant.person_ref
                for participant in packet.participants
                if participant.person_ref not in canonical_names
            }
        )
        packet_rows.append(
            {
                "candidate_id": packet.episode_id,
                "semantic_fingerprint": packet.semantic_fingerprint,
                "evaluation_context": packet.evaluation_context,
                "episode_type": packet.episode_type,
                "participants": [
                    {
                        "observed_ref": participant.person_ref,
                        "canonical_candidate_ref": canonical_names.get(
                            participant.person_ref
                        ),
                        "role_codes": list(participant.role_codes),
                    }
                    for participant in packet.participants
                ],
                "action": packet.action,
                "responsibility": packet.responsibility,
                "time_start": packet.time_start,
                "time_end": packet.time_end,
                "locations": list(packet.locations),
                "assertion_links": [
                    {
                        "assertion_ref": link.assertion_ref,
                        "source_passage_ref": link.source_passage_ref,
                        "relation": link.relation,
                    }
                    for link in packet.assertion_links
                ],
                "conflicts": list(packet.conflicts),
                "uncertainties": list(packet.uncertainties),
                "identity_blockers": unresolved,
                "human_review_required": bool(
                    unresolved or packet.conflicts or packet.uncertainties
                ),
                "merge_split_rationale": {
                    "method": "deterministic_structured_candidate_key_v1",
                    "gold_hint_used": False,
                },
            }
        )

    canonical_input = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        "schema_version": 1,
        "run_code": payload.get("dataset_code"),
        "status": "blind_candidates_proposed",
        "execution_mode": "blind_no_gold_no_model_no_network_no_write",
        "input_sha256": hashlib.sha256(
            canonical_input.encode("utf-8")
        ).hexdigest(),
        "input_assertion_count": len(assertions),
        "candidate_packet_count": len(packet_rows),
        "accuracy_metrics": {
            "status": "sealed_gold_not_opened",
            "autonomous_boundary_recall": None,
            "candidate_precision": None,
            "wrong_merge_count": None,
            "wrong_split_count": None,
        },
        "packets": sorted(
            packet_rows, key=lambda item: item["semantic_fingerprint"]
        ),
        "safety": {
            "gold_fields_detected": 0,
            "model_call_count": 0,
            "network_request_count": 0,
            "database_write_count": 0,
        },
    }


def score_blind_holdout(
    run_report: Mapping[str, Any],
    sealed_gold: Mapping[str, Any],
) -> dict[str, Any]:
    """Post-run scorer. Gold is opened only after the candidate artifact exists."""

    if sealed_gold.get("candidate_input_sha256") != run_report.get("input_sha256"):
        raise ValueError("sealed Gold 与 blind input hash 不一致")
    packets = run_report.get("packets") or []
    fingerprints = {item["semantic_fingerprint"] for item in packets}
    decisions = sealed_gold.get("candidate_decisions") or {}
    if set(decisions) != fingerprints:
        raise ValueError("sealed Gold decisions 未覆盖全部 blind candidates")
    gold_codes = set(sealed_gold.get("gold_episode_codes") or ())
    full_codes = {
        code
        for item in decisions.values()
        if item.get("decision") == "full_match"
        for code in item.get("gold_episode_codes", [])
    }
    full_candidate_count = sum(
        item.get("decision") == "full_match" for item in decisions.values()
    )
    lineage_complete_count = sum(
        bool(item.get("assertion_links"))
        and all(link.get("source_passage_ref") for link in item["assertion_links"])
        for item in packets
    )
    identity_block_count = sum(bool(item.get("identity_blockers")) for item in packets)
    human_review_count = sum(item.get("human_review_required") is True for item in packets)
    return {
        "schema_version": 1,
        "status": "blind_scored_after_sealed_gold_opened",
        "metrics": {
            "autonomous_boundary_recall": (
                len(full_codes) / len(gold_codes) if gold_codes else None
            ),
            "candidate_precision": (
                full_candidate_count / len(packets) if packets else None
            ),
            "wrong_merge_count": len(
                sealed_gold.get("wrong_merge_fingerprints") or ()
            ),
            "wrong_split_count": len(
                sealed_gold.get("wrong_split_gold_episode_codes") or ()
            ),
            "cross_ruler_contamination_count": int(
                sealed_gold.get("cross_ruler_contamination_count") or 0
            ),
            "identity_block_rate": (
                identity_block_count / len(packets) if packets else None
            ),
            "human_review_rate": (
                human_review_count / len(packets) if packets else None
            ),
            "lineage_completeness": (
                lineage_complete_count / len(packets) if packets else None
            ),
        },
        "accepted_metrics": {
            "status": "not_computable_before_independent_human_acceptance",
            "accepted_recall": None,
            "accepted_precision": None,
        },
    }
