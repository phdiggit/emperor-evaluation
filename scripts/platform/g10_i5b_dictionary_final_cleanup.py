from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import i5b_dictionary_snapshot_loader_validator as snapshot_loader  # noqa: E402


PACKAGE_VERSION = "g10-i5b-dictionary-final-cleanup-v1"
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
PLAN_ISSUE = 331
CLEANUP_ISSUE = 332
RELATED_TECH_DEBT_ISSUE = 311
PREREQUISITE_PR = 336
PREREQUISITE_MERGE_COMMIT = "027a084a7045e68343177eb09236cf4f090324d4"
SUPPORTED_MODES = ("cleanup-report", "cleanup-md")
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")

RUNTIME_SOURCE_TARGETS: tuple[dict[str, Any], ...] = (
    {
        "path": "scripts/export/dimension_adapters/i5b_people_delegation/rules.py",
        "classification": "algorithm_invariant_runtime",
        "expected_role": "Runtime symbols, keys, predicates, and loader calls only; rule/display payload lives in the snapshot.",
    },
    {
        "path": "scripts/export/dimension_adapters/i5b_people_delegation/formal_algorithm.py",
        "classification": "algorithm_invariant_runtime",
        "expected_role": "Formal scoring arithmetic and mapping keys only; display rows and labels read from the snapshot.",
    },
    {
        "path": "scripts/export/dimension_adapters/i5b_people_delegation/adapter.py",
        "classification": "display_copy",
        "expected_role": "Exporter display rendering and compatibility labels; not the score/rule dictionary source of truth.",
    },
    {
        "path": "scripts/shared/i5b_markdown_display_defaults.py",
        "classification": "display_config_source",
        "expected_role": "Checked-in Markdown view defaults; controls presentation only, not scoring or adjudication semantics.",
    },
)
TEST_FIXTURE_TARGETS = (
    "tests/test_i5b_dictionary_readthrough.py",
    "tests/test_i5b_auto_adjudication.py",
    "tests/test_g8_i5b_formal_algorithm_release.py",
    "tests/test_g9_i5b_formal_publication_release.py",
)
LEGACY_RUNTIME_COPY_MARKERS = (
    "同一维度内至少三个强正核心",
    "强负核心或中负升强负边界必须阻断高位上探",
    "高位强正，上探极正候选",
    "强正受压制，不上探极正",
    "强正封顶，不上探极正",
    "中正受中负压制",
    "中正受强负压制",
    "自动草案待规则复核",
)
REQUIRED_RULE_RUNTIME_TEXT_KEYS = (
    "auto_band_directions",
    "formal_band_map",
    "infer_dimension_fallback_rules",
    "negative_boundary_results",
    "rule_sensitive_decisions",
    "score_stage_prerequisite_text",
)
REQUIRED_FORMAL_ALGORITHM_DISPLAY_KEYS = (
    "default_formal_grade",
    "mapping_rows",
    "negative_intercept_condition",
    "score_range_text",
)
BLOCKED_OUTPUTS = (
    "postgres_dictionary_table_creation",
    "canonical_dictionary_write",
    "live_dsn_dependency",
    "runtime_database_dictionary_lookup",
    "new_subitem_formal_scores",
    "new_subitem_formal_rankings",
    "stage_total_table",
    "final_total_table",
    "cross_subitem_leaderboard",
    "g10_destructive_cleanup",
)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _read_source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _chinese_string_literals(relative_path: str) -> list[dict[str, Any]]:
    source = _read_source(relative_path)
    tree = ast.parse(source, filename=relative_path)
    strings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and CHINESE_RE.search(node.value):
            value = node.value.replace("\n", "\\n")
            strings.append(
                {
                    "line": int(getattr(node, "lineno", 0)),
                    "sample": value[:96],
                }
            )
    return sorted(strings, key=lambda item: item["line"])


def _source_classification_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for target in RUNTIME_SOURCE_TARGETS:
        strings = _chinese_string_literals(str(target["path"]))
        items.append(
            {
                "path": target["path"],
                "classification": target["classification"],
                "expected_role": target["expected_role"],
                "chinese_string_literal_count": len(strings),
                "sample_literals": strings[:8],
            }
        )
    for relative_path in TEST_FIXTURE_TARGETS:
        strings = _chinese_string_literals(relative_path)
        items.append(
            {
                "path": relative_path,
                "classification": "test_fixture",
                "expected_role": "Expected output and regression fixture text only; not runtime rule or display source.",
                "chinese_string_literal_count": len(strings),
                "sample_literals": strings[:8],
            }
        )
    return items


def _runtime_source_text() -> dict[str, str]:
    return {str(target["path"]): _read_source(str(target["path"])) for target in RUNTIME_SOURCE_TARGETS[:3]}


