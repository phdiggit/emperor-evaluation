from __future__ import annotations

from scripts.dev import i5b_fact_relation_candidate_sync as sync
from scripts.dev import i5b_fact_relation_gap_summary as tool


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "unit_id": 1,
        "emp_id": 12,
        "emperor": "武则天",
        "item_id": 5,
        "item_code": "I5B",
        "rule_id": 99,
        "rule_code": "anti_nepotism",
        "causal_chain_key": "i5b:anti_nepotism:obj_src:1635",
        "scored_obj_id": 801,
        "scored_obj_name": "张易之",
        "scored_obj_type": "person",
        "scored_obj_src_id": 1635,
        "doc_id": 77,
        "scoring_role": "favorite_beneficiary",
        "direction": "negative",
    }
    row.update(overrides)
    return row


def _option() -> sync.RelationOption:
    return sync.RelationOption(
        rule_code="anti_nepotism",
        scoring_role="favorite_beneficiary",
        predicate="favored_private_person",
        relation_role="scored_candidate",
        subject_obj_type="person",
        object_obj_type="",
        direction="negative",
        description="宠幸、近幸或私人偏好受益的具体人物。",
    )


def test_collect_gaps_reports_non_person_direction_and_missing_relation() -> None:
    options = {("anti_nepotism", "favorite_beneficiary", "person"): _option()}

    gaps = tool.collect_gaps(
        [
            _row(scored_obj_type="mechanism", scored_obj_name="酷吏罗织机制"),
            _row(direction="positive"),
            _row(scored_obj_name="张昌宗", scored_obj_src_id=1636),
        ],
        options,
        relation_exists=lambda _candidate: False,
    )
    summary = tool.build_gap_summary(gaps)

    assert summary["totals"]["total"] == 3
    assert summary["totals"]["non_person"] == 1
    assert summary["totals"]["direction_mismatch"] == 1
    assert summary["totals"]["missing_relation"] == 1
    text = tool.render_markdown(summary)
    assert "酷吏罗织机制" in text
    assert "missing_relation" in text


def test_collect_gaps_omits_existing_candidate_relation() -> None:
    options = {("anti_nepotism", "favorite_beneficiary", "person"): _option()}

    gaps = tool.collect_gaps([_row()], options, relation_exists=lambda _candidate: True)

    assert gaps == []
