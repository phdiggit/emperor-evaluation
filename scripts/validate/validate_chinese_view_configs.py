from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHINESE_VIEW_CONFIG_DIR = ROOT / "data" / "configs" / "视图配置"
PERSON_POOL_PATH = CHINESE_VIEW_CONFIG_DIR / "第五项B_人物池.json"
VIEW_GROUPS_PATH = CHINESE_VIEW_CONFIG_DIR / "第五项B_视图分组.json"
PERSON_POOL_REQUIRED_FIELDS = ["person", "subitem"]
VIEW_GROUP_REQUIRED_FIELDS = ["group_id", "group_name", "group_type", "subitem", "persons", "note"]
REQUIRED_VIEW_GROUP_IDS = [
    "第五项B_三人试点",
    "第五项B_扩展第一批",
    "第五项B_净证据导出目标",
]
NET_EVIDENCE_GROUP_ID = "第五项B_净证据导出目标"
NET_EVIDENCE_PATH_TEMPLATE = (
    "exports/markdown_views/第五项B/人工审核/证据链/净证据池/"
    "第五项B_{person}人工审核净证据池.md"
)


def is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_string_list(value: object, *, allow_empty: bool) -> bool:
    if not isinstance(value, list):
        return False
    if not allow_empty and not value:
        return False
    return all(is_non_empty_string(item) for item in value)


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


def load_json_array_objects(path: Path) -> tuple[list[tuple[int, dict[str, object]]], list[str]]:
    rows: list[tuple[int, dict[str, object]]] = []
    errors: list[str] = []

    if not path.exists():
        return rows, [f"{path}: line 1: required file is missing"]

    raw_text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: line {exc.lineno}: invalid JSON ({exc.msg})")
        return rows, errors

    if not isinstance(payload, list):
        return rows, [f"{path}: line 1: expected top-level JSON array, got {type(payload).__name__}"]

    line_numbers = infer_array_object_line_numbers(raw_text, len(payload))
    for index, row in enumerate(payload):
        line_number = line_numbers[index]
        if not isinstance(row, dict):
            errors.append(f"{path}: line {line_number}: expected array item to be JSON object, got {type(row).__name__}")
            continue
        rows.append((line_number, row))

    return rows, errors


def validate_person_pool(
    rows: list[tuple[int, dict[str, object]]],
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    persons: dict[str, int] = {}

    for line_number, row in rows:
        line_label = f"{PERSON_POOL_PATH}: line {line_number}"
        missing_fields = [field for field in PERSON_POOL_REQUIRED_FIELDS if field not in row]
        if missing_fields:
            errors.append(f"{line_label}: missing required fields: {', '.join(missing_fields)}")

        for field in ["person", "subitem"]:
            if field in row and not is_non_empty_string(row[field]):
                errors.append(f"{line_label}: {field} must be a non-empty string")

        if "recommended_priority" in row and not is_non_empty_string(row["recommended_priority"]):
            errors.append(f"{line_label}: recommended_priority must be a non-empty string")

        if "note" in row and not is_non_empty_string(row["note"]):
            errors.append(f"{line_label}: note must be a non-empty string")

        person = row.get("person")
        if isinstance(person, str) and person.strip():
            normalized = person.strip()
            if normalized in persons:
                errors.append(
                    f"{line_label}: duplicate person {normalized!r} (already defined at line {persons[normalized]})"
                )
            else:
                persons[normalized] = line_number

    return errors, persons


def validate_view_groups(
    rows: list[tuple[int, dict[str, object]]],
    person_pool: dict[str, int],
) -> tuple[list[str], dict[str, tuple[int, dict[str, object]]]]:
    errors: list[str] = []
    groups: dict[str, tuple[int, dict[str, object]]] = {}

    for line_number, row in rows:
        line_label = f"{VIEW_GROUPS_PATH}: line {line_number}"
        missing_fields = [field for field in VIEW_GROUP_REQUIRED_FIELDS if field not in row]
        if missing_fields:
            errors.append(f"{line_label}: missing required fields: {', '.join(missing_fields)}")

        for field in ["group_id", "group_name", "group_type", "subitem", "note"]:
            if field in row and not is_non_empty_string(row[field]):
                errors.append(f"{line_label}: {field} must be a non-empty string")

        persons = row.get("persons")
        if "persons" in row and not is_string_list(persons, allow_empty=False):
            errors.append(f"{line_label}: persons must be a non-empty list of non-empty strings")
        elif isinstance(persons, list):
            for person in persons:
                if isinstance(person, str) and person.strip() and person.strip() not in person_pool:
                    errors.append(
                        f"{line_label}: person {person.strip()!r} is not defined in {PERSON_POOL_PATH.name}"
                    )

        if "path_template" in row and not is_non_empty_string(row["path_template"]):
            errors.append(f"{line_label}: path_template must be a non-empty string")

        group_id = row.get("group_id")
        if isinstance(group_id, str) and group_id.strip():
            normalized = group_id.strip()
            if normalized in groups:
                existing_line = groups[normalized][0]
                errors.append(
                    f"{line_label}: duplicate group_id {normalized!r} (already defined at line {existing_line})"
                )
            else:
                groups[normalized] = (line_number, row)

    return errors, groups


def group_person_set(groups: dict[str, tuple[int, dict[str, object]]], group_id: str) -> set[str] | None:
    entry = groups.get(group_id)
    if entry is None:
        return None
    persons = entry[1].get("persons")
    if not isinstance(persons, list):
        return None
    return {person.strip() for person in persons if isinstance(person, str) and person.strip()}


def validate_required_view_groups(
    groups: dict[str, tuple[int, dict[str, object]]],
) -> list[str]:
    errors: list[str] = []
    for group_id in REQUIRED_VIEW_GROUP_IDS:
        group_set = group_person_set(groups, group_id)
        if group_set is None:
            errors.append(f"{VIEW_GROUPS_PATH}: line 1: required group_id {group_id!r} is missing or invalid")

    net_group = groups.get(NET_EVIDENCE_GROUP_ID)
    if net_group is not None:
        line_number, row = net_group
        path_template = row.get("path_template")
        if path_template != NET_EVIDENCE_PATH_TEMPLATE:
            errors.append(
                f"{VIEW_GROUPS_PATH}: line {line_number}: path_template for {NET_EVIDENCE_GROUP_ID!r} "
                f"must be {NET_EVIDENCE_PATH_TEMPLATE!r}"
            )

    return errors


def validate() -> list[str]:
    errors: list[str] = []

    person_rows, person_load_errors = load_json_array_objects(PERSON_POOL_PATH)
    group_rows, group_load_errors = load_json_array_objects(VIEW_GROUPS_PATH)
    errors.extend(person_load_errors)
    errors.extend(group_load_errors)

    person_errors, person_pool = validate_person_pool(person_rows)
    group_errors, groups = validate_view_groups(group_rows, person_pool)
    errors.extend(person_errors)
    errors.extend(group_errors)

    errors.extend(validate_required_view_groups(groups))

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("Chinese view config validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
