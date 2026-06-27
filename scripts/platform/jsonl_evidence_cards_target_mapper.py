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
DEFAULT_SCHEMA = "emperor_eval_evidence_cards_target_mapper"
TOOL_VERSION = "jsonl-evidence-cards-target-mapper-v1"
TARGET_SOURCE_FILES = ("data/evidence_cards.jsonl",)
TARGET_TABLES = ("evd_cards",)
DIRECT_FIELD_PLAN = {
    "evidence_id": {"target_column": "evd_cards.code", "source_bucket": "candidate_fields"},
    "polarity": {"target_column": "evd_cards.polarity candidate", "source_bucket": "direct_fields"},
    "summary": {"target_column": "evd_cards.summary candidate", "source_bucket": "if_present"},
    "claim": {"target_column": "evd_cards.claim candidate", "source_bucket": "if_present"},
    "confidence": {"target_column": "evd_cards.confidence candidate", "source_bucket": "if_present"},
}
PAYLOAD_FIELD_PLAN = {
    "verification_status": "evd_cards.payload",
    "adjudication_status": "evd_cards.payload",
    "notes": "evd_cards.payload",
    "note": "evd_cards.payload if present",
    "meta": "evd_cards.payload",
    "case_classification": "evd_cards.payload",
    "risk_status": "evd_cards.payload",
    "trigger_family": "evd_cards.payload",
    "trigger_terms": "evd_cards.payload",
    "mitigating_factors": "evd_cards.payload",
    "aggravating_factors": "evd_cards.payload",
    "reversal_or_rehabilitation": "evd_cards.payload",
    "mitigation_flag": "evd_cards.payload",
    "upper_bound_flag": "evd_cards.payload diagnostic_only",
}
SOURCE_LINK_FIELDS = ("source_id", "linked_source_ids")
CLUSTER_LINK_FIELDS = ("linked_cluster_ids", "cluster_candidate_id")
ANCHOR_LINK_FIELDS = ("object_anchor", "object_anchors", "thematic_anchor_targets")
MANUAL_REVIEW_FIELDS = ("cluster_role", "evidence_role")
LIMITATIONS = (
    "本 prototype 只覆盖 data/evidence_cards.jsonl。",
    "本 prototype 只写 opt-in 隔离 schema 内的 evd_cards relaxed target rows。",
    "person 只作为 resolver input，不直接写 person_id。",
    "item/subitem 只作为 range/filter 或 resolver input，不证明 evidence relationship。",
    "source_id 是 source document/code candidate，不是 passage_id。",
    "candidate passages 与 quote 不会自动证明 evidence-source relationship。",
    "本 prototype 不写 evd_src_links、cluster_evd、anchors 或 anchor_links。",
    "cluster_role/evidence_role 保持 manual_review。",
    "本报告不输出正式评分、排名或裁判结论。",
)


