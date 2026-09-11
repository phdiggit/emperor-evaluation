from pathlib import Path
import re

from emperor_v4.evaluation.formal_json_store import load_json


def test_formal_b1_rates_and_b80_are_synchronized() -> None:
    credit_path = Path("config/third-item/third-item-result-credit-adjudications.json")
    decisions = {row["ruler_id"]: row for row in load_json(credit_path)["records"]}
    ab_path = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
    rows = load_json(ab_path)["records"]
    for row in rows:
        decision = decisions[row["ruler_id"]]["B80_adjudication"]
        rate = float(decision["adjudicated_B1_rate"])
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


def test_ab_markdown_lists_reader_facing_axis_basis() -> None:
    path = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.md")
    markdown = path.read_text(encoding="utf-8")
    rows = load_json(path.with_suffix(".json"))["records"]
    for label in (
        "**A1 战略威胁**", "**A2 战略边界**", "**B1 控制规模**",
        "**B2 战略价值**", "**B4 交班成熟度**",
        "<summary>计分明细与来源</summary>",
    ):
        assert markdown.count(label) == len(rows)
    assert markdown.count("<details>") == markdown.count("</details>") == len(rows)
    sections = re.split(r"(?=^### )", markdown, flags=re.M)[1:]
    assert len(sections) == len(rows)
    for row in rows:
        section = next(part for part in sections if f". {row['ruler_name']}（" in part.splitlines()[0])
        for axis_code, title in (("A1", "战略威胁"), ("A2", "战略边界")):
            axis = row["A120_axis_adjudications"][axis_code]
            assert f"| {axis_code} {title} | {axis['start_grade']}→{axis['end_grade']}档" in section
            assert f"{float(axis['axis_points']):.2f}／60 |" in section
        for axis_code in ("B1", "B2", "B4"):
            rate = float(row['B80_adjudication'][f'adjudicated_{axis_code}_rate'])
            assert f"| {rate:g}% |" in section
        assert any(label in section for label in ("控制规模增加区域：", "控制规模减少区域：", "控制规模净变化区域：无"))
        main = section.split('<details>')[0]
        assert "NOT_APPLICABLE" not in main
        assert "截断前轨迹值" not in main
        assert "完整轨迹依据：" not in main
    assert "跨项排除-" not in markdown
    assert not re.search(r"(?<![A-Za-z0-9_])(?:(?:A1|A2)S[0-5]|S[0-5])(?![A-Za-z0-9_])", markdown)
    assert "只消费本窗口实际恢复、保全或新形成的控制成果；不按战果数量累计" not in markdown
    assert "仅按本人交班时的制度、驻防、和议或防务闭合度裁定，不读继任者结果" not in markdown
    assert "现有材料未闭合本人可计分的新增、恢复、救危保全或维护控制成果" not in markdown
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
