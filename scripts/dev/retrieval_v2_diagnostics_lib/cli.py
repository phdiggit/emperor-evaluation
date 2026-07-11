from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn
from scripts.dev.retrieval_v2_consumer import fetch_readiness_report
from scripts.dev.retrieval_v2_diagnostics_lib.common import (
    DEFAULT_DSN_ENV,
    DEFAULT_FORMULA_CODE,
    DEFAULT_ITEM_CODE,
    DEFAULT_RULE_CODE,
    DEFAULT_TOP_MATERIALS_PER_TARGET,
    SCOPES,
    RetrievalV2DiagnosticsError,
)
from scripts.dev.retrieval_v2_diagnostics_lib.orchestrator import fetch_db_report, fetch_report
from scripts.dev.retrieval_v2_diagnostics_lib.renderers import write_report
from scripts.dev.retrieval_v2_diagnostics_lib.score_chain import build_score_chain_from_rule_scorer_payload, enrich_score_chain_claim_details
from scripts.dev.retrieval_v2_pg_schema import schema_cursor

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only diagnostic aggregator for retrieval_v2 consumption.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", type=Path)
    common.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    common.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    common.add_argument("--rule-code", default=DEFAULT_RULE_CODE)
    common.add_argument("--formula-code", default=DEFAULT_FORMULA_CODE)
    common.add_argument("--scope", choices=SCOPES, default="accepted-packs")
    common.add_argument("--target-code", action="append", default=[])
    common.add_argument("--emperor", action="append", default=[])
    common.add_argument("--type", dest="selector_type", default="")
    common.add_argument("--role", dest="selector_role", default="")
    common.add_argument("--name", action="append", default=[])
    common.add_argument("--top-materials-per-target", type=int, default=DEFAULT_TOP_MATERIALS_PER_TARGET)
    common.add_argument(
        "--input-rule-scorer-json",
        type=Path,
        help="For score-chain only: render a retrieval_v2_rule_scorer.py apply JSON payload without reading score tables.",
    )
    common.add_argument("--output-json", type=Path, required=True)
    common.add_argument("--output-md", type=Path)
    for command in ("summary", "readiness", "coverage", "duplicates", "next-actions", "report", "score-chain"):
        subparsers.add_parser(command, parents=[common], help=f"Build {command} diagnostics.")
    return parser

def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "readiness":
        payload = fetch_readiness_report(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            item_code=args.item_code,
            rule_code=args.rule_code,
            scope=args.scope,
        )
    elif args.command in {"summary", "coverage", "duplicates"}:
        payload = fetch_db_report(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            item_code=args.item_code,
            rule_code=args.rule_code,
            formula_code=args.formula_code,
            scope=args.scope,
            command=args.command,
        )
    elif args.command == "score-chain":
        if args.input_rule_scorer_json:
            with args.input_rule_scorer_json.open("r", encoding="utf-8") as handle:
                rule_scorer_payload = json.load(handle)
            payload = build_score_chain_from_rule_scorer_payload(
                rule_scorer_payload,
                target_code="",
                target_codes=args.target_code,
                emperors=args.emperor,
                selector_type=args.selector_type,
                selector_role=args.selector_role,
                names=args.name,
                top_materials_per_target=args.top_materials_per_target,
            )
            payload["source"]["path"] = str(args.input_rule_scorer_json)
            if args.env_file is not None:
                load_env_file(args.env_file)
                psycopg, dict_row = import_psycopg()
                with psycopg.connect(resolve_dsn(args.dsn_env), row_factory=dict_row) as conn:
                    with conn.cursor() as raw:
                        # Rule score rows may live in the selected v3 scoring schema,
                        # but imported claim and passage provenance remains in the
                        # native retrieval_v2 consumption tables.
                        payload = enrich_score_chain_claim_details(raw, payload)
        else:
            payload = fetch_db_report(
                env_file=args.env_file,
                dsn_env=args.dsn_env,
                item_code=args.item_code,
                rule_code=args.rule_code,
                formula_code=args.formula_code,
                scope=args.scope,
                command=args.command,
                target_code="",
                target_codes=args.target_code,
                emperors=args.emperor,
                selector_type=args.selector_type,
                selector_role=args.selector_role,
                names=args.name,
                top_materials_per_target=args.top_materials_per_target,
            )
    elif args.command == "report":
        payload = fetch_report(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            item_code=args.item_code,
            rule_code=args.rule_code,
            formula_code=args.formula_code,
            scope=args.scope,
        )
    elif args.command == "next-actions":
        report = fetch_report(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            item_code=args.item_code,
            rule_code=args.rule_code,
            formula_code=args.formula_code,
            scope=args.scope,
        )
        payload = {
            "generated_by": "scripts/dev/retrieval_v2_diagnostics.py",
            "command": "next-actions",
            "ok": report["ok"],
            "scope": report["scope"],
            "next_actions": report["next_actions"],
            "totals": {"next_actions": len(report["next_actions"])},
        }
    else:
        raise RetrievalV2DiagnosticsError(f"unsupported command: {args.command}")
    write_report(args.output_json, args.output_md, payload)
    print(json.dumps({"ok": payload["ok"], "command": args.command, "output_json": str(args.output_json)}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
