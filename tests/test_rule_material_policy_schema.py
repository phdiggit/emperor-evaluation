from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "db" / "migrations" / "20260704_eval_rule_material_policies.sql"


def migration_sql() -> str:
    assert MIGRATION_PATH.exists()
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def test_rule_material_policy_migration_creates_policy_table() -> None:
    sql = migration_sql()

    assert "create table if not exists public.eval_rule_material_policies" in sql
    assert "rule_id bigint references public.eval_rules(id)" in sql
    assert "allowed_scoring_roles text[] not null" in sql
    assert "candidate_obj_types text[] not null" in sql
    assert "require_attrs text[] not null" in sql
    assert "calc_detail_component_paths text[] not null" in sql
    assert "policy_payload jsonb not null" in sql
    assert "create view public.v_eval_rule_material_policies_by_id" in sql


def test_rule_material_policy_migration_seeds_team_building_special_policy() -> None:
    sql = migration_sql()

    assert "'team_building'" in sql
    assert "'team_core_member_policy'" in sql
    assert "array['person']::text[]" in sql
    assert "array['talent_quality']::text[]" in sql
    assert "array['team_quality_components','materials']::text[]" in sql
    assert "selection_priority" in sql
    assert "数字越小优先级越高" in sql


def test_rule_material_policy_migration_documents_runtime_contract() -> None:
    sql = migration_sql()

    assert "运行时代码只读本表，不读取评分规则文档" in sql
    for column in [
        "policy_code",
        "policy_version",
        "selection_priority",
        "carrier_mode",
        "material_source",
        "allowed_scoring_roles",
        "context_roles",
        "disallowed_scored_obj_types",
        "discouraged_scored_obj_types",
        "candidate_obj_types",
        "require_attrs",
        "calc_detail_component_paths",
        "single_scored_per_chain",
        "policy_payload",
    ]:
        assert f"comment on column public.eval_rule_material_policies.{column} is" in sql
