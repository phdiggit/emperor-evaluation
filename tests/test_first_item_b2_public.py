from pathlib import Path

import pytest

from emperor_v4.evaluation.first_item_b2_public import project_b2, DIMENSIONS

ROOT = Path(__file__).resolve().parents[1]


def synthetic_fields(levels=(2, 3, 1)):
    fields = {'公开阅读问题':'前后方怎样分工？', '公开阅读正文':'主将留守后方，另一位主责承担前线任务。',
              '评价窗口':'建基到初始任务完成。', '本人控制链':'本人授权后方与前线分别行动。',
              'B2结算':f'{sum(levels)*2}/30'}
    for (field, _), level in zip(DIMENSIONS, levels):
        fields[field] = f'L{level}。具名主责获得任务与权限并有实际交付。'
    return fields


def test_project_uses_declared_prose_and_contract_grade_mapping():
    fields = synthetic_fields()
    result = project_b2(fields, method='三项分别裁档，按固定表相加。')
    assert result['public_story'] == fields['公开阅读正文']
    assert [d['points'] for d in result['dimensions']] == [4, 6, 2]
    assert result['total_points'] == 12


@pytest.mark.parametrize('field', ['公开阅读问题','公开阅读正文','评价窗口','本人控制链','并行执行'])
def test_missing_authority_fails_closed(field):
    fields = synthetic_fields(); fields.pop(field)
    with pytest.raises(ValueError):
        project_b2(fields, method='逐项裁档。')


def test_inconsistent_score_and_untranslated_prose_are_rejected():
    fields = synthetic_fields(); fields['B2结算'] = '30/30'
    with pytest.raises(ValueError, match='不同值'):
        project_b2(fields, method='逐项裁档。')
    fields = synthetic_fields(); fields['公开阅读正文'] = 'UNKNOWN'
    with pytest.raises(ValueError, match='未转述'):
        project_b2(fields, method='逐项裁档。')
