from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn, schema_cursor
from scripts.dev.retrieval_v3_object_source_cache_seed import STAGED_NAME_SUFFIXES, normalized_name, stage_base_name


ACTIVE_STATUSES = {"active", "draft", "needs_review"}


def text(value: Any) -> str:
    return str(value or "").strip()


def identity_candidates(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    active = [dict(row) for row in rows if text(row.get("identity_status")) in ACTIVE_STATUSES]
    exact_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in active:
        key = normalized_name(row.get("canonical_name"))
        exact_groups[key].append(row)
        by_name[key].append(row)

    candidates: list[dict[str, Any]] = []
    seen_stage_ids: set[int] = set()
    for key, members in sorted(exact_groups.items()):
        if key and len(members) > 1:
            candidates.append(
                {
                    "candidate_type": "exact_name_duplicate",
                    "base_name": text(members[0].get("canonical_name")),
                    "status": "needs_review",
                    "canonical_candidates": [int(row["object_id"]) for row in members],
                    "merge_object_ids": [],
                    "rows": members,
                }
            )

    for row in active:
        name = text(row.get("canonical_name"))
        base = stage_base_name(name)
        if not base or normalized_name(base) == normalized_name(name):
            continue
        stage_id = int(row["object_id"])
        if stage_id in seen_stage_ids:
            continue
        seen_stage_ids.add(stage_id)
        canonical = [candidate for candidate in by_name.get(normalized_name(base), []) if int(candidate["object_id"]) != stage_id]
        if len(canonical) == 1:
            status = "auto_merge_ready"
        elif canonical:
            status = "ambiguous_canonical"
        else:
            status = "missing_canonical"
        candidates.append(
            {
                "candidate_type": "staged_identity_duplicate",
                "base_name": base,
                "stage_suffixes": [suffix for suffix in STAGED_NAME_SUFFIXES if name.endswith(suffix)],
                "status": status,
                "canonical_candidates": [int(candidate["object_id"]) for candidate in canonical],
                "merge_object_ids": [stage_id],
                "rows": [*canonical, row],
            }
        )

    counts: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        counts[text(candidate.get("status"))] += 1
    return {
        "schema": "retrieval_v3_person_identity_audit_v1",
        "active_person_count": len(active),
        "candidate_group_count": len(candidates),
        "counts_by_status": dict(sorted(counts.items())),
        "candidates": candidates,
        "write_db": False,
    }


def fetch_rows(*, dsn: str, schema_name: str) -> list[dict[str, Any]]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                select o.id as object_id, o.object_code, o.canonical_name, o.normalized_name,
                       o.identity_status::text, pp.id as person_profile_id,
                       pp.person_profile_code, pp.talent_grade::text, pp.negative_talent_class
                  from retrieval_v3.objects o
                  left join retrieval_v3.person_profiles pp on pp.object_id = o.id
                 where o.object_type = 'person'
                 order by o.canonical_name, o.id
                """
            )
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    return rows


def write_json(path: Path | None, payload: Mapping[str, Any]) -> None:
    raw = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(raw, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only audit for exact and staged retrieval_v3 person identities.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    parser.add_argument("--pg-schema", default="retrieval_v3")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    report = identity_candidates(fetch_rows(dsn=resolve_dsn(args.dsn_env), schema_name=args.pg_schema))
    write_json(args.output_json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
