from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "db" / "migrations" / "20260702_rule_evidence_units_shadow.sql"


def migration_sql() -> str:
    assert MIGRATION_PATH.exists()
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def test_rule_evidence_unit_migration_creates_shadow_relation_tables() -> None:
    sql = migration_sql()

    assert "create table if not exists public.fact_relations" in sql
    assert "create table if not exists public.fact_relation_predicate_options" in sql
    assert "create table if not exists public.rule_evidence_units" in sql
    assert "create table if not exists public.rule_evidence_unit_members" in sql
    assert "references public.raw_objs(id)" in sql
    assert "references public.obj_srcs(id)" in sql


def test_rule_evidence_unit_migration_keeps_shadow_mode_contract() -> None:
    sql = migration_sql()

    assert "create domain public.eval_lifecycle_status as text" in sql
    assert "create domain public.eval_review_status as text" in sql
    assert "create domain public.eval_source_method as text" in sql
    assert "create domain public.evidence_direction as text" in sql
    assert "create domain public.rule_evidence_score_mode as text" in sql
    assert "score_mode public.rule_evidence_score_mode not null default 'shadow'" in sql
    assert "value in (''shadow'', ''scoring'', ''rejected'')" in sql
    assert "source_method public.eval_source_method not null default 'manual'" in sql
    assert "review_status public.eval_review_status not null default 'draft'" in sql
    assert "value in (''draft'', ''needs_review'', ''accepted'', ''rejected'')" in sql
    assert "status public.eval_lifecycle_status not null default 'active'" in sql
    assert "direction public.evidence_direction not null" in sql
    assert "causal_chain_key text not null" in sql
    assert "scoring_role text not null" in sql
    assert "member_role text not null" in sql
    assert "alter column status type public.eval_lifecycle_status" in sql
    assert "drop constraint if exists rule_evidence_units_status_known" in sql


def test_rule_evidence_unit_migration_exposes_review_views() -> None:
    sql = migration_sql()

    assert "create view public.v_fact_relations_by_id" in sql
    assert "create view public.v_fact_relation_predicate_options_by_id" in sql
    assert "create view public.v_rule_evidence_units_by_id" in sql
    assert "create view public.v_rule_evidence_unit_members_by_id" in sql
    assert "规则承载对象影子层" in sql
    assert "display_note" in sql
    assert "comment on column public.v_fact_relations_by_id.display_note is" in sql
    assert "comment on column public.v_rule_evidence_units_by_id.display_note is" in sql
    assert "comment on column public.v_rule_evidence_unit_members_by_id.display_note is" in sql


def test_rule_evidence_unit_migration_comments_stable_domains() -> None:
    sql = migration_sql()

    assert "comment on domain public.eval_lifecycle_status is" in sql
    assert "comment on domain public.eval_review_status is" in sql
    assert "comment on domain public.eval_source_method is" in sql
    assert "comment on domain public.evidence_direction is" in sql
    assert "comment on domain public.rule_evidence_score_mode is" in sql


def test_rule_evidence_unit_migration_comments_every_table_column() -> None:
    sql = migration_sql()
    expected_columns = {
        "fact_relations": [
            "id",
            "emp_id",
            "item_id",
            "item_code",
            "rule_id",
            "rule_code",
            "subject_obj_id",
            "predicate",
            "object_obj_id",
            "doc_id",
            "obj_src_id",
            "causal_chain_key",
            "relation_role",
            "confidence",
            "source_method",
            "review_status",
            "review_note",
            "note",
            "status",
            "created_at",
            "updated_at",
        ],
        "fact_relation_predicate_options": [
            "id",
            "item_id",
            "item_code",
            "rule_id",
            "rule_code",
            "scoring_role",
            "predicate",
            "relation_role",
            "subject_obj_type",
            "object_obj_type",
            "direction",
            "description",
            "note",
            "status",
            "created_at",
            "updated_at",
        ],
        "rule_evidence_units": [
            "id",
            "emp_id",
            "item_id",
            "item_code",
            "rule_id",
            "rule_code",
            "causal_chain_key",
            "scored_obj_id",
            "scored_obj_src_id",
            "scoring_role",
            "direction",
            "score_mode",
            "source_method",
            "review_status",
            "review_note",
            "note",
            "status",
            "created_at",
            "updated_at",
        ],
        "rule_evidence_unit_members": [
            "id",
            "unit_id",
            "obj_id",
            "obj_src_id",
            "relation_id",
            "member_role",
            "source_method",
            "review_status",
            "review_note",
            "note",
            "status",
            "created_at",
            "updated_at",
        ],
    }

    for table_name, columns in expected_columns.items():
        for column_name in columns:
            assert f"comment on column public.{table_name}.{column_name} is" in sql


def test_fact_relation_notes_remain_sparse_structured_fields() -> None:
    sql = migration_sql()
    seed_block = sql.split("with seed", 1)[1].split("insert into public.fact_relation_predicate_options", 1)[0]

    assert "note" not in seed_block
    assert "set note = ''" in sql
    assert "set review_note = ''" in sql
    assert "不存模板展示句" in sql
    assert "默认留空" in sql
    assert "候选承载对象：%" in sql
    assert "候选上下文成员：%" in sql


def test_rule_evidence_unit_migration_seeds_i5b_fact_relation_predicates() -> None:
    sql = migration_sql()

    assert "insert into public.fact_relation_predicate_options" in sql
    assert "('anti_nepotism', 'favorite_beneficiary', 'favored_private_person'" in sql
    assert "('anti_nepotism', 'nepotistic_beneficiary', 'favored_kin'" in sql
    assert "('tolerate_talent', 'protected_talent', 'protected_talent'" in sql
    assert "('tolerate_talent', 'harmed_talent', 'harmed_talent'" in sql
    assert "('appointment_delegation', 'misappointed_actor', 'misappointed_or_misdelegated_authority'" in sql
    assert "('appointment_delegation', 'misdelegated_actor', 'misappointed_or_misdelegated_authority'" in sql
    assert "appointment_trust" not in sql
    assert "('delegation'," not in sql
    assert "subject_obj_type" in sql
    assert "'person'" in sql
