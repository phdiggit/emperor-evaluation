from itertools import product

from emperor_v4.evaluation.rank_envelope import certify


def test_handoff_exclusions_preserve_d1_and_apply_low_side_cap():
    from emperor_v4.evaluation.rank_envelope import handoff_enclosure
    current={'D1_level':2, 'D3_level':4}
    review={'baseline':current.copy(), 'source_refs':['synthetic-source'],
            'dependency_basis':'D1 unaffected', 'public_basis':'Sourced exclusions',
            'excluded_d3_levels':{'0':'central continuation', '1':'single successor'}}
    # Remaining D3 levels do not imply all 20 handoff points can vary.
    assert handoff_enclosure(current,review)==(8,12)
    import pytest
    with pytest.raises(ValueError,match='基准已变'):
        handoff_enclosure({'D1_level':3,'D3_level':4},review)
    review['excluded_d3_levels']['4']='current ruling invalid'
    with pytest.raises(ValueError,match='先修正'):
        handoff_enclosure(current,review)


def test_bounds_prove_rank_despite_varying_scores_and_preserve_ties():
    result=certify({'a':(100,110),'b':(30,40),'c':(30,40),'d':(0,0)})
    assert result['a']=={'best_possible_rank_bound':1,'worst_possible_rank_bound':1}
    assert result['d']=={'best_possible_rank_bound':4,'worst_possible_rank_bound':4}
    tied=certify({'a':(5,5),'b':(5,5),'c':(0,0)})
    assert tied['a']['worst_possible_rank_bound']==1
    assert tied['c']['best_possible_rank_bound']==3


def test_outer_rank_proof_encloses_every_independent_world():
    bounds={'a':(0,3),'b':(1,4),'c':(3,3)}
    result=certify(bounds)
    for values in product(range(4),range(1,5),(3,)):
        for index,rid in enumerate(bounds):
            rank=1+sum(v>values[index] for v in values)
            assert result[rid]['best_possible_rank_bound']<=rank<=result[rid]['worst_possible_rank_bound']


def test_dependent_worlds_can_be_stable_despite_outer_overlap():
    result=certify({'a':(5,10),'b':(4,9)})
    # The two legal linked worlds keep a above b. Their independent box is
    # wider; overlap is therefore inconclusive, not an instability witness.
    assert all(a>b for a,b in [(5,4),(10,9)])
    assert result['a']['best_possible_rank_bound']==1
    assert result['a']['worst_possible_rank_bound']==2


def test_missing_scope_never_silently_fixes_a_disputed_ruler(tmp_path):
    import pytest
    from emperor_v4.evaluation.rank_envelope import apply
    registry={'cases':[{'case_id':'open','status':'UNRESOLVED_EVIDENCE_GAP'}],
              'rank_envelope':{'case_scopes':{}}}
    with pytest.raises(ValueError,match='精确登记'):
        apply(tmp_path,[],[],{},registry)


def test_cost_limits_take_max_with_ml_and_never_claim_endpoints_admissible(tmp_path):
    import json
    from emperor_v4.evaluation.rank_envelope import apply
    for path,payload in [
        ('config/first-item/military-cost-debits.json',{'max_debit_points':80}),
        ('config/third-item/third-item-cost-credit-factors.json',{'cost_debit_base_points':80})]:
        dest=tmp_path/path;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(payload),encoding='utf-8')
    rows=[dict(ruler_id='a',ruler_name='synthetic',rank=1,first_item_status='NOT_APPLICABLE',
        first_item_raw_score=None,second_item_score=0,third_item_score=80,
        fourth_item_adjustment=0,total_score=80,
        evidence_assessment={'closure_ids':[],'rank_status':'NOT_ESTABLISHED'})]
    pool=[dict(ruler_id='a',ruler_name='synthetic',source_item_ids={'second_item':'a','third_item':'a'})]
    details={'first_cost':{},'third':{'a':dict(
        global_cost_credit_profile={'status':'LOWER_BOUND'},
        applied_military_debit_points=20,cost_debit_points=10,military_net_loss_penalty=-20)}}
    apply(tmp_path,rows,pool,details,{'cases':[],'rank_envelope':{'case_scopes':{}}})
    envelope=rows[0]['evidence_assessment']['contract_envelope']
    assert envelope['score_outer_bounds']==[20,80]
    assert envelope['is_admissible_score_interval'] is False
    assert envelope['rank_proven_within_registered_enclosure'] is True
    assert envelope['public_display'] is False
    assert rows[0]['evidence_assessment']['rank_status']=='NOT_ESTABLISHED'
