"""Authored reading survives projection; scoring is independent of prose."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_b1_settlement import (
    B1_PATH, _authored_public_text, _public_position_basis, _public_tags,
    _scoring_signature, refresh_b1_public_projection, validate_public_profile_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def test_refresh_preserves_authored_experience_responsibility_and_reason():
    source = load_json(ROOT / B1_PATH)
    before = _scoring_signature(source)
    result = refresh_b1_public_projection(deepcopy(source))
    assert _scoring_signature(result) == before
    for original, row in zip(source['records'], result['records']):
        for key in ('public_story', 'public_responsibility', 'public_adjudication_summary'):
            assert row[key] == original[key]
            assert _authored_public_text(row, key) == original[key]
        assert row['public_index_calculation'] == _public_position_basis(row)
        profiles = [p for key in ('M_positive_profile', 'M_mixed_profile', 'M_negative_profile') for p in row[key]]
        assert [(e['profile_id'], e['material_id'], e['public_basis']) for e in row['public_evidence_items']] == [
            (p['profile_id'], p['material_id'], p['adjudication_basis']) for p in profiles
        ]


@pytest.mark.parametrize('text', ['', '正式结算按独立行政运行链判断：正向 2 条、负向 0 条。', '逐字史料所载的制度安排。'])
def test_missing_or_count_template_cannot_replace_authored_reason(text):
    with pytest.raises(ValueError, match='公开正文'):
        _authored_public_text({'ruler_name': '合成对象', 'public_adjudication_summary': text}, 'public_adjudication_summary')


def test_counted_card_cannot_claim_it_is_background_only():
    source = load_json(ROOT / B1_PATH)
    profile = next(p for row in source['records'] for key in ('M_positive_profile', 'M_negative_profile') for p in row[key] if p['adjudication_status'] == 'COUNTED_INDEPENDENT')
    profile['adjudication_basis'] = '只作官僚治理制度背景，不直接计为交付结果。'
    with pytest.raises(ValueError, match='独立计入材料正文'):
        validate_public_profile_contract(source)


def test_index_math_uses_authored_position_and_grade_interval():
    row = {'grade':'G3', 'position':'middle', 'direction_index':62.5,
           'public_position_basis':'合成对象的职责覆盖和质量支持本档典型位置。'}
    text = _public_position_basis(row)
    assert row['public_position_basis'] in text and '余额' not in text
    assert '55+0.5×(69.9−55)=62.5/100' in text


def test_current_b1_validation_does_not_require_historical_batch_versions(monkeypatch):
    from emperor_v4.evaluation import formal_settlements

    original_load = formal_settlements.load_json
    source_path = (ROOT / B1_PATH).resolve()
    current = original_load(source_path)
    current.pop('review_material_absorption', None)
    for row in current['records']:
        row.pop('review_material_basis', None)

    def load_current(path, *args, **kwargs):
        return current if path.resolve() == source_path else original_load(path, *args, **kwargs)

    monkeypatch.setattr(formal_settlements, 'load_json', load_current)
    result = formal_settlements.verify_second_item_b1_snapshot(ROOT)
    assert result['record_count'] == len(current['records'])


def test_unscored_suggestion_cannot_publish_a_sustained_operation_badge():
    tags = _public_tags({'M':'M0', 'b1_role':'context', 'direction':'positive',
                         'result_closure':'sustained_or_systemic'}, 'ZERO_NET')
    assert '边界材料' in tags
    assert '正向' not in tags
    assert '持续或系统运行' not in tags


def test_every_ready_reader_record_projects_the_current_authored_fields_verbatim():
    source = {row['ruler_id']: row for row in load_json(ROOT / B1_PATH)['records']}
    records = [json.loads(path.read_text(encoding='utf-8')).get('record') for path in (ROOT / 'reader/data/people').glob('*.json')]
    ready = {row['ruler_id'] for row in records if row and row.get('settlement_readiness') == 'COMPOSITE_READY'}
    seen = set()
    for record in filter(None, records):
        for item in ((record.get('net') or {}).get('component_details') or {}).get('method', []):
            if item['label'] != 'B1官僚治理':
                continue
            row = source[record['ruler_id']]
            seen.add(record['ruler_id'])
            assert item['reader_confidence'] == row['confidence']
            assert item['reader_evidence_status'] == row['evidence_status']
            assert item['reader_grade_origin'] == row['grade_origin']
            for public, reader in (('public_story','reader_story'), ('public_responsibility','reader_responsibility'),
                                   ('public_adjudication_summary','reader_summary'), ('public_index_calculation','reader_index_calculation'),
                                   ('public_evidence_items','reader_public_evidence_items')):
                assert item[reader] == row[public]
    assert seen == ready and seen
