from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_claim_cache as fs_cache  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import (  # noqa: E402
    DEFAULT_PG_SCHEMA,
    DEFAULT_V3_DSN_ENV,
    schema_cursor,
    table_label,
)


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV

CLAIM_TYPES = {"material_action", "outcome", "evaluation", "relationship", "institution", "numeric", "context"}
FACT_SCHEMAS = {
    "political_action_v1",
    "outcome_v1",
    "evaluation_v1",
    "relationship_v1",
    "institution_v1",
    "numeric_fact_v1",
    "context_v1",
    "unknown",
}
OBJECT_TYPES = {"person", "person_group", "institution", "place", "event", "text", "other"}
DIRECTIONS = {"positive", "negative", "neutral", "mixed"}
CLAIM_STATUSES = {"active", "superseded", "needs_review", "rejected"}
SUPPORT_LEVELS = {"direct", "indirect", "context"}


class ClaimCachePgError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def text(value: Any) -> str:
    return str(value or "").strip()


def enum_value(value: Any, allowed: set[str], default: str) -> str:
    candidate = text(value)
    return candidate if candidate in allowed else default


def fact_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = row.get("fact_payload")
    return dict(payload) if isinstance(payload, Mapping) else {}


def fact_schema(row: Mapping[str, Any]) -> str:
    schema = text(row.get("fact_schema") or fact_payload(row).get("fact_schema"))
    return enum_value(schema, FACT_SCHEMAS, "unknown")


def claim_type(row: Mapping[str, Any]) -> str:
    explicit = text(row.get("claim_type"))
    if explicit in CLAIM_TYPES:
        return explicit
    schema = fact_schema(row)
    if schema == "political_action_v1":
        return "material_action"
    if schema.endswith("_v1"):
        stem = schema.removesuffix("_v1")
        if stem == "numeric_fact":
            return "numeric"
        if stem in CLAIM_TYPES:
            return stem
    return "material_action"


