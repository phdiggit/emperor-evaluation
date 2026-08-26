from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
SETTLEMENT = PROFILE_ROOT / "19-C2信息处理学习与纠错正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "20-C2主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "21-C2高档学习周期与横向校准复核.json"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
POOL = ROOT / "config" / "common" / "canonical-ruler-pool.json"
CONTRACT = ROOT / "docs" / "项目总纲" / "皇帝人物画像评估体系合同.md"
PROJECT = ROOT / "config" / "project.yml"


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise AssertionError(f"UTF-8 BOM is forbidden: {path}")
    raw.decode("utf-8")
    return raw


def _load(path: Path):
    return json.loads(_read(path).decode("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(_read(path)).hexdigest()


def _included_ids() -> set[str]:
    return {
        row["ruler_id"]
        for row in _load(POOL)["records"]
        if row["pool_status"] == "INCLUDED"
    }


def _markdown_rows() -> list[list[str]]:
    rows = []
    for line in _read(MARKDOWN).decode("utf-8").splitlines():
        if line.startswith("| ") and not line.startswith("|---") and "雷达值" not in line:
            rows.append([cell.strip() for cell in line[1:-1].split("|")])
    return rows


def verify() -> dict[str, object]:
    settlement = _load(SETTLEMENT)
    records = settlement["records"]
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["formal_profile_write"] is True
    assert settlement["formal_rank_write"] is False
    assert settlement["profile_total_enabled"] is False
    assert settlement["database_write"] is False
    assert settlement["record_count"] == len(records) == 184
    assert settlement["schema_version"] == "profile-c2-formal-settlement-v2"
    assert settlement["canonical_pool_sha256"] == _sha(POOL)
    assert settlement["contract_sha256"] == _sha(CONTRACT)
    assert {row["ruler_id"] for row in records} == _included_ids()
    assert len({row["task_code"] for row in records}) == 184
    assert records == sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"]))
    required = {
        "task_code", "ruler_id", "ruler_name", "axis_grade", "position",
        "radar_value", "axis_evidence_level", "output_mode", "confidence",
        "score_status", "adjudication_ref", "representative_parent_contexts",
        "typical_pattern", "counterpattern", "grade_basis", "position_basis",
        "axis_relevance_check", "limitations", "formal_status", "parents",
    }
    assert all(required <= row.keys() for row in records)
    assert all(row["axis_evidence_level"] in {"E1", "E2", "E3"} for row in records)
    assert all(row["axis_grade"] in {f"G{i}" for i in range(6)} for row in records)
    assert all(row["position"] in {"LOW", "MID", "HIGH"} for row in records)
    assert all(row["radar_value"] == row["score_100"] for row in records)
    assert all(row["formal_status"] == "FORMAL_CURRENT" for row in records)
    assert all(row["same_chain_semantic_conflict_review_status"] == "REVIEWED_NO_UNRESOLVED_CONFLICT" for row in records)
    assert all(
        (row["axis_evidence_level"] == "E1")
        == (row["score_status"] == "EVIDENCE_LIMITED" and bool(row["limitations"]))
        for row in records
    )
    assert settlement["summary"]["unresolved_count"] == 0

    # Reject pool-wide prose templates and neutral defaults without evidence.
    assert len({row["grade_basis"] for row in records}) == 184
    assert len({row["position_basis"] for row in records}) == 184
    assert all(row["ruler_name"] in row["grade_basis"] for row in records)
    assert all(row["ruler_name"] in row["position_basis"] for row in records)
    forbidden_templates = {
        "逐人复核父链所列反馈到达、本人理解、判断更新、行为改变与后续复验后作整体裁决；既有A2/B2档位、分数与材料数量均未换算。",
        "PASSED_MANUAL_REVIEW",
    }
    assert all(not any(template in row["grade_basis"] for template in forbidden_templates) for row in records)
    no_parent = [row for row in records if not row["parents"]]
    assert no_parent
    assert all(
        row["axis_evidence_level"] == "E1"
        and row["score_status"] == "EVIDENCE_LIMITED"
        and row["axis_grade"] in {"G0", "G1"}
        and len(row["limitations"]) >= 2
        for row in no_parent
    )

    parent_ids = [parent["parent_id"] for row in records for parent in row["parents"]]
    assert len(parent_ids) == len(set(parent_ids))
    for row in records:
        scoring = {parent["parent_id"] for parent in row["parents"]}
        assert set(row["axis_relevance_check"]["scoring_parent_refs"]) == scoring
        for parent in row["parents"]:
            assert parent["direction"] in {"POSITIVE", "MIXED_POSITIVE", "MIXED", "MIXED_NEGATIVE", "NEGATIVE"}
            assert parent["intensity"].startswith("MI")
            assert parent["cycle_anchor_refs"]
            assert "C5" in parent["secondary_projection_reason"]
            assert parent["basis"] and parent["lifecycle_review"]
            assert len(parent["basis"]) <= 400
        directions = {parent["direction"] for parent in row["parents"]}
        assert not (
            row["grade_numeric"] >= 3
            and directions
            and directions <= {"NEGATIVE", "MIXED_NEGATIVE"}
        ), f"grade contradicts all-negative lifecycle text: {row['ruler_name']}"
        if row["axis_grade"] in {"G4", "G5"}:
            assert len(row["parents"]) >= 2, f"high grade uses giant/single parent: {row['ruler_name']}"

    audit = _load(AUDIT)
    assert audit["canonical_status"] == "FORMAL_CURRENT"
    assert audit["record_count"] == 184
    assert audit["unit_count"] == len(audit["units"])
    assert audit["unresolved_count"] == 0
    assert audit["status_counts"]["UNRESOLVED_EVIDENCE_GAP"] == 0
    assert len({unit["unit_id"] for unit in audit["units"]}) == len(audit["units"])
    assert all(unit["source_exists_or_external"] for unit in audit["units"])
    assert audit["status_counts"]["SCORING_PARENT"] > 0
    assert audit["status_counts"]["BACKGROUND_VALIDATION"] > 0
    assert audit["status_counts"]["AXIS_OUT_WITH_REASON"] > 0
    assert len({unit["reason"] for unit in audit["units"]}) >= int(audit["unit_count"] * 0.95)
    assert {
        unit["scoring_parent_id"]
        for unit in audit["units"]
        if unit["status"] == "SCORING_PARENT"
    } <= set(parent_ids)
    assert set(parent_ids) <= {
        parent_id
        for unit in audit["units"]
        for parent_id in unit.get("supports_parent_ids", [])
    }

    high = _load(HIGH_REVIEW)
    expected_high = {row["ruler_id"] for row in records if row["axis_grade"] in {"G4", "G5"}}
    assert {row["ruler_id"] for row in high["profiles"]} == expected_high
    assert high["schema_version"] == "profile-c2-high-grade-calibration-v2"
    assert all(row["independent_cycle_count"] == len(row["learning_cycles"]) >= 2 for row in high["profiles"])
    assert all(row["independence_basis"] and row["later_retest_basis"] and row["c5_boundary_basis"] for row in high["profiles"])
    assert all(
        cycle["lifecycle_basis"] and cycle["anchor_refs"] and cycle["semantic_closure"]
        for row in high["profiles"]
        for cycle in row["learning_cycles"]
    )
    assert "PASSED_MANUAL_REVIEW" not in _read(HIGH_REVIEW).decode("utf-8")
    assert '"later_retest_review": "PASSED"' not in _read(HIGH_REVIEW).decode("utf-8")

    md_rows = _markdown_rows()
    assert len(md_rows) == 184
    assert [
        (int(cells[0]), cells[1], cells[2], cells[3], cells[4], cells[5], cells[6])
        for cells in md_rows
    ] == [
        (row["radar_value"], row["axis_grade"], row["position"], row["ruler_name"], row["polity"], row["axis_evidence_level"], row["confidence"])
        for row in records
    ]

    manifest = _load(MANIFEST)
    axis = next(row for row in manifest["axes"] if row["axis_code"] == "C2")
    assert axis["json"] == SETTLEMENT.name
    assert axis["markdown"] == MARKDOWN.name
    assert axis["json_sha256"] == _sha(SETTLEMENT)
    project = yaml.safe_load(_read(PROJECT).decode("utf-8"))
    assert project["profile_assessment"]["settled_axes"]["C2"]["json"].endswith(SETTLEMENT.name)

    hashes = {path.name: _sha(path) for path in (SETTLEMENT, MARKDOWN, AUDIT, HIGH_REVIEW)}
    combined = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "status": "PASS",
        "record_count": len(records),
        "evidence_limited_count": settlement["summary"]["evidence_limited_count"],
        "grade_distribution": settlement["summary"]["grade_distribution"],
        "unit_count": audit["unit_count"],
        "high_grade_count": len(high["profiles"]),
        "parent_count": len(parent_ids),
        "no_parent_evidence_limited_count": len(no_parent),
        "hashes": hashes,
        "combined_sha256": combined,
    }


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
