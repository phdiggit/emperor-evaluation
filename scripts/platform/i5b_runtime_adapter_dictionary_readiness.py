from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import i5b_dictionary_snapshot_loader_validator as snapshot_loader  # noqa: E402
from scripts.platform import i5b_rule_display_dictionary_contract as contract  # noqa: E402
from scripts.platform.core.fingerprints import file_sha256  # noqa: E402


PACKAGE_VERSION = "i5b-runtime-adapter-dictionary-readiness-v1"
ROADMAP_ISSUE = contract.ROADMAP_ISSUE
EPIC_ISSUE = contract.EPIC_ISSUE
TECH_DEBT_ISSUE = contract.TECH_DEBT_ISSUE
SNAPSHOT_LOADER_VALIDATOR_PACKAGE = snapshot_loader.PACKAGE_VERSION
SNAPSHOT_LOADER_VALIDATOR_PR = 321
SNAPSHOT_LOADER_VALIDATOR_MERGE_COMMIT = "7d9fc11dfde05de50d3134c10a5aebf877771f86"
SUPPORTED_MODES = ("readiness-report", "readiness-md")


MIGRATION_BATCHES = [
    {
        "batch_id": "issue311_readthrough_loader_shim",
        "purpose": "wire a stable dictionary readthrough API while keeping exporter output byte-compatible",
        "runtime_output_change_allowed": False,
        "requires_schema_gate": False,
    },
    {
        "batch_id": "issue311_rules_py_keyword_dictionary_read",
        "purpose": "route rules.py keyword and rule-sensitive dictionaries through the readthrough API",
        "runtime_output_change_allowed": False,
        "requires_schema_gate": False,
    },
    {
        "batch_id": "issue311_formal_algorithm_grade_dictionary_read",
        "purpose": "route formal grade enum, band specs, and direction mapping through the readthrough API",
        "runtime_output_change_allowed": False,
        "requires_schema_gate": False,
    },
    {
        "batch_id": "issue311_display_dictionary_read",
        "purpose": "route G8/G9 display labels and explanatory text through the display dictionary",
        "runtime_output_change_allowed": False,
        "requires_schema_gate": False,
    },
    {
        "batch_id": "issue311_python_constant_cleanup_after_readthrough",
        "purpose": "remove duplicated Python dictionary text only after readthrough parity tests are green",
        "runtime_output_change_allowed": False,
        "requires_schema_gate": False,
    },
]


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _module_symbol_kinds(path: Path) -> dict[str, str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=_relative(path))
    symbols: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols[node.name] = "function"
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for name in _target_names(target):
                    symbols[name] = "assignment"
        elif isinstance(node, ast.AnnAssign):
            for name in _target_names(node.target):
                symbols[name] = "assignment"
    return symbols


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in target.elts:
            names.extend(_target_names(element))
        return names
    return []


def _inventory_by_symbol() -> dict[str, dict[str, Any]]:
    return {str(item["symbol"]): dict(item) for item in contract.HARD_CODED_INVENTORY}


def build_runtime_surface_inventory() -> list[dict[str, Any]]:
    symbols_by_path: dict[str, dict[str, str]] = {}
    file_sha_by_path: dict[str, str] = {}
    for source_path in contract.SOURCE_MODULES:
        path = ROOT / source_path
        symbols_by_path[source_path] = _module_symbol_kinds(path)
        file_sha_by_path[source_path] = file_sha256(path)

    items: list[dict[str, Any]] = []
    for item in contract.HARD_CODED_INVENTORY:
        source_path = str(item["source_path"])
        symbol = str(item["symbol"])
        definition_kind = symbols_by_path[source_path].get(symbol)
        items.append(
            {
                "source_path": source_path,
                "source_sha256": file_sha_by_path[source_path],
                "symbol": symbol,
                "dictionary_type": item["dictionary_type"],
                "target_snapshot": item["target_snapshot"],
                "migration_action": item["migration_action"],
                "definition_kind": definition_kind,
                "symbol_present": definition_kind is not None,
            }
        )
    return items


