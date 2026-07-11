from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn, schema_cursor


def text(value: Any) -> str:
    return str(value or "").strip()


def binding_plan(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_claim[text(row.get("claim_key"))].append(dict(row))
    updates, unresolved = [], []
    for claim_key, matches in sorted(by_claim.items()):
        object_ids = sorted({int(row["object_id"]) for row in matches if row.get("object_id") is not None})
        item = {
            "claim_key": claim_key,
            "object_name": text(matches[0].get("object_name")),
            "matched_object_ids": object_ids,
        }
        if len(object_ids) == 1:
            updates.append({**item, "object_id": object_ids[0]})
        else:
            unresolved.append({**item, "status": "unmatched" if not object_ids else "ambiguous"})
    return {
        "schema": "retrieval_v3_claim_object_binding_backfill_v1",
        "candidate_claim_count": len(by_claim),
        "ready_count": len(updates),
        "unresolved_count": len(unresolved),
        "unresolved_by_status": dict(Counter(row["status"] for row in unresolved)),
        "updates": updates,
        "unresolved": unresolved,
    }


def fetch_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute(
        """
        select cc.claim_key,cc.object_name,o.id object_id,o.canonical_name
          from retrieval_v3.claim_cache cc
          left join retrieval_v3.objects o
            on o.object_type='person' and o.identity_status in ('active','draft','needs_review')
           and (
                lower(o.canonical_name)=lower(cc.object_name)
                or exists (
                    select 1 from retrieval_v3.object_names onm
                     where onm.object_id=o.id and onm.review_status='accepted'
                       and (lower(onm.name_text)=lower(cc.object_name) or lower(onm.normalized_name)=lower(cc.object_name))
                )
           )
         where cc.status='active' and cc.object_id is null and btrim(cc.object_name)<>''
         order by cc.claim_key,o.id
        """
    )
    return [dict(row) for row in cur.fetchall()]


def apply_updates(cur: Any, rows: Sequence[Mapping[str, Any]]) -> int:
    changed = 0
    for row in rows:
        cur.execute(
            "update retrieval_v3.claim_cache set object_id=%s,updated_at=now() where claim_key=%s and object_id is null",
            (int(row["object_id"]), text(row["claim_key"])),
        )
        changed += cur.rowcount
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bind active claim-cache rows to one canonical person; ambiguous names fail closed.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    parser.add_argument("--pg-schema", default="retrieval_v3")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(args.dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw:
            cur = schema_cursor(raw, schema_name=args.pg_schema)
            report = binding_plan(fetch_rows(cur))
            report["updated_count"] = apply_updates(cur, report["updates"]) if args.execute else 0
            report["write_db"] = bool(args.execute)
        conn.commit() if args.execute else conn.rollback()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("candidate_claim_count", "ready_count", "unresolved_count", "updated_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
