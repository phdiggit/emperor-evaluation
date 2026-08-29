import json
from pathlib import Path

from emperor_v4.evaluation.formal_settlements import verify_formal_settlements
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
    }
    assert report["composite_ranking"]["record_count"] == 174
    assert report["composite_ranking"]["pending_second_item_count"] == 10


def test_composite_ranking_uses_only_ready_rulers_and_current_formula() -> None:
    payload = build_composite_ranking(Path("."))
    assert payload["record_count"] == 174
    assert payload["pending_second_item_count"] == 10
    assert payload["records"][0]["ruler_name"] == "李世民"
    assert payload["records"][0]["total_score"] == 820.81
    assert payload["records"][1]["ruler_name"] == "玄烨"
    assert payload["records"][1]["total_score"] == 602.02
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
        "杨行密": (32.0, 14.9, 28.0, 24.9, 99.8),
        "钱镠": (17.1, 23.6, 16.0, 16.9, 73.6),
        "马殷": (54.9, 23.6, 28.0, 24.9, 131.4),
        "高季兴": (32.0, 14.9, 28.0, 24.9, 99.8),
        "孟知祥": (32.0, 14.9, 28.0, 21.0, 95.9),
        "李克用": (17.1, 7.0, 16.0, -9.0, 31.1),
        "刘崇": (17.1, 14.9, 28.0, 7.9, 67.9),
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
        "杨行密": 209.1,
        "钱镠": 180.4,
        "马殷": 237.2,
        "高季兴": 191.9,
        "孟知祥": 213.2,
        "李克用": 94.6,
        "刘崇": 134.2,
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
    assert {name for name in recent if b2[name]["grade"] == "G3"} == {"萧绰", "耶律隆绪"}
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
        "完颜雍": 304.5,
        "萧绰": 271.5,
        "耶律隆绪": 266.6,
        "完颜晟": 178.2,
        "完颜守绪": 94.4,
    }

    c4 = {
        row["ruler_name"]: row
        for row in json.loads(
            (root / "财政民生/04-C4正式结算.json").read_text(encoding="utf-8")
        )["scores"]
    }
    assert c4["耶律隆绪"]["recovery_score"] == 4.1
    assert c4["耶律隆绪"]["stability_score"] == 3.0
    assert c4["耶律隆绪"]["score"] == 7.1


def test_composite_source_fingerprint_is_stable_across_git_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b'{\n  "value": 1\n}\n')
    crlf.write_bytes(b'{\r\n  "value": 1\r\n}\r\n')
    assert composite_source_sha256(lf) == composite_source_sha256(crlf)
