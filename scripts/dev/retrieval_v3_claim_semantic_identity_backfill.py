from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn, schema_cursor
from scripts.dev import retrieval_v3_claim_quality as quality


def text(value: Any) -> str:
    return str(value or "").strip()


def semantic_updates(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in rows:
        row = dict(source)
        payload = quality.claim_quality_payload(row)
        update = {
            "claim_key": text(row.get("claim_key")),
            "object_id": row.get("object_id"),
            "emperor_name": text(row.get("emperor_name")),
            "object_name": text(row.get("object_name")),
            **payload,
            "quality_flags": list(row.get("quality_flags") or []),
            "claim_usage_flags": list(row.get("claim_usage_flags") or []),
        }
        updates.append(update)
        groups[update["canonical_event_key"]].append({**row, **update})
    duplicate_groups = []
    for key, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        outcomes = sorted({text(row.get("outcome")) for row in members if text(row.get("outcome"))})
        duplicate_groups.append(
            {
                "canonical_event_key": key,
                "claim_count": len(members),
                "duplicate_excess": len(members) - 1,
                "emperor_name": text(members[0].get("emperor_name")),
                "object_name": text(members[0].get("object_name")),
                "claim_keys": [text(row.get("claim_key")) for row in members],
                "distinct_outcomes": outcomes,
                "outcome_conflict_review": len(outcomes) > 1,
            }
        )
    by_object = Counter(row["object_name"] for row in updates if row["object_name"])
    return updates, {
        "schema": "retrieval_v3_claim_semantic_identity_backfill_v1",
        "claim_count": len(updates),
        "semantic_event_count": len(groups),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_excess": sum(row["duplicate_excess"] for row in duplicate_groups),
        "outcome_conflict_review_count": sum(bool(row["outcome_conflict_review"]) for row in duplicate_groups),
        "objects_with_claims": len(by_object),
        "duplicate_groups": duplicate_groups,
    }


def fetch_claims(cur: Any) -> list[dict[str, Any]]:
    cur.execute("select * from retrieval_v3.claim_cache where status='active' order by claim_key")
    return [dict(row) for row in cur.fetchall()]


def apply_updates(cur: Any, updates: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in updates:
        cur.execute(
            """
            update retrieval_v3.claim_cache
               set canonical_event_key=%s, canonical_event_payload=%s::jsonb,
                   near_duplicate_group_payload=%s::jsonb, claim_grain=%s,
                   quality_flags=%s::jsonb, fact_type=%s, outcome_support=%s,
                   atomic_fact_payload=%s::jsonb, event_group_key=%s,
                   event_group_payload=%s::jsonb, claim_usage_flags=%s::jsonb,
                   updated_at=now()
             where claim_key=%s
            """,
            (
                row["canonical_event_key"], json.dumps(row["canonical_event_payload"], ensure_ascii=False, sort_keys=True),
                json.dumps(row["near_duplicate_group_payload"], ensure_ascii=False, sort_keys=True), row["claim_grain"],
                json.dumps(row["quality_flags"], ensure_ascii=False, sort_keys=True), row["fact_type"], row["outcome_support"],
                json.dumps(row["atomic_fact_payload"], ensure_ascii=False, sort_keys=True), row["event_group_key"],
                json.dumps(row["event_group_payload"], ensure_ascii=False, sort_keys=True),
                json.dumps(row["claim_usage_flags"], ensure_ascii=False, sort_keys=True), row["claim_key"],
            ),
        )
        count += cur.rowcount
    return count


def write_json(path: Path | None, payload: Mapping[str, Any]) -> None:
    raw = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(raw, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit or backfill semantic claim identities across the active v3 claim cache.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    parser.add_argument("--pg-schema", default="retrieval_v3")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(args.dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=args.pg_schema)
            updates, report = semantic_updates(fetch_claims(cur))
            report["write_db"] = bool(args.execute)
            report["updated_claim_count"] = apply_updates(cur, updates) if args.execute else 0
        conn.commit() if args.execute else conn.rollback()
    write_json(args.output_json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
