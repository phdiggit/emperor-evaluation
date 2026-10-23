import json
from copy import deepcopy

import pytest

from emperor_v4.evaluation.third_item_current_settlement import _replace_non_public_preserving_public, _validate_overlapping_subject_windows


def test_scoring_sync_preserves_only_the_existing_public_projection():
    current = {
        "score": 1,
        "public_basis": "正式视图原有公开说明",
        "nested": {
            "value": 1,
            "public_boundary": "正式视图原有边界",
        },
        "strategy_chains": [
            {
                "chain_id": "synthetic-chain",
                "credit": 0.5,
                "public_boundary": "正式视图原有步骤说明",
            }
        ],
    }
    source = {
        "score": 2,
        "public_basis": "另一投影的公开说明不得迁入",
        "nested": {
            "value": 2,
            "public_boundary": "另一投影的边界不得迁入",
            "public_level_label": "正式视图不存在的公开字段不得新增",
        },
        "strategy_chains": [
            {
                "chain_id": "synthetic-chain",
                "credit": 1.0,
                "public_boundary": "另一投影的步骤说明不得迁入",
            }
        ],
    }

    synchronized = _replace_non_public_preserving_public(current, source)

    assert list(synchronized) == ["score", "public_basis", "nested", "strategy_chains"]
    assert synchronized == {
        "score": 2,
        "public_basis": "正式视图原有公开说明",
        "nested": {
            "value": 2,
            "public_boundary": "正式视图原有边界",
        },
        "strategy_chains": [
            {
                "chain_id": "synthetic-chain",
                "credit": 1.0,
                "public_boundary": "正式视图原有步骤说明",
            }
        ],
    }


def test_scoring_sync_matches_people_and_nested_owners_after_reordering():
    current = dict(records=[dict(ruler_id=rid, score=score,
        public_reading=dict(story=rid+'正文'),
        axis_results=[dict(axis=axis, value=1, public_reading=dict(story=rid+axis+'正文')) for axis in ('X','Y')],
        strategy_chains=[dict(chain_id=rid+'-chain', value=1, public_boundary=rid+'链范围')])
        for rid,score in [('A',2),('B',1)]])
    source = dict(records=[dict(ruler_id=rid, score=score,
        public_reading=dict(story='外来正文不得迁入'),
        axis_results=[dict(axis=axis, value=2) for axis in ('Y','X')],
        strategy_chains=[dict(chain_id=rid+'-new', value=2),dict(chain_id=rid+'-chain', value=2)])
        for rid,score in [('B',3),('A',2)]])
    before = deepcopy((current, source))
    result = _replace_non_public_preserving_public(current, source)
    assert [r['ruler_id'] for r in result['records']] == ['B','A']
    for row in result['records']:
        rid = row['ruler_id']
        assert row['public_reading']['story'] == rid+'正文'
        assert [a['axis'] for a in row['axis_results']] == ['Y','X']
        assert all(a['public_reading']['story'] == rid+a['axis']+'正文' and a['value']==2 for a in row['axis_results'])
        assert 'public_boundary' not in row['strategy_chains'][0]
        assert row['strategy_chains'][1]['public_boundary'] == rid+'链范围'
    assert (current, source) == before
    result['records'][0]['public_reading']['story'] = '消费端变更'
    assert (current, source) == before


def test_scoring_sync_keeps_survivors_on_insertion_and_deletion_without_importing_new_prose():
    current = dict(records=[dict(ruler_id=rid, public_reading=dict(story=rid)) for rid in ('A','B')])
    source = dict(records=[dict(ruler_id=rid, public_reading=dict(story='外来正文')) for rid in ('C','B','D')])
    result = _replace_non_public_preserving_public(current, source)
    assert result == dict(records=[dict(ruler_id='C'),dict(ruler_id='B',public_reading=dict(story='B')),dict(ruler_id='D')])


@pytest.mark.parametrize('side', ['current','source'])
@pytest.mark.parametrize('bad_rows', [[{'ruler_id':'A'},{'ruler_id':'A'}], [{}], [{'ruler_id':''}], [{'ruler_id':None}]])
def test_scoring_sync_rejects_ambiguous_person_identity(side, bad_rows):
    values = dict(current=dict(records=[dict(ruler_id='A', public_reading=dict(story='甲'))]),
                  source=dict(records=[dict(ruler_id='A')]))
    values[side]['records'] = bad_rows
    before = deepcopy(values)
    with pytest.raises(ValueError, match='身份'):
        _replace_non_public_preserving_public(**values)
    assert values == before


