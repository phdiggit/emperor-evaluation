from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.anchors_resolver_contract import (
    ANCHOR_SOURCE_FILES,
    REFERENCE_SOURCE_FILES,
    RESOLVER_STATUS_VALUES,
    RESOLVER_VERSION,
    SCHEMA_PROPOSAL_VERSION,
    SOURCE_FILES,
    build_anchor_candidates,
    build_anchor_link_candidates,
    build_anchor_reference_inputs,
    load_jsonl_rows,
)
from scripts.platform.core.db_env import (
    ResolvedDsn,
    is_psycopg_available,
    make_check_environment,
    make_integration_skip_reason,
    make_resolve_dsn,
    make_validate_isolated_schema,
)
from scripts.platform.jsonl_target_mapping import MAPPING_VERSION, assert_report_has_no_blocked_terms
from scripts.platform.postgres_bootstrap import drop_schema, quote_identifier, schema_exists


PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
DEFAULT_SCHEMA = "emperor_eval_anchors_target_mapper"
TOOL_VERSION = "jsonl-anchors-target-mapper-v1"
TARGET_TABLES = ("anchors", "anchor_links_candidates")
BLOCKED_ACTION = "anchor_links_write"
LIMITATIONS = (
    "contract_report_mode_is_offline",
    "apply_requires_explicit_primary_environment_dsn",
    "writes_only_isolated_relaxed_anchors_and_anchor_link_candidate_rows",
    "does_not_write_formal_anchor_links_or_other_business_targets",
    "anchor_reference_fields_remain_unresolved_resolver_inputs",
)


resolve_dsn = make_resolve_dsn()
check_environment = make_check_environment(resolve_dsn)
integration_skip_reason = make_integration_skip_reason(
    resolve_dsn,
    missing_reason=f"{PRIMARY_ENV_DSN} is not set",
)
validate_isolated_schema = make_validate_isolated_schema(
    quote_identifier,
    public_schema_message="refusing to write anchors target mapper prototype into public schema",
)


def build_contract_report(
    *,
    source_root: Path = ROOT,
    relative_files: Sequence[str] = SOURCE_FILES,
) -> dict[str, Any]:
    rows = load_jsonl_rows(source_root=source_root, relative_files=relative_files)
    anchor_candidates = build_anchor_candidates([row for row in rows if row.source_file in ANCHOR_SOURCE_FILES])
    reference_inputs = build_anchor_reference_inputs([row for row in rows if row.source_file in REFERENCE_SOURCE_FILES])
    link_candidates = build_anchor_link_candidates(reference_inputs)
    rows_by_source_file = count_rows_by_source_file(rows)
    anchor_rows = [candidate for candidate in anchor_candidates if candidate["resolver_status"] in RESOLVER_STATUS_VALUES]
    candidate_rows_by_target = {
        "anchors": len(anchor_rows),
        "anchor_links_candidates": len(link_candidates),
    }
    report = {
        "mode": "contract-report",
        "tool_version": TOOL_VERSION,
        "mapping_version": MAPPING_VERSION,
        "resolver_version": RESOLVER_VERSION,
        "schema_proposal_version": SCHEMA_PROPOSAL_VERSION,
        "source_files": sorted(rows_by_source_file),
        "target_tables": list(TARGET_TABLES),
        "rows_by_source_file": rows_by_source_file,
        "candidate_rows_by_target": candidate_rows_by_target,
        "direct_field_plan": build_direct_field_plan(),
        "payload_field_plan": build_payload_field_plan(),
        "anchor_link_candidate_plan": build_anchor_link_candidate_plan(link_candidates),
        "blocked_relationship_writes": build_blocked_relationship_writes(link_candidates),
        "limitations": list(LIMITATIONS),
    }
    assert_report_has_no_blocked_terms(report)
    return report


