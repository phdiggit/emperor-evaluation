"""Display values follow the current component projection without a second score."""
from copy import deepcopy

from reader.build import governance_display, record_summary


def test_governance_display_copies_states_and_separates_contribution():
    components = {
        'finance': [
            {'label': 'C1民生', 'grade': 'C1-2 / L1', 'value': 7.3, 'reader_boundary': '限核心地区'},
            {'label': 'C2经济财政', 'grade': 'C2-4 / L0', 'value': 11.2},
            {'label': 'C3社会安全', 'grade': 'C3-3 / L2', 'value': 8.1},
            {'label': 'C4恢复与成本', 'value': -3.2},
        ],
        'method': [{'label': '治理手段', 'value': 41.7}],
        'handoff': [{'label': '交接得分', 'value': 6.0}],
    }
    original = deepcopy(components)
    result = governance_display(components)
    assert result['states'] == [{k: item[k] for k in ('label', 'grade', 'value')}
                                for item in components['finance'][:3]]
    assert result['recovery'] == components['finance'][3]['value']
    assert result['method'] == components['method'][0]['value']
    assert result['handoff'] == components['handoff'][0]['value']
    summary = record_summary({'ruler_id': 'synthetic', 'net': {'governance_display': result}, 'impact': {}, 'axes': {}})
    assert summary['net']['governance_display'] == result
    result['states'][0]['grade'] = 'changed'
    assert components == original


def test_missing_governance_values_are_not_rendered_as_zero():
    result = governance_display({})
    assert result == {'states': [], 'recovery': None, 'method': None, 'handoff': None}
