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
from scripts.dev.retrieval_v2_cross_rule_router import upsert_candidate  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import reason_hash  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


RULE_CODE = "appointment_delegation"
ITEM_CODE = "I5B"


class MaterialCandidateConsumerError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def load_plan(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MaterialCandidateConsumerError("candidate plan must be a JSON object")
    if payload.get("rule_code") != RULE_CODE:
        raise MaterialCandidateConsumerError(f"unsupported rule_code: {payload.get('rule_code')!r}")
    return payload


def resolve_rows(cur: Any, candidates: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    claim_codes = sorted({text(row.get("source_material_claim_code")) for row in candidates if text(row.get("source_material_claim_code"))})
    if not claim_codes:
        return [], []
    cur.execute(
        """
        select mc.claim_code, mc.id as claim_id, sp.id as source_pack_id,
               sp.pack_code as source_pack_code, sp.target_id, t.target_code,
               t.contract_id, rr.id as candidate_contract_rule_id
          from retrieval_v3.material_claims mc
          join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v3.retrieval_targets t on t.id = sp.target_id
          left join retrieval_v3.rule_contract_rules rr
            on rr.contract_id = t.contract_id and rr.rule_code = %s
         where mc.claim_code = any(%s)
        """,
        (RULE_CODE, claim_codes),
    )
    lookup = {text(row["claim_code"]): dict(row) for row in cur.fetchall()}
    resolved: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for candidate in candidates:
        claim_code = text(candidate.get("source_material_claim_code"))
        db_row = lookup.get(claim_code)
        if db_row is None:
            missing.append({"source_material_claim_code": claim_code, "reason": "material_claim_not_found"})
            continue
        resolved.append(
            {
                **dict(candidate),
                "claim_id": int(db_row["claim_id"]),
                "source_pack_id": int(db_row["source_pack_id"]),
                "source_pack_code": text(db_row["source_pack_code"]),
                "target_id": int(db_row["target_id"]),
                "target_code": text(db_row["target_code"]),
                "source_contract_rule_id": None,
                "candidate_contract_rule_id": db_row.get("candidate_contract_rule_id"),
                "source_item_code": ITEM_CODE,
                "source_rule_code": "claim_cache_material",
                "candidate_predicate": "",
                "candidate_object_role": "",
                "candidate_direction": None,
                "reason_hash": reason_hash(text(candidate.get("candidate_reason"))),
                "confidence": None,
                "review_status": "pending",
                "required_facts_present": {
                    "source_material_claim": True,
                    "matched_signal": bool(candidate.get("matched_signals")),
                    "matched_term": bool(candidate.get("matched_terms")),
                    "source_binding": False,
                },
                "routed_by_profile": "retrieval_v3_material_candidate_plan",
            }
        )
    return resolved, missing


def run_consumer(
    *,
    plan_path: Path,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    execute: bool,
) -> dict[str, Any]:
    plan = load_plan(plan_path)
    candidates = plan.get("candidates") or []
    if not isinstance(candidates, list):
        raise MaterialCandidateConsumerError("candidate plan candidates must be a list")
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            resolved, missing = resolve_rows(cur, candidates)
            executed_count = 0
            if execute:
                for row in resolved:
                    upsert_candidate(cur, row)
                    executed_count += 1
                conn.commit()
            else:
                conn.rollback()
    return {
        "ok": not missing,
        "generated_by": "scripts/dev/retrieval_v3_material_candidate_consumer.py",
        "rule_code": RULE_CODE,
        "write_db": execute,
        "executed": execute,
        "input_candidates": len(candidates),
        "resolved_candidates": len(resolved),
        "missing_candidates": len(missing),
        "missing": missing[:100],
        "executed_count": executed_count,
        "legacy_data_reads": False,
        "legacy_data_migrated": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve and optionally write candidates from a neutral material candidate plan.")
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output-json", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_consumer(
        plan_path=args.plan_json,
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        execute=args.execute,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("ok", "write_db", "input_candidates", "resolved_candidates", "missing_candidates", "executed_count")}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
