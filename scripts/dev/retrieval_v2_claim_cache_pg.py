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
from scripts.dev import retrieval_v2_claim_quality as claim_quality  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import (  # noqa: E402
    DEFAULT_PG_SCHEMA,
    DEFAULT_V3_DSN_ENV,
    schema_cursor,
    table_label,
)


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_ALLOWED_EXTRACTOR_VERSIONS = ("claim_extraction_only:v4_structured_ref_policy",)

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


def json_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def json_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


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
    quality = claim_quality.claim_quality_payload(row)
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
        "canonical_event_key": text(row.get("canonical_event_key") or quality["canonical_event_key"]),
        "canonical_event_payload": json_mapping(row.get("canonical_event_payload")) or quality["canonical_event_payload"],
        "near_duplicate_group_payload": json_mapping(row.get("near_duplicate_group_payload")) or quality["near_duplicate_group_payload"],
        "claim_grain": text(row.get("claim_grain") or quality["claim_grain"]),
        "quality_flags": json_list(row.get("quality_flags")),
        "fact_type": text(row.get("fact_type") or quality["fact_type"]),
        "outcome_support": enum_value(row.get("outcome_support") or quality["outcome_support"], {"direct", "implicit", "missing", "not_applicable", "mixed"}, "missing"),
        "atomic_fact_payload": json_mapping(row.get("atomic_fact_payload")) or quality["atomic_fact_payload"],
        "event_group_key": text(row.get("event_group_key") or quality["event_group_key"]),
        "event_group_payload": json_mapping(row.get("event_group_payload")) or quality["event_group_payload"],
        "claim_usage_flags": json_list(row.get("claim_usage_flags")),
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


