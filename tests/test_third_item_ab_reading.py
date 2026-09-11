from copy import deepcopy

from emperor_v4.evaluation.third_item_a_scoring import calculate_a_axis
from emperor_v4.evaluation.third_item_ab_reading import a_calculation, prose, render_person
from emperor_v4.evaluation.third_item_current_settlement import CONSTRUCTION_BASE_POINTS


def axis():
    value = {
        'start_grade': 4, 'end_grade': 4, 'objective_delta': 0,
        'attributable_delta': 0, 'improvement_step_credits': [],
        'maintenance_bonus': 12, 'negative_adjustment': 10,
        'reversal_penalty': 10, 'reversal_basis': '另一方向的主要门户丧失。',
        'within_band_deterioration_penalty': 5,
        'settlement_type_label': '档内结构改善型',
        'within_band_structure_improvement': {
            'improvement_level': 'DECISIVE', 'attribution_credit': .5,
            'entry_structure': '接手时前沿缺少联络。',
            'handover_structure': '交班时新防线已能协同。',
            'level_basis': '关键网络形成。',
            'attribution_basis': '本人和地方统帅共同形成结果。',
        },
    }
    value.update(calculate_a_axis('A2', value, structure_credit=CONSTRUCTION_BASE_POINTS['DECISIVE']*.5))
    return value


def test_calculation_shows_actual_special_max_and_keeps_loss():
    a = axis()
    text = a_calculation(a)
    assert f"独立建设{CONSTRUCTION_BASE_POINTS['DECISIVE']*.5*.6:g}" in text
    assert '压力保全' not in text
    assert '－负向调整6' in text
    assert f"{a['axis_points']:.2f}分" in text


def test_calculation_explains_clipped_result_instead_of_false_equality():
    a = axis()
    a['negative_adjustment'] = 90
    a.update(calculate_a_axis('A2', a, structure_credit=CONSTRUCTION_BASE_POINTS['DECISIVE']*.5))
    assert '按0—60分范围限制后' in a_calculation(a)
    assert f"{a['axis_points']:.2f}分" in a_calculation(a)


def test_prose_deduplicates_only_identical_clauses_and_keeps_opposite_states():
    result = prose('接手时门户可守。交班时门户失守。', '接手时门户可守。')
    assert result == '接手时门户可守。交班时门户失守。'


def test_person_render_is_read_only_and_keeps_decision_boundaries():
    row = {
        'ruler_name': '合成主体', 'A120_score_points': 0, 'B80_score_points': 0,
        'A120_axis_adjudications': {'A2': axis(), 'A1': axis()},
        'axes': {name: {'score_rate': 0, 'reason': '该方向的原始事实。'} for name in ('A1', 'A2', 'B1', 'B2', 'B4')},
        'B80_adjudication': {f'adjudicated_{name}_rate': 0 for name in ('B1', 'B2', 'B4')},
        'control_contribution_type': 'INHERITED_ONLY',
    }
    row['axes']['B4']['maturity_review'] = {
        'status': 'EVIDENCE_GAP', 'basis': '仍需本任窗口的接防证据。',
        'source_refs': ['synthetic-source'],
    }
    before = deepcopy(row)
    text = '\n'.join(render_person(row, b_basis=lambda *_: '无本人控制成果。',
        b_grade=lambda *_: '', b_regions=lambda *_: '控制规模净变化区域：无', depth_lines=lambda *_: []))
    assert row == before
    assert text.index('| A1 ') < text.index('| A2 ')
    assert '另一方向的主要门户丧失' in text.split('<details>')[0]
    assert text.count('<details>') == text.count('</details>') == 1
    assert '仅继承存量，不计本人控制贡献' in text
    assert '成熟度待补证：现值暂留，尚未通过边界复核' in text
    assert '仍需本任窗口的接防证据' in text
