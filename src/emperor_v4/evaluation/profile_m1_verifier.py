"""Publication gates for the settled M1 ledger and its reading view."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
SETTLEMENT = PROFILE_ROOT / "M1" / "01-M1军事判断与统帅能力正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
CLEANUP_REVIEW = PROFILE_ROOT / "M1" / "12-M1结算账本整改与异常重裁复核.json"
FORBIDDEN_AGGREGATES = ("第三项A+B", "D线性Q", "总排名", "第三项总分")


def verify() -> dict[str, int]:
    payload = json.loads(SETTLEMENT.read_text(encoding="utf-8"))
    rows = payload["records"]
    assert len(rows) == 184
    for row in rows:
        text = "\n".join(str(row.get(key, "")) for key in ("grade_basis", "position_basis"))
        serialized = json.dumps(row, ensure_ascii=False)
        assert not any(token in serialized for token in FORBIDDEN_AGGREGATES), "third-item aggregate leaked into M1 record"
        claims = set(re.findall(r"(?:取|定|支持)(G[0-5])", text))
        assert claims <= {row["axis_grade"]}, "published grade conflicts with explanatory basis"
    markdown = MARKDOWN.read_text(encoding="utf-8")
    assert "## 结算账本整改（2026-08）" in markdown, "M1 reading view is missing the ledger-cleanup disclosure"
    assert "非前线指挥链" not in markdown or "前线−" not in markdown.split("非前线指挥链")[0][-80:], "operational design displayed as frontline"
    assert not any(token in markdown for token in FORBIDDEN_AGGREGATES), "third-item aggregate leaked into reading view"
    cleanup = json.loads(CLEANUP_REVIEW.read_text(encoding="utf-8"))
    assert cleanup["grade_changes"] == [], "ledger cleanup must not silently regrade records"
    assert cleanup["ledger_cleanup"]["grade_basis_conflicts_remaining"] == 0
    assert cleanup["ledger_cleanup"]["third_item_aggregate_tokens_in_all_m1_records"] == 0
    queue = cleanup["exception_rejudication_queue"]
    assert len(queue) >= 9 and {entry["queue_type"] for entry in queue} == {
        "THIN_G4", "ANCHOR_REVERSE_GAP", "STRATEGIC_G3_HIGH"
    }
    return {"records": len(rows), "aggregate_leaks": 0, "grade_conflicts": 0, "exception_candidates": len(queue)}
