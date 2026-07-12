from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml


def _load_yaml(path: Path) -> Mapping[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _blocking_completeness_mismatches(
    mismatches: Mapping[str, Mapping[str, str]],
) -> dict[str, Mapping[str, str]]:
    blocked: dict[str, Mapping[str, str]] = {}
    for slot, values in mismatches.items():
        expected = values.get("expected")
        actual = values.get("actual")
        if expected == "complete" and actual != "complete":
            blocked[slot] = values
        elif expected == "partial" and actual in {"missing", None}:
            blocked[slot] = values
        elif expected == "conflicted" and actual != "conflicted":
            blocked[slot] = values
    return blocked


def build_reconciliation_review_package(
    manifest_path: Path,
    boundary_review_path: Path,
    pilot_report: Mapping[str, Any],
) -> dict[str, Any]:
    manifest = _load_yaml(manifest_path)
    boundary_review = _load_yaml(boundary_review_path)
    frozen_codes = set(manifest.get("frozen_episode_codes") or ())
    manifest_by_code = {
        item["episode_code"]: item
        for item in manifest.get("episodes", [])
        if item.get("episode_code") in frozen_codes
    }
    boundary_by_code = boundary_review.get("reviews") or {}
    assessments = pilot_report.get("lineage_assisted_reconciliation", {}).get(
        "packet_assessments", []
    )
    assessment_by_code = {item["episode_code"]: item for item in assessments}
    if set(assessment_by_code) != frozen_codes:
        raise ValueError("review package 未一一覆盖 frozen episode")

    items: list[dict[str, Any]] = []
    for episode_code in sorted(frozen_codes):
        episode = manifest_by_code[episode_code]
        boundary = boundary_by_code.get(episode_code) or {}
        packet = assessment_by_code[episode_code]
        links = packet.get("assertion_links") or []
        passage_lineage_complete = bool(links) and all(
            item.get("source_passage_ref") for item in links
        )
        unresolved_participants = [
            item["person_ref"]
            for item in packet.get("participants", [])
            if item.get("role_status") == "unresolved"
        ]
        expected_participants = set(episode.get("participants") or ())
        actual_participants = {
            item["person_ref"] for item in packet.get("participants", [])
        }
        unexpected_participants = sorted(actual_participants - expected_participants)
        blocking_completeness = _blocking_completeness_mismatches(
            packet.get("gold_completeness_mismatches") or {}
        )
        blocking_reasons: list[str] = []
        if boundary.get("decision") != "accepted":
            blocking_reasons.append("gold_boundary_not_accepted")
        if packet.get("assertion_boundary_decision") != "full_boundary_support":
            blocking_reasons.append("assertion_boundary_not_fully_supported")
        if packet.get("participant_coverage") != 1.0:
            blocking_reasons.append("expected_participants_missing")
        if unresolved_participants:
            blocking_reasons.append("canonical_identity_unresolved")
        if unexpected_participants:
            blocking_reasons.append("unexpected_participant_candidate")
        if not passage_lineage_complete:
            blocking_reasons.append("passage_lineage_incomplete")
        if blocking_completeness:
            blocking_reasons.append("blocking_completeness_mismatch")

        if "gold_boundary_not_accepted" in blocking_reasons:
            recommendation = "blocked_boundary_review"
        elif "passage_lineage_incomplete" in blocking_reasons:
            recommendation = "needs_evidence_review"
        elif blocking_completeness:
            recommendation = "needs_evidence_review"
        elif unresolved_participants:
            recommendation = "needs_identity_review"
        else:
            recommendation = "accept_after_human_confirmation"

        items.append(
            {
                "episode_code": episode_code,
                "proposed_episode_id": packet["episode_id"],
                "proposed_semantic_fingerprint": packet["semantic_fingerprint"],
                "semantic_version": packet.get("semantic_version"),
                "evidence_version": packet.get("evidence_version"),
                "current_status": packet["episode_status"],
                "gold_boundary_decision": boundary.get("decision"),
                "gold_boundary_review": boundary.get("boundary_review"),
                "assertion_boundary_decision": packet.get(
                    "assertion_boundary_decision"
                ),
                "participants": packet.get("participants"),
                "unresolved_participants": unresolved_participants,
                "unexpected_participant_candidates": unexpected_participants,
                "action": packet.get("action"),
                "time_start": packet.get("time_start"),
                "time_end": packet.get("time_end"),
                "time_precision": packet.get("time_precision"),
                "locations": packet.get("locations"),
                "evaluation_context": packet.get("evaluation_context"),
                "episode_type": packet.get("episode_type"),
                "responsibility": packet.get("responsibility"),
                "outcome": packet.get("outcome"),
                "consequence": packet.get("consequence"),
                "completeness": packet.get("completeness"),
                "blocking_completeness_mismatches": blocking_completeness,
                "advisory_completeness_mismatches": {
                    slot: values
                    for slot, values in packet.get(
                        "gold_completeness_mismatches", {}
                    ).items()
                    if slot not in blocking_completeness
                },
                "assertion_links": links,
                "passage_lineage_complete": passage_lineage_complete,
                "must_merge": episode.get("must_merge") or [],
                "must_not_merge": episode.get("must_not_merge") or [],
                "conflicts": packet.get("conflicts"),
                "uncertainties": packet.get("uncertainties"),
                "lineage": packet.get("lineage"),
                "recommended_next_status": recommendation,
                "blocking_reasons": blocking_reasons,
                "human_decision": "pending",
                "human_review_note": None,
            }
        )

    return {
        "schema_version": 1,
        "review_package_code": "episode_pilot_v1_reconciliation_review",
        "packet_contract": "historical-episode-packet-v1",
        "status": "pending_human_review",
        "manifest": str(manifest_path).replace("\\", "/"),
        "boundary_review": str(boundary_review_path).replace("\\", "/"),
        "gate": "G2 Assertion 与 Episode",
        "summary": {
            "frozen_episode_count": len(frozen_codes),
            "packet_count": len(items),
            "full_assertion_support_count": sum(
                item["assertion_boundary_decision"] == "full_boundary_support"
                for item in items
            ),
            "passage_lineage_complete_count": sum(
                item["passage_lineage_complete"] for item in items
            ),
            "identity_review_required_count": sum(
                "canonical_identity_unresolved" in item["blocking_reasons"]
                for item in items
            ),
            "unexpected_participant_candidate_packet_count": sum(
                bool(item["unexpected_participant_candidates"]) for item in items
            ),
            "evidence_review_required_count": sum(
                item["recommended_next_status"] == "needs_evidence_review"
                for item in items
            ),
            "acceptance_ready_count": sum(
                item["recommended_next_status"]
                == "accept_after_human_confirmation"
                for item in items
            ),
            "human_decision_pending_count": sum(
                item["human_decision"] == "pending" for item in items
            ),
        },
        "non_negotiable_checks": {
            "automatic_acceptance_disabled": True,
            "rule_projection_disabled": True,
            "production_write_disabled": True,
            "accepted_requires_resolved_identity": True,
            "conflicted_gold_slots_cannot_be_downgraded_to_complete": True,
        },
        "items": items,
    }
