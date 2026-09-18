"""First-item A public prose is formal, complete, and projected at build time."""

import json
from pathlib import Path

from emperor_v4.evaluation.first_item_public_outcomes import (
    PUBLIC_FIELDS,
    load_first_item_public_outcomes,
    public_outcome_for_name,
)
from reader.validate_first_item_docs import parse_people


ROOT = Path(__file__).resolve().parents[1]
A_SOURCE = ROOT / "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/01-第一项A统一主链客观贡献正式结算.md"


def test_formal_a_public_outcomes_cover_the_current_a_source():
    source_names = set(parse_people(A_SOURCE))
    outcomes = load_first_item_public_outcomes(ROOT)

    assert set(outcomes) == source_names
    assert all(set(PUBLIC_FIELDS) <= set(record) for record in outcomes.values())
    assert all(
        isinstance(record["public_share_percent"], (int, float))
        and 0 <= record["public_share_percent"] <= 100
        for record in outcomes.values()
    )
    assert all(
        all(isinstance(record[field], str) and record[field].strip() for field in PUBLIC_FIELDS)
        for record in outcomes.values()
    )


def test_reader_first_item_sources_no_longer_contain_known_person_specific_outcome_rewrites():
    source = (ROOT / "reader/first-item-reading.js").read_text(encoding="utf-8")
    for phrase in (
        "从女真整合到1683核心统一一次结算",
        "郭威取得中原核心、柴荣续接淮南及北方阶段成果",
        "李克用前置基盘、李存勖灭梁主体、李嗣源独立方面贡献",
        "总池封顶100；仅计元统一主链直接继承成果",
    ):
        assert phrase not in source
    assert "reader_public_outcome" in source


def test_generated_person_detail_contains_formal_public_outcome():
    outcomes = load_first_item_public_outcomes(ROOT)
    candidates = []
    for person_path in (ROOT / "reader/data/people").glob("*.json"):
        record = json.loads(person_path.read_text(encoding="utf-8"))["record"]
        for item in (record.get("net") or {}).get("component_details", {}).get("first", []):
            if item.get("label") == "A统一贡献" and "reader_public_outcome" in item:
                candidates.append((record["ruler_name"], item))

    assert candidates
    for name, item in candidates:
        assert item["reader_public_outcome"] == public_outcome_for_name(outcomes, name)
