from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import read_dotenv_values
from scripts.platform.postgres_bootstrap import (
    drop_schema,
    quote_identifier,
    render_bootstrap_sql,
    run_pg_sql,
    schema_exists,
)


PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
DEFAULT_SCHEMA = "emperor_eval_import_dry_run"
TOOL_VERSION = "jsonl-import-dry-run-v1"
CANONICAL_JSONL_FILES = (
    "data/query_profiles.jsonl",
    "data/search_logs.jsonl",
    "data/sources.jsonl",
    "data/evidence_cards.jsonl",
    "data/evidence_clusters.jsonl",
    "data/thematic_anchors.jsonl",
    "data/thematic_anchor_objects.jsonl",
    "data/thematic_anchor_events.jsonl",
    "data/thematic_anchor_mechanisms.jsonl",
)
TARGET_TABLE_BY_FILE = {
    "query_profiles.jsonl": "query_profiles",
    "search_logs.jsonl": "search_tasks_or_search_logs_legacy",
    "sources.jsonl": "src_docs_doc_revs_passages_candidate_source",
    "evidence_cards.jsonl": "evd_cards",
    "evidence_clusters.jsonl": "clusters",
    "thematic_anchors.jsonl": "anchors_anchor_links_candidate_mapping",
    "thematic_anchor_objects.jsonl": "anchors_anchor_links_candidate_mapping",
    "thematic_anchor_events.jsonl": "anchors_anchor_links_candidate_mapping",
    "thematic_anchor_mechanisms.jsonl": "anchors_anchor_links_candidate_mapping",
}
CODE_FIELD_BY_FILE = {
    "query_profiles.jsonl": "query_profile_id",
    "search_logs.jsonl": "search_id",
    "sources.jsonl": "source_id",
    "evidence_cards.jsonl": "evidence_id",
    "evidence_clusters.jsonl": "cluster_id",
    "thematic_anchors.jsonl": "anchor_id",
    "thematic_anchor_objects.jsonl": "anchor_id",
    "thematic_anchor_events.jsonl": "anchor_id",
    "thematic_anchor_mechanisms.jsonl": "anchor_id",
}
RECOMMENDED_FIELDS_BY_FILE = {
    "query_profiles.jsonl": ("query_profile_id", "item", "subitem"),
    "search_logs.jsonl": ("search_id", "query", "result_status"),
    "sources.jsonl": ("source_id", "title", "url"),
    "evidence_cards.jsonl": ("evidence_id", "source_id", "quote_short"),
    "evidence_clusters.jsonl": ("cluster_id", "linked_evidence_ids", "summary"),
    "thematic_anchors.jsonl": ("anchor_id", "linked_evidence_ids", "linked_cluster_ids"),
    "thematic_anchor_objects.jsonl": ("anchor_id", "object_name", "review_status"),
    "thematic_anchor_events.jsonl": ("anchor_id", "object_name", "review_status"),
    "thematic_anchor_mechanisms.jsonl": ("anchor_id", "object_name", "review_status"),
}
LIMITATIONS = (
    "本 dry-run 不等于正式迁库。",
    "本 dry-run 不写业务事实表。",
    "本 dry-run 不验证所有跨表语义引用。",
    "正式切库前仍需 staging -> target table 映射规则和人工复核。",
)
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")


@dataclass(frozen=True)
class ResolvedDsn:
    dsn: str | None
    source: str

    @property
    def present(self) -> bool:
        return bool(self.dsn)


