from pathlib import Path
import re

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.third_item_b1_settlement import (
    load_b1_reaudit_decisions,
    rebuild_third_item_b1,
)


def test_b1_reaudit_decisions_close_the_formal_201_pool() -> None:
    decisions = load_b1_reaudit_decisions(Path("."))
    assert len(decisions) == 201
    assert decisions["RULER-YUAN-TEMUJI"]["final_rate"] == 82
    assert decisions["RULER-YUAN-OGEDEI"]["final_rate"] == 82
    assert decisions["RULER-TANG-LILONGJI"]["final_rate"] == 59
    assert next(
        item["final_rate"]
        for item in decisions.values()
        if item["decision"].get("ruler", item["decision"].get("ruler_name")) == "拓跋嗣"
    ) == 60


def test_b1_recalculation_is_read_only_without_write() -> None:
    report = rebuild_third_item_b1(Path("."), write=False)
    assert report["record_count"] == 201
    assert report["status"] == "READY_TO_WRITE"


def test_formal_b1_rates_and_b80_are_synchronized() -> None:
    decisions = load_b1_reaudit_decisions(Path("."))
    ab_path = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
    rows = load_json(ab_path)["records"]
    assert len(rows) == 201
    for row in rows:
        rate = float(decisions[row["ruler_id"]]["final_rate"])
        adjudication = row["B80_adjudication"]
        assert float(row["axes"]["B1"]["score_rate"]) == rate
        assert float(adjudication["formal_B1_rate"]) == rate
        assert float(adjudication["adjudicated_B1_rate"]) == rate
        expected = round(
            80
            * (0.55 * rate / 100 + 0.45 * float(adjudication["adjudicated_B2_rate"]) / 100)
            * (0.70 + 0.30 * float(adjudication["adjudicated_B4_rate"]) / 100),
            2,
        )
        assert float(adjudication["B80_points"]) == expected


def test_mongol_yuan_unification_precursor_split_is_explicit() -> None:
    ab_path = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
    rows = {row["ruler_id"]: row for row in load_json(ab_path)["records"]}
    temujin = rows["RULER-YUAN-TEMUJI"]
    ogedei = rows["RULER-YUAN-OGEDEI"]

    assert temujin["axes"]["A2"]["end"] == "A2S4_OVERALL_SECURE_WITH_GAPS"
    assert temujin["axes"]["B2"]["grade"] == "B2-5"
    assert temujin["axes"]["B4"]["grade"] == "B4-3"
    assert temujin["b1_cross_item_excluded_weighted_value"] == 1.3
    assert ogedei["axes"]["B2"]["grade"] == "B2-5"
    assert ogedei["axes"]["B4"]["grade"] == "B4-3"
    assert ogedei["b1_cross_item_excluded_weighted_value"] == 1.2


def test_ab_markdown_lists_reader_facing_axis_basis() -> None:
    path = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.md")
    markdown = path.read_text(encoding="utf-8")
    for label in (
        "- A1接手档位：",
        "- A1交班档位：",
        "- A2接手档位：",
        "- A2交班档位：",
        "- B1任内净变化与交班规模：",
        "- B2战略价值说明：",
        "- B4交班成熟度说明：",
    ):
        assert markdown.count(label) == 201
    b1_lines = [
        line for line in markdown.splitlines()
        if line.startswith("- B1任内净变化与交班规模：")
    ]
    assert len(b1_lines) == 201
    assert all(
        any(
            marker in line
            for marker in (
                "控制规模增加区域：",
                "控制规模减少区域：",
                "控制规模净变化区域：无",
            )
        )
        for line in b1_lines
    )
    assert "控制规模增加区域：岭南边疆控制带、北方草原控制空间、西南边疆主要控制空间" in markdown
    assert "控制规模增加区域：晋阳外围恢复州县" in markdown
    assert "跨项排除-" not in markdown
    assert "跨项补回" in markdown
    assert not re.search(r"(?<![A-Za-z0-9_])(?:(?:A1|A2)S[0-5]|S[0-5])(?![A-Za-z0-9_])", markdown)
    assert "只消费本窗口实际恢复、保全或新形成的控制成果；不按战果数量累计" not in markdown
    assert "仅按本人交班时的制度、驻防、和议或防务闭合度裁定，不读继任者结果" not in markdown
    assert "现有材料未闭合本人可计分的新增、恢复、救危保全或维护控制成果" not in markdown
    for line in markdown.splitlines():
        if line.startswith(("- A1接手档位：", "- A1交班档位：", "- A2接手档位：", "- A2交班档位：")):
            assert line.endswith(("。", "！", "？"))
    high_yang_b1 = next(
        line
        for section in markdown.split("\n### ")
        if "高洋（" in section
        for line in section.splitlines()
        if line.startswith("- B1任内净变化与交班规模：")
    )
    assert "控制规模增加区域：北方草原整体" in high_yang_b1
    assert "控制规模减少区域：北方草原整体" not in high_yang_b1
    assert "- A归责：" not in markdown
    assert "- B归责：" not in markdown
    for machine_only_text in (
        "按本人统治窗口",
        "安全结果={",
        "当前公共登记没有可消费主体阶段",
        "第三项保持未结算",
        "原共用裁决未单列接手端独立史实",
        "裁为B2-",
        "裁为B4-",
        "交班控制量-",
    ):
        assert machine_only_text not in markdown

    rows = load_json(path.with_suffix(".json"))["records"]
    assert markdown.count("- A轴共同背景：") == 76
    for row in rows:
        a1 = row["axes"]["A1"]
        a2 = row["axes"]["A2"]
        assert a1["assessment_scope"] == "STRATEGIC_THREAT_CONTROL_STATE"
        assert a2["assessment_scope"] == "STRATEGIC_BOUNDARY_SECURITY_SYSTEM"
        assert str(a1.get("reason") or "").strip()
        assert str(a2.get("reason") or "").strip()
        assert str(a1["reason"]).strip() != str(a2["reason"]).strip()
    mismatch_counts = {"B2": 0, "B4": 0}
    for row in rows:
        for axis_code in mismatch_counts:
            original_rate = float(row["axes"][axis_code]["score_rate"])
            effective_rate = float(
                row["B80_adjudication"][f"adjudicated_{axis_code}_rate"]
            )
            mismatch_counts[axis_code] += original_rate != effective_rate
    for axis_code, count in mismatch_counts.items():
        assert markdown.count(f"原始{axis_code}-") == count
    assert markdown.count("原始档位依据（已被上述调整覆盖）：") == sum(
        mismatch_counts.values()
    )
