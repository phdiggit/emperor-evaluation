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
