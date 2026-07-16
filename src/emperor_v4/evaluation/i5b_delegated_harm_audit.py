from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


SCHEMA_VERSION = "i5b-delegated-harm-attribution-contract-v1"
REPORT_SCHEMA_VERSION = "i5b-delegated-harm-audit-report-v1"


def _hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def evaluate_delegated_harm_audit(
    contract: Mapping[str, Any], incidents: list[Mapping[str, Any]]
) -> dict[str, Any]:
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("委托损害归责合同版本非法")
    required = set(contract.get("required_observations") or ())
    if required != {
        "delegated_authority_boundary",
        "actor_conduct",
        "actual_public_harm",
        "ruler_foreseeability_or_prior_notice",
        "ruler_response_after_notice",
        "later_restoration_or_retention",
    }:
        raise ValueError("委托损害观察字段不完整")
    mappings = contract.get("effect_mapping") or {}
    if set(mappings) != {
        "bounded_control_failure",
        "limited_direct_damage",
        "major_direct_damage",
        "structural_continuing_damage",
    }:
        raise ValueError("委托损害档位不完整")

    reviewed = []
    seen: set[str] = set()
    settlement_keys: set[str] = set()
    duplicates = []
    for row in incidents:
        incident_ref = str(row.get("incident_ref") or "")
        observations = row.get("observations") or {}
        route = str(row.get("primary_route") or "")
        option = str(row.get("effect_option") or "")
        settlement_key = str(row.get("settlement_key") or "")
        if (
            not incident_ref
            or incident_ref in seen
            or set(observations) != required
            or route not in (contract.get("routing_rules") or {})
            or option not in mappings
            or not settlement_key
        ):
            raise ValueError(f"委托损害事件非法: {incident_ref}")
        if settlement_key in settlement_keys:
            duplicates.append(incident_ref)
        settlement_keys.add(settlement_key)
        seen.add(incident_ref)
        reviewed.append(dict(row))
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "complete" if not duplicates else "failed_cross_rule_duplicate",
        "incidents": reviewed,
        "summary": {
            "reviewed_incident_count": len(reviewed),
            "unresolved_incident_count": 0,
            "cross_rule_duplicate_count": len(duplicates),
            "duplicate_incident_refs": duplicates,
            "database_write_count": 0,
            "model_call_count": 0,
        },
        "declarations": {
            "subordinate_misconduct_is_automatic_ruler_fault": False,
            "task_importance_is_harm_severity": False,
            "formal_score": None,
            "tier": None,
            "ranking": None,
        },
    }
    report["report_sha256"] = _hash(report)
    return report


def build_delegated_harm_audit(
    *, contract_path: Path, incidents_path: Path
) -> dict[str, Any]:
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    incidents = yaml.safe_load(incidents_path.read_text(encoding="utf-8"))
    return evaluate_delegated_harm_audit(contract, list(incidents["incidents"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="生成第五项B委托损害归责审计")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--incidents", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_delegated_harm_audit(
        contract_path=args.contract, incidents_path=args.incidents
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
