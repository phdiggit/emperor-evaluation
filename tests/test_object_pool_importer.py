from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
IMPORTER_PATH = ROOT / "scripts" / "dev" / "object_pool_importer.py"


def load_importer():
    spec = importlib.util.spec_from_file_location("object_pool_importer_under_test", IMPORTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_payload() -> dict:
    return {
        "item_code": "I5B",
        "subitem": "第五项B",
        "emperor": {
            "period": "东汉",
            "name": "刘秀",
            "title": "汉光武帝",
            "sort_no": 2,
            "note": "东汉开国皇帝，南阳蔡阳人；新莽末年起兵，后即帝位。",
        },
        "sources": [
            {
                "src_key": "SRC-HHS-J16-DENGYU-TEST",
                "title": "后汉书",
                "author": "范晔",
                "dynasty": "南朝宋",
                "volume": "卷十六",
                "locator": "邓禹传，刘秀延见甚欢段",
                "url": "https://example.invalid/houhanshu/16",
                "note": "邓禹少游学长安，与刘秀相识并受延见任用线回源。",
            }
        ],
        "objects": [
            {
                "obj_type": "person",
                "period": "东汉",
                "name": "邓禹",
                "note": "东汉开国功臣；《后汉书》邓禹传已回源，主要记录其少游长安、与刘秀相识并受延见任用。",
                "links": [
                    {
                        "src_key": "SRC-HHS-J16-DENGYU-TEST",
                        "rule_code": "talent_discovery",
                        "direction": "positive",
                        "note": "邓禹少游长安时与刘秀相识，后闻刘秀安集河北而来归，延见甚欢，可作为早期识才任用材料。",
                    }
                ],
            }
        ],
    }


def test_parse_payload_accepts_valid_payload() -> None:
    importer = load_importer()

    payload = importer.parse_payload(valid_payload())

    assert payload.emperor.name == "刘秀"
    assert payload.objects[0].name == "邓禹"
    assert payload.objects[0].links[0].rule_code == "talent_discovery"


def test_parse_payload_accepts_object_attrs() -> None:
    importer = load_importer()
    raw = valid_payload()
    raw["objects"][0]["attrs"] = [
        {
            "attr_code": "talent_quality",
            "src_key": "SRC-HHS-J16-DENGYU-TEST",
            "value_text": "顶级人才",
            "confidence": 0.85,
            "note": "邓禹为刘秀开国核心功臣，综合质量高。",
        }
    ]

    payload = importer.parse_payload(raw)

    attr = payload.objects[0].attrs[0]
    assert attr.attr_code == "talent_quality"
    assert attr.value_text == "顶级人才"
    assert attr.value_unit == ""
    assert attr.region == "东汉"
    assert attr.obj_name == "邓禹"


def test_parse_payload_rejects_object_attr_without_value() -> None:
    importer = load_importer()
    raw = valid_payload()
    raw["objects"][0]["attrs"] = [
        {
            "attr_code": "talent_quality",
            "src_key": "SRC-HHS-J16-DENGYU-TEST",
            "note": "缺少属性值。",
        }
    ]

    with pytest.raises(importer.ImportErrorWithContext, match="value_text or value_num"):
        importer.parse_payload(raw)


def test_parse_payload_rejects_object_attr_source_not_linked_on_object() -> None:
    importer = load_importer()
    raw = valid_payload()
    raw["sources"].append(
        {
            "src_key": "SRC-HHS-J16-OTHER-TEST",
            "title": "后汉书",
            "author": "范晔",
            "dynasty": "南朝宋",
            "volume": "卷十六",
            "locator": "其他段落",
            "url": "https://example.invalid/houhanshu/16-other",
            "note": "另一个史源。",
        }
    )
    raw["objects"][0]["attrs"] = [
        {
            "attr_code": "talent_quality",
            "src_key": "SRC-HHS-J16-OTHER-TEST",
            "value_text": "顶级人才",
            "note": "属性史源必须已经连到对象。",
        }
    ]

    with pytest.raises(importer.ImportErrorWithContext, match="attr source must also be linked"):
        importer.parse_payload(raw)


def test_parse_payload_rejects_raw_object_note_with_scoring_terms() -> None:
    importer = load_importer()
    raw = valid_payload()
    raw["objects"][0]["note"] = "东汉功臣；第五项B正向对象。"

    with pytest.raises(importer.ImportErrorWithContext, match="forbidden term"):
        importer.parse_payload(raw)


def test_parse_payload_rejects_object_without_source_links() -> None:
    importer = load_importer()
    raw = valid_payload()
    raw["objects"][0]["links"] = []

    with pytest.raises(importer.ImportErrorWithContext, match="at least one source link"):
        importer.parse_payload(raw)


def test_parse_payload_rejects_generic_obj_src_note() -> None:
    importer = load_importer()
    raw = valid_payload()
    raw["objects"][0]["links"][0]["note"] = "I5B回源关联：支撑规则维度，事实方向为正向。"

    with pytest.raises(importer.ImportErrorWithContext, match="forbidden term"):
        importer.parse_payload(raw)


def test_parse_payload_rejects_unknown_source_reference() -> None:
    importer = load_importer()
    raw = valid_payload()
    raw["objects"][0]["links"][0]["src_key"] = "SRC-MISSING"

    with pytest.raises(importer.ImportErrorWithContext, match="unknown src_key"):
        importer.parse_payload(raw)


def test_load_payloads_accepts_batch_shape(tmp_path: Path) -> None:
    importer = load_importer()
    path = tmp_path / "payloads.json"
    path.write_text(
        '{"payloads": [' + json.dumps(valid_payload(), ensure_ascii=False) + "]}",
        encoding="utf-8",
    )

    payloads = importer.load_payloads(path)

    assert len(payloads) == 1
    assert payloads[0].emperor.name == "刘秀"


def test_build_template_payload_from_profile_skips_adjacent_by_default() -> None:
    importer = load_importer()
    profile = {
        "person": "李隆基",
        "source_targets": ["旧唐书：玄宗本纪；姚崇传"],
        "query_bundles": ["李隆基 姚崇 旧唐书"],
        "object_layers": {
            "core_positive_objects": ["姚崇"],
            "negative_reversal_objects": ["安禄山"],
            "adjacent_split_objects": ["开元盛世"],
        },
    }

    template = importer.build_template_payload(profile)

    assert template["emperor"]["name"] == "李隆基"
    assert [item["name"] for item in template["objects"]] == ["姚崇", "安禄山"]
    assert template["objects"][0]["links"][0]["direction"] == "positive"
    assert template["objects"][1]["links"][0]["direction"] == "negative"


def test_upsert_obj_source_binds_emp_object_id() -> None:
    importer = load_importer()

    class FakeCursor:
        sql = ""
        params = ()

        def execute(self, sql, params):
            self.sql = sql
            self.params = params

        def fetchone(self):
            return (123,)

    cur = FakeCursor()
    link = importer.ObjectSourceLink(
        src_key="SRC-1",
        rule_code="talent_discovery",
        direction="positive",
        note="source note",
    )

    obj_src_id = importer._upsert_obj_source(
        cur,
        obj_id=11,
        emp_obj_id=22,
        doc_id=33,
        item_id=44,
        rule_id=55,
        link=link,
    )

    assert obj_src_id == 123
    assert "emp_obj_id" in cur.sql
    assert "on conflict (emp_obj_id, doc_id, item_id, rule_id, direction)" in cur.sql
    assert cur.params == (11, 22, 33, 44, 55, "positive", "source note")


def test_insert_object_attr_uses_source_and_object_link() -> None:
    importer = load_importer()

    class FakeCursor:
        sql = ""
        params = ()

        def execute(self, sql, params):
            self.sql = sql
            self.params = params

        def fetchone(self):
            return (456,)

    cur = FakeCursor()
    attr = importer.ObjectAttrRow(
        attr_code="talent_quality",
        src_key="SRC-1",
        value_text="顶级人才",
        value_num=None,
        value_unit="",
        period_start=None,
        period_end=None,
        region="东汉",
        confidence=0.85,
        note="source note",
        obj_name="邓禹",
    )

    attr_id = importer._insert_object_attr(cur, obj_id=11, doc_id=22, obj_src_id=33, attr=attr)

    assert attr_id == 456
    assert "insert into obj_attrs" in cur.sql
    assert cur.params == (
        11,
        "talent_quality",
        "顶级人才",
        None,
        "",
        None,
        None,
        "东汉",
        22,
        33,
        0.85,
        "source note",
        "邓禹",
    )
