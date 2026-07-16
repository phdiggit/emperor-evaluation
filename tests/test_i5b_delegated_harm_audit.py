from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from emperor_v4.evaluation.i5b_delegated_harm_audit import (
    build_delegated_harm_audit,
    evaluate_delegated_harm_audit,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/i5b-delegated-harm-attribution.yml"
INCIDENTS = ROOT / (
    "eval/i5b_source_ingestion/"
    "team_building_lishimin_delegated_harm_incidents_v1.yml"
)


def test_houjunji_control_breach_and_later_team_risk_are_not_duplicate() -> None:
    report = build_delegated_harm_audit(
        contract_path=CONTRACT, incidents_path=INCIDENTS
    )
    assert report["status"] == "complete"
    assert report["summary"]["reviewed_incident_count"] == 2
    assert report["summary"]["cross_rule_duplicate_count"] == 0
    assert report["incidents"][0]["effect_option"] == "bounded_control_failure"
    assert report["declarations"][
        "subordinate_misconduct_is_automatic_ruler_fault"
    ] is False


def test_same_harm_cannot_be_settled_in_appointment_and_team() -> None:
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    incidents = yaml.safe_load(INCIDENTS.read_text(encoding="utf-8"))["incidents"]
    duplicate = deepcopy(incidents[1])
    duplicate["incident_ref"] = "DHI-DUPLICATE"
    duplicate["settlement_key"] = incidents[0]["settlement_key"]
    report = evaluate_delegated_harm_audit(contract, [*incidents, duplicate])
    assert report["status"] == "failed_cross_rule_duplicate"
    assert report["summary"]["cross_rule_duplicate_count"] == 1
