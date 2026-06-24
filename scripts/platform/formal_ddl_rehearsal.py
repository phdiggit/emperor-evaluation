from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import formal_schema_draft


REHEARSAL_VERSION = "isolated-formal-ddl-rehearsal-v1"
DEFAULT_SCHEMA = "emperor_eval_formal_rehearsal"
SCHEMA_REHEARSAL_META_TABLE = "schema_rehearsal_meta"
SOURCE_OF_TRUTH_MARKER = "canonical_jsonl_remains_source_of_truth"
SQL_MARKERS = (
    "proposal_only",
    "isolated_rehearsal_only",
    "not_production_migration",
    SOURCE_OF_TRUTH_MARKER,
)
SQL_LINT_RULES = (
    "no_public_schema_writes",
    "no_drop_public",
    "no_production_migration_phrase",
    "no_blocked_report_terms",
    "phase_1_tables_only",
    "relationship_tables_not_created",
    "downstream_tables_not_created",
    "schema_rehearsal_meta_present",
    "canonical_jsonl_source_boundary_present",
)
BLOCKED_SQL_TERMS = formal_schema_draft.BLOCKED_REPORT_TERMS
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CREATE_TABLE_RE = re.compile(
    r"(?im)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<table>\"?[A-Za-z_][A-Za-z0-9_]*\"?(?:\.\"?[A-Za-z_][A-Za-z0-9_]*\"?)?)"
)


def build_contract_report() -> dict[str, Any]:
    draft_report = formal_schema_draft.build_contract_report()
    report = {
        "mode": "contract-report",
        "rehearsal_version": REHEARSAL_VERSION,
        "formal_schema_draft_version": draft_report["draft_version"],
        "status": "Proposed",
        "schema_default": DEFAULT_SCHEMA,
        "phase_1_tables_emitted": list(formal_schema_draft.PHASE_1_BASE_TABLES),
        "phase_2_tables_blocked": list(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES),
        "phase_3_tables_deferred": list(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES),
        "schema_version_marker": {
            "table_name": SCHEMA_REHEARSAL_META_TABLE,
            "purpose": "isolated rehearsal metadata marker for review only",
            "draft_version": draft_report["draft_version"],
            "source_of_truth": "canonical JSONL only",
            "production_marker": False,
        },
        "seed_contract_skeleton": {
            "source": "canonical JSONL only",
            "artifact_kind": "proposed",
            "checksum_required": True,
            "secret_free": True,
            "reproducible": True,
            "generated_in_this_pr": False,
        },
        "sql_lint_rules": list(SQL_LINT_RULES),
        "table_gate_alignment": {
            "phase_1_allowed_tables": {
                "tables": list(formal_schema_draft.PHASE_1_BASE_TABLES),
                "gate": "emitted",
            },
            "phase_2_relationship_tables": {
                "tables": list(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES),
                "gate": "blocked",
            },
            "phase_3_downstream_tables": {
                "tables": list(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES),
                "gate": "deferred",
            },
        },
        "non_goals": [
            "does not modify canonical JSONL",
            "does not modify db/schema.sql",
            "does not modify db/postgres/001_init.sql",
            "does not connect to PostgreSQL",
            "does not read .env or DSN values",
            "does not execute DDL or migration",
            "does not generate seed artifact",
            "does not switch the JSONL write source",
            "does not write production target tables",
            "does not generate business conclusions",
        ],
        "strict_boundaries": [
            "offline_static_sql_only",
            "stdout_only_for_sql",
            "does_not_read_dotenv",
            "does_not_read_dsn",
            "does_not_connect_to_database",
            "does_not_execute_ddl",
            "does_not_execute_migration",
            "does_not_modify_canonical_jsonl",
            "does_not_modify_db_schema_sql",
            "does_not_modify_postgres_init_sql",
            "does_not_generate_seed_artifact",
            "does_not_switch_jsonl_write_source",
            "does_not_write_production_target_tables",
        ],
        "future_work": [
            "optional isolated live rehearsal in a separate PR",
            "random isolated schema dry apply in a separate PR",
            "drop verification in a separate PR",
            "no production schema changes in this PR",
        ],
        "limitations": [
            "static SQL rendering only",
            "no PostgreSQL connection",
            "no SQL execution",
            "no formal migration file",
            "no seed artifact output",
            "phase 2 relationship tables are report-only",
            "phase 3 downstream tables are report-only",
        ],
    }
    _assert_no_blocked_terms(report)
    return report


