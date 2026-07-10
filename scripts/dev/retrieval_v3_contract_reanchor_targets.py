from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import json_param  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


def run(*, plan: Mapping[str, Any], dsn: str, schema_name: str, execute: bool) -> dict[str, Any]:
    contract_id = int(plan["native_contract_id"])
    targets = list(plan.get("target_operations") or [])
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw:
            cur = schema_cursor(raw, schema_name=schema_name)
            created = []
            for target in targets:
                payload = {"source": "retrieval_v3_contract_reanchor", "reanchored_from_target_id": target["source_target_id"], "reanchored_from_target_code": target["source_target_code"]}
                if execute:
                    cur.execute("""
                        insert into retrieval_v3.retrieval_targets (target_code, emperor_name, item_code, contract_id, target_payload)
                        values (%s, %s, 'I5B', %s, %s::jsonb)
                        on conflict (contract_id, emperor_name) do update set
                          target_payload = retrieval_v3.retrieval_targets.target_payload || excluded.target_payload,
                          updated_at = now()
                        returning id, target_code
                    """, (target["native_target_code"], target["emperor_name"], contract_id, json_param(payload)))
                    row = dict(cur.fetchone())
                    created.append({"emperor_name": target["emperor_name"], "target_id": row["id"], "target_code": row["target_code"]})
                else:
                    created.append({"emperor_name": target["emperor_name"], "target_code": target["native_target_code"]})
        (conn.commit() if execute else conn.rollback())
    return {"ok": True, "write_db": execute, "executed": execute, "native_targets": created, "target_count": len(created), "requirements_written": 0, "intents_written": 0, "legacy_data_reads": False, "legacy_data_migrated": False}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create only the native v3 targets required by a contract re-anchor plan.")
    parser.add_argument("--plan-json", type=Path, required=True); parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV); parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--execute", action="store_true"); parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.env_file: load_env_file(args.env_file)
    plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
    payload = run(plan=plan, dsn=resolve_dsn(args.dsn_env), schema_name=args.pg_schema, execute=args.execute)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__": raise SystemExit(main())
