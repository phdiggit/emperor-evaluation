"""Result profiles are factual evidence; explicit joint position controls scoring."""
from copy import deepcopy
import pytest
from c_joint_cases import row
from emperor_v4.evaluation.third_item_c_joint import score_fields,verify_joint

@pytest.mark.parametrize('g,p,points',[(0,'LOW',3.6),(1,'MID',18.5),(2,'HIGH',27.8),(5,'HIGH',48.8)])
def test_decimal_mapping_and_rounding_on_independent_synthetic_cases(g,p,points):
    assert score_fields(g,p)['C_score_points']==points

@pytest.mark.parametrize('counts',[{'HIGH_RETURN':8},{'NEGATIVE_RETURN':8},{'UNKNOWN':9},{}])
def test_outcome_counts_do_not_silently_change_authored_position(counts):
    r=row();r['strategy_chain_outcome_profile']={'return_class_counts':counts};before=deepcopy(r)
    verify_joint(r);assert r==before

def test_illegal_position_and_unknown_zero_are_rejected():
    with pytest.raises(ValueError):score_fields(3,'TOP')
    with pytest.raises(ValueError):score_fields(None,'MID')
    r=row();r['C_score_rate']+=1
    with pytest.raises(ValueError):verify_joint(r)

def test_removing_an_adopted_chain_invalidates_its_evidence_binding():
    r=row();r['strategy_chains']=[]
    with pytest.raises(ValueError):verify_joint(r)
