from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_staging_mapper import (
    StagingRow,
    apply_staging_mapper,
    build_staging_rows,
    load_source_rows,
)
from scripts.platform.core.db_env import (
    ResolvedDsn,
    is_psycopg_available,
    make_check_environment,
    make_integration_skip_reason,
    make_resolve_dsn,
    make_validate_isolated_schema,
)
from scripts.platform.jsonl_staging_resolver_contract import RESOLVER_VERSION
from scripts.platform.jsonl_target_mapping import MAPPING_VERSION, assert_report_has_no_blocked_terms
from scripts.platform.postgres_bootstrap import drop_schema, quote_identifier, schema_exists


PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
DEFAULT_SCHEMA = "emperor_eval_evidence_clusters_resolver"
TOOL_VERSION = "jsonl-evidence-clusters-resolver-v1"
TARGET_SOURCE_FILES = ("data/evidence_clusters.jsonl",)
TARGET_TABLES = ("clusters", "cluster_evd_candidates")
DIRECT_FIELD_PLAN = {
    "cluster_id": {"target_column": "clusters.code", "source_bucket": "direct_fields"},
    "summary": {"target_column": "clusters.summary", "source_bucket": "direct_fields"},
    "status": {"target_column": "clusters.status candidate", "source_bucket": "direct_fields"},
    "cluster_type": {"target_column": "clusters.cluster_type candidate", "source_bucket": "candidate_fields"},
    "candidate_strength": {"target_column": "clusters.candidate_strength candidate", "source_bucket": "direct_fields"},
    "polarity": {"target_column": "clusters.polarity candidate", "source_bucket": "direct_fields"},
}
PAYLOAD_FIELD_PLAN = {
    "adjudication_status": "clusters.payload review_state_only",
    "notes": "clusters.payload",
    "note": "clusters.payload if present",
    "meta": "clusters.payload",
    "five_axis_assessment": "clusters.payload",
    "upper_probe": "clusters.payload diagnostic_only",
    "upper_bound": "clusters.payload diagnostic_only",
    "cross_item_split": "clusters.payload manual_review_only",
}
LIMITATIONS = (
    "This tool covers only data/evidence_clusters.jsonl.",
    "Contract report mode is offline and does not read environment files.",
    "Cluster rows are relaxed prototype rows in an isolated schema only.",
    "linked_evidence_ids remain unresolved evidence code candidates.",
    "The tool does not write production relationship, source-link, anchor, adjudication, or release tables.",
    "Review-state fields are kept as payload or manual-review signals only.",
)


resolve_dsn = make_resolve_dsn()
check_environment = make_check_environment(resolve_dsn)
integration_skip_reason = make_integration_skip_reason(
    resolve_dsn,
    missing_reason=f"{PRIMARY_ENV_DSN} is not set",
)
validate_isolated_schema = make_validate_isolated_schema(
    quote_identifier,
    public_schema_message="refusing to write resolver prototype into public schema",
)


