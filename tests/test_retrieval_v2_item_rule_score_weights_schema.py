from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "db" / "migrations" / "20260706_retrieval_v2_item_rule_score_weights.sql"


def migration_sql() -> str:
    assert MIGRATION_PATH.exists()
    return MIGRATION_PATH.read_text(encoding="utf-8")


def lower_sql() -> str:
    return migration_sql().lower()


def created_table_columns(sql: str) -> set[str]:
    match = re.search(
        r"create table if not exists retrieval_v2\.item_rule_score_weights\s*\((.*?)\n\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match
    columns: set[str] = set()
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("constraint "):
            break
        columns.add(line.split()[0].rstrip(","))
    return columns


def commented_columns(sql: str) -> set[str]:
    return set(
        re.findall(
            r"comment on column retrieval_v2\.item_rule_score_weights\.([a-z0-9_]+)\s+is\s+",
            sql,
            flags=re.IGNORECASE,
        )
    )


def seeded_weights(sql: str) -> dict[str, Decimal]:
    return {
        rule_code: Decimal(value)
        for rule_code, value in re.findall(
            r"\('I5B', '([a-z_]+)', '[^']+', 'evidence_cluster_signal_v3', 'v1', ([0-9.]+)::numeric",
            sql,
            flags=re.IGNORECASE,
        )
    }


def test_item_rule_score_weights_schema_is_all_item_generic() -> None:
    sql = lower_sql()

    assert "create table if not exists retrieval_v2.item_rule_score_weights" in sql
    assert "item_code text not null" in sql
    assert "rule_code text not null" in sql
    assert "formula_code text not null" in sql
    assert "weight_version text not null default 'v1'" in sql
    assert "constraint rv2_item_rule_score_weights_item_rule_formula_version_uk unique (item_code, rule_code, formula_code, weight_version)" in sql
    assert "独立于抓包契约排序" in migration_sql()
    assert "所有评价项通用" in migration_sql()
    assert "i5b_item_rule_score_weights" not in sql


def test_item_rule_score_weights_uses_enum_for_status() -> None:
    sql = lower_sql()

    assert "create type retrieval_v2.rv2_rule_weight_status as enum (''active'', ''inactive'', ''retired'')" in sql
    assert "weight_status retrieval_v2.rv2_rule_weight_status not null default 'active'" in sql
    assert "comment on type retrieval_v2.rv2_rule_weight_status is" in sql


def test_item_rule_score_weights_comments_every_table_and_column() -> None:
    sql = migration_sql()
    columns = created_table_columns(sql)

    assert "comment on table retrieval_v2.item_rule_score_weights is" in lower_sql()
    assert columns - commented_columns(sql) == set()


def test_item_rule_score_weights_seeds_i5b_formula_weights_from_docs() -> None:
    weights = seeded_weights(migration_sql())

    assert weights == {
        "talent_discovery": Decimal("0.190000"),
        "appointment_delegation": Decimal("0.360000"),
        "team_building": Decimal("0.210000"),
        "tolerate_talent": Decimal("0.180000"),
        "anti_nepotism": Decimal("0.060000"),
    }
    assert sum(weights.values()) == Decimal("1.000000")

    sql = migration_sql()
    for line in range(419, 424):
        assert f"'docs/分项规则/第五项统治者政治素质/B用人与授权.md', {line}" in sql


def test_item_rule_score_weights_backfills_i5b_contract_rule_labels() -> None:
    sql = lower_sql()

    assert "update retrieval_v2.rule_contract_rules rcr" in sql
    assert "from retrieval_v2.rule_contracts rc" in sql
    assert "rc.item_code = 'i5b'" in sql
    assert "rcr.rule_label is distinct from labels.rule_label" in sql

    original_sql = migration_sql()
    for label in ["发现人才", "任用授权", "建立团队", "容人保全", "避免任人唯亲"]:
        assert label in original_sql
