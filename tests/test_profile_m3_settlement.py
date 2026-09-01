from __future__ import annotations

import copy
import json
import re

import pytest

from emperor_v4.evaluation.profile_m3_settlement import (
    GRADE_PROJECTION,
    M3_CONTRACT,
    M3_MARKDOWN,
    M3_SETTLEMENT,
    ROOT,
)
from emperor_v4.evaluation.profile_m3_settlement import build
from emperor_v4.evaluation.profile_m3_verifier import verify, verify_payload
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_profile_m3_formal_snapshot_passes_lightweight_verifier() -> None:
    result = verify()
    assert result["status"] == "PASS"
    assert result["record_count"] == 184
    assert sum(result["grade_distribution"].values()) == 184
    assert result["grade_distribution"] == {"G0": 13, "G1": 48, "G2": 45, "G3": 62, "G4": 12, "G5": 4}
    assert result["scale_gate_distribution"] == {
        "FULL_OR_MAJOR_REGIONAL": 19,
        "UNRESOLVED_NOT_HIGH_GRADE_GATE": 159,
        "LIMITED_REGIONAL": 6,
    }


def test_profile_m3_scores_are_mechanical_projection_of_stored_decisions() -> None:
    settlement = _load(M3_SETTLEMENT)
    for row in settlement["records"]:
        expected = GRADE_PROJECTION[(row["axis_grade"], row["position"])]
        assert row["score_100"] == row["radar_value"] == expected


def test_profile_m3_confirmed_checklist_changes_are_applied() -> None:
    settlement = _load(M3_SETTLEMENT)
    by_name = {row["ruler_name"]: row for row in settlement["records"]}
    expected = {
        "李忱": ("G3", "HIGH"), "赵曙": ("G3", "HIGH"), "朱瞻基": ("G3", "HIGH"),
        "赵光义": ("G3", "MID"), "司马睿": ("G2", "HIGH"), "武则天": ("G3", "MID"),
        "高欢": ("G3", "MID"), "慈禧": ("G1", "LOW"), "高湛": ("G2", "LOW"),
        "李德旺": ("G1", "MID"), "耶律延禧": ("G1", "LOW"), "胡亥": ("G0", "LOW"),
        "高洋": ("G0", "LOW"), "李隆基": ("G0", "LOW"), "苻坚": ("G0", "LOW"),
        "刘宏": ("G0", "LOW"), "赫连勃勃": ("G0", "LOW"), "刘彻": ("G0", "LOW"),
        "完颜亮": ("G0", "LOW"), "嬴政": ("G0", "LOW"),
    }
    assert {name: (by_name[name]["axis_grade"], by_name[name]["position"]) for name in expected} == expected


def test_profile_m3_checklist_contract_and_yinzhen_boundary_are_explicit() -> None:
    contract = M3_CONTRACT.read_text(encoding="utf-8")
    assert "FORMAL-V3.4" in contract
    assert "M3不重新定义DA0—DA4" in contract
    assert "同档结构建设的待建边界" in contract
    assert "实现表现下限的待建硬门" in contract
    assert "尚未启用为正式自动保底条件" in contract

    settlement = _load(M3_SETTLEMENT)
    yinzhen = next(row for row in settlement["records"] if row["ruler_name"] == "胤禛")
    review = yinzhen["ability_evidence"]["same_band_structural_build_review"]
    assert yinzhen["components"]["C2"]["band"] == "C2-4"
    assert (yinzhen["axis_grade"], yinzhen["position"]) == ("G3", "MID")
    assert review["status"] == "PENDING_RULE_NOT_SCORE_ACTIVE"
    assert review["c2_disposition"] == "C2-4_RETAINED"
    assert review["m3_disposition"] == "G3-MID_RETAINED_PENDING_RULE"