def extractor_version_counts(rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows["claims"]:
        counts[text(row.get("extractor_version")) or "<blank>"] += 1
    return dict(sorted(counts.items()))


def validate_extractor_version_policy(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    allowed_extractor_versions: Sequence[str],
    allow_legacy_extractor_version: bool = False,
) -> list[dict[str, Any]]:
    if allow_legacy_extractor_version:
        return []
    allowed = {text(version) for version in allowed_extractor_versions if text(version)}
    observed = extractor_version_counts(rows)
    blocked = {version: count for version, count in observed.items() if version not in allowed}
    if not blocked:
        return []
    return [
        {
            "kind": "unsupported_extractor_version",
            "allowed_extractor_versions": sorted(allowed),
            "observed_extractor_versions": observed,
            "blocked_extractor_versions": dict(sorted(blocked.items())),
            "hint": "Pass --allowed-extractor-version for a reviewed current version, or --allow-legacy-extractor-version for an explicit legacy import.",
        }
    ]


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
            {"claim_count": 0, "direction_hint_counts": Counter(), "action_type_counts": Counter()},
        )
        entry["claim_count"] += 1
        entry["direction_hint_counts"][text(claim.get("direction"))] += 1
        action = text(claim.get("action_type"))
        if action:
            entry["action_type_counts"][action] += 1
    return {
        name: {
            "claim_count": entry["claim_count"],
            "direction_hint_counts": dict(sorted(entry["direction_hint_counts"].items())),
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
            claim_summary, confidence, fact_payload, canonical_event_key, canonical_event_payload,
            near_duplicate_group_payload, claim_grain, quality_flags, fact_type, outcome_support,
            atomic_fact_payload, event_group_key, event_group_payload, claim_usage_flags,
            first_run_code, last_run_code,
            raw_output_path, extractor_version, status, seen_count
        )
        values (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s::jsonb, %s, %s::jsonb,
            %s::jsonb, %s, %s::jsonb, %s, %s,
            %s::jsonb, %s, %s::jsonb, %s::jsonb,
            %s, %s,
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
            canonical_event_key = excluded.canonical_event_key,
            canonical_event_payload = excluded.canonical_event_payload,
            near_duplicate_group_payload = excluded.near_duplicate_group_payload,
            claim_grain = excluded.claim_grain,
            quality_flags = excluded.quality_flags,
            fact_type = excluded.fact_type,
            outcome_support = excluded.outcome_support,
            atomic_fact_payload = excluded.atomic_fact_payload,
            event_group_key = excluded.event_group_key,
            event_group_payload = excluded.event_group_payload,
            claim_usage_flags = excluded.claim_usage_flags,
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
            row["canonical_event_key"],
            stable_json(row["canonical_event_payload"]),
            stable_json(row["near_duplicate_group_payload"]),
            row["claim_grain"],
            stable_json(row["quality_flags"]),
            row["fact_type"],
            row["outcome_support"],
            stable_json(row["atomic_fact_payload"]),
            row["event_group_key"],
            stable_json(row["event_group_payload"]),
            stable_json(row["claim_usage_flags"]),
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


def pg_owner_scope_inventory(cur: Any) -> dict[str, Any]:
    cur.execute(
        """
        select owner_scope, count(*) as claim_count
          from retrieval_v2.claim_owner_scopes
         group by owner_scope
         order by owner_scope
        """
    )
    by_scope = {text(row["owner_scope"]): int(row["claim_count"]) for row in cur.fetchall()}
    cur.execute(
        """
        select owner_name, owner_scope, count(*) as claim_count
          from retrieval_v2.claim_owner_scopes
         where owner_scope <> 'target_emperor'
         group by owner_name, owner_scope
         order by claim_count desc, owner_name
        """
    )
    non_target_owners = [
        {
            "owner_name": text(row["owner_name"]),
            "owner_scope": text(row["owner_scope"]),
            "claim_count": int(row["claim_count"]),
        }
        for row in cur.fetchall()
    ]
    return {
        "claim_count_by_owner_scope": dict(sorted(by_scope.items())),
        "non_target_owners": non_target_owners,
    }


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
        entry = by_object.setdefault(object_name, {"claim_count": 0, "direction_hint_counts": Counter(), "action_type_counts": Counter()})
        count = int(row["claim_count"])
        entry["claim_count"] += count
        entry["direction_hint_counts"][text(row["direction"])] += count
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
        by_object.setdefault(text(row["object_name"]), {"claim_count": 0, "direction_hint_counts": Counter(), "action_type_counts": Counter()})[
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
        by_object.setdefault(text(row["object_name"]), {"claim_count": 0, "direction_hint_counts": Counter(), "action_type_counts": Counter()})[
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
                        "direction_hint": row["direction"],
                        "action_type": row["action_type"],
                        "summary": row["claim_summary"],
                    }
                )
    return {
        "schema_name": schema_name,
        "totals": pg_table_counts(cur, schema_name=schema_name),
        "owner_scope_inventory": pg_owner_scope_inventory(cur),
        "by_object": {
            object_name: {
                "claim_count": entry.get("claim_count", 0),
                "slice_count": entry.get("slice_count", 0),
                "evidence_count": entry.get("evidence_count", 0),
                "direction_hint_counts": dict(sorted(entry["direction_hint_counts"].items())),
                "action_type_counts": dict(sorted(entry["action_type_counts"].items())),
                "sample_claims": samples.get(object_name, []),
            }
            for object_name, entry in sorted(by_object.items())
        },
    }


def pg_claim_rows_for_quality_backfill(cur: Any, *, only_missing: bool = True) -> list[dict[str, Any]]:
    where = "where canonical_event_key = '' or claim_grain = '' or canonical_event_payload = '{}'::jsonb or near_duplicate_group_payload = '{}'::jsonb"
    cur.execute(
        f"""
        select
            claim_key,
            emperor_name,
            object_name,
            object_type::text as object_type,
            direction::text as direction,
            action_type,
            event_scope,
            office_or_domain,
            time_context,
            outcome,
            claim_summary,
            fact_payload,
            canonical_event_key,
            claim_grain
          from retrieval_v2.claim_cache
          {where if only_missing else ''}
         order by claim_key
        """
    )
    return [dict(row) for row in cur.fetchall()]


def list_arg(values: Sequence[str] | None) -> list[str]:
    return [text(value) for value in values or [] if text(value)]


def cleanup_where_clause(
    *,
    last_run_codes: Sequence[str] | None = None,
    extractor_versions: Sequence[str] | None = None,
    emperor_names: Sequence[str] | None = None,
) -> tuple[str, list[list[str]]]:
    clauses: list[str] = []
    params: list[list[str]] = []
    run_codes = list_arg(last_run_codes)
    versions = list_arg(extractor_versions)
    emperors = list_arg(emperor_names)
    if run_codes:
        clauses.append("last_run_code = any(%s)")
        params.append(run_codes)
    if versions:
        clauses.append("extractor_version = any(%s)")
        params.append(versions)
    if emperors:
        clauses.append("emperor_name = any(%s)")
        params.append(emperors)
    if not clauses:
        raise ClaimCachePgError("cleanup-runs requires at least one selector: --last-run-code, --extractor-version, or --emperor-name")
    return "where " + " and ".join(clauses), params


def cleanup_claim_runs(
    *,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    execute: bool,
    last_run_codes: Sequence[str] | None = None,
    extractor_versions: Sequence[str] | None = None,
    emperor_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    where_sql, params = cleanup_where_clause(
        last_run_codes=last_run_codes,
        extractor_versions=extractor_versions,
        emperor_names=emperor_names,
    )
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                f"""
                select emperor_name, extractor_version, last_run_code, count(*) as claim_count
                  from retrieval_v2.claim_cache
                 {where_sql}
                 group by emperor_name, extractor_version, last_run_code
                 order by emperor_name, extractor_version, last_run_code
                """,
                params,
            )
            groups = [dict(row) for row in cur.fetchall()]
            cur.execute(
                f"""
                select count(*) as evidence_count
                  from retrieval_v2.claim_evidence e
                  join retrieval_v2.claim_cache c on c.claim_key = e.claim_key
                 {where_sql.replace('last_run_code', 'c.last_run_code').replace('extractor_version', 'c.extractor_version').replace('emperor_name', 'c.emperor_name')}
                """,
                params,
            )
            evidence_count = int(cur.fetchone()["evidence_count"])
            deleted: list[dict[str, Any]] = []
            if execute:
                cur.execute(
                    f"""
                    delete from retrieval_v2.claim_cache
                     {where_sql}
                     returning emperor_name, extractor_version, last_run_code, claim_key
                    """,
                    params,
                )
                deleted = [dict(row) for row in cur.fetchall()]
            report: dict[str, Any] = {
                "ok": True,
                "generated_by": "scripts/dev/retrieval_v2_claim_cache_pg.py",
                "mode": "execute" if execute else "dry_run_cleanup_runs",
                "write_db": execute,
                "executed": bool(execute),
                "schema_name": schema_name,
                "selectors": {
                    "last_run_codes": list_arg(last_run_codes),
                    "extractor_versions": list_arg(extractor_versions),
                    "emperor_names": list_arg(emperor_names),
                },
                "planned": {
                    "claim_cache": sum(int(row["claim_count"]) for row in groups),
                    "claim_evidence_cascade": evidence_count,
                },
                "groups": groups,
                "executed_counts": {table_label("claim_cache", schema_name=schema_name): len(deleted)} if execute else {},
            }
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return report


def cleanup_orphan_source_slices(
    *,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                select s.object_name, count(*) as slice_count
                  from retrieval_v2.claim_source_slices s
                 where not exists (
                       select 1
                         from retrieval_v2.claim_evidence e
                        where e.slice_hash = s.slice_hash
                 )
                 group by s.object_name
                 order by s.object_name
                """
            )
            groups = [dict(row) for row in cur.fetchall()]
            total = sum(int(row["slice_count"]) for row in groups)
            deleted: list[dict[str, Any]] = []
            if execute:
                cur.execute(
                    """
                    delete from retrieval_v2.claim_source_slices s
                     where not exists (
                           select 1
                             from retrieval_v2.claim_evidence e
                            where e.slice_hash = s.slice_hash
                     )
                     returning s.object_name, s.slice_hash
                    """
                )
                deleted = [dict(row) for row in cur.fetchall()]
            report: dict[str, Any] = {
                "ok": True,
                "generated_by": "scripts/dev/retrieval_v2_claim_cache_pg.py",
                "mode": "execute" if execute else "dry_run_cleanup_orphan_source_slices",
                "write_db": execute,
                "executed": bool(execute),
                "schema_name": schema_name,
                "planned": {"claim_source_slices": total},
                "groups": groups,
                "executed_counts": {table_label("claim_source_slices", schema_name=schema_name): len(deleted)} if execute else {},
            }
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return report


def update_claim_quality_fields(cur: Any, row: Mapping[str, Any]) -> None:
    quality = claim_quality.claim_quality_payload(row)
    cur.execute(
        """
        update retrieval_v2.claim_cache
           set canonical_event_key = %s,
               canonical_event_payload = %s::jsonb,
               near_duplicate_group_payload = %s::jsonb,
               claim_grain = %s,
               fact_type = %s,
               outcome_support = %s,
               atomic_fact_payload = %s::jsonb,
               event_group_key = %s,
               event_group_payload = %s::jsonb,
               updated_at = now()
         where claim_key = %s
        """,
        (
            quality["canonical_event_key"],
            stable_json(quality["canonical_event_payload"]),
            stable_json(quality["near_duplicate_group_payload"]),
            quality["claim_grain"],
            quality["fact_type"],
            quality["outcome_support"],
            stable_json(quality["atomic_fact_payload"]),
            quality["event_group_key"],
            stable_json(quality["event_group_payload"]),
            text(row.get("claim_key")),
        ),
    )


def backfill_quality_fields(
    *,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    execute: bool,
    all_rows: bool = False,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            rows = pg_claim_rows_for_quality_backfill(cur, only_missing=not all_rows)
            report: dict[str, Any] = {
                "ok": True,
                "generated_by": "scripts/dev/retrieval_v2_claim_cache_pg.py",
                "mode": "execute" if execute else "dry_run_quality_backfill",
                "write_db": execute,
                "executed": False,
                "schema_name": schema_name,
                "all_rows": all_rows,
                "totals": {
                    "candidate_claims": len(rows),
                    "pg_claim_cache": pg_table_counts(cur, schema_name=schema_name)[table_label("claim_cache", schema_name=schema_name)],
                },
                "executed_counts": {},
            }
            if execute:
                for row in rows:
                    update_claim_quality_fields(cur, row)
                report["executed"] = True
                report["executed_counts"] = {table_label("claim_cache", schema_name=schema_name): len(rows)}
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return report


def apply_cache_to_pg(
    *,
    cache_root: Path,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    execute: bool,
    allowed_extractor_versions: Sequence[str] = DEFAULT_ALLOWED_EXTRACTOR_VERSIONS,
    allow_legacy_extractor_version: bool = False,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    rows = prepared_cache_rows(cache_root)
    issues = validate_prepared_rows(rows)
    issues.extend(
        validate_extractor_version_policy(
            rows,
            allowed_extractor_versions=allowed_extractor_versions,
            allow_legacy_extractor_version=allow_legacy_extractor_version,
        )
    )
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
        "extractor_version_policy": {
            "allow_legacy_extractor_version": allow_legacy_extractor_version,
            "allowed_extractor_versions": list(allowed_extractor_versions),
            "observed_extractor_versions": extractor_version_counts(rows),
        },
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
    apply.add_argument(
        "--allowed-extractor-version",
        action="append",
        dest="allowed_extractor_versions",
        help="Extractor version accepted by default import policy; repeatable.",
    )
    apply.add_argument(
        "--allow-legacy-extractor-version",
        action="store_true",
        help="Explicitly allow importing cache rows from legacy or mixed extractor versions.",
    )

    inventory = sub.add_parser("inventory", help="Read PostgreSQL claim cache inventory.")
    inventory.add_argument("--env-file", type=Path)
    inventory.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    inventory.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    inventory.add_argument("--sample-limit", type=int, default=0)
    inventory.add_argument("--output-json", type=Path)

    backfill = sub.add_parser("backfill-quality", help="Backfill canonical event and claim-grain hot fields from PG claim rows.")
    backfill.add_argument("--env-file", type=Path)
    backfill.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    backfill.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    backfill.add_argument("--output-json", type=Path)
    backfill.add_argument("--execute", action="store_true")
    backfill.add_argument("--all-rows", action="store_true", help="Recompute all claim rows instead of only missing hot fields.")

    cleanup = sub.add_parser("cleanup-runs", help="Dry-run or delete imported claim rows selected by run/version/emperor.")
    cleanup.add_argument("--env-file", type=Path)
    cleanup.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    cleanup.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    cleanup.add_argument("--output-json", type=Path)
    cleanup.add_argument("--execute", action="store_true")
    cleanup.add_argument("--last-run-code", action="append", dest="last_run_codes")
    cleanup.add_argument("--extractor-version", action="append", dest="extractor_versions")
    cleanup.add_argument("--emperor-name", action="append", dest="emperor_names")

    orphan_slices = sub.add_parser("cleanup-orphan-source-slices", help="Dry-run or delete source slices no longer referenced by claim evidence.")
    orphan_slices.add_argument("--env-file", type=Path)
    orphan_slices.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    orphan_slices.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    orphan_slices.add_argument("--output-json", type=Path)
    orphan_slices.add_argument("--execute", action="store_true")
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
            allowed_extractor_versions=args.allowed_extractor_versions or DEFAULT_ALLOWED_EXTRACTOR_VERSIONS,
            allow_legacy_extractor_version=bool(args.allow_legacy_extractor_version),
        )
    elif args.command == "inventory":
        report = inventory_from_pg(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            sample_limit=max(0, int(args.sample_limit)),
            schema_name=args.pg_schema,
        )
    elif args.command == "backfill-quality":
        report = backfill_quality_fields(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            schema_name=args.pg_schema,
            execute=bool(args.execute),
            all_rows=bool(args.all_rows),
        )
    elif args.command == "cleanup-runs":
        report = cleanup_claim_runs(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            schema_name=args.pg_schema,
            execute=bool(args.execute),
            last_run_codes=args.last_run_codes,
            extractor_versions=args.extractor_versions,
            emperor_names=args.emperor_names,
        )
    elif args.command == "cleanup-orphan-source-slices":
        report = cleanup_orphan_source_slices(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            schema_name=args.pg_schema,
            execute=bool(args.execute),
        )
    else:  # pragma: no cover
        raise ClaimCachePgError(f"unsupported command: {args.command}")
    if args.output_json is not None:
        write_json(args.output_json, report)
    sys.stdout.write(pretty_json(report))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
