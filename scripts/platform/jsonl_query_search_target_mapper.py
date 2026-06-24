from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_staging_mapper import (
    apply_staging_mapper,
    build_staging_rows,
    load_source_rows,
)
from scripts.platform.jsonl_staging_resolver_contract import RESOLVER_VERSION
from scripts.platform.jsonl_target_mapping import (
    CANONICAL_JSONL_FILES,
    MAPPING_VERSION,
    assert_report_has_no_blocked_terms,
)
from scripts.platform.postgres_bootstrap import drop_schema, quote_identifier, schema_exists


PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
DEFAULT_SCHEMA = "emperor_eval_query_search_target_mapper"
TOOL_VERSION = "jsonl-query-search-target-mapper-v1"
TARGET_SOURCE_FILES = ("data/query_profiles.jsonl", "data/search_logs.jsonl")
TARGET_TABLES = ("query_profiles", "search_tasks")
QUERY_PROFILE_DIRECT_PLAN = {
    "query_profile_id": {"target_column": "code", "source_bucket": "direct_fields"},
    "profile_scope": {"target_column": "scope", "source_bucket": "direct_fields"},
    "status": {"target_column": "status", "source_bucket": "direct_fields"},
}
SEARCH_TASK_DIRECT_PLAN = {
    "search_id": {"target_column": "code", "source_bucket": "direct_fields"},
    "query": {"target_column": "query_text", "source_bucket": "direct_fields"},
    "status": {"target_column": "status", "source_bucket": "direct_fields"},
}
QUERY_PROFILE_PAYLOAD_FIELDS = (
    "payload_fields",
    "range_filter_fields",
    "reference_risk_fields",
)
SEARCH_TASK_PAYLOAD_FIELDS = (
    "payload_fields",
    "candidate_fields.query_terms",
    "range_filter_fields",
    "reference_risk_fields",
)
LIMITATIONS = (
    "本 prototype 只覆盖 query_profiles 与 search_tasks 两张 target 表。",
    "本 prototype 只写 opt-in 隔离 schema，不写生产 schema。",
    "item、subitem、person 只保留为 range/filter 或 resolver input。",
    "query_profile_id、linked_*、*_ids、cross_item* 在 resolver 可靠输出前不写外键或关系表。",
    "thematic anchor 文件保持 staging-only。",
    "本报告不输出正式评分、排名或裁判结论。",
)


@dataclass(frozen=True)
class ResolvedDsn:
    dsn: str | None
    source: str

    @property
    def present(self) -> bool:
        return bool(self.dsn)


def resolve_dsn(*, env: Mapping[str, str] | None = None) -> ResolvedDsn:
    if env is None:
        env = os.environ
    if env.get(PRIMARY_ENV_DSN):
        return ResolvedDsn(env[PRIMARY_ENV_DSN], f"env:{PRIMARY_ENV_DSN}")
    return ResolvedDsn(None, "skip")


def check_environment(
    resolved: ResolvedDsn | None = None,
    *,
    driver_available: bool | None = None,
) -> dict[str, object]:
    if resolved is None:
        resolved = resolve_dsn()
    if driver_available is None:
        driver_available = is_psycopg_available()
    return {
        "mode": "check",
        "dsn_present": resolved.present,
        "dsn_source": resolved.source,
        "driver": "psycopg",
        "driver_available": driver_available,
        "default_tests_require_postgres": False,
        "will_apply": False,
    }


def integration_skip_reason(
    resolved: ResolvedDsn | None = None,
    *,
    driver_available: bool | None = None,
) -> str | None:
    if resolved is None:
        resolved = resolve_dsn()
    if not resolved.dsn:
        return f"{PRIMARY_ENV_DSN} is not set"
    if driver_available is None:
        driver_available = is_psycopg_available()
    if not driver_available:
        return "psycopg is not installed"
    return None


