from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANCHOR_PATH = ROOT / "config/third-item/third-item-b1-region-anchors.json"


def _load() -> dict:
    return json.loads(ANCHOR_PATH.read_text(encoding="utf-8"))


def test_b1_anchor_registry_is_structurally_closed() -> None:
    payload = _load()
    assert payload["schema_id"] == "third-item-b1-region-anchor-registry-v1"
    assert payload["canonical_status"] == "FORMAL_CURRENT"
    assert payload["policy"]["coverage_steps"] == [0.0, 0.25, 0.5, 0.75, 1.0]

    anchors = payload["anchors"]
    ids = [row["region_id"] for row in anchors]
    assert len(ids) == len(set(ids))
    assert all(float(row["spatial_weight"]) > 0 for row in anchors)

    id_set = set(ids)
    for target in payload["legacy_aliases"].values():
        assert target in id_set
    for group in payload["mutual_exclusion_sets"]:
        assert group["members"]
        assert set(group["members"]).issubset(id_set)

    must_rebuild = {row["legacy_id"] for row in payload["legacy_must_rebuild"]}
    assert must_rebuild.isdisjoint(payload["legacy_aliases"])


def test_b1_anchor_registry_keeps_v1_extensions_explicit() -> None:
    payload = _load()
    extensions = {
        row["region_id"]: row
        for row in payload["anchors"]
        if row["origin"] == "V1_EXTENSION_CALIBRATED"
    }
    assert set(extensions) == {
        "TIBETAN_PLATEAU_SYSTEM",
        "NORTHEAST_LIAODONG_SONGWAI",
        "ANNAM_NORTHERN_VIETNAM",
        "HAMI_GATEWAY",
    }
    assert all(row.get("calibration_basis") for row in extensions.values())


def test_b1_grade_threshold_contract_is_frozen() -> None:
    payload = _load()
    assert payload["grade_thresholds"] == [
        {"grade": "B1-0", "condition": "weighted_control_value <= 0"},
        {"grade": "B1-1", "condition": "0 < weighted_control_value < 0.75"},
        {"grade": "B1-2", "condition": "0.75 <= weighted_control_value < 1.5"},
        {"grade": "B1-3", "condition": "1.5 <= weighted_control_value < 3.0"},
        {"grade": "B1-4", "condition": "3.0 <= weighted_control_value < 6.0"},
        {"grade": "B1-5", "condition": "weighted_control_value >= 6.0"},
    ]
