from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_CONFIG_DIR = ROOT / "data" / "review_configs"
SEARCH_KEYWORD_PROFILES_PATH = REVIEW_CONFIG_DIR / "search_keyword_profiles.jsonl"
SEARCH_KEYWORD_OVERRIDES_PATH = REVIEW_CONFIG_DIR / "search_keyword_overrides.jsonl"
PROFILE_REQUIRED_FIELDS = [
    "profile_id",
    "item",
    "subitem",
    "dimension",
    "polarity",
    "keyword_family",
    "terms",
    "purpose",
    "priority",
]
OVERRIDE_REQUIRED_FIELDS = [
    "override_id",
    "base_profile_id",
    "scope_type",
    "scope_key",
    "add_terms",
    "reason",
]
PRIORITY_PATTERN = re.compile(r"P\d+")
ALLOWED_POLARITIES = {"positive", "negative", "neutral", "mixed", "boundary"}
ALLOWED_KEYWORD_FAMILIES = {
    "positive_scan",
    "negative_scan",
    "boundary_scan",
    "adjacent_item_risk",
    "source_verification",
    "counter_evidence",
    "era_context",
}
ALLOWED_SCOPE_TYPES = {"era", "person", "source_family", "project_phase"}


def is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_string_list(value: object, *, allow_empty: bool) -> bool:
    if not isinstance(value, list):
        return False
    if not allow_empty and not value:
        return False
    return all(is_non_empty_string(item) for item in value)


def load_jsonl_rows(path: Path) -> tuple[list[tuple[int, dict[str, object]]], list[str]]:
    rows: list[tuple[int, dict[str, object]]] = []
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

        rows.append((line_number, row))

    return rows, errors


def validate_profiles(
    rows: list[tuple[int, dict[str, object]]],
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    profile_ids: dict[str, int] = {}

    for line_number, row in rows:
        line_label = f"{SEARCH_KEYWORD_PROFILES_PATH}: line {line_number}"
        missing_fields = [field for field in PROFILE_REQUIRED_FIELDS if field not in row]
        if missing_fields:
            errors.append(f"{line_label}: missing required fields: {', '.join(missing_fields)}")

        for field in [
            "profile_id",
            "item",
            "subitem",
            "dimension",
            "polarity",
            "keyword_family",
            "purpose",
            "priority",
        ]:
            if field in row and not is_non_empty_string(row[field]):
                errors.append(f"{line_label}: {field} must be a non-empty string")

        if "terms" in row and not is_string_list(row["terms"], allow_empty=False):
            errors.append(f"{line_label}: terms must be a non-empty list of non-empty strings")

        polarity = row.get("polarity")
        if isinstance(polarity, str) and polarity not in ALLOWED_POLARITIES:
            errors.append(
                f"{line_label}: polarity must be one of {sorted(ALLOWED_POLARITIES)}, got {polarity!r}"
            )

        keyword_family = row.get("keyword_family")
        if isinstance(keyword_family, str) and keyword_family not in ALLOWED_KEYWORD_FAMILIES:
            errors.append(
                f"{line_label}: keyword_family must be one of {sorted(ALLOWED_KEYWORD_FAMILIES)}, got {keyword_family!r}"
            )

        priority = row.get("priority")
        if isinstance(priority, str) and not PRIORITY_PATTERN.fullmatch(priority):
            errors.append(f"{line_label}: priority must match P<number>, got {priority!r}")

        profile_id = row.get("profile_id")
        if isinstance(profile_id, str) and profile_id.strip():
            if profile_id in profile_ids:
                errors.append(
                    f"{line_label}: duplicate profile_id {profile_id!r} (already defined at line {profile_ids[profile_id]})"
                )
            else:
                profile_ids[profile_id] = line_number

    return errors, profile_ids


def validate_overrides(
    rows: list[tuple[int, dict[str, object]]],
    profile_ids: dict[str, int],
) -> list[str]:
    errors: list[str] = []
    override_ids: dict[str, int] = {}

    for line_number, row in rows:
        line_label = f"{SEARCH_KEYWORD_OVERRIDES_PATH}: line {line_number}"
        missing_fields = [field for field in OVERRIDE_REQUIRED_FIELDS if field not in row]
        if missing_fields:
            errors.append(f"{line_label}: missing required fields: {', '.join(missing_fields)}")

        for field in ["override_id", "base_profile_id", "scope_type", "scope_key", "reason"]:
            if field in row and not is_non_empty_string(row[field]):
                errors.append(f"{line_label}: {field} must be a non-empty string")

        if "add_terms" in row and not is_string_list(row["add_terms"], allow_empty=True):
            errors.append(f"{line_label}: add_terms must be a list of non-empty strings")

        if "suppress_terms" in row and not is_string_list(row["suppress_terms"], allow_empty=True):
            errors.append(f"{line_label}: suppress_terms must be a list of non-empty strings")

        if "replace_terms" in row and not isinstance(row["replace_terms"], dict):
            errors.append(f"{line_label}: replace_terms must be an object")

        scope_type = row.get("scope_type")
        if isinstance(scope_type, str) and scope_type not in ALLOWED_SCOPE_TYPES:
            errors.append(
                f"{line_label}: scope_type must be one of {sorted(ALLOWED_SCOPE_TYPES)}, got {scope_type!r}"
            )

        override_id = row.get("override_id")
        if isinstance(override_id, str) and override_id.strip():
            if override_id in override_ids:
                errors.append(
                    f"{line_label}: duplicate override_id {override_id!r} (already defined at line {override_ids[override_id]})"
                )
            else:
                override_ids[override_id] = line_number

        base_profile_id = row.get("base_profile_id")
        if isinstance(base_profile_id, str) and base_profile_id.strip() and base_profile_id not in profile_ids:
            errors.append(
                f"{line_label}: base_profile_id {base_profile_id!r} does not exist in {SEARCH_KEYWORD_PROFILES_PATH.name}"
            )

    return errors


def validate() -> list[str]:
    errors: list[str] = []

    profile_rows, profile_load_errors = load_jsonl_rows(SEARCH_KEYWORD_PROFILES_PATH)
    override_rows, override_load_errors = load_jsonl_rows(SEARCH_KEYWORD_OVERRIDES_PATH)
    errors.extend(profile_load_errors)
    errors.extend(override_load_errors)

    profile_errors, profile_ids = validate_profiles(profile_rows)
    errors.extend(profile_errors)
    errors.extend(validate_overrides(override_rows, profile_ids))

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("Review config validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
