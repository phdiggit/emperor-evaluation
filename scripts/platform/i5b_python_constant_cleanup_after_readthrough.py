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


PACKAGE_VERSION = "i5b-python-constant-cleanup-after-readthrough-v1"
ROADMAP_ISSUE = contract.ROADMAP_ISSUE
EPIC_ISSUE = contract.EPIC_ISSUE
TECH_DEBT_ISSUE = contract.TECH_DEBT_ISSUE
DISPLAY_READTHROUGH_PR = 327
DISPLAY_READTHROUGH_MERGE_COMMIT = "010030af7acf191fb5f94fbd02a03b3f94dfd16a"
SUPPORTED_MODES = ("cleanup-report", "cleanup-md")

LEGACY_LITERAL_MARKERS = (
    'TRIAL_SCORE_MAP = {\n    "极正候选 / 高位强正上探极正"',
    "HIGH_VALUE_ANCHOR_KEYWORDS = (",
    "STARTUP_ANCHOR_KEYWORDS = (",
    "BOUNDARY_ANCHOR_KEYWORDS = (",
    "DIRECT_SAFETY_KEYWORDS = (",
    "DIMENSION_RULES = [",
    "FORMAL_GRADE_ENUM = (",
    'AUTO_DIRECTION_TO_FORMAL_GRADE = {',
    'FORMAL_GRADE_BAND_POSITION = {',
    "本文件定义第五项B《用人与授权》的 V3.2",
    "### 正式分值与排名落地",
)

READTHROUGH_REFERENCES = {
    "TRIAL_SCORE_MAP": '_GRADE_DICTIONARY_VALUES["TRIAL_SCORE_MAP"]',
    "HIGH_VALUE_ANCHOR_KEYWORDS": '_RULE_KEYWORD_VALUES["HIGH_VALUE_ANCHOR_KEYWORDS"]',
    "STARTUP_ANCHOR_KEYWORDS": '_RULE_KEYWORD_VALUES["STARTUP_ANCHOR_KEYWORDS"]',
    "BOUNDARY_ANCHOR_KEYWORDS": '_RULE_KEYWORD_VALUES["BOUNDARY_ANCHOR_KEYWORDS"]',
    "DIRECT_SAFETY_KEYWORDS": '_RULE_KEYWORD_VALUES["DIRECT_SAFETY_KEYWORDS"]',
    "POSITIVE_CORE_KEYWORDS": '_RULE_KEYWORD_VALUES["POSITIVE_CORE_KEYWORDS"]',
    "RULE_SENSITIVE_POINTS": '_RULE_DICTIONARY_VALUES["RULE_SENSITIVE_POINTS"]',
    "DIMENSION_RULES": '_DIRECTION_GRADE_MAPPING_VALUES["DIMENSION_RULES"]',
    "FORMAL_GRADE_ENUM": '_GRADE_DICTIONARY_VALUES["FORMAL_GRADE_ENUM"]',
    "FORMAL_GRADE_SPECS": '_GRADE_DICTIONARY_VALUES["FORMAL_GRADE_SPECS"]',
    "AUTO_DIRECTION_TO_FORMAL_GRADE": '_DIRECTION_GRADE_MAPPING_VALUES["AUTO_DIRECTION_TO_FORMAL_GRADE"]',
    "FORMAL_GRADE_BAND_POSITION": '_DIRECTION_GRADE_MAPPING_VALUES["FORMAL_GRADE_BAND_POSITION"]',
    "render_score_mapping_draft": '_DISPLAY_DICTIONARY_VALUES["render_score_mapping_draft"]',
    "render_formal_person_section": '_DISPLAY_DICTIONARY_VALUES["render_formal_person_section"]',
}


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in target.elts:
            names.extend(_target_names(element))
        return names
    return []