def test_scoring_sync_never_matches_an_unidentified_public_list_by_position():
    current = dict(steps=[dict(value=1, public_boundary='原范围')])
    with pytest.raises(ValueError, match='未声明稳定身份'):
        _replace_non_public_preserving_public(current, dict(steps=[dict(value=2)]))
    assert _replace_non_public_preserving_public(dict(steps=[1,2]),dict(steps=[3])) == dict(steps=[3])


def test_scoring_sync_requires_field_policy_and_rejects_cross_person_mapping():
    with pytest.raises(ValueError, match='未声明维护归属'):
        _replace_non_public_preserving_public(dict(public_new_source='人工正文'),{})
    with pytest.raises(ValueError, match='未声明维护归属'):
        _replace_non_public_preserving_public({},dict(public_new_source='人工正文'))
    with pytest.raises(ValueError, match='身份不一致'):
        _replace_non_public_preserving_public(dict(ruler_id='A',public_reading={}),dict(ruler_id='B'))


def test_total_writer_keeps_public_fields_with_owner_when_scores_change_rank(monkeypatch, tmp_path):
    from emperor_v4.evaluation import third_item_current_settlement as settlement
    from emperor_v4.evaluation import five_dynasties_third_item as rendering

    old = dict(records=[dict(ruler_id=rid, third_item_score_points=score,
                           public_military_net_loss=dict(public_adjudication_summary=rid+'损失说明'))
                        for rid,score in [('A',2),('B',1)]])
    new = dict(records=[dict(ruler_id=rid, third_item_score_points=score)
                        for rid,score in [('B',3),('A',2)]])
    for path,payload in [(settlement.FORMAL_PATH,old), (settlement.AB_PATH,dict(records=[])),
                         (settlement.RESULT_CREDIT_ADJUDICATIONS_PATH,dict(records=[]))]:
        target = tmp_path/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    monkeypatch.setattr(settlement,'_load_a_axis_narrative_adjudications',lambda root:{})
    for name in ('_validate_a_axis_closure','_synchronize_current_ab_view','_synchronize_current_c_outcome_view'):
        monkeypatch.setattr(settlement,name,lambda *args,**kwargs:None)
    monkeypatch.setattr(rendering,'validate_ab_shared_handoffs',lambda *args,**kwargs:None)
    monkeypatch.setattr(settlement,'build_current_third_item_settlement',lambda root:deepcopy(new))
    monkeypatch.setattr(settlement,'_render_current_weighted_markdown',lambda records:'synthetic view\n')
    result = settlement.write_current_third_item_settlement(tmp_path)
    saved = json.loads((tmp_path/settlement.FORMAL_PATH).read_text(encoding='utf-8'))
    assert saved == result
    assert [r['ruler_id'] for r in saved['records']] == ['B','A']
    assert [r['third_item_score_points'] for r in saved['records']] == [3,2]
    for row in saved['records']:
        assert row['public_military_net_loss']['public_adjudication_summary'] == row['ruler_id']+'损失说明'


def test_c_major_result_summary_counts_chains_and_separates_capability():
    from emperor_v4.evaluation.third_item_current_settlement import _current_c_task_basis_reason

    row = {
        "strategy_chains": [{
            "chain_id": "synthetic-pressure",
            "source_event_refs": ["phase-a", "phase-b", "phase-c", "phase-d"],
            "major_system_failure": True,
        }],
        "major_system_failure_refs": ["phase-a", "phase-b", "phase-c", "phase-d"],
        "capability_only_strategy_chains": [{
            "chain_id": "synthetic-capability", "major_system_success": True,
        }],
    }
    text = _current_c_task_basis_reason(row, row["major_system_failure_refs"], 0, {})
    assert "当前战略链重大体系胜绩0项、重大体系失败1项" in text
    assert "能力专用战略链胜绩1项、重大失败0项" in text


