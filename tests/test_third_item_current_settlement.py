from pathlib import Path

from emperor_v4.evaluation.third_item_current_settlement import (
    verify_current_third_item_settlement,
)


ROOT = Path(__file__).resolve().parents[1]


def test_current_third_item_formal_snapshot_is_internally_closed() -> None:
    result = verify_current_third_item_settlement(ROOT)
    assert result["status"] == "PASS"
    assert result["record_count"] == result["score_ready_count"] == 201
    assert result["pending_count"] == 0


def test_current_third_item_reader_view_hides_internal_factor() -> None:
    markdown = (
        ROOT / "docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.md"
    ).read_text(encoding="utf-8")
    assert "factor" not in markdown.casefold()
    assert markdown.count("<summary>成本明细（") == 201
    assert markdown.count("</details>") == 201
