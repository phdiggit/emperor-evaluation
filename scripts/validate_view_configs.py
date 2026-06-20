from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEW_CONFIG_DIR = ROOT / "data" / "view_configs"
I5B_EXPANDED_CANDIDATE_POOL_PATH = VIEW_CONFIG_DIR / "i5b_expanded_candidate_pool.jsonl"
I5B_REQUIRED_FIELDS = [
    "person",
    "candidate_type",
    "why_selected",
    "expected_rule_pressure",
    "required_evidence_focus",
    "adjacent_item_risk",
    "negative_scan_focus",
    "recommended_priority",
]
RECOMMENDED_PRIORITY_PATTERN = re.compile(r"P\d+")


def validate_jsonl_file(path: Path) -> list[str]:
    errors: list[str] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue

        line_label = f"{path}: line {line_number}"
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            errors.append(f"{line_label}: invalid JSON ({exc.msg})")
            continue

        if not isinstance(row, dict):
            errors.append(f"{line_label}: expected JSON object, got {type(row).__name__}")
            continue

        if path == I5B_EXPANDED_CANDIDATE_POOL_PATH:
            missing_fields = [field for field in I5B_REQUIRED_FIELDS if field not in row]
            if missing_fields:
                errors.append(f"{line_label}: missing required fields: {', '.join(missing_fields)}")

            priority = row.get("recommended_priority")
            if priority is not None and not isinstance(priority, str):
                errors.append(f"{line_label}: recommended_priority must be a string in P<number> format")
            elif isinstance(priority, str) and not RECOMMENDED_PRIORITY_PATTERN.fullmatch(priority):
                errors.append(
                    f"{line_label}: recommended_priority must match P<number>, got {priority!r}"
                )

    return errors


def validate() -> list[str]:
    errors: list[str] = []

    for path in sorted(VIEW_CONFIG_DIR.glob("*.jsonl")):
        errors.extend(validate_jsonl_file(path))

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("View config validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
