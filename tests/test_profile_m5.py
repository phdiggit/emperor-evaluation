"""M5 text responsibilities and live source/view contracts, without frozen rulings."""
from pathlib import Path

import pytest

from emperor_v4.evaluation.profile_m5 import render, validate_text_fields, verify


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


def test_reading_view_keeps_later_process_paragraphs_and_counter_boundary():
    row = {
        **sample(), 'ruler_name': '合成对象', 'polity': '合成政体',
        'axis_grade': 'G3', 'position': 'MID', 'radar_value': 65,
        'axis_evidence_level': 'E2', 'confidence': 'MEDIUM',
        'output_mode': 'BOUNDED_PROFILE', 'score_status': 'FINAL',
        'representative_parent_ids': ['synthetic-process'],
        'parent_chains': [{
            'parent_id': 'synthetic-process', 'title': '前线与运输的职责接续',
            'process_narrative': '前线与运输分担任务。\n故障后调整权限，运输恢复交付。',
            'attribution_basis': '只评价实际权限内的安排。',
            'secondary_projection_reason': '不从运输成果推算组织档位。',
        }], 'source_refs': ['docs/synthetic.json'],
        'historical_source_descriptions': ['合成来源说明'],
    }
    text = render({'records': [row]})
    assert '故障后调整权限，运输恢复交付。' in text
    assert row['counterpattern'] in text
    assert row['parent_chains'][0]['secondary_projection_reason'] in text
