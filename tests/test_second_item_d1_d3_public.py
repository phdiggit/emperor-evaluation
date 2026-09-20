from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_d1_d3_public import (
    D1_PATH,
    D3_PATH,
    PUBLIC_EVIDENCE_FIELDS,
    PUBLIC_FORBIDDEN_RE,
    _refresh_payload,
    _scoring_signature,
    verify_public_projection,
)


def _d1_row() -> dict:
    return {
        "ruler_id": "SYNTHETIC-D1-RULER",
        "ruler_name": "合成甲",
        "grade": "G3",
        "handoff_level": "H3",
        "grade_basis": "H3：前任留下的中枢人员与命令链在退出后继续运行；D3事实不在本轴重复计算。",
        "M_positive_profile": [
            {
                "M": "M2",
                "direction": "positive",
                "mechanism": "DIRECT_D1_CONTINUITY",
                "result_closure": "observed_or_repeated",
                "signed_weight": 1.0,
            }
        ],
        "M_mixed_profile": [],
        "M_negative_profile": [
            {
                "M": "M2",
                "direction": "negative",
                "mechanism": "行政链重组",
                "result_closure": "observed_or_repeated",
                "signed_weight": -1.0,
            }
        ],
    }


def _d3_row() -> dict:
    return {
        "ruler_id": "SYNTHETIC-D1-RULER",
        "ruler_name": "合成乙",
        "D3_grade": "D3-2",
        "actual_successor": "继承者乙",
        "prearrangement_evidence": "已立太子并安排辅政。",
        "immediate_result_facts": ["宫廷武装介入", "一个中央很快恢复运行"],
        "reason": "实际承接由强制手段决定。",
        "terminal_evidence": "继承窗口内完成强制接管。",
    }


def test_public_projection_preserves_scoring_fields_and_keeps_all_evidence():
    d1 = {"records": [_d1_row()]}
    d3 = {"records": [_d3_row()]}
    before_d1 = deepcopy(d1)
    before_d3 = deepcopy(d3)

    projected_d1 = _refresh_payload(d1, "D1")
    projected_d3 = _refresh_payload(d3, "D3")

    assert _scoring_signature(projected_d1) == _scoring_signature(before_d1)
    assert _scoring_signature(projected_d3) == _scoring_signature(before_d3)
    assert len(projected_d1["records"][0]["public_evidence_items"]) == 2
    assert len(projected_d3["records"][0]["public_evidence_items"]) == 3
    report = verify_public_projection(
        Path("."), payloads={"D1": projected_d1, "D3": projected_d3}
    )
    assert report["record_count"] == 1
    assert report["D1"]["public_evidence_item_count"] == 2
    assert report["D3"]["public_evidence_item_count"] == 3


def test_current_d1_d3_projection_covers_the_formal_pool_without_internal_public_terms():
    root = Path(__file__).resolve().parents[1]
    d1 = load_json(root / D1_PATH)
    d3 = load_json(root / D3_PATH)
    report = verify_public_projection(root, payloads={"D1": d1, "D3": d3})

    assert report["record_count"] == len(d1["records"]) == len(d3["records"])
    assert {row["ruler_id"] for row in d1["records"]} == {row["ruler_id"] for row in d3["records"]}
    for payload in (d1, d3):
        for row in payload["records"]:
            fields = [row["public_adjudication_summary"]]
            fields.extend(
                item[field]
                for item in row["public_evidence_items"]
                for field in PUBLIC_EVIDENCE_FIELDS
                if field != "id"
            )
            assert all(not PUBLIC_FORBIDDEN_RE.search(value) for value in fields)


def test_reader_uses_the_complete_formal_d1_d3_public_projection():
    root = Path(__file__).resolve().parents[1]
    d1 = {row["ruler_name"]: row for row in load_json(root / D1_PATH)["records"]}
    d3 = {row["ruler_name"]: row for row in load_json(root / D3_PATH)["records"]}
    seen = {"D1": 0, "D3": 0}

    for path in (root / "reader/data/people").glob("*.json"):
        detail = json.loads(path.read_text(encoding="utf-8"))
        person_name = (detail.get("record") or {}).get("ruler_name")
        handoff = ((detail.get("record") or {}).get("net") or {}).get("component_details", {}).get("handoff", [])
        for item in handoff:
            label = item.get("label")
            if label == "D1继任行政连续性":
                formal = d1[person_name]
                axis = "D1"
            elif label == "D3政权交接稳定":
                formal = d3[person_name]
                axis = "D3"
            else:
                continue
            seen[axis] += 1
            assert item["reader_public_evidence_items"] == formal["public_evidence_items"]
            assert item["public_adjudication_summary"] == formal["public_adjudication_summary"]
            assert "reader_full_basis" not in item
            assert len(item["reader_public_evidence_items"]) >= 1

    assert seen["D1"] > 0
    assert seen["D3"] > 0