def test_profile_m3_highest_achieved_vector_covers_main_and_handoff() -> None:
    settlement = _load(M3_SETTLEMENT)
    for row in settlement["records"]:
        trajectory = row["ability_evidence"]["trajectory"]
        assert all(
            highest >= max(main, end)
            for highest, main, end in zip(
                trajectory["peak_vector"], trajectory["main_vector"], trajectory["end_vector"]
            )
        )


def test_profile_m3_rejects_local_hard_constraint_breakage() -> None:
    settlement = _load(M3_SETTLEMENT)
    broken = copy.deepcopy(settlement)
    broken["records"][0]["score_100"] = -1
    with pytest.raises(ValueError, match="score projection mismatch"):
        verify_payload(broken)


def test_profile_m3_rejects_upstream_curve_k_and_da_drift() -> None:
    settlement = _load(M3_SETTLEMENT)

    broken_curve = copy.deepcopy(settlement)
    broken_curve["records"][0]["ability_evidence"]["trajectory"]["start_vector"][0] += 1
    with pytest.raises(ValueError, match="upstream trajectory drift"):
        verify_payload(broken_curve)

    broken_k = copy.deepcopy(settlement)
    broken_k["records"][0]["ability_evidence"]["weighted_K"] = -1
    with pytest.raises(ValueError, match="weighted K drift"):
        verify_payload(broken_k)

    broken_da = copy.deepcopy(settlement)
    broken_da["records"][0]["ability_evidence"]["destructive_amplification_grade"] = "DA9"
    with pytest.raises(ValueError, match="DA grade drift"):
        verify_payload(broken_da)


def test_profile_m3_compiler_reads_formal_snapshot_without_readjudication() -> None:
    before = M3_SETTLEMENT.read_bytes()
    settlement = build(write=False)["settlement"]
    assert M3_SETTLEMENT.read_bytes() == before
    assert M3_MARKDOWN.read_text(encoding="utf-8") == render_profile_markdown(settlement)


def test_profile_m3_high_grades_have_resolved_scale_gate() -> None:
    settlement = _load(M3_SETTLEMENT)
    for row in settlement["records"]:
        gate = row["ability_evidence"]["governance_scale_gate"]
        if row["axis_grade"] in {"G4", "G5"}:
            assert gate["status"] in {"FULL_OR_MAJOR_REGIONAL", "LIMITED_REGIONAL"}
            assert gate["formal_subitem_sources"]


def test_profile_m3_scale_gate_separates_actual_scale_from_material_scope() -> None:
    settlement = _load(M3_SETTLEMENT)
    by_name = {row["ruler_name"]: row for row in settlement["records"]}
    limited = {
        row["ruler_name"]
        for row in settlement["records"]
        if row["ability_evidence"]["governance_scale_gate"]["status"] == "LIMITED_REGIONAL"
    }
    assert limited == {"李雄", "沮渠蒙逊", "高季兴", "刘崇", "朱由榔", "赫连勃勃"}
    for name in {"李暠", "钱镠", "耶律阿保机", "李嗣源", "李适", "孙休"}:
        gate = by_name[name]["ability_evidence"]["governance_scale_gate"]
        assert gate["classification"] == "MATERIAL_SCOPE_LIMIT_ONLY"
        assert gate["status"] == "UNRESOLVED_NOT_HIGH_GRADE_GATE"
    for name in {"刘义隆", "司马曜", "杨行密", "苻健"}:
        gate = by_name[name]["ability_evidence"]["governance_scale_gate"]
        assert gate["classification"] == "FULL_OR_MAJOR_ACTUAL_SCALE"
        assert gate["status"] == "FULL_OR_MAJOR_REGIONAL"


