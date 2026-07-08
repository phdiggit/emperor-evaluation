from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, normalize_alias, resolve_dsn, seed_target  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import write_json  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_V3_DSN_ENV, pg_schema_name, schema_cursor, table_label  # noqa: E402
from scripts.dev.retrieval_v2_retrieval_target_backfill import fetch_contract, fetch_contract_rule_count  # noqa: E402


DEFAULT_EMPEROR_LIST = ROOT / "data" / "configs" / "lists" / "所有君主.yml"
DEFAULT_ALIAS_FILE = ROOT / "data" / "configs" / "lists" / "君主别名.yml"


class TargetAliasBackfillError(RuntimeError):
    pass


def read_yaml(path: Path) -> Any:
    if not path.exists():
        raise TargetAliasBackfillError(f"missing YAML file: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def unique_texts(values: Sequence[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = text(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def load_emperor_names(path: Path) -> list[str]:
    payload = read_yaml(path)
    if not isinstance(payload, list):
        raise TargetAliasBackfillError(f"{path}: expected a list of emperor names")
    return unique_texts(payload)


def load_alias_seed(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = read_yaml(path)
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise TargetAliasBackfillError(f"{path}: expected object keyed by canonical emperor name")
    result: dict[str, list[dict[str, Any]]] = {}
    for emperor_name, rows in payload.items():
        name = text(emperor_name)
        if not isinstance(rows, list):
            raise TargetAliasBackfillError(f"{path}: aliases for {name} must be a list")
        parsed: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            if isinstance(row, str):
                parsed.append({"alias": row, "alias_type": "alias", "scopes": []})
                continue
            if not isinstance(row, Mapping):
                raise TargetAliasBackfillError(f"{path}: aliases for {name}[{index}] must be object or string")
            alias = text(row.get("alias"))
            if not alias:
                raise TargetAliasBackfillError(f"{path}: aliases for {name}[{index}] missing alias")
            scopes = row.get("scopes") or []
            if isinstance(scopes, str):
                scopes = [scopes]
            if not isinstance(scopes, list):
                raise TargetAliasBackfillError(f"{path}: aliases for {name}[{index}].scopes must be list")
            parsed.append(
                {
                    "alias": alias,
                    "alias_type": text(row.get("alias_type")) or "alias",
                    "source": text(row.get("source")) or "manual_seed",
                    "scopes": unique_texts(scopes),
                }
            )
        result[name] = parsed
    return result


def alias_rows_for_emperors(emperor_names: Sequence[str], alias_seed: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    known = set(emperor_names)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for name in emperor_names:
        base = {"emperor_name": name, "alias": name, "alias_type": "name", "source": "canonical_list", "scopes": []}
        key = (name, base["alias_type"], normalize_alias(name))
        seen.add(key)
        rows.append(base)
    for owner, aliases in sorted(alias_seed.items()):
        if owner not in known:
            raise TargetAliasBackfillError(f"alias seed references unknown emperor name: {owner}")
        for row in aliases:
            alias = text(row.get("alias"))
            alias_type = text(row.get("alias_type")) or "alias"
            key = (owner, alias_type, normalize_alias(alias))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "emperor_name": owner,
                    "alias": alias,
                    "alias_type": alias_type,
                    "source": text(row.get("source")) or "manual_seed",
                    "scopes": [scope for scope in unique_texts(row.get("scopes") or []) if scope in known],
                }
            )
    return rows


def alias_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = {"seed_source": "data/configs/lists/君主别名.yml"}
    scopes = [text(scope) for scope in row.get("scopes") or [] if text(scope)]
    if scopes:
        payload["scopes"] = scopes
    return payload


def build_plan(*, emperor_names: Sequence[str], alias_rows: Sequence[Mapping[str, Any]], schema_name: str) -> dict[str, Any]:
    counts_by_type = Counter(text(row.get("alias_type")) for row in alias_rows)
    return {
        "generated_by": "scripts/dev/retrieval_v2_target_alias_backfill.py",
        "mode": "dry_run_target_alias_backfill",
        "schema_name": pg_schema_name(schema_name),
        "write_db": False,
        "executed": False,
        "ok": True,
        "totals": {
            "emperor_count": len(emperor_names),
            "alias_count": len(alias_rows),
            "name_alias_count": counts_by_type.get("name", 0),
            "extra_alias_count": len(alias_rows) - counts_by_type.get("name", 0),
        },
        "alias_type_counts": dict(sorted(counts_by_type.items())),
        "target_rows": [{"emperor_name": name} for name in emperor_names],
        "alias_rows": list(alias_rows),
        "executed_counts": {},
    }


def upsert_target_alias(cur: Any, *, target_id: int, row: Mapping[str, Any]) -> None:
    cur.execute(
        """
        insert into retrieval_v2.target_aliases (
            target_id, alias, alias_type, norm_alias, source, alias_payload, status
        )
        values (%s, %s, %s, %s, %s, %s::jsonb, 'active')
        on conflict (target_id, alias_type, norm_alias) do update set
            alias = excluded.alias,
            source = excluded.source,
            alias_payload = retrieval_v2.target_aliases.alias_payload || excluded.alias_payload,
            status = 'active'
        """,
        (
            target_id,
            text(row.get("alias")),
            text(row.get("alias_type")) or "alias",
            normalize_alias(text(row.get("alias"))),
            text(row.get("source")) or "manual_seed",
            json.dumps(alias_payload(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        ),
    )


def execute_alias_backfill(
    *,
    emperor_list: Path,
    alias_file: Path,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    item_code: str,
    contract_code: str,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    emperor_names = load_emperor_names(emperor_list)
    alias_seed = load_alias_seed(alias_file)
    alias_rows = alias_rows_for_emperors(emperor_names, alias_seed)
    payload = build_plan(emperor_names=emperor_names, alias_rows=alias_rows, schema_name=schema_name)
    payload["mode"] = "execute" if execute else "dry_run_target_alias_backfill"
    payload["write_db"] = execute
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            contract = fetch_contract(cur, item_code=item_code, contract_code=contract_code)
            rule_count = fetch_contract_rule_count(cur, contract_id=int(contract["contract_id"]))
            payload["contract"] = {
                "contract_id": int(contract["contract_id"]),
                "contract_code": text(contract["contract_code"]),
                "item_code": text(contract["item_code"]),
                "rule_count": rule_count,
            }
            if execute:
                target_ids: dict[str, int] = {}
                target_rows = []
                for name in emperor_names:
                    seeded = seed_target(
                        cur,
                        emperor_name=name,
                        item_code=item_code,
                        contract_id=int(contract["contract_id"]),
                        contract_code=text(contract["contract_code"]),
                    )
                    cur.execute(
                        "select id from retrieval_v2.retrieval_targets where target_code = %s",
                        (text(seeded["target_code"]),),
                    )
                    target_ids[name] = int(cur.fetchone()["id"])
                    target_rows.append(seeded)
                for row in alias_rows:
                    upsert_target_alias(cur, target_id=target_ids[text(row.get("emperor_name"))], row=row)
                payload["executed"] = True
                payload["executed_counts"] = {
                    table_label("retrieval_targets", schema_name=schema_name): len(target_rows),
                    table_label("target_aliases", schema_name=schema_name): len(alias_rows),
                    table_label("target_rule_requirements", schema_name=schema_name): sum(
                        int(row.get("requirements") or 0) for row in target_rows
                    ),
                    table_label("retrieval_intents", schema_name=schema_name): sum(
                        int(row.get("retrieval_intents") or 0) for row in target_rows
                    ),
                }
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return payload


def markdown_report(payload: Mapping[str, Any]) -> str:
    totals = payload.get("totals") or {}
    lines = [
        "# retrieval_v2 target alias backfill report",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- schema_name: `{payload.get('schema_name')}`",
        f"- write_db: `{str(payload.get('write_db')).lower()}`",
        f"- executed: `{str(payload.get('executed')).lower()}`",
        f"- emperor_count: `{totals.get('emperor_count', 0)}`",
        f"- alias_count: `{totals.get('alias_count', 0)}`",
        f"- extra_alias_count: `{totals.get('extra_alias_count', 0)}`",
        "",
        "## Alias Types",
        "",
        "| alias_type | count |",
        "| --- | ---: |",
    ]
    for alias_type, count in (payload.get("alias_type_counts") or {}).items():
        lines.append(f"| {alias_type} | {count} |")
    lines.extend(["", "## Alias Sample", "", "| emperor_name | alias | alias_type | scopes |", "| --- | --- | --- | --- |"])
    for row in (payload.get("alias_rows") or [])[:120]:
        scopes = ", ".join(row.get("scopes") or [])
        lines.append(f"| {row.get('emperor_name')} | {row.get('alias')} | {row.get('alias_type')} | {scopes} |")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill retrieval_v3 target aliases from canonical emperor list and alias seed.")
    sub = parser.add_subparsers(dest="command", required=True)
    apply = sub.add_parser("apply", help="Dry-run or execute target/alias backfill.")
    apply.add_argument("--emperor-list", type=Path, default=DEFAULT_EMPEROR_LIST)
    apply.add_argument("--alias-file", type=Path, default=DEFAULT_ALIAS_FILE)
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    apply.add_argument("--pg-schema", default="retrieval_v3")
    apply.add_argument("--item-code", default="I5B")
    apply.add_argument("--contract-code", default="")
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path, required=True)
    apply.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "apply":
        raise TargetAliasBackfillError(f"unsupported command: {args.command}")
    payload = execute_alias_backfill(
        emperor_list=args.emperor_list,
        alias_file=args.alias_file,
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        item_code=args.item_code,
        contract_code=args.contract_code,
        execute=bool(args.execute),
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": payload["ok"], "write_db": payload["write_db"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
