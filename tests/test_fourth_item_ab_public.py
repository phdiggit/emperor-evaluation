"""Contract and public-projection behavior, with no fixed ruler judgments."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from importlib import import_module
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.third_fourth_item_public import FOURTH_PATH

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=["A", "B"])
def axis(request):
    return request.param


@pytest.fixture
def api(axis):
    return import_module(f"emperor_v4.evaluation.fourth_item_{axis.lower()}_public")


def synthetic_package(api, axis):
    prose = {k:'独立构造的有限身份变化。' for k in ('title','story','baseline','responsibility','level_basis','coverage','duration','boundary','source_note')}
    prose.update(schema=api.SCHEMA, sources=[dict(original='https://example.org/source',target='https://example.org/source',label='合成来源',kind='独立构造的来源')])
    return dict(package_code=f'SYNTHETIC-{axis}',ruler_id='SYNTHETIC',axis=axis,direction='MIXED',
                positive_component_level=None,negative_component_level='R2',source_refs=['https://example.org/source'],
                public_reading=prose,hard_negative_gate='ACTIVE')


def test_public_direction_follows_actual_components_instead_of_legacy_mixed_tag(api, axis):
    package = synthetic_package(api, axis)
    before = deepcopy(package)
    reading = api.package_reading(package)
    assert reading['status'] == '负向损害'
    assert '正向结果强度0级' in reading['components']
    assert package == before


def test_revoked_material_remains_visible_but_does_not_supply_components_or_negative_gate(api, axis):
    package = synthetic_package(api, axis)
    package['scoring_eligibility'] = 'REVOKED'
    reading = api.package_reading(package)
    assert reading['status'] == '不单独计分，保留相关事实'
    assert '负向损害强度0级' in reading['components']
    assert '未触发' in reading['major_negative']


def test_public_sources_are_bound_to_exact_existing_references(api, axis):
    package = synthetic_package(api, axis)
    package['public_reading']['sources'][0]['original'] = 'https://example.org/unrelated'
    with pytest.raises(ValueError, match='史源'):
        api.package_reading(package)


def test_missing_authored_body_cannot_fall_back_to_generic_translation(api, axis):
    package = synthetic_package(api, axis)
    del package['public_reading']['responsibility']
    with pytest.raises(ValueError, match='responsibility'):
        api.package_reading(package)


def test_axis_binding_rejects_foreign_schema_and_same_axis_background(api, axis):
    package = synthetic_package(api, axis)
    other = import_module(f"emperor_v4.evaluation.fourth_item_{'b' if axis == 'A' else 'a'}_public")
    with pytest.raises(ValueError, match=f'第四项{axis}'):
        api.package_reading({**package, 'public_reading': {**package['public_reading'], 'schema': other.SCHEMA}})

    prose = {key: '合成正文。' for key in (
        'question', 'window', 'story', 'decision', 'responsibility', 'boundary', 'source_note')}
    prose.update(schema=api.SCHEMA, assessment_sources=package['public_reading']['sources'], context_items=[
        dict(package_ref=package['package_code'], story='同轴材料不可冒充跨轴背景。', boundary='合成边界。',
             source_refs=package['source_refs'], sources=package['public_reading']['sources'])])
    row = dict(ruler_id='SYNTHETIC', ruler_name='合成对象')
    axis_row = dict(public_reading=prose, package_refs=[], signed_adjustment=0)
    with pytest.raises(ValueError, match='背景材料跨人、跨界或丢失引用'):
        api.axis_reading(row, axis_row, {package['package_code']: package})


def test_current_reader_surfaces_match_formal_readings(api, axis):
    payload = load_json(ROOT / FOURTH_PATH)
    packages = {p['package_code']: p for p in payload['accepted_packages']}
    by_id = {r['ruler_id']: r for r in payload['records']}
    field = f'reader_public_fourth_{axis.lower()}'
    label = {'A': 'A国家共同体', 'B': 'B教育与人才'}[axis]
    for path in (ROOT / 'reader/data/people').glob('*.json'):
        person = json.loads(path.read_text(encoding='utf-8'))['record']
        for item in (person.get('net') or {}).get('component_details', {}).get('civilization', []):
            if item['label'] != label:
                continue
            formal_id = (person['net'].get('source_item_ids') or {}).get('fourth_item', person['ruler_id'])
            row = by_id[formal_id]
            axis_row = next(a for a in row['axis_results'] if a['axis'] == axis)
            assert item[field] == api.axis_reading(row, axis_row, packages)
    html = (ROOT / f'reader/fourth-item-{axis.lower()}.html').read_text(encoding='utf-8')
    marker = f'<script id="fourth-{axis.lower()}-data" type="application/json">'
    start = html.index(marker) + len(marker)
    records = json.loads(html[start:html.index('</script>', start)])
    assert {r['ruler_id'] for r in records} == set(by_id)
    for row in records:
        source = by_id[row['ruler_id']]
        axis_row = next(a for a in source['axis_results'] if a['axis'] == axis)
        assert row['item'][field] == api.axis_reading(source, axis_row, packages)