def render_sql(schema: str = DEFAULT_SCHEMA) -> str:
    schema = _validate_schema(schema)
    lines = [
        f"CREATE SCHEMA IF NOT EXISTS {schema};",
        f"SET search_path TO {schema}, public;",
        "",
        "-- proposal_only",
        "-- isolated_rehearsal_only",
        "-- not_production_migration",
        f"-- {SOURCE_OF_TRUTH_MARKER}",
        "",
        f"CREATE TABLE {SCHEMA_REHEARSAL_META_TABLE} (",
        "  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,",
        "  schema_name TEXT NOT NULL,",
        "  draft_version TEXT NOT NULL,",
        "  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),",
        "  source_of_truth TEXT NOT NULL,",
        "  payload JSONB NOT NULL DEFAULT '{}'::jsonb",
        ");",
        f"COMMENT ON TABLE {SCHEMA_REHEARSAL_META_TABLE} IS 'proposal_only isolated_rehearsal_only not_production_migration {SOURCE_OF_TRUTH_MARKER}';",
        "",
    ]
    for table_name in formal_schema_draft.PHASE_1_BASE_TABLES:
        lines.extend(_render_phase_1_table(table_name))
    lines.extend(
        [
            "-- Phase 2 relationship tables are report-only in this rehearsal:",
            f"-- {', '.join(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES)}",
            "-- Phase 3 downstream tables are report-only in this rehearsal:",
            f"-- {', '.join(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES)}",
            "",
        ]
    )
    return "\n".join(lines)


def lint_sql(sql: str, schema: str = DEFAULT_SCHEMA) -> dict[str, Any]:
    schema = _validate_schema(schema)
    created_tables = _created_tables(sql)
    allowed_tables = set(formal_schema_draft.PHASE_1_BASE_TABLES) | {SCHEMA_REHEARSAL_META_TABLE}
    relationship_created = sorted(set(created_tables) & set(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES))
    downstream_created = sorted(set(created_tables) & set(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES))
    unexpected_created = sorted(set(created_tables) - allowed_tables)
    lowered = sql.lower()
    rule_results = {
        "no_public_schema_writes": "public." not in lowered,
        "no_drop_public": not re.search(r"(?i)\bDROP\s+(SCHEMA|TABLE)\s+public\b", sql),
        "no_production_migration_phrase": all(
            phrase not in lowered for phrase in ("production migration marker", "production_migration_marker")
        ),
        "no_blocked_report_terms": all(term not in lowered for term in BLOCKED_SQL_TERMS),
        "phase_1_tables_only": not unexpected_created,
        "relationship_tables_not_created": not relationship_created,
        "downstream_tables_not_created": not downstream_created,
        "schema_rehearsal_meta_present": SCHEMA_REHEARSAL_META_TABLE in created_tables,
        "canonical_jsonl_source_boundary_present": SOURCE_OF_TRUTH_MARKER in sql,
    }
    checked_rules = [
        {
            "rule": rule,
            "passed": bool(rule_results[rule]),
        }
        for rule in SQL_LINT_RULES
    ]
    failed = [rule for rule in SQL_LINT_RULES if not rule_results[rule]]
    return {
        "mode": "lint-sql",
        "schema": schema,
        "sql_generated": True,
        "passed": not failed,
        "failed": failed,
        "checked_rules": checked_rules,
        "emitted_tables": [table for table in created_tables if table in formal_schema_draft.PHASE_1_BASE_TABLES],
        "blocked_tables": list(formal_schema_draft.PHASE_2_RELATIONSHIP_TABLES),
        "deferred_tables": list(formal_schema_draft.PHASE_3_DOWNSTREAM_TABLES),
        "limitations": [
            "static string lint only",
            "does not parse PostgreSQL grammar",
            "does not connect to PostgreSQL",
            "does not execute SQL",
        ],
    }


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Render and lint isolated formal DDL rehearsal output.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-report", action="store_true", help="print the isolated rehearsal contract report")
    mode.add_argument("--emit-sql", action="store_true", help="print isolated rehearsal SQL")
    mode.add_argument("--lint-sql", action="store_true", help="render and lint isolated rehearsal SQL")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help="isolated rehearsal schema name")
    args = parser.parse_args(argv)

    if args.contract_report:
        sys.stdout.write(report_as_json(build_contract_report()))
        sys.stdout.write("\n")
        return 0
    if args.emit_sql:
        sys.stdout.write(render_sql(args.schema))
        sys.stdout.write("\n")
        return 0

    result = lint_sql(render_sql(args.schema), args.schema)
    sys.stdout.write(report_as_json(result))
    sys.stdout.write("\n")
    return 0 if result["passed"] else 1


def _render_phase_1_table(table_name: str) -> list[str]:
    return [
        f"CREATE TABLE {table_name} (",
        "  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,",
        "  code TEXT NOT NULL UNIQUE,",
        "  payload JSONB NOT NULL DEFAULT '{}'::jsonb,",
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),",
        "  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");",
        f"COMMENT ON TABLE {table_name} IS 'isolated_rehearsal_only phase_1_base_table';",
        "",
    ]


def _created_tables(sql: str) -> list[str]:
    tables: list[str] = []
    for match in _CREATE_TABLE_RE.finditer(sql):
        raw = match.group("table").replace('"', "")
        tables.append(raw.rsplit(".", 1)[-1])
    return tables


def _validate_schema(schema: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(schema):
        raise ValueError(f"invalid isolated rehearsal schema name: {schema!r}")
    if schema == "public":
        raise ValueError("isolated rehearsal schema must not be public")
    return schema


def _assert_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = report_as_json(report).lower()
    for term in formal_schema_draft.BLOCKED_REPORT_TERMS:
        if term in text:
            raise AssertionError(f"report unexpectedly contains {term!r}")


if __name__ == "__main__":
    raise SystemExit(main())
