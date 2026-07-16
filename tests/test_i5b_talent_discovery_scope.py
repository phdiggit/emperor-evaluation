from __future__ import annotations

import json
from pathlib import Path

import yaml

from emperor_v4.evaluation.i5b_talent_discovery_scope import (
    build_talent_discovery_scope_refreeze,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / (
    "tests/fixtures/i5b_talent_discovery_scope_contract.yml"
)


def test_pre_accession_li_shimin_discovery_is_reopened_without_auto_acceptance(
    tmp_path: Path,
) -> None:
    base_inventory = tmp_path / "base.json"
    base_inventory.write_text(
        json.dumps(
            {
                "candidate_inventory": [
                    {
                        "event_group_key": f"CEG-PRE-{index:02d}",
                        "final_disposition": "reject_pre_reign_scope",
                    }
                    for index in range(11)
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cross_inventory = tmp_path / "cross.json"
    cross_inventory.write_text(
        json.dumps(
            {
                "rule_code": "appointment_delegation",
                "candidate_inventory": [
                    {
                        "event_group_key": f"CEG-CROSS-{index:02d}",
                        "candidate_persons": [f"人物{index}"],
                        "candidate_event_summary": "待语义路由",
                        "final_rationale": "秦王时期发生，需核对识才语义。",
                    }
                    for index in range(12)
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract["base_inventory_ref"] = str(base_inventory)
    contract["cross_rule_inventory_refs"] = [str(cross_inventory)]
    runtime_contract = tmp_path / "contract.yml"
    runtime_contract.write_text(
        yaml.safe_dump(contract, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    report = build_talent_discovery_scope_refreeze(runtime_contract)
    assert report["scope"] == {
        "evaluation_window": {"start": 626, "end": 649},
        "discovery_lookback": "pre_accession_leadership_formation",
        "predecessor_only_recruitment": "excluded",
    }
    assert report["candidate_summary"]["reopened_pre_accession_count"] == 11
    assert report["candidate_summary"]["scheduled_pre_accession_review_count"] == 6
    assert report["candidate_summary"]["deferred_pre_accession_review_count"] == 5
    assert report["candidate_summary"]["cross_rule_time_exclusion_count"] > 11
    assert report["candidate_summary"][
        "cross_rule_pending_semantic_route_count"
    ] > 0
    assert all(
        row["route_status"] in {
            "bound_for_pre_accession_agency_review",
            "pending_talent_discovery_semantic_route_review",
            "deferred_cross_rule_route_budget",
        }
        for row in report["cross_rule_pre_accession_review"]
    )
    yuchi = next(
        row
        for row in report["candidate_inventory"]
        if row["event_group_key"] == "CEG-LSM-YUCHIJINGDE-RECRUITMENT-V1"
    )
    assert yuchi["final_disposition"] == "candidate_pending_primary_source_acceptance"
    assert yuchi["scope_relation"] == "pre_accession_leadership_formation"
    assert len(yuchi["primary_source_locators"]) == 2
    assert report["formal_fact_acceptance_ready"] is False
    assert report["historical_coverage_complete"] is False
    assert report["declarations"][
        "li_yuan_or_predecessor_recruitment_attributed_to_li_shimin"
    ] is False
