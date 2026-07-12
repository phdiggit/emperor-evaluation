from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, seed_target  # noqa: E402
from scripts.dev.retrieval_v3_bootstrap import resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import write_json  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v3_object_source_cache_pg_backfill import load_cache_rows  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_V3_DSN_ENV, pg_schema_name, schema_cursor, table_label  # noqa: E402


CONTRACT_SQL = """
select
    id as contract_id,
    contract_code,
    item_code,
    status
from retrieval_v3.rule_contracts
where status = 'active'
  and item_code = %s
  and (%s = '' or contract_code = %s)
order by source_snapshot_at desc, id desc
limit 1
"""

CONTRACT_RULE_COUNT_SQL = """
select count(*) as count
from retrieval_v3.rule_contract_rules
where contract_id = %s
"""


class RetrievalTargetBackfillError(RuntimeError):
    pass


def list_texts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        name = text(item)
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def target_emperors_from_cache(cache_root: Path | None) -> list[str]:
    if cache_root is None:
        return []
    cache_rows = load_cache_rows(cache_root)
    names: set[str] = set()
    for seed in cache_rows.get("seeds") or []:
        names.update(list_texts(seed.get("target_emperors")))
    return sorted(names)


def target_emperor_names(*, cache_root: Path | None, emperor_names: Sequence[str]) -> list[str]:
    names = set(target_emperors_from_cache(cache_root))
    names.update(text(name) for name in emperor_names if text(name))
    return sorted(names)


def fetch_contract(cur: Any, *, item_code: str, contract_code: str = "") -> dict[str, Any]:
    cur.execute(CONTRACT_SQL, (item_code, contract_code, contract_code))
    row = cur.fetchone()
    if not row:
        raise RetrievalTargetBackfillError(
            f"active rule contract not found for item_code={item_code!r} contract_code={contract_code!r}"
        )
    return dict(row)


def fetch_contract_rule_count(cur: Any, *, contract_id: int) -> int:
    cur.execute(CONTRACT_RULE_COUNT_SQL, (contract_id,))
    row = cur.fetchone()
    return int(row["count"]) if row else 0


def build_target_plan(
    *,
    emperor_names: Sequence[str],
    contract: Mapping[str, Any],
    contract_rule_count: int,
    cache_root: Path | None,
    schema_name: str | None = None,
) -> dict[str, Any]:
    schema = pg_schema_name(schema_name)
    names = sorted({text(name) for name in emperor_names if text(name)})
    if not names:
        raise RetrievalTargetBackfillError("no emperor names to seed")
    targets = [
        {
            "emperor_name": name,
            "item_code": text(contract.get("item_code")),
            "contract_code": text(contract.get("contract_code")),
        }
        for name in names
    ]
    operation_counts = {
        table_label("retrieval_targets", schema_name=schema): len(targets),
        table_label("target_aliases", schema_name=schema): len(targets),
        table_label("target_rule_requirements", schema_name=schema): len(targets) * contract_rule_count,
        table_label("retrieval_intents", schema_name=schema): len(targets) * contract_rule_count,
    }
    return {
        "generated_by": f"scripts/dev/{Path(__file__).name}",
        "mode": "dry_run_retrieval_target_backfill",
        "schema_name": schema,
        "cache_root": str(cache_root) if cache_root else "",
        "write_db": False,
        "executed": False,
        "ok": True,
        "contract": {
            "contract_id": int(contract.get("contract_id")),
            "contract_code": text(contract.get("contract_code")),
            "item_code": text(contract.get("item_code")),
            "status": text(contract.get("status")),
            "rule_count": contract_rule_count,
        },
        "totals": {
            "emperor_rows": len(targets),
            "contract_rule_count": contract_rule_count,
            "target_rule_requirement_rows": len(targets) * contract_rule_count,
            "retrieval_intent_rows": len(targets) * contract_rule_count,
        },
        "operation_counts": operation_counts,
        "target_rows": targets,
        "seeded_targets": [],
        "executed_counts": {},
    }


def execute_target_backfill(
    *,
    cache_root: Path | None,
    emperor_names: Sequence[str],
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    item_code: str,
    contract_code: str,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    names = target_emperor_names(cache_root=cache_root, emperor_names=emperor_names)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            contract = fetch_contract(cur, item_code=item_code, contract_code=contract_code)
            rule_count = fetch_contract_rule_count(cur, contract_id=int(contract["contract_id"]))
            payload = build_target_plan(
                emperor_names=names,
                contract=contract,
                contract_rule_count=rule_count,
                cache_root=cache_root,
                schema_name=schema_name,
            )
            payload["mode"] = "execute" if execute else "dry_run_retrieval_target_backfill"
            payload["write_db"] = execute
            if not execute:
                conn.rollback()
                return payload
            seeded = [
                seed_target(
                    cur,
                    emperor_name=name,
                    item_code=item_code,
                    contract_id=int(contract["contract_id"]),
                    contract_code=text(contract["contract_code"]),
                )
                for name in names
            ]
            payload["seeded_targets"] = seeded
            payload["executed"] = True
            payload["executed_counts"] = {
                table_label("retrieval_targets", schema_name=schema_name): len(seeded),
                table_label("target_aliases", schema_name=schema_name): len(seeded),
                table_label("target_rule_requirements", schema_name=schema_name): sum(
                    int(row.get("requirements") or 0) for row in seeded
                ),
                table_label("retrieval_intents", schema_name=schema_name): sum(
                    int(row.get("retrieval_intents") or 0) for row in seeded
                ),
            }
        conn.commit()
    return payload


def markdown_report(payload: Mapping[str, Any]) -> str:
    totals = payload.get("totals") or {}
    contract = payload.get("contract") or {}
    lines = [
        "# retrieval_v3 retrieval target backfill report",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- schema_name: `{payload.get('schema_name')}`",
        f"- write_db: `{str(payload.get('write_db')).lower()}`",
        f"- executed: `{str(payload.get('executed')).lower()}`",
        f"- contract_code: `{contract.get('contract_code', '')}`",
        f"- item_code: `{contract.get('item_code', '')}`",
        f"- emperor_rows: `{totals.get('emperor_rows', 0)}`",
        f"- contract_rule_count: `{totals.get('contract_rule_count', 0)}`",
        "",
        "## Operation Counts",
        "",
        "| table | rows |",
        "| --- | ---: |",
    ]
    for table, count in (payload.get("operation_counts") or {}).items():
        lines.append(f"| {table} | {count} |")
    lines.extend(["", "## Targets", "", "| emperor |", "| --- |"])
    for row in (payload.get("target_rows") or [])[:200]:
        lines.append(f"| {row.get('emperor_name')} |")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill retrieval_v3 retrieval_targets from object source cache target emperors.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply = subparsers.add_parser("apply", help="Plan or apply retrieval target backfill; dry-run unless --execute.")
    apply.add_argument("--cache-root", type=Path)
    apply.add_argument("--emperor-name", action="append", default=[])
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path, required=True)
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    apply.add_argument("--pg-schema", default="retrieval_v3")
    apply.add_argument("--item-code", default="I5B")
    apply.add_argument("--contract-code", default="")
    apply.add_argument("--execute", action="store_true", help="Actually commit PG upserts. Omit for dry-run.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "apply":
        raise RetrievalTargetBackfillError(f"unsupported command: {args.command}")
    payload = execute_target_backfill(
        cache_root=args.cache_root,
        emperor_names=args.emperor_name or [],
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        item_code=args.item_code,
        contract_code=args.contract_code,
        execute=args.execute,
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": payload["ok"], "write_db": payload["write_db"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
