from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


PROFILE = "retrieval_v3_material_candidate_plan"
RULE_CODE = "appointment_delegation"
NATIVE_CONTRACT_CODE = "I5B-CLAIM-CACHE-V3-NATIVE-20260710"


def code(prefix: str, *parts: Any) -> str:
    value = "|".join(str(part) for part in parts)
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()[:20].upper()


def build_plan(*, dsn: str, schema_name: str) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw:
            cur = schema_cursor(raw, schema_name=schema_name)
            cur.execute("select id from retrieval_v3.rule_contracts where contract_code = %s", (NATIVE_CONTRACT_CODE,))
            contract = cur.fetchone()
            if not contract:
                raise ValueError(f"native contract missing: {NATIVE_CONTRACT_CODE}")
            contract_id = int(contract["id"])
            cur.execute("select id from retrieval_v3.rule_contract_rules where contract_id = %s and rule_code = %s", (contract_id, RULE_CODE))
            rule = cur.fetchone()
            if not rule:
                raise ValueError(f"native contract rule missing: {RULE_CODE}")
            cur.execute(
                """
                select c.id as candidate_id, c.candidate_code, c.claim_id,
                       mc.claim_code, mc.emperor_name, mc.object_name,
                       sp.id as source_pack_id, sp.pack_code as source_pack_code,
                       rt.id as source_target_id, rt.target_code as source_target_code,
                       nt.id as native_target_id, nt.target_code as native_target_code
                  from retrieval_v3.claim_rule_binding_candidates c
                  join retrieval_v3.material_claims mc on mc.id = c.claim_id
                  join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
                  join retrieval_v3.retrieval_targets rt on rt.id = sp.target_id
                  left join retrieval_v3.retrieval_targets nt
                    on nt.contract_id = %s and nt.emperor_name = mc.emperor_name
                 where c.routed_by_profile = %s
                   and c.candidate_rule_code = %s
                   and c.review_status::text = 'accepted'
                   and c.candidate_payload #>> '{candidate_review,identity_gate}' = 'identity_ready'
                 order by c.id
                """,
                (contract_id, PROFILE, RULE_CODE),
            )
            rows = [dict(row) for row in cur.fetchall()]
    target_ops = {}
    mappings = []
    for row in rows:
        emperor = str(row["emperor_name"])
        target_ops.setdefault(emperor, {
            "emperor_name": emperor,
            "source_target_id": row["source_target_id"],
            "source_target_code": row["source_target_code"],
            "native_target_id": row.get("native_target_id"),
            "native_target_code": row.get("native_target_code") or code("TGT-I5B-R3R-", NATIVE_CONTRACT_CODE, emperor),
        })
        mappings.append({
            "source_candidate_id": row["candidate_id"],
            "source_candidate_code": row["candidate_code"],
            "source_claim_id": row["claim_id"],
            "source_claim_code": row["claim_code"],
            "source_pack_id": row["source_pack_id"],
            "source_pack_code": row["source_pack_code"],
            "emperor_name": emperor,
            "object_name": row["object_name"],
            "native_candidate_code": code("CRBC-R3R-", row["candidate_code"], contract_id),
            "native_claim_code": code("CLM-R3R-", row["claim_code"], contract_id),
            "native_contract_rule_id": int(rule["id"]),
        })
    return {
        "ok": True, "generated_by": "scripts/dev/retrieval_v3_contract_reanchor_plan.py",
        "native_contract_code": NATIVE_CONTRACT_CODE, "native_contract_id": contract_id,
        "native_contract_rule_id": int(rule["id"]), "candidate_count": len(mappings),
        "target_operations": list(target_ops.values()), "source_pack_count": len({row["source_pack_id"] for row in rows}),
        "candidate_counts_by_emperor": dict(sorted(Counter(row["emperor_name"] for row in rows).items())),
        "mappings": mappings, "legacy_data_reads": False, "legacy_data_migrated": False, "write_db": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only v3 contract re-anchor plan for identity-ready candidates.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    payload = build_plan(dsn=resolve_dsn(args.dsn_env), schema_name=args.pg_schema)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("ok", "candidate_count", "source_pack_count", "write_db")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
