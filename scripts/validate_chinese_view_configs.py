from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHINESE_VIEW_CONFIG_DIR = ROOT / "data" / "configs" / "视图配置"
PERSON_POOL_PATH = CHINESE_VIEW_CONFIG_DIR / "第五项B_人物池.jsonl"
VIEW_GROUPS_PATH = CHINESE_VIEW_CONFIG_DIR / "第五项B_视图分组.jsonl"
LEGACY_TRIAL_TARGETS_PATH = ROOT / "data" / "view_configs" / "i5b_trial_targets.jsonl"
LEGACY_EXPANDED_BATCH1_PATH = ROOT / "data" / "view_configs" / "i5b_expanded_batch1_targets.jsonl"
LEGACY_NET_EVIDENCE_TARGETS_PATH = ROOT / "data" / "view_configs" / "i5b_net_evidence_targets.jsonl"
LEGACY_TRIAL_CONFIG_JSON_PATH = ROOT / "configs" / "i5b_trial_targets.json"
PERSON_POOL_REQUIRED_FIELDS = ["person", "subitem"]
VIEW_GROUP_REQUIRED_FIELDS = ["group_id", "group_name", "group_type", "subitem", "persons", "note"]


def is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_string_list(value: object, *, allow_empty: bool) -> bool:
    if not isinstance(value, list):
        return False
    if not allow_empty and not value:
        return False
    return all(is_non_empty_string(item) for item in value)


def load_jsonl_objects(path: Path) -> tuple[list[tuple[int, dict[str, object]]], list[str]]:
    rows: list[tuple[int, dict[str, object]]] = []
    errors: list[str] = []

    if not path.exists():
        return rows, [f"{path}: line 1: required file is missing"]

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


def load_legacy_persons_from_jsonl(path: Path) -> tuple[list[tuple[int, str]], list[str]]:
    rows, errors = load_jsonl_objects(path)
    persons: list[tuple[int, str]] = []

    for line_number, row in rows:
        person = row.get("person")
        if not is_non_empty_string(person):
            errors.append(f"{path}: line {line_number}: person must be a non-empty string")
            continue
        persons.append((line_number, person.strip()))

    return persons, errors


def load_legacy_trial_json(path: Path) -> tuple[list[str], list[str]]:
    if not path.exists():
        return [], [f"{path}: line 1: required file is missing"]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"{path}: line 1: invalid JSON ({exc.msg})"]

    if not isinstance(payload, dict):
        return [], [f"{path}: line 1: expected JSON object, got {type(payload).__name__}"]

    targets = payload.get("targets")
    if not is_string_list(targets, allow_empty=False):
        return [], [f"{path}: line 1: targets must be a non-empty list of non-empty strings"]

    return [target.strip() for target in targets], []


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

        if "legacy_sources" in row and not is_string_list(row["legacy_sources"], allow_empty=False):
            errors.append(f"{line_label}: legacy_sources must be a non-empty list of non-empty strings")

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


def validate_group_coverage(
    groups: dict[str, tuple[int, dict[str, object]]],
    legacy_people: list[tuple[int, str]],
    expected_group_id: str,
    legacy_path: Path,
) -> list[str]:
    errors: list[str] = []
    group_set = group_person_set(groups, expected_group_id)
    if group_set is None:
        errors.append(f"{VIEW_GROUPS_PATH}: line 1: required group_id {expected_group_id!r} is missing or invalid")
        return errors

    group_line = groups[expected_group_id][0]
    legacy_set = {person for _, person in legacy_people}

    for line_number, person in legacy_people:
        if person not in group_set:
            errors.append(
                f"{legacy_path}: line {line_number}: person {person!r} is missing from group {expected_group_id!r} in {VIEW_GROUPS_PATH.name}"
            )

    for person in sorted(group_set - legacy_set):
        errors.append(
            f"{VIEW_GROUPS_PATH}: line {group_line}: person {person!r} is not present in legacy source {legacy_path.name} for group {expected_group_id!r}"
        )

    return errors


