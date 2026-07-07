from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "migrations" / "20260704_retrieval_v2_control_plane.sql"


def schema_text() -> str:
    assert SCHEMA_PATH.exists()
    return SCHEMA_PATH.read_text(encoding="utf-8")


def created_tables(sql: str) -> set[str]:
    return set(re.findall(r"create table if not exists retrieval_v2\.([a-z_]+)\s*\(", sql, flags=re.IGNORECASE))


def created_table_columns(sql: str) -> dict[str, set[str]]:
    columns_by_table: dict[str, set[str]] = {}
    table_pattern = re.compile(
        r"create table if not exists retrieval_v2\.([a-z_]+)\s*\((.*?)\n\);",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in table_pattern.finditer(sql):
        table = match.group(1)
        columns: set[str] = set()
        for raw_line in match.group(2).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("constraint "):
                break
            columns.add(line.split()[0].rstrip(","))
        columns_by_table[table] = columns
    return columns_by_table


def commented_tables(sql: str) -> set[str]:
    return set(re.findall(r"comment on table retrieval_v2\.([a-z_]+)\s+is\s+", sql, flags=re.IGNORECASE))


def commented_columns(sql: str) -> set[tuple[str, str]]:
    return set(
        re.findall(
            r"comment on column retrieval_v2\.([a-z_]+)\.([a-z0-9_]+)\s+is\s+",
            sql,
            flags=re.IGNORECASE,
        )
    )


def test_retrieval_v2_schema_contains_only_retrieval_control_plane_tables() -> None:
    tables = created_tables(schema_text())

    assert tables >= {
        "eval_items",
        "eval_rules",
        "eval_rule_factors",
        "eval_rule_factor_options",
        "eval_rule_material_policies",
        "fact_relation_predicate_options",
        "rule_contracts",
        "rule_contract_rules",
        "retrieval_targets",
        "target_aliases",
        "target_rule_requirements",
        "retrieval_intents",
        "jobs",
        "job_runs",
        "search_tasks",
        "search_hits",
        "source_packs",
        "source_pack_artifacts",
        "source_documents",
        "source_passages",
        "material_claims",
        "claim_rule_bindings",
        "coverage_reports",
        "coverage_gap_events",
    }
    assert not (tables & {"raw_objs", "emp_objs", "obj_srcs", "obj_attrs", "evd_clusters", "emp_item_results"})


def test_retrieval_v2_schema_anchors_source_packs_to_rule_contracts() -> None:
    sql = schema_text()

    assert "create schema if not exists retrieval_v2" in sql
    assert "contract_id bigint not null references retrieval_v2.rule_contracts" in sql
    assert "target_id bigint not null references retrieval_v2.retrieval_targets" in sql
    assert "constraint rv2_source_packs_target_contract_version_uk unique" in sql
    assert "constraint rv2_contract_rules_rule_uk unique (contract_id, rule_code)" in sql


def test_retrieval_v2_schema_supports_multi_rule_claim_bindings_and_feedback_events() -> None:
    sql = schema_text()

    assert "claim_id bigint not null references retrieval_v2.material_claims" in sql
    assert "contract_rule_id bigint not null references retrieval_v2.rule_contract_rules" in sql
    assert "constraint rv2_claim_rule_bindings_uk unique (claim_id, contract_rule_id, predicate, object_role)" in sql
    assert "usable_for_object_payload boolean not null default false" in sql
    assert "usable_for_scoring_cluster boolean not null default false" in sql
    assert "create table if not exists retrieval_v2.coverage_gap_events" in sql
    assert "source_pack_refinement" in sql
    assert "codex_review" in sql
    assert "source_missing" in sql
    assert "object_claim_undercoverage" in sql
    assert "alias_missing" in sql
    assert "fetch_error" in sql
    assert "negative_undercoverage" in sql
    assert "mixed_claim_not_split" in sql
    assert "needs_primary_source" in sql
    assert "drop constraint if exists rv2_coverage_gap_events_gap_type_ck" in sql


def test_retrieval_v2_jobs_are_idempotent_and_dispatcher_ready() -> None:
    sql = schema_text()

    assert "constraint rv2_jobs_idem_uk unique (idem_key)" in sql
    assert "locked_by text" in sql
    assert "lease_until timestamptz" in sql
    assert "rv2_jobs_ready_idx" in sql
    assert "where status in ('ready', 'retry_wait')" in sql


def test_retrieval_v2_schema_comments_every_table_and_column() -> None:
    sql = schema_text()
    tables = created_tables(sql)
    table_comments = commented_tables(sql)
    columns_by_table = created_table_columns(sql)
    column_comments = commented_columns(sql)

    assert tables - table_comments == set()
    assert table_comments - tables == set()

    missing_column_comments = sorted(
        f"{table}.{column}"
        for table, columns in columns_by_table.items()
        for column in columns
        if (table, column) not in column_comments
    )
    extra_column_comments = sorted(
        f"{table}.{column}"
        for table, column in column_comments
        if table not in columns_by_table or column not in columns_by_table[table]
    )

    assert missing_column_comments == []
    assert extra_column_comments == []
