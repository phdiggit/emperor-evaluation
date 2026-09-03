from __future__ import annotations

import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(".")
FIRST_ITEM_DIR = ROOT / "docs/评分结算/第一项创业与政权取得能力"
FORMAL_PATH = FIRST_ITEM_DIR / "01-第一项创业与政权取得能力正式结算.json"
SUBITEM_PATHS = (
    FIRST_ITEM_DIR / "战略决策能力/01-第一项A战略决策能力结算.md",
    FIRST_ITEM_DIR / "政治整合能力/01-第一项B政治整合能力结算.md",
    FIRST_ITEM_DIR / "军事夺取能力/01-第一项C军事夺取能力结算.md",
)
SUMMARY_PATH = FIRST_ITEM_DIR / "02-第一项结算总结分析.md"


def _eligible_names() -> set[str]:
    payload = json.loads(FORMAL_PATH.read_text(encoding="utf-8"))
    return {
        row["ruler_name"]
        for row in payload["records"]
        if row["score_applicable"]
    }


def test_each_first_item_subitem_has_person_by_person_basis() -> None:
    expected = _eligible_names()
    assert len(expected) == 84
    for path in SUBITEM_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "## 逐人结算依据" in text, path
        section = text.split("## 逐人结算依据", 1)[1]
        blocks = re.findall(
            r"(?ms)^### \d+\. (?P<name>[^\r\n]+)\r?\n(?P<body>.*?)(?=^### |^## |\Z)",
            section,
        )
        assert {name for name, _ in blocks} == expected, path
        assert all(
            any(label in body for label in ("- 归责：", "- 裁决：", "- C1依据："))
            for _, body in blocks
        ), path


def test_first_item_summary_uses_current_rank_and_evidence_scopes() -> None:
    text = SUMMARY_PATH.read_text(encoding="utf-8")
    assert "李世民以204.3列第3" in text
    assert "朱元璋以216.5列第1" in text
    assert "A、B、C保留100/60/80原始量尺，分别折算为130/40/70计入" in text
    assert "C有6人因创业军事证据缺口采用保守值" in text
    assert "正式总表另有54人标记为证据下限" in text
    assert "109名非奠基者属于第一项不适用，不是第一项零分" in text
    assert "朱元璋以214.8居首" not in text


def test_first_item_formal_total_uses_a130_b40_c70() -> None:
    payload = json.loads(FORMAL_PATH.read_text(encoding="utf-8"))
    assert payload["axis_weighting"]["formal_weights"] == {
        "A": 130.0,
        "B": 40.0,
        "C": 70.0,
    }
    eligible = [row for row in payload["records"] if row["score_applicable"]]
    def weighted(raw: float, weight: int, raw_max: int) -> float:
        value = Decimal(str(raw)) * Decimal(weight) / Decimal(raw_max)
        return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

    for row in eligible:
        assert row["A_weighted_points"] == weighted(row["A_score_points"], 130, 100)
        assert row["B_weighted_points"] == weighted(row["B_score_points"], 40, 60)
        assert row["C_weighted_points"] == weighted(row["C_score_points"], 70, 80)
        assert row["first_item_score_points"] == float(
            sum(
                (
                    Decimal(str(row["A_weighted_points"])),
                    Decimal(str(row["B_weighted_points"])),
                    Decimal(str(row["C_weighted_points"])),
                ),
                start=Decimal("0"),
            ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        )
    assert [(row["ruler_name"], row["first_item_score_points"]) for row in eligible[:3]] == [
        ("朱元璋", 216.5),
        ("刘秀", 210.9),
        ("李世民", 204.3),
    ]


def test_first_item_weight_change_is_bounded_across_full_pool() -> None:
    payload = json.loads(FORMAL_PATH.read_text(encoding="utf-8"))
    eligible = [row for row in payload["records"] if row["score_applicable"]]
    old_order = sorted(
        eligible,
        key=lambda row: (
            -round(
                row["A_score_points"]
                + row["B_score_points"]
                + row["C_score_points"],
                1,
            ),
            row["ruler_name"],
        ),
    )
    old_ranks: dict[str, int] = {}
    previous_score: float | None = None
    current_rank = 0
    for position, row in enumerate(old_order, start=1):
        score = round(
            row["A_score_points"] + row["B_score_points"] + row["C_score_points"],
            1,
        )
        if score != previous_score:
            current_rank = position
            previous_score = score
        old_ranks[row["ruler_name"]] = current_rank
    assert [row["ruler_name"] for row in old_order[:4]] == [
        "朱元璋",
        "刘秀",
        "李世民",
        "刘邦",
    ]
    assert [row["ruler_name"] for row in eligible[:4]] == [
        "朱元璋",
        "刘秀",
        "李世民",
        "刘邦",
    ]
    assert max(
        abs(old_ranks[row["ruler_name"]] - row["canonical_rank"])
        for row in eligible
    ) == 7
