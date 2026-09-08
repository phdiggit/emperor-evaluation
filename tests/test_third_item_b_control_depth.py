from copy import deepcopy

import pytest

from emperor_v4.evaluation.third_item_b_control_depth import (
    control_depth_package_ids, render_control_depth_packages,
)
from emperor_v4.evaluation.third_item_current_settlement import _validate_ab_control_contribution_contract


def row():
    return {
        "ruler_id": "synthetic-ruler", "ruler_name": "合成主体",
        "parent_cycle_refs": ["prior-war"], "evidence_event_refs": [],
        "control_depth_packages": [{
            "package_id": "B-DEPTH-synthetic", "object_name": "同一边疆据点网络",
            "assessment_window": "同一实际主政窗口", "entry_control": "依赖临时征军",
            "handover_control": "常设屯兵与支援网络", "ruler_action": "批准并执行驻守改制",
            "cross_item_boundary": "不计空间、行政或社会整合", "all_results_review": "其他主要成果已核",
            "context_parent_refs": ["prior-war"], "spatial_increment_claimed": False,
            "sources": [{"title": "合成史源", "url": "https://example.org/source", "locator": "独立段",
                         "evidence": "驻守改制实际交付"}],
        }],
        "primary_control_package_refs": ["B-DEPTH-synthetic"],
        "control_contribution_type": "NEW_RECOVERED_REBUILT", "control_contribution_grade_cap": 5,
        "axes": {
            "B2": {"grade": "B2-2", "band_position": "LOW", "score_rate": 45},
            "B4": {"grade": "B4-3", "band_position": "LOW", "score_rate": 60},
        },
    }


def test_independent_control_package_does_not_mutate_battle_context():
    r = row()
    before = deepcopy(r)
    assert control_depth_package_ids(r) == {"B-DEPTH-synthetic"}
    rendered = "\n".join(render_control_depth_packages(r))
    assert "https://example.org/source" in rendered
    assert r == before
    assert "B-DEPTH-synthetic" not in r["parent_cycle_refs"]


@pytest.mark.parametrize("fault", ["area", "missing_action", "excluded", "unknown_context", "duplicate", "missing_source"])
def test_control_depth_evidence_gates(fault):
    r = row()
    p = r["control_depth_packages"][0]
    if fault == "area":
        p["spatial_increment_claimed"] = True
    elif fault == "missing_action":
        p["ruler_action"] = ""
    elif fault == "excluded":
        r["excluded_founding_unification_refs"] = ["prior-war"]
    elif fault == "unknown_context":
        p["context_parent_refs"] = ["unregistered"]
    elif fault == "duplicate":
        r["control_depth_packages"].append(deepcopy(p))
    else:
        p["sources"] = []
    with pytest.raises(ValueError):
        control_depth_package_ids(r)


def test_current_source_controls_formal_evidence_and_subject_binding():
    r = row()
    source = {"control_contribution_corrections": [{
        "ruler_id": r["ruler_id"], "control_depth_packages": deepcopy(r["control_depth_packages"]),
    }]}
    _validate_ab_control_contribution_contract({"records": [r]}, depth_source=source)
    r["control_depth_packages"][0]["ruler_action"] = "改写正式副本"
    with pytest.raises(ValueError, match="裁决源"):
        _validate_ab_control_contribution_contract({"records": [r]}, depth_source=source)
    second = deepcopy(r)
    second["ruler_id"] = "another-ruler"
    with pytest.raises(ValueError, match="跨主体"):
        _validate_ab_control_contribution_contract({"records": [r, second]})


def test_primary_control_reference_must_resolve_to_registered_package():
    r = row()
    r["primary_control_package_refs"] = ["B-DEPTH-unregistered"]
    with pytest.raises(ValueError, match="主控制成果引用"):
        _validate_ab_control_contribution_contract({"records": [r]})