def test_changed_a_endpoints_do_not_restore_retired_atomic_scores(monkeypatch, tmp_path):
    from copy import deepcopy
    from emperor_v4.evaluation import third_item_current_settlement as settlement
    from emperor_v4.evaluation import five_dynasties_third_item as rendering

    # Independent synthetic endpoints exercise a writer transition, not ruler results.
    row = {
        "ruler_id": "synthetic", "ruler_name": "合成对象",
        "control_contribution_type": "INHERITED_ONLY",
        "axes": {name: {"axis_points": 99, "reason": name + "合成事实"}
                 for name in ("A1", "A2", "B4")},
    }
    adjudication = {
        "ruler_id": "synthetic", "ruler_name": "合成对象", "score_ready": True,
        "axes": {name: {"start_grade": 2, "end_grade": 2, "objective_delta": 0}
                 for name in ("A1", "A2")},
        "A120_points": 0, "B80_adjudication": {"B80_points": 0},
    }
    payloads = {settlement.AB_PATH: {"records": [row]},
                settlement.RESULT_CREDIT_ADJUDICATIONS_PATH: {"records": [adjudication]},
                settlement.AB_HANDOFF_ADJUDICATIONS_PATH: {}}
    monkeypatch.setattr(settlement, "_load", lambda path: payloads[path.relative_to(tmp_path)])
    monkeypatch.setattr(settlement, "_load_a_axis_narrative_adjudications", lambda root: {})
    # Scoring and evidence validation have separate tests; isolate the write boundary.
    for name in ("_validate_result_credit_contract", "_validate_ab_control_contribution_contract",
                 "_validate_ab_axis_narratives"):
        monkeypatch.setattr(settlement, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(settlement, "_decompose_a120_axis", lambda *args: (0, 0))
    monkeypatch.setattr(settlement, "load_ruler_polities", lambda root: {})
    saved = []
    monkeypatch.setattr(settlement, "write_json", lambda path, payload, **kwargs: saved.append(deepcopy(payload)))
    monkeypatch.setattr(rendering, "_render_formal_markdown", lambda *args, **kwargs: "")
    monkeypatch.setattr(settlement, "_write_text_atomic", lambda *args: None)

    settlement._synchronize_current_ab_view(tmp_path)
    settlement._validate_current_ab_score_fields(saved[-1])
    for name in ("A1", "A2"):
        assert row["axes"][name]["end"] == settlement._a_axis_state_fields(name, adjudication["axes"][name])["end"]
        assert "axis_points" not in row["axes"][name]
    first = saved[-1]
    settlement._synchronize_current_ab_view(tmp_path)
    assert saved[-1] == first


def _shared_window_payloads():
    scope = {axis: f"synthetic {axis}" for axis in ("A", "B", "C", "D")}
    reviews = {
        "li": {
            "review_id": "synthetic-shared-window",
            "status": "REVIEWED_SHARED_POWER_SINGLE_ACCOUNTING_OWNER",
            "component_scope": scope,
        },
        "wu": {
            "review_id": "synthetic-shared-window",
            "status": "REVIEWED_SHARED_POWER_SINGLE_ACCOUNTING_OWNER",
            "component_scope": scope,
        },
    }
    windows = {
        "li": [{"start": 1, "end": 2, "status": "ACCOUNTING_OWNER"}],
        "wu": [{"start": 1, "end": 2, "status": "NON_ACCOUNTING_OWNER"}],
    }
    rows = [
        {
            "ruler_id": "li",
            "ruler_name": "合成甲",
            "active_rule_windows": windows["li"],
            "overlapping_subject_window_review": reviews["li"],
        },
        {
            "ruler_id": "wu",
            "ruler_name": "合成乙",
            "active_rule_windows": windows["wu"],
            "overlapping_subject_window_review": reviews["wu"],
        },
    ]
    return {component: {"records": json.loads(json.dumps(rows))} for component in ("AB", "C", "D", "result_credit")}


def test_shared_power_window_requires_one_synchronized_component_review(tmp_path):
    path = tmp_path / "config/common/canonical-ruler-pool.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "ruler_id": "li",
                        "ruler_name": "合成甲",
                        "pool_status": "INCLUDED",
                        "actual_power_window": "1—2年与合成乙共享权力",
                        "actual_power_window_adjudication": {
                            "third_item_overlap_status": "COMPONENT_REVIEW_COMPLETE",
                            "overlap_review_id": "synthetic-shared-window",
                            "overlapping_ruler_ids": ["li", "wu"],
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    payloads = _shared_window_payloads()
    _validate_overlapping_subject_windows(tmp_path, payloads)
    payloads["D"]["records"][1].pop("overlapping_subject_window_review")
    with pytest.raises(ValueError, match="统一review_id"):
        _validate_overlapping_subject_windows(tmp_path, payloads)
