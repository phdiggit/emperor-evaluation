from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import read_dotenv_values
from scripts.platform.jsonl_import_dry_run import apply_dry_run
from scripts.platform.jsonl_target_mapping import (
    BLOCKED_REPORT_TERMS,
    CANONICAL_JSONL_FILES,
    MAPPING_VERSION,
    JsonlFileMapping,
    build_mappings,
    is_reference_risk_field,
)
from scripts.platform.postgres_bootstrap import drop_schema, quote_identifier, schema_exists


PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
DEFAULT_SCHEMA = "emperor_eval_staging_mapper"
TOOL_VERSION = "jsonl-staging-mapper-v1"
STAGING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stg_jsonl_rows (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_row_id BIGINT NOT NULL REFERENCES import_rows(id),
    source_file TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    jsonl_code TEXT,
    mapping_version TEXT NOT NULL,
    target_tables TEXT[] NOT NULL,
    staging_only BOOLEAN NOT NULL DEFAULT false,
    direct_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    candidate_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    range_filter_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    reference_risk_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    unknown_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stg_jsonl_import_row_uk UNIQUE (import_row_id)
);

CREATE INDEX IF NOT EXISTS stg_jsonl_source_idx ON stg_jsonl_rows (source_file, line_no);
CREATE INDEX IF NOT EXISTS stg_jsonl_code_idx ON stg_jsonl_rows (jsonl_code);
CREATE INDEX IF NOT EXISTS stg_jsonl_reference_risk_gin
    ON stg_jsonl_rows USING GIN (reference_risk_fields);
