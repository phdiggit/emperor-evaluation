"""The nine-axis reading table must track every current formal axis."""

from pathlib import Path

import yaml

from emperor_v4.evaluation.formal_json_store import load_json


ROOT = Path(__file__).resolve().parents[1]


def test_nine_axis_summary_matches_formal_records():
    project = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    profile = project["profile_assessment"]
    axes = profile["axis_order"]
    pool = load_json(ROOT / project["canonical_ruler_pool"]["json"])
    people = [r for r in pool["records"] if r["pool_status"] == "INCLUDED"]
    formal = {
        axis: {r["ruler_id"]: r for r in load_json(ROOT / profile["settled_axes"][axis]["json"])["records"]}
        for axis in axes
    }
    path = ROOT / profile["summary_markdown"]
    table = path.read_text(encoding="utf-8").split("## 人物九轴结算", 1)[1]
    rows = [line.strip("| ").split(" | ") for line in table.splitlines() if line.startswith("| ")]
    assert rows[0][3:] == axes
    assert len(rows[2:]) == len(people)
    for number, (person, cells) in enumerate(zip(people, rows[2:]), 1):
        assert cells[:3] == [str(number), person["ruler_name"], person["polity"]]
        for axis, actual in zip(axes, cells[3:]):
            row = formal[axis][person["ruler_id"]]
            label = f"{row['axis_grade']}-{row['position']}"
            if row.get("adjudication_state") == "EVIDENCE_INSUFFICIENT_CLOSED":
                expected = "无档结案·证据不足（—）"
            elif row.get("score_status") == "NOT_APPLICABLE":
                expected = "不适用（—）"
            elif row.get("display_point_only") or row.get("adjudication_state") in {"UNRESOLVED_EVIDENCE_GAP", "REASSESSMENT_REQUIRED"}:
                expected = f"显示点·{label}（—）"
            else:
                expected = label
            assert actual == expected, (person["ruler_id"], axis)
