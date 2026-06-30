from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from yaml.tokens import AliasToken, AnchorToken, DocumentStartToken, TagToken


ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG_PATH = ROOT / "data" / "configs" / "project_config.yml"
ALLOWED_TOP_LEVEL_KEYS = {"version", "timezone", "active_subitem", "default_person_group", "person_groups", "outputs"}
ALLOWED_TIMEZONES = {"Asia/Shanghai"}
ALLOWED_GROUP_KEYS = {"label", "persons", "persons_ref"}
PERSON_SOURCE_KEYS = {"persons", "persons_ref"}
ALLOWED_OUTPUT_KEYS = {
    "matrix",
    "auto_adjudication",
    "review_entry",
    "subitem_details",
    "net_evidence",
    "evidence_indexes",
}
ALLOWED_OUTPUT_DETAIL_KEYS = {"enabled", "person_group_override"}
FORBIDDEN_KEYS = {
    "i5b",
    "subitems",
    "groups",
    "defaults",
    "trial_group",
    "expanded_group",
    "net_evidence_group",
    "persons_from_group",
    "candidate_pool",
    "review_warning_rules",
    "candidate_type",
    "why_selected",
    "expected_rule_pressure",
    "required_evidence_focus",
    "adjacent_item_risk",
    "negative_scan_focus",
    "trigger_terms",
    "warning_message",
    "evidence_strength_scope",
    "polarity_scope",
    "path_template",
    "subitem",
    "note",
    "group_type",
}


def is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_non_empty_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(is_non_empty_string(item) for item in value)


def validate_yaml_surface(path: Path, raw_text: str) -> list[str]:
    errors: list[str] = []
    try:
        tokens = yaml.scan(raw_text)
        for token in tokens:
            line = token.start_mark.line + 1
            if isinstance(token, AnchorToken):
                errors.append(f"{path}: line {line}: YAML anchors are not allowed")
            elif isinstance(token, AliasToken):
                errors.append(f"{path}: line {line}: YAML aliases are not allowed")
            elif isinstance(token, TagToken):
                errors.append(f"{path}: line {line}: custom YAML tags are not allowed")
            elif isinstance(token, DocumentStartToken):
                errors.append(f"{path}: line {line}: explicit document markers are not allowed")
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML ({exc})")
    return errors


def validate_basic_subset(path: Path, value: object, label: str = "$") -> list[str]:
    errors: list[str] = []
    if value is None or isinstance(value, (str, int, float, bool)):
        return errors
    if isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(validate_basic_subset(path, item, f"{label}[{index}]"))
        return errors
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                errors.append(f"{path}: {label}: mapping keys must be strings")
                continue
            errors.extend(validate_basic_subset(path, item, f"{label}.{key}"))
        return errors
    errors.append(f"{path}: {label}: unsupported YAML value type {type(value).__name__}")
    return errors


