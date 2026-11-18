from copy import deepcopy
from decimal import Decimal

import pytest

from emperor_v4.evaluation.civilian_harm import (
    calculate_harm, legacy_c4_score, remaining_deterioration, validate_candidate,
)


def inputs():
    return dict(recovery=10, price=4.5,
                actual={a:{'main_band':2,'loss_grade':'L0'} for a in ('C1','C2','C3')},
                references={'C1':{'main_band':3,'loss_grade':'L0'}},
                paths={a:{'raw_drop':2,'attribution_factor':1} for a in ('C1','C2','C3')},
                removed={'C1':1})


def candidate():
    return dict(migration_state='PRICED_CANDIDATE',price=4.5,price_basis='Bounded synthetic injury',
                outcomes=[dict(id='household',scope='One synthetic district',consequence='Asset loss',
                               attribution='Authorized seizure',allocation='Direct loss, no military input',
                               evidence_mode='DIRECT',source_refs=['docs/synthetic-source.md#asset-loss'])],
                calculation_input=inputs(),
                state_bindings={'C1':dict(outcome_ids=['household'],basis='Same asset loss in actual state')},
                E_bindings={'C1':dict(outcome_ids=['household'],basis='Same asset loss in decline')})


def test_combines_after_removal_and_refunds_each_existing_ledger_once():
    source=inputs();before=deepcopy(source);r=calculate_harm(**source)
    assert r['E_before']==13 and r['E_remaining']==9.8 and r['C_E']==3.2
    assert r['C_state_L']==14.9 and r['C4']==10.6
    assert source==before
    assert validate_candidate(candidate())==r


def test_cap_can_hide_a_real_removal():
    data=inputs()
    for p in data['paths'].values():p['raw_drop']=5
    result=calculate_harm(**data)
    assert result['E_before']==result['E_remaining']==13
    assert result['C_E']==0


def test_deterioration_uses_its_authored_factor_not_recovery_grade_enum():
    data=inputs()
    for p in data['paths'].values():p['attribution_factor']=.55
    assert remaining_deterioration(data['paths'],{})==Decimal('7.2')


def test_combined_state_and_loss_reference_not_separate_refunds():
    data=inputs();data['actual']['C1']={'main_band':4,'loss_grade':'L2'}
    data['references']['C1']={'main_band':5,'loss_grade':'L0'}
    r=calculate_harm(**data)
    assert r['C_state_L']==23.2
    assert len(r['state_credit_details'])==1


def test_new_calculation_has_no_component_cap_but_combined_block_is_bounded():
    data=inputs();data.update(recovery=27,removed={},price=4.5)
    for p in data['paths'].values():p['raw_drop']=0
    r=calculate_harm(**data)
    assert r['C4']>27
    assert sum([17.1,7,16])+r['C4']<=202
    assert legacy_c4_score(27,0,-10)==27


@pytest.mark.parametrize('value',[None,True,float('nan'),float('inf'),-4.5,31.5,5])
def test_invalid_prices_are_not_adoptable(value):
    data=inputs();data['price']=value
    with pytest.raises(ValueError):calculate_harm(**data)


@pytest.mark.parametrize('removed',[{'C1':3},{'C1':-1},{'C1':True},{'C1':.5},{'C9':1}])
def test_decline_removal_requires_existing_integer_boundaries(removed):
    with pytest.raises(ValueError):remaining_deterioration(inputs()['paths'],removed)


def test_repricing_an_alternate_state_does_not_reuse_stale_refund():
    data=inputs();data['actual']['C1']['main_band']=4
    with pytest.raises(ValueError,match='Negative state credit'):calculate_harm(**data)
    data=inputs();data['actual']['C1']['score']=0
    with pytest.raises(ValueError,match='drift'):calculate_harm(**data)


@pytest.mark.parametrize('state',['UNRESOLVED','BASELINE_RETAINED','NOT_READY'])
def test_nonadjudicated_states_require_null_price_and_no_new_calculation(state):
    r={'migration_state':state,'price':None,'calculation_input':None}
    assert validate_candidate(r) is None
    r['price']=0
    with pytest.raises(ValueError,match='cannot carry'):validate_candidate(r)


def test_partial_unresolved_event_does_not_erase_closed_scope():
    r=candidate();r['open_events']=[{'event':'another event, unresolved'}]
    assert validate_candidate(r)==validate_candidate(candidate())


def test_same_consequence_cannot_be_refunded_on_two_state_axes():
    r=candidate();r['calculation_input']['references']['C2']={'main_band':3,'loss_grade':'L0'}
    r['state_bindings']['C2']=deepcopy(r['state_bindings']['C1'])
    with pytest.raises(ValueError,match='multiple axes'):validate_candidate(r)


def test_unadmitted_outcome_cannot_receive_credit():
    r=candidate();r['E_bindings']['C1']['outcome_ids']=['unknown']
    with pytest.raises(ValueError,match='Unknown'):validate_candidate(r)


def test_inferred_scope_and_permanent_source_constraints():
    r=candidate();r['outcomes'][0]['evidence_mode']='INFERRED'
    r['price']=r['calculation_input']['price']=9
    with pytest.raises(ValueError,match='conservative'):validate_candidate(r)
    r=candidate();r['outcomes'][0]['source_refs']=['.tmp/trial.json']
    with pytest.raises(ValueError,match='permanent'):validate_candidate(r)


