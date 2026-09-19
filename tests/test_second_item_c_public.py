from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_c_public import (
    FORMAL_PATHS,
    PUBLIC_FORBIDDEN_RE,
    _refresh_payload,
    _scoring_signature,
    verify_public_projection,
)


def _state_row(axis: str) -> dict:
    return {
        "ruler_id": f"SYNTHETIC-{axis}",
        "ruler_name": "合成甲",
        "main_band": f"{axis}-3",
        "loss_grade": "L1",
        "score": 12.5,
        "adjudication_reason": "主要阶段形成可运行结果，另有局部损害。",
        "material_limitations": ["战争成本和制度设计不在本轴重复计算。"],
        "state_adjudication": {
            "loss_review": {
                "grade": "L1",
                "main_representativeness": "主要阶段形成可运行结果。",
                "basis": "局部地区出现实际损害。",
            }
        },
    }


def _c4_row() -> dict:
    return {
        "ruler_id": "SYNTHETIC-C4",
        "ruler_name": "合成甲",
        "score": 3.0,
        "recovery_path_basis": {
            "C1": {"start_band": "C1-2", "highest_achieved_band": "C1-3", "retained_increment": True},
            "C2": {"start_band": "C2-3", "highest_achieved_band": "C2-3", "retained_increment": False},
            "C3": {"start_band": "C3-2", "highest_achieved_band": "C3-2", "retained_increment": False},
        },
        "recovery_chain_attributions": {
            "C1": {"grade": "SHARED", "basis": "共同掌权，无法拆分。"},
        },
        "recovery_attribution": {"grade": "SHARED", "basis": "共同掌权。"},
        "deterioration_path_basis": {
            "C1": {"attributable_drop": 0, "attribution_factor": 0},
            "C2": {"attributable_drop": 0, "attribution_factor": 0},
            "C3": {"attributable_drop": 0, "attribution_factor": 0},
        },
        "deterioration_penalty": 0.0,
        "destructive_amplification_grade": "DA0",
        "active_civilian_cost_review": {
            "choice_and_civilian_basis": "未发现独立额外民力对象。",
            "absorbed_and_excluded_basis": "纯军事投入不在本轴重复计算。",
        },
    }


def test_c_public_projection_keeps_scoring_fields_and_exposes_every_required_role():
    for axis, row in [("C1", _state_row("C1")), ("C4", _c4_row())]:
        payload = {"records": [row]}
        before = deepcopy(payload)
        projected = _refresh_payload(axis, payload)
        expected_roles = {"主要状态", "低谷", "边界"} if axis != "C4" else {
            "恢复", "责任范围", "状态恶化", "额外代价", "边界"
        }
        actual = projected["records"][0]
        assert {item["public_role"] for item in actual["public_evidence_items"]} == expected_roles
        assert _scoring_signature(projected) == _scoring_signature(before)
        assert not PUBLIC_FORBIDDEN_RE.search(actual["public_adjudication_summary"])
        assert all(
            not PUBLIC_FORBIDDEN_RE.search(item[field])
            for item in actual["public_evidence_items"]
            for field in ("public_label", "public_role", "public_basis", "public_boundary")
        )


def test_current_c_public_projection_covers_the_same_formal_people():
    root = Path(__file__).resolve().parents[1]
    report = verify_public_projection(root)
    assert report["record_count"] == len(
        load_json(root / FORMAL_PATHS["C1"])["scores"]
    )
    assert set(report["axis_reports"]) == set(FORMAL_PATHS)
