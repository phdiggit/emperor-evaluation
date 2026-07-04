from __future__ import annotations

from scripts.dev import i5b_rule_evidence_unit_db_sync as sync


def _unit() -> dict[str, object]:
    return {
        "rule_code": "anti_nepotism",
        "causal_chain_key": "i5b:anti_nepotism:obj_src:1635",
        "direction": "negative",
        "scoring_role": "favorite_beneficiary",
        "score_mode": "shadow",
        "source_method": "candidate_from_calc_detail",
        "review_status": "needs_review",
        "review_note": "候选来自当前 calc_detail.materials；需人工复核。",
        "scored_obj": {
            "obj_id": 801,
            "name": "张易之",
            "obj_type": "person",
            "obj_src_id": 1635,
        },
        "members": [
            {
                "role": "source_context",
                "obj_id": 801,
                "name": "张易之",
                "obj_type": "person",
                "obj_src_id": 1636,
                "source_method": "candidate_from_calc_detail",
                "review_status": "needs_review",
            }
        ],
    }


def test_unit_db_values_keeps_candidate_notes_sparse() -> None:
    values = sync.unit_db_values(
        unit=_unit(),
        emp_id=1,
        item_id=5,
        rule_id=9,
        item_code="I5B",
    )

    assert values["emp_id"] == 1
    assert values["item_code"] == "I5B"
    assert values["rule_code"] == "anti_nepotism"
    assert values["scored_obj_id"] == 801
    assert values["scored_obj_src_id"] == 1635
    assert values["score_mode"] == "shadow"
    assert values["review_status"] == "needs_review"
    assert values["review_note"] == ""
    assert values["note"] == ""


def test_member_db_values_keeps_context_member_separate_from_scored_unit() -> None:
    member = _unit()["members"][0]
    assert isinstance(member, dict)

    values = sync.member_db_values(member=member, unit_id=42)

    assert values["unit_id"] == 42
    assert values["obj_id"] == 801
    assert values["obj_src_id"] == 1636
    assert values["member_role"] == "source_context"
    assert values["review_status"] == "needs_review"
    assert values["review_note"] == ""
    assert values["note"] == ""


def test_unit_and_member_updates_do_not_overwrite_human_notes() -> None:
    class FakeCursor:
        sql = ""
        params: tuple[object, ...] = ()

        def execute(self, sql: str, params: tuple[object, ...]) -> None:
            self.sql = sql
            self.params = params

    unit_values = sync.unit_db_values(unit=_unit(), emp_id=1, item_id=5, rule_id=9, item_code="I5B")
    unit_cursor = FakeCursor()
    sync._update_unit(unit_cursor, 42, unit_values)

    assert "review_note =" not in unit_cursor.sql
    assert "\n               note =" not in unit_cursor.sql
    assert unit_values["review_note"] not in unit_cursor.params
    assert unit_values["note"] not in unit_cursor.params

    member_values = sync.member_db_values(member=_unit()["members"][0], unit_id=42)  # type: ignore[index]
    member_cursor = FakeCursor()
    sync._update_member(member_cursor, 43, member_values)

    assert "review_note =" not in member_cursor.sql
    assert "\n               note =" not in member_cursor.sql
    assert member_values["review_note"] not in member_cursor.params
    assert member_values["note"] not in member_cursor.params


def test_sync_payload_dry_run_counts_without_db_writes() -> None:
    payload = {
        "emperor": "武则天",
        "item_code": "I5B",
        "units": [_unit()],
        "supporting_materials": [{"obj_src_id": 2000}],
        "preview": {"issue_count": 2, "has_blocking_issue": True},
    }

    stats = sync.sync_payload(cur=object(), payload=payload, dry_run=True)  # type: ignore[arg-type]

    assert stats.emperor == "武则天"
    assert stats.units_seen == 1
    assert stats.units_inserted == 0
    assert stats.members_seen == 1
    assert stats.supporting_unattached == 1
    assert stats.preview_issues == 2
    assert stats.preview_blocking is True


def test_payload_rule_codes_include_declared_rules_without_units() -> None:
    assert sync._payload_rule_codes({"rule_codes": ["anti_nepotism"]}, []) == ("anti_nepotism",)


def test_retire_stale_candidate_units_only_targets_candidate_rows() -> None:
    class FakeCursor:
        calls: list[tuple[str, tuple[object, ...]]] = []

        def __init__(self) -> None:
            self._fetches = [[(100,), (101,)], [(200,)]]

        def execute(self, sql: str, params: tuple[object, ...]) -> None:
            self.calls.append((sql, params))

        def fetchall(self) -> list[tuple[int]]:
            return self._fetches.pop(0)

    cursor = FakeCursor()

    retired_units, retired_members = sync._retire_stale_candidate_units(
        cursor,  # type: ignore[arg-type]
        emp_id=1,
        item_id=5,
        rule_ids={"tolerate_talent": 9},
        active_unit_ids=[42],
    )

    assert retired_units == 2
    assert retired_members == 1
    unit_sql, unit_params = cursor.calls[0]
    member_sql, member_params = cursor.calls[1]
    assert "source_method = %s::public.eval_source_method" in unit_sql
    assert "review_status = %s::public.eval_review_status" in unit_sql
    assert "not (id = any(%s))" in unit_sql
    assert "rule_code = any(%s)" in unit_sql
    assert unit_params[-3:] == ([9], ["tolerate_talent"], [42])
    assert "unit_id = any(%s)" in member_sql
    assert member_params[-1] == [100, 101]


def test_render_markdown_includes_totals() -> None:
    text = sync.render_markdown(
        [
            sync.SyncStats(
                emperor="武则天",
                units_seen=8,
                units_inserted=8,
                units_retired=1,
                members_seen=1,
                members_inserted=1,
                members_retired=1,
            )
        ],
        dry_run=False,
    )

    assert "# I5B 规则证据单元影子表同步" in text
    assert "| 武则天 | 8 | 8 | 0 | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 否 |" in text
    assert "- units_seen: `8`" in text
    assert "- units_retired: `1`" in text
    assert "- members_retired: `1`" in text
