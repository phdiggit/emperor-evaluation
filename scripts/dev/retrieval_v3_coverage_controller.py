from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.object_pool_aliases import normalize_object_alias  # noqa: E402
from scripts.dev.retrieval_v3_coverage_convergence import (  # noqa: E402
    apply_convergence,
    build_consumer_handoffs, build_convergence_delta,
    build_gap_routes, build_reconciliation_index,
    build_repair_ledger, score_lineage_gaps,
)
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402

DEFAULT_ITEM_CODE = "I5B"; DEFAULT_RULE_CODE = "appointment_delegation"
ACTIVE_STATUSES = ("active", "needs_review")
APPOINTMENT_TERMS = ("任命", "任用", "委任", "授", "拜", "擢", "命", "令", "使", "统", "領", "领", "留守", "托付")
RESPONSIBILITY_TERMS = ("负责", "主持", "掌", "典", "总", "统", "领", "修订", "征", "讨", "守", "治", "辅政")
RESULT_TERMS = ("成功", "平定", "攻克", "灭", "破", "败", "失守", "治理", "完成", "奏效", "有功", "获罪", "伏诛", "害民")
EMPTY_OUTCOME_SUPPORT = {"", "none", "unknown", "unclear", "not_applicable", "context_only"}; build_gap_router = build_gap_routes
VERIFIED_RECONCILIATION_DECISIONS = {"already_covered", "rebuild_event_group"}
RECONCILIATION_ROUTES = dict(
    already_covered=("none", True, False), rebuild_event_group=("rebuild_event_groups", False, True),
    reextract_cached_source=("claim_extraction", False, True), fetch_missing_source=("source_refinement", False, True),
    identity_mismatch=("identity_review", True, False),
    inventory_needs_review=("expected_event_inventory_review", True, False),
    insufficient_for_scoring=("expected_event_inventory_review", True, False),
)


def text(value: Any) -> str:
    return str(value or "").strip()


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def contains_any(value: Any, terms: Sequence[str]) -> bool:
    normalized = text(value).lower()
    return any(term.lower() in normalized for term in terms)


def timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    raw = text(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def later_than(left: Any, right: Any) -> bool:
    left_dt = timestamp(left)
    right_dt = timestamp(right)
    if left_dt is None:
        return False
    if right_dt is None:
        return True
    try:
        return left_dt > right_dt
    except TypeError:
        return text(left) > text(right)


def list_texts(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [text(item) for item in value if text(item)]

def identity_key(row: Mapping[str, Any]) -> str:
    object_id = as_int(row.get("object_id"))
    if object_id:
        return f"id:{object_id}"
    return "name:" + normalize_object_alias(row.get("object_name"))


def claim_signals(row: Mapping[str, Any]) -> tuple[bool, bool, bool]:
    payload = row.get("fact_payload") if isinstance(row.get("fact_payload"), Mapping) else {}
    action = " ".join(
        text(value)
        for value in (
            row.get("action_type"),
            row.get("fact_type"),
            payload.get("action_type"),
            payload.get("relation"),
        )
    )
    responsibility = " ".join(
        text(value)
        for value in (
            row.get("office_or_domain"),
            payload.get("office_or_domain"),
            payload.get("task"),
            payload.get("responsibility"),
            row.get("claim_summary"),
        )
    )
    outcome = " ".join(
        text(value)
        for value in (
            row.get("outcome"),
            payload.get("outcome"),
            payload.get("result"),
            row.get("claim_summary"),
        )
    )
    outcome_support = text(row.get("outcome_support") or payload.get("outcome_support")).lower()
    has_appointment = contains_any(action + " " + responsibility, APPOINTMENT_TERMS)
    has_responsibility = bool(text(row.get("office_or_domain")) or text(payload.get("office_or_domain"))) or contains_any(
        action + " " + responsibility, RESPONSIBILITY_TERMS
    )
    has_result = outcome_support not in EMPTY_OUTCOME_SUPPORT or contains_any(outcome, RESULT_TERMS)
    return has_appointment, has_responsibility, has_result


def merge_rows(
    claim_rows: Sequence[Mapping[str, Any]],
    downstream_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    source_rows: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    aliases: dict[tuple[str, str], str] = {}
    for row in (*target_rows, *claim_rows, *source_rows, *downstream_rows):
        emperor = text(row.get("emperor_name"))
        object_id = as_int(row.get("object_id"))
        names = [row.get("object_name"), row.get("canonical_name")]
        if isinstance(row.get("names"), Sequence) and not isinstance(row.get("names"), (str, bytes)):
            names.extend(row.get("names") or [])
        if emperor and object_id:
            for raw_name in names:
                name = normalize_object_alias(raw_name)
                if name:
                    aliases.setdefault((emperor, name), f"id:{object_id}")

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for source, rows in (
        ("target", target_rows),
        ("source", source_rows),
        ("claim", claim_rows),
        ("downstream", downstream_rows),
    ):
        for raw_row in rows:
            row = dict(raw_row)
            emperor = text(row.get("emperor_name"))
            name = normalize_object_alias(row.get("object_name"))
            key = identity_key(row)
            if key.startswith("name:"):
                key = aliases.get((emperor, name), key)
            merged_row = merged.setdefault(
                (emperor, key),
                {
                    "emperor_name": emperor,
                    "object_id": as_int(row.get("object_id")) or None,
                    "object_name": text(row.get("canonical_name") or row.get("object_name")),
                    "object_type": text(row.get("object_type")),
                    "target_attached": False,
                    "active_claim_count": 0,
                    "source_document_count": 0,
                    "source_slice_count": 0,
                    "claimed_source_slice_count": 0,
                    "evidence_count": 0,
                    "event_group_count": 0,
                    "event_group_member_count": 0,
                    "_event_group_keys": set(),
                    "material_claim_count": 0,
                    "candidate_count": 0,
                    "unresolved_candidate_count": 0,
                    "binding_count": 0,
                    "scoring_binding_count": 0,
                    "factor_judgment_count": 0, "scoring_factor_judgment_count": 0,
                    "material_score_count": 0, "rule_score_cluster_count": 0,
                    "has_appointment": False,
                    "has_responsibility": False,
                    "has_result": False,
                    "_chain_by_group": {},
                    "latest_claim_at": None,
                    "latest_consumed_at": None,
                    "latest_factor_at": None, "latest_material_score_at": None, "latest_rule_cluster_at": None,
                },
            )
            if not merged_row["object_id"] and as_int(row.get("object_id")):
                merged_row["object_id"] = as_int(row.get("object_id"))
            if not merged_row["object_name"]:
                merged_row["object_name"] = text(row.get("canonical_name") or row.get("object_name"))
            if source == "target":
                merged_row["target_attached"] = True
                if text(row.get("object_type")):
                    merged_row["object_type"] = text(row.get("object_type"))
            elif source == "source":
                merged_row["source_slice_count"] += as_int(row.get("source_slice_count"))
                merged_row["claimed_source_slice_count"] += as_int(row.get("claimed_source_slice_count"))
                merged_row["source_document_count"] = max(
                    as_int(merged_row.get("source_document_count")), as_int(row.get("source_document_count"))
                )
            elif source == "claim":
                for field in (
                    "active_claim_count",
                    "evidence_count",
                    "event_group_member_count",
                ):
                    merged_row[field] += as_int(row.get(field))
                group_keys = row.get("event_group_keys") or []
                if isinstance(group_keys, Sequence) and not isinstance(group_keys, (str, bytes)):
                    merged_row["_event_group_keys"].update(text(value) for value in group_keys if text(value))
                appointment, responsibility, result = claim_signals(row)
                merged_row["has_appointment"] |= appointment
                merged_row["has_responsibility"] |= responsibility
                merged_row["has_result"] |= result
                for group_key in group_keys:
                    chain = merged_row["_chain_by_group"].setdefault(
                        text(group_key), {"appointment": False, "responsibility": False, "result": False}
                    )
                    chain["appointment"] |= appointment
                    chain["responsibility"] |= responsibility
                    chain["result"] |= result
                if later_than(row.get("latest_claim_at"), merged_row["latest_claim_at"]):
                    merged_row["latest_claim_at"] = row.get("latest_claim_at")
            else:
                for field in (
                    "material_claim_count",
                    "candidate_count",
                    "unresolved_candidate_count",
                    "binding_count",
                    "scoring_binding_count",
                    "factor_judgment_count", "scoring_factor_judgment_count",
                    "material_score_count", "rule_score_cluster_count",
                ):
                    merged_row[field] += as_int(row.get(field))
                if later_than(row.get("latest_consumed_at"), merged_row["latest_consumed_at"]):
                    merged_row["latest_consumed_at"] = row.get("latest_consumed_at")
                for field in ("latest_factor_at", "latest_material_score_at", "latest_rule_cluster_at"):
                    if later_than(row.get(field), merged_row[field]):
                        merged_row[field] = row.get(field)
    result = []
    for row in merged.values():
        row["event_group_count"] = len(row.pop("_event_group_keys"))
        chains = row.pop("_chain_by_group")
        row["chain_ready"] = any(all(chain.values()) for chain in chains.values())
        result.append(row)
    identities_by_name: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in result:
        object_id = as_int(row.get("object_id"))
        name_key = normalize_object_alias(row.get("object_name"))
        if object_id and name_key:
            identities_by_name[(text(row.get("emperor_name")), name_key)].add(object_id)
    for row in result:
        ids = identities_by_name[(text(row.get("emperor_name")), normalize_object_alias(row.get("object_name")))]
        row["identity_conflict_ids"] = sorted(ids) if len(ids) > 1 else []
    return sorted(result, key=lambda row: (text(row["emperor_name"]), text(row["object_name"])))


def gap(gap_type: str, action: str, reason: str, *, blocking: bool = False) -> dict[str, Any]:
    return {"gap_type": gap_type, "next_action": action, "reason": reason, "blocking": blocking}


def assess_object(row: Mapping[str, Any], *, rule_code: str = DEFAULT_RULE_CODE) -> dict[str, Any]:
    result = dict(row)
    claim_count = as_int(row.get("active_claim_count"))
    downstream_started = any(
        as_int(row.get(field))
        for field in ("candidate_count", "binding_count", "factor_judgment_count")
    )
    chain_ready = bool(row.get("chain_ready"))
    native_claim_chain_relevant = rule_code == DEFAULT_RULE_CODE and chain_ready
    scoring_relevant = bool(native_claim_chain_relevant or downstream_started)
    gaps: list[dict[str, Any]] = []
    if row.get("identity_conflict_ids"):
        gaps.append(
            gap(
                "identity_conflict",
                "identity_review",
                "the same normalized name resolves to multiple v3 object identities for this emperor",
                blocking=True,
            )
        )
    if (row.get("target_attached") or as_int(row.get("source_slice_count"))) and not claim_count:
        gaps.append(gap("claim_cache_missing", "object_source_cache", "target object has no active claim cache", blocking=True))
    if claim_count and not row.get("object_id"):
        gaps.append(gap("identity_missing", "identity_review", "claim cache object has no resolved v3 object identity", blocking=True))
    if claim_count and as_int(row.get("evidence_count")) == 0:
        gaps.append(gap("source_evidence_missing", "object_source_cache", "active claims have no claim evidence", blocking=True))
    unclaimed_slices = max(as_int(row.get("source_slice_count")) - as_int(row.get("claimed_source_slice_count")), 0)
    result["unclaimed_source_slice_count"] = unclaimed_slices
    if unclaimed_slices:
        gaps.append(
            gap(
                "source_slice_unclaimed",
                "claim_extraction_coverage_review",
                "cached source slices are not referenced by any active claim evidence",
            )
        )
    if claim_count and as_int(row.get("event_group_member_count")) < claim_count:
        gaps.append(
            gap(
                "event_group_stale_or_missing",
                "rebuild_event_groups",
                "not every active claim is represented in the rebuildable event-group shadow",
            )
        )
    if claim_count and row.get("has_appointment") and not row.get("has_responsibility"):
        gaps.append(gap("responsibility_missing", "claim_source_refinement", "appointment signal lacks a concrete duty or task"))
    if claim_count and row.get("has_appointment") and not row.get("has_result"):
        gaps.append(gap("result_feedback_missing", "claim_source_refinement", "appointment chain lacks result or continuity feedback"))
    if native_claim_chain_relevant and claim_count and as_int(row.get("material_claim_count")) == 0:
        gaps.append(gap("material_claim_missing", "promote_claim_cache_to_material", "ready claim chain has not entered native material claims", blocking=True))
    if scoring_relevant and as_int(row.get("material_claim_count")) and as_int(row.get("candidate_count")) == 0:
        gaps.append(gap("candidate_missing", "route_material_candidates", f"material claims have no {rule_code} candidate", blocking=True))
    if scoring_relevant and as_int(row.get("candidate_count")) and as_int(row.get("binding_count")) == 0:
        gaps.append(gap("binding_missing", "candidate_review_and_binding", "rule candidates have no formal binding", blocking=True))
    if as_int(row.get("scoring_binding_count")) and as_int(row.get("factor_judgment_count")) < as_int(row.get("scoring_binding_count")):
        gaps.append(gap("factorization_missing", "build_factorization_worklist", "scoring bindings are not fully factorized", blocking=True))
    for gap_type, reason in score_lineage_gaps(row):
        gaps.append(gap(gap_type, "run_rule_scorer_dry_run", reason, blocking=True))
    if downstream_started and later_than(row.get("latest_claim_at"), row.get("latest_consumed_at")):
        gaps.append(gap("consumption_stale", "rerun_native_consumers", "claim cache changed after the latest downstream consumption"))
    result["chain_ready"] = chain_ready
    result["scoring_relevant"] = scoring_relevant
    result["coverage_status"] = "blocked" if any(item["blocking"] for item in gaps) else ("gap" if gaps else "complete")
    result["gaps"] = gaps
    return result


def claim_group_index(claim_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in claim_rows:
        group_keys = list_texts(row.get("event_group_keys"))
        if not group_keys:
            continue
        object_token = f"id:{as_int(row.get('object_id'))}" if as_int(row.get("object_id")) else "name:" + normalize_object_alias(row.get("object_name"))
        payload = row.get("fact_payload") if isinstance(row.get("fact_payload"), Mapping) else {}
        blob = " ".join(
            text(value)
            for value in (
                row.get("claim_summary"),
                row.get("action_type"),
                row.get("fact_type"),
                row.get("office_or_domain"),
                row.get("outcome"),
                row.get("outcome_support"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            )
        )
        appointment, responsibility, result = claim_signals(row)
        for group_key in group_keys:
            group = groups.setdefault(
                (text(row.get("emperor_name")), object_token, group_key),
                {
                    "emperor_name": text(row.get("emperor_name")),
                    "object_id": as_int(row.get("object_id")) or None,
                    "object_name": text(row.get("object_name")),
                    "group_key": group_key,
                    "text": "",
                    "has_appointment": False,
                    "has_responsibility": False,
                    "has_result": False,
                },
            )
            group["text"] += " " + blob
            group["has_appointment"] |= appointment
            group["has_responsibility"] |= responsibility
            group["has_result"] |= result
    return list(groups.values())


def event_matches_object(event: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    if text(event.get("emperor_name")) != text(row.get("emperor_name")):
        return False
    event_id = as_int(event.get("object_id"))
    row_id = as_int(row.get("object_id"))
    if event_id and row_id:
        return event_id == row_id
    return normalize_object_alias(event.get("object_name")) == normalize_object_alias(row.get("object_name"))


def assess_expected_event(event: Mapping[str, Any], groups: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    event_terms = list_texts(event.get("event_anchor_terms"))
    duty_terms = list_texts(event.get("duty_anchor_terms"))
    outcome_terms = list_texts(event.get("outcome_anchor_terms"))
    best: dict[str, Any] | None = None
    for group in groups:
        if not event_matches_object(event, group):
            continue
        blob = text(group.get("text"))
        matched_event_terms = [term for term in event_terms if term in blob]
        matched_duty_terms = [term for term in duty_terms if term in blob]
        matched_outcome_terms = [term for term in outcome_terms if term in blob]
        required_event_term_count = min(2, len(event_terms))
        facets = {
            "event_anchor": len(matched_event_terms) >= required_event_term_count,
            "appointment": bool(group.get("has_appointment")),
            "duty": bool(matched_duty_terms or group.get("has_responsibility")),
            "outcome": bool(matched_outcome_terms),
        }
        candidate = {
            "group_key": text(group.get("group_key")),
            "facets": facets,
            "matched_event_terms": matched_event_terms,
            "matched_duty_terms": matched_duty_terms,
            "matched_outcome_terms": matched_outcome_terms,
            "required_event_term_count": required_event_term_count,
            "facet_count": sum(facets.values()),
        }
        if best is None or candidate["facet_count"] > best["facet_count"]:
            best = candidate
    best = best or {
        "group_key": "",
        "facets": {"event_anchor": False, "appointment": False, "duty": False, "outcome": False},
        "matched_event_terms": [],
        "matched_duty_terms": [],
        "matched_outcome_terms": [],
        "required_event_term_count": min(2, len(event_terms)),
        "facet_count": 0,
    }
    status = "covered" if best["facet_count"] == 4 else ("partial" if best["facet_count"] else "missing")
    return {
        "event_inventory_code": text(event.get("event_inventory_code")),
        "event_label": text(event.get("event_label")),
        "importance": text(event.get("importance")),
        "direction": text(event.get("direction")),
        "coverage_status": status,
        "matched_group_key": best["group_key"],
        "matched_facets": best["facets"],
        "matched_event_terms": best["matched_event_terms"],
        "matched_duty_terms": best["matched_duty_terms"],
        "matched_outcome_terms": best["matched_outcome_terms"],
        "required_event_term_count": best["required_event_term_count"],
        "source_leads": event.get("source_leads") or [],
        "scoring_allowed": False,
    }


def apply_expected_event_inventory(
    objects: Sequence[Mapping[str, Any]],
    claim_rows: Sequence[Mapping[str, Any]],
    expected_events: Sequence[Mapping[str, Any]],
    reconciliation: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    groups = claim_group_index(claim_rows)
    event_records = [row for row in expected_events if text(row.get("record_type")) != "object_assessment"]
    assessment_records = [row for row in expected_events if text(row.get("record_type")) == "object_assessment"]
    results: list[dict[str, Any]] = []
    for raw_row in objects:
        row = dict(raw_row)
        events = [event for event in event_records if event_matches_object(event, row)]
        object_assessments = [record for record in assessment_records if event_matches_object(record, row)]
        assessments = [assess_expected_event(event, groups) for event in events]
        for assessment in assessments:
            reconciled = (reconciliation or {}).get(text(assessment.get("event_inventory_code")))
            if not reconciled:
                assessment["repair_state"] = "not_reconciled"
                continue
            current = dict(reconciled.get("current") or {})
            history = list(reconciled.get("history") or [])
            decision = text(current.get("decision"))
            verified = text(current.get("gate_mode")) == "repair_verification" and decision in VERIFIED_RECONCILIATION_DECISIONS
            next_action, terminal, retryable = RECONCILIATION_ROUTES.get(decision, ("reconciliation_review", False, False))
            assessment.update({
                "mechanical_coverage_status": assessment["coverage_status"],
                "coverage_status": "covered" if verified else assessment["coverage_status"],
                "reconciliation_decision": decision,
                "reconciliation_gate_mode": text(current.get("gate_mode")),
                "reconciliation_attempt_count": len(history),
                "reconciliation_previous_decisions": [text(item.get("decision")) for item in history[:-1]],
                "repair_state": "verified_covered" if verified else "pending_repair",
                "repair_terminal": terminal,
                "repair_retryable": retryable,
                "repair_next_action": next_action,
            })
        inventory_verdicts = list_texts([record.get("inventory_verdict") for record in object_assessments])
        if events:
            historical_status = "assessed"
        elif "no_relevant_events" in inventory_verdicts:
            historical_status = "assessed_no_relevant_events"
        elif "identity_mismatch_needs_review" in inventory_verdicts:
            historical_status = "identity_mismatch_needs_review"
        else:
            historical_status = "unassessed"
        row["historical_event_coverage_status"] = historical_status
        row["inventory_verdicts"] = inventory_verdicts
        row["expected_event_count"] = len(assessments)
        row["covered_expected_event_count"] = sum(item["coverage_status"] == "covered" for item in assessments)
        row["partial_expected_event_count"] = sum(item["coverage_status"] == "partial" for item in assessments)
        row["missing_expected_event_count"] = sum(item["coverage_status"] == "missing" for item in assessments)
        row["expected_event_assessments"] = assessments
        uncovered_major = [
            item for item in assessments if item["importance"] == "major" and item["coverage_status"] != "covered"
        ]
        uncovered_secondary = [
            item for item in assessments if item["importance"] == "secondary" and item["coverage_status"] != "covered"
        ]
        gaps = list(row.get("gaps") or [])
        if historical_status == "identity_mismatch_needs_review":
            gaps.append(
                gap(
                    "inventory_identity_mismatch",
                    "identity_review",
                    "expected-event inventory found a target-period identity mismatch",
                    blocking=True,
                )
            )
        if uncovered_major:
            gaps.append(
                gap(
                    "historical_event_missing",
                    "source_document_refinement",
                    f"{len(uncovered_major)} major expected events lack a complete source-to-event-group chain",
                    blocking=True,
                )
            )
        if uncovered_secondary:
            gaps.append(
                gap(
                    "historical_event_gap",
                    "source_document_refinement",
                    f"{len(uncovered_secondary)} secondary expected events lack a complete source-to-event-group chain",
                )
            )
        row["gaps"] = gaps
        row["mechanical_coverage_status"] = text(row.get("coverage_status"))
        row["coverage_status"] = "blocked" if any(item["blocking"] for item in gaps) else ("gap" if gaps else "complete")
        results.append(row)
    return results


def build_report(
    *,
    claim_rows: Sequence[Mapping[str, Any]],
    downstream_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    source_rows: Sequence[Mapping[str, Any]] = (),
    schema_name: str,
    item_code: str,
    rule_code: str,
    emperors: Sequence[str],
    expected_events: Sequence[Mapping[str, Any]] = (),
    reconciliation_reports: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    reconciliations = build_reconciliation_index(reconciliation_reports)
    objects = apply_expected_event_inventory(
        [assess_object(row, rule_code=rule_code) for row in merge_rows(claim_rows, downstream_rows, target_rows, source_rows)],
        claim_rows,
        expected_events,
        reconciliations,
    )
    action_counts: Counter[str] = Counter()
    gap_counts: Counter[str] = Counter()
    emperor_stats: dict[str, Counter[str]] = defaultdict(Counter)
    for row in objects:
        stats = emperor_stats[text(row.get("emperor_name"))]
        stats["objects"] += 1
        stats[row["coverage_status"]] += 1
        if row["chain_ready"]:
            stats["chain_ready"] += 1
        if row["scoring_relevant"]:
            stats["scoring_relevant"] += 1
        for item in row["gaps"]:
            gap_counts[item["gap_type"]] += 1
            action_counts[item["next_action"]] += 1
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_coverage_controller.py",
        "mode": "read_only_source_to_score_coverage",
        "write_db": False,
        "schema_name": schema_name,
        "item_code": item_code,
        "rule_code": rule_code,
        "emperors": list(emperors),
        "coverage_scope": "observed_cached_sources_and_native_pipeline",
        "historical_event_coverage_status": (
            "partially_assessed_by_expected_event_inventory"
            if expected_events
            else "unassessed_without_expected_event_inventory"
        ),
        "expected_event_count": sum(text(row.get("record_type")) != "object_assessment" for row in expected_events),
        "inventory_object_assessment_count": sum(
            text(row.get("record_type")) == "object_assessment" for row in expected_events
        ),
        "reconciliation_report_count": len(reconciliation_reports),
        "reconciled_expected_event_count": len(reconciliations),
        "verified_expected_event_count": sum(
            text(item.get("current", {}).get("gate_mode")) == "repair_verification" and
            text(item.get("current", {}).get("decision")) in VERIFIED_RECONCILIATION_DECISIONS
            for item in reconciliations.values()),
        "counts": {
            "objects": len(objects),
            "complete": sum(row["coverage_status"] == "complete" for row in objects),
            "gap": sum(row["coverage_status"] == "gap" for row in objects),
            "blocked": sum(row["coverage_status"] == "blocked" for row in objects),
            "chain_ready": sum(bool(row["chain_ready"]) for row in objects),
            "scoring_relevant": sum(bool(row["scoring_relevant"]) for row in objects),
        },
        "gap_counts": dict(sorted(gap_counts.items())),
        "repair_plan": [
            {"next_action": action, "object_count": count}
            for action, count in sorted(action_counts.items(), key=lambda pair: (-pair[1], pair[0]))
        ],
        "by_emperor": {name: dict(sorted(stats.items())) for name, stats in sorted(emperor_stats.items())},
        "objects": objects,
        "execute_effect": "read-only diagnosis; no queue writes, no database writes, no scoring",
    }


def fetch_rows(
    *, dsn: str, schema_name: str, item_code: str, rule_code: str, emperors: Sequence[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    psycopg, dict_row = import_psycopg()
    emperor_names = [text(name) for name in emperors if text(name)]
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                with evidence as (
                    select e.claim_key, count(distinct e.evidence_key) as evidence_count,
                           count(distinct s.document_code) as source_document_count
                      from retrieval_v3.claim_evidence e
                      left join retrieval_v3.claim_source_slices s on s.slice_hash = e.slice_hash
                     group by e.claim_key
                ), groups as (
                    select m.claim_key, count(distinct m.group_key) as event_group_count,
                           count(*) as event_group_member_count,
                           array_agg(distinct m.group_key) as event_group_keys
                      from retrieval_v3.claim_event_group_members m
                      join retrieval_v3.claim_event_groups g on g.group_key = m.group_key
                     where g.group_status::text not in ('rejected', 'retired')
                     group by m.claim_key
                )
                select c.emperor_name, c.object_id, c.object_name, c.object_type,
                       1 as active_claim_count,
                       coalesce(e.source_document_count, 0) as source_document_count,
                       coalesce(e.evidence_count, 0) as evidence_count,
                       coalesce(g.event_group_count, 0) as event_group_count,
                       coalesce(g.event_group_member_count, 0) as event_group_member_count,
                       coalesce(g.event_group_keys, array[]::text[]) as event_group_keys,
                       c.action_type, c.fact_type, c.office_or_domain, c.outcome,
                       c.outcome_support, c.claim_summary, c.fact_payload, c.updated_at as latest_claim_at
                  from retrieval_v3.claim_cache c
                  left join evidence e on e.claim_key = c.claim_key
                  left join groups g on g.claim_key = c.claim_key
                 where c.status::text = any(%s::text[])
                   and (coalesce(array_length(%s::text[], 1), 0) = 0 or c.emperor_name = any(%s::text[]))
                 order by c.emperor_name, c.object_name, c.claim_key
                """,
                (list(ACTIVE_STATUSES), emperor_names, emperor_names),
            )
            claim_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                with owners as (
                    select distinct emperor_name, object_id, object_name
                      from retrieval_v3.claim_cache
                     where status::text = any(%s::text[])
                       and (coalesce(array_length(%s::text[], 1), 0) = 0 or emperor_name = any(%s::text[]))
                ), claimed as (
                    select distinct e.slice_hash
                      from retrieval_v3.claim_evidence e
                      join retrieval_v3.claim_cache c on c.claim_key = e.claim_key
                     where c.status::text = any(%s::text[])
                       and (coalesce(array_length(%s::text[], 1), 0) = 0 or c.emperor_name = any(%s::text[]))
                )
                select o.emperor_name, o.object_id, o.object_name,
                       count(distinct s.slice_hash) as source_slice_count,
                       count(distinct s.document_code) as source_document_count,
                       count(distinct s.slice_hash) filter (where c.slice_hash is not null) as claimed_source_slice_count
                  from owners o
                  join retrieval_v3.claim_source_slices s
                    on (o.object_id is not null and s.object_id = o.object_id)
                    or (o.object_id is null and s.object_id is null and s.object_name = o.object_name)
                  left join claimed c on c.slice_hash = s.slice_hash
                 group by o.emperor_name, o.object_id, o.object_name
                 order by o.emperor_name, o.object_name
                """,
                (
                    list(ACTIVE_STATUSES),
                    emperor_names,
                    emperor_names,
                    list(ACTIVE_STATUSES),
                    emperor_names,
                    emperor_names,
                ),
            )
            source_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                with candidates as (
                    select claim_id, count(*) as candidate_count,
                           count(*) filter (where resolved_binding_id is null) as unresolved_candidate_count
                      from retrieval_v3.claim_rule_binding_candidates
                     where candidate_item_code = %s and candidate_rule_code = %s
                       and review_status::text not in ('rejected', 'retired')
                     group by claim_id
                ), bindings as (
                    select claim_id, count(*) as binding_count,
                           count(*) filter (where usable_for_scoring_cluster and review_status::text = 'accepted') as scoring_binding_count,
                           max(updated_at) as latest_binding_at
                      from retrieval_v3.claim_rule_bindings
                     where rule_code = %s and review_status::text not in ('rejected', 'retired')
                     group by claim_id
                ), factors as (
                    select claim_id, count(distinct binding_id) as factor_judgment_count, count(distinct binding_id) filter (where target_action::text = 'score') as scoring_factor_judgment_count,
                           max(updated_at) as latest_factor_at
                      from retrieval_v3.claim_rule_binding_factor_judgments
                     where item_code = %s and rule_code = %s and review_status::text not in ('rejected', 'retired')
                     group by claim_id
                ), scores as (
                    select claim_id, count(*) as material_score_count, max(updated_at) as latest_material_score_at
                      from retrieval_v3.claim_rule_binding_material_scores where item_code = %s and rule_code = %s group by claim_id
                ), clusters as (
                    select target_id, count(*) as rule_score_cluster_count, max(updated_at) as latest_rule_cluster_at from retrieval_v3.target_rule_score_clusters where item_code = %s and rule_code = %s
                       and review_status::text not in ('rejected', 'retired') group by target_id
                )
                select mc.emperor_name, mc.object_name, mc.object_type,
                       count(*) as material_claim_count,
                       sum(coalesce(c.candidate_count, 0)) as candidate_count,
                       sum(coalesce(c.unresolved_candidate_count, 0)) as unresolved_candidate_count,
                       sum(coalesce(b.binding_count, 0)) as binding_count,
                       sum(coalesce(b.scoring_binding_count, 0)) as scoring_binding_count,
                       sum(coalesce(f.factor_judgment_count, 0)) as factor_judgment_count, sum(coalesce(f.scoring_factor_judgment_count, 0)) as scoring_factor_judgment_count,
                       sum(coalesce(s.material_score_count, 0)) as material_score_count,
                       max(coalesce(cl.rule_score_cluster_count, 0)) as rule_score_cluster_count,
                       max(f.latest_factor_at) as latest_factor_at, max(s.latest_material_score_at) as latest_material_score_at,
                       max(cl.latest_rule_cluster_at) as latest_rule_cluster_at,
                       greatest(max(mc.updated_at), max(b.latest_binding_at), max(f.latest_factor_at)) as latest_consumed_at
                  from retrieval_v3.material_claims mc
                  join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
                  join retrieval_v3.retrieval_targets rt on rt.id = sp.target_id
                  left join candidates c on c.claim_id = mc.id
                  left join bindings b on b.claim_id = mc.id
                  left join factors f on f.claim_id = mc.id
                  left join scores s on s.claim_id = mc.id
                  left join clusters cl on cl.target_id = rt.id
                 where rt.item_code = %s
                   and mc.review_status::text not in ('rejected', 'retired')
                   and (coalesce(array_length(%s::text[], 1), 0) = 0 or mc.emperor_name = any(%s::text[]))
                 group by mc.emperor_name, mc.object_name, mc.object_type
                 order by mc.emperor_name, mc.object_name
                """,
                (item_code, rule_code, rule_code, item_code, rule_code, item_code, rule_code,
                 item_code, rule_code, item_code, emperor_names, emperor_names),
            )
            downstream_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select rt.emperor_name, o.id as object_id, o.canonical_name, o.canonical_name as object_name,
                       o.object_type,
                       coalesce(jsonb_agg(distinct onm.name_text) filter (
                           where onm.id is not null and onm.review_status::text = 'accepted'
                       ), '[]'::jsonb) as names
                  from retrieval_v3.retrieval_targets rt
                  join retrieval_v3.target_objects tob on tob.target_id = rt.id
                  join retrieval_v3.objects o on o.id = tob.object_id
                  left join retrieval_v3.object_names onm on onm.object_id = o.id
                 where rt.item_code = %s
                   and rt.target_status::text not in ('rejected', 'retired')
                   and tob.review_status::text not in ('rejected', 'retired')
                   and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
                 group by rt.emperor_name, o.id, o.canonical_name, o.object_type
                 order by rt.emperor_name, o.canonical_name
                """,
                (item_code, emperor_names, emperor_names),
            )
            target_rows = [dict(row) for row in cur.fetchall()]
    return claim_rows, downstream_rows, target_rows, source_rows


def markdown_cell(value: Any, limit: int = 120) -> str:
    result = text(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return result if len(result) <= limit else result[: limit - 1] + "…"


def render_markdown(report: Mapping[str, Any]) -> str:
    counts = report.get("counts") or {}
    lines = [
        "# retrieval_v3 源头到计分覆盖报告",
        "",
        f"- schema: `{report.get('schema_name')}`",
        f"- item/rule: `{report.get('item_code')}/{report.get('rule_code')}`",
        "- write_db: `false`",
        f"- objects: `{counts.get('objects', 0)}`; complete: `{counts.get('complete', 0)}`; gap: `{counts.get('gap', 0)}`; blocked: `{counts.get('blocked', 0)}`",
        "",
        "> 只读控制面报告。只有同一 event group 的事实链已完整或下游已启动的对象，才会产生 material/candidate/binding/factorization 缺口。",
        "> `complete` 只表示已观察到的缓存史源和 native 管线机械闭合；未提供预期史源/事件清单时，不代表历史事件覆盖完整。",
        "",
        f"- expected events: `{report.get('expected_event_count', 0)}`; historical coverage: `{report.get('historical_event_coverage_status')}`",
        f"- reconciled events: `{report.get('reconciled_expected_event_count', 0)}`; verified events: `{report.get('verified_expected_event_count', 0)}`",
        f"- mechanical coverage: `{json.dumps(report.get('mechanical_coverage_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- convergence: `{json.dumps(report.get('convergence_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## 修复队列",
        "",
        "| 动作 | 对象数 |",
        "| --- | ---: |",
    ]
    for row in report.get("repair_plan") or []:
        lines.append(f"| {markdown_cell(row.get('next_action'))} | {row.get('object_count', 0)} |")
    lines.extend(
        [
            "",
            "## 对象覆盖",
            "",
            "| 皇帝 | 对象 | claimed/source slices | claims | groups | materials | candidates | bindings | factor/score/cluster | 预期事件覆盖 | 链完整 | 机械覆盖 | 历史收敛 | 当前状态 | 缺口 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("objects") or []:
        lines.append(
            "| {emperor} | {object_name} | {slices} | {claims} | {groups} | {materials} | {candidates} | {bindings} | {lineage} | {events} | {ready} | {mechanical} | {convergence} | {status} | {gaps} |".format(
                emperor=markdown_cell(row.get("emperor_name")),
                object_name=markdown_cell(row.get("object_name")),
                slices=f"{as_int(row.get('claimed_source_slice_count'))}/{as_int(row.get('source_slice_count'))}",
                claims=as_int(row.get("active_claim_count")),
                groups=as_int(row.get("event_group_count")),
                materials=as_int(row.get("material_claim_count")),
                candidates=as_int(row.get("candidate_count")),
                bindings=as_int(row.get("binding_count")),
                lineage=f"{as_int(row.get('factor_judgment_count'))}/{as_int(row.get('material_score_count'))}/{as_int(row.get('rule_score_cluster_count'))}",
                events=(
                    f"{as_int(row.get('covered_expected_event_count'))}/{as_int(row.get('expected_event_count'))}"
                    if as_int(row.get("expected_event_count"))
                    else "未评估"
                ),
                ready="是" if row.get("chain_ready") else "否",
                mechanical=markdown_cell(row.get("mechanical_coverage_status")),
                convergence=markdown_cell(row.get("convergence_state")),
                status=markdown_cell(row.get("coverage_status")),
                gaps=markdown_cell(", ".join(item["gap_type"] for item in row.get("gaps") or [])),
            )
        )
    return "\n".join(lines) + "\n"


def build_source_refinement_worklist(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    worklist: list[dict[str, Any]] = []
    for row in report.get("objects") or []:
        for event in row.get("expected_event_assessments") or []:
            if event.get("coverage_status") == "covered":
                continue
            facets = event.get("matched_facets") if isinstance(event.get("matched_facets"), Mapping) else {}
            importance = text(event.get("importance"))
            coverage_status = text(event.get("coverage_status"))
            priority = {
                ("major", "missing"): 10,
                ("major", "partial"): 20,
                ("secondary", "missing"): 30,
                ("secondary", "partial"): 40,
            }.get((importance, coverage_status), 50)
            worklist.append({
                "repair_code": "EER-" + text(event.get("event_inventory_code")).removeprefix("EEI-"),
                "emperor_name": text(row.get("emperor_name")), "object_id": row.get("object_id"),
                "object_name": text(row.get("object_name")),
                "event_inventory_code": text(event.get("event_inventory_code")),
                "event_label": text(event.get("event_label")), "importance": importance,
                "direction": text(event.get("direction")), "coverage_status": coverage_status, "priority": priority,
                "matched_group_key": text(event.get("matched_group_key")),
                "missing_facets": [name for name, present in facets.items() if not present],
                "source_document_hints": event.get("source_leads") or [],
                "next_stage": "object_source_cache_then_claim_extraction", "evidence_status": "retrieval_lead_only",
                "write_db": False, "scoring_allowed": False,
            })
    return sorted(
        worklist,
        key=lambda row: (
            as_int(row.get("priority")),
            text(row.get("emperor_name")),
            text(row.get("object_name")),
            text(row.get("event_inventory_code")),
        ),
    )
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only retrieval_v3 source-to-score coverage controller.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--rule-code", default=DEFAULT_RULE_CODE)
    parser.add_argument("--emperor", action="append", default=[])
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--expected-events-jsonl", type=Path)
    parser.add_argument("--reconciliation-report", type=Path, action="append", default=[])
    parser.add_argument("--output-repair-worklist", type=Path)
    parser.add_argument("--output-gap-router", type=Path)
    parser.add_argument("--previous-repair-ledger", type=Path); parser.add_argument("--output-repair-ledger", type=Path)
    parser.add_argument("--output-consumer-handoff-root", type=Path); parser.add_argument("--output-convergence-delta", type=Path)
    parser.add_argument("--repair-limit", type=int, default=0)
    return parser
def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    claim_rows, downstream_rows, target_rows, source_rows = fetch_rows(
        dsn=resolve_dsn(args.dsn_env),
        schema_name=args.pg_schema,
        item_code=args.item_code,
        rule_code=args.rule_code,
        emperors=args.emperor,
    )
    expected_events: list[dict[str, Any]] = []
    if args.expected_events_jsonl is not None:
        for line_no, line in enumerate(args.expected_events_jsonl.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError(f"{args.expected_events_jsonl}:{line_no}: expected object")
            expected_events.append(dict(value))
    reconciliation_reports: list[dict[str, Any]] = []
    for report_path in args.reconciliation_report:
        value = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError(f"{report_path}: expected object")
        reconciliation_reports.append(dict(value))
    report = build_report(
        claim_rows=claim_rows,
        downstream_rows=downstream_rows,
        target_rows=target_rows,
        source_rows=source_rows,
        schema_name=args.pg_schema,
        item_code=args.item_code,
        rule_code=args.rule_code,
        emperors=args.emperor,
        expected_events=expected_events,
        reconciliation_reports=reconciliation_reports,
    )
    previous_ledger: list[dict[str, Any]] = []
    if args.previous_repair_ledger is not None:
        for line in args.previous_repair_ledger.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if isinstance(value, Mapping):
                previous_ledger.append(dict(value))
    repair_ledger = build_repair_ledger(report, previous_ledger)
    apply_convergence(report, repair_ledger)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8", newline="\n")
    elif args.output_md is None:
        print(payload, end="")
    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    if args.output_repair_worklist is not None:
        args.output_repair_worklist.parent.mkdir(parents=True, exist_ok=True)
        repair_rows = build_source_refinement_worklist(report)
        if args.repair_limit > 0:
            repair_rows = repair_rows[: args.repair_limit]
        args.output_repair_worklist.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n"
                for row in repair_rows
            ),
            encoding="utf-8",
            newline="\n",
        )
    if args.output_gap_router is not None:
        args.output_gap_router.parent.mkdir(parents=True, exist_ok=True)
        rows = build_gap_routes(report)
        payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows)
        args.output_gap_router.write_text(payload, encoding="utf-8", newline="\n")
    if args.output_repair_ledger is not None:
        args.output_repair_ledger.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in repair_ledger)
        args.output_repair_ledger.write_text(payload, encoding="utf-8", newline="\n")
    if args.output_consumer_handoff_root is not None:
        handoff = build_consumer_handoffs(repair_ledger)
        args.output_consumer_handoff_root.mkdir(parents=True, exist_ok=True)
        manifest = dict(handoff); manifest.pop("handoffs", None)
        (args.output_consumer_handoff_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in handoff["handoffs"]:
            by_stage[text(row.get("consumer_stage")) or "manual_review"].append(row)
        for stage, rows in sorted(by_stage.items()):
            payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows)
            (args.output_consumer_handoff_root / f"{stage}.jsonl").write_text(payload, encoding="utf-8", newline="\n")
    if args.output_convergence_delta is not None:
        delta = build_convergence_delta(repair_ledger, previous_ledger)
        args.output_convergence_delta.parent.mkdir(parents=True, exist_ok=True)
        args.output_convergence_delta.write_text(
            json.dumps(delta, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
