from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_object_pool_detail.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_object_pool_detail_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_detail_report_groups_object_rules_and_materials() -> None:
    tool = load_tool()
    rows_by_emperor = {
        "测试帝": [
            {
                "emperor": "测试帝",
                "emp_obj_id": 10,
                "obj_id": 20,
                "obj_name": "甲臣",
                "obj_type": "person",
                "obj_period": "唐",
                "obj_note": "身份说明",
                "emp_obj_note": "皇帝语境说明",
                "attrs": [
                    {"attr_code": "talent_quality", "value_text": "顶级人才", "value_num": None, "note": "审定"},
                    {"attr_code": "talent_quality", "value_text": "顶级人才", "value_num": None, "note": "审定"},
                ],
                "rule_links": [
                    {
                        "obj_src_id": 101,
                        "rule_code": "talent_discovery",
                        "direction": "positive",
                        "src_key": "SRC-1",
                        "source_title": "旧书",
                        "locator": "卷一",
                        "note": "拔擢甲臣",
                    },
                    {
                        "obj_src_id": 102,
                        "rule_code": "delegation",
                        "direction": "positive",
                        "src_key": "SRC-2",
                        "source_title": "新书",
                        "locator": "卷二",
                        "note": "授权甲臣",
                    },
                ],
            }
        ]
    }

    report = tool.build_detail_report(emperors=("测试帝",), rows_by_emperor=rows_by_emperor)
    markdown = tool.render_markdown(report)

    emperor = report["emperors"][0]
    assert emperor["object_count"] == 1
    assert emperor["rule_count"] == 2
    assert emperor["material_count"] == 2
    obj = emperor["objects"][0]
    assert obj["attrs"] == [
        {
            "attr_code": "talent_quality",
            "value_text": "顶级人才",
            "value_num": None,
            "value_unit": None,
            "confidence": None,
            "note": "审定",
        }
    ]
    assert [rule["rule_code"] for rule in obj["rules"]] == ["delegation", "talent_discovery"]
    assert "| 甲臣 `obj:20` `emp_obj:10` | person/唐 | talent_quality=顶级人才 |" in markdown
    assert "合理授权 (`delegation`), materials=1" in markdown
    assert "#101 `positive` SRC-1 卷一: 拔擢甲臣" in markdown


def test_detail_report_keeps_missing_emperor_section() -> None:
    tool = load_tool()

    report = tool.build_detail_report(emperors=("空帝",), rows_by_emperor={})

    assert report["missing_emperors"] == ["空帝"]
    assert report["emperors"][0]["object_count"] == 0
    assert "| - | - | - | - |" in tool.render_markdown(report)


def test_detail_report_filters_rules_without_marking_existing_emperor_missing() -> None:
    tool = load_tool()
    rows_by_emperor = {
        "测试帝": [
            {
                "emperor": "测试帝",
                "emp_obj_id": 10,
                "obj_id": 20,
                "obj_name": "甲臣",
                "obj_type": "person",
                "obj_period": "唐",
                "attrs": [],
                "rule_links": [
                    {
                        "obj_src_id": 101,
                        "rule_code": "talent_discovery",
                        "direction": "positive",
                        "src_key": "SRC-1",
                        "note": "发现甲臣",
                    },
                    {
                        "obj_src_id": 102,
                        "rule_code": "delegation",
                        "direction": "positive",
                        "src_key": "SRC-2",
                        "note": "授权甲臣",
                    },
                ],
            },
            {
                "emperor": "测试帝",
                "emp_obj_id": 11,
                "obj_id": 21,
                "obj_name": "乙臣",
                "obj_type": "person",
                "obj_period": "唐",
                "attrs": [],
                "rule_links": [
                    {
                        "obj_src_id": 103,
                        "rule_code": "team_building",
                        "direction": "positive",
                        "src_key": "SRC-3",
                        "note": "团队成员",
                    }
                ],
            },
        ]
    }

    report = tool.build_detail_report(
        emperors=("测试帝",),
        rows_by_emperor=rows_by_emperor,
        rule_codes=("delegation",),
    )
    markdown = tool.render_markdown(report)

    assert report["missing_emperors"] == []
    assert report["rule_filter"] == ["delegation"]
    assert report["emperors"][0]["object_count"] == 1
    assert report["emperors"][0]["objects"][0]["obj_name"] == "甲臣"
    assert report["emperors"][0]["objects"][0]["material_count"] == 1
    assert "合理授权(`delegation`)" in markdown
    assert "发现人才" not in markdown
    assert "乙臣" not in markdown


def test_object_report_lists_bindings_rules_and_scores() -> None:
    tool = load_tool()

    report = tool.build_object_report(
        objects=("甲臣",),
        object_rows=[
            {
                "obj_id": 20,
                "obj_name": "甲臣",
                "obj_type": "person",
                "obj_period": "唐",
                "obj_note": "身份说明",
                "attrs": [{"attr_code": "talent_quality", "value_text": "顶级人才"}],
            }
        ],
        link_rows=[
            {
                "obj_id": 20,
                "emp_id": 1,
                "emperor": "测试帝",
                "emp_obj_id": 10,
                "emp_obj_note": "皇帝语境说明",
                "obj_src_id": 101,
                "rule_code": "delegation",
                "direction": "positive",
                "src_key": "SRC-1",
                "locator": "卷一",
                "note": "授权甲臣",
                "score_material": {
                    "obj_src_id": 101,
                    "side": "positive",
                    "raw_score": "1.500",
                    "abs_score": "1.500",
                    "factor_values": {"authorization_intensity": "1.5"},
                    "factor_refs": {"authorization_intensity": {"label": "高"}},
                },
            },
            {
                "obj_id": 20,
                "emp_id": 2,
                "emperor": "参照帝",
                "emp_obj_id": 11,
                "obj_src_id": 102,
                "rule_code": "team_building",
                "direction": "positive",
                "src_key": "SRC-2",
                "note": "只作覆盖材料",
                "covered_material_ids": [102],
            },
        ],
    )
    markdown = tool.render_markdown(report)

    assert report["report_type"] == "object_binding_score"
    assert report["missing_objects"] == []
    obj = report["objects"][0]
    assert obj["binding_count"] == 2
    assert obj["rule_count"] == 2
    assert obj["scored_material_count"] == 1
    scored_rule = obj["bindings"][1]["rules"][0]
    assert scored_rule["rule_code"] == "delegation"
    assert scored_rule["raw_score_total"] == "1.500"
    assert scored_rule["abs_score_total"] == "1.500"
    assert "测试帝" in markdown
    assert "合理授权(`delegation`)" in markdown
    assert "#101 `scored` `positive` raw=1.500 abs=1.500 SRC-1 卷一: 授权甲臣" in markdown
    assert "#102 `covered_unscored` `positive` raw=- abs=- SRC-2: 只作覆盖材料" in markdown


def test_object_report_records_missing_object_name() -> None:
    tool = load_tool()

    report = tool.build_object_report(objects=("不存在",), object_rows=[], link_rows=[])

    assert report["missing_objects"] == ["不存在"]
    assert report["objects"] == []
