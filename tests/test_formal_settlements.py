import json
from copy import deepcopy
from pathlib import Path

import pytest

from emperor_v4.evaluation.formal_settlements import (
    verify_formal_settlements,
    verify_second_item_a_snapshot,
    verify_second_item_b1_snapshot,
    verify_second_item_b2_snapshot,
)
from emperor_v4.evaluation.composite_ranking import build_composite_ranking
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_b1_settlement import validate_gate_references


def test_c4_contract_uses_cost_scale_da_boundaries() -> None:
    contract = Path(
        "docs/分项规则/第二项治国净收益/财政民生/00-规则与结算合同.md"
    ).read_text(encoding="utf-8")
    assert "C1—C3主态、K折损和C4可归责恶化均未消费的主动成本" in contract
    assert "C1/C2/C3绝对状态与C4可归责恶化可以共同使用同一事实" in contract
    assert "纯军队伤亡不得直接转入第二项" in contract
    assert "军粮、转输、财政抽取" in contract
    assert all(label in contract for label in ("DA5", "DA6", "NEW_BUILD", "仁寿宫"))


def test_all_five_formal_settlements_are_coherent() -> None:
    report = verify_formal_settlements(Path("."))
    assert report["status"] == "PASS"
    assert set(report["items"]) == {
        "first_item",
        "second_item",
        "third_item",
        "fourth_item",
        "fifth_item",
    }
    assert all(item["record_count"] > 0 for item in report["items"].values())
    assert report["second_item_components"] == {
        "component_file_count": 12,
        "complete_ruler_count": 185,
        "finance_ruler_count": 195,
            "A_institution_node_count": 331,
            "A_scoring_node_count": 297,
            "B2_review_adjudication_count": 142,
            "B2_duplicate_markdown_ruler_count": 0,
            "D3_formal_record_count": 185,
            "handoff_formula_record_count": 185,
        }
    assert report["composite_ranking"]["record_count"] == 174
    assert report["composite_ranking"]["pending_second_item_count"] == 10


def test_second_item_a_snapshot_applies_v2_explicit_patch_and_registry() -> None:
    report = verify_second_item_a_snapshot(Path("."))
    assert report == {
        "status": "PASS_WITH_REOPEN",
        "record_count": 185,
        "institution_node_count": 331,
        "scoring_node_count": 297,
        "reference_node_count": 34,
        "explicit_patch_count": 47,
        "extreme_delta_reopen_count": 36,
    }

    payload = load_json(Path("docs/评分结算/第二项治国净收益/制度行政/01-A制度建设与实际运行方向卡.json"))
    rows = {row["ruler_name"]: row for row in payload["records"]}
    assert all(row["C_A"] in {0, 0.5, 1, 2} for row in payload["records"])
    assert all(
        row["S_total"] >= 1 and row["S_net"] >= 0
        for row in payload["records"]
        if row["grade"] in {"G4", "G5"}
    )
    assert rows["朱元璋"]["grade"] == "G3"
    assert rows["朱元璋"]["polarization_floor_triggered"] is True
    assert rows["朱元璋"]["floor_grade"] == "G3"
    assert rows["司马炎"]["polarization_floor_triggered"] is True
    assert rows["赵佶"]["polarization_floor_triggered"] is True
    assert rows["武则天"]["position"] == "lower"
    assert rows["李适"]["position"] == "middle"
    assert rows["武则天"]["direction_index"] < rows["李适"]["direction_index"]
    assert rows["朱厚照"]["S_minus"] == 0
    assert rows["玄烨"]["A_C_A_support_mechanism"] == "内外大臣具折陈事的奏折制度起点"
    assert rows["吕雉"]["grade"] == "G2"
    assert rows["赵佶"]["grade"] == "G2"
    assert rows["陈霸先"]["grade"] == "G2"
    assert rows["耶律洪基"]["grade"] == "G0"
    assert rows["完颜守绪"]["grade"] == "G0"
    assert rows["完颜珣"]["grade"] == "G0"
    assert rows["孙权"]["grade"] == "G3"
    assert rows["忽必烈"]["grade"] == "G4"
    assert rows["杨坚"]["position"] == "middle"
    assert rows["曹叡"]["grade"] == "G2"
    assert rows["朱载坖"]["grade"] == "G4"
    generic_mechanisms = {"其他制度行政机制", "法律、司法与刑罚运行", "选官、人事与官僚专业化", "地方行政与政策交付", "A"}
    assert not any(
        profile.get("mechanism") in generic_mechanisms
        for row in payload["records"]
        for group in ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
        for profile in row[group]
    )
    markdown = Path(
        "docs/评分结算/第二项治国净收益/制度行政/01-A制度建设与实际运行方向卡.md"
    ).read_text(encoding="utf-8")
    ruler_sections = markdown.split("\n### ")[1:]
    assert len(ruler_sections) == 185
    assert all("\n- 材料依据：\n  - 《" in section for section in ruler_sections)
    material_lines = [line for line in markdown.splitlines() if line.startswith("  - ")]
    assert material_lines
    assert all(line.startswith("  - 《") for line in material_lines)
    assert not any(
        token in line
        for line in material_lines
        for token in ("material_id", "evidence_id", "source_url", "revision_ref", "sha256")
    )
    assert not any(
        token in line.split("》", 1)[0]
        for line in material_lines
        for token in ("底账", "登记", "方向卡", "结算", "清单", "index.php")
    )


