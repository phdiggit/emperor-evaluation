"""M5 text responsibilities and live source/view contracts, without frozen rulings."""
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.formal_json_store import M5_SCHEMA, load_json, write_json
from emperor_v4.evaluation.profile_m5 import SCOPE_GUIDE, render, validate_text_fields, verify


def sample():
    return {
        "ruler_id": "synthetic-controller",
        "typical_pattern": "给前线与运输中心配置实际职责。",
        "counterpattern": "资源冲突出现后仍需本人临时协调。",
        "grade_basis": "两个中心在相互依赖的任务中可以运行。",
        "position_basis": "同一任务内有反馈，但跨任务迁移尚未充分观察。",
        "limitations": ["运输负责人的正常退出和替补过程未记录。"],
    }


def test_distinct_field_responsibilities_are_allowed():
    validate_text_fields(sample())


@pytest.mark.parametrize("field,value", [
    ("counterpattern", " "), ("limitations", []),
    ("limitations", "not a list"), ("limitations", [" "]),
])
def test_rejects_missing_text_and_invalid_limitations(field, value):
    row = sample()
    row[field] = value
    with pytest.raises(ValueError):
        validate_text_fields(row)


def test_current_m5_records_match_current_pool_and_reading_view():
    verify(Path(__file__).resolve().parents[1])


def test_m5_shard_shares_only_equal_fields_and_keeps_source_order(tmp_path):
    path = tmp_path / "m5.json"
    prose = "前线与运输分担任务。"
    refs = ["z.json#ruler_id=A", "a.json#ruler_id=A", "z.json#ruler_id=A"]
    payload = {
        "schema_version": M5_SCHEMA,
        "records": [
            {"ruler_id": "A", "polity": "合成朝", "source_refs": refs, "search_scope": list(refs),
             "parent_chains": [
                 {"parent_id": "P1", "process_narrative": prose, "basis": prose},
                 {"parent_id": "P2", "process_narrative": prose},
                 {"parent_id": "P3", "process_narrative": prose, "basis": "仅限前线交付。"},
             ]},
            {"ruler_id": "B", "polity": "合成朝", "source_refs": refs, "search_scope": refs[:1]},
        ],
    }
    write_json(path, payload, ruler_polities={}, route=True)
    shard = path.with_suffix("") / "合成朝.json"
    raw = json.loads(shard.read_bytes())
    packed = raw["collections"]["records"]["records"]
    assert packed[0]["search_scope"] == {"same_as": "source_refs"}
    assert packed[0]["parent_chains"][0]["basis"] == {"same_as": "process_narrative"}
    assert load_json(path, polities=["合成朝"]) == payload
    direct = load_json(shard)["collections"]["records"]["records"]
    assert direct == payload["records"]
    direct[0]["search_scope"].append("other.json#ruler_id=A")
    assert direct[0]["source_refs"] == refs

    packed[0]["parent_chains"][0].pop("process_narrative")
    shard.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="字段引用无效: P1/basis"):
        load_json(shard)


def test_reading_view_keeps_later_process_paragraphs_and_counter_boundary():
    common = '只取多责任中心的任务、权责资源、协调监督与替补过程；C3个人识配、C4长期结构、B1运行结果不转档。'
    specific = common + '此案的粮运只覆盖西线。'
    row = {
        **sample(), 'ruler_name': '合成对象', 'polity': '合成政体',
        'axis_grade': 'G3', 'position': 'MID', 'radar_value': 65,
        'axis_evidence_level': 'E2', 'confidence': 'MEDIUM',
        'output_mode': 'BOUNDED_PROFILE', 'score_status': 'FINAL',
        'representative_parent_ids': ['synthetic-process', 'synthetic-transfer'],
        'parent_chains': [{
            'parent_id': 'synthetic-process', 'title': '前线与运输的职责接续',
            'process_narrative': '前线与运输分担任务。\n故障后调整权限，运输恢复交付。',
            'attribution_basis': '只评价实际权限内的安排。',
            'secondary_projection_reason': specific,
        }, {
            'parent_id': 'synthetic-transfer', 'title': '转交督运职责',
            'process_narrative': '新任督运官接收账册。',
            'attribution_basis': '留任与交接有各自的责任人。',
            'secondary_projection_reason': common,
        }], 'source_refs': ['docs/synthetic.json'],
        'historical_source_descriptions': ['合成来源说明'],
    }
    text = render({'records': [row]})
    assert '故障后调整权限，运输恢复交付。' in text
    assert row['counterpattern'] in text
    assert text.count(SCOPE_GUIDE) == 1
    assert text.count('[查看组织执行的通用评价范围](#m5-scope-guide)') == 1
    assert specific in text and text.count(common) == 1
    assert '新任督运官接收账册。' in text
