from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_b2_public import (
    B2_PATH,
    PUBLIC_FORBIDDEN_RE,
    _refresh_payload,
    _scoring_signature,
    verify_public_projection,
)


def _profile(*, direction: str, weight: float, mechanism: str, lifecycle: str | None = None) -> dict:
    row = {
        "M": "M2",
        "direction": direction,
        "direction_factor": 1.0 if weight >= 0 else -1.0,
        "signed_weight": weight,
        "material_id": mechanism,
        "mechanism": mechanism,
        "result_closure": "observed_or_repeated",
    }
    if lifecycle:
        row["lifecycle_key"] = lifecycle
    return row


def _row() -> dict:
    return {
        "ruler_id": "SYNTHETIC-B2-RULER",
        "ruler_name": "合成甲",
        "grade": "G2",
        "position": "middle",
        "direction_index": 38.0,
        "rank": 1,
        "grade_basis": "一条M2反馈链实际改变决策，另一阶段形成负向约束；主档G2，生命周期只计算一次。",
        "M_positive_profile": [
            _profile(direction="positive", weight=1.0, mechanism="外部意见改变处置", lifecycle="L1"),
            _profile(direction="positive", weight=1.0, mechanism="低位信息进入中枢"),
        ],
        "M_mixed_profile": [
            _profile(direction="mixed_positive", weight=0.5, mechanism="同一反馈链的纠偏与保护", lifecycle="L1"),
        ],
        "M_negative_profile": [
            _profile(direction="negative", weight=-1.0, mechanism="反馈者受到压制", lifecycle="L2"),
        ],
    }


def test_b2_public_projection_groups_only_declared_lifecycles_and_keeps_all_items():
    payload = {"records": [_row()]}
    before = deepcopy(payload)
    projected = _refresh_payload(payload)
    row = projected["records"][0]

    assert len(row["public_evidence_items"]) == 3
    assert row["public_evidence_items"][0]["public_direction"] == "正向主导"
    assert row["public_evidence_items"][1]["public_direction"] == "正向"
    assert _scoring_signature(projected) == _scoring_signature(before)
    assert not PUBLIC_FORBIDDEN_RE.search(row["public_adjudication_summary"])
    assert all(
        not PUBLIC_FORBIDDEN_RE.search(field)
        for item in row["public_evidence_items"]
        for key in ("public_label", "public_basis", "public_boundary")
        for field in [item[key]]
    )
    assert verify_public_projection(Path("."), projected)["public_evidence_item_count"] == 3


def test_current_b2_public_projection_covers_the_formal_pool():
    root = Path(__file__).resolve().parents[1]
    payload = load_json(root / B2_PATH)
    report = verify_public_projection(root, payload=payload)

    assert report["record_count"] == len(payload["records"])
    assert report["profile_count"] >= report["public_evidence_item_count"]


def test_reader_details_project_all_current_b2_public_evidence():
    root = Path(__file__).resolve().parents[1]
    projected = []
    for path in (root / "reader/data/people").glob("*.json"):
        detail = json.loads(path.read_text(encoding="utf-8"))
        for item in ((detail.get("record") or {}).get("net") or {}).get("component_details", {}).get("method", []):
            if item.get("label") == "B2反馈与约束":
                projected.append(item)

    assert projected
    for item in projected:
        assert item["reader_public_evidence_items"] == item["public_evidence_items"]
        assert len(item["reader_public_evidence_items"]) == len(item["reader_highlights"])
        assert "reader_full_basis" not in item