def build_contract_report(
    *,
    source_root: Path = ROOT,
    relative_files: Sequence[str] = CANONICAL_JSONL_FILES,
) -> dict[str, Any]:
    source_rows = load_source_rows(source_root=source_root, relative_files=relative_files)
    staging_rows = build_staging_rows(source_rows)
    rows_by_source_file: dict[str, int] = {}
    candidate_rows_by_target = {table: 0 for table in TARGET_TABLES}
    unresolved_references_by_file: dict[str, list[dict[str, Any]]] = {}
    staging_only_files: set[str] = set()

    for row in staging_rows:
        rows_by_source_file[row.source_file] = rows_by_source_file.get(row.source_file, 0) + 1
        if row.staging_only:
            staging_only_files.add(row.source_file)
        if row.source_file == "data/query_profiles.jsonl" and row.jsonl_code and not row.staging_only:
            candidate_rows_by_target["query_profiles"] += 1
        if row.source_file == "data/search_logs.jsonl" and row.jsonl_code and not row.staging_only:
            candidate_rows_by_target["search_tasks"] += 1
        if row.source_file in TARGET_SOURCE_FILES:
            unresolved = build_unresolved_entries(row)
            if unresolved:
                unresolved_references_by_file.setdefault(row.source_file, []).extend(unresolved)

    report = {
        "mode": "contract-report",
        "tool_version": TOOL_VERSION,
        "mapping_version": MAPPING_VERSION,
        "resolver_version": RESOLVER_VERSION,
        "source_files": sorted(rows_by_source_file),
        "target_tables": list(TARGET_TABLES),
        "rows_by_source_file": rows_by_source_file,
        "candidate_rows_by_target": candidate_rows_by_target,
        "direct_field_plan": {
            "query_profiles": QUERY_PROFILE_DIRECT_PLAN,
            "search_tasks": SEARCH_TASK_DIRECT_PLAN,
        },
        "payload_field_plan": {
            "query_profiles": list(QUERY_PROFILE_PAYLOAD_FIELDS),
            "search_tasks": list(SEARCH_TASK_PAYLOAD_FIELDS),
        },
        "resolver_blocked_fields": build_resolver_blocked_fields(),
        "unresolved_references_by_file": normalize_unresolved_entries(unresolved_references_by_file),
        "staging_only_files": sorted(staging_only_files),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def build_unresolved_entries(row: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for field in sorted(row.range_filter_fields):
        entries.append(
            {
                "field": field,
                "line_numbers": [row.line_no],
                "kept_as": "range_filter_or_resolver_input",
                "blocked_action": "direct_fk_or_evidence_relationship_write",
            }
        )
    for field in sorted(row.reference_risk_fields):
        entries.append(
            {
                "field": field,
                "line_numbers": [row.line_no],
                "kept_as": "payload_or_resolver_input",
                "blocked_action": "direct_fk_or_relationship_table_write",
            }
        )
    return entries


def normalize_unresolved_entries(
    unresolved: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for source_file, entries in sorted(unresolved.items()):
        merged: dict[tuple[str, str, str], dict[str, Any]] = {}
        for entry in entries:
            key = (str(entry["field"]), str(entry["kept_as"]), str(entry["blocked_action"]))
            target = merged.setdefault(
                key,
                {
                    "field": key[0],
                    "kept_as": key[1],
                    "blocked_action": key[2],
                    "line_numbers": [],
                },
            )
            for line_no in entry["line_numbers"]:
                if line_no not in target["line_numbers"]:
                    target["line_numbers"].append(line_no)
        result[source_file] = sorted(
            ({**entry, "line_numbers": sorted(entry["line_numbers"])} for entry in merged.values()),
            key=lambda item: (item["field"], item["kept_as"], item["blocked_action"]),
        )
    return result


def build_resolver_blocked_fields() -> dict[str, list[dict[str, str]]]:
    return {
        "data/query_profiles.jsonl": [
            {
                "field": "item",
                "blocked_action": "subitem_id_write",
                "allowed_action": "range_filter_or_resolver_input_only",
            },
            {
                "field": "subitem",
                "blocked_action": "subitem_id_write",
                "allowed_action": "range_filter_or_resolver_input_only",
            },
            {
                "field": "person",
                "blocked_action": "person_id_write",
                "allowed_action": "range_filter_or_resolver_input_only",
            },
            {
                "field": "inherits_from",
                "blocked_action": "query_profile_relationship_write",
                "allowed_action": "payload_or_resolver_input_only",
            },
            {
                "field": "object_anchors",
                "blocked_action": "anchors_or_anchor_links_write",
                "allowed_action": "payload_or_resolver_input_only",
            },
            {
                "field": "thematic_anchor_targets",
                "blocked_action": "anchors_or_anchor_links_write",
                "allowed_action": "payload_or_resolver_input_only",
            },
        ],
        "data/search_logs.jsonl": [
            {
                "field": "query_profile_id",
                "blocked_action": "query_profile_id_fk_write_without_resolver",
                "allowed_action": "payload_or_resolver_input_only",
            },
            {
                "field": "linked_source_ids",
                "blocked_action": "source_fk_or_search_hits_write",
                "allowed_action": "payload_or_resolver_input_only",
            },
            {
                "field": "linked_evidence_ids",
                "blocked_action": "evidence_fk_or_relationship_table_write",
                "allowed_action": "payload_or_resolver_input_only",
            },
            {
                "field": "cross_item*",
                "blocked_action": "relationship_table_write",
                "allowed_action": "payload_or_resolver_input_only",
            },
            {
                "field": "*_ids",
                "blocked_action": "direct_fk_write",
                "allowed_action": "payload_or_resolver_input_only",
            },
        ],
    }


def apply_target_mapper(
    dsn: str,
    *,
    schema: str = DEFAULT_SCHEMA,
    source_root: Path = ROOT,
    drop_schema_after: bool = False,
) -> dict[str, Any]:
    validate_isolated_schema(schema)
    staging_report = apply_staging_mapper(dsn, schema=schema, source_root=source_root, drop_schema_after=False)
    dropped = False
    db_report: dict[str, int] = {}
    try:
        create_target_prototype_tables(dsn, schema=schema)
        db_report = insert_target_rows(dsn, schema=schema)
    finally:
        if drop_schema_after:
            drop_schema(dsn, schema)
            dropped = True

    report = {
        "mode": "apply",
        "schema": schema,
        "import_rows": staging_report["import_rows"],
        "staging_rows": staging_report["staging_rows"],
        "query_profile_rows": db_report.get("query_profile_rows", 0),
        "search_task_rows": db_report.get("search_task_rows", 0),
        "unresolved_reference_rows": db_report.get("unresolved_reference_rows", 0),
        "dropped": dropped,
        "schema_exists_after_drop": schema_exists(dsn, schema) if drop_schema_after else None,
    }
    assert_report_has_no_blocked_terms(report)
    return report


def create_target_prototype_tables(dsn: str, *, schema: str) -> None:
    import psycopg

    schema_ident = quote_identifier(schema)
    sql = """
    DROP TABLE IF EXISTS search_tasks CASCADE;
    DROP TABLE IF EXISTS query_profiles CASCADE;

    CREATE TABLE query_profiles (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        code TEXT NOT NULL,
        scope TEXT,
        status TEXT,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT qprof_target_mapper_code_uk UNIQUE (code)
    );

    CREATE TABLE search_tasks (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        code TEXT NOT NULL,
        query_text TEXT,
        status TEXT,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT stask_target_mapper_code_uk UNIQUE (code)
    );
    """
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            cur.execute(sql)
        conn.commit()


def insert_target_rows(dsn: str, *, schema: str) -> dict[str, int]:
    import psycopg

    schema_ident = quote_identifier(schema)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            cur.execute(
                """
                INSERT INTO query_profiles (code, scope, status, payload)
                SELECT
                    jsonl_code,
                    direct_fields -> 'profile_scope' ->> 'value',
                    direct_fields -> 'status' ->> 'value',
                    jsonb_build_object(
                        'payload_fields', payload_fields,
                        'range_filter_fields', range_filter_fields,
                        'reference_risk_fields', reference_risk_fields,
                        'source_file', source_file,
                        'line_no', line_no
                    )
                FROM stg_jsonl_rows
                WHERE source_file = 'data/query_profiles.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                ON CONFLICT (code) DO NOTHING
                """
            )
            query_profile_rows = cur.rowcount
            cur.execute(
                """
                INSERT INTO search_tasks (code, query_text, status, payload)
                SELECT
                    jsonl_code,
                    COALESCE(
                        direct_fields -> 'query' ->> 'value',
                        candidate_fields -> 'query_terms' ->> 'value'
                    ),
                    direct_fields -> 'status' ->> 'value',
                    jsonb_build_object(
                        'payload_fields', payload_fields,
                        'candidate_fields', candidate_fields,
                        'range_filter_fields', range_filter_fields,
                        'reference_risk_fields', reference_risk_fields,
                        'source_file', source_file,
                        'line_no', line_no
                    )
                FROM stg_jsonl_rows
                WHERE source_file = 'data/search_logs.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                ON CONFLICT (code) DO NOTHING
                """
            )
            search_task_rows = cur.rowcount
            cur.execute(
                """
                SELECT COUNT(*)
                FROM stg_jsonl_rows
                WHERE source_file IN ('data/query_profiles.jsonl', 'data/search_logs.jsonl')
                  AND (
                    range_filter_fields <> '{}'::jsonb
                    OR reference_risk_fields <> '{}'::jsonb
                  )
                """
            )
            unresolved_reference_rows = int(cur.fetchone()[0] or 0)
        conn.commit()
    return {
        "query_profile_rows": int(query_profile_rows),
        "search_task_rows": int(search_task_rows),
        "unresolved_reference_rows": unresolved_reference_rows,
    }


def validate_isolated_schema(schema: str) -> None:
    quote_identifier(schema)
    if schema == "public":
        raise ValueError("refusing to write target mapper prototype into public schema")


def is_psycopg_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Prototype query/search target mapping from stg_jsonl_rows.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--contract-report", action="store_true", help="print the offline target mapper contract")
    mode.add_argument("--apply", action="store_true", help="write query/search prototype target rows")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help=f"isolated schema name, default: {DEFAULT_SCHEMA}")
    parser.add_argument("--drop-schema-after", action="store_true", help="drop the isolated schema after apply")
    parser.add_argument("--source-root", type=Path, default=ROOT, help="repository root or fixture root")
    args = parser.parse_args(argv)

    if args.drop_schema_after and not args.apply:
        parser.error("--drop-schema-after requires --apply")

    if args.contract_report or not (args.check or args.apply):
        report = build_contract_report(source_root=args.source_root)
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
        return 0

    resolved = resolve_dsn()
    if args.apply:
        reason = integration_skip_reason(resolved)
        if reason:
            sys.stderr.write(f"skip: {reason}\n")
            return 2
        result = apply_target_mapper(
            resolved.dsn or "",
            schema=args.schema,
            source_root=args.source_root,
            drop_schema_after=args.drop_schema_after,
        )
    else:
        result = check_environment(resolved)

    sys.stdout.write(report_as_json(result))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
