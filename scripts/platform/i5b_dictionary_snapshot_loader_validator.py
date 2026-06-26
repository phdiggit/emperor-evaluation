from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import i5b_rule_display_dictionary_contract as contract  # noqa: E402
from scripts.platform.core.fingerprints import file_sha256, stable_json_sha256  # noqa: E402


PACKAGE_VERSION = "i5b-dictionary-snapshot-loader-validator-v1"
SNAPSHOT_VERSION = "i5b-rule-display-dictionary-snapshot-v1"
DEFAULT_SNAPSHOT_PATH = (
    ROOT / "scripts" / "platform" / "i5b_dictionary_snapshots" / "i5b_rule_display_dictionary_snapshot_v1.json"
)
ROADMAP_ISSUE = contract.ROADMAP_ISSUE
EPIC_ISSUE = contract.EPIC_ISSUE
TECH_DEBT_ISSUE = contract.TECH_DEBT_ISSUE
CONTRACT_PACKAGE_VERSION = contract.PACKAGE_VERSION
CONTRACT_PR = 320
CONTRACT_MERGE_COMMIT = "30a45414931440c5235d0f339e0f9d6ab9b09025"
SUPPORTED_MODES = ("snapshot-report", "validate-snapshot", "snapshot-md")
ALLOWED_STATUSES = {"active", "deprecated", "draft"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _inventory_by_symbol() -> dict[str, dict[str, Any]]:
    return {str(item["symbol"]): dict(item) for item in contract.HARD_CODED_INVENTORY}


def _dictionary_types() -> set[str]:
    return {str(item["dictionary_type"]) for item in contract.HARD_CODED_INVENTORY}


def load_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_snapshot(snapshot: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if snapshot.get("package_version") != PACKAGE_VERSION:
        errors.append("snapshot.package_version_mismatch")
    if snapshot.get("snapshot_version") != SNAPSHOT_VERSION:
        errors.append("snapshot.snapshot_version_mismatch")
    if snapshot.get("contract_package_version") != CONTRACT_PACKAGE_VERSION:
        errors.append("snapshot.contract_package_version_mismatch")
    if snapshot.get("scope") != "i5b_people_delegation":
        errors.append("snapshot.scope_mismatch")
    if not snapshot.get("gate_source"):
        errors.append("snapshot.gate_source_missing")
    if snapshot.get("status") not in ALLOWED_STATUSES:
        errors.append("snapshot.status_invalid")

    items = snapshot.get("items")
    if not isinstance(items, list) or not items:
        errors.append("snapshot.items_missing")
        return errors

    errors.extend(_validate_items(items))
    errors.extend(_validate_inventory_coverage(items))
    return errors


def _validate_items(items: Sequence[object]) -> list[str]:
    errors: list[str] = []
    seen_keys: set[tuple[str, str, str]] = set()
    dictionary_types = _dictionary_types()
    for index, item in enumerate(items):
        path = f"items[{index}]"
        if not isinstance(item, Mapping):
            errors.append(f"{path}.not_object")
            continue

        missing = [field for field in contract.SNAPSHOT_SCHEMA_REQUIRED_FIELDS if field not in item]
        for field in missing:
            errors.append(f"{path}.{field}_missing")

        scope = str(item.get("scope", ""))
        rule_id = str(item.get("rule_id", ""))
        locale = str(item.get("locale", ""))
        key = (scope, rule_id, locale)
        if key in seen_keys:
            errors.append(f"{path}.rule_id_duplicate")
        seen_keys.add(key)

        if item.get("snapshot_version") != SNAPSHOT_VERSION:
            errors.append(f"{path}.snapshot_version_mismatch")
        if not scope:
            errors.append(f"{path}.scope_missing")
        if not rule_id:
            errors.append(f"{path}.rule_id_missing")
        if item.get("dictionary_type") not in dictionary_types:
            errors.append(f"{path}.dictionary_type_unknown")
        if not locale:
            errors.append(f"{path}.locale_missing")
        if item.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{path}.status_invalid")
        if not DATE_RE.fullmatch(str(item.get("effective_from", ""))):
            errors.append(f"{path}.effective_from_invalid")
        if not item.get("gate_source"):
            errors.append(f"{path}.gate_source_missing")

        digest = str(item.get("digest_sha256", ""))
        payload = item.get("payload")
        if not SHA256_RE.fullmatch(digest):
            errors.append(f"{path}.digest_sha256_invalid")
        if not isinstance(payload, Mapping):
            errors.append(f"{path}.payload_missing")
            continue
        if digest and digest != stable_json_sha256(payload):
            errors.append(f"{path}.digest_sha256_mismatch")
        if payload.get("algorithm_runtime_migrated") is not False:
            errors.append(f"{path}.algorithm_runtime_migrated_must_remain_false")
        if payload.get("contains_release_scores") is not False:
            errors.append(f"{path}.contains_release_scores_must_remain_false")
    return errors


def _validate_inventory_coverage(items: Sequence[object]) -> list[str]:
    errors: list[str] = []
    inventory = _inventory_by_symbol()
    covered: dict[str, str] = {}
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            continue
        dictionary_type = str(item.get("dictionary_type", ""))
        payload = item.get("payload")
        if not isinstance(payload, Mapping):
            continue
        source_symbols = payload.get("source_symbols")
        if not isinstance(source_symbols, list) or not source_symbols:
            errors.append(f"items[{index}].payload.source_symbols_missing")
            continue
        for symbol in source_symbols:
            symbol_name = str(symbol)
            if symbol_name in covered:
                errors.append(f"items[{index}].payload.source_symbols_duplicate:{symbol_name}")
            covered[symbol_name] = dictionary_type
            expected = inventory.get(symbol_name)
            if expected is None:
                errors.append(f"items[{index}].payload.source_symbols_unknown:{symbol_name}")
                continue
            if expected["dictionary_type"] != dictionary_type:
                errors.append(f"items[{index}].payload.dictionary_type_mismatch:{symbol_name}")

    expected_symbols = set(inventory)
    covered_symbols = set(covered)
    for symbol in sorted(expected_symbols - covered_symbols):
        errors.append(f"inventory.symbol_missing:{symbol}")
    for symbol in sorted(covered_symbols - expected_symbols):
        errors.append(f"inventory.symbol_extra:{symbol}")
    return errors


def build_snapshot_report(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, Any]:
    snapshot = load_snapshot(path)
    errors = validate_snapshot(snapshot)
    items = snapshot.get("items", [])
    item_digests = {
        str(item["rule_id"]): str(item["digest_sha256"])
        for item in items
        if isinstance(item, Mapping) and "rule_id" in item and "digest_sha256" in item
    }
    inventory_symbols = sorted(_inventory_by_symbol())
    covered_symbols = sorted(
        {
            str(symbol)
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("payload"), Mapping)
            for symbol in item["payload"].get("source_symbols", [])
        }
    )
    return {
        "mode": "snapshot-report",
        "package_version": PACKAGE_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "tech_debt_issue": TECH_DEBT_ISSUE,
        "contract_pr": CONTRACT_PR,
        "contract_merge_commit": CONTRACT_MERGE_COMMIT,
        "snapshot_path": _relative(path) if path.is_relative_to(ROOT) else str(path),
        "snapshot_file_sha256": file_sha256(path),
        "snapshot_version": snapshot.get("snapshot_version"),
        "snapshot_item_count": len(items) if isinstance(items, list) else 0,
        "validated": not errors,
        "validation_errors": errors,
        "inventory_symbol_count": len(inventory_symbols),
        "covered_inventory_symbol_count": len(covered_symbols),
        "inventory_symbols": inventory_symbols,
        "covered_inventory_symbols": covered_symbols,
        "item_digests": item_digests,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
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
            "current_phase": "issue311_i5b_dictionary_snapshot_loader_validator_ready",
            "active_epic": EPIC_ISSUE,
            "active_tech_debt": TECH_DEBT_ISSUE,
            "issue311_dictionary_contract_ready": True,
            "issue311_dictionary_snapshot_loader_validator_ready": True,
            "immutable_repo_snapshot_loaded": True,
            "snapshot_digest_validation_passed": not errors,
            "hardcoded_inventory_symbols_covered": covered_symbols == inventory_symbols,
            "runtime_adapter_migrated": False,
            "postgres_dictionary_tables_created": False,
            "canonical_dictionary_write_performed": False,
            "ordinary_exports_require_live_dsn": False,
            "g10_destructive_cleanup_entered": False,
        },
        "blocked_outputs": list(snapshot.get("blocked_outputs", [])),
        "next_required_work": snapshot.get("next_required_work"),
    }