def test_zero_price_is_an_explicit_empty_scope_not_unknown():
    r=candidate();r.update(price=0,outcomes=[],state_bindings={},E_bindings={})
    r['calculation_input'].update(price=0,references={},removed={})
    assert validate_candidate(r)['P']==0


def test_legacy_rounding_is_decimal_half_up():
    assert legacy_c4_score(Decimal('2.25'),0,0)==2.3


def formal_record():
    from emperor_v4.evaluation.civilian_harm import FORMAL_VERSION
    v=inputs()
    row={'positive_score_retained':v['recovery'],'deterioration_penalty':13,
         'deterioration_path_basis':v['paths'],'destructive_amplification_penalty':9,
         'destructive_amplification_grade':'DA2',
         'civilian_harm_adjudication':{
             'version':FORMAL_VERSION,'status':'ADOPTED','group_id':'synthetic-group',
             'price':v['price'],'actual_states':v['actual'],'state_references':v['references'],
             'E_removed_steps':v['removed'],'scope_basis':'Synthetic household loss',
             'price_basis':'Bounded loss','state_credit_basis':'One state boundary',
             'E_basis':'Same group in endpoint decline','R_basis':'Unrelated restoration',
             'source_refs':['docs/synthetic-source.md'],
             'state_bindings':{'C1':{'basis':'Household assets'}},
             'E_bindings':{'C1':{'basis':'Same assets in endpoint decline'}},
             'military_inputs_excluded':True,'same_consequence_multiple_refunds':False}}
    from emperor_v4.evaluation.civilian_harm import formal_calculation
    c=formal_calculation(row)
    row.update(score=c['C4'],raw_score=c['C4'],civilian_harm_calculation=c)
    return row


def test_formal_adoption_ignores_legacy_da_and_validates_the_derived_projection():
    from emperor_v4.evaluation.civilian_harm import formal_calculation,validate_formal
    row=formal_record();expected=formal_calculation(row)
    row['destructive_amplification_penalty']=27
    assert formal_calculation(row)==expected
    validate_formal(row)
    row['score']+=row['civilian_harm_calculation']['C_E']
    with pytest.raises(ValueError,match='score drift'):validate_formal(row)


def test_formal_unresolved_is_a_legacy_mechanism_not_a_zero_harm_ruling():
    from emperor_v4.evaluation.civilian_harm import formal_calculation,validate_formal
    row=formal_record();j=row['civilian_harm_adjudication']
    j.update(status='UNRESOLVED',price=None,state_references={},E_removed_steps={})
    result=formal_calculation(row)
    assert result['P'] is None and result['legacy_DA']==9
    assert result['C4']==-12
    row.update(score=-12,raw_score=-12)
    validate_formal(row)
    j['price']=0
    with pytest.raises(ValueError,match='Unadjudicated'):validate_formal(row)


def test_alternate_state_and_decline_cannot_keep_nonexistent_refunds():
    from emperor_v4.evaluation.civilian_harm import formal_calculation
    row=formal_record();before=deepcopy(row)
    ruling={'axes':{a:{'main_band':4,'s0_band':2,'end_band':2,'loss_review':{'grade':'L0'}} for a in ('C1','C2','C3')},
            'recovery':{'deterioration_attribution_by_axis':dict.fromkeys(('C1','C2','C3'),1)}}
    result=formal_calculation(row,ruling,10,0,scenario=True)
    assert result['C_state_L']==0 and result['C_E']==0 and result['C4']==5.5
    assert row==before
    with pytest.raises(ValueError):formal_calculation(row,ruling,10,0)


def test_public_formula_separates_recovery_from_refund():
    from emperor_v4.evaluation.civilian_harm import formal_net_line
    line=formal_net_line(formal_record())
    assert '剩余恶化 9.8' in line and '损害总价 4.5' in line and '已计回补 14.9' in line
    assert '3.2' not in line  # E credit is already included in the remaining debit.


def test_zero_harm_cannot_authorize_a_formal_refund():
    from emperor_v4.evaluation.civilian_harm import validate_formal
    row=formal_record();row['civilian_harm_adjudication']['price']=0
    with pytest.raises(ValueError,match='Zero admitted harm'):validate_formal(row)


def test_current_summary_refresh_preserves_legacy_evidence_and_rejects_drift():
    from emperor_v4.evaluation.civilian_harm import refresh_current_summary, validate_formal
    row=formal_record()
    row.update(recovery_score=2, closed_recovery_axes=['C1'],
               public_adjudication='Obsolete total',
               typical_pattern={'status':'STRUCTURED_C4_FORMAL','positive_score_retained':99},
               c4_attribution_readjudication={'basis_version':'legacy','final_penalty':9})
    legacy=deepcopy(row['c4_attribution_readjudication'])
    with pytest.raises(ValueError,match='public summary'):validate_formal(row)
    refresh_current_summary(row)
    validate_formal(row)
    assert row['c4_attribution_readjudication']==legacy
    assert row['typical_pattern']['closed_recovery_axes'] is not row['closed_recovery_axes']
    row['typical_pattern']['positive_score_retained']+=1
    with pytest.raises(ValueError,match='recovery summary'):validate_formal(row)
