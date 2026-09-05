from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.formal_json_store import load_json

from emperor_v4.evaluation.profile_markdown import render_profile_markdown

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
SETTLEMENT = PROFILE_ROOT / "C3/24-C3人才识别配置与授权正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "C3/25-C3主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "C3/26-C3高档授权生命周期复核.json"
SYSTEMIC_REVIEW = PROFILE_ROOT / "C3/28-C3高档门与错误清洗系统复核.json"
C5_SETTLEMENT = PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json"
POOL = ROOT / "config" / "common" / "canonical-ruler-pool.json"
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
    _read(path)
    return load_json(path)


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


def verify_payloads(settlement: dict[str, Any], audit: dict[str, Any], high: dict[str, Any], systemic: dict[str, Any]) -> dict[str, Any]:
    records = settlement["records"]
    pool = _load(POOL)
    included = {r["ruler_id"] for r in pool["records"] if r["pool_status"] == "INCLUDED"}
    assert settlement["schema_version"] == "profile-c3-formal-settlement-v1"
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["axis_code"] == "C3"
    assert settlement["contract_version"]
    assert settlement["authority_mode"] == "FORMAL_SETTLEMENT_PATCH_SOURCE"
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
        "position_basis", "axis_relevance_check", "limitations",
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
            assert not re.match(r"^按\d+条", row["grade_basis"]), "high grade requires person-specific gate basis"
            assert row["axis_grade"] in row["grade_basis"], "high-grade basis must name the published gate"
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

    assert systemic["schema_version"] == "profile-c3-systemic-review-v1"
    assert systemic["record_count"] == systemic["mechanical_screen_count"] == 184
    assert systemic["open_latent_high_count"] == high["latent_high_candidate_count"] == 0
    assert len(systemic["records"]) == 184
    assert {row["ruler_id"] for row in systemic["records"]} == included
    assert all(row["review_status"] in {"SEMANTIC_HIT_REVIEWED", "MECHANICAL_SCREEN_NO_SEMANTIC_HIT"} for row in systemic["records"])
    decision_ids = {
        row["ruler_id"]
        for row in systemic["records"]
        if row.get("high_gate_semantic_decision")
    }
    latent_ids = {row["ruler_id"] for row in records if row.get("latent_high_grade_hypothesis")}
    assert latent_ids <= decision_ids, "every latent high hypothesis needs a person-specific decision"
    c5_decisions = [
        decision
        for row in systemic["records"]
        for decision in row.get("c5_boundary_semantic_decisions", [])
    ]
    assert systemic["high_gate_decision_count"] == len(decision_ids)
    assert systemic["c5_boundary_decision_count"] == len(c5_decisions)
    strength_calibrations = systemic.get("authorization_strength_calibrations", [])
    assert systemic["authorization_strength_calibration_count"] == len(strength_calibrations)
    assert systemic["authorization_strength_calibrations"] == strength_calibrations
    by_id = {row["ruler_id"]: row for row in records}
    assert all(
        calibration["parent_id"] in {parent["parent_id"] for parent in by_id[calibration["ruler_id"]]["parents"]}
        and len(calibration["comparators"]) >= 2
        and all(comparator["ruler_id"] in by_id for comparator in calibration["comparators"])
        for calibration in strength_calibrations
    )
    c5_parent_ids = {
        parent["parent_id"]
        for row in _load(C5_SETTLEMENT)["records"]
        for parent in row.get("parents", [])
    }
    assert all(row["c5_parent_id"] in c5_parent_ids for row in c5_decisions)
    assert all(row["outcome"] in {"PROJECTED_TO_C3", "ALREADY_CAPTURED_IN_C3", "C3_BACKGROUND_INSUFFICIENT", "C5_ONLY", "ATTRIBUTION_INSUFFICIENT"} for row in c5_decisions)

    rows = _markdown_rows()
    assert len(rows) == 184
    for md, record in zip(rows, records):
        assert md[1] == record["ruler_name"]
        assert md[4:10] == [record["axis_grade"], record["position"], str(record["radar_value"]), record["axis_evidence_level"], record["output_mode"], record["score_status"]]
        assert md[10] == str(len(record["parents"]))
    return {"status": "PASS", "record_count": 184, "parent_count": len(parent_ids), "audit_unit_count": audit["unit_count"]}


def verify() -> dict[str, Any]:
    settlement, audit, high, systemic = _load(SETTLEMENT), _load(AUDIT), _load(HIGH_REVIEW), _load(SYSTEMIC_REVIEW)
    assert _read(MARKDOWN).decode("utf-8") == render_profile_markdown(settlement)
    result = verify_payloads(settlement, audit, high, systemic)
    project = yaml.safe_load(_read(PROJECT).decode("utf-8"))
    profile = project["profile_assessment"]
    assert profile["settled_axes"]["C3"]["json"].endswith(SETTLEMENT.name)
    manifest = _load(MANIFEST)
    c3 = next(axis for axis in manifest["axes"] if axis["axis_code"] == "C3")
    assert c3["json"] == SETTLEMENT.relative_to(MANIFEST.parent).as_posix()
    assert SYSTEMIC_REVIEW.name in c3["audit_jsons"]
    assert c3["record_count"] == 184
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