@dataclass(frozen=True)
class ImportRowDraft:
    source_file: str
    line_no: int
    payload_hash: str
    import_status: str
    target_table: str | None
    target_id: None
    error: str | None
    payload: dict[str, Any]


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
) -> tuple[dict[str, Any], list[ImportRowDraft]]:
    files_seen: list[str] = []
    files_missing: list[str] = []
    rows: list[ImportRowDraft] = []
    duplicate_lines: dict[str, dict[str, list[int]]] = {}
    missing_fields: dict[str, dict[str, list[int]]] = {}
    reference_risks: dict[str, list[str]] = {}
    unknown_target_mapping: list[str] = []
    rows_valid_json = 0
    rows_invalid_json = 0
    rows_with_code = 0
    code_lines_by_file: dict[str, dict[str, list[int]]] = {}

    for relative in relative_files:
        path = source_root / relative
        display_path = relative.replace("\\", "/")
        name = Path(relative).name
        target_table = TARGET_TABLE_BY_FILE.get(name)
        if target_table is None:
            unknown_target_mapping.append(display_path)
        if not path.exists():
            files_missing.append(display_path)
            continue
        files_seen.append(display_path)
        code_field = CODE_FIELD_BY_FILE.get(name)
        recommended_fields = RECOMMENDED_FIELDS_BY_FILE.get(name, ())
        code_lines: dict[str, list[int]] = {}

        for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            payload_hash = hash_payload_text(raw_line)
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                rows_invalid_json += 1
                rows.append(
                    ImportRowDraft(
                        source_file=display_path,
                        line_no=line_no,
                        payload_hash=payload_hash,
                        import_status="error",
                        target_table=target_table,
                        target_id=None,
                        error=f"invalid JSON: {exc.msg}",
                        payload={"raw_line": raw_line},
                    )
                )
                continue
            if not isinstance(payload, dict):
                rows_invalid_json += 1
                rows.append(
                    ImportRowDraft(
                        source_file=display_path,
                        line_no=line_no,
                        payload_hash=payload_hash,
                        import_status="error",
                        target_table=target_table,
                        target_id=None,
                        error="JSON payload must be an object",
                        payload={"value": payload},
                    )
                )
                continue

            rows_valid_json += 1
            normalized_hash = hash_payload_object(payload)
            code = str(payload.get(code_field) or "").strip() if code_field else ""
            if code:
                rows_with_code += 1
                code_lines.setdefault(code, []).append(line_no)
            missing = [field for field in recommended_fields if not payload.get(field)]
            if missing:
                by_field = missing_fields.setdefault(display_path, {})
                for field in missing:
                    by_field.setdefault(field, []).append(line_no)
            risk_keys = sorted(key for key in payload if is_reference_risk_key(key))
            if risk_keys:
                reference_risks.setdefault(display_path, [])
                for key in risk_keys:
                    if key not in reference_risks[display_path]:
                        reference_risks[display_path].append(key)
            rows.append(
                ImportRowDraft(
                    source_file=display_path,
                    line_no=line_no,
                    payload_hash=normalized_hash,
                    import_status="accepted",
                    target_table=target_table,
                    target_id=None,
                    error=None,
                    payload=payload,
                )
            )

        duplicates = {code: lines for code, lines in code_lines.items() if len(lines) > 1}
        if duplicates:
            duplicate_lines[display_path] = duplicates
        code_lines_by_file[display_path] = code_lines

    report = {
        "mode": "contract-report",
        "files_seen": files_seen,
        "files_missing": files_missing,
        "rows_total": rows_valid_json + rows_invalid_json,
        "rows_valid_json": rows_valid_json,
        "rows_invalid_json": rows_invalid_json,
        "rows_with_code": rows_with_code,
        "duplicate_codes_by_file": duplicate_lines,
        "missing_recommended_fields_by_file": missing_fields,
        "unknown_target_mapping": unknown_target_mapping,
        "reference_risk_summary": reference_risks,
        "would_write_import_rows": len(rows),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report, rows


def apply_dry_run(
    dsn: str,
    *,
    schema: str = DEFAULT_SCHEMA,
    source_root: Path = ROOT,
    drop_schema_after: bool = False,
) -> dict[str, Any]:
    report, rows = build_contract_report(source_root=source_root)
    import_code = f"jsonl_dry_run_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
    input_hash = hash_payload_object({"rows": [row.payload_hash for row in rows]})

    run_pg_sql(dsn, render_bootstrap_sql(schema))
    db_report: dict[str, Any] = {}
    dropped = False
    try:
        import_id, inserted_rows = insert_dry_run_rows(
            dsn,
            schema=schema,
            import_code=import_code,
            input_hash=input_hash,
            rows=rows,
            report=report,
        )
        db_report = inspect_import_report(dsn, schema=schema, import_id=import_id)
        report = {
            **report,
            "mode": "apply",
            "schema": schema,
            "import_code": import_code,
            "import_id": import_id,
            "inserted_import_rows": inserted_rows,
            "database_report": db_report,
        }
    finally:
        if drop_schema_after:
            drop_schema(dsn, schema)
            dropped = True

    report["drop_schema_after"] = drop_schema_after
    report["dropped"] = dropped
    if drop_schema_after:
        report["schema_exists_after_drop"] = schema_exists(dsn, schema)
    assert_report_has_no_blocked_terms(report)
    return report


def insert_dry_run_rows(
    dsn: str,
    *,
    schema: str,
    import_code: str,
    input_hash: str,
    rows: Sequence[ImportRowDraft],
    report: Mapping[str, Any],
) -> tuple[int, int]:
    import psycopg
    from psycopg.types.json import Jsonb

    schema_ident = quote_identifier(schema)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            cur.execute(
                """
                INSERT INTO imports (
                    code, source_kind, source_ref, status, tool_version,
                    input_hash, row_count, meta
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    import_code,
                    "canonical_jsonl",
                    "data/*.jsonl",
                    "dry_run",
                    TOOL_VERSION,
                    input_hash,
                    len(rows),
                    Jsonb(summarize_report_for_db(report)),
                ),
            )
            import_id = cur.fetchone()[0]
            row_values = [
                (
                    f"{import_code}_row_{idx:06d}",
                    import_id,
                    row.source_file,
                    row.line_no,
                    row.payload_hash,
                    row.import_status,
                    row.target_table,
                    row.target_id,
                    row.error,
                    Jsonb(row.payload),
                )
                for idx, row in enumerate(rows, start=1)
            ]
            cur.executemany(
                """
                INSERT INTO import_rows (
                    code, import_id, source_file, line_no, payload_hash,
                    import_status, target_table, target_id, error, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                row_values,
            )
            cur.execute(
                """
                UPDATE imports
                SET ended_at = now(), status = 'dry_run', row_count = %s
                WHERE id = %s
                """,
                (len(rows), import_id),
            )
        conn.commit()
    return import_id, len(row_values)


def inspect_import_report(dsn: str, *, schema: str, import_id: int) -> dict[str, Any]:
    import psycopg

    schema_ident = quote_identifier(schema)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            cur.execute(
                """
                SELECT
                    i.code,
                    i.status,
                    i.row_count,
                    COUNT(r.id) AS import_rows,
                    COUNT(*) FILTER (WHERE r.import_status = 'error') AS error_rows
                FROM imports i
                LEFT JOIN import_rows r ON r.import_id = i.id
                WHERE i.id = %s
                GROUP BY i.id
                """,
                (import_id,),
            )
            row = cur.fetchone()
    if row is None:
        return {}
    return {
        "import_code": row[0],
        "import_status": row[1],
        "row_count": row[2],
        "import_rows": row[3],
        "error_rows": row[4],
    }


def summarize_report_for_db(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "files_seen": report["files_seen"],
        "files_missing": report["files_missing"],
        "rows_total": report["rows_total"],
        "rows_valid_json": report["rows_valid_json"],
        "rows_invalid_json": report["rows_invalid_json"],
        "limitations": report["limitations"],
    }


def hash_payload_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_payload_object(value: Any) -> str:
    normalized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hash_payload_text(normalized)


def is_reference_risk_key(key: str) -> bool:
    lowered = key.lower()
    return (
        lowered.endswith("_ids")
        or lowered.startswith("linked_")
        or lowered.startswith("source_")
        or lowered == "source_id"
        or lowered.startswith("cross_item")
    )


def assert_report_has_no_blocked_terms(report: Mapping[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False, sort_keys=True)
    for term in BLOCKED_REPORT_TERMS:
        if term in text:
            raise AssertionError(f"report unexpectedly contains {term!r}")


def is_psycopg_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def rows_as_dicts(rows: Sequence[ImportRowDraft]) -> list[dict[str, Any]]:
    return [asdict(row) for row in rows]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run a local JSONL import dry-run audit.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--contract-report", action="store_true", help="parse JSONL files and print a local report")
    mode.add_argument("--apply", action="store_true", help="write dry-run rows to imports/import_rows in PostgreSQL")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help=f"isolated schema name, default: {DEFAULT_SCHEMA}")
    parser.add_argument("--drop-schema-after", action="store_true", help="drop the isolated schema after apply")
    parser.add_argument("--source-root", type=Path, default=ROOT, help="repository root or fixture root")
    args = parser.parse_args(argv)

    if args.drop_schema_after and not args.apply:
        parser.error("--drop-schema-after requires --apply")

    if args.contract_report or not (args.check or args.apply):
        report, _rows = build_contract_report(source_root=args.source_root)
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")
        return 0

    resolved = resolve_dsn()
    if args.apply:
        reason = integration_skip_reason(resolved)
        if reason:
            sys.stderr.write(f"skip: {reason}\n")
            return 2
        result = apply_dry_run(
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
