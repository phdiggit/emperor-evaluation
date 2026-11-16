"""Keep authored C reading in formal records across deterministic reconstruction."""
from copy import deepcopy
import json

import pytest

from emperor_v4.evaluation.third_item_c_strategy_chain import (
    C_PATH, SOURCE_PATH, SOURCE_SCHEMA, apply_strategy_chain_writeback_to_payload,
    compact_strategy_chain_source, load_strategy_chain_source,
)


def inputs():
    formal = {"records": [{"ruler_id": "synthetic", "public_reading": {
        "story": "Authored account", "source_reviews": [{"quote": "Evidence excerpt"}],
    }}]}
    rebuilt = {"records": [{"ruler_id": "synthetic", "score": -1,
                             "public_reading": {"story": "Obsolete generated text"}}]}
    source = {
        "schema_version": SOURCE_SCHEMA,
        "public_reading_source": C_PATH.as_posix(),
        "canonical_status": "FORMAL_SETTLEMENT_PATCH_SOURCE", "status": "CURRENT",
        "primary_scoring_unit": "STRATEGIC_CHAIN",
        "parent_cycle_role": "EVIDENCE_ONLY_AND_DISPUTE_DRILLDOWN",
        "records": [{"ruler_id": "synthetic", "formal_writeback": {"fields": {"score": 7}}}],
    }
    return formal, rebuilt, source


def test_reconstruction_preserves_formal_reading_without_mutating_inputs():
    formal, rebuilt, source = inputs()
    baseline = deepcopy((formal, rebuilt, source))
    output = apply_strategy_chain_writeback_to_payload(rebuilt, source, formal_payload=formal)
    assert output["records"][0]["score"] == 7
    assert output["records"][0]["public_reading"] == formal["records"][0]["public_reading"]
    assert apply_strategy_chain_writeback_to_payload(output, source, formal_payload=formal) == output
    output["records"][0]["public_reading"]["source_reviews"].clear()
    assert (formal, rebuilt, source) == baseline


def test_formal_c_writer_uses_the_same_utf8_lf_bytes_as_generated_packaging(monkeypatch, tmp_path):
    from emperor_v4.evaluation import third_item_c_strategy_chain as settlement
    from emperor_v4.evaluation import five_dynasties_third_item as rendering
    from emperor_v4.evaluation import third_item_c_contract_reading as review
    formal,_,source=inputs()
    path=tmp_path/C_PATH
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(formal),encoding='utf-8')
    monkeypatch.setattr(settlement,'load_strategy_chain_source',lambda root:source)
    monkeypatch.setattr(settlement,'load_ruler_polities',lambda root:{})
    monkeypatch.setattr(review,'load_context',lambda root:{})
    text='# 合成阅读视图\n\n保留原文与来源。\n'
    monkeypatch.setattr(rendering,'_render_formal_markdown',lambda *args,**kwargs:text)
    settlement.write_third_item_c_strategy_chain_settlement(tmp_path)
    assert path.with_suffix('.md').read_bytes()==text.encode('utf-8')


def test_duplicate_writeback_reading_is_rejected():
    formal, rebuilt, source = inputs()
    source["records"][0]["formal_writeback"]["fields"]["public_reading"] = {"story": "Duplicate"}
    with pytest.raises(ValueError, match="不得存入战略链写回源"):
        apply_strategy_chain_writeback_to_payload(rebuilt, source, formal_payload=formal)


@pytest.mark.parametrize('alias', ['raw_grade', 'C_overall_grade'])
@pytest.mark.parametrize('location', ['source', 'formal', 'rebuilt'])
def test_reconstruction_rejects_retired_grade_aliases_in_every_input(alias, location):
    formal, rebuilt, source = inputs()
    target = (source['records'][0]['formal_writeback']['fields'] if location=='source'
              else (formal if location=='formal' else rebuilt)['records'][0])
    target.update(axis_floor_grade='C-3', final_grade='C-3')
    target[alias]='C-3'
    before=deepcopy((formal,rebuilt,source))
    with pytest.raises(ValueError, match='不得保存重复别名'):
        apply_strategy_chain_writeback_to_payload(rebuilt,source,formal_payload=formal)
    assert (formal,rebuilt,source)==before


@pytest.mark.parametrize("fault", ["missing_reading", "missing_identity", "duplicate_identity", "other_identity"])
def test_invalid_formal_reading_cannot_fall_back_to_generated_text(fault):
    formal, rebuilt, source = inputs()
    if fault == "missing_reading":
        formal["records"][0].pop("public_reading")
    elif fault == "missing_identity":
        formal["records"][0].pop("ruler_id")
    elif fault == "duplicate_identity":
        formal["records"].append(deepcopy(formal["records"][0]))
    else:
        formal["records"][0]["ruler_id"] = "other"
    with pytest.raises(ValueError):
        apply_strategy_chain_writeback_to_payload(rebuilt, source, formal_payload=formal)


def test_loader_uses_declared_formal_reading_authority(tmp_path):
    formal, _, source = inputs()
    fields = source["records"][0]["formal_writeback"]["fields"]
    basis = '同一出处作为两个不同任务的证据，先后关系和逐条归责均保留。'
    fields.update(
        combat_delivery_grade="C1-2",
        joint_assessment={"position": "MID", "position_basis": basis},
        current_item_task_refs=["parent"],
        strategy_chains=[{"chain_id": "a", "basis": basis, "major_system_success": True, "member_parent_refs": ["parent"]},
                         {"chain_id": "b", "basis": basis}],
        capability_only_strategy_chains=[],
    )
    storage = compact_strategy_chain_source(source)
    for path, payload in ((C_PATH, formal), (SOURCE_PATH, storage)):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")
    expanded = load_strategy_chain_source(tmp_path)
    result = expanded["records"][0]["formal_writeback"]["fields"]
    assert result["strategy_chains"] == fields["strategy_chains"]
    assert result["strategy_chain_refs"] == ["a", "b"]
    assert result["major_system_success_refs"] == ["parent"]
    assert result["final_grade"] == "C-2"
    assert result["C_score_points"] == 26
    assert result["C_score_within_band_adjudication"] == {"position": "MID", "reason": basis}
    assert compact_strategy_chain_source(expanded) == storage

    storage["records"][0]["formal_writeback"]["fields"]["C_score_points"] = 26
    (tmp_path / SOURCE_PATH).write_text(json.dumps(storage), encoding="utf-8")
    with pytest.raises(ValueError, match="不得保存派生字段"):
        load_strategy_chain_source(tmp_path)
    storage["public_reading_source"] = "unregistered.json"
    (tmp_path / SOURCE_PATH).write_text(json.dumps(storage), encoding="utf-8")
    with pytest.raises(ValueError, match="正文来源必须"):
        load_strategy_chain_source(tmp_path)
