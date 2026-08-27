import json
from pathlib import Path

from emperor_v4.evaluation.third_item_current_settlement import (
    build_current_third_item_settlement,
)


ROOT = Path(__file__).resolve().parents[1]
FORMAL_PATH = ROOT / "docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json"


def test_current_third_item_rebuild_matches_formal_scores() -> None:
    rebuilt = build_current_third_item_settlement(ROOT)
    formal = json.loads(FORMAL_PATH.read_text(encoding="utf-8"))
    assert rebuilt["component_coverage_counts"] == formal["component_coverage_counts"]
    assert [
        (row["ruler_id"], row["third_item_score_points"], row["rank"])
        for row in rebuilt["records"]
    ] == [
        (row["ruler_id"], row["third_item_score_points"], row["rank"])
        for row in formal["records"]
    ]
