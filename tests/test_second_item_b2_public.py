from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import pytest

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_b2_public import (
    B2_PATH,
    PUBLIC_FORBIDDEN_RE,
    _refresh_payload,
    _scoring_signature,
    _group_profiles,
    _stable_id,
    _public_direction,
    verify_public_projection,
)


def _profile(*, direction: str, weight: float, mechanism: str, lifecycle: str | None = None) -> dict:
    row = {
        "M": "M2",
        "direction": direction,
        "direction_factor": 1.0 if weight >= 0 else -1.0,
        "signed_weight": weight,
        "material_id": mechanism,
        "mechanism": mechanism,
        "result_closure": "observed_or_repeated",
    }
    if lifecycle:
        row["lifecycle_key"] = lifecycle
    return row


def _row() -> dict:
    row = {
        "ruler_id": "SYNTHETIC-B2-RULER",
        "ruler_name": "合成甲",
        "grade": "G2",
        "position": "middle",
        "direction_index": 38.0,
        "rank": 1,
        "grade_basis": "一条M2反馈链实际改变决策，另一阶段形成负向约束；主档G2，生命周期只计算一次。",
        "M_positive_profile": [
            _profile(direction="positive", weight=1.0, mechanism="外部意见改变处置", lifecycle="L1"),
            _profile(direction="positive", weight=1.0, mechanism="低位信息进入中枢"),
        ],
        "M_mixed_profile": [
            _profile(direction="mixed_positive", weight=0.5, mechanism="同一反馈链的纠偏与保护", lifecycle="L1"),
        ],
        "M_negative_profile": [
            _profile(direction="negative", weight=-1.0, mechanism="反馈者受到压制", lifecycle="L2"),
        ],
    }
    row['public_adjudication_summary'] = '外部意见使处置改变，但另一阶段反馈者受到压制；实际纠正与安全风险并存。'
    row['public_evidence_items'] = [
        dict(id=_stable_id(row, key), public_label=f'合成机制{i}',
             public_direction=_public_direction(group), public_tags=['反馈与纠错'],
             public_basis='合成意见进入决策，处置发生改变，仍保留另一阶段的安全限制。',
             public_boundary='同一过程只评价一次。',
             source_refs=[dict(path='docs/公共成果/制度行政/01-制度行政计分材料登记/synthetic.json',
                               material_id=profile['material_id'],source_title='正式材料登记',
                               source_locator='',source_url='',exact_quote='') for profile in group])
        for i,(key,group) in enumerate(_group_profiles(row).items())
    ]
    return row


def _sources(root, row):
    path = root / 'docs/公共成果/制度行政/01-制度行政计分材料登记/synthetic.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'records':[{'material_id':p['material_id']} for group in _group_profiles(row).values() for p in group]}),encoding='utf-8')


def test_b2_public_projection_preserves_authored_prose_and_all_declared_groups(tmp_path):
    payload = {"records": [_row()]}
    before = deepcopy(payload)
    projected = _refresh_payload(payload)
    row = projected["records"][0]

    assert len(row["public_evidence_items"]) == 3
    assert row["public_evidence_items"][0]["public_direction"] == "正向主导"
    assert row["public_evidence_items"][1]["public_direction"] == "正向"
    assert _scoring_signature(projected) == _scoring_signature(before)
    assert not PUBLIC_FORBIDDEN_RE.search(row["public_adjudication_summary"])
    assert all(
        not PUBLIC_FORBIDDEN_RE.search(field)
        for item in row["public_evidence_items"]
        for key in ("public_label", "public_basis", "public_boundary")
        for field in [item[key]]
    )
    _sources(tmp_path,row)
    assert row['public_adjudication_summary'] == before['records'][0]['public_adjudication_summary']
    assert row['public_evidence_items'] == before['records'][0]['public_evidence_items']
    assert _refresh_payload(deepcopy(projected)) == projected
    assert verify_public_projection(tmp_path, projected)["public_evidence_item_count"] == len(_group_profiles(row))


def test_b2_refresh_fails_without_authored_text():
    row = _row()
    del row['public_adjudication_summary']
    with pytest.raises(ValueError,match='公开定档理由'):
        _refresh_payload({'records':[row]})


def test_b2_effective_group_cannot_be_marked_as_wholly_background(tmp_path):
    row = _row()
    row['M_mixed_profile'][0]['signed_weight'] = 0
    item = row['public_evidence_items'][0]
    item['public_direction'] = _public_direction(list(_group_profiles(row).values())[0])
    item['public_tags'] = ['部分阶段不另计']
    _sources(tmp_path,row)
    projected = _refresh_payload({'records':[row]})
    verify_public_projection(tmp_path,projected)
    projected['records'][0]['public_evidence_items'][0]['public_tags'].append('背景材料')
    with pytest.raises(ValueError,match='整条背景'):
        verify_public_projection(tmp_path,projected)


def test_b2_source_identity_must_match_bound_material(tmp_path):
    row = _row()
    _sources(tmp_path,row)
    projected = _refresh_payload({'records':[row]})
    projected['records'][0]['public_evidence_items'][0]['source_refs'][0]['material_id']='unbound'
    with pytest.raises(ValueError,match='材料身份'):
        verify_public_projection(tmp_path,projected)


def test_full_pool_reading_collection_preserves_current_public_text():
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('b2_reader_build',root/'reader/build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from html import escape
    text = module.render_second_b2_collection(root)
    payload = load_json(root/B2_PATH)
    assert text.count('<article id=') == len(payload['records'])
    for row in payload['records']:
        assert escape(row['public_adjudication_summary']) in text
        for item in row['public_evidence_items']:
            assert escape(item['public_basis']) in text
            assert escape(item['public_boundary']) in text
            assert item['id'] in text
