from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "configs" / "人工复核配置" / "第五项B_证据簇裁判提示.json"
I5B_SUBITEM = "第五项B"
STRING_ARRAY_FIELDS = {
    "trigger_terms",
    "polarity_scope",
    "evidence_strength_scope",
    "adjacent_item_risk",
}
REQUIRED_STRING_FIELDS = {
    "rule_id",
    "trigger_type",
    "warning_type",
    "warning_message",
    "note",
}
FORBIDDEN_RESULT_FIELDS = {
    "formal_score",
    "ranking",
    "final_score",
    "definitive_band",
    "final_band",
    "leaderboard",
    "auto_publish",
    "formal_result",
    "person_final_band",
    "person_final_score",
    "score",
    "rank",
}
FIRST_PHASE_FORBIDDEN_FIELDS = {
    "person",
    "cluster_id",
    "evidence_id",
    "linked_evidence_ids",
    "auto_band_direction",
    "candidate_strength",
    "net_adjudication_draft",
}
UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")
ENABLED_RULE_ERROR = "第一阶段不允许启用证据簇裁判提示规则；只能保留 skeleton。"


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


def is_non_empty_string_array(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(is_non_empty_string(item) for item in value)


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

    if not path.exists():
        return rows, [f"{path}: file does not exist"]

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


def validate_row(path: Path, line_number: int, row: dict[str, object]) -> list[str]:
    errors: list[str] = []
    line_label = f"{path}: line {line_number}"

    for field in sorted(FORBIDDEN_RESULT_FIELDS):
        if field in row:
            errors.append(f"{line_label}: forbidden result field is not allowed in skeleton config: {field}")

    for field in sorted(FIRST_PHASE_FORBIDDEN_FIELDS):
        if field in row:
            errors.append(f"{line_label}: first-phase skeleton must not bind concrete adjudication data field: {field}")

    for field in sorted(REQUIRED_STRING_FIELDS):
        if not is_non_empty_string(row.get(field)):
            errors.append(f"{line_label}: {field} must be a non-empty string")

    if row.get("subitem") != I5B_SUBITEM:
        errors.append(f"{line_label}: subitem must be {I5B_SUBITEM!r}")

    if not isinstance(row.get("required_human_review"), bool):
        errors.append(f"{line_label}: required_human_review must be a bool")

    if "enabled" in row and not isinstance(row.get("enabled"), bool):
        errors.append(f"{line_label}: enabled must be a bool")
    if row.get("enabled") is True:
        errors.append(f"{line_label}: {ENABLED_RULE_ERROR}")

    for field in sorted(STRING_ARRAY_FIELDS):
        if field in row and not is_non_empty_string_array(row[field]):
            errors.append(f"{line_label}: {field} must be a non-empty list of non-empty strings")

    return errors


def validate_unique_rule_ids(path: Path, rows: list[tuple[int, dict[str, object]]]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, int] = {}

    for line_number, row in rows:
        rule_id = row.get("rule_id")
        if not is_non_empty_string(rule_id):
            continue
        normalized = rule_id.strip()
        if normalized in seen:
            errors.append(f"{path}: line {line_number}: duplicate rule_id {normalized!r} (already defined at line {seen[normalized]})")
        else:
            seen[normalized] = line_number

    return errors


def validate(path: Path = CONFIG_PATH) -> list[str]:
    rows, errors = load_json_array_objects(path)
    for line_number, row in rows:
        errors.extend(validate_row(path, line_number, row))
    errors.extend(validate_unique_rule_ids(path, rows))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("I5B cluster adjudication config validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