def _snapshot_values() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    snapshot = snapshot_loader.load_snapshot()
    rule_values: dict[str, Any] = {}
    direction_values: dict[str, Any] = {}
    for item in snapshot["items"]:
        if item["rule_id"] == "i5b.rule_dictionary.v1":
            rule_values = dict(item["payload"]["values_by_symbol"])
        elif item["rule_id"] == "i5b.direction_grade_mapping.v1":
            direction_values = dict(item["payload"]["values_by_symbol"])
    return snapshot, rule_values, direction_values


def _runtime_readthrough_checks(source_by_path: Mapping[str, str]) -> dict[str, bool]:
    rules_source = source_by_path["scripts/export/dimension_adapters/i5b_people_delegation/rules.py"]
    formal_source = source_by_path["scripts/export/dimension_adapters/i5b_people_delegation/formal_algorithm.py"]
    adapter_source = source_by_path["scripts/export/dimension_adapters/i5b_people_delegation/adapter.py"]
    return {
        "rules_py_rule_runtime_text_readthrough": '_RULE_DICTIONARY_VALUES["RULE_RUNTIME_TEXT"]' in rules_source,
        "rules_py_auto_band_directions_exported": 'AUTO_BAND_DIRECTIONS = _RULE_RUNTIME_TEXT["auto_band_directions"]'
        in rules_source,
        "formal_algorithm_display_readthrough": '_DIRECTION_GRADE_MAPPING_VALUES["FORMAL_ALGORITHM_DISPLAY"]'
        in formal_source,
        "adapter_auto_band_directions_readthrough": 'AUTO_BAND_DIRECTIONS["high_strong_extreme_candidate"]'
        in adapter_source,
    }


def _legacy_runtime_copy_matches(source_by_path: Mapping[str, str]) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for path, source in source_by_path.items():
        for marker in LEGACY_RUNTIME_COPY_MARKERS:
            if marker in source:
                matches.append({"path": path, "marker": marker})
    return matches


def _dictionary_payload_summary(rule_values: Mapping[str, Any], direction_values: Mapping[str, Any]) -> dict[str, Any]:
    rule_runtime_text = rule_values.get("RULE_RUNTIME_TEXT", {})
    formal_algorithm_display = direction_values.get("FORMAL_ALGORITHM_DISPLAY", {})
    return {
        "dictionary_payload_classification": "dictionary_payload",
        "rule_runtime_text_present": isinstance(rule_runtime_text, Mapping),
        "rule_runtime_text_keys": sorted(rule_runtime_text) if isinstance(rule_runtime_text, Mapping) else [],
        "formal_algorithm_display_present": isinstance(formal_algorithm_display, Mapping),
        "formal_algorithm_display_keys": sorted(formal_algorithm_display)
        if isinstance(formal_algorithm_display, Mapping)
        else [],
        "required_rule_runtime_text_keys_present": all(
            key in rule_runtime_text for key in REQUIRED_RULE_RUNTIME_TEXT_KEYS
        )
        if isinstance(rule_runtime_text, Mapping)
        else False,
        "required_formal_algorithm_display_keys_present": all(
            key in formal_algorithm_display for key in REQUIRED_FORMAL_ALGORITHM_DISPLAY_KEYS
        )
        if isinstance(formal_algorithm_display, Mapping)
        else False,
        "auto_band_direction_keys": sorted(rule_runtime_text.get("auto_band_directions", {}))
        if isinstance(rule_runtime_text, Mapping)
        and isinstance(rule_runtime_text.get("auto_band_directions"), Mapping)
        else [],
        "mapping_row_count": len(formal_algorithm_display.get("mapping_rows", []))
        if isinstance(formal_algorithm_display, Mapping)
        else 0,
    }


