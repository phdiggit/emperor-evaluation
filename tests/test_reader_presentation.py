from copy import deepcopy
from reader.build import axis_summary
from reader.presentation import period_label, prepare_collections


def test_overview_preserves_semantic_flags_without_copying_evidence_body():
    source = dict(axis_grade='G0', position='MID', output_mode='BOUNDED_PROFILE',
                  assessment_basis='NO_DEMONSTRATED_CAPABILITY',
                  evidence_floor_review={'status': 'BOUNDED_EVIDENCE_FLOOR', 'basis': '长证据'},
                  adjudication_state='SETTLED', score_status='EVIDENCE_LIMITED')
    before = deepcopy(source)
    result = axis_summary(source)
    assert result['assessment_basis'] == source['assessment_basis']
    assert result['evidence_floor_review'] is True
    assert result['score_status'] == source['score_status']
    assert result['axis_grade'] == source['axis_grade']
    assert source == before


def test_periods_keep_ranges_and_multiple_terms():
    assert period_label([404, 422]) == '404—422年'
    assert period_label([[-10, -2], [4, 9]]) == '前10—前2年；4—9年'
    assert period_label('某年亲政') == '某年亲政'


def test_collection_identity_and_access_do_not_depend_on_total_score():
    pool = {'records': [dict(ruler_id='canonical', ruler_name='甲', pool_status='INCLUDED',
                            settlement_readiness='PENDING', source_item_ids={'second_item': 'source-id'}),
                        dict(ruler_id='outside', ruler_name='乙', pool_status='EXCLUDED', source_item_ids={})]}
    impact = {'records': [dict(ruler_id='canonical', ruler_name='甲', identity_label='甲（合成帝）')]}
    pages = {'test.html': ('某分项', '<h1>分项</h1><article id="source-id"><h2>甲</h2><p>原有依据</p></article><article id="outside"><h2>乙</h2></article>')}
    original = deepcopy((pages, pool, impact))
    rendered, entries = prepare_collections(pages, pool, impact)
    assert entries == {'canonical': [{'label': '某分项', 'href': 'test.html#source-id'}]}
    assert '<h2>甲（合成帝）</h2>' in rendered['test.html']
    assert '<p>原有依据</p>' in rendered['test.html']
    assert '池外单项记录' in rendered['test.html']
    assert (pages, pool, impact) == original
    folded, links = prepare_collections({'fold.html': ('分项', '<h1>阅读</h1><details id="source-id"><summary><h2>甲</h2></summary><p>正文</p></details>')}, pool, impact)
    assert '</summary><p class="collection-scope">' in folded['fold.html']
    assert '<summary><h2>甲（合成帝）</h2></summary>' in folded['fold.html']
    assert links['canonical'][0]['href'] == 'fold.html#source-id'
