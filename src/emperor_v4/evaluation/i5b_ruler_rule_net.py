from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.i5b_scoring_policy import RULE_ORDER, RULE_WEIGHTS


MANIFEST_SCHEMA_VERSION = "i5b-ruler-rule-net-manifest-v1"
REPORT_SCHEMA_VERSION = "i5b-ruler-rule-net-report-v1"
POLICY_VERSION = "i5b-ruler-rule-net-shadow-v1"
CALCULATION_STATES = {
    "historical_coverage_complete",
    "expanded_declared_workset",
    "partial_declared_workset",
    "provisional_pending_source_rebind",
}


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _decimal(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{label} must be decimal") from exc


def _text(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def build_i5b_ruler_rule_net_report(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("ruler rule net manifest schema mismatch")
    ruler = str(manifest.get("ruler") or "")
    ruler_ref = str(manifest.get("ruler_ref") or "")
    if not ruler or not ruler_ref:
        raise ValueError("ruler rule net requires ruler identity")
    rows = manifest.get("rule_results") or ()
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("rule_results must be an array")
    by_rule = {str(row.get("rule_code") or ""): row for row in rows}
    if len(rows) != len(RULE_ORDER) or set(by_rule) != set(RULE_ORDER):
        raise ValueError("ruler rule net requires exactly five I5B rules")

    results: list[dict[str, Any]] = []
    weighted_total = Decimal("0")
    all_coverage_complete = True
    for rule_code in RULE_ORDER:
        row = by_rule[rule_code]
        state = str(row.get("calculation_status") or "")
        if state not in CALCULATION_STATES:
            raise ValueError(f"{rule_code} calculation status is invalid")
        positive = _decimal(row.get("positive_signal"), f"{rule_code}.positive_signal")
        negative = _decimal(row.get("negative_signal"), f"{rule_code}.negative_signal")
        if positive < 0 or negative < 0:
            raise ValueError(f"{rule_code} side signals must be non-negative")
        source_refs = [str(item) for item in row.get("source_refs") or ()]
        material_refs = [str(item) for item in row.get("material_refs") or ()]
        if not source_refs or not material_refs:
            raise ValueError(f"{rule_code} requires source and material lineage")
        historical_status = str(row.get("historical_coverage_status") or "")
        if historical_status not in {
            "unassessed",
            "in_progress",
            "coverage_complete",
            "insufficient_evidence",
        }:
            raise ValueError(f"{rule_code} historical coverage status is invalid")
        if state == "historical_coverage_complete" and historical_status != "coverage_complete":
            raise ValueError(f"{rule_code} cannot claim complete calculation without coverage")
        all_coverage_complete &= historical_status == "coverage_complete"
        net = positive - negative
        weight = RULE_WEIGHTS[rule_code]
        weighted = net * weight
        weighted_total += weighted
        scenarios = []
        for scenario in row.get("sensitivity_scenarios") or ():
            scenario_net = _decimal(
                scenario.get("rule_raw_net"), f"{rule_code}.sensitivity.rule_raw_net"
            )
            if not scenario.get("scenario_code") or not scenario.get("condition"):
                raise ValueError(f"{rule_code} sensitivity scenario is incomplete")
            scenarios.append(
                {
                    "scenario_code": str(scenario["scenario_code"]),
                    "rule_raw_net": _text(scenario_net),
                    "condition": str(scenario["condition"]),
                    "included_in_current_net": False,
                }
            )
        results.append(
            {
                "rule_code": rule_code,
                "calculation_status": state,
                "historical_coverage_status": historical_status,
                "positive_signal": _text(positive),
                "negative_signal": _text(negative),
                "rule_raw_net": _text(net),
                "rule_weight": _text(weight),
                "weighted_raw_contribution": _text(weighted),
                "source_refs": source_refs,
                "material_refs": material_refs,
                "limitations": [str(item) for item in row.get("limitations") or ()],
                "sensitivity_scenarios": scenarios,
                "formal_score": None,
            }
        )

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": (
            "historical_rule_nets_complete"
            if all_coverage_complete
            else "declared_workset_rule_nets_available_coverage_incomplete"
        ),
        "ruler": ruler,
        "ruler_ref": ruler_ref,
        "input_version": str(manifest.get("input_version") or ""),
        "rules": results,
        "summary": {
            "rule_count": len(results),
            "all_rule_net_available": True,
            "historical_coverage_complete_rule_count": sum(
                row["historical_coverage_status"] == "coverage_complete" for row in results
            ),
            "declared_workset_weighted_raw_signal": _text(weighted_total),
            "batch_dynamic_mapping_input_allowed": all_coverage_complete,
            "formal_45_point_score": None,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_scoring_allowed": False,
        },
        "declarations": {
            "missing_rule_treated_as_zero": False,
            "declared_workset_net_claimed_as_historical_complete": False,
            "single_ruler_dynamic_mapping_performed": False,
            "old_opened_or_sealed_gold_modified": False,
            "formal_scoring_allowed": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report
