"""Inherited continuity remains evidence-based, capped, and separate from war credit."""
from copy import deepcopy
import pytest
from c_joint_cases import row
from emperor_v4.evaluation.third_item_c_joint import verify_joint

def inherited(g=3):
    r=row(g,'LOW');r['strategy_chains']=[];r['capability_only_strategy_chains']=[]
    r['strategy_chain_refs']=[];r['capability_only_strategy_chain_refs']=[];r['joint_assessment']['adopted_chain_refs']=[]
    r['public_reading']['evidence_items'][0]['c_chain_refs']=[]
    r['system_observation_status']='INHERITED_UNTESTED'
    r['inherited_system_assessment']=dict(ruler_window='本人',baseline_window='前期',baseline_ruler_id='PREDECESSOR',
        baseline_source_refs=['史源'],counterevidence_review=['反证'],window_review='NO_ACTUAL_SYSTEM_STRESS',continuity_status='SUPPORTED_WITH_LIMITS')
    return r

@pytest.mark.parametrize('g',[0,1,2,3])
def test_continuity_is_not_default_three_or_neutral_position(g):
    r=inherited(g);before=deepcopy(r);assert verify_joint(r)==g;assert r==before
    assert r['C_score_band_position']==.25

@pytest.mark.parametrize('missing',['baseline_source_refs','counterevidence_review','ruler_window','baseline_ruler_id'])
def test_required_continuity_evidence_is_not_inferred(missing):
    r=inherited();del r['inherited_system_assessment'][missing]
    with pytest.raises(ValueError):verify_joint(r)

def test_no_war_does_not_justify_high_grade_broken_continuity_or_copied_battles():
    with pytest.raises(ValueError):verify_joint(inherited(4))
    r=inherited();r['inherited_system_assessment']['continuity_status']='BROKEN'
    with pytest.raises(ValueError):verify_joint(r)
    r=inherited();r['strategy_chains']=[{'chain_id':'PREDECESSOR-WAR'}]
    with pytest.raises(ValueError):verify_joint(r)

def test_unknown_is_not_zero():
    r=inherited(None);assert verify_joint(r) is None
    r['C_score_points']=0
    with pytest.raises(ValueError):verify_joint(r)
