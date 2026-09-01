from __future__ import annotations

import copy
import json
import re

import pytest

from emperor_v4.evaluation.profile_m3_settlement import (
    GRADE_PROJECTION,
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
    assert result["grade_distribution"] == {"G0": 6, "G1": 54, "G2": 49, "G3": 59, "G4": 12, "G5": 4}
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


def test_profile_m3_rejects_local_hard_constraint_breakage() -> None:
    settlement = _load(M3_SETTLEMENT)
    broken = copy.deepcopy(settlement)
    broken["records"][0]["score_100"] = -1
    with pytest.raises(ValueError, match="score projection mismatch"):
        verify_payload(broken)


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
