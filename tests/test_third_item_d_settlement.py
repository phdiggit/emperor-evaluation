from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from emperor_v4.evaluation.formal_json_store import load_json

from emperor_v4.evaluation.third_item_d_settlement import (
    FORMAL_SETTLEMENT_JSON_PATH,
    validate_third_item_d_payload,
    verify_third_item_d_formal_settlement,
)


ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict:
    return load_json(ROOT / FORMAL_SETTLEMENT_JSON_PATH)


def test_third_item_d_formal_snapshot_passes_lightweight_verifier() -> None:
    result = verify_third_item_d_formal_settlement(ROOT)
    assert result["status"] == "PASS"
    assert result["record_count"] == 201
    assert result["strategic_chain_count"] == 720
    assert result["excluded_chain_count"] == 18


def test_mongol_yuan_unification_precursor_chains_exit_d_whole() -> None:
    rows = {row["ruler_id"]: row for row in _payload()["records"]}
    expected = {
        "RULER-YUAN-TEMUJI": {"MONGOL-JIN-1211-1215", "MONGOL-XIXIA-1226-1227"},
        "RULER-YUAN-OGEDEI": {"CHAIN-OGEDEI-JIN-1231-1234", "CHAIN-OGEDEI-DONGXIA-1233"},
    }
    for ruler_id, excluded_ids in expected.items():
        row = rows[ruler_id]
        actual_excluded = {
            chain["chain_id"] for chain in row["cross_item_excluded_chains"]
        }
        active = {
            chain["chain_id"] for chain in row["external_strategic_chains"]
        }
        assert excluded_ids <= actual_excluded
        assert excluded_ids.isdisjoint(active)


def test_third_item_d_rejects_grade_score_mismatch() -> None:
    payload = copy.deepcopy(_payload())
    payload["records"][0]["D_score_points"] += 1
    with pytest.raises(ValueError, match="点值与档位不一致"):
        validate_third_item_d_payload(payload)


def test_third_item_d_rejects_duplicate_ruler_id() -> None:
    payload = copy.deepcopy(_payload())
    payload["records"][1]["ruler_id"] = payload["records"][0]["ruler_id"]
    with pytest.raises(ValueError, match="重复人物ID"):
        validate_third_item_d_payload(payload)