def test_second_item_b1_snapshot_applies_v20_v50_union_and_v54_contract_recalculation() -> None:
    assert verify_second_item_b1_snapshot(Path(".")) == {
        "status": "PASS_V54_LOW_GATE_NEGATIVE_PURITY_CONTRACT_READJUDICATED",
        "record_count": 185,
        "reviewed_count": 185,
        "direct_material_count": 447,
        "verification_material_count": 83,
        "invalid_M1_count": 0,
        "duplicate_markdown_ruler_count": 0,
        "profile_semantic_review_count": 185,
        "grade_distribution": {
            "G0": 7, "G1": 25, "G2": 52, "G3": 55, "G4": 43, "G5": 3,
        },
        "contract_recalculation_count": 185,
        "position_basis_refresh_count": 185,
        "structured_basis_count": 185,
    }

    payload = load_json(Path("docs/评分结算/第二项治国净收益/制度行政/02-B1官僚治理与行政执行方向卡.json"))
    rows = {row["ruler_name"]: row for row in payload["records"]}
    assert (rows["刘裕"]["grade"], rows["刘裕"]["position"], rows["刘裕"]["direction_index"]) == (
        "G4", "middle-upper", 80.4
    )
    assert (rows["陈叔宝"]["grade"], rows["陈叔宝"]["position"], rows["陈叔宝"]["direction_index"]) == (
        "G0", "lower", 2.0
    )
    assert payload["contract_recalculation_status"] == "FORMAL_COMPLETE"
    assert all(row["profile_semantic_review_status"] == "B1_CONTRACT_V54_LOW_GATE_NEGATIVE_PURITY_REVIEWED" for row in rows.values())
    assert payload["review_material_absorption"]["v20_reviewed_count"] == 174
    assert payload["review_material_absorption"]["v50_reviewed_count"] == 164
    assert not any("position_depth_bonus" in json.dumps(row, ensure_ascii=False) for row in rows.values())
    assert all(len(row["structured_grade_basis"]) >= 2 for row in rows.values())
    assert (rows["李世民"]["position"], rows["李世民"]["direction_index"], rows["李世民"]["position_residual"]) == ("upper", 98.5, 2.0)
    assert (rows["陈蒨"]["grade"], rows["陈蒨"]["position"], rows["陈蒨"]["direction_index"]) == (
        "G4", "middle", 77.5
    )
    assert rows["陈蒨"]["g4_core_profile_id"] and rows["陈蒨"]["g4_secondary_profile_id"]
    assert (rows["刘秀"]["grade"], rows["刘秀"]["position"], rows["刘秀"]["direction_index"]) == (
        "G4", "middle-upper", 80.4
    )
    assert "侯霸—郭贺—冯勤" in rows["刘秀"]["grade_basis"]
    assert (rows["完颜晟"]["grade"], rows["完颜晟"]["position"], rows["完颜晟"]["direction_index"]) == (
        "G4", "middle-upper", 80.4
    )
    assert [profile["signed_weight"] for profile in rows["完颜晟"]["M_positive_profile"]] == [2.0, 2.0]
    assert rows["完颜晟"]["M_negative_profile"][0]["b1_role"] == "context"
    assert rows["朱见深"]["M_negative_profile"][0]["M"] == "M2"
    assert rows["朱见深"]["M_negative_profile"][0]["direction"] == "mixed_negative"
    assert (rows["赵光义"]["grade"], rows["赵光义"]["position"]) == ("G4", "upper")
    assert (rows["刘启"]["grade"], rows["刘启"]["position"]) == ("G3", "middle-upper")
    assert (rows["马殷"]["grade"], rows["马殷"]["position"]) == ("G2", "lower")
    assert rows["刘询"]["g5_extra_route"] == "PRESSURE_RECOVERY"
    assert rows["完颜雍"]["g5_extra_route"] == "CROSS_STAGE_REPLACEMENT"
    assert (rows["完颜雍"]["position"], rows["完颜雍"]["direction_index"]) == ("upper", 98.5)
    assert "I2-JIN-MAT-5A3139D53395A1D3" in rows["完颜雍"]["direct_material_ids"]
    assert "I2-JIN-MAT-5A3139D53395A1D3" not in rows["完颜雍"]["verification_material_ids"]
    assert any(point["role"] == "负向依据（M3，cross）" for point in rows["朱棣"]["structured_grade_basis"])
    assert any(point["role"] == "负向依据（M3，terminal）" for point in rows["完颜守绪"]["structured_grade_basis"])
    assert rows["曹操"]["M_mixed_profile"] == []
    assert {profile["M"] for profile in rows["曹操"]["M_positive_profile"]} == {"M3"}
    assert rows["曹操"]["M_negative_profile"][0]["M"] == "M3"
    assert (rows["旻宁"]["grade"], rows["旻宁"]["position"], rows["旻宁"]["direction_index"]) == (
        "G4", "middle", 77.5
    )
    assert rows["旻宁"]["M_negative_profile"][0]["b1_role"] == "context"
    for name in ("刘奭", "赵佶", "刘聪", "孙皓"):
        assert any(
            profile.get("M") == "M3"
            and profile.get("severity") == "N3-cross"
            and profile.get("severity_scope") in {"major-stage", "broad"}
            for profile in rows[name]["M_negative_profile"]
        )
    assert rows["耶律延禧"]["M_negative_profile"][1]["severity"] == "N3-terminal"
    assert rows["耶律延禧"]["M_negative_profile"][1]["severity_scope"] == "broad"
    assert rows["李煜"]["M_negative_profile"][0]["b1_role"] == "context"
    assert rows["完颜亮"]["M_negative_profile"][1]["b1_role"] == "context"