"""
LIMITATIONS = (
    "本 prototype 只写隔离 schema 内的 imports、import_rows 和 staging 表。",
    "本 prototype 不写正式 PostgreSQL target business tables。",
    "reference risk 字段只结构化保留，不能直接转换成外键。",
    "thematic anchor 文件在本阶段保持 staging-only。",
    "staging -> target mapper、resolver 和人工复核流程必须另开 PR。",
)


@dataclass(frozen=True)
class ResolvedDsn:
    dsn: str | None
    source: str

    @property
    def present(self) -> bool:
        return bool(self.dsn)


@dataclass(frozen=True)
class SourceImportRow:
    id: int
    source_file: str
    line_no: int
    import_status: str
    error: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class StagingRow:
    import_row_id: int | None
    source_file: str
    line_no: int
    jsonl_code: str | None
    mapping_version: str
    target_tables: tuple[str, ...]
    staging_only: bool
    direct_fields: dict[str, Any]
    candidate_fields: dict[str, Any]
    payload_fields: dict[str, Any]
    range_filter_fields: dict[str, Any]
    reference_risk_fields: dict[str, Any]
    unknown_fields: list[str]
    validation_errors: list[str]


def resolve_dsn(
    *,
    env: Mapping[str, str] | None = None,
    env_path: Path = ROOT / ".env",
) -> ResolvedDsn:
    if env is None:
        env = os.environ
    if env.get(PRIMARY_ENV_DSN):
        return ResolvedDsn(env[PRIMARY_ENV_DSN], f"env:{PRIMARY_ENV_DSN}")
    dotenv = read_dotenv_values(env_path)
    if dotenv.get(PRIMARY_ENV_DSN):
        return ResolvedDsn(dotenv[PRIMARY_ENV_DSN], f".env:{PRIMARY_ENV_DSN}")
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
    mappings = build_mappings()
    files_seen = [
        relative.replace("\\", "/")
        for relative in relative_files
        if (source_root / relative).exists()
    ]
    rows_by_file: dict[str, int] = {relative: 0 for relative in files_seen}
    staging_only_files: set[str] = {
        relative for relative in files_seen if mappings.get(relative) and mappings[relative].staging_only
    }
    target_table_candidates: set[str] = set()
    for relative in files_seen:
        mapping = mappings.get(relative)
        if mapping:
            target_table_candidates.update(mapping.target_tables)

    for row in staging_rows:
        rows_by_file[row.source_file] = rows_by_file.get(row.source_file, 0) + 1
        target_table_candidates.update(row.target_tables)
        if row.staging_only:
            staging_only_files.add(row.source_file)

    files_missing = [
        relative.replace("\\", "/")
        for relative in relative_files
        if not (source_root / relative).exists()
    ]
    report = {
        "mode": "contract-report",
        "mapping_version": MAPPING_VERSION,
        "default_tests_require_postgres": False,
        "source_files": files_seen,
        "files_missing": files_missing,
        "rows_total": len(source_rows),
        "rows_mapped": len(staging_rows),
        "rows_with_reference_risk": count_rows_with(staging_rows, "reference_risk_fields"),
        "rows_with_unknown_fields": count_rows_with(staging_rows, "unknown_fields"),
        "rows_with_validation_errors": count_rows_with(staging_rows, "validation_errors"),
        "staging_only_files": sorted(staging_only_files),
        "target_table_candidates": sorted(target_table_candidates),
        "rows_by_file": rows_by_file,
        "mapped_files": sorted(mappings),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def load_source_rows(
    *,
    source_root: Path,
    relative_files: Sequence[str],
) -> list[SourceImportRow]:
    rows: list[SourceImportRow] = []
    next_id = 1
    for relative in relative_files:
        path = source_root / relative
        display_path = relative.replace("\\", "/")
        if not path.exists():
            continue
        for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            error: str | None = None
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                payload = {"raw_line": raw_line}
                error = f"invalid JSON: {exc.msg}"
            if not isinstance(payload, dict):
                payload = {"value": payload}
                error = "JSON payload must be an object"
            rows.append(
                SourceImportRow(
                    id=next_id,
                    source_file=display_path,
                    line_no=line_no,
                    import_status="error" if error else "accepted",
                    error=error,
                    payload=payload,
                )
            )
            next_id += 1
    return rows


def build_staging_rows(rows: Sequence[SourceImportRow]) -> list[StagingRow]:
    mappings = build_mappings()
    return [classify_import_row(row, mappings.get(row.source_file)) for row in rows]


def classify_import_row(row: SourceImportRow, mapping: JsonlFileMapping | None) -> StagingRow:
    validation_errors: list[str] = []
    if row.error:
        validation_errors.append(row.error)
    if mapping is None:
        validation_errors.append("missing mapping contract for source file")
        return StagingRow(
            import_row_id=row.id,
            source_file=row.source_file,
            line_no=row.line_no,
            jsonl_code=None,
            mapping_version=MAPPING_VERSION,
            target_tables=(),
            staging_only=True,
            direct_fields={},
            candidate_fields={},
            payload_fields=sanitize_field_values(row.payload),
            range_filter_fields={},
            reference_risk_fields={},
            unknown_fields=[],
            validation_errors=validation_errors,
        )

    direct_fields: dict[str, Any] = {}
    candidate_fields: dict[str, Any] = {}
    payload_fields: dict[str, Any] = {}
    range_filter_fields: dict[str, Any] = {}
    reference_risk_fields: dict[str, Any] = {}
    unknown_fields: list[str] = []

    for field, value in row.payload.items():
        if field in mapping.direct_fields:
            direct_fields[field] = {"target": mapping.direct_fields[field], "value": value}
        elif field in mapping.candidate_fields:
            candidate_fields[field] = {"targets": list(mapping.candidate_fields[field]), "value": value}
        elif field in mapping.payload_fields:
            payload_fields[field] = value
        elif field in mapping.range_filter_fields:
            range_filter_fields[field] = {"rule": mapping.range_filter_fields[field], "value": value}
        elif field in mapping.reference_risk_fields:
            reference_risk_fields[field] = {"reason": mapping.reference_risk_fields[field], "value": value}
        elif is_reference_risk_field(field):
            reference_risk_fields[field] = {"reason": "dynamic reference risk field; resolver required", "value": value}
        else:
            unknown_fields.append(sanitize_report_field(field))

    for required in mapping.required_fields:
        if not row.payload.get(required):
            validation_errors.append(f"missing required field: {sanitize_report_field(required)}")

    jsonl_code = str(row.payload.get(mapping.code_field) or "").strip() if mapping.code_field else ""
    return StagingRow(
        import_row_id=row.id,
        source_file=row.source_file,
        line_no=row.line_no,
        jsonl_code=jsonl_code or None,
        mapping_version=MAPPING_VERSION,
        target_tables=tuple(mapping.target_tables),
        staging_only=mapping.staging_only,
        direct_fields=sanitize_field_values(direct_fields),
        candidate_fields=sanitize_field_values(candidate_fields),
        payload_fields=sanitize_field_values(payload_fields),
        range_filter_fields=sanitize_field_values(range_filter_fields),
        reference_risk_fields=sanitize_field_values(reference_risk_fields),
        unknown_fields=sorted(unknown_fields),
        validation_errors=validation_errors,
    )


def apply_staging_mapper(
    dsn: str,
    *,
    schema: str = DEFAULT_SCHEMA,
    source_root: Path = ROOT,
    drop_schema_after: bool = False,
) -> dict[str, Any]:
    dry_run_report = apply_dry_run(dsn, schema=schema, source_root=source_root, drop_schema_after=False)
    import_id = int(dry_run_report["import_id"])
    dropped = False
    try:
        create_staging_tables(dsn, schema=schema)
        import_rows = fetch_import_rows(dsn, schema=schema, import_id=import_id)
        staging_rows = build_staging_rows(import_rows)
        inserted = insert_staging_rows(dsn, schema=schema, rows=staging_rows)
        db_report = inspect_staging_report(dsn, schema=schema, import_id=import_id)
    finally:
        if drop_schema_after:
            drop_schema(dsn, schema)
            dropped = True

    report = {
        "mode": "apply",
        "schema": schema,
        "import_rows": dry_run_report["inserted_import_rows"],
        "staging_rows": inserted,
        "reference_risk_rows": db_report["reference_risk_rows"],
        "unknown_field_rows": db_report["unknown_field_rows"],
        "validation_error_rows": db_report["validation_error_rows"],
        "staging_only_rows": db_report["staging_only_rows"],
        "dropped": dropped,
        "schema_exists_after_drop": schema_exists(dsn, schema) if drop_schema_after else None,
    }
    assert_report_has_no_blocked_terms(report)
    return report


def create_staging_tables(dsn: str, *, schema: str) -> None:
    import psycopg

    schema_ident = quote_identifier(schema)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            cur.execute(STAGING_TABLE_SQL)
        conn.commit()


def fetch_import_rows(dsn: str, *, schema: str, import_id: int) -> list[SourceImportRow]:
    import psycopg

    schema_ident = quote_identifier(schema)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            cur.execute(
                """
                SELECT id, source_file, line_no, import_status, error, payload
                FROM import_rows
                WHERE import_id = %s
                ORDER BY id
                """,
                (import_id,),
            )
            db_rows = cur.fetchall()
    return [
        SourceImportRow(
            id=int(row[0]),
            source_file=row[1],
            line_no=int(row[2]),
            import_status=row[3],
            error=row[4],
            payload=dict(row[5]),
        )
        for row in db_rows
    ]


def insert_staging_rows(dsn: str, *, schema: str, rows: Sequence[StagingRow]) -> int:
    import psycopg
    from psycopg.types.json import Jsonb

    schema_ident = quote_identifier(schema)
    values = [
        (
            row.import_row_id,
            row.source_file,
            row.line_no,
            row.jsonl_code,
            row.mapping_version,
            list(row.target_tables),
            row.staging_only,
            Jsonb(row.direct_fields),
            Jsonb(row.candidate_fields),
            Jsonb(row.payload_fields),
            Jsonb(row.range_filter_fields),
            Jsonb(row.reference_risk_fields),
            Jsonb(row.unknown_fields),
            Jsonb(row.validation_errors),
        )
        for row in rows
    ]
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            cur.executemany(
                """
                INSERT INTO stg_jsonl_rows (
                    import_row_id, source_file, line_no, jsonl_code, mapping_version,
                    target_tables, staging_only, direct_fields, candidate_fields,
                    payload_fields, range_filter_fields, reference_risk_fields,
                    unknown_fields, validation_errors
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                values,
            )
        conn.commit()
    return len(values)


