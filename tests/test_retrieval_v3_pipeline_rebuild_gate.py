from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "db/migrations/20260712_retrieval_v3_pipeline_rebuild_gate.sql").read_text(encoding="utf-8")


def test_rebuild_gate_covers_every_mutable_pipeline_stage() -> None:
    for table in (
        "claim_cache", "claim_event_groups", "material_claims", "claim_source_passages",
        "material_object_links", "claim_rule_routes", "claim_route_cache",
        "claim_rule_binding_candidates", "claim_rule_bindings",
        "claim_rule_binding_factor_judgments", "claim_rule_binding_factor_choices",
        "claim_rule_binding_material_scores", "target_rule_score_clusters",
    ):
        assert f"array['{table}'" in SQL


def test_rebuild_gate_requires_explicit_transaction_bypass() -> None:
    assert "retrieval_v3.rebuild_bypass" in SQL
    assert "pipeline rebuild gate blocks" in SQL
    assert "gate_status = 'active'" in SQL