def render_snapshot_md(path: Path = DEFAULT_SNAPSHOT_PATH) -> str:
    report = build_snapshot_report(path)
    lines = [
        "# I5B Dictionary Snapshot Loader Validator",
        "",
        f"- package_version: `{report['package_version']}`",
        f"- roadmap_issue: `#{report['roadmap_issue']}`",
        f"- epic_issue: `#{report['epic_issue']}`",
        f"- tech_debt_issue: `#{report['tech_debt_issue']}`",
        f"- snapshot_path: `{report['snapshot_path']}`",
        f"- snapshot_file_sha256: `{report['snapshot_file_sha256']}`",
        f"- validated: `{str(report['validated']).lower()}`",
        f"- snapshot_item_count: `{report['snapshot_item_count']}`",
        f"- covered_inventory_symbol_count: `{report['covered_inventory_symbol_count']}`",
        "",
        "## Item Digests",
        "",
    ]
    for rule_id, digest in sorted(report["item_digests"].items()):
        lines.append(f"- `{rule_id}`: `{digest}`")

    lines.extend(["", "## Blocked Outputs", ""])
    for item in report["blocked_outputs"]:
        lines.append(f"- `{item}`")

    lines.append("")
    return "\n".join(lines)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def clone_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(snapshot))


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Load and validate the I5B rule/display dictionary snapshot.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--snapshot-report", action="store_true")
    mode.add_argument("--validate-snapshot", action="store_true")
    mode.add_argument("--snapshot-md", action="store_true")
    parser.add_argument("--snapshot-path", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    args = parser.parse_args(argv)

    if args.snapshot_md:
        sys.stdout.write(render_snapshot_md(args.snapshot_path))
        return 0

    report = build_snapshot_report(args.snapshot_path)
    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    if args.validate_snapshot and not report["validated"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