def confidence(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0 or parsed > 1:
        return None
    return parsed


def int_count(value: Any, *, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 1 else default


def load_cache(cache_root: Path) -> dict[str, list[dict[str, Any]]]:
    paths = fs_cache.cache_paths(cache_root)
    return {
        "claims": fs_cache.read_jsonl(paths["claims"]),
        "source_slices": fs_cache.read_jsonl(paths["slices"]),
        "claim_evidence": fs_cache.read_jsonl(paths["evidence"]),
        "import_runs": fs_cache.read_jsonl(paths["runs"]),
    }


def source_slice_row(row: Mapping[str, Any]) -> dict[str, Any]:
    preview = text(row.get("slice_text_preview"))
    return {
        "slice_hash": text(row.get("slice_hash")),
        "object_name": text(row.get("object_name")),
        "document_code": text(row.get("document_code")),
        "raw_document_code": text(row.get("raw_document_code")),
        "source_title": text(row.get("source_title")),
        "source_url": text(row.get("source_url")),
        "source_slice_ref": text(row.get("source_slice_ref")),
        "text_hash": text(row.get("text_hash")) or (fs_cache.sha256_text(preview) if preview else ""),
        "slice_text_preview": preview,
        "raw_text_path": text(row.get("raw_text_path")),
        "first_run_code": text(row.get("first_run_code")),
        "seen_count": int_count(row.get("seen_count")),
    }


def claim_row(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = fact_payload(row)
    return {
        "claim_key": text(row.get("claim_key")),
        "claim_type": claim_type(row),
        "fact_schema": fact_schema(row),
        "emperor_name": text(row.get("emperor_name")),
        "object_name": text(row.get("object_name") or payload.get("object")),
        "object_type": enum_value(row.get("object_type"), OBJECT_TYPES, "person"),
        "direction": enum_value(row.get("direction"), DIRECTIONS, "neutral"),
        "action_type": text(row.get("action_type") or payload.get("action_type")),
        "event_scope": text(row.get("event_scope") or payload.get("event_scope")),
        "office_or_domain": text(row.get("office_or_domain") or payload.get("office_or_domain")),
        "time_context": text(row.get("time_context") or payload.get("time_context")),
        "outcome": text(row.get("outcome") or payload.get("outcome")),
        "claim_summary": text(row.get("claim_summary") or row.get("summary")),
        "confidence": confidence(row.get("confidence")),
        "fact_payload": payload,
        "first_run_code": text(row.get("first_run_code")),
        "last_run_code": text(row.get("last_run_code")),
        "raw_output_path": text(row.get("raw_output_path")),
        "extractor_version": text(row.get("extractor_version")),
        "status": enum_value(row.get("status"), CLAIM_STATUSES, "active"),
        "seen_count": int_count(row.get("seen_count")),
    }


def evidence_row(row: Mapping[str, Any]) -> dict[str, Any]:
    span_payload = row.get("span_payload")
    span = dict(span_payload) if isinstance(span_payload, Mapping) else {}
    quote = text(row.get("quote_preview") or span.get("text"))
    return {
        "evidence_key": text(row.get("evidence_key")),
        "claim_key": text(row.get("claim_key")),
        "slice_hash": text(row.get("slice_hash")),
        "source_slice_ref": text(row.get("source_slice_ref")),
        "document_code": text(row.get("document_code")),
        "object_name": text(row.get("object_name")),
        "support_level": enum_value(row.get("support_level"), SUPPORT_LEVELS, "direct"),
        "span_payload": span,
        "quote_preview": fs_cache.compact_preview(quote),
        "slice_text_preview": text(row.get("slice_text_preview")),
        "raw_output_path": text(row.get("raw_output_path")),
        "first_run_code": text(row.get("first_run_code")),
    }


def prepared_cache_rows(cache_root: Path) -> dict[str, list[dict[str, Any]]]:
    cache = load_cache(cache_root)
    return {
        "claims": [claim_row(row) for row in cache["claims"]],
        "source_slices": [source_slice_row(row) for row in cache["source_slices"]],
        "claim_evidence": [evidence_row(row) for row in cache["claim_evidence"]],
        "import_runs": list(cache["import_runs"]),
    }


def validate_prepared_rows(rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    claim_keys = {row["claim_key"] for row in rows["claims"] if text(row.get("claim_key"))}
    slice_hashes = {row["slice_hash"] for row in rows["source_slices"] if text(row.get("slice_hash"))}
    for row in rows["claims"]:
        if not text(row.get("claim_key")):
            issues.append({"kind": "claim_missing_key", "row": row})
        if not text(row.get("object_name")):
            issues.append({"kind": "claim_missing_object_name", "claim_key": row.get("claim_key")})
        if not text(row.get("claim_summary")):
            issues.append({"kind": "claim_missing_summary", "claim_key": row.get("claim_key")})
    for row in rows["source_slices"]:
        if not text(row.get("slice_hash")):
            issues.append({"kind": "slice_missing_hash", "row": row})
    for row in rows["claim_evidence"]:
        if not text(row.get("evidence_key")):
            issues.append({"kind": "evidence_missing_key", "row": row})
        if text(row.get("claim_key")) not in claim_keys:
            issues.append({"kind": "evidence_missing_claim", "evidence_key": row.get("evidence_key"), "claim_key": row.get("claim_key")})
        if text(row.get("slice_hash")) not in slice_hashes:
            issues.append({"kind": "evidence_missing_slice", "evidence_key": row.get("evidence_key"), "slice_hash": row.get("slice_hash")})
    return issues


def row_counts(rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, int]:
    return {
        "claim_cache": len(rows["claims"]),
        "claim_source_slices": len(rows["source_slices"]),
        "claim_evidence": len(rows["claim_evidence"]),
        "import_runs": len(rows["import_runs"]),
    }


def object_inventory(rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    by_object: dict[str, dict[str, Any]] = {}
    for claim in rows["claims"]:
        name = text(claim.get("object_name"))
        entry = by_object.setdefault(
            name,
            {"claim_count": 0, "direction_counts": Counter(), "action_type_counts": Counter()},
        )
        entry["claim_count"] += 1
        entry["direction_counts"][text(claim.get("direction"))] += 1
        action = text(claim.get("action_type"))
        if action:
            entry["action_type_counts"][action] += 1
    return {
        name: {
            "claim_count": entry["claim_count"],
            "direction_counts": dict(sorted(entry["direction_counts"].items())),
            "action_type_counts": dict(sorted(entry["action_type_counts"].items())),
        }
        for name, entry in sorted(by_object.items())
    }


def existing_key_counts(cur: Any, rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, int]:
    specs = {
        "claim_cache": ("claim_key", [row["claim_key"] for row in rows["claims"]]),
        "claim_source_slices": ("slice_hash", [row["slice_hash"] for row in rows["source_slices"]]),
        "claim_evidence": ("evidence_key", [row["evidence_key"] for row in rows["claim_evidence"]]),
    }
    counts: dict[str, int] = {}
    for table, (column, keys) in specs.items():
        keys = [key for key in keys if key]
        if not keys:
            counts[table] = 0
            continue
        cur.execute(f"select count(*) as count from retrieval_v2.{table} where {column} = any(%s)", (keys,))
        counts[table] = int(cur.fetchone()["count"])
    return counts


def upsert_source_slice(cur: Any, row: Mapping[str, Any]) -> None:
    cur.execute(
        """
        insert into retrieval_v2.claim_source_slices (
            slice_hash, object_name, document_code, raw_document_code, source_title, source_url,
            source_slice_ref, text_hash, slice_text_preview, raw_text_path, first_run_code, seen_count
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (slice_hash) do update set
            object_name = excluded.object_name,
            document_code = excluded.document_code,
            raw_document_code = excluded.raw_document_code,
            source_title = excluded.source_title,
            source_url = excluded.source_url,
            source_slice_ref = excluded.source_slice_ref,
            text_hash = excluded.text_hash,
            slice_text_preview = excluded.slice_text_preview,
            raw_text_path = excluded.raw_text_path,
            first_run_code = coalesce(nullif(retrieval_v2.claim_source_slices.first_run_code, ''), excluded.first_run_code),
            seen_count = greatest(retrieval_v2.claim_source_slices.seen_count, excluded.seen_count),
            updated_at = now()
        """,
        (
            row["slice_hash"],
            row["object_name"],
            row["document_code"],
            row["raw_document_code"],
            row["source_title"],
            row["source_url"],
            row["source_slice_ref"],
            row["text_hash"],
            row["slice_text_preview"],
            row["raw_text_path"],
            row["first_run_code"],
            row["seen_count"],
        ),
    )


def upsert_claim(cur: Any, row: Mapping[str, Any]) -> None:
    cur.execute(
        """
        insert into retrieval_v2.claim_cache (
            claim_key, claim_type, fact_schema, emperor_name, object_name, object_type,
            direction, action_type, event_scope, office_or_domain, time_context, outcome,
            claim_summary, confidence, fact_payload, first_run_code, last_run_code,
            raw_output_path, extractor_version, status, seen_count
        )
        values (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s::jsonb, %s, %s,
            %s, %s, %s, %s
        )
        on conflict (claim_key) do update set
            claim_type = excluded.claim_type,
            fact_schema = excluded.fact_schema,
            emperor_name = excluded.emperor_name,
            object_name = excluded.object_name,
            object_type = excluded.object_type,
            direction = excluded.direction,
            action_type = excluded.action_type,
            event_scope = excluded.event_scope,
            office_or_domain = excluded.office_or_domain,
            time_context = excluded.time_context,
            outcome = excluded.outcome,
            claim_summary = excluded.claim_summary,
            confidence = excluded.confidence,
            fact_payload = excluded.fact_payload,
            first_run_code = coalesce(nullif(retrieval_v2.claim_cache.first_run_code, ''), excluded.first_run_code),
            last_run_code = excluded.last_run_code,
            raw_output_path = excluded.raw_output_path,
            extractor_version = excluded.extractor_version,
            status = case
                when retrieval_v2.claim_cache.status::text in ('rejected', 'superseded') then retrieval_v2.claim_cache.status
                else excluded.status
            end,
            seen_count = greatest(retrieval_v2.claim_cache.seen_count, excluded.seen_count),
            updated_at = now()
        """,
        (
            row["claim_key"],
            row["claim_type"],
            row["fact_schema"],
            row["emperor_name"],
            row["object_name"],
            row["object_type"],
            row["direction"],
            row["action_type"],
            row["event_scope"],
            row["office_or_domain"],
            row["time_context"],
            row["outcome"],
            row["claim_summary"],
            row["confidence"],
            stable_json(row["fact_payload"]),
            row["first_run_code"],
            row["last_run_code"],
            row["raw_output_path"],
            row["extractor_version"],
            row["status"],
            row["seen_count"],
        ),
    )


def upsert_evidence(cur: Any, row: Mapping[str, Any]) -> None:
    cur.execute(
        """
        insert into retrieval_v2.claim_evidence (
            evidence_key, claim_key, slice_hash, source_slice_ref, document_code,
            object_name, support_level, span_payload, quote_preview, slice_text_preview,
            raw_output_path, first_run_code
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
        on conflict (evidence_key) do update set
            claim_key = excluded.claim_key,
            slice_hash = excluded.slice_hash,
            source_slice_ref = excluded.source_slice_ref,
            document_code = excluded.document_code,
            object_name = excluded.object_name,
            support_level = excluded.support_level,
            span_payload = excluded.span_payload,
            quote_preview = excluded.quote_preview,
            slice_text_preview = excluded.slice_text_preview,
            raw_output_path = excluded.raw_output_path,
            first_run_code = coalesce(nullif(retrieval_v2.claim_evidence.first_run_code, ''), excluded.first_run_code)
        """,
        (
            row["evidence_key"],
            row["claim_key"],
            row["slice_hash"],
            row["source_slice_ref"],
            row["document_code"],
            row["object_name"],
            row["support_level"],
            stable_json(row["span_payload"]),
            row["quote_preview"],
            row["slice_text_preview"],
            row["raw_output_path"],
            row["first_run_code"],
        ),
    )


def execute_upserts(cur: Any, rows: Mapping[str, Sequence[Mapping[str, Any]]], *, schema_name: str = DEFAULT_PG_SCHEMA) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows["source_slices"]:
        upsert_source_slice(cur, row)
        counts[table_label("claim_source_slices", schema_name=schema_name)] += 1
    for row in rows["claims"]:
        upsert_claim(cur, row)
        counts[table_label("claim_cache", schema_name=schema_name)] += 1
    for row in rows["claim_evidence"]:
        upsert_evidence(cur, row)
        counts[table_label("claim_evidence", schema_name=schema_name)] += 1
    return dict(sorted(counts.items()))


def pg_table_counts(cur: Any, *, schema_name: str = DEFAULT_PG_SCHEMA) -> dict[str, int]:
    result: dict[str, int] = {}
    for table in ["claim_cache", "claim_source_slices", "claim_evidence", "claim_route_cache", "person_profile_claim_links"]:
        cur.execute(f"select count(*) as count from retrieval_v2.{table}")
        result[table_label(table, schema_name=schema_name)] = int(cur.fetchone()["count"])
    return result


def pg_inventory(cur: Any, *, sample_limit: int = 0, schema_name: str = DEFAULT_PG_SCHEMA) -> dict[str, Any]:
    cur.execute(
        """
        select object_name, direction::text as direction, action_type, count(*) as claim_count
          from retrieval_v2.claim_cache
         group by object_name, direction::text, action_type
         order by object_name, direction::text, action_type
        """
    )
    by_object: dict[str, dict[str, Any]] = {}
    for row in cur.fetchall():
        object_name = text(row["object_name"])
        entry = by_object.setdefault(object_name, {"claim_count": 0, "direction_counts": Counter(), "action_type_counts": Counter()})
        count = int(row["claim_count"])
        entry["claim_count"] += count
        entry["direction_counts"][text(row["direction"])] += count
        action = text(row["action_type"])
        if action:
            entry["action_type_counts"][action] += count
    cur.execute(
        """
        select object_name, count(*) as evidence_count
          from retrieval_v2.claim_evidence
         group by object_name
         order by object_name
        """
    )
    for row in cur.fetchall():
        by_object.setdefault(text(row["object_name"]), {"claim_count": 0, "direction_counts": Counter(), "action_type_counts": Counter()})[
            "evidence_count"
        ] = int(row["evidence_count"])
    cur.execute(
        """
        select object_name, count(*) as slice_count
          from retrieval_v2.claim_source_slices
         group by object_name
         order by object_name
        """
    )
    for row in cur.fetchall():
        by_object.setdefault(text(row["object_name"]), {"claim_count": 0, "direction_counts": Counter(), "action_type_counts": Counter()})[
            "slice_count"
        ] = int(row["slice_count"])
    samples: dict[str, list[dict[str, Any]]] = {}
    if sample_limit > 0:
        cur.execute(
            """
            select object_name, claim_key, direction::text as direction, action_type, claim_summary
              from retrieval_v2.claim_cache
             order by object_name, claim_key
            """
        )
        for row in cur.fetchall():
            bucket = samples.setdefault(text(row["object_name"]), [])
            if len(bucket) < sample_limit:
                bucket.append(
                    {
                        "claim_key": row["claim_key"],
                        "direction": row["direction"],
                        "action_type": row["action_type"],
                        "summary": row["claim_summary"],
                    }
                )
    return {
        "schema_name": schema_name,
        "totals": pg_table_counts(cur, schema_name=schema_name),
        "by_object": {
            object_name: {
                "claim_count": entry.get("claim_count", 0),
                "slice_count": entry.get("slice_count", 0),
                "evidence_count": entry.get("evidence_count", 0),
                "direction_counts": dict(sorted(entry["direction_counts"].items())),
                "action_type_counts": dict(sorted(entry["action_type_counts"].items())),
                "sample_claims": samples.get(object_name, []),
            }
            for object_name, entry in sorted(by_object.items())
        },
    }


def apply_cache_to_pg(
    *,
    cache_root: Path,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    rows = prepared_cache_rows(cache_root)
    issues = validate_prepared_rows(rows)
    report: dict[str, Any] = {
        "ok": not issues,
        "generated_by": "scripts/dev/retrieval_v2_claim_cache_pg.py",
        "mode": "execute" if execute else "dry_run_executor",
        "write_db": execute,
        "executed": False,
        "schema_name": schema_name,
        "cache_root": str(cache_root),
        "totals": row_counts(rows),
        "by_object": object_inventory(rows),
        "issues": issues,
        "existing_before": {},
        "planned": {},
        "executed_counts": {},
        "pg_totals_after": {},
    }
    if issues:
        return report
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            existing = existing_key_counts(cur, rows)
            report["existing_before"] = existing
            report["planned"] = {
                table: {
                    "input": count,
                    "existing": existing.get(table, 0),
                    "new": max(0, count - existing.get(table, 0)),
                    "upsert": count,
                }
                for table, count in {
                    "claim_cache": len(rows["claims"]),
                    "claim_source_slices": len(rows["source_slices"]),
                    "claim_evidence": len(rows["claim_evidence"]),
                }.items()
            }
            report["executed_counts"] = execute_upserts(cur, rows, schema_name=schema_name)
            report["pg_totals_after"] = pg_table_counts(cur, schema_name=schema_name)
        if execute:
            conn.commit()
            report["executed"] = True
        else:
            conn.rollback()
    return report


def inventory_from_pg(*, env_file: Path | None, dsn_env: str, sample_limit: int, schema_name: str) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            report = pg_inventory(cur, sample_limit=sample_limit, schema_name=schema_name)
    report["ok"] = True
    report["generated_by"] = "scripts/dev/retrieval_v2_claim_cache_pg.py"
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import and inspect retrieval_v2 filesystem claim cache in PostgreSQL.")
    sub = parser.add_subparsers(dest="command", required=True)

    apply = sub.add_parser("apply", help="DB-backed dry-run or execute filesystem claim cache upserts.")
    apply.add_argument("--cache-root", type=Path, required=True)
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    apply.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    apply.add_argument("--output-json", type=Path)
    apply.add_argument("--execute", action="store_true")

    inventory = sub.add_parser("inventory", help="Read PostgreSQL claim cache inventory.")
    inventory.add_argument("--env-file", type=Path)
    inventory.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    inventory.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    inventory.add_argument("--sample-limit", type=int, default=0)
    inventory.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "apply":
        report = apply_cache_to_pg(
            cache_root=args.cache_root,
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            schema_name=args.pg_schema,
            execute=bool(args.execute),
        )
    elif args.command == "inventory":
        report = inventory_from_pg(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            sample_limit=max(0, int(args.sample_limit)),
            schema_name=args.pg_schema,
        )
    else:  # pragma: no cover
        raise ClaimCachePgError(f"unsupported command: {args.command}")
    if args.output_json is not None:
        write_json(args.output_json, report)
    sys.stdout.write(pretty_json(report))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
