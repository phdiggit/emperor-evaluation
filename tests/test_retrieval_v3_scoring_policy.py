from __future__ import annotations

import json

import pytest

from scripts.dev import retrieval_v3_scoring_policy as tool


def policy() -> dict:
    return {
        "item_code": "I5B", "rule_code": "appointment_delegation",
        "policy_code": "POL-I5B-APPOINTMENT-DELEGATION", "policy_version": "v3-native-density-decay-20260711",
        "side_aggregation": {
            "mode": "hierarchical_rank_decay", "all_scored_materials_contribute": True,
            "hard_aggregation_cap": False, "top_k": False,
        },
        "trial_scope": ["甲"],
    }


def test_read_policy_requires_all_materials_and_forbids_caps(tmp_path) -> None:
    path = tmp_path / "policy.json"
    value = policy()
    value["side_aggregation"]["top_k"] = True
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(tool.ScoringPolicyError, match="forbidden"):
        tool.read_policy(path)


def test_build_plan_updates_source_and_runtime_policy_versions() -> None:
    current_payload = {"existing": True}
    rows = {
        "runtime_rows": [{
            "id": 2, "policy_code": "POL-I5B-APPOINTMENT-DELEGATION",
            "policy_version": "v1", "policy_payload": current_payload,
            "source_row": {"policy_version": "v1", "policy_payload": current_payload},
        }],
    }

    plan = tool.build_plan(rows, policy())

    assert plan["unchanged"] is False
    assert plan["desired_policy_payload"]["existing"] is True
    assert plan["desired_policy_payload"]["side_aggregation"]["mode"] == "hierarchical_rank_decay"
    assert plan["desired_source_row"]["policy_version"] == "v3-native-density-decay-20260711"
    assert plan["write_db"] is False
