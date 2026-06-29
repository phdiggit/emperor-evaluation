from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.i5b_runtime_defaults import (
    DEFAULT_I5B_NET_EVIDENCE_PATH_TEMPLATE,
    I5B_CANDIDATE_POOL_REQUIRED_FIELDS,
    default_i5b_candidate_pool_rows,
    default_i5b_review_warning_rules,
)


ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG_PATH = ROOT / "data" / "configs" / "project_config.yml"
DEFAULT_I5B_ITEM = "第五项"
DEFAULT_I5B_SUBITEM = "第五项B"
I5B_OUTPUT_SWITCHES = {
    "matrix",
    "auto_adjudication",
    "review_entry",
    "subitem_details",
    "net_evidence",
    "evidence_indexes",
}


def load_project_config(path: Path | None = None) -> dict[str, Any]:
    resolved_path = path or PROJECT_CONFIG_PATH
    payload = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{resolved_path} must contain a top-level YAML mapping")
    return payload


def get_active_subitem() -> str:
    project_config = load_project_config()
    active_subitem = project_config.get("active_subitem")
    if not isinstance(active_subitem, str) or not active_subitem.strip():
        raise ValueError("project_config.yml active_subitem must be a non-empty string")
    return active_subitem


def get_subitem_config(subitem: str | None = None) -> dict[str, Any]:
    target_subitem = subitem or get_active_subitem()
    active_subitem = get_active_subitem()
    if target_subitem != active_subitem:
        raise ValueError(f"subitem {target_subitem!r} is not the active project_config.yml workflow")
    return {
        "default_person_group": _default_i5b_person_group_key(),
        "person_groups": _load_i5b_person_groups_config(),
        "outputs": _load_i5b_outputs_config(),
    }


def _load_i5b_person_groups_config() -> dict[str, Any]:
    groups = load_project_config().get("person_groups")
    if not isinstance(groups, dict):
        raise ValueError("project_config.yml person_groups must be a mapping")
    return groups


def _load_i5b_outputs_config() -> dict[str, Any]:
    outputs = load_project_config().get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("project_config.yml outputs must be a mapping")
    return outputs


def _load_persons_ref(persons_ref: str) -> list[str]:
    ref_path = ROOT / persons_ref
    payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{persons_ref} must contain a top-level YAML list")
    return [str(person) for person in payload]


def _resolve_i5b_group_persons(group_key: str) -> list[str]:
    groups = _load_i5b_person_groups_config()
    group = groups.get(group_key)
    if not isinstance(group, dict):
        raise ValueError(f"group key {group_key!r} is missing from project_config.yml")

    if "persons" in group:
        persons = group["persons"]
        if not isinstance(persons, list):
            raise ValueError(f"group key {group_key!r} persons must be a list")
        return [str(person) for person in persons]
    if "persons_ref" in group:
        persons_ref = group["persons_ref"]
        if not isinstance(persons_ref, str) or not persons_ref.strip():
            raise ValueError(f"group key {group_key!r} persons_ref must be a non-empty string")
        return _load_persons_ref(persons_ref)
    raise ValueError(f"group key {group_key!r} must define persons or persons_ref")


def _default_i5b_person_group_key() -> str:
    group_key = load_project_config().get("default_person_group")
    if not isinstance(group_key, str) or not group_key.strip():
        raise ValueError("project_config.yml default_person_group must be a non-empty string")
    return group_key


def _output_switch(output_name: str) -> dict[str, Any]:
    raw_output = _load_i5b_outputs_config().get(output_name)
    if isinstance(raw_output, bool):
        return {"enabled": raw_output, "person_group_override": None}
    if isinstance(raw_output, dict):
        enabled = raw_output.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"outputs.{output_name}.enabled must be a boolean")
        override = raw_output.get("person_group_override")
        if override is not None and (not isinstance(override, str) or not override.strip()):
            raise ValueError(f"outputs.{output_name}.person_group_override must be null or a non-empty string")
        return {"enabled": enabled, "person_group_override": override}
    if raw_output is None:
        return {"enabled": False, "person_group_override": None}
    raise ValueError(f"outputs.{output_name} must be a boolean or mapping")


def load_i5b_person_pool() -> list[dict[str, Any]]:
    return default_i5b_candidate_pool_rows()


