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
    passages = payload.get("source_passages")
    if not passages:
        raise ValueError("blind kernel 输入缺少 source_passages")
    passage_refs = [str(item.get("passage_code") or "") for item in passages]
    if any(not passage_ref for passage_ref in passage_refs):
        raise ValueError("blind kernel source_passages 缺少 passage_code")
    if len(set(passage_refs)) != len(passage_refs):
        raise ValueError("blind kernel source_passages 包含重复 passage_code")
    missing_lineage = sorted(
        {
            str(row.get("source_passage_ref") or "")
            for row in payload["assertions"]
            if str(row.get("source_passage_ref") or "") not in passage_refs
        }
    )
    if missing_lineage:
        raise ValueError(f"blind kernel assertion passage lineage 不存在: {missing_lineage}")


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
        "input_source_passage_count": len(payload["source_passages"]),
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
    """Post-run scorer over independently frozen boundaries, never candidate decisions."""

    if sealed_gold.get("candidate_input_sha256") != run_report.get("input_sha256"):
        raise ValueError("sealed Gold 与 blind input hash 不一致")
    if sealed_gold.get("status") != "frozen":
        raise ValueError("sealed Gold 尚未冻结")
    if sealed_gold.get("frozen_without_candidate_access") is not True:
        raise ValueError("sealed Gold 未声明在隔离 candidate 的条件下冻结")
    if sealed_gold.get("candidate_decisions") is not None:
        raise ValueError("sealed Gold 不得包含 candidate_decisions 循环裁定")

    packets = run_report.get("packets") or []
    gold_rows = sealed_gold.get("gold_episodes") or []
    if not gold_rows:
        raise ValueError("sealed Gold 缺少 gold_episodes")
    gold_by_code = {}
    assertion_owner = {}
    for row in gold_rows:
        code = str(row.get("gold_episode_code") or "")
        if not code or code in gold_by_code:
            raise ValueError("sealed Gold episode code 缺失或重复")
        refs = frozenset(row.get("expected_assertion_refs") or ())
        gold_by_code[code] = {**row, "assertion_refs": refs}
        for assertion_ref in refs:
            previous = assertion_owner.setdefault(assertion_ref, code)
            if previous != code:
                raise ValueError(f"Gold assertion 被多个 episode 占用: {assertion_ref}")

    candidate_sets = {
        packet["semantic_fingerprint"]: frozenset(
            link["assertion_ref"] for link in packet.get("assertion_links") or ()
        )
        for packet in packets
    }
    all_candidate_assertions = set().union(*candidate_sets.values()) if candidate_sets else set()
    unknown_gold_assertions = sorted(set(assertion_owner) - all_candidate_assertions)
    if unknown_gold_assertions:
        raise ValueError(
            f"sealed Gold 引用了 blind input 中不存在的 assertion: {unknown_gold_assertions}"
        )

    exact_candidate_matches = {}
    exact_gold_matches = {}
    candidate_overlaps = {}
    for fingerprint, candidate_refs in candidate_sets.items():
        overlaps = {
            code
            for code, gold in gold_by_code.items()
            if candidate_refs & gold["assertion_refs"]
        }
        candidate_overlaps[fingerprint] = overlaps
        exact = [
            code
            for code in overlaps
            if candidate_refs == gold_by_code[code]["assertion_refs"]
        ]
        if len(exact) == 1:
            exact_candidate_matches[fingerprint] = exact[0]
            exact_gold_matches[exact[0]] = fingerprint

    gold_candidate_overlaps = {
        code: {
            fingerprint
            for fingerprint, refs in candidate_sets.items()
            if refs & gold["assertion_refs"]
        }
        for code, gold in gold_by_code.items()
    }
    wrong_merge_fingerprints = sorted(
        fingerprint
        for fingerprint, overlaps in candidate_overlaps.items()
        if len(overlaps) > 1
    )
    wrong_split_gold_codes = sorted(
        code
        for code, overlaps in gold_candidate_overlaps.items()
        if len(overlaps) > 1
    )
    cross_ruler_fingerprints = []
    packet_by_fingerprint = {
        packet["semantic_fingerprint"]: packet for packet in packets
    }
    for fingerprint, overlaps in candidate_overlaps.items():
        contexts = {
            str(gold_by_code[code].get("evaluation_context") or "")
            for code in overlaps
        }
        packet_context = str(
            packet_by_fingerprint[fingerprint].get("evaluation_context") or ""
        )
        if len(contexts) > 1 or (contexts and packet_context not in contexts):
            cross_ruler_fingerprints.append(fingerprint)

    catastrophic_pairs = {
        frozenset(pair)
        for pair in sealed_gold.get("catastrophic_must_not_merge_pairs") or ()
        if len(pair) == 2
    }
    catastrophic_wrong_merge_fingerprints = sorted(
        fingerprint
        for fingerprint, overlaps in candidate_overlaps.items()
        if any(pair <= overlaps for pair in catastrophic_pairs)
    )
    lineage_complete_count = sum(
        bool(item.get("assertion_links"))
        and all(link.get("source_passage_ref") for link in item["assertion_links"])
        for item in packets
    )
    identity_block_count = sum(bool(item.get("identity_blockers")) for item in packets)
    human_review_count = sum(item.get("human_review_required") is True for item in packets)
    unmatched_gold = sorted(set(gold_by_code) - set(exact_gold_matches))
    source_only_misses = sorted(
        code
        for code in unmatched_gold
        if not gold_by_code[code]["assertion_refs"]
        and gold_by_code[code].get("required_source_passage_refs")
    )
    return {
        "schema_version": 1,
        "status": "blind_scored_after_sealed_gold_opened",
        "metrics": {
            "autonomous_boundary_recall": (
                len(exact_gold_matches) / len(gold_by_code) if gold_by_code else None
            ),
            "candidate_precision": (
                len(exact_candidate_matches) / len(packets) if packets else None
            ),
            "wrong_merge_count": len(wrong_merge_fingerprints),
            "wrong_split_count": len(wrong_split_gold_codes),
            "catastrophic_wrong_merge_count": len(
                catastrophic_wrong_merge_fingerprints
            ),
            "cross_ruler_contamination_count": len(cross_ruler_fingerprints),
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
        "diagnostics": {
            "exact_gold_matches": exact_gold_matches,
            "exact_candidate_matches": exact_candidate_matches,
            "wrong_merge_fingerprints": wrong_merge_fingerprints,
            "wrong_split_gold_episode_codes": wrong_split_gold_codes,
            "catastrophic_wrong_merge_fingerprints": catastrophic_wrong_merge_fingerprints,
            "cross_ruler_contamination_fingerprints": cross_ruler_fingerprints,
            "unmatched_gold_episode_codes": unmatched_gold,
            "assertion_layer_miss_gold_episode_codes": source_only_misses,
            "reconciliation_layer_error_gold_episode_codes": sorted(
                set(unmatched_gold) - set(source_only_misses)
            ),
            "unassigned_candidate_assertion_refs": sorted(
                all_candidate_assertions - set(assertion_owner)
            ),
        },
        "accepted_metrics": {
            "status": "not_computable_before_independent_human_acceptance",
            "accepted_recall": None,
            "accepted_precision": None,
        },
    }
