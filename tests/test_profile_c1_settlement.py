from __future__ import annotations

from pathlib import Path

from emperor_v4.evaluation.profile_c1_verifier import verify


ROOT = Path(__file__).resolve().parents[1]


def test_c1_formal_settlement_passes_semantic_and_structural_gates() -> None:
    result = verify(ROOT)
    assert result["status"] == "PASS"
    assert result["record_count"] == 184
    assert result["unresolved_count"] == 0
    assert result["scoring_parent_count"] > 0
