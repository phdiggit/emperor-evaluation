from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_parent_schema import parent_chains
from emperor_v4.evaluation.profile_record_integrity import verify_current_records

from emperor_v4.evaluation.profile_markdown import render_profile_markdown

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "人物画像"
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


def verify_resolved_gate_decision(row: dict) -> None:
    """A current explicit gate decision cannot publish a different grade/position."""
    decision = row.get("resolved_high_gate_decision")
    if decision is None:
        return
    label = row["ruler_id"]
    assert decision["ruler_id"] == label, f"detached C3 gate decision: {label}"
    assert decision["ruler_name"] == row["ruler_name"], f"C3 gate identity mismatch: {label}"
    assert decision["reason"].strip(), f"empty C3 gate reason: {label}"
    match = re.search(r"(?:^|_)(G[0-5])_(LOW|MID|HIGH)(?:_|$)", decision["outcome"])
    if match:
        assert match.groups() == (row["axis_grade"], row["position"]), f"stale C3 gate decision: {label}"


def verify_payloads(settlement: dict) -> dict:
    records = settlement["records"]
    pool = _load(POOL)
    included = {r["ruler_id"] for r in pool["records"] if r["pool_status"] == "INCLUDED"}
    assert settlement["schema_version"] == "profile-c3-formal-settlement-v2"
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["axis_code"] == "C3"
    assert settlement["contract_version"]
    assert settlement["authority_mode"] == "FORMAL_SETTLEMENT_PATCH_SOURCE"
    assert settlement["record_count"] == len(records) == len(included)
    assert {r["ruler_id"] for r in records} == included
    assert len({r["task_code"] for r in records}) == len(records)
    assert all(r["task_code"] == f"PROFILE-C3-{r['ruler_id']}" for r in records)
    assert records == sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"]))
    assert settlement["formal_rank_write"] is False and settlement["profile_total_enabled"] is False
    assert settlement["profile_ranking_enabled"] is False and settlement["database_write"] is False
    _assert_no_mechanical_adjudicator(settlement)
    required = {
        "task_code", "ruler_id", "axis_grade", "position", "radar_value", "axis_evidence_level",
        "output_mode", "confidence", "score_status", "parent_chains", "representative_parent_ids", "typical_pattern", "grade_basis",
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
        verify_resolved_gate_decision(row)
        parents = parent_chains(row)
        check = row["axis_relevance_check"]
        assert check == {
            "famous_minister_count_used": False, "office_count_used": False,
            "final_outcome_backsolve_used": False, "c5_ethics_leakage": False,
            "m4_group_outcome_leakage": False,
        }
        if not parents:
            assert row["score_status"] == "EVIDENCE_LIMITED"
            assert row["axis_evidence_level"] == "E1" and row["output_mode"] == "EPISODE_TAG"
            assert row["limitations"] and len(row["typical_pattern"]) >= 20
        if row["score_status"] == "EVIDENCE_LIMITED":
            assert row["axis_evidence_level"] != "E3"
            assert row["axis_grade"] not in {"G4", "G5"}
        pattern_clauses = _clauses(row["typical_pattern"])
        assert len(pattern_clauses) == len(set(pattern_clauses)), f"duplicate typical-pattern clause: {row['ruler_name']}"
        for parent in parents:
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
        directions = {p["direction"] for p in parents}
        if row["axis_grade"] in {"G4", "G5"}:
            assert len(parents) >= 2, "single giant chain cannot support G4/G5"
            assert len(row["major_task_domains_observed"]) >= 2, "high grade requires cross-task retest"
            assert directions != {"NEGATIVE"}
            assert not re.match(r"^按\d+条", row["grade_basis"]), "high grade requires person-specific gate basis"
            assert row["axis_grade"] in row["grade_basis"], "high-grade basis must name the published gate"
        if row["axis_grade"] == "G0":
            assert "POSITIVE" not in directions or directions & {"NEGATIVE", "MIXED", "MIXED_NEGATIVE"}
    assert len(parent_ids) == len(set(parent_ids)), "C3 parent IDs must be globally unique"
    verify_current_records(settlement)
    return {"status": "PASS", "record_count": len(records), "parent_count": sum(len(parent_chains(r)) for r in records)}


def verify() -> dict:
    settlement = _load(SETTLEMENT)
    assert _read(MARKDOWN).decode("utf-8") == render_profile_markdown(settlement), "reading view differs from current formal records"
    result = verify_payloads(settlement)
    profile = yaml.safe_load(_read(PROJECT).decode("utf-8"))["profile_assessment"]
    entry = profile["settled_axes"]["C3"]
    assert (ROOT / entry["json"]).resolve() == SETTLEMENT.resolve()
    assert (ROOT / entry["markdown"]).resolve() == MARKDOWN.resolve()
    manifest = _load(MANIFEST)
    registered = next(r for r in manifest["axes"] if r["axis_code"] == "C3")
    assert registered["json"] == SETTLEMENT.relative_to(MANIFEST.parent).as_posix()
    assert registered["markdown"] == MARKDOWN.relative_to(MANIFEST.parent).as_posix()
    assert registered["record_count"] == len(settlement["records"])
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