resolve_dsn = make_resolve_dsn()
check_environment = make_check_environment(resolve_dsn)
integration_skip_reason = make_integration_skip_reason(
    resolve_dsn,
    missing_reason=f"{PRIMARY_ENV_DSN} is not set",
)
validate_isolated_schema = make_validate_isolated_schema(
    quote_identifier,
    public_schema_message="refusing to write target mapper prototype into public schema",
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
    targetable_rows = [row for row in staging_rows if is_targetable_evidence_row(row)]

    report = {
        "mode": "contract-report",
        "tool_version": TOOL_VERSION,
        "mapping_version": MAPPING_VERSION,
        "resolver_version": RESOLVER_VERSION,
        "source_files": sorted(rows_by_source_file),
        "target_tables": list(TARGET_TABLES),
        "rows_by_source_file": rows_by_source_file,
        "candidate_rows_by_target": {"evd_cards": len(targetable_rows)},
        "direct_field_plan": build_direct_field_plan(line_index),
        "payload_field_plan": build_payload_field_plan(line_index),
        "resolver_blocked_fields": build_resolver_blocked_fields(line_index),
        "manual_review_fields_by_file": build_manual_review_fields_by_file(line_index),
        "source_link_plan": build_source_link_plan(line_index),
        "cluster_link_plan": build_cluster_link_plan(line_index),
        "anchor_link_plan": build_anchor_link_plan(line_index),
        "blocked_relationship_writes": build_blocked_relationship_writes(line_index),
        "unresolved_references_by_file": build_unresolved_references_by_file(line_index),
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
            fields.setdefault(field, []).append(row.line_no)
    return index


def count_source_rows(source_rows: Sequence[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in source_rows:
        if row.source_file in TARGET_SOURCE_FILES:
            counts[row.source_file] = counts.get(row.source_file, 0) + 1
    return counts


def build_direct_field_plan(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, dict[str, Any]]:
    fields = line_index.get("data/evidence_cards.jsonl", {})
    return {
        field: {
            **plan,
            "present": field in fields,
            "line_numbers": sorted(fields.get(field, [])),
        }
        for field, plan in DIRECT_FIELD_PLAN.items()
    }


def build_payload_field_plan(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, dict[str, Any]]:
    fields = line_index.get("data/evidence_cards.jsonl", {})
    return {
        field: {
            "target_column": target,
            "present": field in fields,
            "line_numbers": sorted(fields.get(field, [])),
        }
        for field, target in PAYLOAD_FIELD_PLAN.items()
    }


def build_resolver_blocked_fields(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, list[dict[str, Any]]]:
    fields = line_index.get("data/evidence_cards.jsonl", {})
    blocked: list[dict[str, Any]] = []
    for field in ("person", "item", "subitem", *SOURCE_LINK_FIELDS, *CLUSTER_LINK_FIELDS, *ANCHOR_LINK_FIELDS):
        if field not in fields:
            continue
        if field == "person":
            domain = "person"
            blocked_action = "direct_person_id_write"
            allowed_action = "resolver_input_only"
        elif field in {"item", "subitem"}:
            domain = "subitem"
            blocked_action = "subitem_fk_or_evidence_relationship_write"
            allowed_action = "range_filter_or_resolver_input_only"
        elif field in SOURCE_LINK_FIELDS:
            domain = "source_document_or_passage"
            blocked_action = "evd_src_links_write"
            allowed_action = "source_document_resolver_input_then_manual_passage_review"
        elif field in CLUSTER_LINK_FIELDS:
            domain = "evidence_cluster"
            blocked_action = "cluster_evd_write"
            allowed_action = "cluster_resolver_input_only"
        else:
            domain = "anchor"
            blocked_action = "anchors_or_anchor_links_write"
            allowed_action = "anchor_resolver_input_only"
        blocked.append(
            {
                "source_file": "data/evidence_cards.jsonl",
                "field": field,
                "resolver_domain": domain,
                "blocked_action": blocked_action,
                "allowed_action": allowed_action,
                "line_numbers": sorted(fields[field]),
            }
        )
    return {"data/evidence_cards.jsonl": blocked} if blocked else {}


def build_manual_review_fields_by_file(
    line_index: Mapping[str, Mapping[str, Sequence[int]]],
) -> dict[str, list[dict[str, Any]]]:
    fields = line_index.get("data/evidence_cards.jsonl", {})
    manual = [
        {
            "field": field,
            "line_numbers": sorted(fields[field]),
            "reason": "manual_review required before relationship or adjudication use",
        }
        for field in MANUAL_REVIEW_FIELDS
        if field in fields
    ]
    return {"data/evidence_cards.jsonl": manual} if manual else {}


def build_source_link_plan(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, Any]:
    fields = line_index.get("data/evidence_cards.jsonl", {})
    source_rows = sorted(set(fields.get("source_id", [])) | set(fields.get("linked_source_ids", [])))
    quote_rows = sorted(set(fields.get("quote", [])) | set(fields.get("quote_short", [])))
    return {
        "source_fields": [
            {"field": field, "line_numbers": sorted(fields.get(field, []))}
            for field in SOURCE_LINK_FIELDS
            if field in fields
        ],
        "quote_candidate_rows": quote_rows,
        "source_id_is_passage_id": False,
        "candidate_passage_status": "unreviewed_candidate",
        "allowed_action": "source_document_resolver_input_only",
        "blocked_action": "evd_src_links_write",
        "blocked_rows": source_rows,
    }


def build_cluster_link_plan(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, Any]:
    fields = line_index.get("data/evidence_cards.jsonl", {})
    blocked_rows = sorted(set(fields.get("linked_cluster_ids", [])) | set(fields.get("cluster_candidate_id", [])))
    return {
        "cluster_fields": [
            {"field": field, "line_numbers": sorted(fields.get(field, []))}
            for field in CLUSTER_LINK_FIELDS
            if field in fields
        ],
        "allowed_action": "cluster_resolver_input_only",
        "blocked_action": "cluster_evd_write",
        "blocked_rows": blocked_rows,
    }


def build_anchor_link_plan(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, Any]:
    fields = line_index.get("data/evidence_cards.jsonl", {})
    blocked_rows = sorted(
        set(fields.get("object_anchor", []))
        | set(fields.get("object_anchors", []))
        | set(fields.get("thematic_anchor_targets", []))
    )
    return {
        "anchor_fields": [
            {"field": field, "line_numbers": sorted(fields.get(field, []))}
            for field in ANCHOR_LINK_FIELDS
            if field in fields
        ],
        "allowed_action": "anchor_resolver_input_only",
        "blocked_action": "anchors_or_anchor_links_write",
        "blocked_rows": blocked_rows,
    }


def build_blocked_relationship_writes(line_index: Mapping[str, Mapping[str, Sequence[int]]]) -> list[dict[str, Any]]:
    fields = line_index.get("data/evidence_cards.jsonl", {})
    all_rows = sorted({line for lines in fields.values() for line in lines})
    source_rows = sorted(set(fields.get("source_id", [])) | set(fields.get("linked_source_ids", [])))
    cluster_rows = sorted(set(fields.get("linked_cluster_ids", [])) | set(fields.get("cluster_candidate_id", [])))
    anchor_rows = sorted(
        set(fields.get("object_anchor", []))
        | set(fields.get("object_anchors", []))
        | set(fields.get("thematic_anchor_targets", []))
    )
    manual_rows = sorted(set(fields.get("cluster_role", [])) | set(fields.get("evidence_role", [])))
    blocked = [
        {
            "source_file": "data/evidence_cards.jsonl",
            "target_table": "evd_src_links",
            "blocked_action": "write_evidence_source_relationship",
            "allowed_action": "report_only_until_reviewed_passage_span_exists",
            "line_numbers": source_rows,
        },
        {
            "source_file": "data/evidence_cards.jsonl",
            "target_table": "cluster_evd",
            "blocked_action": "write_evidence_cluster_relationship",
            "allowed_action": "report_only_until_cluster_resolver_exists",
            "line_numbers": cluster_rows,
        },
        {
            "source_file": "data/evidence_cards.jsonl",
            "target_table": "anchors_or_anchor_links",
            "blocked_action": "write_anchor_relationship",
            "allowed_action": "report_only_until_anchor_schema_exists",
            "line_numbers": anchor_rows,
        },
        {
            "source_file": "data/evidence_cards.jsonl",
            "target_table": "adjudications_or_release_tables",
            "blocked_action": "write_downstream_business_conclusion",
            "allowed_action": "evd_cards_payload_only",
            "line_numbers": all_rows,
        },
        {
            "source_file": "data/evidence_cards.jsonl",
            "target_table": "manual_review_relationships",
            "blocked_action": "auto_resolve_cluster_role_or_evidence_role",
            "allowed_action": "manual_review_only",
            "line_numbers": manual_rows,
        },
    ]
    return [item for item in blocked if item["line_numbers"]]


def build_unresolved_references_by_file(
    line_index: Mapping[str, Mapping[str, Sequence[int]]],
) -> dict[str, list[dict[str, Any]]]:
    fields = line_index.get("data/evidence_cards.jsonl", {})
    unresolved: list[dict[str, Any]] = []
    for field in ("person", "item", "subitem", *SOURCE_LINK_FIELDS, *CLUSTER_LINK_FIELDS, *ANCHOR_LINK_FIELDS):
        if field not in fields:
            continue
        unresolved.append(
            {
                "field": field,
                "line_numbers": sorted(fields[field]),
                "kept_as": "resolver_or_manual_review_input",
                "blocked_action": "direct_fk_or_relationship_write",
            }
        )
    return {"data/evidence_cards.jsonl": unresolved} if unresolved else {}


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
        "evd_card_rows": db_report.get("evd_card_rows", 0),
        "blocked_source_link_rows": db_report.get("blocked_source_link_rows", 0),
        "blocked_cluster_link_rows": db_report.get("blocked_cluster_link_rows", 0),
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
    DROP TABLE IF EXISTS evd_cards CASCADE;

    CREATE TABLE evd_cards (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        code TEXT NOT NULL,
        summary TEXT,
        claim TEXT,
        polarity TEXT,
        confidence TEXT,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT evd_cards_target_mapper_code_uk UNIQUE (code)
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
                INSERT INTO evd_cards (code, summary, claim, polarity, confidence, payload)
                SELECT
                    jsonl_code,
                    payload_fields ->> 'summary',
                    payload_fields ->> 'claim',
                    direct_fields -> 'polarity' ->> 'value',
                    payload_fields ->> 'confidence',
                    jsonb_strip_nulls(jsonb_build_object(
                        'source_file', source_file,
                        'line_no', line_no,
                        'verification_status', payload_fields -> 'verification_status',
                        'adjudication_status', payload_fields -> 'adjudication_status',
                        'notes', payload_fields -> 'notes',
                        'note', payload_fields -> 'note',
                        'meta', payload_fields -> 'meta',
                        'case_classification', payload_fields -> 'case_classification',
                        'risk_status', payload_fields -> 'risk_status',
                        'trigger_family', payload_fields -> 'trigger_family',
                        'trigger_terms', payload_fields -> 'trigger_terms',
                        'mitigating_factors', payload_fields -> 'mitigating_factors',
                        'aggravating_factors', payload_fields -> 'aggravating_factors',
                        'reversal_or_rehabilitation', payload_fields -> 'reversal_or_rehabilitation',
                        'mitigation_flag', payload_fields -> 'mitigation_flag',
                        'upper_bound_flag', payload_fields -> 'upper_bound_flag',
                        'source_link_boundary', 'source_id_document_code_not_passage_id',
                        'cluster_link_boundary', 'cluster_fields_report_only',
                        'anchor_link_boundary', 'anchor_fields_report_only'
                    ))
                FROM stg_jsonl_rows
                WHERE source_file = 'data/evidence_cards.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                ON CONFLICT (code) DO NOTHING
                """
            )
            evd_card_rows = cur.rowcount
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE reference_risk_fields ? 'source_id'
                           OR reference_risk_fields ? 'linked_source_ids'
                    ),
                    COUNT(*) FILTER (
                        WHERE reference_risk_fields ? 'linked_cluster_ids'
                           OR reference_risk_fields ? 'cluster_candidate_id'
                    ),
                    COUNT(*) FILTER (
                        WHERE unknown_fields ? 'cluster_role'
                           OR unknown_fields ? 'evidence_role'
                    )
                FROM stg_jsonl_rows
                WHERE source_file = 'data/evidence_cards.jsonl'
                  AND jsonl_code IS NOT NULL
                  AND NOT staging_only
                  AND validation_errors = '[]'::jsonb
                """
            )
            row = cur.fetchone()
        conn.commit()
    return {
        "evd_card_rows": int(evd_card_rows),
        "blocked_source_link_rows": int(row[0] or 0),
        "blocked_cluster_link_rows": int(row[1] or 0),
        "manual_review_rows": int(row[2] or 0),
    }


def is_targetable_evidence_row(row: StagingRow) -> bool:
    return (
        row.source_file in TARGET_SOURCE_FILES
        and bool(row.jsonl_code)
        and not row.staging_only
        and not row.validation_errors
    )


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Prototype evidence_cards target mapping from stg_jsonl_rows.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check DSN and psycopg availability without connecting")
    mode.add_argument("--contract-report", action="store_true", help="print the offline evidence_cards target mapper contract")
    mode.add_argument("--apply", action="store_true", help="write evidence_cards prototype target rows")
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
