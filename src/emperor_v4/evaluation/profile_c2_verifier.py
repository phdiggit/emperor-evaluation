from __future__ import annotations

import hashlib
import json
import re
import collections
from pathlib import Path

import yaml

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
SETTLEMENT = PROFILE_ROOT / "19-C2信息处理学习与纠错正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "20-C2主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "21-C2高档学习周期与横向校准复核.json"
B2 = ROOT / "docs" / "评分结算" / "第二项治国净收益" / "制度行政" / "03-B2反馈纠错与权力约束方向卡.json"
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


def verify_payloads(settlement: dict, audit: dict, high: dict) -> dict[str, object]:
    records = settlement["records"]
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["formal_profile_write"] is True
    assert settlement["formal_rank_write"] is False
    assert settlement["profile_total_enabled"] is False
    assert settlement["database_write"] is False
    assert settlement["record_count"] == len(records) == 184
    assert settlement["schema_version"] == "profile-c2-formal-settlement-v4"
    assert settlement["method"] == "CHRONOLOGICAL_OPPORTUNITY_STATE_TRANSITION_MANUAL_ADJUDICATION"
    assert {row["ruler_id"] for row in records} == _included_ids()
    assert len({row["task_code"] for row in records}) == 184
    assert records == sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"]))
    _assert_no_keyword_adjudicator(settlement)
    _assert_no_keyword_adjudicator(audit)
    _assert_no_keyword_adjudicator(high)

    required = {
        "task_code", "ruler_id", "ruler_name", "axis_grade", "position", "radar_value",
        "axis_evidence_level", "output_mode", "confidence", "score_status", "grade_basis",
        "position_basis", "axis_relevance_check", "limitations", "formal_status", "parents",
        "coverage_review",
    }
    assert all(required <= row.keys() for row in records)
    assert all(row["axis_evidence_level"] in {"E1", "E2", "E3"} for row in records)
    assert all(row["axis_grade"] in {f"G{i}" for i in range(6)} for row in records)
    assert all(row["position"] in {"LOW", "MID", "HIGH"} for row in records)
    assert all(row["radar_value"] == row["score_100"] for row in records)
    assert all(row["formal_status"] == "FORMAL_CURRENT" for row in records)
    same_chain_statuses = {row["same_chain_semantic_conflict_review_status"] for row in records}
    assert same_chain_statuses == {"NO_TRIGGER", "CONSTRUCT_SEPARATED"}
    assert settlement["summary"]["unresolved_count"] == 0
    assert settlement["summary"]["score_70_or_above_count"] == sum(row["radar_value"] >= 70 for row in records)

    assert len({row["grade_basis"] for row in records}) == 184
    assert len({row["position_basis"] for row in records}) == 184
    assert all(row["ruler_name"] in row["grade_basis"] for row in records)
    assert all(row["ruler_name"] in row["position_basis"] for row in records)
    forbidden_templates = {
        "人工回读确认信息或反证已到达本人", "PASSED_MANUAL_REVIEW",
        "该直接材料记录其他制度行政机制", "该直接材料记录法律、司法与刑罚运行",
        "逐人复核父链所列反馈到达",
    }
    assert all(not any(text in row["grade_basis"] for text in forbidden_templates) for row in records)

    parent_ids = [parent["parent_id"] for row in records for parent in row["parents"]]
    assert len(parent_ids) == len(set(parent_ids))
    parent_by_id = {parent["parent_id"]: (row["ruler_id"], parent) for row in records for parent in row["parents"]}
    no_parent = [row for row in records if not row["parents"]]
    assert no_parent
    for row in records:
        coverage = row["coverage_review"]
        assert coverage["method"] == "CHRONOLOGICAL_OPPORTUNITY_STATE_TRANSITION"
        assert coverage["actual_power_window"] == row["actual_power_window"]
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
        if not row["parents"]:
            assert row["axis_evidence_level"] == "E1"
            assert row["score_status"] == "EVIDENCE_LIMITED"
            assert row["axis_grade"] in {"G0", "G1", "G2"}
            assert row["limitations"] and len(row["position_basis"]) >= 40

        scoring = {parent["parent_id"] for parent in row["parents"]}
        assert set(row["axis_relevance_check"]["scoring_parent_refs"]) == scoring
        for parent in row["parents"]:
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
        directions = {parent["direction"] for parent in row["parents"]}
        assert not (row["grade_numeric"] >= 3 and directions and directions <= {"NEGATIVE", "MIXED_NEGATIVE"}), f"grade contradicts all-negative parents: {row['ruler_name']}"
        assert not (row["grade_numeric"] == 0 and directions and directions <= {"POSITIVE", "MIXED_POSITIVE"}), f"grade contradicts all-positive parents: {row['ruler_name']}"
        if row["axis_grade"] in {"G4", "G5"}:
            assert len(row["parents"]) >= 3, f"high grade uses giant/single parent: {row['ruler_name']}"
            assert sum(p["direction"] in {"POSITIVE", "MIXED_POSITIVE"} for p in row["parents"]) >= 2
            assert any(p["cycle_type"] == "TRUTH_ACQUISITION" for p in row["parents"])
            assert coverage["positive_window_status"] == "CLOSED_PARENT_PRESENT"
            assert coverage["negative_window_status"] == "CLOSED_PARENT_PRESENT"

    assert audit["canonical_status"] == "FORMAL_CURRENT"
    expected_suppression_policy = {
        "duration_and_scope_are_separate_from_severity": True,
        "death_or_irreversibility_does_not_automatically_grant_mi3": True,
        "mi3_or_mi4_suppression_not_offset_by_isolated_positive_cases": True,
        "c2_requires_feedback_arrival_and_update_or_refusal": True,
        "c5_retains_safety_punishment_proportion_and_power_procedure": True,
    }
    assert settlement["suppression_intensity_policy"] == expected_suppression_policy
    assert audit["schema_version"] == "profile-c2-unit-disposition-audit-v3"
    assert audit["suppression_intensity_policy"] == expected_suppression_policy
    assert audit["record_count"] == 184
    assert audit["unit_count"] == len(audit["units"])
    assert audit["unresolved_count"] == 0
    for status in ("SCORING_PARENT", "BACKGROUND_VALIDATION", "AXIS_OUT_WITH_REASON", "UNRESOLVED_EVIDENCE_GAP"):
        assert status in audit["status_counts"]
    assert audit["status_counts"]["UNRESOLVED_EVIDENCE_GAP"] == 0
    assert len({unit["unit_id"] for unit in audit["units"]}) == len(audit["units"])
    assert all(unit["source_exists_or_external"] for unit in audit["units"])
    assert len({unit["status"] for unit in audit["units"]}) >= 3, "all entries cannot receive one uniform disposition"
    assert len({unit["reason"] for unit in audit["units"]}) >= int(audit["unit_count"] * 0.95)
    assert {u["scoring_parent_id"] for u in audit["units"] if u["status"] == "SCORING_PARENT"} <= set(parent_ids)
    assert set(parent_ids) <= {pid for unit in audit["units"] for pid in unit.get("supports_parent_ids", [])}
    for unit in audit["units"]:
        supports = unit.get("supports_parent_ids", [])
        assert all(parent_id in parent_by_id for parent_id in supports)
        assert all(parent_by_id[parent_id][0] == unit["ruler_id"] for parent_id in supports)
        if unit["status"] == "SCORING_PARENT":
            assert unit["scoring_parent_id"] in supports
            assert parent_by_id[unit["scoring_parent_id"]][0] == unit["ruler_id"]
        else:
            assert unit["scoring_parent_id"] is None
        if unit["status"] == "AXIS_OUT_WITH_REASON":
            assert not supports

    ledger = audit["coverage_ledger"]
    assert len(ledger) == 184
    assert {entry["ruler_id"] for entry in ledger} == {row["ruler_id"] for row in records}
    record_by_id = {row["ruler_id"]: row for row in records}
    for entry in ledger:
        record = record_by_id[entry["ruler_id"]]
        assert entry["actual_power_window"] == record["actual_power_window"]
        assert set(entry["observed_parent_ids"]) == {p["parent_id"] for p in record["parents"]}
        assert entry["phase_domain_coverage_status"] == record["coverage_review"]["phase_domain_coverage_status"]
        assert entry["publication_mode"] == record["coverage_review"]["publication_mode"]

    expected_high = {row["ruler_id"] for row in records if row["axis_grade"] in {"G4", "G5"}}
    assert high["schema_version"] == "profile-c2-high-grade-calibration-v4"
    assert high["suppression_intensity_policy"] == expected_suppression_policy
    assert high["profile_count"] == len(high["profiles"])
    assert {row["ruler_id"] for row in high["profiles"]} == expected_high
    for profile in high["profiles"]:
        assert len(profile["independent_cycles"]) >= 3
        assert profile["positive_observation_window_review"] == "CLOSED_WITH_NAMED_CYCLES"
        assert profile["negative_observation_window_review"] == "CLOSED_WITH_NAMED_COUNTEREVIDENCE"
        assert profile["source_density_asymmetry_review"] == "MATERIAL_DENSITY_LIMITED_E2_MEDIUM_CONFIDENCE"
        assert profile["multiple_independent_learning_cycles_review"] and profile["later_retest_review"]

    assert high["material_budget_policy"] == "MAX_4_SUPPLEMENTAL_PRIMARY_SOURCE_UNITS_PER_CANDIDATE"
    assert high["source_union_policy"] == "ALL_LOCAL_NORMATIVE_ENTRIES_UNION_MAX_4_SUPPLEMENTAL_PRIMARY_UNITS_EXCLUDING_PERSON_SPECIFIC_COMPILATIONS"
    candidate_reviews = high["candidate_reviews"]
    assert high["intuitive_candidate_count"] == len(candidate_reviews) >= 8
    assert settlement["summary"]["material_cap_candidate_count"] == len(candidate_reviews)
    assert len({entry["ruler_id"] for entry in candidate_reviews}) == len(candidate_reviews)
    for entry in candidate_reviews:
        record = record_by_id[entry["ruler_id"]]
        assert entry["material_budget_policy"] == high["material_budget_policy"]
        assert entry["unit_count"] == len(entry["supplemental_primary_units"])
        assert entry["material_units_consumed"] == entry["supplemental_primary_units"]
        assert 1 <= entry["unit_count"] <= 4, f"candidate source budget exceeded: {entry['ruler_name']}"
        assert entry["supplemental_primary_units"] == record["coverage_review"]["supplemental_primary_units"]
        assert entry["normative_entry_refs"] == record["coverage_review"]["normative_entry_refs"]
        assert entry["normative_entry_refs"], f"candidate lost all normative entries: {entry['ruler_name']}"
        assert entry["combined_source_refs"] == list(dict.fromkeys(entry["normative_entry_refs"] + entry["supplemental_primary_units"]))
        assert entry["combined_source_refs"] == record["coverage_review"]["combined_source_refs"]
        assert record["coverage_review"]["direct_chronological_or_primary_refs"] == entry["combined_source_refs"]
        assert record["coverage_review"]["material_budget_policy"] == high["material_budget_policy"]
        assert entry["post_review_grade"] == record["axis_grade"]
        assert entry["post_review_position"] == record["position"]
        expected_strength = {
            direction: dict(sorted(collections.Counter(
                parent["intensity"] for parent in record["parents"] if parent["direction"] in directions
            ).items()))
            for direction, directions in {
                "POSITIVE_OR_MIXED_POSITIVE": {"POSITIVE", "MIXED_POSITIVE"},
                "NEGATIVE_OR_MIXED_NEGATIVE": {"NEGATIVE", "MIXED_NEGATIVE", "MIXED"},
            }.items()
        }
        assert entry["directional_material_strength"] == expected_strength
        balance = record["directional_strength_balance_review"]
        assert entry["feedback_suppression_strength_review"] == balance
        assert balance["review_status"] == "MANUAL_ABSOLUTE_PERFORMANCE_REVIEWED"
        assert set(balance["suppression_parent_ids"]) <= {p["parent_id"] for p in record["parents"]}
        assert set(balance["isolated_positive_parent_ids"]) <= {p["parent_id"] for p in record["parents"]}
        assert "MI3/MI4" in balance["asymmetry_decision"]
        assert "父链数量" in balance["grade_effect"]

        dispositions = entry["b2_material_disposition_review"]
        expected_b2_ids = []
        b2_record = next(row for row in _load(B2)["records"] if row["ruler_id"] == entry["ruler_id"])
        for profile_key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
            for item in b2_record.get(profile_key, []):
                expected_b2_ids.extend(item.get("material_ids") or [item.get("material_id")])
        expected_b2_ids = [material_id for material_id in expected_b2_ids if material_id]
        assert [item["material_id"] for item in dispositions] == expected_b2_ids
        assert len(dispositions) == len(set(expected_b2_ids))
        audit_units = {
            unit["source_ref"]: unit
            for unit in audit["units"]
            if unit["ruler_id"] == entry["ruler_id"] and unit["entry"] == "B2"
        }
        for disposition in dispositions:
            material_id = disposition["material_id"]
            assert material_id in audit_units
            unit = audit_units[material_id]
            assert disposition["status"] == unit["status"]
            assert disposition["scoring_parent_id"] == unit["scoring_parent_id"]
            assert disposition["supports_parent_ids"] == unit["supports_parent_ids"]
            assert disposition["reason"] == unit["reason"]
            assert "另由具体父链" not in disposition["reason"]
            assert len(disposition["reason"]) >= 20
            if disposition["status"] == "SCORING_PARENT":
                _, scoring_parent = parent_by_id[disposition["scoring_parent_id"]]
                assert material_id in scoring_parent["source_parent_refs"]
            elif disposition["status"] == "BACKGROUND_VALIDATION":
                assert disposition["supports_parent_ids"], f"candidate background must name its parent: {material_id}"

        for parent in record["parents"]:
            suppression = parent["feedback_suppression_review"]
            assert suppression["review_status"] in {"REVIEWED", "NOT_APPLICABLE_NO_FEEDBACK_SUPPRESSION"}
            if suppression["review_status"] == "REVIEWED":
                assert suppression["sanction_or_exclusion_intensity"] in {"NONE", "LOW", "MODERATE", "HIGH", "EXTREME"}
                assert suppression["recurrence_scope"] in {"SINGLE_CASE", "REPEATED_SAME_MECHANISM", "SUSTAINED_MULTI_OBJECT", "CROSS_PHASE_SYSTEMIC"}
                assert suppression["future_channel_effect"] in {"NO_CHANNEL_DAMAGE", "TEMPORARY_CHILLING", "SUSTAINED_CHILLING", "CHANNEL_DESTRUCTION"}
                assert suppression["feedback_arrival"] and suppression["c2_slice"] and suppression["c5_exclusion"]
                assert parent["parent_id"] in balance["suppression_parent_ids"]
                if parent["intensity"] in {"MI3_SUSTAINED_SYSTEMIC", "MI4_CROSS_PHASE_SYSTEMIC"}:
                    assert suppression["recurrence_scope"] in {"SUSTAINED_MULTI_OBJECT", "CROSS_PHASE_SYSTEMIC"}
                if suppression["recurrence_scope"] == "SINGLE_CASE":
                    assert parent["intensity"] not in {"MI3_SUSTAINED_SYSTEMIC", "MI4_CROSS_PHASE_SYSTEMIC"}

    candidate_intensities = {
        parent["intensity"]
        for entry in candidate_reviews
        for parent in record_by_id[entry["ruler_id"]]["parents"]
    }
    assert {"MI1_CASE", "MI2_LIFECYCLE", "MI3_SUSTAINED_SYSTEMIC"} <= candidate_intensities
    assert high["candidate_b2_material_count"] == sum(
        len(entry["b2_material_disposition_review"]) for entry in candidate_reviews
    ) == settlement["summary"]["candidate_b2_material_count"] == 58
    assert settlement["summary"]["candidate_b2_scoring_parent_count"] == sum(
        disposition["status"] == "SCORING_PARENT"
        for entry in candidate_reviews
        for disposition in entry["b2_material_disposition_review"]
    )

    candidate_source_refs = [
        ref
        for entry in candidate_reviews
        for ref in entry["combined_source_refs"]
    ] + [
        ref
        for entry in candidate_reviews
        for parent in record_by_id[entry["ruler_id"]]["parents"]
        for ref in parent["cycle_anchor_refs"]
    ]
    serialized_sources = json.dumps(candidate_source_refs, ensure_ascii=False)
    assert not any(marker in serialized_sources for marker in ("贞观政要", "貞觀政要", "蒙古秘史", "聖武親征錄", "圣武亲征录"))

    return {
        "status": "PASS", "record_count": len(records),
        "evidence_limited_count": settlement["summary"]["evidence_limited_count"],
        "evidence_level_distribution": settlement["summary"]["evidence_level_distribution"],
        "grade_distribution": settlement["summary"]["grade_distribution"],
        "unit_count": audit["unit_count"], "high_grade_count": len(high["profiles"]),
        "parent_count": len(parent_ids), "no_parent_evidence_limited_count": len(no_parent),
        "intuitive_candidate_count": len(candidate_reviews),
        "score_70_or_above_count": settlement["summary"]["score_70_or_above_count"],
    }