def test_second_item_c4_exposes_unified_m3_scale_adjudication_for_all_records() -> None:
    path = ROOT / "docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json"
    payload = _load(path)
    contract = payload["m3_governance_scale_adjudication_contract"]
    assert contract["schema_version"] == "m3-governance-scale-adjudication-v1"
    assert contract["record_count"] == len(payload["scores"]) == 195
    assert contract["classification_distribution"] == {
        "FULL_OR_MAJOR_ACTUAL_SCALE": 19,
        "LIMITED_ACTUAL_SCALE": 9,
        "MATERIAL_SCOPE_LIMIT_ONLY": 6,
        "UNRESOLVED": 161,
    }
    limited = {
        row["ruler_name"]
        for row in payload["scores"]
        if row["m3_governance_scale_adjudication"]["classification"] == "LIMITED_ACTUAL_SCALE"
    }
    assert limited == {"李雄", "沮渠蒙逊", "高季兴", "刘崇", "朱由崧", "朱聿键", "朱由榔", "萧绎", "赫连勃勃"}
    for row in payload["scores"]:
        adjudication = row["m3_governance_scale_adjudication"]
        assert adjudication["name_or_polity_inference_used"] is False
        if adjudication["classification"] != "UNRESOLVED":
            assert adjudication["supporting_formal_fields"]


def test_profile_m3_reader_rationales_are_concise_and_sources_are_quotations() -> None:
    settlement = _load(M3_SETTLEMENT)
    for row in settlement["records"]:
        costs = row["costs_and_consequences"]
        behavior = row["behavior_chain"]
        assert costs not in behavior
        assert behavior not in costs
        assert len(costs) <= 240
        assert len(behavior) <= 360
        cost_parts = [part for part in re.split(r"(?<=[。！？；])", costs) if len(part.strip()) >= 20]
        behavior_parts = [part for part in re.split(r"(?<=[。！？；])", behavior) if len(part.strip()) >= 20]
        assert not any(
            cost_part.strip() in behavior_part.strip() or behavior_part.strip() in cost_part.strip()
            for cost_part in cost_parts
            for behavior_part in behavior_parts
        )
        assert row["source_evidence"]
        for source in row["source_evidence"]:
            assert re.match(r"^《[^》]+》", source["source_title"])
            assert source["quote"].strip()
            assert source["source_origin"] in {
                "C4_FORMAL_PUBLIC_SOURCE",
                "C4_FORMAL_LINEAGE_EXPANDED_QUOTATION",
                "M3_SUPPLEMENT",
            }
            assert not re.search(
                r"https?://|docs/|source_ref|material_id|\\",
                source["source_title"] + source["quote"],
                re.I,
            )

    markdown = render_profile_markdown(settlement)
    adjudications = markdown.split("## 逐人裁决依据", 1)[1]
    assert not re.search(
        r"JSON|机器|审计|SOURCE_GAP|source_ref|material_id|正式归责链|"
        r"https?://|docs/|\bformal\b|\braw\b|terminal_quality|"
        r"M\d+(?:-[A-Z0-9]+)+|同步|过时|旧C4|机械|合同|去重|消费|补审",
        adjudications,
        re.I,
    )
    source_lines = [line for line in adjudications.splitlines() if line.startswith("  - 《")]
    assert len(source_lines) == sum(len(row["source_evidence"]) for row in settlement["records"])
    assert all(re.match(r"^  - 《[^》]+》.*：\S", line) for line in source_lines)


def test_profile_m3_reader_includes_c4_sources() -> None:
    settlement = _load(M3_SETTLEMENT)
    c4 = _load(ROOT / "docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json")
    c4_by_id = {row["ruler_id"]: row for row in c4["scores"]}
    direct_count = 0
    legacy_count = 0
    for row in settlement["records"]:
        origins = [source["source_origin"] for source in row["source_evidence"]]
        refs = c4_by_id[row["ruler_id"]]["public_source_refs"]
        direct_refs = [ref for ref in refs if "：" in ref and "《" in ref and "》" in ref]
        if direct_refs:
            direct_count += 1
            assert origins.count("C4_FORMAL_PUBLIC_SOURCE") == len(direct_refs)
        else:
            legacy_count += 1
            assert "C4_FORMAL_LINEAGE_EXPANDED_QUOTATION" in origins
    assert (direct_count, legacy_count) == (89, 95)
