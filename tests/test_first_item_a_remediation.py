from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.evaluation.first_item_settlement import build_first_item_formal_settlement
from emperor_v4.evaluation.formal_json_store import load_json


ROOT = Path(".")
A_PATH = ROOT / "docs/评分结算/第一项创业与政权取得能力/战略决策能力/01-第一项A战略决策能力结算.json"


def _load(path: Path) -> dict:
    return load_json(path)


def test_first_item_a_uses_decided_weights_and_full_o_coverage() -> None:
    payload = _load(A_PATH)
    eligible = [row for row in payload["records"] if row["score_applicable"]]
    assert payload["schema_version"] == "first-item-a-registry-v8"
    assert len(eligible) == 84
    assert payload["opponent_threat_source_counts"] == {
        "OPPONENT_SYSTEM_O_GRADE_WITH_RELATIVE_RESOURCES": 84
    }
    for row in eligible:
        a1 = row["A1"]
        pure = (
            0.15 * a1["starting_resource_disadvantage"]
            + 0.35 * a1["project_start_resource_disadvantage"]
            + 0.50 * a1["opponent_pressure"]
        )
        assert abs(pure - a1["pure_difficulty_rate"]) <= 0.02
        assert a1["opponent_system_pressure"] is not None
        assert a1["major_opponent_systems"]
        assert not a1["unknown_opponent_campaign_refs"]
        assert row["initial_resource_source_refs"]
        assert row["initial_resource_source_status"] == "SOURCE_ANCHORED_RULE_MAPPED"
        assert row["initial_resource_class"].startswith("R")
        assert "百分比不是史书原文数字" in row["initial_resource_share_basis"]


def test_first_item_a2_lineage_covers_c_inputs_without_hash_binding() -> None:
    payload = _load(A_PATH)
    lineage = payload["a2_c_lineage"]
    territorial = _load(
        ROOT / "config/first-item/first-item-c-territorial-control-adjudications.json"
    )
    assert "territorial_semantic_fingerprint" not in lineage
    assert "acquisition_semantic_fingerprint" not in lineage
    assert len(lineage["aligned_names"]) == 84
    assert lineage["pending_names"] == []
    expected_supplemental = {
        "刘崇", "孟知祥", "李克用", "杨行密", "钱镠", "马殷", "高季兴", "李德明", "铁木真"
    }
    assert set(lineage["supplemental_control_window_names"]) == expected_supplemental
    controls = {
        row["ruler_name"]: row
        for row in territorial["a2_control_window_adjudications"]
    }
    assert set(controls) == expected_supplemental
    assert controls["刘崇"]["created_net_control_value"] == 0
    assert all(row["source_refs"] for row in controls.values())


def test_first_item_a_cofounder_allocations_and_temujin_are_settled() -> None:
    payload = _load(A_PATH)
    by_name = {row["ruler_name"]: row for row in payload["records"]}
    expected = {
        "李世民": (51.0, 31.0, 82.0),
        "李渊": (39.0, 17.0, 56.0),
        "李存勖": (41.6, 2.5, 44.1),
        "李嗣源": (33.4, 8.2, 41.6),
        "石勒": (45.4, 20.3, 65.7),
        "石虎": (35.6, 10.4, 46.0),
        "蒙哥": (5.4, 3.1, 8.5),
        "忽必烈": (44.8, 14.3, 59.1),
        "耶律阿保机": (41.9, 5.3, 47.2),
        "述律平": (26.3, 4.0, 30.3),
        "铁木真": (49.6, 28.4, 78.0),
    }
    assert {
        name: (row["A1"]["points"], row["A2"]["points"], row["A_score_points"])
        for name, row in by_name.items()
        if name in expected
    } == expected
    assert by_name["述律平"]["end_boundary"].startswith("916")
    assert by_name["铁木真"]["end_boundary"].startswith("1227")


def test_formal_settlement_propagates_a_b_c_limitations() -> None:
    common = {
        "ruler_id": "RULER-TEST",
        "ruler_name": "测试人物",
        "polity": "测试",
        "reign_range": "1-2",
        "score_applicable": True,
    }
    a_payload = {"schema_version": "a", "records": [{
        **common,
        "scope_status": "ELIGIBLE_DYNASTY_FOUNDER",
        "A1": {"points": 10.0},
        "A2": {"points": 10.0},
        "A_score_points": 20.0,
        "evidence_lower_bound": True,
        "limitations": ["A限制"],
    }]}
    b_payload = {"schema_version": "b", "records": [{
        **common,
        "B1": {"points": 10.0},
        "B2": {"points": 10.0},
        "B_score_points": 20.0,
        "limitations": ["B限制"],
    }]}
    c_payload = {"schema_version": "c", "records": [{
        **common,
        "C1": {"points": 10.0},
        "C2": {"points": 10.0},
        "C_score_points": 20.0,
        "coverage_status": "DEFAULT_ZERO_EVIDENCE_GAP",
        "default_applied": True,
        "default_basis": "C限制",
        "unresolved_gaps": [],
    }]}
    result = build_first_item_formal_settlement(
        a_payload=a_payload, b_payload=b_payload, c_payload=c_payload
    )
    row = result["records"][0]
    assert row["evidence_lower_bound"] is True
    assert row["limitations"] == ["A：A限制", "B：B限制", "C：C限制"]
