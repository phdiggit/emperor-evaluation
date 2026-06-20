from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_CONFIG_DIR = ROOT / "data" / "configs" / "人工复核配置"
TERMS_FIELD_NAMES = {
    "terms",
    "positive_terms",
    "negative_terms",
    "reversal_terms",
    "include_terms",
    "exclude_terms",
    "suppress_terms",
    "append_terms",
    "replace_terms",
    "source_scopes",
}
KEY_FIELD_NAMES = {
    "profile_id",
    "keyword_profile_id",
    "override_id",
    "scope",
    "scope_type",
    "scope_key",
    "person",
    "subitem",
}
UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")


def is_cjk_readability_escape(codepoint: int) -> bool:
    return (
        0x3000 <= codepoint <= 0x303F
        or 0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0xFF00 <= codepoint <= 0xFFEF
    )


def is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(is_non_empty_string(item) for item in value)


def infer_array_object_line_numbers(text: str, count: int) -> list[int]:
    line_numbers: list[int] = []
    line_number = 1
    depth = 0
    in_string = False
    escaping = False

    for char in text:
        if char == "\n":
            line_number += 1

        if in_string:
            if escaping:
                escaping = False
            elif char == "\\":
                escaping = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "[":
            depth += 1
            continue

        if char == "{":
            depth += 1
            if depth == 2:
                line_numbers.append(line_number)
            continue

        if char in "}]":
            depth = max(depth - 1, 0)

    if len(line_numbers) != count:
        return list(range(1, count + 1))

    return line_numbers


def validate_unicode_readability(path: Path, raw_text: str) -> list[str]:
    errors: list[str] = []
    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        for match in UNICODE_ESCAPE_PATTERN.finditer(raw_line):
            codepoint = int(match.group(1), 16)
            if is_cjk_readability_escape(codepoint):
                errors.append(
                    f"{path}: line {line_number}: found escaped CJK unicode sequence {match.group(0)!r}; "
                    "user-editable config must use UTF-8 Chinese text directly"
                )
                break
    return errors


def load_json_array_objects(path: Path) -> tuple[list[tuple[int, dict[str, object]]], list[str]]:
    rows: list[tuple[int, dict[str, object]]] = []
    errors: list[str] = []
    raw_text = path.read_text(encoding="utf-8")
    errors.extend(validate_unicode_readability(path, raw_text))

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: line {exc.lineno}: invalid JSON ({exc.msg})")
        return rows, errors

    if not isinstance(payload, list):
        errors.append(f"{path}: line 1: expected top-level JSON array, got {type(payload).__name__}")
        return rows, errors

    line_numbers = infer_array_object_line_numbers(raw_text, len(payload))
    for index, row in enumerate(payload):
        line_number = line_numbers[index]
        if not isinstance(row, dict):
            errors.append(f"{path}: line {line_number}: expected array item to be JSON object, got {type(row).__name__}")
            continue
        rows.append((line_number, row))

    return rows, errors


def validate_row_fields(path: Path, line_number: int, row: dict[str, object]) -> list[str]:
    errors: list[str] = []
    line_label = f"{path}: line {line_number}"

    for field in KEY_FIELD_NAMES:
        if field in row and not is_non_empty_string(row[field]):
            errors.append(f"{line_label}: {field} must be a non-empty string")

    for field in TERMS_FIELD_NAMES:
        if field in row and not is_string_list(row[field]):
            errors.append(f"{line_label}: {field} must be a list of non-empty strings")

    has_terms = any(field in row for field in TERMS_FIELD_NAMES)
    has_scope = any(field in row for field in ["profile_id", "keyword_profile_id", "scope", "scope_key", "person", "subitem"])
    if not has_terms:
        errors.append(f"{line_label}: must include at least one terms/source_scopes field")
    if not has_scope:
        errors.append(f"{line_label}: must include at least one profile/scope/person/subitem field")

    return errors


def validate_unique_ids(path: Path, rows: list[tuple[int, dict[str, object]]]) -> list[str]:
    errors: list[str] = []
    seen: dict[tuple[str, str], int] = {}

    for line_number, row in rows:
        for field, value in row.items():
            if not field.endswith("_id") or not is_non_empty_string(value):
                continue
            key = (field, value.strip())
            if key in seen:
                errors.append(f"{path}: line {line_number}: duplicate {field} {value!r} (already defined at line {seen[key]})")
            else:
                seen[key] = line_number

    return errors


def validate_file(path: Path) -> list[str]:
    rows, errors = load_json_array_objects(path)
    for line_number, row in rows:
        errors.extend(validate_row_fields(path, line_number, row))
    errors.extend(validate_unique_ids(path, rows))
    return errors


def validate() -> list[str]:
    errors: list[str] = []

    if not REVIEW_CONFIG_DIR.exists():
        return errors

    for path in sorted(REVIEW_CONFIG_DIR.glob("*.json")):
        errors.extend(validate_file(path))

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
