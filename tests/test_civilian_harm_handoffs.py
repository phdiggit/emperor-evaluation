from copy import deepcopy
import json
import pytest
from emperor_v4.evaluation.civilian_harm_handoffs import validate_pair


def pair():
    forward={'binding_id':'synthetic','relation':'DISTINCT_OUTCOMES',
             'basis':'Separate realized asset loss and legal dependency',
             'owned_outcome':'Asset loss','peer_owned_outcome':'Legal dependency'}
    reverse={**forward,'owned_outcome':'Legal dependency','peer_owned_outcome':'Asset loss'}
    return forward,reverse


def test_reciprocal_outcome_roles_are_read_only():
    a,b=pair();before=deepcopy((a,b));validate_pair(a,b);assert (a,b)==before


@pytest.mark.parametrize('field',['binding_id','relation','basis','owned_outcome','peer_owned_outcome'])
def test_one_sided_handoff_changes_are_rejected(field):
    a,b=pair();b[field]='different'
    with pytest.raises(ValueError):validate_pair(a,b)


def test_institution_bindings_must_match_in_both_directions():
    a,b=pair();a['institution_node_ids']=['synthetic-rule']
    with pytest.raises(ValueError,match='institution-node'):validate_pair(a,b)


def test_missing_reciprocal_record_is_rejected(tmp_path):
    from emperor_v4.evaluation.civilian_harm_handoffs import verify_handoffs
    path=tmp_path/'docs/评分结算/peer.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'records':[{'ruler_id':'peer'}]}),encoding='utf-8')
    link={**pair()[0],'peer_source':'docs/评分结算/peer.json','peer_ruler_id':'peer','peer_component':'I2.B2'}
    row={'ruler_id':'ruler','civilian_harm_adjudication':{'group_id':'group','cross_item_handoffs':[link]}}
    with pytest.raises(ValueError,match='reciprocal'):verify_handoffs(tmp_path,[row])


def test_excluded_fourth_result_cannot_claim_an_independent_price(tmp_path):
    from emperor_v4.evaluation.civilian_harm_handoffs import verify_handoffs
    path=tmp_path/'docs/评分结算/peer.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'records':[{'ruler_id':'peer','axis_results':[
        {'results':[],'nonadmitted_results':[{'result_id':'unpriced'}]}]}]}),encoding='utf-8')
    link={**pair()[0],'peer_source':'docs/评分结算/peer.json','peer_ruler_id':'peer',
          'peer_component':'I4.A','peer_result_id':'unpriced'}
    row={'ruler_id':'ruler','civilian_harm_adjudication':{'group_id':'group','cross_item_handoffs':[link]}}
    with pytest.raises(ValueError,match='admission status'):verify_handoffs(tmp_path,[row])