def verify() -> dict[str, object]:
    settlement, audit, high = _load(SETTLEMENT), _load(AUDIT), _load(HIGH_REVIEW)
    assert _read(MARKDOWN).decode("utf-8") == render_profile_markdown(settlement)
    result = verify_payloads(settlement, audit, high)
    assert settlement["canonical_pool_sha256"] == _sha(POOL)
    assert settlement["contract_sha256"] == _sha(CONTRACT)
    md_rows = _markdown_rows()
    assert len(md_rows) == 184
    assert [(int(c[0]), c[1], c[2], c[3], c[4], c[5], c[6]) for c in md_rows] == [
        (r["radar_value"], r["axis_grade"], r["position"], r["ruler_name"], r["polity"], r["axis_evidence_level"], r["confidence"])
        for r in settlement["records"]
    ]
    manifest = _load(MANIFEST)
    assert manifest["contract_sha256"] == _sha(CONTRACT)
    assert manifest["settled_axis_count"] == 6
    assert manifest["unsettled_axis_count"] == 2
    axis = next(row for row in manifest["axes"] if row["axis_code"] == "C2")
    assert axis["json"] == SETTLEMENT.name and axis["markdown"] == MARKDOWN.name
    assert axis["json_sha256"] == _sha(SETTLEMENT)
    project = yaml.safe_load(_read(PROJECT).decode("utf-8"))
    assert project["profile_assessment"]["settled_axes"]["C2"]["json"].endswith(SETTLEMENT.name)
    hashes = {path.name: _sha(path) for path in (SETTLEMENT, MARKDOWN, AUDIT, HIGH_REVIEW)}
    result["hashes"] = hashes
    result["combined_sha256"] = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode("utf-8")).hexdigest()
    return result


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
