from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import (
    anchors_resolver_contract,
    anchors_schema_proposal,
    jsonl_anchors_target_mapper,
    jsonl_evidence_cards_target_mapper,
    jsonl_evidence_clusters_resolver,
    jsonl_query_search_target_mapper,
    jsonl_sources_target_mapper,
    jsonl_staging_mapper,
    jsonl_staging_resolver_contract,
    jsonl_unknown_field_triage,
)


PRIMARY_ENV_DSN = "EMPEROR_EVAL_PG_DSN"
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")


@dataclass(frozen=True)
class ContractTool:
    name: str
    path: str
    build_report: Callable[[], Mapping[str, Any]]


@dataclass(frozen=True)
class ApplyTool:
    name: str
    path: str
    apply_report: Callable[..., Mapping[str, Any]]


CONTRACT_TOOLS = (
    ContractTool(
        "jsonl_staging_mapper",
        "scripts/platform/jsonl_staging_mapper.py",
        jsonl_staging_mapper.build_contract_report,
    ),
    ContractTool(
        "jsonl_unknown_field_triage",
        "scripts/platform/jsonl_unknown_field_triage.py",
        jsonl_unknown_field_triage.build_contract_report,
    ),
    ContractTool(
        "jsonl_staging_resolver_contract",
        "scripts/platform/jsonl_staging_resolver_contract.py",
        jsonl_staging_resolver_contract.build_contract_report,
    ),
    ContractTool(
        "jsonl_query_search_target_mapper",
        "scripts/platform/jsonl_query_search_target_mapper.py",
        jsonl_query_search_target_mapper.build_contract_report,
    ),
    ContractTool(
        "jsonl_sources_target_mapper",
        "scripts/platform/jsonl_sources_target_mapper.py",
        jsonl_sources_target_mapper.build_contract_report,
    ),
    ContractTool(
        "jsonl_evidence_cards_target_mapper",
        "scripts/platform/jsonl_evidence_cards_target_mapper.py",
        jsonl_evidence_cards_target_mapper.build_contract_report,
    ),
    ContractTool(
        "jsonl_evidence_clusters_resolver",
        "scripts/platform/jsonl_evidence_clusters_resolver.py",
        jsonl_evidence_clusters_resolver.build_contract_report,
    ),
    ContractTool(
        "anchors_schema_proposal",
        "scripts/platform/anchors_schema_proposal.py",
        anchors_schema_proposal.build_contract_report,
    ),
    ContractTool(
        "anchors_resolver_contract",
        "scripts/platform/anchors_resolver_contract.py",
        anchors_resolver_contract.build_contract_report,
    ),
    ContractTool(
        "jsonl_anchors_target_mapper",
        "scripts/platform/jsonl_anchors_target_mapper.py",
        jsonl_anchors_target_mapper.build_contract_report,
    ),
)

APPLY_TOOLS = (
    ApplyTool(
        "jsonl_query_search_target_mapper",
        "scripts/platform/jsonl_query_search_target_mapper.py",
        jsonl_query_search_target_mapper.apply_target_mapper,
    ),
    ApplyTool(
        "jsonl_sources_target_mapper",
        "scripts/platform/jsonl_sources_target_mapper.py",
        jsonl_sources_target_mapper.apply_target_mapper,
    ),
    ApplyTool(
        "jsonl_evidence_cards_target_mapper",
        "scripts/platform/jsonl_evidence_cards_target_mapper.py",
        jsonl_evidence_cards_target_mapper.apply_target_mapper,
    ),
    ApplyTool(
        "jsonl_evidence_clusters_resolver",
        "scripts/platform/jsonl_evidence_clusters_resolver.py",
        jsonl_evidence_clusters_resolver.apply_resolver,
    ),
    ApplyTool(
        "jsonl_anchors_target_mapper",
        "scripts/platform/jsonl_anchors_target_mapper.py",
        jsonl_anchors_target_mapper.apply_target_mapper,
    ),
)


def build_contract_matrix() -> dict[str, Any]:
    tools: list[dict[str, Any]] = []
    passed: list[str] = []
    failed: list[dict[str, str]] = []

    for tool in CONTRACT_TOOLS:
        try:
            report = dict(tool.build_report())
            report_text = report_as_json(report).lower()
            blocked = any(term in report_text for term in BLOCKED_REPORT_TERMS)
            status = "passed" if not blocked else "failed"
            entry = {
                "name": tool.name,
                "path": tool.path,
                "mode": str(report.get("mode", "contract-report")),
                "status": status,
                "report_keys": sorted(str(key) for key in report),
            }
            if blocked:
                entry["reason"] = "blocked report term present"
                failed.append({"tool": tool.name, "reason": "blocked report term present"})
            else:
                passed.append(tool.name)
            tools.append(entry)
        except Exception as exc:  # pragma: no cover - exercised by failure diagnostics.
            tools.append(
                {
                    "name": tool.name,
                    "path": tool.path,
                    "mode": "contract-report",
                    "status": "failed",
                    "reason": exc.__class__.__name__,
                }
            )
            failed.append({"tool": tool.name, "reason": exc.__class__.__name__})

    return {
        "mode": "contract-matrix",
        "tool_count": len(CONTRACT_TOOLS),
        "tools": tools,
        "passed": passed,
        "failed": failed,
        "skipped": [],
        "reports_checked": len(tools),
        "blocked_terms_checked": {
            "count": len(BLOCKED_REPORT_TERMS),
            "passed": not failed,
        },
        "limitations": [
            "offline_only",
            "does_not_read_dotenv_or_dsn",
            "does_not_connect_to_database",
            "does_not_access_network",
            "does_not_write_target_tables",
        ],
    }