def build_contract_report(
    *,
    source_root: Path = ROOT,
    relative_files: Sequence[str] = TARGET_SOURCE_FILES,
) -> dict[str, Any]:
    source_rows = load_source_rows(source_root=source_root, relative_files=relative_files)
    staging_rows = [row for row in build_staging_rows(source_rows) if row.source_file in TARGET_SOURCE_FILES]
    line_index = build_field_line_index(source_rows)
    rows_by_source_file = count_source_rows(source_rows)
    targetable_rows = [row for row in staging_rows if is_targetable_cluster_row(row)]
    linked_evidence_summary = build_linked_evidence_summary(source_rows)

    report = {
        "mode": "contract-report",
        "tool_version": TOOL_VERSION,
        "mapping_version": MAPPING_VERSION,
        "resolver_version": RESOLVER_VERSION,
        "source_files": sorted(rows_by_source_file),
        "target_tables": list(TARGET_TABLES),
        "rows_by_source_file": rows_by_source_file,
        "candidate_rows_by_target": {"clusters": len(targetable_rows), "cluster_evd_candidates": linked_evidence_summary["candidate_count"]},
        "direct_field_plan": build_direct_field_plan(line_index),
        "payload_field_plan": build_payload_field_plan(line_index),
        "linked_evidence_plan": build_linked_evidence_plan(line_index, linked_evidence_summary),
        "cluster_evd_candidate_plan": build_cluster_evd_candidate_plan(linked_evidence_summary),
        "resolver_blocked_fields": build_resolver_blocked_fields(line_index),
        "manual_review_fields_by_file": build_manual_review_fields_by_file(line_index),
        "blocked_relationship_writes": build_blocked_relationship_writes(line_index),
        "unresolved_references_by_file": build_unresolved_references_by_file(linked_evidence_summary),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def build_field_line_index(source_rows: Sequence[Any]) -> dict[str, dict[str, list[int]]]:
    index: dict[str, dict[str, list[int]]] = {}
    for row in source_rows:
        if row.source_file not in TARGET_SOURCE_FILES:
            continue
        fields = index.setdefault(row.source_file, {})
        for field in row.payload:
            safe_field = sanitize_report_field(field)
            fields.setdefault(safe_field, []).append(row.line_no)
    return index


def count_source_rows(source_rows: Sequence[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in source_rows:
        if row.source_file in TARGET_SOURCE_FILES:
            counts[row.source_file] = counts.get(row.source_file, 0) + 1
    return counts


def build_direct_field_plan(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, dict[str, Any]]:
    fields = line_index.get("data/evidence_clusters.jsonl", {})
    return {
        field: {
            **plan,
            "present": field in fields,
            "line_numbers": sorted(fields.get(field, [])),
        }
        for field, plan in DIRECT_FIELD_PLAN.items()
    }


def build_payload_field_plan(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, dict[str, Any]]:
    fields = line_index.get("data/evidence_clusters.jsonl", {})
    return {
        field: {
            "target_column": target,
            "present": field in fields,
            "line_numbers": sorted(fields.get(field, [])),
        }
        for field, target in PAYLOAD_FIELD_PLAN.items()
    }


def build_linked_evidence_summary(source_rows: Sequence[Any]) -> dict[str, Any]:
    candidate_rows: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    manual_review_lines: list[int] = []
    observed_lines: list[int] = []

    for row in source_rows:
        if row.source_file not in TARGET_SOURCE_FILES:
            continue
        raw_value = row.payload.get("linked_evidence_ids")
        if raw_value is None:
            continue
        observed_lines.append(row.line_no)
        values = normalize_linked_evidence_ids(raw_value)
        seen_on_line: set[str] = set()
        for value in values:
            candidate = {
                "cluster_code": str(row.payload.get("cluster_id") or ""),
                "evidence_code": value,
                "source_file": row.source_file,
                "line_no": row.line_no,
                "resolver_status": "unresolved_candidate",
                "blocked_action": "cluster_evd_write",
            }
            candidate_rows.append(candidate)
            if value in seen_on_line:
                duplicates.append(
                    {
                        "cluster_code": candidate["cluster_code"],
                        "evidence_code": value,
                        "source_file": row.source_file,
                        "line_no": row.line_no,
                    }
                )
                manual_review_lines.append(row.line_no)
            seen_on_line.add(value)

    return {
        "observed_lines": sorted(set(observed_lines)),
        "candidate_count": len(candidate_rows),
        "candidates": candidate_rows,
        "duplicate_link_candidates": duplicates,
        "manual_review_lines": sorted(set(manual_review_lines)),
    }


def normalize_linked_evidence_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    elif value in (None, ""):
        raw_values = []
    else:
        raw_values = [value]
    return [str(item).strip() for item in raw_values if str(item).strip()]


def build_linked_evidence_plan(
    line_index: Mapping[str, Mapping[str, Sequence[int]]],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    fields = line_index.get("data/evidence_clusters.jsonl", {})
    return {
        "source_field": "linked_evidence_ids",
        "line_numbers": sorted(fields.get("linked_evidence_ids", [])),
        "observed": bool(fields.get("linked_evidence_ids")),
        "evidence_code_candidates": summary["candidate_count"],
        "missing_evidence_code_candidates": [],
        "duplicate_link_candidates": summary["duplicate_link_candidates"],
        "manual_review_required": bool(summary["manual_review_lines"]),
        "blocked_action": "cluster_evd_write",
        "allowed_action": "unresolved_cluster_evd_candidate_report",
        "resolution_status": "not_resolved_in_contract_report",
    }


def build_cluster_evd_candidate_plan(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target_table": "cluster_evd_candidates",
        "formal_relationship_table": False,
        "columns": [
            "cluster_code",
            "evidence_code",
            "source_file",
            "line_no",
            "resolver_status",
            "blocked_action",
            "reason",
            "payload",
        ],
        "resolver_status_allowed": ["unresolved_candidate", "manual_review_required"],
        "blocked_action": "cluster_evd_write",
        "candidate_rows": summary["candidate_count"],
        "writes_cluster_evd": False,
    }


def build_resolver_blocked_fields(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, list[dict[str, Any]]]:
    fields = line_index.get("data/evidence_clusters.jsonl", {})
    blocked: list[dict[str, Any]] = []
    if "linked_evidence_ids" in fields:
        blocked.append(
            {
                "source_file": "data/evidence_clusters.jsonl",
                "field": "linked_evidence_ids",
                "resolver_domain": "evidence_card",
                "blocked_action": "cluster_evd_write",
                "allowed_action": "unresolved_cluster_evd_candidate_report",
                "line_numbers": sorted(fields["linked_evidence_ids"]),
            }
        )
    for field in ("adjudication_status", "five_axis_assessment", "upper_probe", "upper_bound"):
        if field not in fields:
            continue
        blocked.append(
            {
                "source_file": "data/evidence_clusters.jsonl",
                "field": field,
                "resolver_domain": "review_state",
                "blocked_action": "downstream_business_conclusion_write",
                "allowed_action": "clusters_payload_or_diagnostic_only",
                "line_numbers": sorted(fields[field]),
            }
        )
    return {"data/evidence_clusters.jsonl": blocked} if blocked else {}


def build_manual_review_fields_by_file(
    line_index: Mapping[str, Mapping[str, Sequence[int]]],
) -> dict[str, list[dict[str, Any]]]:
    fields = line_index.get("data/evidence_clusters.jsonl", {})
    manual = [
        {
            "field": field,
            "line_numbers": sorted(fields[field]),
            "reason": "manual review required before relationship or conclusion use",
        }
        for field in ("linked_evidence_ids", "adjudication_status", "five_axis_assessment", "upper_probe", "upper_bound", "cross_item_split")
        if field in fields
    ]
    return {"data/evidence_clusters.jsonl": manual} if manual else {}


def build_blocked_relationship_writes(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> list[dict[str, Any]]:
    fields = line_index.get("data/evidence_clusters.jsonl", {})
    linked_rows = sorted(fields.get("linked_evidence_ids", []))
    blocked = [
        {
            "source_file": "data/evidence_clusters.jsonl",
            "target_table": "cluster_evd",
            "blocked_action": "write_evidence_cluster_relationship",
            "allowed_action": "unresolved_cluster_evd_candidate_report",
            "line_numbers": linked_rows,
        }
    ]
    return [item for item in blocked if item["line_numbers"]]


def build_unresolved_references_by_file(summary: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if not summary["observed_lines"]:
        return {}
    return {
        "data/evidence_clusters.jsonl": [
            {
                "field": "linked_evidence_ids",
                "line_numbers": summary["observed_lines"],
                "candidate_count": summary["candidate_count"],
                "kept_as": "unresolved_evidence_code_candidates",
                "blocked_action": "cluster_evd_write",
            }
        ]
    }


def apply_resolver(
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
        "cluster_rows": db_report.get("cluster_rows", 0),
        "cluster_evd_candidate_rows": db_report.get("cluster_evd_candidate_rows", 0),
        "blocked_cluster_evd_rows": db_report.get("blocked_cluster_evd_rows", 0),
        "manual_review_rows": db_report.get("manual_review_rows", 0),
        "dropped": dropped,
        "schema_exists_after_drop": schema_exists(dsn, schema) if drop_schema_after else None,
    }
    assert_report_has_no_blocked_terms(report)
    return report


def create_target_prototype_tables(dsn: str, *, schema: str) -> None:
    import psycopg

    schema_ident = quote_identifier(schema)
    sql = """
    DROP TABLE IF EXISTS cluster_evd_candidates CASCADE;
    DROP TABLE IF EXISTS clusters CASCADE;

    CREATE TABLE clusters (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        code TEXT NOT NULL,
        summary TEXT,
        status TEXT,
        cluster_type TEXT,
        candidate_strength JSONB,
        polarity TEXT,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT clusters_resolver_code_uk UNIQUE (code)
    );

    CREATE TABLE cluster_evd_candidates (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        cluster_code TEXT NOT NULL,
        evidence_code TEXT NOT NULL,
        source_file TEXT NOT NULL,
        line_no INTEGER NOT NULL,
        resolver_status TEXT NOT NULL CHECK (resolver_status IN ('unresolved_candidate', 'manual_review_required')),
        blocked_action TEXT NOT NULL CHECK (blocked_action = 'cluster_evd_write'),
        reason TEXT NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
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
                INSERT INTO clusters (code, summary, status, cluster_type, candidate_strength, polarity, payload)
                SELECT
                    jsonl_code,
                    direct_fields -> 'summary' ->> 'value',
                    direct_fields -> 'status' ->> 'value',
                    candidate_fields -> 'cluster_type' ->> 'value',
                    direct_fields -> 'candidate_strength' -> 'value',
                    direct_fields -> 'polarity' ->> 'value',
                    jsonb_strip_nulls(jsonb_build_object(
                        'source_file', source_file,
                        'line_no', line_no,
                        'adjudication_status', direct_fields -> 'adjudication_status' -> 'value',
                        'notes', payload_fields -> 'notes',
                        'note', payload_fields -> 'note',
                        'meta', payload_fields -> 'meta',
                        'five_axis_assessment', payload_fields -> 'five_axis_assessment',
                        'upper_probe', payload_fields -> 'upper_probe',
                        'upper_bound', payload_fields -> 'upper_bound',
                        'cross_item_split', unknown_fields -> 'cross_item_split',
                        'review_boundary', 'review_state_payload_only',
                        'relationship_boundary', 'linked_evidence_ids_unresolved_candidates'
                    ))
                FROM stg_jsonl_rows
                WHERE source_file = 'data/evidence_clusters.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                ON CONFLICT (code) DO NOTHING
                """
            )
            cluster_rows = cur.rowcount
            cur.execute(
                """
                INSERT INTO cluster_evd_candidates (
                    cluster_code, evidence_code, source_file, line_no,
                    resolver_status, blocked_action, reason, payload
                )
                SELECT
                    jsonl_code,
                    candidate.evidence_code,
                    source_file,
                    line_no,
                    'unresolved_candidate',
                    'cluster_evd_write',
                    'linked_evidence_ids require evidence card resolver output before relationship write',
                    jsonb_build_object(
                        'source_field', 'linked_evidence_ids',
                        'resolver_version', mapping_version,
                        'formal_relationship_table', false
                    )
                FROM stg_jsonl_rows
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    CASE
                        WHEN jsonb_typeof(reference_risk_fields -> 'linked_evidence_ids' -> 'value') = 'array'
                            THEN reference_risk_fields -> 'linked_evidence_ids' -> 'value'
                        WHEN reference_risk_fields ? 'linked_evidence_ids'
                            THEN jsonb_build_array(reference_risk_fields -> 'linked_evidence_ids' -> 'value')
                        ELSE '[]'::jsonb
                    END
                ) AS candidate(evidence_code)
                WHERE source_file = 'data/evidence_clusters.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                """
            )
            candidate_rows = cur.rowcount
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE reference_risk_fields ? 'linked_evidence_ids'),
                    COUNT(*) FILTER (
                        WHERE reference_risk_fields ? 'linked_evidence_ids'
                           OR direct_fields ? 'adjudication_status'
                           OR payload_fields ? 'five_axis_assessment'
                           OR payload_fields ? 'upper_probe'
                           OR payload_fields ? 'upper_bound'
                           OR unknown_fields ? 'cross_item_split'
                    )
                FROM stg_jsonl_rows
                WHERE source_file = 'data/evidence_clusters.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                """
            )
            row = cur.fetchone()
        conn.commit()
    return {
        "cluster_rows": int(cluster_rows),
        "cluster_evd_candidate_rows": int(candidate_rows),
        "blocked_cluster_evd_rows": int(row[0] or 0),
        "manual_review_rows": int(row[1] or 0),
    }


def is_targetable_cluster_row(row: StagingRow) -> bool:
    return (
        row.source_file in TARGET_SOURCE_FILES
        and bool(row.jsonl_code)
        and not row.staging_only
        and not row.validation_errors
    )


def sanitize_report_field(field: str) -> str:
    lowered = field.lower()
    if any(term in lowered for term in ("score", "rank", "final_score", "leaderboard")):
        return "[blocked-report-field]"
    return field


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Prepare evidence cluster relaxed rows and unresolved link candidates.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--contract-report", action="store_true", help="print the offline evidence cluster resolver contract")
    mode.add_argument("--apply", action="store_true", help="write evidence cluster resolver prototype rows")
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
        result = apply_resolver(
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
