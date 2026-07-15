from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.i5b_scoring_policy import (
    RULE_ORDER,
    RuleSignals,
    build_batch_mapping_input,
    calculate_weighted_raw_signal,
)


SCHEMA_VERSION = "i5b-unified-raw-signal-readiness-v2"
POLICY_VERSION = "i5b-unified-raw-signal-runner-v2"
COVERAGE_SCHEMA_VERSION = "i5b-ruler-rule-coverage-report-v1"


def _hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _rows(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} may contain only objects")
    return list(value)


def build_i5b_unified_raw_signal_readiness(
    *,
    appointment_report: Mapping[str, Any],
    team_report: Mapping[str, Any],
    joint_reports: Sequence[Mapping[str, Any]],
    coverage_reports: Sequence[Mapping[str, Any]],
    calibration_version: str,
) -> dict[str, Any]:
    appointment_status = appointment_report.get("status")
    if appointment_status not in {
        "appointment_delegation_v3_parity_shadow_ready",
        "appointment_delegation_historical_scored_shadow_complete",
    }:
        raise ValueError("appointment parity report is not ready")
    team_status = team_report.get("status")
    if team_status not in {
        "full_cohort_scored_shadow_raw_signal_only",
        "team_building_historical_scored_shadow_complete",
    }:
        raise ValueError("full team scored shadow report is not ready")
    joint = {str(report.get("rule_code")): report for report in joint_reports}
    if set(joint) != {"talent_discovery", "tolerate_talent", "anti_nepotism"}:
        raise ValueError("unified runner requires exactly three joint projection reports")
    if any(
        report.get("status") != "opened_regression_scored_shadow_raw_signal_only"
        for report in joint.values()
    ):
        raise ValueError("joint projection report is not ready")

    if not coverage_reports:
        raise ValueError("unified runner requires ruler-rule coverage reports")
    coverage_by_ruler: dict[str, dict[str, Mapping[str, Any]]] = {}
    for coverage_report in coverage_reports:
        if coverage_report.get("schema_version") != COVERAGE_SCHEMA_VERSION:
            raise ValueError("unified runner requires versioned ruler-rule coverage reports")
        ruler = str(coverage_report.get("ruler") or "")
        if not ruler or ruler in coverage_by_ruler:
            raise ValueError("ruler-rule coverage reports require unique ruler identities")
        rule_rows = _rows(coverage_report.get("rules"), "coverage rules")
        coverage_by_ruler[ruler] = {
            str(row["rule_code"]): row for row in rule_rows
        }

    by_ruler: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    appointment_source_ref = (
        "eval/i5b_appointment_delegation_historical_coverage/"
        "lishimin_scored_shadow_report_v1.json"
        if appointment_status == "appointment_delegation_historical_scored_shadow_complete"
        else "eval/appointment_delegation_v3_parity_demo/report.json"
    )
    for row in _rows(appointment_report.get("ruler_aggregates"), "appointment rulers"):
        by_ruler[str(row["ruler"])]["appointment_delegation"] = {
            "workset_projection_status": "workset_projection_complete",
            "positive_signal": str(row["positive_signal"]),
            "negative_signal": str(row["negative_signal"]),
            "source_ref": appointment_source_ref,
        }

    if team_status == "team_building_historical_scored_shadow_complete":
        raw = team_report["raw_signal"]
        by_ruler[str(team_report["ruler"])]["team_building"] = {
            "workset_projection_status": "workset_projection_complete",
            "positive_signal": raw["positive_signal"],
            "negative_signal": raw["negative_signal"],
            "source_ref": (
                "eval/i5b_team_building_historical_coverage/"
                "lishimin_scored_shadow_report_v2.json"
            ),
        }
    else:
        team_by_ruler: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in _rows(team_report.get("windows"), "team windows"):
            team_by_ruler[str(row["ruler"])].append(row)
        for ruler, windows in team_by_ruler.items():
            if len(windows) == 1:
                raw = windows[0]["raw_signal"]
                by_ruler[ruler]["team_building"] = {
                    "workset_projection_status": "workset_projection_complete",
                    "positive_signal": raw["positive_signal"],
                    "negative_signal": raw["negative_signal"],
                    "source_ref": windows[0]["unit_ref"],
                }
            else:
                by_ruler[ruler]["team_building"] = {
                    "workset_projection_status": "workset_aggregation_blocked",
                    "blocker": "multiple_windows_require_temporal_aggregation_contract",
                    "window_refs": [row["unit_ref"] for row in windows],
                }

    for rule_code, report in joint.items():
        for row in _rows(report.get("score_contributions"), f"{rule_code} contributions"):
            insufficient = int(row["insufficient_projection_count"])
            by_ruler[str(row["ruler"])][rule_code] = {
                "workset_projection_status": (
                    "workset_projection_complete"
                    if insufficient == 0
                    else "workset_projection_incomplete"
                ),
                "positive_signal": row["positive_signal"],
                "negative_signal": row["negative_signal"],
                "insufficient_projection_count": insufficient,
                "source_ref": row["contribution_ref"],
                **(
                    {}
                    if insufficient == 0
                    else {"blocker": "insufficient_projection_is_not_zero_material"}
                ),
            }

    ruler_rows: list[dict[str, Any]] = []
    envelopes: list[dict[str, Any]] = []
    for ruler in sorted(by_ruler):
        coverage = by_ruler[ruler]
        historical_by_rule = coverage_by_ruler.get(ruler, {})
        blockers = []
        signals: dict[str, RuleSignals] = {}
        for rule_code in RULE_ORDER:
            state = coverage.get(rule_code)
            historical = historical_by_rule.get(rule_code)
            historical_status = (
                "unassessed"
                if historical is None
                else str(historical["historical_coverage_status"])
            )
            if historical_status != "coverage_complete":
                blockers.append(
                    {
                        "rule_code": rule_code,
                        "code": f"historical_coverage_{historical_status}",
                    }
                )
            elif state is None:
                blockers.append(
                    {"rule_code": rule_code, "code": "workset_projection_absent"}
                )
            elif state["workset_projection_status"] != "workset_projection_complete":
                blockers.append(
                    {"rule_code": rule_code, "code": state["blocker"]}
                )
            else:
                signals[rule_code] = RuleSignals(
                    positive_signal=Decimal(str(state["positive_signal"])),
                    negative_signal=Decimal(str(state["negative_signal"])),
                    signal_ref=str(state["source_ref"]),
                )
        eligible = not blockers
        envelope = calculate_weighted_raw_signal(signals) if eligible else None
        if envelope is not None:
            envelopes.append({"ruler": ruler, "raw_signal_envelope": envelope})
        ruler_rows.append(
            {
                "ruler": ruler,
                "eligible_for_mapping_input": eligible,
                "rule_coverage": {
                    rule: {
                        "workset": coverage.get(rule),
                        "historical_coverage": historical_by_rule.get(rule),
                    }
                    for rule in RULE_ORDER
                },
                "blockers": blockers,
                "raw_signal_envelope": envelope,
            }
        )

    batch = (
        build_batch_mapping_input(envelopes, calibration_version=calibration_version)
        if len(envelopes) >= 2
        else None
    )
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": (
            "candidate_batch_mapping_input_ready"
            if batch is not None
            else "blocked_no_coverage_complete_multi_ruler_cohort"
        ),
        "calibration_version": calibration_version,
        "summary": {
            "observed_ruler_count": len(ruler_rows),
            "coverage_report_count": len(coverage_by_ruler),
            "eligible_ruler_count": len(envelopes),
            "batch_mapping_input_generated": batch is not None,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_scoring_allowed": False,
        },
        "rulers": ruler_rows,
        "batch_mapping_input": batch,
        "declarations": {
            "missing_rule_treated_as_zero": False,
            "insufficient_projection_treated_as_zero": False,
            "multiple_team_windows_silently_aggregated": False,
            "workset_projection_implies_historical_coverage": False,
            "formal_scoring_allowed": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report
