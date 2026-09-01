import json
from pathlib import Path

from emperor_v4.evaluation.formal_settlements import (
    verify_formal_settlements,
    verify_second_item_a_snapshot,
    verify_second_item_b2_snapshot,
)
from emperor_v4.evaluation.composite_ranking import _sha256 as composite_source_sha256
from emperor_v4.evaluation.composite_ranking import build_composite_ranking


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
        "A_institution_node_count": 299,
        "A_scoring_node_count": 263,
        "B2_review_adjudication_count": 142,
        "B2_duplicate_markdown_ruler_count": 0,
    }
    assert report["composite_ranking"]["record_count"] == 174
    assert report["composite_ranking"]["pending_second_item_count"] == 10


def test_second_item_a_snapshot_applies_v2_explicit_patch_and_registry() -> None:
    report = verify_second_item_a_snapshot(Path("."))
    assert report == {
        "status": "PASS_WITH_REOPEN",
        "record_count": 185,
        "institution_node_count": 299,
        "scoring_node_count": 263,
        "reference_node_count": 36,
        "explicit_patch_count": 47,
        "extreme_delta_reopen_count": 36,
    }

    payload = json.loads(
        Path("docs/评分结算/第二项治国净收益/制度行政/01-A制度建设与实际运行方向卡.json").read_text(
            encoding="utf-8"
        )
    )
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
    assert payload["records"][0]["total_score"] == 820.61
    assert payload["records"][1]["ruler_name"] == "玄烨"
    assert payload["records"][1]["total_score"] == 612.62
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
        axis: json.loads((root / filename).read_text(encoding="utf-8"))
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
        "S0": "C2-2",
        "S_avg": "C2-2",
        "S_end": "C2-2",
    }
    liu_zhi_c3_refs = json.dumps(rows["C3"]["刘志"]["evidence"], ensure_ascii=False)
    assert "卷058" not in liu_zhi_c3_refs
    assert "黄巾均不进入刘志结算" in liu_zhi_c3_refs
    assert "C2/C3同源回落仅作互证，不重复扣分" in rows["C4"]["刘祜"][
        "deterioration_curve_summary"
    ]
    liu_zhuang_c4 = rows["C4"]["刘庄"]
    assert liu_zhuang_c4["main_band"] == "C4-2"
    assert liu_zhuang_c4["score"] == 12.6
    assert liu_zhuang_c4["destructive_amplification_grade"] == "DA0"
    assert "不以外生冲击追加归责扣分" in liu_zhuang_c4[
        "deterioration_curve_summary"
    ]
    assert "最终为C4-1" not in liu_zhuang_c4["deterioration_curve_summary"]


def test_five_dynasties_batch_is_fully_settled() -> None:
    root = Path("docs/评分结算/第二项治国净收益")
    finance = root / "财政民生"
    files = {
        "C1": "01-C1正式结算.json",
        "C2": "02-C2正式结算.json",
        "C3": "03-C3正式结算.json",
        "C4": "04-C4正式结算.json",
        "result": "05-治理结果220分正式结算.json",
    }
    rows = {
        axis: {
            row["ruler_name"]: row
            for row in json.loads((finance / filename).read_text(encoding="utf-8"))["scores"]
        }
        for axis, filename in files.items()
    }
    expected = {
        "杨行密": (32.0, 14.9, 28.0, 15.9, 90.8),
        "钱镠": (17.1, 23.6, 16.0, 3.4, 60.1),
        "马殷": (54.9, 23.6, 28.0, 15.9, 122.4),
        "高季兴": (32.0, 14.9, 28.0, 19.7, 94.6),
        "孟知祥": (32.0, 14.9, 28.0, 11.0, 85.9),
        "李克用": (17.1, 7.0, 16.0, -9.0, 31.1),
        "刘崇": (17.1, 14.9, 28.0, -1.1, 58.9),
    }
    for name, scores in expected.items():
        assert tuple(rows[axis][name]["score"] for axis in files) == scores
    total_rows = {
        row["ruler_name"]: row
        for row in json.loads(
            (root / "01-第二项治国净收益405分正式结算.json").read_text(encoding="utf-8")
        )["records"]
    }
    assert {name: total_rows[name]["second_item_score"] for name in expected} == {
        "杨行密": 200.1,
        "钱镠": 166.9,
        "马殷": 228.2,
        "高季兴": 186.7,
        "孟知祥": 203.2,
        "李克用": 94.6,
        "刘崇": 125.2,
    }


def test_recent_batch_calibration_keeps_rare_feedback_grades_rare() -> None:
    root = Path("docs/评分结算/第二项治国净收益")
    recent = {
        "刘崇", "孟知祥", "李克用", "杨行密", "钱镠", "马殷", "高季兴",
        "耶律阿保机", "耶律德光", "耶律阮", "耶律贤", "萧绰", "耶律隆绪", "耶律宗真", "耶律洪基", "耶律延禧", "耶律大石",
        "完颜阿骨打", "完颜晟", "完颜亶", "完颜亮", "完颜雍", "完颜璟", "完颜永济", "完颜珣", "完颜守绪",
    }
    b1 = {
        row["ruler_name"]: row
        for row in json.loads(
            (root / "制度行政/02-B1官僚治理与行政执行方向卡.json").read_text(encoding="utf-8")
        )["records"]
    }
    b2 = {
        row["ruler_name"]: row
        for row in json.loads(
            (root / "制度行政/03-B2反馈纠错与权力约束方向卡.json").read_text(encoding="utf-8")
        )["records"]
    }
    assert all(b1[name]["grade"] != "G5" for name in recent)
    assert {name for name in recent if b2[name]["grade"] == "G4"} == {"完颜雍"}
    assert {name for name in recent if b2[name]["grade"] == "G3"} == {"耶律宗真"}
    assert all(b2[name]["grade"] != "G5" for name in recent)

    totals = {
        row["ruler_name"]: row
        for row in json.loads(
            (root / "01-第二项治国净收益405分正式结算.json").read_text(encoding="utf-8")
        )["records"]
    }
    assert {name: totals[name]["second_item_score"] for name in (
        "完颜雍", "萧绰", "耶律隆绪", "完颜晟", "完颜守绪"
    )} == {
        "完颜雍": 282.8,
        "萧绰": 262.5,
        "耶律隆绪": 243.0,
        "完颜晟": 173.2,
        "完颜守绪": 89.9,
    }

def test_composite_source_fingerprint_is_stable_across_git_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b'{\n  "value": 1\n}\n')
    crlf.write_bytes(b'{\r\n  "value": 1\r\n}\r\n')
    assert composite_source_sha256(lf) == composite_source_sha256(crlf)
