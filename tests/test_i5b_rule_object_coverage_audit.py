from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_rule_object_coverage_audit.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_rule_object_coverage_audit_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def row(name: str, *, has_rule: bool, obj_type: str = "person", talent_quality: str = "重要人才") -> dict[str, object]:
    seed = sum(ord(char) for char in name)
    return {
        "emperor": "测试帝",
        "emp_obj_id": seed,
        "obj_id": seed * 10,
        "obj_name": name,
        "obj_type": obj_type,
        "has_rule": has_rule,
        "attrs": [{"attr_code": "talent_quality", "value_text": talent_quality}],
        "i5b_obj_srcs": [],
    }


def test_report_flags_emp_objs_missing_target_rule() -> None:
    tool = load_tool()

    report = tool.build_audit_report(
        rule_code="delegation",
        emp_object_rows={
            "测试帝": [
                row("甲", has_rule=True, talent_quality="历史级人才"),
                row("乙", has_rule=False, talent_quality="顶级人才"),
                row("丙", has_rule=False, obj_type="event", talent_quality=""),
            ]
        },
    )
    markdown = tool.render_markdown(report)

    assert report["ok"] is False
    assert report["rows"][0]["candidate_count"] == 3
    assert report["rows"][0]["current_count"] == 1
    assert [item["obj_name"] for item in report["rows"][0]["missing"]] == ["乙", "丙"]
    assert "乙（person/顶级人才）" in markdown
    assert "丙（event）" in markdown


def test_report_allows_reviewed_missing_objects() -> None:
    tool = load_tool()

    report = tool.build_audit_report(
        rule_code="team_building",
        accepted_missing=tool.parse_accepted_missing(("测试帝:乙",)),
        emp_object_rows={"测试帝": [row("甲", has_rule=True), row("乙", has_rule=False)]},
    )

    assert report["ok"] is True
    assert report["rows"][0]["missing"] == []
    assert [item["obj_name"] for item in report["rows"][0]["accepted_missing"]] == ["乙"]


def test_report_can_filter_by_object_type_and_required_attr() -> None:
    tool = load_tool()

    report = tool.build_audit_report(
        rule_code="team_building",
        obj_types=("person",),
        require_attrs=("talent_quality",),
        emp_object_rows={
            "测试帝": [
                row("甲", has_rule=True),
                row("乙", has_rule=False, obj_type="event"),
                {
                    "emperor": "测试帝",
                    "emp_obj_id": 3,
                    "obj_id": 30,
                    "obj_name": "丙",
                    "obj_type": "person",
                    "has_rule": False,
                    "attrs": [],
                },
            ]
        },
    )

    assert report["ok"] is True
    assert report["rows"][0]["candidate_count"] == 1
    assert [item["obj_name"] for item in report["rows"][0]["current"]] == ["甲"]


def test_team_building_coverage_uses_calc_detail_components() -> None:
    tool = load_tool()
    emp_object_rows = {
        "测试帝": [
            row("甲", has_rule=False),
            row("乙", has_rule=False),
        ]
    }

    tool.apply_team_building_calc_detail_coverage(
        emp_object_rows,
        cluster_rows={
            ("测试帝", "team_building"): {
                "calc_detail": {
                        "team_quality_components": [
                            {"obj_id": sum(ord(char) for char in "甲") * 10},
                        ]
                }
            }
        },
    )
    report = tool.build_audit_report(
        rule_code="team_building",
        emp_object_rows=emp_object_rows,
    )

    assert [item["obj_name"] for item in report["rows"][0]["current"]] == ["甲"]
    assert [item["obj_name"] for item in report["rows"][0]["missing"]] == ["乙"]
