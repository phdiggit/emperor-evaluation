from __future__ import annotations

from argparse import Namespace

from scripts.dev import i5b_fact_relation_candidate_sync as sync


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


def test_resolve_rule_codes_defaults_to_high_risk_rules() -> None:
    args = Namespace(rule_code=[], all_rules=False)

    assert sync.resolve_rule_codes(args) == ("anti_nepotism", "tolerate_talent")


def test_relation_candidate_requires_person_subject() -> None:
    options = {("anti_nepotism", "favorite_beneficiary", "person"): _option()}

    candidate, reason = sync.relation_candidate(_row(scored_obj_type="mechanism"), options)

    assert candidate is None
    assert reason == "non_person"


def test_relation_candidate_requires_catalog_row() -> None:
    candidate, reason = sync.relation_candidate(_row(scoring_role="mechanism_context"), {})

    assert candidate is None
    assert reason == "no_catalog"


def test_relation_candidate_rejects_direction_mismatch() -> None:
    options = {("anti_nepotism", "favorite_beneficiary", "person"): _option()}

    candidate, reason = sync.relation_candidate(_row(direction="positive"), options)

    assert candidate is None
    assert reason == "direction_mismatch"


def test_relation_candidate_builds_fact_relation_values() -> None:
    options = {("anti_nepotism", "favorite_beneficiary", "person"): _option()}

    candidate, reason = sync.relation_candidate(_row(), options)

    assert reason == ""
    assert candidate is not None
    assert candidate["emp_id"] == 12
    assert candidate["item_code"] == "I5B"
    assert candidate["rule_code"] == "anti_nepotism"
    assert candidate["subject_obj_id"] == 801
    assert candidate["predicate"] == "favored_private_person"
    assert candidate["object_obj_id"] is None
    assert candidate["obj_src_id"] == 1635
    assert candidate["relation_role"] == "scored_candidate"
    assert candidate["review_status"] == "needs_review"
    assert candidate["review_note"] == ""
    assert candidate["note"] == ""


def test_update_relation_does_not_overwrite_human_notes() -> None:
    class FakeCursor:
        sql = ""
        params: tuple[object, ...] = ()

        def execute(self, sql: str, params: tuple[object, ...]) -> None:
            self.sql = sql
            self.params = params

    values = sync.relation_values(_row(), _option())
    cursor = FakeCursor()

    sync._update_relation(cursor, 42, values)

    assert "review_note =" not in cursor.sql
    assert "\n               note =" not in cursor.sql
    assert values["review_note"] not in cursor.params
    assert values["note"] not in cursor.params


def test_render_markdown_includes_audit_columns() -> None:
    text = sync.render_markdown(
        [
            sync.RelationSyncStats(
                emperor="武则天",
                rule_code="anti_nepotism",
                units_seen=5,
                person_units=5,
                relation_candidates=5,
                inserted=5,
                units_with_relation=5,
            )
        ],
        dry_run=False,
    )

    assert "# I5B 事实关系候选同步" in text
    assert "| 武则天 | anti_nepotism | 5 | 5 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 0 |" in text
    assert "- relation_candidates: `5`" in text
