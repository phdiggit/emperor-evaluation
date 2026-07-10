from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn
from scripts.dev.retrieval_v2_import_plan import json_param
from scripts.dev.retrieval_v2_intake_manifest import text
from scripts.dev.retrieval_v3_direct_binding_plan import validate_direct_assessment
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor
from scripts.dev.retrieval_v3_direct_binding_plan import read_jsonl


class DirectBindingConsumerError(ValueError):
    pass


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:20].upper()


def binding_code(row: Mapping[str, Any]) -> str:
    return "CRB-DIRECT-" + stable_hash([row["claim_id"], row["contract_rule_id"], row["predicate"], row["direction"], row["object_role"]])


def link_code(row: Mapping[str, Any]) -> str:
    return "MOL-DIRECT-" + stable_hash([row["claim_id"], row["object_id"], row["object_role"]])[:16]


def verify_identity_anchor(cur: Any, row: Mapping[str, Any]) -> None:
    cur.execute(
        """
        select 1
          from retrieval_v2.material_claims mc
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v2.target_objects tob on tob.id = %s and tob.target_id = sp.target_id
         where mc.id = %s and tob.object_id = %s and tob.review_status = 'accepted'
        """,
        (row["target_object_id"], row["claim_id"], row["object_id"]),
    )
    if not cur.fetchone():
        raise DirectBindingConsumerError(f"claim_id={row['claim_id']}: accepted target-object identity anchor is missing")


def apply_direct_assessments(cur: Any, rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for raw in rows:
        row = validate_direct_assessment(raw)
        verify_identity_anchor(cur, row)
        payload = {
            "source": "retrieval_v3_direct_binding_consumer",
            "assessment_lane": "normal_direct",
            "candidate_required": False,
            "binding_note": row["binding_note"],
            "usable_for_scoring_cluster": True,
        }
        cur.execute(
            """
            insert into retrieval_v2.claim_rule_bindings (
                claim_id, contract_rule_id, rule_code, predicate, direction, object_role,
                usable_for_object_payload, usable_for_scoring_cluster, confidence, review_status,
                binding_payload, binding_code, raw_binding_code
            ) values (%s, %s, %s, %s, %s, %s, false, true, %s, 'pending', %s::jsonb, %s, '')
            on conflict on constraint rv2_claim_rule_bindings_uk do update set
                usable_for_scoring_cluster = true,
                binding_payload = retrieval_v2.claim_rule_bindings.binding_payload || excluded.binding_payload,
                updated_at = now()
            returning id
            """,
            (row["claim_id"], row["contract_rule_id"], row["rule_code"], row["predicate"], row["direction"], row["object_role"], row.get("confidence"), json_param(payload), binding_code(row)),
        )
        binding_id = cur.fetchone()["id"]
        cur.execute(
            """
            insert into retrieval_v2.material_object_links (
                link_code, claim_id, object_id, target_object_id, role, confidence, review_status, link_payload
            ) values (%s, %s, %s, %s, %s, %s, 'accepted', %s::jsonb)
            on conflict on constraint rv2_material_object_links_uk do update set
                target_object_id = excluded.target_object_id, review_status = 'accepted',
                link_payload = retrieval_v2.material_object_links.link_payload || excluded.link_payload, updated_at = now()
            returning id
            """,
            (link_code(row), row["claim_id"], row["object_id"], row["target_object_id"], row["object_role"], row.get("confidence"), json_param(payload)),
        )
        link_id = cur.fetchone()["id"]
        cur.execute(
            """update retrieval_v2.claim_rule_bindings
                  set binding_payload = binding_payload || %s::jsonb, updated_at = now()
                where id = %s""",
            (json_param({"direct_material_object_link_id": link_id}), binding_id),
        )
        counts["claim_rule_bindings"] += 1
        counts["material_object_links"] += 1
    return dict(counts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply v3 direct formal bindings; dry-run unless --execute.")
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    rows = read_jsonl(args.input_jsonl)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(args.dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            counts = apply_direct_assessments(schema_cursor(raw_cur, schema_name=args.pg_schema), rows)
        (conn.commit() if args.execute else conn.rollback())
    payload = {"ok": True, "executed": args.execute, "write_db": args.execute, "schema": args.pg_schema, "counts": counts}
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
