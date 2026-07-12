from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import (
    import_psycopg,
    json_param,
    load_env_file,
    resolve_dsn,
    stable_fingerprint,
)
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV


class ScoringPolicyError(ValueError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def read_policy(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ScoringPolicyError(f"{path}: expected object")
    required = ("item_code", "rule_code", "policy_code", "policy_version", "side_aggregation")
    missing = [key for key in required if not value.get(key)]
    if missing:
        raise ScoringPolicyError(f"{path}: missing {', '.join(missing)}")
    aggregation = value["side_aggregation"]
    if not isinstance(aggregation, Mapping) or text(aggregation.get("mode")) != "hierarchical_rank_decay":
        raise ScoringPolicyError(f"{path}: invalid side_aggregation mode")
    if not aggregation.get("all_scored_materials_contribute"):
        raise ScoringPolicyError(f"{path}: all_scored_materials_contribute must be true")
    if aggregation.get("hard_aggregation_cap") or aggregation.get("top_k"):
        raise ScoringPolicyError(f"{path}: hard cap and top_k are forbidden")
    return dict(value)


def merged_policy_payload(current: Mapping[str, Any] | None, policy: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(current or {})
    payload["side_aggregation"] = dict(policy["side_aggregation"])
    payload["aggregation_trial_scope"] = list(policy.get("trial_scope") or [])
    payload["aggregation_policy_source"] = text(policy.get("policy_source"))
    return payload


def fetch_rows(dsn: str, *, schema_name: str, policy: Mapping[str, Any]) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select id, source_policy_id, policy_code, policy_version, policy_payload, policy_status,
                       source_row, source_fingerprint
                  from {schema_name}.eval_rule_material_policies
                 where item_code = %s and rule_code = %s
                 order by selection_priority, id
                """,
                (policy["item_code"], policy["rule_code"]),
            )
            runtime_rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    return {"runtime_rows": runtime_rows}


def build_plan(rows: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    runtime_rows = list(rows.get("runtime_rows") or [])
    if len(runtime_rows) != 1:
        raise ScoringPolicyError(f"expected one retrieval_v3 policy row, found {len(runtime_rows)}")
    runtime = runtime_rows[0]
    if text(runtime.get("policy_code")) != text(policy.get("policy_code")):
        raise ScoringPolicyError(
            f"policy_code mismatch: runtime={runtime.get('policy_code')} config={policy.get('policy_code')}"
        )
    desired_payload = merged_policy_payload(runtime.get("policy_payload") or {}, policy)
    desired_source_row = dict(runtime.get("source_row") or {})
    desired_source_row["policy_version"] = text(policy.get("policy_version"))
    desired_source_row["policy_payload"] = desired_payload
    unchanged = (
        text(runtime.get("policy_version")) == text(policy.get("policy_version"))
        and runtime.get("policy_payload") == desired_payload
        and runtime.get("source_row") == desired_source_row
    )
    return {
        "ok": True,
        "write_db": False,
        "item_code": policy["item_code"],
        "rule_code": policy["rule_code"],
        "policy_code": policy["policy_code"],
        "desired_policy_version": policy["policy_version"],
        "runtime_policy_id": runtime["id"],
        "current_runtime_version": runtime.get("policy_version"),
        "unchanged": unchanged,
        "desired_policy_payload": desired_payload,
        "desired_source_row": desired_source_row,
        "desired_source_fingerprint": stable_fingerprint(desired_source_row),
    }


def update_runtime_policy(
    dsn: str, *, schema_name: str, runtime_policy_id: int, policy_version: str,
    policy_payload: Mapping[str, Any], source_row: Mapping[str, Any], source_fingerprint: str,
) -> None:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                update {schema_name}.eval_rule_material_policies
                   set policy_version = %s,
                       policy_payload = %s::jsonb,
                       source_row = %s::jsonb,
                       source_fingerprint = %s,
                       copied_at = now()
                 where id = %s
                returning id
                """,
                (
                    policy_version, json_param(policy_payload), json_param(source_row),
                    source_fingerprint, runtime_policy_id,
                ),
            )
            if cur.fetchone() is None:
                raise ScoringPolicyError(f"retrieval_v3 policy row disappeared: {runtime_policy_id}")
        conn.commit()


def apply_policy(
    *, dsn: str, schema_name: str, policy: Mapping[str, Any],
) -> dict[str, Any]:
    before_rows = fetch_rows(dsn, schema_name=schema_name, policy=policy)
    plan = build_plan(before_rows, policy)
    if plan["unchanged"]:
        return {**plan, "write_db": True, "executed": True}
    update_runtime_policy(
        dsn,
        schema_name=schema_name,
        runtime_policy_id=int(plan["runtime_policy_id"]),
        policy_version=text(policy["policy_version"]),
        policy_payload=plan["desired_policy_payload"],
        source_row=plan["desired_source_row"],
        source_fingerprint=plan["desired_source_fingerprint"],
    )
    after = build_plan(fetch_rows(dsn, schema_name=schema_name, policy=policy), policy)
    if not after["unchanged"]:
        raise ScoringPolicyError("source policy updated but retrieval_v3 snapshot did not converge")
    return {**after, "write_db": True, "executed": True}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan or apply the retrieval_v3 appointment scoring aggregation policy.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    dsn = resolve_dsn(args.dsn_env)
    policy = read_policy(args.policy)
    if args.execute:
        report = apply_policy(
            dsn=dsn, schema_name=args.pg_schema, policy=policy)
    else:
        report = build_plan(fetch_rows(dsn, schema_name=args.pg_schema, policy=policy), policy)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({
        "ok": report["ok"], "write_db": report.get("write_db", False),
        "unchanged": report["unchanged"], "output_json": str(args.output_json),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
