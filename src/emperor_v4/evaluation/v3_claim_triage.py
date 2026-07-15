from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "v3-claim-source-rebind-worklist-v1"
REPORT_SCHEMA_VERSION = "v3-claim-triage-report-v1"
POLICY_VERSION = "v3-claim-triage-stratified-v1"
RULE_ORDER = (
    "anti_nepotism",
    "talent_discovery",
    "tolerate_talent",
    "appointment_delegation",
)
DEFAULT_RULE_QUOTA = 8
PRE_SOURCE_REVIEW_SCHEMA_VERSION = "v3-claim-pre-source-review-v1"
PRE_SOURCE_REPORT_SCHEMA_VERSION = "v3-claim-pre-source-review-report-v1"
REVIEW_DISPOSITIONS = {
    "new_event_candidate_pending_source_rebind",
    "existing_aggregate_component_pending_dedup",
    "cross_rule_primary_settlement_required",
    "wrong_rule_hint",
    "insufficient_applicability",
    "insufficient_source",
}


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _walk_dicts(value: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _walk_dicts(child)


def _workset_index(
    *, ruler: str, worksets: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    unit_fields = ("unit_ref", "rule_evidence_unit_ref")
    event_fields = ("canonical_event_group", "canonical_event_key", "event_group")
    subject_fields = ("subject", "person", "object_name")
    for rule_code, documents in worksets.items():
        units: dict[str, dict[str, Any]] = {}
        for document in documents:
            for row in _walk_dicts(document):
                if row.get("ruler") not in (None, ruler):
                    continue
                unit_ref = next(
                    (str(row.get(field)) for field in unit_fields if row.get(field)), ""
                )
                if not unit_ref:
                    continue
                unit = units.setdefault(
                    unit_ref,
                    {
                        "unit_ref": unit_ref,
                        "subjects": set(),
                        "event_refs": set(),
                    },
                )
                for field in subject_fields:
                    if row.get(field):
                        unit["subjects"].add(str(row[field]))
                for field in event_fields:
                    if row.get(field):
                        unit["event_refs"].add(str(row[field]))
                for material in row.get("factor_materials") or ():
                    if isinstance(material, Mapping) and material.get("event_group"):
                        unit["event_refs"].add(str(material["event_group"]))
        result[rule_code] = [
            {
                "unit_ref": unit["unit_ref"],
                "subjects": sorted(unit["subjects"]),
                "event_refs": sorted(unit["event_refs"]),
            }
            for unit in sorted(units.values(), key=lambda item: item["unit_ref"])
        ]
    return result


def _route_hints(entry: Mapping[str, Any], rule_code: str) -> list[Mapping[str, Any]]:
    return [
        hint
        for hint in entry.get("route_hints") or ()
        if hint.get("candidate_rule_code") == rule_code
    ]


def _gate_reasons(entry: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    material = entry.get("material_membership") or {}
    if material.get("member_role") != "representative":
        reasons.append("blocked_material_not_representative")
    if (entry.get("identity_resolution") or {}).get("status") != "exact_identity_accepted_v4":
        reasons.append("blocked_identity_not_exact")
    evidence = entry.get("evidence") or ()
    if not evidence:
        reasons.append("blocked_evidence_missing")
    elif not any(
        item.get("support_level") == "direct"
        and item.get("source_slice_ref")
        and item.get("document_code")
        and item.get("slice_hash")
        and item.get("text_hash")
        for item in evidence
    ):
        reasons.append("blocked_direct_lineage_incomplete")
    return reasons


def _candidate_sort_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    direct_count = sum(
        item.get("support_level") == "direct" for item in entry.get("evidence") or ()
    )
    claim = entry.get("claim_source") or {}
    return (
        -direct_count,
        -float(claim.get("confidence") or 0),
        str(claim.get("canonical_event_key") or ""),
        str(entry.get("legacy_claim_ref") or ""),
    )


def _diversity_order(entries: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    buckets: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for entry in entries:
        claim = entry.get("claim_source") or {}
        identity = entry.get("identity_resolution") or {}
        buckets[
            (
                str(claim.get("action_type") or "unknown"),
                str(identity.get("candidate_v4_person_ref") or "unknown"),
            )
        ].append(entry)
    for bucket in buckets.values():
        bucket.sort(key=_candidate_sort_key)
    ordered: list[Mapping[str, Any]] = []
    while buckets:
        keys = sorted(
            buckets,
            key=lambda key: (_candidate_sort_key(buckets[key][0]), key),
        )
        for key in keys:
            ordered.append(buckets[key].pop(0))
            if not buckets[key]:
                del buckets[key]
    return ordered


def _select_for_rule(
    entries: Sequence[Mapping[str, Any]],
    *,
    rule_code: str,
    quota: int,
    already_selected: set[str],
) -> list[tuple[Mapping[str, Any], str]]:
    eligible = [
        entry
        for entry in entries
        if not _gate_reasons(entry)
        and _route_hints(entry, rule_code)
        and entry.get("legacy_claim_ref") not in already_selected
    ]
    by_status: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for entry in eligible:
        statuses = sorted(
            {str(hint.get("route_status") or "unknown") for hint in _route_hints(entry, rule_code)}
        )
        by_status[statuses[0]].append(entry)
    status_order = [status for status in ("candidate", "needs_review", "unknown") if status in by_status]
    status_order.extend(sorted(set(by_status) - set(status_order)))
    if not status_order:
        return []
    base, remainder = divmod(quota, len(status_order))
    status_quota = {
        status: base + (1 if index < remainder else 0)
        for index, status in enumerate(status_order)
    }
    selected: list[tuple[Mapping[str, Any], str]] = []
    used: set[str] = set()
    ordered_by_status = {
        status: _diversity_order(by_status[status]) for status in status_order
    }
    for status in status_order:
        for entry in ordered_by_status[status]:
            ref = str(entry["legacy_claim_ref"])
            if ref in used:
                continue
            selected.append((entry, status))
            used.add(ref)
            if sum(chosen_status == status for _, chosen_status in selected) >= status_quota[status]:
                break
    if len(selected) < quota:
        remainder_entries = [
            entry
            for status in status_order
            for entry in ordered_by_status[status]
            if entry["legacy_claim_ref"] not in used
        ]
        for entry in _diversity_order(remainder_entries):
            statuses = sorted(
                {str(hint.get("route_status") or "unknown") for hint in _route_hints(entry, rule_code)}
            )
            selected.append((entry, statuses[0]))
            used.add(str(entry["legacy_claim_ref"]))
            if len(selected) >= quota:
                break
    return selected


def build_v3_claim_triage(
    package: Mapping[str, Any],
    *,
    worksets: Mapping[str, Sequence[Mapping[str, Any]]],
    semantic_collision_reviews: Sequence[Mapping[str, Any]] = (),
    per_rule_quota: int = DEFAULT_RULE_QUOTA,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if package.get("schema_version") != "v3-claim-freeze-package-v1":
        raise ValueError("unsupported V3 claim package schema")
    if per_rule_quota <= 0:
        raise ValueError("per-rule quota must be positive")
    entries = list(package.get("entries") or ())
    entry_by_claim_key = {
        str((entry.get("claim_source") or {}).get("claim_key") or ""): entry
        for entry in entries
    }
    semantic_reviews_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    semantic_rule_slot_count = 0
    for review in semantic_collision_reviews:
        level = str(review.get("collision_level") or "")
        if level not in {"aggregate_component", "whole_event", "exact_lineage"}:
            raise ValueError("unsupported semantic collision review level")
        if review.get("automatic_duplicate_disposition_allowed") is not False:
            raise ValueError("semantic collision review cannot auto-dispose candidates")
        claim_keys = [str(key) for key in review.get("claim_keys") or ()]
        if not claim_keys or any(key not in entry_by_claim_key for key in claim_keys):
            raise ValueError("semantic collision review references unknown claims")
        semantic_rule_slot_count += len(claim_keys)
        for claim_key in claim_keys:
            semantic_reviews_by_claim[claim_key].append(
                {
                    "review_id": review.get("review_id"),
                    "rule_code": review.get("rule_code"),
                    "workset_unit_ref": review.get("workset_unit_ref"),
                    "collision_level": level,
                    "rationale": review.get("rationale"),
                    "automatic_duplicate_disposition_allowed": False,
                    "manual_semantic_dedup_required": True,
                }
            )
    ruler = str((package.get("scope") or {}).get("ruler") or "")
    if not ruler:
        raise ValueError("V3 claim package ruler is missing")
    workset_index = _workset_index(ruler=ruler, worksets=worksets)

    selected_by_ref: dict[str, dict[str, Any]] = {}
    selected_refs: set[str] = set()
    primary_counts: Counter[str] = Counter()
    primary_status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for rule_code in RULE_ORDER:
        chosen = _select_for_rule(
            entries,
            rule_code=rule_code,
            quota=per_rule_quota,
            already_selected=selected_refs,
        )
        if len(chosen) != per_rule_quota:
            raise ValueError(f"insufficient unique eligible claims for {rule_code}")
        for entry, route_status in chosen:
            ref = str(entry["legacy_claim_ref"])
            selected_refs.add(ref)
            selected_by_ref[ref] = {
                "entry": entry,
                "primary_rule_code": rule_code,
                "primary_route_status": route_status,
            }
            primary_counts[rule_code] += 1
            primary_status_counts[rule_code][route_status] += 1

    event_inventory = {
        item["canonical_event_key"]: item for item in package.get("event_inventory") or ()
    }
    items: list[dict[str, Any]] = []
    for rank, (ref, selection) in enumerate(selected_by_ref.items(), start=1):
        entry = selection["entry"]
        claim = entry["claim_source"]
        identity = entry["identity_resolution"]
        material = entry["material_membership"]
        event_key = str(claim.get("canonical_event_key") or "")
        route_reviews = []
        collision_rows = []
        for hint in entry.get("route_hints") or ():
            rule_code = str(hint.get("candidate_rule_code") or "")
            if rule_code not in RULE_ORDER:
                continue
            route_reviews.append(
                {
                    "rule_code": rule_code,
                    "route_status": hint.get("route_status"),
                    "candidate_lane": hint.get("candidate_lane"),
                    "candidate_direction": hint.get("candidate_direction"),
                    "route_reason": hint.get("route_reason"),
                    "accepted_as_v4_rule_binding": False,
                    "required_v4_route_review": True,
                }
            )
            exact_units = []
            same_object_units = []
            for unit in workset_index.get(rule_code, ()):
                if event_key and event_key in unit["event_refs"]:
                    exact_units.append(unit["unit_ref"])
                if claim.get("object_name") in unit["subjects"]:
                    same_object_units.append(unit["unit_ref"])
            collision_rows.append(
                {
                    "rule_code": rule_code,
                    "exact_event_ref_collision_units": sorted(set(exact_units)),
                    "same_object_possible_collision_units": sorted(set(same_object_units)),
                    "automatic_duplicate_disposition_allowed": False,
                    "manual_semantic_collision_review_required": True,
                }
            )
        evidence_refs = [
            {
                "evidence_key": evidence.get("evidence_key"),
                "source_slice_ref": evidence.get("source_slice_ref"),
                "document_code": evidence.get("document_code"),
                "slice_hash": evidence.get("slice_hash"),
                "text_hash": evidence.get("text_hash"),
                "support_level": evidence.get("support_level"),
                "span_type": (evidence.get("span_payload") or {}).get("span_type"),
                "quote_preview": evidence.get("quote_preview"),
                "source_title": evidence.get("source_title") or None,
                "source_url": evidence.get("source_url") or None,
            }
            for evidence in entry.get("evidence") or ()
        ]
        item: dict[str, Any] = {
            "work_item_ref": "V3CR-" + _hash((package["package_sha256"], ref))[:20].upper(),
            "legacy_claim_ref": ref,
            "source_row_fingerprint": entry.get("source_row_fingerprint"),
            "entry_sha256": entry.get("entry_sha256"),
            "primary_rule_code": selection["primary_rule_code"],
            "primary_route_status": selection["primary_route_status"],
            "route_reviews": sorted(route_reviews, key=lambda row: row["rule_code"]),
            "canonical_event_key": event_key,
            "event_group_claim_refs": (event_inventory.get(event_key) or {}).get("claim_refs", [ref]),
            "automatic_atom_merge_allowed": False,
            "claim_summary": claim.get("claim_summary"),
            "action_type": claim.get("action_type"),
            "time_context": claim.get("time_context"),
            "object_name": claim.get("object_name"),
            "outcome": claim.get("outcome"),
            "claim_confidence_schedule_tiebreaker_only": claim.get("confidence"),
            "identity_resolution": identity,
            "material_membership": material,
            "evidence_refs": evidence_refs,
            "existing_workset_collision_review": sorted(
                collision_rows, key=lambda row: row["rule_code"]
            ),
            "known_semantic_collision_reviews": sorted(
                semantic_reviews_by_claim.get(str(claim.get("claim_key") or ""), ()),
                key=lambda row: (str(row["rule_code"]), str(row["workset_unit_ref"])),
            ),
            "selection_rank": rank,
            "selection_reasons": [
                "scarce_rule_first_primary_quota",
                "route_status_stratification",
                "person_and_action_diversity",
                "confidence_used_as_schedule_tiebreaker_only",
            ],
            "required_reviews": [
                "source_rebind",
                "identity_confirmation",
                "semantic_dedup",
                "rule_applicability",
                "passage_support",
                "direction_and_factor_semantics",
                "existing_workset_collision",
            ],
            "disposition": "scheduled_first_cohort",
            "formal_v4_assertion": False,
            "counts_toward_historical_coverage": False,
        }
        items.append(item)

    disposition_rows = []
    disposition_counts: Counter[str] = Counter()
    for entry in entries:
        ref = str(entry["legacy_claim_ref"])
        gate_reasons = _gate_reasons(entry)
        routed_rules = sorted(
            {
                str(hint.get("candidate_rule_code"))
                for hint in entry.get("route_hints") or ()
                if hint.get("candidate_rule_code") in RULE_ORDER
            }
        )
        if ref in selected_refs:
            disposition = "scheduled_first_cohort"
            reasons: list[str] = []
        elif gate_reasons:
            disposition = "blocked_gate"
            reasons = gate_reasons
        elif routed_rules:
            disposition = "deferred_capacity_not_dropped"
            reasons = ["eligible_after_first_cohort"]
        else:
            disposition = "unrouted_candidate_not_dropped"
            reasons = ["no_i5b_route_hint"]
        disposition_counts[disposition] += 1
        disposition_rows.append(
            {
                "legacy_claim_ref": ref,
                "routed_rule_codes": routed_rules,
                "disposition": disposition,
                "reasons": reasons,
            }
        )

    route_hint_count = sum(
        hint.get("candidate_rule_code") in RULE_ORDER
        for entry in entries
        for hint in entry.get("route_hints") or ()
    )
    routed_claim_count = sum(
        any(hint.get("candidate_rule_code") in RULE_ORDER for hint in entry.get("route_hints") or ())
        for entry in entries
    )
    duplicate_event_groups = [
        item for item in package.get("event_inventory") or () if item.get("claim_count", 0) > 1
    ]
    summary = {
        "input_claim_count": len(entries),
        "routed_unique_claim_count": routed_claim_count,
        "route_hint_count": route_hint_count,
        "scheduled_unique_claim_count": len(items),
        "scheduled_primary_rule_counts": dict(sorted(primary_counts.items())),
        "scheduled_primary_route_status_counts": {
            rule: dict(sorted(counts.items())) for rule, counts in sorted(primary_status_counts.items())
        },
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "duplicate_canonical_event_group_count": len(duplicate_event_groups),
        "dropped_claim_count": 0,
        "formal_v4_assertion_count": 0,
        "historical_coverage_accepted_claim_count": 0,
        "model_call_count": 0,
        "v3_database_write_count": 0,
        "v4_database_write_count": 0,
    }
    worklist: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "task_code": "I5B-V3-CLAIM-SOURCE-REBIND-LISHIMIN-01",
        "status": "first_source_rebind_cohort_scheduled_report_only",
        "input_package_sha256": package["package_sha256"],
        "source_freeze_ref": package["source"]["source_freeze_ref"],
        "ruler": ruler,
        "capacity_policy": {
            "unique_claim_capacity": per_rule_quota * len(RULE_ORDER),
            "per_rule_primary_quota": per_rule_quota,
            "scarcity_first_rule_order": list(RULE_ORDER),
            "appointment_route_status_target": {"candidate": 4, "needs_review": 4},
            "selection_is_business_score": False,
        },
        "summary": summary,
        "items": items,
        "inventory_dispositions": disposition_rows,
        "declarations": {
            "report_only": True,
            "v3_routes_inherited_as_v4_bindings": False,
            "automatic_event_atom_merge_allowed": False,
            "old_workset_or_gold_modified": False,
            "historical_coverage_status_changed": False,
            "formal_scoring_allowed": False,
        },
    }
    worklist["worklist_sha256"] = _hash(worklist)

    exact_collision_count = sum(
        bool(row["exact_event_ref_collision_units"])
        for item in items
        for row in item["existing_workset_collision_review"]
    )
    possible_collision_count = sum(
        bool(row["same_object_possible_collision_units"])
        for item in items
        for row in item["existing_workset_collision_review"]
    )
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": "triaged_without_v4_fact_acceptance",
        "input_package_sha256": package["package_sha256"],
        "worklist_sha256": worklist["worklist_sha256"],
        "ruler": ruler,
        "summary": summary,
        "event_dedup_diagnostic": {
            "duplicate_canonical_event_groups": duplicate_event_groups,
            "automatic_atom_merge_allowed": False,
        },
        "existing_workset_collision_diagnostic": {
            "indexed_units_by_rule": workset_index,
            "selected_rule_review_exact_event_collision_count": exact_collision_count,
            "selected_rule_review_same_object_possible_collision_count": possible_collision_count,
            "different_identifier_namespaces_limit_exact_matching": True,
            "manual_semantic_review_required": True,
        },
        "human_audited_semantic_collision_diagnostic": {
            "review_groups": list(semantic_collision_reviews),
            "aggregate_component_rule_slot_count": semantic_rule_slot_count,
            "unique_claim_count": len(semantic_reviews_by_claim),
            "automatic_duplicate_disposition_allowed": False,
            "coverage_or_fact_status_changed": False,
        },
        "next_gate": {
            "required": "complete_source_rebind_and_human_semantic_disposition",
            "coverage_completion_allowed": False,
        },
        "declarations": worklist["declarations"],
    }
    report["report_sha256"] = _hash(report)
    return worklist, report


def build_v3_claim_pre_source_review_report(
    worklist: Mapping[str, Any], review: Mapping[str, Any]
) -> dict[str, Any]:
    if worklist.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported V3 Claim worklist schema")
    if review.get("schema_version") != PRE_SOURCE_REVIEW_SCHEMA_VERSION:
        raise ValueError("unsupported V3 Claim pre-source review schema")
    if review.get("input_worklist_sha256") != worklist.get("worklist_sha256"):
        raise ValueError("pre-source review worklist hash mismatch")
    items = list(worklist.get("items") or ())
    item_by_ref = {str(item.get("legacy_claim_ref") or ""): item for item in items}
    rows = list(review.get("reviews") or ())
    row_by_ref = {str(row.get("legacy_claim_ref") or ""): row for row in rows}
    if len(row_by_ref) != len(rows) or set(row_by_ref) != set(item_by_ref):
        raise ValueError("pre-source review must cover every worklist Claim exactly once")
    disposition_counts: Counter[str] = Counter()
    rule_disposition_counts: dict[str, Counter[str]] = defaultdict(Counter)
    new_event_refs: list[str] = []
    for ref, row in row_by_ref.items():
        item = item_by_ref[ref]
        if row.get("primary_rule_code") != item.get("primary_rule_code"):
            raise ValueError("pre-source review primary rule mismatch")
        disposition = str(row.get("recommended_disposition") or "")
        if disposition not in REVIEW_DISPOSITIONS:
            raise ValueError("pre-source review disposition is invalid")
        if not row.get("rationale") or not isinstance(row.get("missing_inputs"), list):
            raise ValueError("pre-source review requires rationale and missing inputs")
        disposition_counts[disposition] += 1
        rule_disposition_counts[str(row["primary_rule_code"])][disposition] += 1
        if disposition == "new_event_candidate_pending_source_rebind":
            new_event_refs.append(ref)
    declarations = review.get("declarations") or {}
    if any(
        declarations.get(field) is not expected
        for field, expected in (
            ("formal_v4_assertion_created", False),
            ("historical_coverage_status_changed", False),
            ("old_workset_or_gold_modified", False),
            ("formal_scoring_allowed", False),
        )
    ):
        raise ValueError("pre-source review safety declarations are incomplete")
    report: dict[str, Any] = {
        "schema_version": PRE_SOURCE_REPORT_SCHEMA_VERSION,
        "status": "first_cohort_pre_source_review_complete_without_fact_acceptance",
        "input_worklist_sha256": worklist["worklist_sha256"],
        "input_review_sha256": _hash(review),
        "ruler": worklist["ruler"],
        "summary": {
            "reviewed_claim_count": len(rows),
            "recommended_disposition_counts": dict(sorted(disposition_counts.items())),
            "rule_disposition_counts": {
                rule: dict(sorted(counts.items()))
                for rule, counts in sorted(rule_disposition_counts.items())
            },
            "new_event_candidate_pending_source_rebind_count": len(new_event_refs),
            "formal_v4_assertion_count": 0,
            "historical_coverage_accepted_claim_count": 0,
            "model_call_count": 0,
            "database_write_count": 0,
        },
        "new_event_candidate_claim_refs": sorted(new_event_refs),
        "next_gate": {
            "required": "v4_source_rebind_for_new_and_unresolved_candidates",
            "automatic_assertion_acceptance_allowed": False,
        },
        "declarations": dict(declarations),
    }
    report["report_sha256"] = _hash(report)
    return report
