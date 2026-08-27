from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
SETTLEMENT = PROFILE_ROOT / "24-C3人才识别配置与授权正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "25-C3主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "26-C3高档授权生命周期复核.json"
ACCEPTANCE = PROFILE_ROOT / "27-C3全池结算验收报告.md"
MANUAL = ROOT / "config" / "profile" / "c3-adjudications.json"
POOL = ROOT / "config" / "common" / "canonical-ruler-pool.json"
CONTRACT = ROOT / "docs" / "项目总纲" / "皇帝人物画像评估体系合同.md"
PROJECT = ROOT / "config" / "project.yml"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"

SCORES = {
    "G0": {"LOW": 2, "MID": 7, "HIGH": 12}, "G1": {"LOW": 18, "MID": 25, "HIGH": 31},
    "G2": {"LOW": 38, "MID": 45, "HIGH": 51}, "G3": {"LOW": 58, "MID": 65, "HIGH": 71},
    "G4": {"LOW": 77, "MID": 82, "HIGH": 87}, "G5": {"LOW": 91, "MID": 94, "HIGH": 97},
}


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {path}"
    raw.decode("utf-8")
    return raw


def _load(path: Path) -> Any:
    return json.loads(_read(path).decode("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(_read(path)).hexdigest()


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _assert_no_mechanical_adjudicator(*payloads: Any) -> None:
    forbidden_keys = {
        "keyword_hits", "matched_keywords", "keyword_score", "famous_minister_count",
        "office_count", "minister_count", "source_axis_grade", "source_axis_position",
        "source_axis_score", "inherited_grade", "inherited_direction", "inherited_intensity",
    }
    for payload in payloads:
        strings = []
        for value in _walk(payload):
            if isinstance(value, str):
                strings.append(value)
        assert not any(value in forbidden_keys for value in strings), "mechanical keyword/count/legacy adjudicator forbidden"


def _markdown_rows() -> list[list[str]]:
    rows = []
    for line in _read(MARKDOWN).decode("utf-8").splitlines():
        if line.startswith("| ") and "雷达值" not in line and not line.startswith("|---"):
            rows.append([cell.strip().replace("\\|", "|") for cell in line[1:-1].split("|")])
    return rows


def _clauses(text: str) -> list[str]:
    return [part.strip("。； \n") for part in re.split(r"[；。]", text) if part.strip("。； \n")]


def verify_payloads(settlement: dict[str, Any], audit: dict[str, Any], high: dict[str, Any]) -> dict[str, Any]:
    records = settlement["records"]
    pool = _load(POOL)
    included = {r["ruler_id"] for r in pool["records"] if r["pool_status"] == "INCLUDED"}
    assert settlement["schema_version"] == "profile-c3-formal-settlement-v1"
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["axis_code"] == "C3"
    assert settlement["contract_sha256"] == _sha(CONTRACT) == "11a0b60464214c125a6805b68dc83b95ecb75135500bcea8cbe11cc6d2af76aa"
    assert settlement["canonical_pool_sha256"] == _sha(POOL)
    assert settlement["manual_adjudication_sha256"] == _sha(MANUAL)
    assert settlement["record_count"] == len(records) == 184
    assert {r["ruler_id"] for r in records} == included
    assert len({r["task_code"] for r in records}) == 184
    assert all(r["task_code"] == f"PROFILE-C3-{r['ruler_id']}" for r in records)
    assert records == sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"]))
    assert settlement["formal_rank_write"] is False and settlement["profile_total_enabled"] is False
    assert settlement["profile_ranking_enabled"] is False and settlement["database_write"] is False
    _assert_no_mechanical_adjudicator(settlement, audit, high)

    required = {
        "task_code", "ruler_id", "axis_grade", "position", "radar_value", "axis_evidence_level",
        "output_mode", "confidence", "score_status", "parents", "typical_pattern", "grade_basis",
        "position_basis", "axis_relevance_check", "limitations", "adjudication_ref",
    }
    assert all(required <= row.keys() for row in records)
    assert all(row["radar_value"] == row["score_100"] == SCORES[row["axis_grade"]][row["position"]] for row in records)
    assert all(row["formal_status"] == "FORMAL_CURRENT" for row in records)
    assert all(row["axis_evidence_level"] in {"E1", "E2", "E3"} for row in records)
    assert all(row["output_mode"] in {"EPISODE_TAG", "BOUNDED_PROFILE", "FULL_GRADE"} for row in records)
    assert all(row["score_status"] in {"FINAL", "EVIDENCE_LIMITED"} for row in records)

    parent_ids = []
    narratives = []
    for row in records:
        check = row["axis_relevance_check"]
        assert check == {
            "famous_minister_count_used": False, "office_count_used": False,
            "final_outcome_backsolve_used": False, "c5_ethics_leakage": False,
            "m4_group_outcome_leakage": False,
        }
        if not row["parents"]:
            assert row["score_status"] == "EVIDENCE_LIMITED"
            assert row["axis_evidence_level"] == "E1" and row["output_mode"] == "EPISODE_TAG"
            assert row["limitations"] and len(row["typical_pattern"]) >= 20
        if row["score_status"] == "EVIDENCE_LIMITED":
            assert row["axis_evidence_level"] != "E3"
            assert row["axis_grade"] not in {"G4", "G5"}
        pattern_clauses = _clauses(row["typical_pattern"])
        assert len(pattern_clauses) == len(set(pattern_clauses)), f"duplicate typical-pattern clause: {row['ruler_name']}"
        for parent in row["parents"]:
            parent_ids.append(parent["parent_id"])
            narratives.append(parent["lifecycle_narrative"])
            assert parent["closure_status"] == "CLOSED"
            assert parent["direction"] in {"POSITIVE", "NEGATIVE", "MIXED", "MIXED_POSITIVE", "MIXED_NEGATIVE"}
            assert parent["material_strength"] in {"MI1", "MI2", "MI3", "MI4"}
            assert parent["source_refs"]
            for field in ("task_requirement", "candidate_identification", "position_configuration", "actual_authority", "delivery", "feedback", "authorization_response"):
                assert str(parent[field]).strip(), f"open parent lifecycle: {parent['parent_id']} {field}"
            lifecycle_clauses = _clauses(parent["lifecycle_narrative"])
            assert len(lifecycle_clauses) == len(set(lifecycle_clauses)), f"duplicate lifecycle clause: {parent['parent_id']}"
            if row["axis_grade"] in {"G4", "G5"}:
                states = [str(parent[field]).strip() for field in (
                    "task_requirement", "candidate_identification", "position_configuration", "actual_authority",
                    "delivery", "feedback", "authorization_response",
                )]
                assert len(set(states)) >= 5, f"high-grade template lifecycle: {parent['parent_id']}"
            boundary = parent["boundary_review"]
            assert set(boundary) == {"c5_excluded", "m4_excluded", "result_only_excluded"}
        directions = {p["direction"] for p in row["parents"]}
        if row["axis_grade"] in {"G4", "G5"}:
            assert len(row["parents"]) >= 2, "single giant chain cannot support G4/G5"
            assert len(row["major_task_domains_observed"]) >= 2, "high grade requires cross-task retest"
            assert directions != {"NEGATIVE"}
        if row["axis_grade"] == "G0":
            assert "POSITIVE" not in directions or directions & {"NEGATIVE", "MIXED", "MIXED_NEGATIVE"}
    assert len(parent_ids) == len(set(parent_ids)), "C3 parent IDs must be globally unique"
    assert len(set(narratives)) >= 150, "template evidence detected: lifecycle narratives insufficiently individualized"
    assert len(set(row["typical_pattern"] for row in records)) >= 175, "template person bases detected"

    assert audit["schema_version"] == "profile-c3-unit-disposition-audit-v1"
    assert audit["record_count"] == 184 and audit["unit_count"] == len(audit["units"])
    assert audit["unresolved_count"] == 0
    allowed = {"SCORING_PARENT", "BACKGROUND_VALIDATION", "AXIS_OUT_WITH_REASON", "UNRESOLVED_EVIDENCE_GAP"}
    assert set(audit["status_counts"]) <= allowed
    assert set(audit["status_counts"]) >= {"SCORING_PARENT", "BACKGROUND_VALIDATION", "AXIS_OUT_WITH_REASON"}
    assert all(unit["status"] in allowed for unit in audit["units"])
    parent_set = set(parent_ids)
    assert all(unit["scoring_parent_id"] in parent_set for unit in audit["units"] if unit["status"] == "SCORING_PARENT")
    assert all(unit["reason"].strip() for unit in audit["units"])
    assert len({unit["unit_id"] for unit in audit["units"]}) == len(audit["units"])
    assert any(len(statuses) >= 2 for statuses in audit["entry_status_counts"].values()), "uniform entry disposition forbidden"
    explicit = [unit for unit in audit["units"] if unit["entry"] == "C3_EXPLICIT_ADJUDICATION"]
    assert {unit["scoring_parent_id"] for unit in explicit} == parent_set, "every C3 parent needs an explicit audit unit"

    assert high["schema_version"] == "profile-c3-high-grade-review-v1"
    assert all(review["supplemental_primary_unit_count"] <= 4 for review in high["reviews"])
    assert all("貞觀政要" not in ref for review in high["reviews"] for ref in review["supplemental_primary_units"])
    high_ids = {row["ruler_id"] for row in records if row["axis_grade"] in {"G4", "G5"}}
    high_review_ids = {row["ruler_id"] for row in high["reviews"] if row["review_outcome"] == "HIGH_GRADE_SUPPORTED"}
    assert high_ids == high_review_ids
    assert all(review["multiple_named_lifecycle_gate"] == "PASS" and review["cross_task_or_phase_retest"] == "PASS" for review in high["reviews"] if review["ruler_id"] in high_ids)

    rows = _markdown_rows()
    assert len(rows) == 184
    for md, record in zip(rows, records):
        assert md[1] == record["ruler_name"]
        assert md[4:10] == [record["axis_grade"], record["position"], str(record["radar_value"]), record["axis_evidence_level"], record["output_mode"], record["score_status"]]
        assert md[10] == str(len(record["parents"]))
    return {"status": "PASS", "record_count": 184, "parent_count": len(parent_ids), "audit_unit_count": audit["unit_count"]}


def verify() -> dict[str, Any]:
    settlement, audit, high = _load(SETTLEMENT), _load(AUDIT), _load(HIGH_REVIEW)
    result = verify_payloads(settlement, audit, high)
    project = yaml.safe_load(_read(PROJECT).decode("utf-8"))
    profile = project["profile_assessment"]
    assert profile["status"] == "six_axes_formally_settled"
    assert set(profile["settled_axes"]) == {"M1", "M2", "C1", "C2", "C3", "C5"}
    manifest = _load(MANIFEST)
    assert manifest["settled_axis_count"] == 6 and manifest["unsettled_axis_count"] == 2
    c3 = next(axis for axis in manifest["axes"] if axis["axis_code"] == "C3")
    assert c3["json"] == SETTLEMENT.name and c3["json_sha256"] == _sha(SETTLEMENT)
    assert c3["markdown_sha256"] == _sha(MARKDOWN)
    assert c3["record_count"] == 184
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
