from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.profile_m3_livelihood_settlement import (
    C4_ATTRIBUTION,
    C_PATHS,
    GRADE_PROJECTION,
    M3_ACCEPTANCE,
    M3_ADJUDICATIONS,
    M3_MARKDOWN,
    M3_REVIEW,
    M3_SETTLEMENT,
    MISSING,
    POOL,
    RESULT,
    ROOT,
    SUPPLEMENT,
)
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


PROJECT = ROOT / "config/project.yml"


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {path}"
    return json.loads(raw.decode("utf-8"))


def verify_payloads() -> dict[str, Any]:
    pool = {row["ruler_id"] for row in _load(POOL)["records"] if row["pool_status"] == "INCLUDED"}
    missing = _load(MISSING)
    supplement = _load(SUPPLEMENT)
    attribution = _load(C4_ATTRIBUTION)
    result = _load(RESULT)
    settlement = _load(M3_SETTLEMENT)
    adjudications = _load(M3_ADJUDICATIONS)
    review = _load(M3_REVIEW)
    finance = {
        axis: {row["ruler_id"]: row for row in _load(path)["scores"]}
        for axis, path in C_PATHS.items()
    }
    c4_payload = _load(C_PATHS["C4"])
    assert len(pool) == 184
    assert missing["record_count"] == len(missing["records"]) == 10
    assert supplement["record_count"] == len(supplement["records"]) == 184
    assert supplement["parent_chain_count"] == 204
    assert supplement["candidate_trace_count"] == 316
    assert {row["ruler_id"] for row in supplement["records"]} == pool
    assert all(row["review_status"] == "FULLY_ROUTED_TO_C1_C2_C3_C4" for row in supplement["records"])
    assert all(set(row["axis_resolutions"]) == set(C_PATHS) for row in supplement["records"])
    assert attribution["record_count"] == len(attribution["records"]) == 184
    assert {row["ruler_id"] for row in attribution["records"]} == pool
    assert all(row["review_status"] == "FULLY_ADJUDICATED" for row in attribution["records"])
    assert all(row["source_refs"] for row in attribution["records"])
    assert all(
        row["closed_residual_harm_observations"]
        for row in attribution["records"]
        if row["decision"]["final_grade"] != "DA0"
    )
    assert all(
        len({item["observation"] for item in row["closed_residual_harm_observations"]})
        == len(row["closed_residual_harm_observations"])
        for row in attribution["records"]
    )
    grade_counts = {
        grade: sum(row["decision"]["final_grade"] == grade for row in attribution["records"])
        for grade in ("DA0", "DA1", "DA2", "DA3", "DA4")
    }
    assert attribution["grade_counts"] == grade_counts == {"DA0": 36, "DA1": 32, "DA2": 72, "DA3": 41, "DA4": 3}
    assert attribution["decision_basis_version"] == "C4-DA-INDIVIDUAL-BASIS-V3"
    assert all(row.get("da_basis") for row in attribution["records"])
    assert all(
        row["decision"].get("basis_version") == "C4-DA-INDIVIDUAL-BASIS-V3"
        and row["decision"].get("behavior_chain_basis", "").strip()
        and row["decision"].get("grade_boundary_basis", "").strip()
        and row["decision"].get("source_refs")
        and row.get("da_basis", {}).get("source_refs")
        and row["ruler_name"] in row["decision"]["reason"]
        for row in attribution["records"]
    )
    assert len({row["decision"]["reason"] for row in attribution["records"]}) == 184
    records_hash = hashlib.sha256(
        json.dumps(attribution["records"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert attribution["records_sha256"] == records_hash
    assert all(len(rows) == 195 and pool <= set(rows) for rows in finance.values())
    assert c4_payload["schema_id"] == "i2_c4_signed_recovery_deterioration_formal_v4"
    assert c4_payload["public_basis_version"] == "C4-PUBLIC-BASIS-V3"
    assert c4_payload["recovery_formula_version"] == "C4-DIFFICULTY-WEIGHTED-BOUNDARIES-V1"
    public_fields = {
        "starting_context",
        "recovery_and_absorption",
        "behavior_and_attribution",
        "handoff_state",
        "public_adjudication",
    }
    assert all(public_fields <= set(row) for row in finance["C4"].values())
    assert all(
        all(str(row[field]).strip() for field in public_fields)
        for row in finance["C4"].values()
    )
    assert len({row["public_adjudication"] for row in finance["C4"].values()}) == 195
    assert all(0.0 <= float(row["recovery_score"]) <= 27.0 for row in finance["C4"].values())
    assert all(0.0 <= float(row["stability_score"]) <= 18.0 for row in finance["C4"].values())
    terminal_caps = {"C4T-1": 7.9, "C4T-2": 15.9, "C4T-3": 24.9, "C4T-4": 34.9, "C4T-5": 40.9, "C4T-6": 45.0}
    assert all(float(row["terminal_cap"]) == terminal_caps[row["terminal_band"]] for row in finance["C4"].values())
    assert all(
        row["recovery_formula_version"] == "C4-DIFFICULTY-WEIGHTED-BOUNDARIES-V1"
        and row["recovery_boundary_difficulty"]
        == {"1_TO_2": 0.6, "2_TO_3": 0.8, "3_TO_4": 1.0, "4_TO_5": 1.3, "5_TO_6": 1.6}
        and round(min(27.0, float(row["difficulty_weighted_recovery_credit"]) * 10.0), 1)
        == float(row["recovery_score"])
        for row in finance["C4"].values()
    )
    assert all(
        round(
            float(row["positive_score_retained"])
            - float(row["deterioration_penalty"])
            - float(row["destructive_amplification_penalty"]),
            1,
        )
        == float(row["raw_score"])
        for row in finance["C4"].values()
    )
    li_deming = next(row for row in finance["C4"].values() if row["ruler_id"] == "RULER-XIXIA-LIDEMING")
    assert (
        li_deming["weighted_net_recovery_delta"],
        li_deming["recovery_score"],
        li_deming["stability_score"],
        li_deming["terminal_band"],
        li_deming["score"],
        ) == (1.0, 10.0, 16.9, "C4T-4", 17.9)
    c4_by_name = {row["ruler_name"]: row for row in finance["C4"].values()}
    assert c4_by_name["完颜雍"]["recovery_score"] == 12.4
    assert c4_by_name["刘秀"]["recovery_score"] == 24.0
    assert c4_by_name["李世民"]["recovery_score"] == 26.8
    attribution_by_id = {row["ruler_id"]: row for row in attribution["records"]}
    for ruler_id in pool:
        c4_row = finance["C4"][ruler_id]
        decision = attribution_by_id[ruler_id]["decision"]
        assert c4_row["destructive_amplification_grade"] == decision["final_grade"]
        assert c4_row["destructive_amplification_penalty"] == decision["final_penalty"]
        assert c4_row["c4_attribution_readjudication"]["review_status"] == "FULLY_ADJUDICATED"
    assert result["record_count"] == len(result["scores"]) == 195
    result_by_id = {row["ruler_id"]: row for row in result["scores"]}
    assert set(result_by_id) == set(finance["C1"])
    for ruler_id, row in result_by_id.items():
        expected = round(sum(float(finance[axis][ruler_id]["score"]) for axis in C_PATHS), 1)
        assert row["score"] == expected
    assert adjudications["schema_version"] == "profile-m3-livelihood-adjudications-v3"
    assert adjudications["contract_version"] == "FORMAL-V3.0"
    assert adjudications["record_count"] == len(adjudications["records"]) == 184
    assert {row["ruler_id"] for row in adjudications["records"]} == pool
    assert adjudications["forbidden_inputs"] == [
        "C1_C2_C3_C4_SUM",
        "QUANTILE",
        "NORMALIZATION",
        "NAME_OVERRIDE",
        "POLICY_COUNT",
        "MATERIAL_COUNT",
    ]
    assert settlement["schema_version"] == "profile-m3-livelihood-finance-formal-settlement-v3"
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["contract_version"] == "FORMAL-V3.0"
    assert settlement["axis_name"] == "民生财政建设"
    assert settlement["formal_profile_write"] is True
    assert settlement["formal_rank_write"] is False
    assert settlement["profile_total_enabled"] is False
    assert settlement["profile_ranking_enabled"] is False
    assert settlement["composite_ranking_write"] is False
    assert settlement["database_write"] is False
    assert settlement["record_order_policy"] == "RADAR_VALUE_DESC_THEN_RULER_ID_ASC"
    assert settlement["record_count"] == len(settlement["records"]) == 184
    assert {row["ruler_id"] for row in settlement["records"]} == pool
    assert settlement["records"] == sorted(
        settlement["records"], key=lambda row: (-row["radar_value"], row["ruler_id"])
    )
    for row in settlement["records"]:
        decision = next(item for item in adjudications["records"] if item["ruler_id"] == row["ruler_id"])
        assert row["score_100"] == row["radar_value"] == GRADE_PROJECTION[(row["axis_grade"], row["position"])]
        assert row["axis_grade"] == decision["axis_grade"]
        assert row["position"] == decision["position"]
        assert set(row["components"]) == set(C_PATHS)
        assert row["value_mode"] == "SEMANTIC_HOLISTIC_ADJUDICATION_WITH_FIXED_GRADE_PROJECTION"
        assert row["formal_status"] == "FORMAL_CURRENT"
        assert row["output_mode"] in {"BOUNDED_PROFILE", "FULL_GRADE"}
        assert row["score_status"] == "FINAL"
        assert row["limitations"]
        assert row["parents"] == decision["parents"]
        ability = row["ability_evidence"]
        trajectory = ability["trajectory"]
        assert len(trajectory["start_vector"]) == len(trajectory["peak_vector"]) == len(trajectory["end_vector"]) == 3
        assert ability["route"] in {
            "RARE_BROAD_RECONSTRUCTION",
            "HIGH_LEVEL_CONSTRUCTION",
            "HIGH_LEVEL_STEWARDSHIP",
            "SUBSTANTIAL_CONSTRUCTION",
            "LIMITED_IMPROVEMENT",
            "ORDINARY_MAINTENANCE",
            "STAGNATION_OR_FAILURE",
        }
        if ability["governance_scale_class"] == "LIMITED_REGIONAL" and not ability["six_band_main_state"]:
            assert int(row["axis_grade"][1]) <= 4
            if row["axis_grade"] == "G4":
                assert row["position"] == "LOW"
        if row["axis_grade"] == "G0" and row["position"] == "LOW":
            net_decline_axes = sum(
                final < initial
                for initial, final in zip(
                    trajectory["start_vector"], trajectory["end_vector"], strict=True
                )
            )
            assert (
                float(ability["destructive_amplification_penalty"]) >= 18.0
                or net_decline_axes >= 2
            )
        assert row["axis_relevance_check"] == {
            "status": "HOLISTIC_C1_C4_SEMANTIC_ADJUDICATION",
            "component_codes": ["C1", "C2", "C3", "C4"],
            "component_sum_used": False,
            "quantile_or_normalization_used": False,
            "name_override_used": False,
            "old_process_material_role": "BEHAVIOR_CHAIN_AND_ATTRIBUTION_REVIEW_ONLY",
        }
        for field in (
            "starting_context",
            "construction_and_maintenance",
            "costs_and_consequences",
            "behavior_chain",
            "handoff_state",
            "grade_basis",
            "position_basis",
            "public_adjudication",
        ):
            assert row[field].strip()
        public_text = " ".join(
            row[field]
            for field in (
                "starting_context",
                "construction_and_maintenance",
                "costs_and_consequences",
                "behavior_chain",
                "handoff_state",
                "grade_basis",
                "position_basis",
            )
        )
        assert "C1+C2" not in public_text and "线性折算" not in public_text
        assert ".cache/" not in json.dumps(row, ensure_ascii=False)
        assert "web_ref:turn" not in json.dumps(row, ensure_ascii=False)
        for axis in C_PATHS:
            source_review = finance[axis][row["ruler_id"]]["m3_supplement_review"]
            assert len(source_review["applied_parent_chain_supplements"]) == len(
                source_review["applied_parent_ids"]
            )
            assert len(source_review["applied_orphan_candidate_supplements"]) == len(
                source_review["applied_orphan_candidate_ids"]
            )
    assert review["record_count"] == 184
    assert review["parent_chain_count"] == 204
    assert review["candidate_trace_count"] == 316
    assert review["c4_attribution_readjudication"]["record_count"] == 184
    assert review["c4_attribution_readjudication"]["grade_counts"] == grade_counts
    assert review["calibration"]["old_grade_distribution"] == {"G0": 36, "G1": 61, "G2": 56, "G3": 27, "G4": 4, "G5": 0}
    assert review["calibration"]["new_grade_distribution"] == {"G0": 6, "G1": 54, "G2": 49, "G3": 48, "G4": 23, "G5": 4}
    assert review["calibration"]["cross_grade_count"] == 125
    assert len(review["subitem_adjustments_in_this_recalibration"]) == 23
    assert M3_MARKDOWN.exists() and M3_ACCEPTANCE.exists()
    assert M3_MARKDOWN.read_text(encoding="utf-8") == render_profile_markdown(settlement)
    project = yaml.safe_load(PROJECT.read_text(encoding="utf-8"))
    assert project["profile_assessment"]["contract_version"] == "FORMAL-V2.0"
    entry = project["profile_assessment"]["settled_axes"]["M3"]
    assert entry["name"] == "民生财政建设"
    assert entry["contract_version"] == "FORMAL-V3.0"
    assert ROOT / entry["json"] == M3_SETTLEMENT
    assert ROOT / entry["markdown"] == M3_MARKDOWN
    assert ROOT / entry["adjudications_json"] == M3_ADJUDICATIONS
    assert ROOT / project["formal_settlements"]["second_item"]["c4_attribution_readjudications_json"] == C4_ATTRIBUTION
    manifest = _load(ROOT / "docs/评分结算/皇帝人物画像/00-已结算轴正式入口.json")
    manifest_entry = next(axis for axis in manifest["axes"] if axis["axis_code"] == "M3")
    assert manifest["contract_version"] == "FORMAL-V2.0"
    assert manifest_entry["json"] == M3_SETTLEMENT.relative_to(M3_SETTLEMENT.parents[1]).as_posix()
    assert manifest_entry["contract_version"] == "FORMAL-V3.0"
    assert manifest_entry["json_sha256"] == hashlib.sha256(M3_SETTLEMENT.read_bytes()).hexdigest()
    assert manifest_entry["markdown_sha256"] == hashlib.sha256(M3_MARKDOWN.read_bytes()).hexdigest()
    return {
        "profile_population": 184,
        "finance_population": 195,
        "old_m3_candidate_count": 316,
        "old_m3_parent_chain_count": 204,
        "new_finance_record_count": 10,
        "m3_grade_distribution": {"G0": 6, "G1": 54, "G2": 49, "G3": 48, "G4": 23, "G5": 4},
        "m3_cross_grade_count": 125,
    }


def verify() -> dict[str, Any]:
    return verify_payloads()


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True))
