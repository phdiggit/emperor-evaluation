"""Publication gates for the settled M1 ledger and its reading view."""
from __future__ import annotations

import json
import re
from pathlib import Path

from emperor_v4.evaluation.formal_json_store import load_json

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "人物画像"
SETTLEMENT = PROFILE_ROOT / "M1" / "01-M1军事判断与统帅能力正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
FORBIDDEN_AGGREGATES = ("第三项A+B", "D线性Q", "总排名", "第三项总分")
FORBIDDEN_WINDOW_GATES = ("限定于实际权力窗口", "按现有实际权力窗口内可观察机会", "结合实际权力窗口、本人角色")
WINDOW_DURATION_PATTERNS = (
    r"窗口.{0,10}(?:短|很短|极短|只有|仅)",
    r"亲政窗口.{0,10}(?:短|很短|极短)",
    r"(?:[三四五六七八九十]|[0-9]{1,2})年.{0,8}窗口",
)


def verify() -> dict[str, int]:
    payload = load_json(SETTLEMENT)
    rows = payload["records"]
    pool = load_json(ROOT / "config/common/canonical-ruler-pool.json")
    assert {r["ruler_id"] for r in rows} == {r["ruler_id"] for r in pool["records"] if r["pool_status"] == "INCLUDED"}
    for row in rows:
        text = "\n".join(str(row.get(key, "")) for key in ("grade_basis", "position_basis"))
        serialized = json.dumps(row, ensure_ascii=False)
        assert not any(token in serialized for token in FORBIDDEN_AGGREGATES), "third-item aggregate leaked into M1 record"
        assert not any(token in serialized for token in FORBIDDEN_WINDOW_GATES), "actual_power_window cannot gate M1 evidence admission"
        grading_text = "\n".join(str(row.get(key, "")) for key in ("typical_pattern", "grade_basis", "position_basis")) + "\n" + "\n".join(str(x) for x in row.get("limitations", []))
        assert not any(re.search(pattern, grading_text) for pattern in WINDOW_DURATION_PATTERNS), "actual_power_window duration cannot gate M1 grade"
        claims = set(re.findall(r"(?:取|定|支持)(G[0-5])", text))
        assert claims <= {row["axis_grade"]}, "published grade conflicts with explanatory basis"
    markdown = MARKDOWN.read_text(encoding="utf-8")
    assert "非前线指挥链" not in markdown or "前线−" not in markdown.split("非前线指挥链")[0][-80:], "operational design displayed as frontline"
    assert not any(token in markdown for token in FORBIDDEN_AGGREGATES), "third-item aggregate leaked into reading view"
    assert not any(token in markdown for token in FORBIDDEN_WINDOW_GATES), "actual_power_window gate leaked into M1 reading view"
    return {"records": len(rows), "aggregate_leaks": 0, "window_gate_leaks": 0, "grade_conflicts": 0}