def inspect_staging_report(dsn: str, *, schema: str, import_id: int) -> dict[str, int]:
    import psycopg

    schema_ident = quote_identifier(schema)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE reference_risk_fields <> '{}'::jsonb),
                    COUNT(*) FILTER (WHERE unknown_fields <> '[]'::jsonb),
                    COUNT(*) FILTER (WHERE validation_errors <> '[]'::jsonb),
                    COUNT(*) FILTER (WHERE staging_only)
                FROM stg_jsonl_rows s
                JOIN import_rows r ON r.id = s.import_row_id
                WHERE r.import_id = %s
                """,
                (import_id,),
            )
            row = cur.fetchone()
    return {
        "reference_risk_rows": int(row[0] or 0),
        "unknown_field_rows": int(row[1] or 0),
        "validation_error_rows": int(row[2] or 0),
        "staging_only_rows": int(row[3] or 0),
    }


def count_rows_with(rows: Sequence[StagingRow], field_name: str) -> int:
    return sum(1 for row in rows if getattr(row, field_name))


def sanitize_field_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {sanitize_report_field(str(key)): sanitize_field_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_field_values(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_field_values(item) for item in value]
    return value


def sanitize_report_field(field: str) -> str:
    lowered = field.lower()
    if any(term in lowered for term in BLOCKED_REPORT_TERMS):
        return "[blocked-report-field]"
    return field


def assert_report_has_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False, sort_keys=True).lower()
    for term in BLOCKED_REPORT_TERMS:
        if term in text:
            raise AssertionError(f"report unexpectedly contains {term!r}")


def is_psycopg_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def rows_as_dicts(rows: Sequence[StagingRow]) -> list[dict[str, Any]]:
    return [asdict(row) for row in rows]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Map canonical JSONL import_rows payloads into staging rows.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--contract-report", action="store_true", help="print a local staging mapping report")
    mode.add_argument("--apply", action="store_true", help="write staging rows in an isolated PostgreSQL schema")
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
        result = apply_staging_mapper(
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