def load_i5b_view_groups() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group_key, group in _load_i5b_person_groups_config().items():
        if not isinstance(group, dict):
            raise ValueError(f"group key {group_key!r} must be a mapping")
        label = group.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"group key {group_key!r} label must be a non-empty string")
        rows.append(
            {
                "group_id": str(group_key),
                "group_name": label,
                "persons": _resolve_i5b_group_persons(str(group_key)),
            }
        )
    return rows


def get_i5b_group(group_key: str) -> dict[str, Any] | None:
    for row in load_i5b_view_groups():
        if row.get("group_id") == group_key:
            return row
    return None


def get_i5b_group_persons(group_key: str) -> list[str] | None:
    group = get_i5b_group(group_key)
    if group is None:
        return None
    persons = group.get("persons")
    if not isinstance(persons, list):
        raise ValueError(f"group {group_key!r} persons must be a list")
    return [str(person) for person in persons]


def get_i5b_active_workflow_config() -> dict[str, Any]:
    group_key = _default_i5b_person_group_key()
    group = get_i5b_group(group_key)
    if group is None:
        raise ValueError(f"{group_key} group is missing from project_config.yml")
    persons = group.get("persons")
    if not isinstance(persons, list):
        raise ValueError(f"{group_key} persons must be a list")
    return {
        "item": DEFAULT_I5B_ITEM,
        "subitem": get_active_subitem(),
        "default_person_group": group_key,
        "group": group_key,
        "group_label": group.get("group_name") or group_key,
        "targets": [str(person) for person in persons],
        "outputs": {name: _output_switch(name) for name in sorted(I5B_OUTPUT_SWITCHES)},
    }


def get_i5b_active_person_targets() -> list[str]:
    return [str(person) for person in get_i5b_active_workflow_config()["targets"]]


def get_i5b_output_person_targets(output_name: str) -> list[str]:
    switch = _output_switch(output_name)
    if not switch["enabled"]:
        return []
    group_key = switch.get("person_group_override") or _default_i5b_person_group_key()
    persons = get_i5b_group_persons(str(group_key))
    if persons is None:
        raise ValueError(f"{group_key} group is missing from project_config.yml")
    return persons


def get_i5b_trial_config() -> dict[str, Any]:
    group_key = "three_pilot"
    group = get_i5b_group(group_key)
    if group is None:
        raise ValueError(f"{group_key} group is missing from project_config.yml")

    persons = group.get("persons")
    if not isinstance(persons, list):
        raise ValueError(f"{group_key} persons must be a list")
    return {
        "item": DEFAULT_I5B_ITEM,
        "subitem": DEFAULT_I5B_SUBITEM,
        "targets": [str(person) for person in persons],
        "group": group_key,
    }


def get_i5b_trial_targets() -> list[str]:
    return [str(person) for person in get_i5b_trial_config()["targets"]]


def get_i5b_net_evidence_targets() -> list[tuple[str, Path]]:
    persons = get_i5b_output_person_targets("net_evidence")
    return [
        (str(person), ROOT / DEFAULT_I5B_NET_EVIDENCE_PATH_TEMPLATE.format(person=person))
        for person in persons
    ]


def get_i5b_expanded_candidate_pool_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in load_i5b_person_pool():
        if all(row.get(field) for field in I5B_CANDIDATE_POOL_REQUIRED_FIELDS):
            rows.append(row)
    return rows


def load_i5b_cluster_warning_rules() -> list[dict[str, Any]]:
    return default_i5b_review_warning_rules()


def get_i5b_cluster_warning_rules(
    *,
    rule_id: str | None = None,
    warning_type: str | None = None,
    trigger_type: str | None = None,
    subitem: str | None = None,
) -> list[dict[str, Any]]:
    rows = load_i5b_cluster_warning_rules()
    if rule_id is not None:
        rows = [row for row in rows if row.get("rule_id") == rule_id]
    if warning_type is not None:
        rows = [row for row in rows if row.get("warning_type") == warning_type]
    if trigger_type is not None:
        rows = [row for row in rows if row.get("trigger_type") == trigger_type]
    if subitem is not None:
        rows = [row for row in rows if row.get("subitem") == subitem]
    return rows


def get_i5b_cluster_warning_rule(rule_id: str) -> dict[str, Any] | None:
    rows = get_i5b_cluster_warning_rules(rule_id=rule_id)
    if not rows:
        return None
    return rows[0]
