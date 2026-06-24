from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_staging_mapper import (
    StagingRow,
    apply_staging_mapper,
    build_staging_rows,
    load_source_rows,
)
from scripts.platform.jsonl_staging_resolver_contract import RESOLVER_VERSION
from scripts.platform.jsonl_target_mapping import MAPPING_VERSION, assert_report_has_no_blocked_terms
from scripts.platform.postgres_bootstrap import drop_schema, quote_identifier, schema_exists


PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
DEFAULT_SCHEMA = "emperor_eval_sources_target_mapper"
TOOL_VERSION = "jsonl-sources-target-mapper-v1"
TARGET_SOURCE_FILES = ("data/sources.jsonl",)
TARGET_TABLES = ("src_hosts", "src_docs", "doc_revs", "passages")
SOURCE_DIRECT_PLAN = {
    "source_id": {"target_column": "src_docs.code", "source_bucket": "candidate_fields"},
    "title": {"target_column": "src_docs.title", "source_bucket": "direct_fields"},
    "source_title": {"target_column": "src_docs.title", "source_bucket": "direct_fields"},
    "url": {"target_column": "src_docs.canon_url", "source_bucket": "direct_fields"},
    "source_url": {"target_column": "src_docs.canon_url", "source_bucket": "direct_fields"},
    "host": {"target_column": "src_hosts.code", "source_bucket": "direct_fields"},
    "source_host": {"target_column": "src_hosts.code", "source_bucket": "direct_fields"},
}
PAYLOAD_FIELD_PLAN = {
    "doc_revs": ("raw_text", "excerpt", "quote", "context", "meta", "notes", "note"),
    "src_docs": ("author", "dynasty", "volume", "location", "notes", "note", "meta"),
    "passages": ("quote", "excerpt", "context", "location", "volume"),
}
LIMITATIONS = (
    "本 prototype 只覆盖 data/sources.jsonl。",
    "本 prototype 只写 opt-in 隔离 schema 内的 src_hosts、src_docs、doc_revs、passages relaxed target rows。",
    "host/source_host 有值时才写 src_hosts；URL host 只报告 inferred_host_candidate，不作为写入依据。",
    "source_id 是 source document/code，不是 passage_id。",
    "passages 仅为 unreviewed candidate，不代表人工 reviewed passage span。",
    "本 prototype 不写 evd_src_links，也不证明 evidence relationship。",
    "本 prototype 不写 query/search/evidence/cluster/anchor/adjudication target tables。",
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
    relative_files: Sequence[str] = TARGET_SOURCE_FILES,
) -> dict[str, Any]:
    source_rows = load_source_rows(source_root=source_root, relative_files=relative_files)
    staging_rows = [row for row in build_staging_rows(source_rows) if row.source_file in TARGET_SOURCE_FILES]
    rows_by_source_file: dict[str, int] = {}
    candidate_rows_by_target = {table: 0 for table in TARGET_TABLES}
    inferred_host_candidates = 0

    for row in staging_rows:
        rows_by_source_file[row.source_file] = rows_by_source_file.get(row.source_file, 0) + 1
        if is_targetable_source_row(row):
            candidate_rows_by_target["src_docs"] += 1
            candidate_rows_by_target["doc_revs"] += 1
            if direct_text(row, "host", "source_host"):
                candidate_rows_by_target["src_hosts"] += 1
            elif inferred_url_host_candidate(row):
                inferred_host_candidates += 1
            if passage_text_candidate(row):
                candidate_rows_by_target["passages"] += 1

    report = {
        "mode": "contract-report",
        "tool_version": TOOL_VERSION,
        "mapping_version": MAPPING_VERSION,
        "resolver_version": RESOLVER_VERSION,
        "source_files": sorted(rows_by_source_file),
        "target_tables": list(TARGET_TABLES),
        "rows_by_source_file": rows_by_source_file,
        "candidate_rows_by_target": candidate_rows_by_target,
        "direct_field_plan": build_direct_field_plan(),
        "payload_field_plan": {table: list(fields) for table, fields in PAYLOAD_FIELD_PLAN.items()},
        "host_resolution_plan": {
            "direct_host_fields": ["host", "source_host"],
            "write_src_hosts_from_direct_fields": True,
            "url_host_extraction": "reported_only",
            "inferred_host_candidate_rows": inferred_host_candidates,
            "network_access": False,
        },
        "document_resolution_plan": {
            "source_id_target": "src_docs.code",
            "allowed_action": "source_document_code_candidate",
            "source_id_is_passage_id": False,
        },
        "revision_plan": {
            "prototype_code": "<source_id>::rev0",
            "source_id_target": "doc_revs.source_code candidate",
            "version_semantics": "prototype_only",
        },
        "passage_candidate_plan": {
            "text_fields": ["quote", "excerpt"],
            "context_fields": ["context", "location", "volume"],
            "raw_text_behavior": "doc_revs_payload_only_unless_reviewed_later",
            "passage_candidate_status": "unreviewed_candidate",
            "source_id_usage": "source_document_resolver_input_only",
        },
        "blocked_relationship_writes": build_blocked_relationship_writes(staging_rows),
        "unresolved_references_by_file": build_unresolved_references_by_file(staging_rows),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def build_direct_field_plan() -> dict[str, dict[str, Any]]:
    return {
        "src_hosts": {
            "host": SOURCE_DIRECT_PLAN["host"],
            "source_host": SOURCE_DIRECT_PLAN["source_host"],
        },
        "src_docs": {
            "source_id": SOURCE_DIRECT_PLAN["source_id"],
            "title": SOURCE_DIRECT_PLAN["title"],
            "source_title": SOURCE_DIRECT_PLAN["source_title"],
            "url": SOURCE_DIRECT_PLAN["url"],
            "source_url": SOURCE_DIRECT_PLAN["source_url"],
            "host": {"target_column": "src_docs.host_code candidate", "source_bucket": "direct_fields"},
            "source_host": {"target_column": "src_docs.host_code candidate", "source_bucket": "direct_fields"},
        },
        "doc_revs": {
            "source_id": {"target_column": "doc_revs.source_code candidate", "source_bucket": "candidate_fields"},
        },
        "passages": {
            "source_id": {
                "target_column": "source_document_resolver_input_only",
                "source_bucket": "candidate_fields",
            },
            "quote": {"target_column": "passages.text candidate", "source_bucket": "payload_fields"},
            "excerpt": {"target_column": "passages.text candidate", "source_bucket": "payload_fields"},
            "context": {"target_column": "passages.payload.context", "source_bucket": "payload_fields"},
        },
    }


def build_blocked_relationship_writes(rows: Sequence[StagingRow]) -> list[dict[str, Any]]:
    line_numbers = sorted(row.line_no for row in rows if row.source_file in TARGET_SOURCE_FILES and row.jsonl_code)
    if not line_numbers:
        return []
    return [
        {
            "source_file": "data/sources.jsonl",
            "field": "source_id",
            "blocked_action": "passage_id_write_or_evd_src_links_write",
            "allowed_action": "resolve_to_source_document_or_code_only",
            "line_numbers": line_numbers,
            "reason": "source_id identifies a source document/code candidate, not a reviewed passage span.",
        },
        {
            "source_file": "data/sources.jsonl",
            "field": "quote/context/excerpt/raw_text",
            "blocked_action": "evidence_relationship_write",
            "allowed_action": "unreviewed_candidate_payload_only",
            "line_numbers": line_numbers,
            "reason": "Source text candidates require later manual passage review before evidence linking.",
        },
    ]


def build_unresolved_references_by_file(rows: Sequence[StagingRow]) -> dict[str, list[dict[str, Any]]]:
    line_numbers = sorted(row.line_no for row in rows if row.source_file in TARGET_SOURCE_FILES and row.jsonl_code)
    if not line_numbers:
        return {}
    return {
        "data/sources.jsonl": [
            {
                "field": "source_id",
                "resolver_domain": "source_document",
                "line_numbers": line_numbers,
                "blocked_action": "passage_id_write_or_evd_src_links_write",
                "kept_as": "source_document_code_candidate",
            },
            {
                "field": "passage_span",
                "resolver_domain": "source_passage",
                "line_numbers": line_numbers,
                "blocked_action": "automatic_passage_link_write",
                "kept_as": "manual_passage_review_input_only",
            },
        ]
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
        "src_host_rows": db_report.get("src_host_rows", 0),
        "src_doc_rows": db_report.get("src_doc_rows", 0),
        "doc_rev_rows": db_report.get("doc_rev_rows", 0),
        "passage_rows": db_report.get("passage_rows", 0),
        "blocked_relationship_rows": db_report.get("blocked_relationship_rows", 0),
        "dropped": dropped,
        "schema_exists_after_drop": schema_exists(dsn, schema) if drop_schema_after else None,
    }
    assert_report_has_no_blocked_terms(report)
    return report


def create_target_prototype_tables(dsn: str, *, schema: str) -> None:
    import psycopg

    schema_ident = quote_identifier(schema)
    sql = """
    DROP TABLE IF EXISTS passages CASCADE;
    DROP TABLE IF EXISTS doc_revs CASCADE;
    DROP TABLE IF EXISTS src_docs CASCADE;
    DROP TABLE IF EXISTS src_hosts CASCADE;

    CREATE TABLE src_hosts (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        code TEXT NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT src_hosts_target_mapper_code_uk UNIQUE (code)
    );

    CREATE TABLE src_docs (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        code TEXT NOT NULL,
        title TEXT,
        canon_url TEXT,
        host_code TEXT,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT src_docs_target_mapper_code_uk UNIQUE (code)
    );

    CREATE TABLE doc_revs (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        code TEXT NOT NULL,
        source_code TEXT NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT doc_revs_target_mapper_code_uk UNIQUE (code)
    );

    CREATE TABLE passages (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        code TEXT NOT NULL,
        doc_code TEXT NOT NULL,
        text TEXT NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        candidate_status TEXT NOT NULL DEFAULT 'unreviewed_candidate',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT passages_target_mapper_code_uk UNIQUE (code)
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
                INSERT INTO src_hosts (code, payload)
                SELECT DISTINCT
                    COALESCE(
                        direct_fields -> 'host' ->> 'value',
                        direct_fields -> 'source_host' ->> 'value'
                    ) AS code,
                    jsonb_build_object(
                        'source_file', 'data/sources.jsonl',
                        'host_source', 'direct_host_field'
                    )
                FROM stg_jsonl_rows
                WHERE source_file = 'data/sources.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                  AND COALESCE(
                        direct_fields -> 'host' ->> 'value',
                        direct_fields -> 'source_host' ->> 'value'
                  ) IS NOT NULL
                ON CONFLICT (code) DO NOTHING
                """
            )
            src_host_rows = cur.rowcount
            cur.execute(
                """
                INSERT INTO src_docs (code, title, canon_url, host_code, payload)
                SELECT
                    jsonl_code,
                    COALESCE(
                        direct_fields -> 'title' ->> 'value',
                        direct_fields -> 'source_title' ->> 'value'
                    ),
                    COALESCE(
                        direct_fields -> 'url' ->> 'value',
                        direct_fields -> 'source_url' ->> 'value'
                    ),
                    COALESCE(
                        direct_fields -> 'host' ->> 'value',
                        direct_fields -> 'source_host' ->> 'value'
                    ),
                    jsonb_build_object(
                        'source_file', source_file,
                        'line_no', line_no,
                        'payload_fields', payload_fields,
                        'source_id_boundary', 'source_document_code_not_passage_id'
                    )
                FROM stg_jsonl_rows
                WHERE source_file = 'data/sources.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                ON CONFLICT (code) DO NOTHING
                """
            )
            src_doc_rows = cur.rowcount
            cur.execute(
                """
                INSERT INTO doc_revs (code, source_code, payload)
                SELECT
                    jsonl_code || '::rev0',
                    jsonl_code,
                    jsonb_build_object(
                        'prototype_revision', true,
                        'source_file', source_file,
                        'line_no', line_no,
                        'payload_fields', payload_fields,
                        'source_id_boundary', 'source_document_code_not_passage_id'
                    )
                FROM stg_jsonl_rows
                WHERE source_file = 'data/sources.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                ON CONFLICT (code) DO NOTHING
                """
            )
            doc_rev_rows = cur.rowcount
            cur.execute(
                """
                INSERT INTO passages (code, doc_code, text, payload)
                SELECT
                    jsonl_code || '::passage0',
                    jsonl_code,
                    COALESCE(payload_fields ->> 'quote', payload_fields ->> 'excerpt'),
                    jsonb_build_object(
                        'candidate_status', 'unreviewed_candidate',
                        'source_file', source_file,
                        'line_no', line_no,
                        'context', payload_fields -> 'context',
                        'location', payload_fields -> 'location',
                        'volume', payload_fields -> 'volume',
                        'source_id_usage', 'source_document_resolver_input_only'
                    )
                FROM stg_jsonl_rows
                WHERE source_file = 'data/sources.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                  AND COALESCE(payload_fields ->> 'quote', payload_fields ->> 'excerpt') IS NOT NULL
                ON CONFLICT (code) DO NOTHING
                """
            )
            passage_rows = cur.rowcount
            cur.execute(
                """
                SELECT COUNT(*)
                FROM stg_jsonl_rows
                WHERE source_file = 'data/sources.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                """
            )
            blocked_relationship_rows = int(cur.fetchone()[0] or 0)
        conn.commit()
    return {
        "src_host_rows": int(src_host_rows),
        "src_doc_rows": int(src_doc_rows),
        "doc_rev_rows": int(doc_rev_rows),
        "passage_rows": int(passage_rows),
        "blocked_relationship_rows": blocked_relationship_rows,
    }


def is_targetable_source_row(row: StagingRow) -> bool:
    return (
        row.source_file in TARGET_SOURCE_FILES
        and bool(row.jsonl_code)
        and not row.staging_only
        and not row.validation_errors
    )


def direct_text(row: StagingRow, *fields: str) -> str | None:
    for field in fields:
        value = row.direct_fields.get(field, {}).get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def payload_text(row: StagingRow, *fields: str) -> str | None:
    for field in fields:
        value = row.payload_fields.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def passage_text_candidate(row: StagingRow) -> str | None:
    return payload_text(row, "quote", "excerpt")


def inferred_url_host_candidate(row: StagingRow) -> bool:
    value = direct_text(row, "url", "source_url")
    if not value:
        return False
    parsed = urlparse(value)
    return bool(parsed.netloc)


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

    parser = argparse.ArgumentParser(description="Prototype sources target mapping from stg_jsonl_rows.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--contract-report", action="store_true", help="print the offline sources target mapper contract")
    mode.add_argument("--apply", action="store_true", help="write sources prototype target rows")
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