def build_direct_field_plan() -> dict[str, Any]:
    return {
        "anchors": {
            "code": "anchor_code_candidate_or_diagnostic_key",
            "anchor_type": "inferred_from_anchor_source_file_or_payload",
            "label": "display_label_only",
            "status": "resolver_status",
        },
        "anchor_links_candidates": {
            "anchor_code": "unresolved_anchor_code_candidate",
            "target_domain": "source_file_target_domain",
            "target_code": "source_row_code_candidate",
            "link_role": "reference_field_name",
            "resolver_status": "unresolved_or_manual_review_candidate",
            "blocked_action": BLOCKED_ACTION,
            "relationship_proven": False,
            "source_file": "canonical_jsonl_path",
            "line_no": "canonical_jsonl_line_number",
        },
    }


def build_payload_field_plan() -> dict[str, Any]:
    return {
        "anchors": [
            "source_file",
            "line_no",
            "identity_source_field",
            "diagnostic_key",
            "display_label_is_stable_id",
            "resolver_status",
            "raw_payload",
        ],
        "anchor_links_candidates": [
            "display_label",
            "diagnostic_key",
            "source_reference_field",
            "resolver_version",
            "formal_relationship_table",
        ],
    }


def build_anchor_link_candidate_plan(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "target_table": "anchor_links_candidates",
        "formal_relationship_table": False,
        "candidate_rows": len(candidates),
        "resolver_status_allowed": list(RESOLVER_STATUS_VALUES),
        "blocked_action": BLOCKED_ACTION,
        "relationship_proven": False,
        "writes_anchor_links": False,
        "rows_by_source_file": count_rows_by_source_file(candidates),
    }