def test_second_item_b1_v54_validator_blocks_hidden_weights_severity_cross_low_gates_and_support_core() -> None:
    payload = load_json(Path("docs/评分结算/第二项治国净收益/制度行政/02-B1官僚治理与行政执行方向卡.json"))
    validate_gate_references(payload)

    broken = deepcopy(payload)
    next(row for row in broken["records"] if row["ruler_name"] == "完颜晟")["M_positive_profile"][0]["signed_weight"] = 1.0
    with pytest.raises(ValueError, match="M档与signed_weight不一致"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    yelu_deguang = next(row for row in broken["records"] if row["ruler_name"] == "耶律德光")
    yelu_deguang["M_negative_profile"][0].pop("severity_scope")
    with pytest.raises(ValueError, match="Severity scope"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    chen_qian = next(row for row in broken["records"] if row["ruler_name"] == "陈蒨")
    core = next(profile for profile in chen_qian["M_positive_profile"] if profile["profile_id"] == chen_qian["g4_core_profile_id"])
    core["b1_role"] = "support"
    with pytest.raises(ValueError, match="不是B1-core正M3"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    liu_cong = next(row for row in broken["records"] if row["ruler_name"] == "刘聪")
    profile = liu_cong["M_negative_profile"][0]
    profile.update({"M": "M0", "direction": "context", "direction_factor": 0.0, "signed_weight": 0.0, "b1_role": "context"})
    for field in ("severity", "severity_scope", "severity_basis"):
        profile.pop(field, None)
    with pytest.raises(ValueError, match="B1 G1缺少"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    yelu_yanxi = next(row for row in broken["records"] if row["ruler_name"] == "耶律延禧")
    terminal = next(profile for profile in yelu_yanxi["M_negative_profile"] if profile.get("severity") == "N3-terminal")
    terminal["severity"] = "N3-cross"
    terminal["severity_scope"] = "major-stage"
    with pytest.raises(ValueError, match="B1 G0缺少"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    zhu_jianshen = next(row for row in broken["records"] if row["ruler_name"] == "朱见深")
    west_depot = zhu_jianshen["M_negative_profile"][0]
    west_depot.update({"M": "M3", "signed_weight": -2.0, "severity": "N3-cross", "severity_scope": "major-stage"})
    with pytest.raises(ValueError, match="major-stage/broad N3-cross"):
        validate_gate_references(broken)


def test_second_item_b2_snapshot_applies_review_final_table() -> None:
    assert verify_second_item_b2_snapshot(Path(".")) == {
        "status": "PASS",
        "record_count": 185,
        "review_adjudication_count": 142,
        "person_patch_count": 142,
        "settlement_basis_count": 185,
        "grade_distribution": {
            "G0": 14,
            "G1": 72,
            "G2": 65,
            "G3": 27,
            "G4": 5,
            "G5": 2,
        },
        "invalid_M1_count": 0,
        "duplicate_markdown_ruler_count": 0,
    }


def test_composite_ranking_uses_only_ready_rulers_and_current_formula() -> None:
    payload = build_composite_ranking(Path("."))
    assert payload["record_count"] == 174
    assert payload["pending_second_item_count"] == 10
    assert payload["records"][0]["ruler_name"] == "李世民"
    assert payload["formula"] == "T = S2 + S3 + S5 + 0.10 * 757 * (S1 / 240) ^ 1.25 + CIV4"
    assert payload["records"][0]["total_score"] == 809.04
    assert payload["records"][1]["ruler_name"] == "玄烨"
    assert payload["records"][1]["total_score"] == 592.74
    zhao_ji = next(row for row in payload["records"] if row["ruler_name"] == "赵佶")
    assert zhao_ji["first_item_status"] == "NOT_APPLICABLE"
    assert zhao_ji["first_item_raw_score"] is None
    assert zhao_ji["first_item_add_on"] == 0.0
    assert all(
        row["ruler_name"] not in {pending["ruler_name"] for pending in payload["pending_second_item_records"]}
        for row in payload["records"]
    )
    for row in payload["records"]:
        expected = round(
            row["second_item_score"]
            + row["third_item_score"]
            + row["fifth_item_score"]
            + row["first_item_add_on"]
            + row["fourth_item_adjustment"],
            2,
        )
        assert abs(row["total_score"] - expected) <= 0.01


def test_liu_hu_and_liu_zhi_finance_records_use_personal_rule_windows() -> None:
    root = Path("docs/评分结算/第二项治国净收益/财政民生")
    payloads = {
        axis: load_json(root / filename)
        for axis, filename in {
            "C1": "01-C1正式结算.json",
            "C2": "02-C2正式结算.json",
            "C3": "03-C3正式结算.json",
            "C4": "04-C4正式结算.json",
        }.items()
    }
    rows = {
        axis: {
            row["ruler_name"]: row
            for row in (payload.get("scores") or payload.get("records") or [])
        }
        for axis, payload in payloads.items()
    }
    for axis in rows:
        assert rows[axis]["刘祜"]["reign_range"] == "121—125"
        assert rows[axis]["刘志"]["reign_range"] == "150—168"
    for axis in ("C1", "C2", "C3"):
        assert rows[axis]["刘祜"]["confidence"].endswith("WINDOW_READJUDICATED")
        assert rows[axis]["刘志"]["confidence"].endswith("WINDOW_READJUDICATED")
    assert rows["C2"]["刘志"]["state_anchors"] == {
        "S0": "C2-3",
        "S_avg": "C2-2",
        "S_end": "C2-2",
    }
    liu_zhi_c3_refs = json.dumps(rows["C3"]["刘志"]["evidence"], ensure_ascii=False)
    assert "卷058" not in liu_zhi_c3_refs
    assert "黄巾均不进入刘志结算" in liu_zhi_c3_refs
    liu_hu_c4 = rows["C4"]["刘祜"]
    assert "征役无度，老弱相随，动有万计" in liu_hu_c4[
        "deterioration_curve_summary"
    ]
    assert liu_hu_c4["destructive_amplification_grade"] == "DA2"
    liu_zhuang_c4 = rows["C4"]["刘庄"]
    assert liu_zhuang_c4["score"] == round(
        liu_zhuang_c4["positive_score_retained"]
        - liu_zhuang_c4["deterioration_penalty"]
        - liu_zhuang_c4["destructive_amplification_penalty"],
        1,
    )
    assert liu_zhuang_c4["destructive_amplification_grade"] == "DA2"
    assert "人失农时" in liu_zhuang_c4[
        "deterioration_curve_summary"
    ]


def test_c4_uses_one_current_destructive_amplification_verdict() -> None:
    path = Path("docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json")
    payload = load_json(path)
    penalties = {
        "DA0": 0.0, "DA1": 4.5, "DA2": 9.0, "DA3": 13.5,
        "DA4": 18.0, "DA5": 22.5, "DA6": 27.0,
    }

    assert payload["attribution_readjudication"]["status"] == "FORMAL_COMPLETE"
    assert payload["review_progress"]["remaining_record_count"] == 0
    for row in payload["scores"]:
        grade = row["destructive_amplification_grade"]
        review = row["c4_attribution_readjudication"]
        assert row["destructive_amplification_penalty"] == penalties[grade]
        assert review["final_grade"] == grade
        assert review["final_penalty"] == penalties[grade]
        assert row["military_cost_review"]["final_grade"] == grade
        assert row["negative_tail_adjudication_reason"] == row["behavior_and_attribution"]
        assert row["attribution_readjudication_reason"] == row["behavior_and_attribution"]
        assert "previous_grade" not in review
        assert "original_adjudication_reason" not in review


def test_five_dynasties_batch_is_fully_settled() -> None:
    root = Path("docs/评分结算/第二项治国净收益")
    finance = root / "财政民生"
    files = {
        "C1": "01-C1正式结算.json",
        "C2": "02-C2正式结算.json",
        "C3": "03-C3正式结算.json",
        "C4": "04-C4正式结算.json",
        "result": "05-治理结果正式结算.json",
    }
    rows = {
        axis: {
            row["ruler_name"]: row
            for row in load_json(finance / filename)["scores"]
        }
        for axis, filename in files.items()
    }
    expected = {"杨行密", "钱镠", "马殷", "高季兴", "孟知祥", "李克用", "刘崇"}
    for name in expected:
        components = [rows[axis][name]["score"] for axis in ("C1", "C2", "C3", "C4")]
        assert rows["result"][name]["score"] == round(sum(components), 1)
    total_rows = {
        row["ruler_name"]: row
        for row in json.loads(
            (root / "01-第二项治国净收益正式结算.json").read_text(encoding="utf-8")
        )["records"]
    }
    for name in expected:
        row = total_rows[name]
        assert row["second_item_score"] == round(
            row["governance_method_score"] + row["governance_result_score"] + row["handoff_score"], 1
        )


def test_recent_batch_calibration_keeps_rare_feedback_grades_rare() -> None:
    root = Path("docs/评分结算/第二项治国净收益")
    recent = {
        "刘崇", "孟知祥", "李克用", "杨行密", "钱镠", "马殷", "高季兴",
        "耶律阿保机", "耶律德光", "耶律阮", "耶律贤", "萧绰", "耶律隆绪", "耶律宗真", "耶律洪基", "耶律延禧", "耶律大石",
        "完颜阿骨打", "完颜晟", "完颜亶", "完颜亮", "完颜雍", "完颜璟", "完颜永济", "完颜珣", "完颜守绪",
    }
    b1 = {
        row["ruler_name"]: row
        for row in load_json(root / "制度行政/02-B1官僚治理与行政执行方向卡.json")["records"]
    }
    b2 = {
        row["ruler_name"]: row
        for row in load_json(root / "制度行政/03-B2反馈纠错与权力约束方向卡.json")["records"]
    }
    assert {name for name in recent if b1[name]["grade"] == "G5"} == {"完颜雍"}
    assert {name for name in recent if b2[name]["grade"] == "G4"} == {"完颜雍"}
    assert {name for name in recent if b2[name]["grade"] == "G3"} == {"耶律宗真"}
    assert all(b2[name]["grade"] != "G5" for name in recent)

    totals = {
        row["ruler_name"]: row
        for row in json.loads(
            (root / "01-第二项治国净收益正式结算.json").read_text(encoding="utf-8")
        )["records"]
    }
    for name in ("完颜雍", "萧绰", "耶律隆绪", "完颜晟", "完颜守绪"):
        row = totals[name]
        assert row["second_item_score"] == round(
            row["governance_method_score"] + row["governance_result_score"] + row["handoff_score"], 1
        )