def find_forbidden_keys(path: Path, value: object, label: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_label = f"{label}.{key}" if label != "$" else str(key)
            if isinstance(key, str) and key in FORBIDDEN_KEYS:
                errors.append(f"{path}: {child_label}: {key} is not allowed in project_config.yml")
            errors.extend(find_forbidden_keys(path, item, child_label))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(find_forbidden_keys(path, item, f"{label}[{index}]"))
    return errors


def validate_persons_ref(path: Path, persons_ref: str, label: str) -> list[str]:
    errors: list[str] = []
    ref_path = Path(persons_ref)
    allowed_root = Path("data") / "configs" / "lists"
    if ref_path.is_absolute() or ".." in ref_path.parts or not ref_path.as_posix().startswith(
        allowed_root.as_posix() + "/"
    ):
        errors.append(f"{path}: {label}.persons_ref must stay under data/configs/lists/")
        return errors
    if not (ROOT / ref_path).exists():
        errors.append(f"{path}: {label}.persons_ref target does not exist: {persons_ref}")
    return errors


def validate_group(path: Path, groups: dict[str, Any], group_key: str, row: object) -> list[str]:
    _ = groups
    label = f"person_groups.{group_key}"
    errors: list[str] = []
    if not isinstance(row, dict):
        return [f"{path}: {label} must be a mapping"]
    extra_keys = sorted(set(row) - ALLOWED_GROUP_KEYS)
    if extra_keys:
        errors.append(f"{path}: {label}: person_groups only allow label/persons/persons_ref")
        for key in extra_keys:
            errors.append(f"{path}: {label}.{key}: group field is not allowed")
    if not is_non_empty_string(row.get("label")):
        errors.append(f"{path}: {label}.label must be a non-empty string")

    source_keys = [key for key in PERSON_SOURCE_KEYS if key in row]
    if len(source_keys) != 1:
        errors.append(f"{path}: {label}: provide exactly one of persons or persons_ref")
        return errors

    if "persons" in row and not is_non_empty_string_list(row["persons"]):
        errors.append(f"{path}: {label}.persons must be a non-empty list of non-empty strings")
    if "persons_ref" in row:
        persons_ref = row["persons_ref"]
        if not is_non_empty_string(persons_ref):
            errors.append(f"{path}: {label}.persons_ref must be a non-empty string")
        else:
            errors.extend(validate_persons_ref(path, str(persons_ref), label))
    return errors


def validate_outputs(path: Path, outputs: object, groups: dict[str, Any]) -> list[str]:
    label = "outputs"
    errors: list[str] = []
    if not isinstance(outputs, dict):
        return [f"{path}: {label} must be a mapping"]
    extra_keys = sorted(set(outputs) - ALLOWED_OUTPUT_KEYS)
    for key in extra_keys:
        errors.append(f"{path}: {label}.{key}: outputs only allow known product output switches")
    for key in sorted(ALLOWED_OUTPUT_KEYS):
        if key not in outputs:
            errors.append(f"{path}: {label}.{key} must be declared")
            continue
        value = outputs[key]
        if isinstance(value, bool):
            continue
        if not isinstance(value, dict):
            errors.append(f"{path}: {label}.{key} must be a boolean or output switch mapping")
            continue
        if key != "net_evidence":
            errors.append(f"{path}: {label}.{key}: only net_evidence may use an output switch mapping")
        extra_detail_keys = sorted(set(value) - ALLOWED_OUTPUT_DETAIL_KEYS)
        for detail_key in extra_detail_keys:
            errors.append(f"{path}: {label}.{key}.{detail_key}: output switch field is not allowed")
        if "enabled" in value and not isinstance(value["enabled"], bool):
            errors.append(f"{path}: {label}.{key}.enabled must be a boolean")
        override = value.get("person_group_override")
        if override is not None:
            if not is_non_empty_string(override):
                errors.append(f"{path}: {label}.{key}.person_group_override must be null or a non-empty group key")
            elif override not in groups:
                errors.append(f"{path}: {label}.{key}.person_group_override references missing group {override!r}")
    return errors


def validate_person_groups(path: Path, groups: object) -> list[str]:
    label = "person_groups"
    errors: list[str] = []
    if not isinstance(groups, dict) or not groups:
        return [f"{path}: {label} must be a non-empty mapping"]
    for group_key, row in groups.items():
        if not is_non_empty_string(group_key):
            errors.append(f"{path}: {label}: group keys must be non-empty strings")
            continue
        errors.extend(validate_group(path, groups, str(group_key), row))
    return errors


def validate_timezone(path: Path, value: object) -> list[str]:
    if not is_non_empty_string(value):
        return [f"{path}: timezone must be a non-empty IANA timezone string"]
    if value not in ALLOWED_TIMEZONES:
        return [f"{path}: timezone must be one of {sorted(ALLOWED_TIMEZONES)}"]
    return []


def validate(path: Path = PROJECT_CONFIG_PATH) -> list[str]:
    if not path.exists():
        return [f"{path}: file does not exist"]

    raw_text = path.read_text(encoding="utf-8")
    errors = validate_yaml_surface(path, raw_text)
    if any("invalid YAML" in error for error in errors):
        return errors
    try:
        payload = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        return [*errors, f"{path}: invalid YAML ({exc})"]

    if not isinstance(payload, dict):
        return [*errors, f"{path}: top-level value must be a mapping"]
    errors.extend(validate_basic_subset(path, payload))
    errors.extend(find_forbidden_keys(path, payload))

    extra_top_level = sorted(set(payload) - ALLOWED_TOP_LEVEL_KEYS)
    for key in extra_top_level:
        errors.append(
            f"{path}: {key}: top-level config only allows "
            "version/timezone/active_subitem/default_person_group/person_groups/outputs"
        )
    if payload.get("version") != 2:
        errors.append(f"{path}: version must be 2")
    errors.extend(validate_timezone(path, payload.get("timezone")))
    active_subitem = payload.get("active_subitem")
    if not is_non_empty_string(active_subitem):
        errors.append(f"{path}: active_subitem must be a non-empty string")

    groups = payload.get("person_groups")
    errors.extend(validate_person_groups(path, groups))
    if isinstance(groups, dict):
        default_person_group = payload.get("default_person_group")
        if not is_non_empty_string(default_person_group):
            errors.append(f"{path}: default_person_group must be a non-empty group key")
        elif default_person_group not in groups:
            errors.append(f"{path}: default_person_group references missing group {default_person_group!r}")
        errors.extend(validate_outputs(path, payload.get("outputs"), groups))
    else:
        errors.append(f"{path}: outputs cannot be validated without person_groups")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("Project config validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
