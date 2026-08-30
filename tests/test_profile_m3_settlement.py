from __future__ import annotations

import copy
import json

import pytest

from emperor_v4.evaluation.profile_m3_settlement import (
    GRADE_PROJECTION,
    M3_MARKDOWN,
    M3_SETTLEMENT,
)
from emperor_v4.evaluation.profile_m3_settlement import build
from emperor_v4.evaluation.profile_m3_verifier import verify, verify_payload
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_profile_m3_formal_snapshot_passes_lightweight_verifier() -> None:
    result = verify()
    assert result["status"] == "PASS"
    assert result["record_count"] == 184
    assert sum(result["grade_distribution"].values()) == 184


def test_profile_m3_scores_are_mechanical_projection_of_stored_decisions() -> None:
    settlement = _load(M3_SETTLEMENT)
    for row in settlement["records"]:
        expected = GRADE_PROJECTION[(row["axis_grade"], row["position"])]
        assert row["score_100"] == row["radar_value"] == expected


def test_profile_m3_rejects_local_hard_constraint_breakage() -> None:
    settlement = _load(M3_SETTLEMENT)
    broken = copy.deepcopy(settlement)
    broken["records"][0]["score_100"] = -1
    with pytest.raises(ValueError, match="score projection mismatch"):
        verify_payload(broken)


def test_profile_m3_compiler_reads_formal_snapshot_without_readjudication() -> None:
    before = M3_SETTLEMENT.read_bytes()
    settlement = build(write=False)["settlement"]
    assert M3_SETTLEMENT.read_bytes() == before
    assert M3_MARKDOWN.read_text(encoding="utf-8") == render_profile_markdown(settlement)