def build_readiness_report() -> dict[str, Any]:
    snapshot_report = snapshot_loader.build_snapshot_report()
    runtime_inventory = build_runtime_surface_inventory()
    missing_symbols = [item["symbol"] for item in runtime_inventory if not item["symbol_present"]]
    covered_symbols = set(snapshot_report["covered_inventory_symbols"])
    inventory_symbols = set(_inventory_by_symbol())
    snapshot_missing_symbols = sorted(inventory_symbols - covered_symbols)
    blockers = []
    if missing_symbols:
        blockers.append("runtime_symbol_inventory_incomplete")
    if snapshot_report["validation_errors"]:
        blockers.append("snapshot_validation_failed")
    if snapshot_missing_symbols:
        blockers.append("snapshot_inventory_coverage_incomplete")

    ready = not blockers
    return {
        "mode": "readiness-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "tech_debt_issue": TECH_DEBT_ISSUE,
        "snapshot_loader_validator_package": SNAPSHOT_LOADER_VALIDATOR_PACKAGE,
        "snapshot_loader_validator_pr": SNAPSHOT_LOADER_VALIDATOR_PR,
        "snapshot_loader_validator_merge_commit": SNAPSHOT_LOADER_VALIDATOR_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_import_runtime_adapter": True,
        "does_not_render_exports": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_write_business_tables": True,
        "does_not_write_postgres_dictionary_tables": True,
        "does_not_modify_runtime_adapter": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "current_state": {
            "current_phase": "issue311_i5b_runtime_adapter_dictionary_readiness_ready",
            "active_epic": EPIC_ISSUE,
            "active_tech_debt": TECH_DEBT_ISSUE,
            "issue311_dictionary_contract_ready": True,
            "issue311_dictionary_snapshot_loader_validator_ready": True,
            "issue311_runtime_adapter_dictionary_readiness_ready": ready,
            "runtime_symbol_inventory_complete": not missing_symbols,
            "snapshot_validation_passed": snapshot_report["validated"],
            "snapshot_inventory_coverage_complete": not snapshot_missing_symbols,
            "runtime_adapter_migrated": False,
            "postgres_dictionary_tables_created": False,
            "canonical_dictionary_write_performed": False,
            "ordinary_exports_require_live_dsn": False,
            "g10_destructive_cleanup_entered": False,
        },
        "readiness_blockers": blockers,
        "runtime_inventory": runtime_inventory,
        "runtime_inventory_count": len(runtime_inventory),
        "runtime_missing_symbols": missing_symbols,
        "snapshot_missing_symbols": snapshot_missing_symbols,
        "migration_batches": MIGRATION_BATCHES,
        "next_required_work": "issue311_readthrough_loader_shim_package",
    }


def render_readiness_md() -> str:
    report = build_readiness_report()
    lines = [
        "# I5B Runtime Adapter Dictionary Readiness",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- tech_debt_issue: `#{report['tech_debt_issue']}`",
        f"- runtime_inventory_count: `{report['runtime_inventory_count']}`",
        f"- readiness_blockers: `{len(report['readiness_blockers'])}`",
        "",
        "## Runtime Inventory",
        "",
    ]
    for item in report["runtime_inventory"]:
        lines.append(
            f"- `{item['source_path']}::{item['symbol']}` -> "
            f"`{item['dictionary_type']}` / `{item['definition_kind']}`"
        )

    lines.extend(["", "## Migration Batches", ""])
    for batch in report["migration_batches"]:
        lines.append(
            f"- `{batch['batch_id']}`: runtime_output_change_allowed="
            f"`{str(batch['runtime_output_change_allowed']).lower()}`"
        )

    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Check I5B runtime adapter readiness for dictionary readthrough.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--readiness-report", action="store_true")
    mode.add_argument("--readiness-md", action="store_true")
    args = parser.parse_args(argv)

    if args.readiness_md:
        sys.stdout.write(render_readiness_md())
        return 0

    sys.stdout.write(report_as_json(build_readiness_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
