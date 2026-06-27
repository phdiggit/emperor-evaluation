from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_cleanup_inventory_plan as inventory_plan  # noqa: E402
from scripts.platform import g10_script_asset_risk_governance as governance  # noqa: E402


GUARD_VERSION = "script-lifecycle-registry-guard-v1"
SCRIPT_GOVERNANCE_ENFORCEMENT_ISSUE = 342
ROADMAP_ISSUE = 287
EPIC_ISSUE = 312
SUPPORTED_MODES = ("guard-report",)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _duplicate_review_problem(review: Mapping[str, Any]) -> str | None:
    module_count = int(review.get("module_count", 0))
    if module_count <= 1:
        return None
    reason = str(review.get("retain_or_consolidation_reason") or "").strip()
    plan = str(review.get("governance_plan") or "").strip()
    if reason or plan:
        return None
    return (
        f"duplicate capability group {review.get('group_id', '<unknown>')}: "
        "module_count > 1 requires retain_or_consolidation_reason or governance_plan"
    )


def validate_registry_lifecycle(
    registry: Mapping[str, Any],
    default_route_sources: Mapping[str, str] | None = None,
    duplicate_reviews: Sequence[Mapping[str, Any]] | None = None,
) -> list[str]:
    if default_route_sources is None:
        default_route_sources = governance._load_default_route_sources()
    analysis = governance.analyze_scripts_registry(registry, default_route_sources)
    reviews = list(duplicate_reviews) if duplicate_reviews is not None else analysis["duplicate_capability_review"]
    errors: list[str] = []

    for path in analysis["transitional_scripts_without_sunset"]:
        errors.append(f"{path}: transitional lifecycle_status requires sunset_milestone")

    for path in analysis["retired_public_cli_modules"]:
        errors.append(f"{path}: retired lifecycle_status must not be public_cli_stable")

    for item in analysis["default_validate_retired_script_references"]:
        errors.append(
            f"{item['entrypoint']}: retired script route reference is forbidden: {item['retired_path']}"
        )

    for review in reviews:
        problem = _duplicate_review_problem(review)
        if problem:
            errors.append(problem)

    return sorted(errors)


def build_guard_report(
    registry: Mapping[str, Any] | None = None,
    default_route_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    registry = registry or _load_json(inventory_plan.SCRIPT_REGISTRY_PATH)
    if default_route_sources is None:
        default_route_sources = governance._load_default_route_sources()
    analysis = governance.analyze_scripts_registry(registry, default_route_sources)
    errors = validate_registry_lifecycle(registry, default_route_sources)
    duplicate_reviews = analysis["duplicate_capability_review"]
    duplicate_exception_count = sum(1 for item in duplicate_reviews if int(item["module_count"]) > 1)

    return {
        "mode": "guard-report",
        "guard_version": GUARD_VERSION,
        "roadmap_issue": ROADMAP_ISSUE,
        "epic_issue": EPIC_ISSUE,
        "script_governance_enforcement_issue": SCRIPT_GOVERNANCE_ENFORCEMENT_ISSUE,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "does_not_read_dotenv": True,
        "does_not_connect_database": True,
        "does_not_connect_rabbitmq": True,
        "does_not_access_network": True,
        "does_not_read_canonical_jsonl": True,
        "does_not_read_batch_payloads": True,
        "does_not_read_generated_exports": True,
        "does_not_touch_data_archive_export_roots": True,
        "current_state": {
            "registry_lifecycle_guard_ready": not errors,
            "transitional_scripts_without_sunset": analysis["transitional_scripts_without_sunset_count"],
            "retired_scripts_in_default_validate_or_public_cli": analysis[
                "retired_scripts_in_default_validate_or_public_cli"
            ],
            "duplicate_capability_groups_reviewed": analysis["duplicate_capability_group_count"],
            "duplicate_capability_exceptions_explicit": not any(
                _duplicate_review_problem(review) for review in duplicate_reviews
            ),
            "duplicate_capability_exception_count": duplicate_exception_count,
        },
        "default_route_entrypoints": sorted(default_route_sources),
        "scripts_registry_analysis": {
            "platform_lifecycle_status_counts": analysis["platform_lifecycle_status_counts"],
            "transitional_scripts_without_sunset": analysis["transitional_scripts_without_sunset"],
            "retired_public_cli_modules": analysis["retired_public_cli_modules"],
            "default_validate_retired_script_references": analysis[
                "default_validate_retired_script_references"
            ],
            "duplicate_capability_review": duplicate_reviews,
        },
        "errors": errors,
    }


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Validate scripts registry lifecycle governance rules.")
    parser.add_argument("--guard-report", action="store_true", help="print a structured guard report")
    args = parser.parse_args(argv)

    report = build_guard_report()
    if args.guard_report:
        sys.stdout.write(report_as_json(report))
        sys.stdout.write("\n")

    errors = report["errors"]
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    if not args.guard_report:
        print("Script lifecycle registry validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
