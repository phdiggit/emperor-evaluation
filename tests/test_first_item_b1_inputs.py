from pathlib import Path
import math
import pytest

from emperor_v4.evaluation.first_item_b1_inputs import load_b1_inputs, load_opponent_systems, b1_components
from emperor_v4.evaluation.first_item_weights import b1_efficiency_points

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('ratio,points', [(.75,20),(1,18),(1.25,16),(1.5,14),(2,11),(2.5,8),(3,5),(4,2),(4.1,0)])
def test_efficiency_uses_contract_boundaries(ratio, points):
    assert b1_efficiency_points(1000, 12 * ratio) == points


@pytest.mark.parametrize('credit,years', [(-1,1),(1,-1),(math.nan,1),(1,math.inf)])
def test_efficiency_rejects_invalid_stage_parameters(credit, years):
    with pytest.raises(ValueError):
        b1_efficiency_points(credit, years)


def test_independent_machines_are_weighted_without_double_counting():
    systems = {'a':{'organization_grade':'O6'},'b':{'organization_grade':'O4'}}
    row = {'start_resource_grade':'R2','opponent_refs':['b','a'],'efficiency_stages':[]}
    result = b1_components(row, systems)
    assert result == {'start_points':11.,'opponent_points':13.,'efficiency_points':0.,'total_points':24.}
    row['opponent_refs'] = ['a','a']
    with pytest.raises(ValueError):
        b1_components(row, systems)


def test_multistage_efficiency_uses_declared_weights_instead_of_one_lifetime():
    row = {'start_resource_grade':'R6','opponent_refs':[], 'efficiency_stages':[
        {'control_credit':1000,'years':6,'weight':1,'basis':'独立合成目标甲'},
        {'control_credit':1000,'years':24,'weight':3,'basis':'独立合成目标乙'},
    ]}
    assert b1_components(row,{})['efficiency_points'] == 13.3


def test_current_inputs_and_formal_markdown_are_coherent():
    rows = load_b1_inputs(ROOT)
    systems = load_opponent_systems(ROOT)
    assert rows
    for row in rows.values():
        result = b1_components(row, systems)
        assert 0 <= result['total_points'] <= 50
        assert row['source_refs'] and row['timing_basis']
