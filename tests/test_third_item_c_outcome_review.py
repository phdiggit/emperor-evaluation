import pytest

from emperor_v4.evaluation.third_item_c_contract_reading import _outcome_review_label
from emperor_v4.evaluation.third_item_c_public import _json_passage_matches


@pytest.mark.parametrize('outcome', ['success', 'failure'])
def test_pending_and_rejected_outcomes_are_distinct(outcome):
    row = {f'major_system_{outcome}': False}
    assert _outcome_review_label(row, outcome) == '未登记'
    row[f'major_{outcome}_review_status'] = 'PENDING'
    assert _outcome_review_label(row, outcome) == '待裁（不作已审零项）'
    row[f'major_{outcome}_review_status'] = 'REVIEWED_NOT_ESTABLISHED'
    assert _outcome_review_label(row, outcome) == '已审不成立'
    row[f'major_{outcome}_review_status'] = 'REVIEWED_CONFIRMED'
    row[f'major_system_{outcome}'] = True
    assert _outcome_review_label(row, outcome) == '已审成立'


def test_json_excerpt_must_match_the_named_record():
    document = {'cards': [
        {'battle_id': 'alpha', 'process': '首军有序撤退'},
        {'battle_id': 'beta', 'process': '另一支军队覆没'},
    ]}
    assert _json_passage_matches(document, 'alpha', '有序撤退')
    assert not _json_passage_matches(document, 'alpha', '军队覆没')
    assert not _json_passage_matches(document, 'alpha', '')
    with pytest.raises(ValueError, match='锚点不存在'):
        _json_passage_matches(document, 'missing', '有序撤退')
