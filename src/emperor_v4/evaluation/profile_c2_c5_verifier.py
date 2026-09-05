from __future__ import annotations

import json
from pathlib import Path

import yaml

from emperor_v4.evaluation.formal_json_store import load_json

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
C5 = PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json"
C5_MD = C5.with_suffix(".md")
C5_AUDIT = PROFILE_ROOT / "C5/04-C5主要入口单元处置审计.json"
C5_DENSITY = PROFILE_ROOT / "C5/05-C5高档材料密度复核.json"
C5_STRUCTURE = PROFILE_ROOT / "C5/07-C5高档与证据门结构复核.json"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
PROJECT = ROOT / "config" / "project.yml"

GRADE_POINTS = {
    "G0": {"LOW": 2, "MID": 7, "HIGH": 12},
    "G1": {"LOW": 18, "MID": 25, "HIGH": 31},
    "G2": {"LOW": 38, "MID": 45, "HIGH": 51},
    "G3": {"LOW": 58, "MID": 65, "HIGH": 71},
    "G4": {"LOW": 77, "MID": 82, "HIGH": 87},
    "G5": {"LOW": 91, "MID": 94, "HIGH": 97},
}
OUTPUT_BY_EVIDENCE = {
    "E1": ("EPISODE_TAG", "LOW", "EVIDENCE_LIMITED"),
    "E2": ("BOUNDED_PROFILE", "MEDIUM", "EVIDENCE_LIMITED"),
    "E3": ("FULL_GRADE", "HIGH", "FINAL"),
}


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM is forbidden: {path}"
    raw.decode("utf-8")
    return raw


def _load(path: Path) -> dict:
    _read(path)
    return load_json(path)


def _md_rows() -> list[tuple[int, str, str, str, str, str]]:
    rows = []
    for line in _read(C5_MD).decode("utf-8").splitlines():
        if line.startswith("| ") and not line.startswith("|---") and "展示序" not in line:
            cells = [cell.strip().replace("\\|", "|") for cell in line[1:-1].split("|")]
            rows.append((int(cells[5]), cells[3], cells[2], cells[6], cells[7], cells[8]))
    return rows


def verify() -> dict[str, object]:
    c5, audit, density, structure = (
        _load(path) for path in (C5, C5_AUDIT, C5_DENSITY, C5_STRUCTURE)
    )
    assert _read(C5_MD).decode("utf-8") == render_profile_markdown(c5)
    c5_by_id = {row["ruler_id"]: row for row in c5["records"]}
    pool = _load(ROOT / "config/common/canonical-ruler-pool.json")
    assert set(c5_by_id) == {r["ruler_id"] for r in pool["records"] if r["pool_status"] == "INCLUDED"}

    allowed_same_chain = {"NO_TRIGGER", "CONSTRUCT_SEPARATED"}
    c5_statuses = {row["same_chain_semantic_conflict_review_status"] for row in c5["records"]}
    assert c5_statuses <= allowed_same_chain

    c5_parent_ids = set()
    for row in c5["records"]:
        assert row["grade_numeric"] == int(row["axis_grade"][1])
        assert row["radar_value"] == row["score_100"] == GRADE_POINTS[row["axis_grade"]][row["position"]]
        assert (row["output_mode"], row["confidence"], row["score_status"]) == OUTPUT_BY_EVIDENCE[
            row["axis_evidence_level"]
        ]
        parents = {parent["parent_id"]: parent for parent in row["parents"]}
        assert len(parents) == len(row["parents"])
        c5_parent_ids.update(parents)
        assert set(row["axis_relevance_check"]["scoring_parent_refs"]) == set(parents)
        for group in row["unit_groups"]:
            if group["status"] == "SCORING_PARENT":
                assert group["parent_id"] in parents
            else:
                assert "parent_id" not in group or group["parent_id"] is None
        directions = {parent["direction"] for parent in row["parents"]}
        if row["grade_numeric"] >= 3 and directions and directions <= {"NEGATIVE", "MIXED_NEGATIVE"}:
            assert row["review_status"] in {"RECALIBRATED", "VALIDATED"}
            assert row["public_evidence_points"] and row["source_refs"]
        assert not (row["grade_numeric"] == 0 and directions and directions <= {"POSITIVE", "MIXED_POSITIVE"})

    for row in c5_by_id.values():
        assert row["public_evidence_points"] and row["source_refs"]
        assert row["source_quality"]["named_source_count"] >= 1
        assert row["source_quality"]["locator_count"] >= 1

    units = audit["units"]
    assert audit["unit_count"] == len(units)
    assert len({unit["unit_id"] for unit in units}) == len(units)
    assert set(audit["status_counts"]) == {
        "SCORING_PARENT", "BACKGROUND_VALIDATION", "AXIS_OUT_WITH_REASON"
    }, "all entries cannot receive one uniform disposition"
    assert sum(audit["status_counts"].values()) == len(units)
    assert {unit["scoring_parent_id"] for unit in units if unit["status"] == "SCORING_PARENT"} <= c5_parent_ids
    assert all((unit["status"] == "SCORING_PARENT") == bool(unit["scoring_parent_id"]) for unit in units)

    assert _md_rows() == [
        (
            row["radar_value"], f"{row['axis_grade']}-{row['position']}", row["ruler_name"],
            row["axis_evidence_level"], row["confidence"], row["output_mode"],
        )
        for row in c5["records"]
    ]
    manifest = _load(MANIFEST)
    axis = next(item for item in manifest["axes"] if item["axis_code"] == "C5")

    return {
        "status": "PASS",
        "record_count": len(c5_by_id),
        "c5_parent_count": sum(len(row["parents"]) for row in c5["records"]),
        "c5_unit_count": len(units),
        "grade_distribution": c5["summary"]["grade_distribution"],
        "evidence_distribution": c5["summary"]["axis_evidence_distribution"],
    }


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
