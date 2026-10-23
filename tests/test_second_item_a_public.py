"""Contract checks use synthetic records; historical verdicts are not fixtures."""
from copy import deepcopy

import pytest

from emperor_v4.evaluation.second_item_a_public import (
    PUBLIC_PROJECTION_SCHEMA, _public_nodes, _refresh_payload,
    _scoring_signature, _verify_ref, public_markdown,
)
from emperor_v4.evaluation.formal_settlements import _verify_a_profile_registry_binding


@pytest.mark.parametrize("strength,direction,effect,minus,weight", [
    ("M2", "positive", "S+", 0, 2),
    ("M3", "positive", "S++", 0, 4),
    ("M3", "negative", "S-1", 1, -3),
    ("M3", "mixed_positive", "NON_S", 0, 1),
])
def test_registered_profile_uses_contract_base_and_durability_bonus(
    strength, direction, effect, minus, weight,
):
    nodes = {"SYNTHETIC": {"counts_toward_A": True,
        "counts_toward_S": effect != "NON_S", "S_effect": effect,
        "S_minus_weight": minus, "material_ids": ["SYNTHETIC-MATERIAL"]}}
    profile = {"institution_node_id": "SYNTHETIC", "M": strength,
        "direction": direction, "signed_weight": weight}
    _verify_a_profile_registry_binding("合成甲", profile, nodes)
    profile["signed_weight"] = weight + 0.5
    with pytest.raises(ValueError, match="任内基值与S溢价"):
        _verify_a_profile_registry_binding("合成甲", profile, nodes)


def test_profile_reference_cannot_score_and_retired_identity_cannot_reenter():
    nodes = {"CURRENT": {"counts_toward_A": False}}
    profile = {"institution_node_id": "CURRENT", "signed_weight": 0}
    _verify_a_profile_registry_binding("合成甲", profile, nodes)
    profile["signed_weight"] = 1
    with pytest.raises(ValueError, match="参考节点仍被计权"):
        _verify_a_profile_registry_binding("合成甲", profile, nodes)
    profile.update(institution_node_id="RETIRED", signed_weight=0)
    with pytest.raises(ValueError, match="未登记或仍使用别名"):
        _verify_a_profile_registry_binding("合成甲", profile, nodes)


def test_weighted_profile_requires_material_binding():
    nodes = {"SYNTHETIC": {"counts_toward_A": True, "counts_toward_S": False}}
    profile = {"institution_node_id": "SYNTHETIC", "M": "M2",
        "direction": "positive", "signed_weight": 1}
    with pytest.raises(ValueError, match="缺少登记材料"):
        _verify_a_profile_registry_binding("合成甲", profile, nodes)


def test_factual_reference_is_not_presented_as_offsetting_proven_gains_and_losses():
    row = payload()["records"][0]
    row["M_positive_profile"][0].update(direction="neutral", signed_weight=0)
    row["public_institution_nodes"][0].update(public_direction="事实参考", signed_weight=0)
    assert _public_nodes(row)[0]["public_direction"] == "事实参考"


def payload():
    node = {
        "institution_node_id":"SYNTHETIC-NODE", "public_label":"文书复核",
        "public_direction":"正向", "public_tags":["局部建设"], "signed_weight":1,
        "public_adjudication_basis":"本人设置文书复核，由指定官员实际办理。但不证明所有案件均无差错。",
        "public_boundary":None, "public_reception":"只证明任内办理，后继采用尚缺证据。",
        "public_sources":[{"label":"合成证据", "ref":"evidence.json#material_id=SYNTHETIC-MATERIAL"}],
        "public_material_ids":["SYNTHETIC-MATERIAL"],
    }
    return {"public_projection_schema_version":PUBLIC_PROJECTION_SCHEMA, "records":[{
        "ruler_id":"SYNTHETIC-RULER", "ruler_name":"合成甲",
        "grade":"G2", "position":"lower", "direction_index":40, "rank":1,
        "P_gross":1, "N_gross":0, "A_net_units":1,
        "important_institutions":[{"institution_node_id":"SYNTHETIC-NODE", "normative_direction":"negative"}],
        "M_positive_profile":[{"institution_node_id":"SYNTHETIC-NODE", "direction":"positive", "signed_weight":1, "material_ids":["SYNTHETIC-MATERIAL"]}],
        "M_mixed_profile":[], "M_negative_profile":[],
        "public_story":"本人建立文书复核组织。",
        "public_adjudication_summary":"有限建设已经运行，长期范围不明，支持C级下位。",
        "public_boundary":"只评价该制度改变。",
        "public_institution_nodes":[node], "public_evidence_items":[],
    }]}


def test_projection_preserves_authored_prose_and_all_scoring_fields(tmp_path):
    original = payload()
    result = _refresh_payload(deepcopy(original), tmp_path)
    assert _scoring_signature(result) == _scoring_signature(original)
    row = result["records"][0]
    assert row["public_story"] == original["records"][0]["public_story"]
    assert row["public_adjudication_summary"] == original["records"][0]["public_adjudication_summary"]
    assert row["public_evidence_items"][0]["public_basis"] == row["public_institution_nodes"][0]["public_adjudication_basis"]
    assert _refresh_payload(deepcopy(result), tmp_path) == result
    assert row["public_story"] in public_markdown(result)
    assert row["public_adjudication_summary"] in public_markdown(result)


@pytest.mark.parametrize("field", ["public_story", "public_adjudication_summary"])
def test_missing_authored_words_fail_closed(tmp_path, field):
    data = payload()
    data["records"][0].pop(field)
    with pytest.raises(ValueError, match="人工正文"):
        _refresh_payload(data, tmp_path)


@pytest.mark.parametrize("text", ["该节点被判断为重构，已有材料支持。", "不在本节点中判断正负方向", "制度净值为1", "M2运行"])
def test_stale_or_technical_copy_is_rejected_not_rewritten(tmp_path, text):
    data = payload()
    data["records"][0]["public_institution_nodes"][0]["public_adjudication_basis"] = text
    with pytest.raises(ValueError, match="人工正文"):
        _refresh_payload(data, tmp_path)
    assert data["records"][0]["public_institution_nodes"][0]["public_adjudication_basis"] == text


@pytest.mark.parametrize("key,value", [("signed_weight",2), ("public_direction","负向"), ("institution_node_id","UNKNOWN")])
def test_public_node_cannot_override_formal_identity_direction_or_weight(key,value):
    data = payload()
    row = data["records"][0]
    row["public_institution_nodes"][0][key] = value
    with pytest.raises(ValueError):
        _public_nodes(row)


def test_no_nodes_is_an_empty_list_not_a_counted_explanation_card(tmp_path):
    data = payload()
    row = data["records"][0]
    row.update(important_institutions=[], M_positive_profile=[], public_institution_nodes=[])
    result = _refresh_payload(data, tmp_path)
    assert result["records"][0]["public_evidence_items"] == []
    assert result["records"][0]["public_story"]


def test_source_anchor_resolves_and_missing_anchor_or_path_is_rejected(tmp_path):
    (tmp_path/"evidence.json").write_text('{"records":[{"material_id":"SYNTHETIC-MATERIAL","facts":["原句"]}]}',encoding="utf-8")
    _verify_ref(tmp_path,"evidence.json#material_id=SYNTHETIC-MATERIAL/facts/0")
    for ref in ["evidence.json#material_id=UNKNOWN", "missing.json", "../escape.json", "javascript:alert(1)"]:
        with pytest.raises(ValueError): _verify_ref(tmp_path,ref)
