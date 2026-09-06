from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.evaluation.third_item_b1_audit import build_b1_audit


ROUTER = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
ANCHORS = Path("config/third-item/third-item-b1-region-anchors.json")


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _anchor_payload() -> dict:
    return {
        "schema_id": "third-item-b1-region-anchor-registry-v1",
        "policy": {"coverage_steps": [0.0, 0.25, 0.5, 0.75, 1.0]},
        "anchors": [
            {"region_id": "NORTHWEST_FRONTIER", "spatial_weight": 0.8},
            {"region_id": "WESTERN_REGIONS_WHOLE", "spatial_weight": 2.0},
        ],
        "legacy_aliases": {"OLD_NW": "NORTHWEST_FRONTIER"},
        "legacy_must_rebuild": [{"legacy_id": "AGGREGATE_REVIEWED"}],
        "mutual_exclusion_sets": [],
    }


def _record(name: str = "甲") -> dict:
    return {
        "ruler_id": f"RULER-{name}",
        "ruler_name": name,
        "polity": "测试",
        "reign_range": "1-2",
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
                "spatial_weight": 0.8,
                "coverage_factor": 1.0,
                "anchors": ["start", "end"],
                "counted": True,
            }
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


def _workspace(tmp_path: Path, records: list[dict]) -> Path:
    _write(tmp_path / ANCHORS, _anchor_payload())
    shard_rel = "01-皇帝AB项正式结算/测试.json"
    _write(
        tmp_path / ROUTER,
        {
            "collections": {"records": {"record_count": len(records)}},
            "routes": [
                {
                    "polity": "测试",
                    "path": shard_rel,
                    "collection_counts": {"records": len(records)},
                }
            ],
        },
    )
    _write(
        (tmp_path / ROUTER).parent / shard_rel,
        {"collections": {"records": {"records": records}}},
    )
    return tmp_path


def _codes(row: dict) -> set[str]:
    return {issue["code"] for issue in row["issues"]}


def test_clean_record_passes_machine_consistency(tmp_path: Path) -> None:
    payload = build_b1_audit(_workspace(tmp_path, [_record()]))
    assert payload["record_count"] == 1
    assert payload["summary"]["blocked_count"] == 0
    assert payload["records"][0]["machine_consistency_status"] == "PASS"
    assert payload["records"][0]["b1_reaudit_required"] is True


def test_nonzero_snapshot_with_empty_ledger_is_blocked(tmp_path: Path) -> None:
    row = _record()
    row["b1_region_adjudications"] = []
    payload = build_b1_audit(_workspace(tmp_path, [row]))
    result = payload["records"][0]
    assert result["machine_consistency_status"] == "BLOCKED"
    assert "B1_EMPTY_LEDGER_NONZERO" in _codes(result)


def test_formula_and_override_conflicts_are_detected(tmp_path: Path) -> None:
    row = _record()
    row["b1_control_equivalents"]["weighted_value"] = 0.9
    row["B80_adjudication"]["formal_B1_rate"] = 90.0
    row["B80_adjudication"]["adjudicated_B1_rate"] = 90.0
    payload = build_b1_audit(_workspace(tmp_path, [row]))
    codes = _codes(payload["records"][0])
    assert "B1_WEIGHTED_VALUE_MISMATCH" in codes
    assert "B1_GRADE_MISMATCH" in codes
    assert "B1_AXIS_WEIGHTED_MISMATCH" in codes
    assert "B1_FORMAL_RATE_MISMATCH" in codes
    assert "B1_ADJUDICATED_RATE_MISMATCH" in codes


def test_adhoc_absolute_control_value_is_detected(tmp_path: Path) -> None:
    row = _record()
    row["b1_region_control"] = {
        "start": {"NORTHWEST_FRONTIER": 0.75},
        "end": {"NORTHWEST_FRONTIER": 0.75},
    }
    row["b1_control_equivalents"] = {
        "start": 0.75,
        "end": 0.75,
        "net_change": 0.0,
        "weighted_value": 0.3,
    }
    row["axes"]["B1"].update({"raw_net_change": 0.0, "weighted_control_value": 0.3})
    payload = build_b1_audit(_workspace(tmp_path, [row]))
    assert "B1_SNAPSHOT_NONSTANDARD_COVERAGE" in _codes(payload["records"][0])


def test_must_rebuild_legacy_region_is_blocked(tmp_path: Path) -> None:
    row = _record()
    row["b1_region_control"] = {
        "start": {"AGGREGATE_REVIEWED": 0.8},
        "end": {"AGGREGATE_REVIEWED": 0.8},
    }
    row["b1_region_adjudications"] = [
        {
            "object_id": "AGGREGATE_REVIEWED",
            "coverage_factor": 1.0,
            "counted": True,
        }
    ]
    payload = build_b1_audit(_workspace(tmp_path, [row]))
    codes = _codes(payload["records"][0])
    assert "B1_MUST_REBUILD_REGION" in codes
    assert "B1_MUST_REBUILD_LEDGER_REGION" in codes


def test_legacy_alias_is_warned_but_can_still_reconcile(tmp_path: Path) -> None:
    row = _record()
    row["b1_region_control"] = {
        "start": {"OLD_NW": 0.8},
        "end": {"OLD_NW": 0.8},
    }
    row["b1_region_adjudications"][0]["object_id"] = "OLD_NW"
    payload = build_b1_audit(_workspace(tmp_path, [row]))
    result = payload["records"][0]
    assert result["machine_consistency_status"] == "WARN"
    assert "B1_LEGACY_REGION_ALIAS" in _codes(result)