def validate_pool_covers_legacy_sources(
    person_pool: dict[str, int],
    legacy_people: list[tuple[int, str]],
    legacy_path: Path,
) -> list[str]:
    errors: list[str] = []
    for line_number, person in legacy_people:
        if person not in person_pool:
            errors.append(
                f"{legacy_path}: line {line_number}: person {person!r} is missing from {PERSON_POOL_PATH.name}"
            )
    return errors


def validate() -> list[str]:
    errors: list[str] = []

    person_rows, person_load_errors = load_jsonl_objects(PERSON_POOL_PATH)
    group_rows, group_load_errors = load_jsonl_objects(VIEW_GROUPS_PATH)
    errors.extend(person_load_errors)
    errors.extend(group_load_errors)

    person_errors, person_pool = validate_person_pool(person_rows)
    group_errors, groups = validate_view_groups(group_rows, person_pool)
    errors.extend(person_errors)
    errors.extend(group_errors)

    legacy_trial_people, legacy_trial_errors = load_legacy_persons_from_jsonl(LEGACY_TRIAL_TARGETS_PATH)
    legacy_expanded_people, legacy_expanded_errors = load_legacy_persons_from_jsonl(LEGACY_EXPANDED_BATCH1_PATH)
    legacy_net_people, legacy_net_errors = load_legacy_persons_from_jsonl(LEGACY_NET_EVIDENCE_TARGETS_PATH)
    legacy_trial_json_targets, legacy_trial_json_errors = load_legacy_trial_json(LEGACY_TRIAL_CONFIG_JSON_PATH)
    errors.extend(legacy_trial_errors)
    errors.extend(legacy_expanded_errors)
    errors.extend(legacy_net_errors)
    errors.extend(legacy_trial_json_errors)

    errors.extend(validate_pool_covers_legacy_sources(person_pool, legacy_trial_people, LEGACY_TRIAL_TARGETS_PATH))
    errors.extend(validate_pool_covers_legacy_sources(person_pool, legacy_expanded_people, LEGACY_EXPANDED_BATCH1_PATH))
    errors.extend(validate_pool_covers_legacy_sources(person_pool, legacy_net_people, LEGACY_NET_EVIDENCE_TARGETS_PATH))
    for index, person in enumerate(legacy_trial_json_targets, start=1):
        if person not in person_pool:
            errors.append(f"{LEGACY_TRIAL_CONFIG_JSON_PATH}: line {index}: person {person!r} is missing from {PERSON_POOL_PATH.name}")

    errors.extend(
        validate_group_coverage(groups, legacy_trial_people, "第五项B_三人试点", LEGACY_TRIAL_TARGETS_PATH)
    )
    errors.extend(
        validate_group_coverage(groups, legacy_expanded_people, "第五项B_扩展第一批", LEGACY_EXPANDED_BATCH1_PATH)
    )
    errors.extend(
        validate_group_coverage(groups, legacy_net_people, "第五项B_净证据导出目标", LEGACY_NET_EVIDENCE_TARGETS_PATH)
    )

    trial_group_set = group_person_set(groups, "第五项B_三人试点")
    if trial_group_set is not None:
        legacy_trial_json_set = set(legacy_trial_json_targets)
        for index, person in enumerate(legacy_trial_json_targets, start=1):
            if person not in trial_group_set:
                errors.append(
                    f"{LEGACY_TRIAL_CONFIG_JSON_PATH}: line {index}: person {person!r} is missing from group '第五项B_三人试点' in {VIEW_GROUPS_PATH.name}"
                )
        group_line = groups["第五项B_三人试点"][0] if "第五项B_三人试点" in groups else 1
        for person in sorted(trial_group_set - legacy_trial_json_set):
            errors.append(
                f"{VIEW_GROUPS_PATH}: line {group_line}: person {person!r} is not present in legacy source {LEGACY_TRIAL_CONFIG_JSON_PATH.name} for group '第五项B_三人试点'"
            )

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
