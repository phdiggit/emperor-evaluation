from __future__ import annotations

from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
SQL=(ROOT/'db/migrations/20260712_retrieval_v3_downstream_event_dedupe.sql').read_text(encoding='utf-8')


def test_every_downstream_scoring_layer_inherits_event_identity() -> None:
    for table in ('claim_rule_binding_candidates','claim_rule_bindings','claim_rule_binding_factor_judgments','claim_rule_binding_material_scores'):
        assert f'alter table retrieval_v3.{table} add column if not exists canonical_event_key' in SQL
        assert table in SQL
    assert 'inherit_material_canonical_event_key' in SQL


def test_downstream_layers_have_database_unique_event_gates() -> None:
    for index in ('rv3_binding_candidates_event_rule_uk','rv3_bindings_event_rule_uk','rv3_factor_judgments_event_rule_uk','rv3_material_scores_event_rule_uk','rv3_score_clusters_target_rule_formula_uk'):
        assert index in SQL
