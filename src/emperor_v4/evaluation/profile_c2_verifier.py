from __future__ import annotations

import json
import re
import collections
from pathlib import Path

import yaml

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_parent_schema import parent_chains
from emperor_v4.evaluation.profile_record_integrity import verify_current_records

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "人物画像"
SETTLEMENT = PROFILE_ROOT / "C2/19-C2信息处理学习与纠错正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "C2/20-C2主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "C2/21-C2高档学习周期与横向校准复核.json"
B2 = ROOT / "docs" / "评分结算" / "净收益" / "第二项治国净收益" / "制度行政" / "03-B2反馈纠错与权力约束方向卡.json"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
POOL = ROOT / "config" / "common" / "canonical-ruler-pool.json"
PROJECT = ROOT / "config" / "project.yml"


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise AssertionError(f"UTF-8 BOM is forbidden: {path}")
    raw.decode("utf-8")
    return raw


def _load(path: Path):
    _read(path)
    return load_json(path)


def _included_ids() -> set[str]:
    return {row["ruler_id"] for row in _load(POOL)["records"] if row["pool_status"] == "INCLUDED"}


def _markdown_rows() -> list[list[str]]:
    rows = []
    for line in _read(MARKDOWN).decode("utf-8").splitlines():
        if line.startswith("| ") and not line.startswith("|---") and "雷达值" not in line:
            rows.append([cell.strip().replace("\\|", "|") for cell in line[1:-1].split("|")])
    return rows