def build_blocked_relationship_writes(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows_by_file: dict[str, set[int]] = {}
    for candidate in candidates:
        rows_by_file.setdefault(str(candidate["source_file"]), set()).add(int(candidate["line_no"]))
    return [
        {
            "source_file": source_file,
            "target_table": "anchor_links",
            "blocked_action": BLOCKED_ACTION,
            "allowed_action": "write_anchor_links_candidates_only",
            "line_numbers": sorted(line_numbers),
            "relationship_proven": False,
        }
        for source_file, line_numbers in sorted(rows_by_file.items())
    ]


def apply_target_mapper(
    dsn: str,
    *,
    schema: str = DEFAULT_SCHEMA,
    source_root: Path = ROOT,
    drop_schema_after: bool = False,
) -> dict[str, Any]:
    validate_isolated_schema(schema)
    rows = load_jsonl_rows(source_root=source_root, relative_files=SOURCE_FILES)
    anchor_candidates = build_anchor_candidates([row for row in rows if row.source_file in ANCHOR_SOURCE_FILES])
    reference_inputs = build_anchor_reference_inputs([row for row in rows if row.source_file in REFERENCE_SOURCE_FILES])
    link_candidates = build_anchor_link_candidates(reference_inputs)
    dropped = False
    db_report: dict[str, int] = {}
    try:
        create_target_prototype_tables(dsn, schema=schema)
        db_report = insert_target_rows(dsn, schema=schema, anchor_candidates=anchor_candidates, link_candidates=link_candidates)
    finally:
        if drop_schema_after:
            drop_schema(dsn, schema)
            dropped = True

    report = {
        "mode": "apply",
        "schema": schema,
        "import_rows": len(rows),
        "staging_rows": len(rows),
        "anchor_rows": db_report.get("anchor_rows", 0),
        "anchor_link_candidate_rows": db_report.get("anchor_link_candidate_rows", 0),
        "blocked_anchor_link_rows": db_report.get("blocked_anchor_link_rows", 0),
        "manual_review_rows": db_report.get("manual_review_rows", 0),
        "dropped": dropped,
        "schema_exists_after_drop": schema_exists(dsn, schema) if drop_schema_after else None,
    }
    assert_report_has_no_blocked_terms(report)
    return report


def create_target_prototype_tables(dsn: str, *, schema: str) -> None:
    import psycopg

    schema_ident = quote_identifier(schema)
    sql = f"""
    CREATE SCHEMA IF NOT EXISTS {schema_ident};
    SET search_path TO {schema_ident}, public;

    DROP TABLE IF EXISTS anchor_links_candidates CASCADE;
    DROP TABLE IF EXISTS anchors CASCADE;

    CREATE TABLE anchors (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        code TEXT NOT NULL,
        anchor_type TEXT,
        label TEXT,
        status TEXT NOT NULL CHECK (status IN ('unresolved_candidate', 'manual_review_required', 'blocked_pending_schema')),
        payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT anchors_target_mapper_code_uk UNIQUE (code)
    );

    CREATE TABLE anchor_links_candidates (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        anchor_code TEXT NOT NULL,
        target_domain TEXT NOT NULL,
        target_code TEXT,
        link_role TEXT NOT NULL,
        resolver_status TEXT NOT NULL CHECK (
            resolver_status IN ('unresolved_candidate', 'manual_review_required', 'blocked_pending_schema')
        ),
        blocked_action TEXT NOT NULL CHECK (blocked_action = 'anchor_links_write'),
        relationship_proven BOOLEAN NOT NULL CHECK (relationship_proven = false),
        source_file TEXT NOT NULL,
        line_no INTEGER NOT NULL,
        payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def insert_target_rows(
    dsn: str,
    *,
    schema: str,
    anchor_candidates: Sequence[Mapping[str, Any]],
    link_candidates: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    import psycopg
    from psycopg.types.json import Jsonb

    schema_ident = quote_identifier(schema)
    anchor_values = [
        (
            candidate["anchor_code_candidate"] or candidate["diagnostic_key"],
            candidate["anchor_type"],
            candidate["display_label"],
            candidate["resolver_status"],
            Jsonb(
                {
                    "source_file": candidate["source_file"],
                    "line_no": candidate["line_no"],
                    "identity_source_field": candidate["identity_source_field"],
                    "diagnostic_key": candidate["diagnostic_key"],
                    "display_label_is_stable_id": False,
                    "resolver_status": candidate["resolver_status"],
                    "payload_fields": candidate["payload_fields"],
                }
            ),
        )
        for candidate in anchor_candidates
    ]
    link_values = [
        (
            candidate["anchor_code"],
            candidate["target_domain"],
            candidate["target_code"],
            candidate["link_role"],
            candidate["resolver_status"],
            candidate["blocked_action"],
            candidate["relationship_proven"],
            candidate["source_file"],
            candidate["line_no"],
            Jsonb(
                {
                    "resolver_version": RESOLVER_VERSION,
                    "formal_relationship_table": False,
                    "source_reference_field": candidate["link_role"],
                }
            ),
        )
        for candidate in link_candidates
    ]
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema_ident}, public;")
            cur.executemany(
                """
                INSERT INTO anchors (code, anchor_type, label, status, payload)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (code) DO NOTHING
                """,
                anchor_values,
            )
            anchor_rows = cur.rowcount
            cur.executemany(
                """
                INSERT INTO anchor_links_candidates (
                    anchor_code, target_domain, target_code, link_role, resolver_status,
                    blocked_action, relationship_proven, source_file, line_no, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                link_values,
            )
            link_rows = cur.rowcount
            cur.execute(
                """
                SELECT COUNT(*) FILTER (WHERE resolver_status = 'manual_review_required')
                FROM anchor_links_candidates
                """
            )
            manual_review_rows = int(cur.fetchone()[0] or 0)
        conn.commit()
    return {
        "anchor_rows": int(anchor_rows),
        "anchor_link_candidate_rows": int(link_rows),
        "blocked_anchor_link_rows": int(link_rows),
        "manual_review_rows": manual_review_rows,
    }


def count_rows_by_source_file(rows: Sequence[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        source_file = row.source_file if hasattr(row, "source_file") else str(row["source_file"])
        counts[source_file] = counts.get(source_file, 0) + 1
    return counts


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Prototype anchors target mapping from canonical JSONL.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--contract-report", action="store_true", help="print the offline anchors target mapper contract")
    mode.add_argument("--apply", action="store_true", help="write anchors prototype target rows")
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
