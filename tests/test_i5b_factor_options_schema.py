from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "db" / "migrations" / "20260702_eval_rule_factor_options.sql"


def migration_sql() -> str:
    assert MIGRATION_PATH.exists()
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_factor_option_migration_creates_structured_factor_tables() -> None:
    sql = migration_sql().lower()

    assert "create table if not exists public.eval_rule_factors" in sql
    assert "create table if not exists public.eval_rule_factor_options" in sql
    assert "references public.eval_items(id)" in sql
    assert "references public.eval_rules(id)" in sql
    assert "references public.eval_rule_factors(id) on delete cascade" in sql


def test_factor_option_migration_keeps_doc_sync_lookup_contract() -> None:
    sql = migration_sql().lower()

    assert "item_code text not null" in sql
    assert "rule_code text not null default ''" in sql
    assert "formula_code text not null" in sql
    assert "factor_name text not null" in sql
    assert "source_doc text not null default ''" in sql
    assert "description text not null default ''" in sql
    assert "note text not null default ''" in sql
    assert "source_line integer" in sql
    assert "on public.eval_rule_factors(item_code, rule_code, formula_code, factor_name)" in sql
    assert "on public.eval_rule_factor_options(factor_id, label)" in sql


def test_factor_option_migration_exposes_human_review_views_and_scope_checks() -> None:
    sql = migration_sql().lower()

    assert "create view public.v_eval_rule_factors_by_id" in sql
    assert "create view public.v_eval_rule_factor_options_by_id" in sql
    assert "eval_rule_factors_scope_known" in sql
    assert "comment on column public.eval_rule_factors.description is" in sql
    assert "comment on column public.eval_rule_factor_options.note is" in sql
    assert "不复制到每个取值行" in migration_sql()
    assert "不存因子级整段说明" in migration_sql()
    for scope in ["'default'", "'shared'", "'rule'", "'attribute_mapping'", "'team'", "'retired'"]:
        assert scope in sql
