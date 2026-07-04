from __future__ import annotations

from scripts.dev import i5b_finite_value_audit as audit


def test_audit_flags_period_aliases_as_errors() -> None:
    issues = audit.audit_value_rows("raw_objs.period", [{"value": "Qing", "count": 2}])

    assert issues == [
        {
            "field": "raw_objs.period",
            "value": "Qing",
            "normalized": "清",
            "count": 2,
            "severity": "error",
            "status": "alias_value",
        }
    ]


def test_audit_flags_unknown_attr_direction_subitem_and_rule_values() -> None:
    assert audit.audit_value_rows("obj_attrs.attr_code", [{"value": "free_text_level", "count": 1}])[0]["status"] == "non_canonical_value"
    assert audit.audit_value_rows("obj_srcs.direction", [{"value": "maybe", "count": 1}])[0]["status"] == "non_canonical_value"
    assert audit.audit_value_rows("emp_objs.subitem", [{"value": "第五项C", "count": 1}])[0]["status"] == "non_canonical_value"
    assert audit.audit_value_rows("eval_rules.rule_code", [{"value": "talent", "count": 1}])[0]["status"] == "non_canonical_value"


def test_build_report_flags_duplicate_emperor_names() -> None:
    report = audit.build_report_from_snapshots(
        {
            "emps.period": [{"value": "清", "count": 1}],
            "raw_objs.period": [],
            "obj_attrs.region": [],
            "obj_attrs.attr_code": [{"value": "talent_quality", "count": 1}],
            "obj_attrs.talent_quality": [],
            "obj_srcs.direction": [{"value": "positive", "count": 3}],
            "emp_objs.subitem": [{"value": "第五项B", "count": 3}],
            "eval_rules.rule_code": [{"value": "team_building", "count": 1}],
        },
        duplicate_emps=[{"name": "弘历", "count": 2, "ids": [111, 213], "periods": ["清", "Qing"]}],
    )

    assert report["ok"] is False
    assert report["error_count"] == 1
    assert report["issues"][0]["status"] == "duplicate_emperor_name"


def test_audit_flags_normalized_emperor_key_collisions() -> None:
    issues = audit.audit_normalized_emperor_keys(
        [
            {"id": 1, "period": "Qing", "name": "玄烨"},
            {"id": 2, "period": "清", "name": "玄烨"},
        ]
    )

    assert issues == [
        {
            "field": "emps.normalized_period_name",
            "value": "玄烨",
            "normalized": "清/玄烨",
            "count": 2,
            "ids": [1, 2],
            "periods": ["Qing", "清"],
            "severity": "error",
            "status": "normalized_key_collision",
        }
    ]


def test_build_report_flags_normalized_raw_object_key_collisions() -> None:
    report = audit.build_report_from_snapshots(
        {
            "emps.period": [],
            "raw_objs.period": [{"value": "Ming", "count": 1}, {"value": "明", "count": 1}],
            "obj_attrs.region": [],
            "obj_attrs.attr_code": [],
            "obj_attrs.talent_quality": [],
            "obj_srcs.direction": [],
            "emp_objs.subitem": [],
            "eval_rules.rule_code": [],
        },
        normalized_key_rows={
            "raw_objs": [
                {"id": 1518, "obj_type": "person", "period": "明", "name": "杨士奇"},
                {"id": 1649, "obj_type": "person", "period": "Ming", "name": "杨士奇"},
            ],
        },
    )

    statuses = [issue["status"] for issue in report["issues"]]
    assert "alias_value" in statuses
    assert "normalized_key_collision" in statuses
