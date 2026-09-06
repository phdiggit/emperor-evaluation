from __future__ import annotations

import copy
import re

import pytest

from emperor_v4.evaluation.formal_json_store import load_json

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
    return load_json(path)


def test_profile_m3_formal_snapshot_passes_lightweight_verifier() -> None:
    result = verify()
    assert result["status"] == "PASS"
    assert sum(result["grade_distribution"].values()) == result["record_count"]


def test_profile_m3_scores_are_mechanical_projection_of_stored_decisions() -> None:
    settlement = _load(M3_SETTLEMENT)
    for row in settlement["records"]:
        expected = GRADE_PROJECTION[(row["axis_grade"], row["position"])]
        assert row["score_100"] == row["radar_value"] == expected


def test_profile_m3_full_pool_regrade_is_complete_and_reader_order_is_descending() -> None:
    settlement = _load(M3_SETTLEMENT)
    detail = M3_MARKDOWN.read_text(encoding="utf-8").split("## 逐人裁决依据", 1)[1]
    detail_names = re.findall(r"^### \d+\. (.+)$", detail, re.M)
    assert detail_names == [row["ruler_name"] for row in settlement["records"]]
    assert [row["radar_value"] for row in settlement["records"]] == sorted(
        (row["radar_value"] for row in settlement["records"]), reverse=True
    )


def test_profile_m3_checklist_contract_and_yinzhen_boundary_are_explicit() -> None:
    contract = M3_CONTRACT.read_text(encoding="utf-8")
    assert "FORMAL-V3.6" in contract
    assert "M3不重新定义DA0—DA6" in contract
    assert "M3直接读取三轴正式记录中的`stability_class_diagnostic_only`" in contract
    assert "同档结构建设的待建边界" in contract
    assert "实现表现下限硬门" in contract
    assert "强建设事实保留例外" in contract
    assert "高压守成不得消费本人自造压力" in contract
    assert "长期高位兑现保护门" in contract
    assert "交班保留恢复量≥12" in contract


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
    broken_k["records"][0]["ability_evidence"]["stability_k_basis"]["C1"]["K_grade"] = "K9"
    with pytest.raises(ValueError, match="K basis drift"):
        verify_payload(broken_k)

    broken_da = copy.deepcopy(settlement)
    broken_da["records"][0]["ability_evidence"]["destructive_amplification_grade"] = "DA9"
    with pytest.raises(ValueError, match="DA grade drift"):
        verify_payload(broken_da)

    stale_da_label = copy.deepcopy(settlement)
    stale_da_label["records"][0]["behavior_chain"] += " 旧结论DA4。"
    with pytest.raises(ValueError, match="stale DA reader label"):
        verify_payload(stale_da_label)


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


def test_second_item_c4_exposes_unified_m3_scale_adjudication_for_all_records() -> None:
    path = ROOT / "docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json"
    payload = _load(path)
    contract = payload["m3_governance_scale_adjudication_contract"]
    assert contract["schema_version"] == "m3-governance-scale-adjudication-v1"
    assert contract["record_count"] == len(payload["scores"])
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


def test_c4_checklist_structural_recalculation_and_net_legacy_deterioration() -> None:
    finance = ROOT / "docs/评分结算/第二项治国净收益/财政民生"
    c4_payload = _load(finance / "04-C4正式结算.json")
    c4 = {row["ruler_name"]: row for row in c4_payload["scores"]}
    axes = {
        axis: {row["ruler_id"]: row for row in _load(finance / filename)["scores"]}
        for axis, filename in {
            "C1": "01-C1正式结算.json",
            "C2": "02-C2正式结算.json",
            "C3": "03-C3正式结算.json",
        }.items()
    }
    for row in c4.values():
        if row.get("closed_recovery_axes"):
            assert row["recovery_score"] > 0, row["ruler_name"]
        assert "stability_score" not in row
        assert "stability_k_basis" not in row
        assert "weighted_K" not in row
        assert row["positive_score_retained"] == min(row["recovery_score"], row["terminal_cap"])
        for axis, item in row.get("deterioration_path_basis", {}).items():
            state = axes[axis][row["ruler_id"]]["state_anchors"]
            assert item["end_band"] == state["S_end"]


def test_profile_m3_redundant_summaries_follow_current_structured_values() -> None:
    settlement = _load(M3_SETTLEMENT)
    c4 = {
        row["ruler_id"]: row
        for row in _load(ROOT / "docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json")["scores"]
    }
    for row in settlement["records"]:
        upstream = c4[row["ruler_id"]]
        expected = (
            f"可归责恶化扣减{upstream['deterioration_penalty']:.1f}；"
            f"本人可选择行为的残余额外成本为{upstream['destructive_amplification_grade']}，"
            f"扣减{upstream['destructive_amplification_penalty']:.1f}。"
        )
        assert expected in row["costs_and_consequences"]
        assert f"{row['axis_grade']}-{row['position']}" in row["typical_pattern"]


def test_retired_m3_audit_views_are_not_public_entries() -> None:
    project = (ROOT / "config/project.yml").read_text(encoding="utf-8")
    manifest = (ROOT / "docs/评分结算/皇帝人物画像/00-已结算轴正式入口.json").read_text(encoding="utf-8")
    for filename in (
        "30-M3对第二项C1-C4逐人补正审计.json",
        "31-M3民生财政建设全池收口.md",
        "32-M3上游同步与规模档界整改审计.json",
    ):
        assert filename not in project
        assert filename not in manifest
