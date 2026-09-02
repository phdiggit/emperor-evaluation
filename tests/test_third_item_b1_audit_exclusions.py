from __future__ import annotations

from emperor_v4.evaluation.third_item_b1_audit import audit_record


def test_non_counted_exclusion_does_not_require_region_anchor() -> None:
    anchors = {
        "policy": {"coverage_steps": [0.0, 0.25, 0.5, 0.75, 1.0]},
        "anchors": [{"region_id": "NORTHWEST_FRONTIER", "spatial_weight": 0.8}],
        "legacy_aliases": {},
        "legacy_must_rebuild": [],
        "mutual_exclusion_sets": [],
    }
    record = {
        "ruler_id": "RULER-TEST",
        "ruler_name": "测试",
        "polity": "测试",
        "axes": {
            "B1": {
                "grade": "B1-1",
                "score_rate": 37.0,
                "raw_net_change": 0.0,
                "weighted_control_value": 0.32,
            }
        },
        "b1_region_control": {
            "start": {"NORTHWEST_FRONTIER": 0.8},
            "end": {"NORTHWEST_FRONTIER": 0.8},
        },
        "b1_region_adjudications": [
            {
                "object_id": "NORTHWEST_FRONTIER",
                "counted": True,
                "spatial_weight": 0.8,
                "coverage_factor": 1.0,
            },
            {
                "object_id": "UNIFICATION_CORE_EXCLUSION_ONLY",
                "counted": False,
                "reason": "第一项已消费，仅保留排除说明。",
            },
        ],
        "b1_control_equivalents": {
            "start": 0.8,
            "end": 0.8,
            "net_change": 0.0,
            "weighted_value": 0.32,
        },
        "B80_adjudication": {
            "formal_B1_rate": 37.0,
            "adjudicated_B1_rate": 37.0,
        },
    }
    result = audit_record(record, anchors)
    assert result["machine_consistency_status"] == "PASS"
    assert not any(issue["code"] == "B1_UNKNOWN_LEDGER_REGION" for issue in result["issues"])