def build_cleanup_report() -> dict[str, Any]:
    snapshot_report = snapshot_loader.build_snapshot_report()
    _, rule_values, direction_values = _snapshot_values()
    source_by_path = _runtime_source_text()
    readthrough_checks = _runtime_readthrough_checks(source_by_path)
    legacy_matches = _legacy_runtime_copy_matches(source_by_path)
    dictionary_payload = _dictionary_payload_summary(rule_values, direction_values)
    source_classifications = _source_classification_items()

    blockers = []
    if not snapshot_report["validated"]:
        blockers.append("snapshot_validation_failed")
    if not all(readthrough_checks.values()):
        blockers.append("runtime_readthrough_check_failed")
    if legacy_matches:
        blockers.append("legacy_runtime_copy_still_present")
    if not dictionary_payload["required_rule_runtime_text_keys_present"]:
        blockers.append("rule_runtime_text_payload_incomplete")
    if not dictionary_payload["required_formal_algorithm_display_keys_present"]:
        blockers.append("formal_algorithm_display_payload_incomplete")

    ready = not blockers
    return {
        "mode": "cleanup-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "plan_issue": PLAN_ISSUE,
        "cleanup_issue": CLEANUP_ISSUE,
        "related_tech_debt_issue": RELATED_TECH_DEBT_ISSUE,
        "prerequisite_pr": PREREQUISITE_PR,
        "prerequisite_merge_commit": PREREQUISITE_MERGE_COMMIT,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_import_runtime_adapter": True,
        "does_not_render_exports": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_read_batch_payloads": True,
        "does_not_read_generated_exports": True,
        "does_not_write_business_tables": True,
        "does_not_write_postgres_dictionary_tables": True,
        "does_not_move_delete_or_archive_files": True,
        "does_not_publish_scores": True,
        "does_not_publish_rankings": True,
        "snapshot_path": snapshot_report["snapshot_path"],
        "snapshot_file_sha256": snapshot_report["snapshot_file_sha256"],
        "snapshot_item_count": snapshot_report["snapshot_item_count"],
        "snapshot_validated": snapshot_report["validated"],
        "snapshot_validation_errors": snapshot_report["validation_errors"],
        "snapshot_item_digests": snapshot_report["item_digests"],
        "dictionary_payload_summary": dictionary_payload,
        "runtime_readthrough_checks": readthrough_checks,
        "legacy_runtime_copy_matches": legacy_matches,
        "source_text_classifications": source_classifications,
        "source_text_classification_paths": [item["path"] for item in source_classifications],
        "classification_policy": {
            "algorithm_invariant_runtime": "Runtime predicate/key/control-flow literals only; business rule copy is not authoritative here.",
            "dictionary_payload": "Versioned immutable snapshot payload carrying rule, mapping, and display text with digest validation.",
            "display_copy": "Renderer labels and summaries for human-readable Markdown; no scoring source-of-truth role.",
            "display_config_source": "Checked-in Markdown presentation defaults; no scoring or adjudication source-of-truth role.",
            "test_fixture": "Expected output strings that lock parity and regressions only.",
        },
        "current_state": {
            "current_phase": "g10_i5b_dictionary_final_cleanup_ready",
            "active_epic": EPIC_ISSUE,
            "active_tech_debt": RELATED_TECH_DEBT_ISSUE,
            "g10_1_i5b_dictionary_final_cleanup_ready": ready,
            "g10_execution_started": True,
            "g10_cleanup_execution_started": True,
            "g10_destructive_cleanup_started": False,
            "issue311_completion_state_synchronized": True,
            "i5b_rule_runtime_text_readthrough_enabled": readthrough_checks[
                "rules_py_rule_runtime_text_readthrough"
            ],
            "i5b_formal_algorithm_display_readthrough_enabled": readthrough_checks[
                "formal_algorithm_display_readthrough"
            ],
            "i5b_adapter_auto_band_directions_readthrough_enabled": readthrough_checks[
                "adapter_auto_band_directions_readthrough"
            ],
            "i5b_remaining_python_text_classified": bool(source_classifications),
            "i5b_snapshot_final_cleanup_digest_validation_passed": snapshot_report["validated"],
            "i5b_no_legacy_runtime_copy_regressions": not legacy_matches,
            "postgres_dictionary_tables_created": False,
            "canonical_dictionary_write_performed": False,
            "ordinary_exports_require_live_dsn": False,
            "new_subitem_formal_scores_released": False,
            "new_subitem_formal_rankings_released": False,
            "cross_subitem_leaderboard_released": False,
        },
        "cleanup_blockers": blockers,
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "next_required_work": "issue333_historical_asset_retirement_after_inventory",
    }


def render_cleanup_md() -> str:
    report = build_cleanup_report()
    lines = [
        "# G10 I5B Dictionary Final Cleanup",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- cleanup_issue: `#{report['cleanup_issue']}`",
        f"- related_tech_debt_issue: `#{report['related_tech_debt_issue']}`",
        f"- prerequisite_pr: `#{report['prerequisite_pr']}`",
        f"- snapshot_validated: `{str(report['snapshot_validated']).lower()}`",
        f"- cleanup_blockers: `{len(report['cleanup_blockers'])}`",
        f"- next_required_work: `{report['next_required_work']}`",
        "",
        "## Runtime Readthrough",
        "",
    ]
    for key, value in sorted(report["runtime_readthrough_checks"].items()):
        lines.append(f"- `{key}`: `{str(value).lower()}`")

    lines.extend(["", "## Source Text Classifications", ""])
    for item in report["source_text_classifications"]:
        lines.append(
            f"- `{item['path']}` -> classification=`{item['classification']}`, "
            f"chinese_string_literals=`{item['chinese_string_literal_count']}`"
        )

    lines.extend(["", "## Blocked Outputs", ""])
    for item in report["blocked_outputs"]:
        lines.append(f"- `{item}`")

    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Report the G10-1 I5B dictionary final cleanup state.")
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
