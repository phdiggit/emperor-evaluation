from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from html.parser import HTMLParser
import pytest

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_d1_d3_public import D1_PATH, D3_PATH, PUBLIC_RECORD_FIELDS, _refresh_payload, _scoring_signature, verify_public_projection, render_public_markdown, public_record


def synthetic(root, axis):
    folder = root / 'docs'
    folder.mkdir(exist_ok=True)
    source = folder / 'synthetic-source.md'
    source.write_text('旧臣继续办事，太子承接。\n', encoding='utf-8')
    row = dict(ruler_id='SYNTHETIC-RULER', ruler_name='合成甲', polity='合成国',
               direction_index=1.5, grade='G2', handoff_level='H2', D3_grade='D3-2',
               grade_basis='允许保留内部H2代码', reason='内部判词不得生成公开正文',
               public_story='旧臣继续办事，太子承接。',
               public_adjudication_summary='承接有实际运行依据，但存在明确限制。',
               public_window='观察实际退出后的接续。',
               public_responsibility='只采用所留人员和安排。',
               public_boundary='不以继任者全部成果证明前任贡献。',
               public_evidence_items=[dict(id=f'{axis}-SYNTHETIC-EVIDENCE',
                   public_label='既有人员与承接', public_role='交接结果',
                   public_basis='太子承接且旧臣继续办事。',
                   public_boundary='此条不说明继任者长期成败。', evidence_mode='INFERRED',
                   source_refs=[dict(path='docs/synthetic-source.md',
                       source_title='合成史料', source_locator='第1行', source_kind='史料原文引句',
                       source_url='', excerpt='旧臣继续办事，太子承接。', public_excerpt='旧臣继续办事，太子承接。', line=1)])])
    return _refresh_payload(dict(records=[row]), axis)


def test_refresh_preserves_authored_text_sources_and_nonpublic_fields(tmp_path):
    for axis in ('D1', 'D3'):
        payload = synthetic(tmp_path, axis)
        before = deepcopy(payload)
        payload['records'][0]['grade_basis'] = '换成新的内部说明也不重写正文'
        signature = _scoring_signature(payload)
        refreshed = _refresh_payload(payload, axis)
        assert _scoring_signature(refreshed) == signature
        for field in PUBLIC_RECORD_FIELDS:
            assert refreshed['records'][0][field] == before['records'][0][field]
        assert all('public_excerpt' not in ref for item in refreshed['records'][0]['public_evidence_items'] for ref in item['source_refs'])


def test_reading_formats_only_the_retained_quote_and_keeps_editorial_notes(tmp_path):
    row = synthetic(tmp_path, 'D1')['records'][0]
    raw = "'''[[甲]]'''<ref>乙</ref><br>丙"
    row['public_evidence_items'][0]['source_refs'][0]['excerpt'] = raw
    before = deepcopy(row)
    result = public_record(row)
    source = result['public_evidence_items'][0]['source_refs'][0]
    assert source['excerpt'] == raw
    assert source['public_excerpt'] == '甲〔校注：乙〕\n丙'
    source['excerpt'] = '消费端修改。'
    assert row == before


def test_missing_authored_text_is_rejected_instead_of_inferred(tmp_path):
    payload = synthetic(tmp_path, 'D1')
    del payload['records'][0]['public_story']
    with pytest.raises(ValueError, match='缺少直接维护'):
        _refresh_payload(payload, 'D1')


@pytest.mark.parametrize('damage', ['quote', 'transcription', 'line', 'path', 'source', 'code', 'fragment'])
def test_invalid_source_or_prose_fails_closed(tmp_path, damage):
    payloads = {axis: synthetic(tmp_path, axis) for axis in ('D1', 'D3')}
    item = payloads['D1']['records'][0]['public_evidence_items'][0]
    ref = item['source_refs'][0]
    if damage == 'quote': ref['excerpt'] = '没有这句史料'
    elif damage == 'transcription': ref['public_excerpt'] = '在史料引句中添加新结论'
    elif damage == 'line': ref['line'] = 7
    elif damage == 'path': ref['path'] = '../outside.md'
    elif damage == 'source': item['source_refs'] = []
    elif damage == 'code': item['public_basis'] = 'H2达到条件。'
    else: item['public_basis'] = '其价值达到。'
    with pytest.raises(ValueError):
        verify_public_projection(tmp_path, payloads=payloads)


def test_markdown_displays_full_authored_text_and_quotations(tmp_path):
    payload = synthetic(tmp_path, 'D1')
    markdown = render_public_markdown(payload, 'D1')
    row = payload['records'][0]
    for field in PUBLIC_RECORD_FIELDS:
        if field != 'public_evidence_items': assert row[field] in markdown
    assert row['public_evidence_items'][0]['source_refs'][0]['excerpt'] in markdown
    assert markdown == render_public_markdown(payload, 'D1')


def test_reader_uses_complete_authored_projection_without_transforming_evidence():
    root = Path(__file__).resolve().parents[1]
    sources = {axis: {r['ruler_id']: r for r in load_json(root / path)['records']}
               for axis, path in [('D1', D1_PATH), ('D3', D3_PATH)]}
    seen = set()
    for path in (root / 'reader/data/people').glob('*.json'):
        record = json.loads(path.read_text(encoding='utf-8'))['record']
        for item in (record.get('net') or {}).get('component_details', {}).get('handoff', []):
            axis = {'D1继任行政连续性': 'D1', 'D3政权交接稳定': 'D3'}.get(item.get('label'))
            if not axis: continue
            formal = public_record(sources[axis][record['ruler_id']])
            assert item['reader_public_d'] == {k: formal[k] for k in PUBLIC_RECORD_FIELDS}
            assert item['reader_public_evidence_items'] == formal['public_evidence_items']
            seen.add(axis)
    assert seen == set(sources)


def test_full_pool_collection_keeps_every_authored_record_and_quotation():
    class Collection(HTMLParser):
        def __init__(self):
            super().__init__()
            self.current = None
            self.people = {}
            self.evidence = set()

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'article':
                self.current = attrs['id']
                self.people[self.current] = ''
            if 'data-public-evidence-id' in attrs:
                self.evidence.add(attrs['data-public-evidence-id'])

        def handle_endtag(self, tag):
            if tag == 'article': self.current = None

        def handle_data(self, data):
            if self.current: self.people[self.current] += data

    root = Path(__file__).resolve().parents[1]
    page = Collection()
    page.feed((root / 'reader/second-item-d.html').read_text(encoding='utf-8'))
    expected_ids, expected_evidence = set(), set()
    for path in (D1_PATH, D3_PATH):
        for row in load_json(root / path)['records']:
            row = public_record(row)
            expected_ids.add(row['ruler_id'])
            text = page.people[row['ruler_id']]
            for field in PUBLIC_RECORD_FIELDS:
                if field != 'public_evidence_items':
                    assert all(part in text for part in row[field].split('\n\n'))
            for item in row['public_evidence_items']:
                expected_evidence.add(item['id'])
                assert item['public_basis'] in text
                for ref in item['source_refs']:
                    assert ref['public_excerpt'] in text
    assert set(page.people) == expected_ids
    assert page.evidence == expected_evidence
