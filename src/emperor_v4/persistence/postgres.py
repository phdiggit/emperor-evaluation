from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal



G3A_TABLES = frozenset(
    {
        "source_documents",
        "source_passages",
        "assertions",
        "historical_episodes",
        "episode_participants",
        "episode_assertion_dispositions",
        "episode_relations",
        "governance_achievements",
        "governance_achievement_members",
        "rule_evidence_units",
        "rule_evidence_members",
    }
)


class G3ASchemaStateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class G3ASchemaBootstrapResult:
    action: Literal["applied", "reused"]
    table_count: int
    constraint_count: int
    database_write_count: int


def migration_path() -> Path:
    return Path(__file__).resolve().parents[3] / "db" / "postgres" / "001_g3a_episode_core.sql"


def decide_schema_action(existing_tables: Iterable[str]) -> Literal["apply", "reuse"]:
    existing = frozenset(existing_tables)
    if not existing:
        return "apply"
    if existing == G3A_TABLES:
        return "reuse"
    missing = sorted(G3A_TABLES - existing)
    unexpected = sorted(existing - G3A_TABLES)
    raise G3ASchemaStateError(
        f"G3A schema 不是空库或完整合同；missing={missing}, unexpected={unexpected}"
    )


def bootstrap_g3a_schema(dsn: str) -> G3ASchemaBootstrapResult:
    """在调用方明确提供的 V4 DSN 上应用或复用 G3A schema。"""

    if not dsn.strip():
        raise ValueError("G3A bootstrap 需要显式 DSN")
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - 取决于可选运行环境
        raise RuntimeError("G3A PostgreSQL bootstrap 需要 psycopg") from exc

    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname = current_schema()
                ORDER BY tablename
                """
            )
            existing = {str(row[0]) for row in cursor.fetchall()}
            action = decide_schema_action(existing)
            if action == "apply":
                cursor.execute(migration_path().read_text(encoding="utf-8"))

            cursor.execute(
                """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname = current_schema()
                ORDER BY tablename
                """
            )
            actual = {str(row[0]) for row in cursor.fetchall()}
            if actual != G3A_TABLES:
                raise G3ASchemaStateError("G3A migration 后表集合与合同不一致")

            cursor.execute(
                """
                SELECT count(*)
                FROM pg_catalog.pg_constraint c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.connamespace
                WHERE n.nspname = current_schema()
                """
            )
            constraint_count = int(cursor.fetchone()[0])
            if constraint_count < 18:
                raise G3ASchemaStateError("G3A schema 约束数量低于合同下限")

    return G3ASchemaBootstrapResult(
        action=(
            "applied"
            if action == "apply"
            else "reused"
        ),
        table_count=len(G3A_TABLES),
        constraint_count=constraint_count,
        database_write_count=1 if action == "apply" else 0,
    )