def _module_symbol_segments(path: Path) -> dict[str, dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=_relative(path))
    symbols: dict[str, dict[str, Any]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols[node.name] = {
                "definition_kind": "function",
                "source": ast.get_source_segment(source, node) or "",
                "rhs_literal_container": False,
            }
        elif isinstance(node, ast.Assign):
            rhs_literal_container = isinstance(node.value, (ast.Dict, ast.List, ast.Tuple, ast.Set))
            segment = ast.get_source_segment(source, node) or ""
            for target in node.targets:
                for name in _target_names(target):
                    symbols[name] = {
                        "definition_kind": "assignment",
                        "source": segment,
                        "rhs_literal_container": rhs_literal_container,
                    }
        elif isinstance(node, ast.AnnAssign):
            rhs_literal_container = isinstance(node.value, (ast.Dict, ast.List, ast.Tuple, ast.Set))
            segment = ast.get_source_segment(source, node) or ""
            for name in _target_names(node.target):
                symbols[name] = {
                    "definition_kind": "assignment",
                    "source": segment,
                    "rhs_literal_container": rhs_literal_container,
                }
    return symbols


def build_cleanup_inventory() -> list[dict[str, Any]]:
    symbols_by_path = {
        source_path: _module_symbol_segments(ROOT / source_path)
        for source_path in contract.SOURCE_MODULES
    }
    items: list[dict[str, Any]] = []
    for inventory_item in contract.HARD_CODED_INVENTORY:
        source_path = str(inventory_item["source_path"])
        symbol = str(inventory_item["symbol"])
        symbol_info = symbols_by_path[source_path].get(symbol, {})
        source_segment = str(symbol_info.get("source") or "")
        marker_matches = [marker for marker in LEGACY_LITERAL_MARKERS if marker in source_segment]
        reference = READTHROUGH_REFERENCES[symbol]
        items.append(
            {
                "source_path": source_path,
                "symbol": symbol,
                "dictionary_type": inventory_item["dictionary_type"],
                "definition_kind": symbol_info.get("definition_kind"),
                "symbol_present": bool(symbol_info),
                "readthrough_reference": reference,
                "readthrough_reference_present": reference in source_segment,
                "legacy_literal_container_present": bool(symbol_info.get("rhs_literal_container")),
                "legacy_literal_markers_present": bool(marker_matches),
                "legacy_literal_marker_matches": marker_matches,
            }
        )
    return items


def build_cleanup_report() -> dict[str, Any]:
    snapshot_report = snapshot_loader.build_snapshot_report()
    inventory = build_cleanup_inventory()
    missing_symbols = [item["symbol"] for item in inventory if not item["symbol_present"]]
    missing_readthrough_refs = [item["symbol"] for item in inventory if not item["readthrough_reference_present"]]
    legacy_literal_symbols = [
        item["symbol"]
        for item in inventory
        if item["legacy_literal_container_present"] or item["legacy_literal_markers_present"]
    ]
    blockers = []
    if missing_symbols:
        blockers.append("runtime_symbol_missing")
    if missing_readthrough_refs:
        blockers.append("readthrough_reference_missing")
    if legacy_literal_symbols:
        blockers.append("legacy_python_dictionary_text_still_present")
    if snapshot_report["validation_errors"]:
        blockers.append("snapshot_validation_failed")

    ready = not blockers
    return {
        "mode": "cleanup-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "tech_debt_issue": TECH_DEBT_ISSUE,
        "display_readthrough_pr": DISPLAY_READTHROUGH_PR,
        "display_readthrough_merge_commit": DISPLAY_READTHROUGH_MERGE_COMMIT,
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
            "current_phase": "issue311_i5b_python_constant_cleanup_after_readthrough_ready",
            "active_epic": EPIC_ISSUE,
            "active_tech_debt": TECH_DEBT_ISSUE,
            "issue311_python_constant_cleanup_after_readthrough_ready": ready,
            "runtime_adapter_migrated": True,
            "legacy_python_dictionary_text_removed": not legacy_literal_symbols,
            "readthrough_references_complete": not missing_readthrough_refs,
            "snapshot_validation_passed": snapshot_report["validated"],
            "postgres_dictionary_tables_created": False,
            "canonical_dictionary_write_performed": False,
            "ordinary_exports_require_live_dsn": False,
            "g10_destructive_cleanup_entered": False,
        },
        "cleanup_blockers": blockers,
        "cleanup_inventory": inventory,
        "cleanup_inventory_count": len(inventory),
        "missing_symbols": missing_symbols,
        "missing_readthrough_references": missing_readthrough_refs,
        "legacy_literal_symbols": legacy_literal_symbols,
        "next_required_work": "issue_311_rule_display_dictionary_governance_gate",
    }


def render_cleanup_md() -> str:
    report = build_cleanup_report()
    lines = [
        "# I5B Python Constant Cleanup After Readthrough",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- tech_debt_issue: `#{report['tech_debt_issue']}`",
        f"- cleanup_blockers: `{len(report['cleanup_blockers'])}`",
        f"- next_required_work: `{report['next_required_work']}`",
        "",
        "## Cleanup Inventory",
        "",
    ]
    for item in report["cleanup_inventory"]:
        lines.append(
            f"- `{item['source_path']}::{item['symbol']}` -> "
            f"readthrough=`{str(item['readthrough_reference_present']).lower()}`, "
            f"legacy_literal=`{str(item['legacy_literal_container_present'] or item['legacy_literal_markers_present']).lower()}`"
        )

    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Audit I5B Python dictionary constant cleanup after readthrough.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cleanup-report", action="store_true")
    mode.add_argument("--cleanup-md", action="store_true")
    args = parser.parse_args(argv)

    if args.cleanup_md:
        sys.stdout.write(render_cleanup_md())
        return 0

    sys.stdout.write(report_as_json(build_cleanup_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
