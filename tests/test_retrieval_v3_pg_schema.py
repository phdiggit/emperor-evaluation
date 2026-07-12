from __future__ import annotations

import pytest

from scripts.dev import retrieval_v3_pg_schema as tool


def test_render_sql_defaults_to_retrieval_v3_schema_and_prefix() -> None:
    sql = tool.render_sql(
        """
        create schema if not exists retrieval_v3;
        create type retrieval_v3.rv3_claim_cache_status as enum ('active');
        create table retrieval_v3.claim_cache (
            constraint rv3_claim_cache_key_not_blank check (true)
        );
        """
    )

    assert "retrieval_v3" in sql
    assert "rv3_claim_cache_status" in sql
    assert "rv3_claim_cache_key_not_blank" in sql


def test_rendered_bootstrap_schema_contains_claim_event_group_shadow_layer() -> None:
    from scripts.dev import retrieval_v3_bootstrap as bootstrap

    sql = bootstrap.read_schema_sql(schema_name="retrieval_v3")

    assert "retrieval_v3.claim_event_groups" in sql
    assert "retrieval_v3.claim_event_group_members" in sql
    assert "retrieval_v3.claim_rule_routes" in sql
    assert "retrieval_v3.claim_atomic_facts" in sql
    assert "retrieval_v3.claim_owner_scopes" in sql
    assert "external_or_unregistered_owner" in sql
    assert "rv3_claim_outcome_support" in sql
    assert "legacy extraction hint" not in sql
    assert "claim_cache.direction" not in sql


def test_claim_atomic_facts_view_is_direction_free() -> None:
    from scripts.dev import retrieval_v3_bootstrap as bootstrap

    sql = bootstrap.read_schema_sql(schema_name="retrieval_v3")
    view_sql = sql.split("create or replace view retrieval_v3.claim_atomic_facts as", 1)[1].split(
        "create or replace view retrieval_v3.claim_owner_scopes as",
        1,
    )[0]

    assert "direction" not in view_sql
    assert "atomic_fact_payload" in view_sql
    assert "event_group_payload" in view_sql


def test_pg_schema_name_rejects_unsafe_identifier() -> None:
    with pytest.raises(tool.RetrievalPgSchemaError):
        tool.pg_schema_name("retrieval_v3;drop schema public")