def _assert_no_keyword_adjudicator(value: object) -> None:
    forbidden = {
        "keyword_hits", "keyword_score", "keyword_direction", "keyword_coverage", "matched_keywords",
        "candidate_keywords", "selection_keywords",
    }
    if isinstance(value, dict):
        assert not (set(value) & forbidden), "keyword hits cannot define C2 coverage or adjudication"
        for child in value.values():
            _assert_no_keyword_adjudicator(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_keyword_adjudicator(child)


def verify_payloads(settlement: dict) -> dict:
    records = settlement["records"]
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["formal_profile_write"] is True
    assert settlement["formal_rank_write"] is False
    assert settlement["profile_total_enabled"] is False
    assert settlement["database_write"] is False
    assert settlement["record_count"] == len(records) == len(_included_ids())
    assert settlement["schema_version"] == "profile-c2-settlement-v6"
    assert settlement["method"] == "CHRONOLOGICAL_OPPORTUNITY_STATE_TRANSITION_MANUAL_ADJUDICATION"
    assert {row["ruler_id"] for row in records} == _included_ids()
    assert len({row["task_code"] for row in records}) == len(records)
    assert records == sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"]))
    _assert_no_keyword_adjudicator(settlement)
    required = {
        "task_code", "ruler_id", "ruler_name", "axis_grade", "position", "radar_value",
        "axis_evidence_level", "output_mode", "confidence", "score_status", "grade_basis",
        "position_basis", "axis_relevance_check", "limitations", "formal_status",
        "parent_chains", "representative_parent_ids",
        "coverage_review",
    }
    assert all(required <= row.keys() for row in records)
    assert all("parents" not in row and "representative_parent_contexts" not in row for row in records)
    assert all(
        len(row["representative_parent_ids"]) == len(set(row["representative_parent_ids"]))
        and set(row["representative_parent_ids"]) <= {parent["parent_id"] for parent in row["parent_chains"]}
        for row in records
    )
    assert all(row["axis_evidence_level"] in {"E1", "E2", "E3"} for row in records)
    assert all(row["axis_grade"] in {f"G{i}" for i in range(6)} for row in records)
    assert all(row["position"] in {"LOW", "MID", "HIGH"} for row in records)
    assert all(row["radar_value"] == row["score_100"] for row in records)
    assert all(row["formal_status"] == "FORMAL_CURRENT" for row in records)
    assert all(row["review_status"] for row in records)
    evidence_floor = [row for row in records if row["review_status"].startswith("EVIDENCE_FLOOR")]
    assert len(evidence_floor) == settlement["summary"]["evidence_floor_count"]
    assert all(row["score_status"] == "EVIDENCE_LIMITED" for row in evidence_floor)
    assert all("不是对全生涯能力" in row["position_basis"] and "断言" in row["position_basis"] for row in evidence_floor)
    same_chain_statuses = {row["same_chain_semantic_conflict_review_status"] for row in records}
    assert same_chain_statuses <= {"NO_TRIGGER", "CONSTRUCT_SEPARATED"}
    assert settlement["summary"]["unresolved_count"] == 0
    assert settlement["summary"]["score_70_or_above_count"] == sum(row["radar_value"] >= 70 for row in records)
    assert len({row["grade_basis"] for row in records}) == len(records)
    assert len({row["position_basis"] for row in records}) == len(records)
    assert all(row["ruler_name"] in row["grade_basis"] for row in records)
    assert all(row["ruler_name"] in row["position_basis"] for row in records)
    forbidden_templates = {
        "人工回读确认信息或反证已到达本人", "PASSED_MANUAL_REVIEW",
        "该直接材料记录其他制度行政机制", "该直接材料记录法律、司法与刑罚运行",
        "逐人复核父链所列反馈到达",
    }
    assert all(not any(text in row["grade_basis"] for text in forbidden_templates) for row in records)
    parent_ids = [parent["parent_id"] for row in records for parent in parent_chains(row)]
    assert len(parent_ids) == len(set(parent_ids))
    parent_by_id = {parent["parent_id"]: (row["ruler_id"], parent) for row in records for parent in parent_chains(row)}
    no_parent = [row for row in records if not parent_chains(row)]
    for row in records:
        coverage = row["coverage_review"]
        assert coverage["method"] == "CHRONOLOGICAL_OPPORTUNITY_STATE_TRANSITION"
        assert coverage["local_normative_entries_role"] in {
            "DISCOVERY_LOCATION_BACKGROUND_ONLY",
            "FULL_UNION_DISCOVERY_LOCATION_BACKGROUND_OR_SCORING_BY_SEMANTIC_REVIEW",
        }
        assert coverage["positive_window_status"] in {"CLOSED_PARENT_PRESENT", "NO_CLOSED_POSITIVE_PARENT"}
        assert coverage["negative_window_status"] in {"CLOSED_PARENT_PRESENT", "NO_CLOSED_NEGATIVE_PARENT"}
        assert coverage["phase_domain_coverage_status"] in {"BOUNDED_NOT_FULL_LIFETIME", "FULL_LIFETIME_PHASE_DOMAIN_CLOSED"}
        assert coverage["unresolved_phase_domain_windows"] or coverage["phase_domain_coverage_status"] == "FULL_LIFETIME_PHASE_DOMAIN_CLOSED"
        if coverage["phase_domain_coverage_status"] == "BOUNDED_NOT_FULL_LIFETIME":
            assert row["axis_evidence_level"] != "E3", f"targeted/local-only scope cannot publish E3: {row['ruler_name']}"
            assert row["score_status"] == "EVIDENCE_LIMITED"
            assert row["output_mode"] == "BOUNDED_PROFILE"
        parents = parent_chains(row)
        if not parents:
            assert row["axis_evidence_level"] == "E1"
            assert row["score_status"] == "EVIDENCE_LIMITED"
            assert row["axis_grade"] in {"G0", "G1", "G2"}
            assert row["limitations"] and len(row["position_basis"]) >= 40
        scoring = {parent["parent_id"] for parent in parents}
        assert set(row["axis_relevance_check"]["scoring_parent_refs"]) == scoring
        for parent in parents:
            assert parent["cycle_type"] in {"TRUTH_ACQUISITION", "ERROR_CORRECTION", "REFUSAL_OR_RECURRENCE"}
            assert parent["direction"] in {"POSITIVE", "MIXED_POSITIVE", "MIXED", "MIXED_NEGATIVE", "NEGATIVE"}
            assert parent["intensity"] in {
                "MI1", "MI2", "MI3", "MI4",
                "MI1_CASE", "MI2_LIFECYCLE", "MI3_SUSTAINED_SYSTEMIC", "MI4_CROSS_PHASE_SYSTEMIC",
            }
            if "material_intensity" in parent:
                assert parent["material_intensity"] == parent["intensity"]
            assert parent["cycle_anchor_refs"] and parent["basis"] and parent["lifecycle_review"]
            assert "C5" in parent["secondary_projection_reason"]
            assert any(token in parent["secondary_projection_reason"] for token in ("认知", "理解", "信息", "更新", "求真", "改策", "成本"))
            assert not any(text in parent["basis"] for text in forbidden_templates)
            assert not re.search(r"(?:裁|构成)(?:DW|PS)[0-9]", parent["basis"])
            assert "战败后改变策略，因此证明认知更新" not in parent["basis"]
            assert len(parent["basis"]) <= 500
        directions = {parent["direction"] for parent in parents}
        assert not (row["grade_numeric"] >= 3 and directions and directions <= {"NEGATIVE", "MIXED_NEGATIVE"}), f"grade contradicts all-negative parents: {row['ruler_name']}"
        assert not (row["grade_numeric"] == 0 and directions and directions <= {"POSITIVE", "MIXED_POSITIVE"}), f"grade contradicts all-positive parents: {row['ruler_name']}"
        if row["axis_grade"] in {"G4", "G5"}:
            assert len(parents) >= 2, f"high grade uses giant/single parent: {row['ruler_name']}"
            assert sum(p["direction"] in {"POSITIVE", "MIXED_POSITIVE"} for p in parents) >= 2
            assert any(p["cycle_type"] == "TRUTH_ACQUISITION" for p in parents)
            assert coverage["positive_window_status"] == "CLOSED_PARENT_PRESENT"
            if coverage["negative_window_status"] != "CLOSED_PARENT_PRESENT":
                assert (
                    row["position"] == "LOW"
                    or (
                        row["axis_grade"] == "G4"
                        and coverage.get("negative_window_review") == "REVIEWED_NO_CLOSED_NEGATIVE_PARENT"
                    )
                )
                assert coverage["negative_window_status"] == "NO_CLOSED_NEGATIVE_PARENT"
    verify_current_records(settlement)
    return {"status": "PASS", "record_count": len(records), "parent_count": sum(len(parent_chains(r)) for r in records)}


def verify() -> dict:
    settlement = _load(SETTLEMENT)
    assert _read(MARKDOWN).decode("utf-8") == render_profile_markdown(settlement), "reading view differs from current formal records"
    result = verify_payloads(settlement)
    profile = yaml.safe_load(_read(PROJECT).decode("utf-8"))["profile_assessment"]
    entry = profile["settled_axes"]["C2"]
    assert (ROOT / entry["json"]).resolve() == SETTLEMENT.resolve()
    assert (ROOT / entry["markdown"]).resolve() == MARKDOWN.resolve()
    manifest = _load(MANIFEST)
    registered = next(r for r in manifest["axes"] if r["axis_code"] == "C2")
    assert registered["json"] == SETTLEMENT.relative_to(MANIFEST.parent).as_posix()
    assert registered["markdown"] == MARKDOWN.relative_to(MANIFEST.parent).as_posix()
    assert registered["record_count"] == len(settlement["records"])
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
