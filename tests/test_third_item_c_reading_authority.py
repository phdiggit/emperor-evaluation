"""Keep authored C reading in formal records across deterministic reconstruction."""
from copy import deepcopy
import json

import pytest

from emperor_v4.evaluation.third_item_c_strategy_chain import (
    C_PATH, SOURCE_PATH, apply_strategy_chain_writeback_to_payload, load_strategy_chain_source,
)


def inputs():
    formal = {"records": [{"ruler_id": "synthetic", "public_reading": {
        "story": "Authored account", "source_reviews": [{"quote": "Evidence excerpt"}],
    }}]}
    rebuilt = {"records": [{"ruler_id": "synthetic", "score": -1,
                             "public_reading": {"story": "Obsolete generated text"}}]}
    source = {
        "schema_version": "third-item-c-strategy-chain-adjudications-v2",
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


def test_duplicate_writeback_reading_is_rejected():
    formal, rebuilt, source = inputs()
    source["records"][0]["formal_writeback"]["fields"]["public_reading"] = {"story": "Duplicate"}
    with pytest.raises(ValueError, match="不得存入战略链写回源"):
        apply_strategy_chain_writeback_to_payload(rebuilt, source, formal_payload=formal)


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
    for path, payload in ((C_PATH, formal), (SOURCE_PATH, source)):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")
    assert load_strategy_chain_source(tmp_path) == source
    source["public_reading_source"] = "unregistered.json"
    (tmp_path / SOURCE_PATH).write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="正文来源必须"):
        load_strategy_chain_source(tmp_path)
