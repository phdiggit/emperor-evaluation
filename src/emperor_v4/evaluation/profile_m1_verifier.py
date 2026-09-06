"""Publication gates for the settled M1 ledger and its reading view."""
from __future__ import annotations

import json
import re
from pathlib import Path

from emperor_v4.evaluation.formal_json_store import load_json

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
SETTLEMENT = PROFILE_ROOT / "M1" / "01-M1军事判断与统帅能力正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
FORBIDDEN_AGGREGATES = ("第三项A+B", "D线性Q", "总排名", "第三项总分")


def verify() -> dict[str, int]:
    payload = load_json(SETTLEMENT)
    rows = payload["records"]
    pool = load_json(ROOT / "config/common/canonical-ruler-pool.json")
    assert {r["ruler_id"] for r in rows} == {r["ruler_id"] for r in pool["records"] if r["pool_status"] == "INCLUDED"}
    for row in rows:
        text = "\n".join(str(row.get(key, "")) for key in ("grade_basis", "position_basis"))
        serialized = json.dumps(row, ensure_ascii=False)
        assert not any(token in serialized for token in FORBIDDEN_AGGREGATES), "third-item aggregate leaked into M1 record"
        claims = set(re.findall(r"(?:取|定|支持)(G[0-5])", text))
        assert claims <= {row["axis_grade"]}, "published grade conflicts with explanatory basis"
    markdown = MARKDOWN.read_text(encoding="utf-8")
    assert "非前线指挥链" not in markdown or "前线−" not in markdown.split("非前线指挥链")[0][-80:], "operational design displayed as frontline"
    assert not any(token in markdown for token in FORBIDDEN_AGGREGATES), "third-item aggregate leaked into reading view"
    return {"records": len(rows), "aggregate_leaks": 0, "grade_conflicts": 0}
