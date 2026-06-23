from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from yaml.tokens import AliasToken, AnchorToken, DocumentStartToken, TagToken


ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG_PATH = ROOT / "data" / "configs" / "project_config.yml"
ALLOWED_TOP_LEVEL_KEYS = {"version", "active_subitem", "subitems"}
ALLOWED_SUBITEM_KEYS = {"groups", "defaults"}
ALLOWED_GROUP_KEYS = {"label", "persons", "persons_ref", "persons_from_group"}
ALLOWED_DEFAULT_KEYS = {"trial_group", "expanded_group", "net_evidence_group"}
PERSON_SOURCE_KEYS = {"persons", "persons_ref", "persons_from_group"}
FORBIDDEN_KEYS = {
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
    for token in yaml.scan(raw_text):
        line = token.start_mark.line + 1
        if isinstance(token, AnchorToken):
            errors.append(f"{path}: line {line}: YAML anchors are not allowed")
        elif isinstance(token, AliasToken):
            errors.append(f"{path}: line {line}: YAML aliases are not allowed")
        elif isinstance(token, TagToken):
            errors.append(f"{path}: line {line}: custom YAML tags are not allowed")
        elif isinstance(token, DocumentStartToken):
            errors.append(f"{path}: line {line}: explicit document markers are not allowed")
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


def validate_group(path: Path, groups: dict[str, Any], selector: str, row: object) -> list[str]:
    label = f"subitems.*.groups.{selector}"
    errors: list[str] = []
    if not isinstance(row, dict):
        return [f"{path}: {label} must be a mapping"]
    extra_keys = sorted(set(row) - ALLOWED_GROUP_KEYS)
    if extra_keys:
        errors.append(f"{path}: {label}: groups only allow label/persons/persons_ref/persons_from_group")
        for key in extra_keys:
            errors.append(f"{path}: {label}.{key}: group field is not allowed")
    if not is_non_empty_string(row.get("label")):
        errors.append(f"{path}: {label}.label must be a non-empty string")

    source_keys = [key for key in PERSON_SOURCE_KEYS if key in row]
    if len(source_keys) != 1:
        errors.append(f"{path}: {label}: provide exactly one of persons, persons_ref, or persons_from_group")
        return errors

    if "persons" in row and not is_non_empty_string_list(row["persons"]):
        errors.append(f"{path}: {label}.persons must be a non-empty list of non-empty strings")
    if "persons_ref" in row:
        persons_ref = row["persons_ref"]
        if not is_non_empty_string(persons_ref):
            errors.append(f"{path}: {label}.persons_ref must be a non-empty string")
        else:
            errors.extend(validate_persons_ref(path, str(persons_ref), label))
    if "persons_from_group" in row:
        source_selector = row["persons_from_group"]
        if not is_non_empty_string(source_selector):
            errors.append(f"{path}: {label}.persons_from_group must be a non-empty string")
        elif source_selector == selector:
            errors.append(f"{path}: {label}.persons_from_group must not reference itself")
        elif source_selector not in groups:
            errors.append(f"{path}: {label}.persons_from_group references missing group {source_selector!r}")
    return errors


def validate_defaults(path: Path, defaults: object, groups: dict[str, Any]) -> list[str]:
    label = "subitems.*.defaults"
    errors: list[str] = []
    if not isinstance(defaults, dict):
        return [f"{path}: {label} must be a mapping"]
    extra_keys = sorted(set(defaults) - ALLOWED_DEFAULT_KEYS)
    for key in extra_keys:
        errors.append(f"{path}: {label}.{key}: defaults only allow group selector fields")
    for key in sorted(ALLOWED_DEFAULT_KEYS):
        selector = defaults.get(key)
        if not is_non_empty_string(selector):
            errors.append(f"{path}: {label}.{key} must be a non-empty group selector")
        elif selector not in groups:
            errors.append(f"{path}: {label}.{key} references missing group {selector!r}")
    return errors


def validate_subitem(path: Path, name: str, value: object) -> list[str]:
    label = f"subitems.{name}"
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{path}: {label} must be a mapping"]
    extra_keys = sorted(set(value) - ALLOWED_SUBITEM_KEYS)
    for key in extra_keys:
        errors.append(f"{path}: {label}.{key}: subitem config only allows groups/defaults")
    groups = value.get("groups")
    if not isinstance(groups, dict) or not groups:
        return [*errors, f"{path}: {label}.groups must be a non-empty mapping"]
    for selector, row in groups.items():
        if not is_non_empty_string(selector):
            errors.append(f"{path}: {label}.groups: group selector keys must be non-empty strings")
            continue
        errors.extend(validate_group(path, groups, str(selector), row))
    errors.extend(validate_defaults(path, value.get("defaults"), groups))
    return errors


def validate(path: Path = PROJECT_CONFIG_PATH) -> list[str]:
    if not path.exists():
        return [f"{path}: file does not exist"]

    raw_text = path.read_text(encoding="utf-8")
    errors = validate_yaml_surface(path, raw_text)
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
        errors.append(f"{path}: {key}: top-level config only allows version/active_subitem/subitems")
    if payload.get("version") != 1:
        errors.append(f"{path}: version must be 1")
    active_subitem = payload.get("active_subitem")
    if not is_non_empty_string(active_subitem):
        errors.append(f"{path}: active_subitem must be a non-empty string")
    subitems = payload.get("subitems")
    if not isinstance(subitems, dict) or not subitems:
        errors.append(f"{path}: subitems must be a non-empty mapping")
        return errors
    if is_non_empty_string(active_subitem) and active_subitem not in subitems:
        errors.append(f"{path}: active_subitem references missing subitem {active_subitem!r}")
    for name, subitem in subitems.items():
        if not is_non_empty_string(name):
            errors.append(f"{path}: subitems keys must be non-empty strings")
            continue
        errors.extend(validate_subitem(path, str(name), subitem))
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
