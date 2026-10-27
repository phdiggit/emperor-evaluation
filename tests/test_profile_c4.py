from copy import deepcopy

import pytest

from emperor_v4.evaluation.profile_c4 import render, validate_decision


def decision():
    return {
        "applicability": {"status": "APPLICABLE"},
        "axis_grade": "G3",
        "position": "MID",
        "score_100": 65,
        "radar_value": 65,
        "axis_evidence_level": "E2",
    }


def test_c4_projection_rejects_independent_score_change():
    row = decision()
    validate_decision(row)
    row["score_100"] = 66
    with pytest.raises(ValueError, match="不同值"):
        validate_decision(row)


def test_not_applicable_is_null_not_zero():
    row = decision()
    row.update(
        applicability={"status": "NOT_APPLICABLE", "basis": "无真实结构选择权"},
        axis_grade=None,
        position=None,
        score_100=None,
        radar_value=None,
    )
    validate_decision(row)
    invalid = deepcopy(row)
    invalid["radar_value"] = 0
    with pytest.raises(ValueError, match="不适用"):
        validate_decision(invalid)


def test_g5_requires_documented_magnitude_review():
    row = decision()
    row.update(axis_grade="G5", position="LOW", score_100=91, radar_value=91)
    with pytest.raises(ValueError, match="架构量级"):
        validate_decision(row)


def test_g5_single_integrated_am4_needs_no_second_am3():
    row = decision()
    row.update(axis_grade="G5", position="LOW", score_100=91, radar_value=91)
    row["architecture_review"] = {
        "magnitude": "AM4",
        "basis": "合成例：三个核心功能在共同治理逻辑下重写并运行。",
        "integrated_architecture_policy": "单组一体化架构，不拆分补票。",
    }
    validate_decision(row)


def test_reader_keeps_all_design_processes_and_source_limits():
    row = decision()
    row.update(ruler_id='synthetic', ruler_name='合成例', typical_pattern='局部制度调整。',
               grade_basis='依据已观察设计判断。', position_basis='长期复验有限。',
               counterpattern='机关仍可继续工作。', limitations=['只限区域制度。'],
               confidence='MEDIUM', applicability={'status': 'APPLICABLE', 'basis': '有实际选择。'},
               source_refs=['docs/synthetic.md'], representative_parent_ids=['selected'])
    long_body = '具体的制度规则和运行结果。' * 50
    row['parent_chains'] = [
        dict(parent_id='selected', title='已选局部设计', mechanism=long_body, direction='POSITIVE',
             attribution='本人选择，臣僚执行。', source_refs=['docs/synthetic.md']),
        dict(parent_id='extra', title='另一条适用边界', mechanism='既有制度延续不算原创。',
             interfaces=['人员归属', '资源核算'], direction='MIXED', attribution='前制。',
             source_refs=['docs/boundary.md'], source_review=[dict(
                 source_title='合成来源', source_url='https://example.org/source',
                 passage_locator='具体章节', adopted_fact='规则实际实施。',
                 counterevidence='存在地区差异。', limitation='未覆盖长期。')]),
    ]
    before = deepcopy(row)
    text = render({'records': [row]})
    assert long_body in text
    for value in ('既有制度延续不算原创。', '人员归属', '资源核算', '具体章节',
                  '存在地区差异。', '未覆盖长期。', '机关仍可继续工作。'):
        assert value in text
    assert '……（节选' not in text
    assert row == before
