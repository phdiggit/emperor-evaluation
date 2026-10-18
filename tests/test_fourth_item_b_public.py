"""Contract and public-projection behavior, with no fixed ruler judgments."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from emperor_v4.evaluation.fourth_item_b_public import SCHEMA, package_reading, axis_reading, verify_readings
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.third_fourth_item_public import FOURTH_PATH, _refresh_fourth, _signature

ROOT = Path(__file__).resolve().parents[1]


def synthetic_package():
    prose = {k:'独立构造的有限受教变化。' for k in ('title','story','baseline','responsibility','level_basis','coverage','duration','boundary','source_note')}
    prose.update(schema=SCHEMA, sources=[dict(original='https://example.org/source',target='https://example.org/source',label='合成来源',kind='独立构造的来源')])
    return dict(package_code='SYNTHETIC-B',ruler_id='SYNTHETIC',axis='B',direction='MIXED',
                positive_component_level=None,negative_component_level='R2',source_refs=['https://example.org/source'],
                public_reading=prose,hard_negative_gate='ACTIVE')


def test_public_direction_follows_actual_components_instead_of_legacy_mixed_tag():
    package = synthetic_package()
    before = deepcopy(package)
    reading = package_reading(package)
    assert reading['status'] == '负向损害'
    assert '正向结果强度0级' in reading['components']
    assert package == before


def test_revoked_material_remains_visible_but_does_not_supply_components_or_negative_gate():
    package = synthetic_package()
    package['scoring_eligibility'] = 'REVOKED'
    reading = package_reading(package)
    assert reading['status'] == '不单独计分，保留相关事实'
    assert '负向损害强度0级' in reading['components']
    assert '未触发' in reading['major_negative']


def test_public_sources_are_bound_to_exact_existing_references():
    package = synthetic_package()
    package['public_reading']['sources'][0]['original'] = 'https://example.org/unrelated'
    with pytest.raises(ValueError, match='史源'):
        package_reading(package)


def test_missing_authored_body_cannot_fall_back_to_generic_translation():
    package = synthetic_package()
    del package['public_reading']['responsibility']
    with pytest.raises(ValueError, match='responsibility'):
        package_reading(package)


def test_current_formal_coverage_source_parity_and_readonly_projection():
    payload = load_json(ROOT / FOURTH_PATH)
    before = deepcopy(payload)
    assert verify_readings(payload, ROOT) == len(payload['records'])
    projected = _refresh_fourth(deepcopy(payload))
    assert _signature(projected) == _signature(payload)
    assert payload == before
    packages = {p['package_code']:p for p in payload['accepted_packages']}
    by_id = {r['ruler_id']:r for r in payload['records']}
    for row in projected['records']:
        axis = next(a for a in row['axis_results'] if a['axis']=='B')
        original = next(a for a in by_id[row['ruler_id']]['axis_results'] if a['axis']=='B')
        assert axis['public_reading'] == original['public_reading']
        assert row['public_axis_projections']['B']['public_reading'] == original['public_reading']
    for path in (ROOT / 'reader/data/people').glob('*.json'):
        person = json.loads(path.read_text(encoding='utf-8'))['record']
        for item in (person.get('net') or {}).get('component_details',{}).get('civilization',[]):
            if item['label'] != 'B教育与人才':
                continue
            formal_id = person['net']['source_item_ids']['fourth_item'] if 'source_item_ids' in person['net'] else person['ruler_id']
            row = by_id[formal_id]
            axis = next(a for a in row['axis_results'] if a['axis']=='B')
            assert item['reader_public_fourth_b'] == axis_reading(row,axis,packages)
    html = (ROOT / 'reader/fourth-item-b.html').read_text(encoding='utf-8')
    start = html.index('<script id="fourth-b-data" type="application/json">') + len('<script id="fourth-b-data" type="application/json">')
    records = json.loads(html[start:html.index('</script>',start)])
    assert {r['ruler_id'] for r in records} == set(by_id)
    for row in records:
        source = by_id[row['ruler_id']]
        axis = next(a for a in source['axis_results'] if a['axis']=='B')
        assert row['item']['reader_public_fourth_b'] == axis_reading(source,axis,packages)


def test_all_reader_routes_use_shared_authored_renderer():
    for filename in ('index.template.html','home-interactions.js','person-readability.js'):
        text = (ROOT / 'reader' / filename).read_text(encoding='utf-8')
        assert 'reader_public_fourth_b' in text and 'FourthItemBReading.html' in text
    renderer = (ROOT / 'reader/fourth-item-b-public.js').read_text(encoding='utf-8')
    assert 'replace(/结果方向' not in renderer
    assert 'data-formal-public-source' in renderer