def build_apply_matrix(*, schema_prefix: str, drop_schema_after: bool = True) -> dict[str, Any]:
    validate_schema_prefix(schema_prefix)
    dsn = os.environ.get(PRIMARY_ENV_DSN)
    dsn_present = bool(dsn)
    driver_available = importlib.util.find_spec("psycopg") is not None
    tools: list[dict[str, Any]] = []
    passed: list[str] = []
    failed: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    if not dsn_present or not driver_available:
        reason = f"{PRIMARY_ENV_DSN} is not set" if not dsn_present else "psycopg is not installed"
        for tool in APPLY_TOOLS:
            entry = {
                "name": tool.name,
                "path": tool.path,
                "mode": "apply",
                "status": "skipped",
                "reason": reason,
            }
            tools.append(entry)
            skipped.append({"tool": tool.name, "reason": reason})
        return {
            "mode": "apply-matrix",
            "dsn_present": dsn_present,
            "driver_available": driver_available,
            "tools": tools,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "schema_prefix": schema_prefix,
            "all_schemas_dropped": True,
            "limitations": [
                "opt_in_only",
                "uses_primary_environment_dsn_only",
                "does_not_print_dsn",
                "uses_isolated_random_schema_per_tool",
            ],
        }

    for tool in APPLY_TOOLS:
        schema = build_schema_name(schema_prefix, tool.name)
        try:
            report = dict(tool.apply_report(dsn or "", schema=schema, drop_schema_after=drop_schema_after))
            schema_exists_after_drop = report.get("schema_exists_after_drop")
            dropped = bool(drop_schema_after and schema_exists_after_drop is False)
            status = "passed" if dropped else "failed"
            entry = {
                "name": tool.name,
                "path": tool.path,
                "mode": "apply",
                "status": status,
                "schema": schema,
                "schema_exists_after_drop": schema_exists_after_drop,
            }
            if status == "passed":
                passed.append(tool.name)
            else:
                entry["reason"] = "schema cleanup was not confirmed"
                failed.append({"tool": tool.name, "reason": "schema cleanup was not confirmed"})
            tools.append(entry)
        except Exception as exc:  # pragma: no cover - requires a live PostgreSQL failure.
            tools.append(
                {
                    "name": tool.name,
                    "path": tool.path,
                    "mode": "apply",
                    "status": "failed",
                    "schema": schema,
                    "reason": exc.__class__.__name__,
                }
            )
            failed.append({"tool": tool.name, "reason": exc.__class__.__name__})

    return {
        "mode": "apply-matrix",
        "dsn_present": dsn_present,
        "driver_available": driver_available,
        "tools": tools,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "schema_prefix": schema_prefix,
        "all_schemas_dropped": not failed,
        "limitations": [
            "opt_in_only",
            "uses_primary_environment_dsn_only",
            "does_not_print_dsn",
            "uses_isolated_random_schema_per_tool",
        ],
    }


def build_schema_name(schema_prefix: str, tool_name: str) -> str:
    suffix = re.sub(r"[^a-z0-9_]+", "_", tool_name.lower()).strip("_")
    token = uuid.uuid4().hex[:10]
    value = f"{schema_prefix}_{suffix}_{token}"
    if len(value) > 63:
        value = f"{schema_prefix}_{token}"
    validate_schema_prefix(value)
    return value


def validate_schema_prefix(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"invalid PostgreSQL schema prefix: {value!r}")


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run platform prototype contract and opt-in apply smoke checks.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--contract-matrix", action="store_true", help="run offline prototype contract reports")
    mode.add_argument("--apply-matrix", action="store_true", help="run opt-in PostgreSQL apply smoke checks")
    parser.add_argument("--schema-prefix", default="emperor_eval_smoke", help="schema prefix for apply smoke checks")
    parser.add_argument(
        "--drop-schema-after",
        action="store_true",
        default=True,
        help="drop isolated apply schemas after each tool; enabled by default",
    )
    args = parser.parse_args(argv)

    report = (
        build_contract_matrix()
        if args.contract_matrix
        else build_apply_matrix(schema_prefix=args.schema_prefix, drop_schema_after=args.drop_schema_after)
    )
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
