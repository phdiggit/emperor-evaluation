from __future__ import annotations

import pytest

from scripts.dev import retrieval_v2_pg_schema as tool


def test_render_sql_defaults_to_retrieval_v3_schema_and_prefix() -> None:
    sql = tool.render_sql(
        """
        create schema if not exists retrieval_v2;
        create type retrieval_v2.rv2_claim_cache_status as enum ('active');
        create table retrieval_v2.claim_cache (
            constraint rv2_claim_cache_key_not_blank check (true)
        );
        """
    )

    assert "retrieval_v3" in sql
    assert "rv3_claim_cache_status" in sql
    assert "rv3_claim_cache_key_not_blank" in sql
    assert "retrieval_v2" not in sql
    assert "rv2_" not in sql


def test_rendered_bootstrap_schema_contains_claim_event_group_shadow_layer() -> None:
    from scripts.dev import retrieval_v2_bootstrap as bootstrap

    sql = bootstrap.read_schema_sql(schema_name="retrieval_v3")

    assert "retrieval_v3.claim_event_groups" in sql
    assert "retrieval_v3.claim_event_group_members" in sql
    assert "retrieval_v3.claim_rule_routes" in sql
    assert "retrieval_v3.claim_atomic_facts" in sql
    assert "rv3_claim_outcome_support" in sql
    assert "legacy extraction hint" in sql


def test_pg_schema_name_rejects_unsafe_identifier() -> None:
    with pytest.raises(tool.RetrievalPgSchemaError):
        tool.pg_schema_name("retrieval_v3;drop schema public")
