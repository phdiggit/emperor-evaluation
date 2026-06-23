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
I5B_GROUP_ID_BY_SELECTOR = {
    "three_pilot": "第五项B_三人试点",
    "expanded_batch1": "第五项B_扩展第一批",
    "net_evidence": "第五项B_净证据导出目标",
}
I5B_SELECTOR_BY_GROUP_ID = {group_id: selector for selector, group_id in I5B_GROUP_ID_BY_SELECTOR.items()}


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
    project_config = load_project_config()
    target_subitem = subitem or get_active_subitem()
    subitems = project_config.get("subitems")
    if not isinstance(subitems, dict):
        raise ValueError("project_config.yml subitems must be a mapping")
    config = subitems.get(target_subitem)
    if not isinstance(config, dict):
        raise ValueError(f"subitem {target_subitem!r} is missing from project_config.yml")
    return config


def _load_i5b_groups_config() -> dict[str, Any]:
    groups = get_subitem_config(DEFAULT_I5B_SUBITEM).get("groups")
    if not isinstance(groups, dict):
        raise ValueError(f"subitems.{DEFAULT_I5B_SUBITEM}.groups must be a mapping")
    return groups


def _load_i5b_defaults_config() -> dict[str, Any]:
    defaults = get_subitem_config(DEFAULT_I5B_SUBITEM).get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError(f"subitems.{DEFAULT_I5B_SUBITEM}.defaults must be a mapping")
    return defaults


def _selector_for_group_id(group_id_or_selector: str) -> str:
    return I5B_SELECTOR_BY_GROUP_ID.get(group_id_or_selector, group_id_or_selector)


def _load_persons_ref(persons_ref: str) -> list[str]:
    ref_path = ROOT / persons_ref
    payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{persons_ref} must contain a top-level YAML list")
    return [str(person) for person in payload]


def _resolve_i5b_group_persons(selector: str, *, seen: set[str] | None = None) -> list[str]:
    groups = _load_i5b_groups_config()
    group = groups.get(selector)
    if not isinstance(group, dict):
        raise ValueError(f"group selector {selector!r} is missing from project_config.yml")

    if "persons" in group:
        persons = group["persons"]
        if not isinstance(persons, list):
            raise ValueError(f"group selector {selector!r} persons must be a list")
        return [str(person) for person in persons]
    if "persons_ref" in group:
        persons_ref = group["persons_ref"]
        if not isinstance(persons_ref, str) or not persons_ref.strip():
            raise ValueError(f"group selector {selector!r} persons_ref must be a non-empty string")
        return _load_persons_ref(persons_ref)
    if "persons_from_group" in group:
        source_selector = group["persons_from_group"]
        if not isinstance(source_selector, str) or not source_selector.strip():
            raise ValueError(f"group selector {selector!r} persons_from_group must be a non-empty string")
        active_seen = set(seen or set())
        if selector in active_seen:
            raise ValueError(f"group selector {selector!r} persons_from_group creates a cycle")
        active_seen.add(selector)
        return _resolve_i5b_group_persons(source_selector, seen=active_seen)
    raise ValueError(f"group selector {selector!r} must define persons, persons_ref, or persons_from_group")


def _default_i5b_group_selector(default_key: str) -> str:
    selector = _load_i5b_defaults_config().get(default_key)
    if not isinstance(selector, str) or not selector.strip():
        raise ValueError(f"subitems.{DEFAULT_I5B_SUBITEM}.defaults.{default_key} must be a non-empty string")
    return selector


def load_i5b_person_pool() -> list[dict[str, Any]]:
    return default_i5b_candidate_pool_rows()


def load_i5b_view_groups() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for selector, group in _load_i5b_groups_config().items():
        if not isinstance(group, dict):
            raise ValueError(f"group selector {selector!r} must be a mapping")
        label = group.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"group selector {selector!r} label must be a non-empty string")
        rows.append(
            {
                "group_id": I5B_GROUP_ID_BY_SELECTOR.get(selector, selector),
                "group_name": label,
                "selector": selector,
                "persons": _resolve_i5b_group_persons(str(selector)),
            }
        )
    return rows


def get_i5b_group(group_id: str) -> dict[str, Any] | None:
    selector = _selector_for_group_id(group_id)
    for row in load_i5b_view_groups():
        if row.get("group_id") == group_id or row.get("selector") == selector:
            return row
    return None


def get_i5b_group_persons(group_id: str) -> list[str] | None:
    group = get_i5b_group(group_id)
    if group is None:
        return None
    persons = group.get("persons")
    if not isinstance(persons, list):
        raise ValueError(f"group {group_id!r} persons must be a list")
    return [str(person) for person in persons]


def get_i5b_trial_config() -> dict[str, Any]:
    selector = _default_i5b_group_selector("trial_group")
    group = get_i5b_group(selector)
    if group is None:
        raise ValueError(f"{selector} group is missing from project_config.yml")

    persons = group.get("persons")
    if not isinstance(persons, list):
        raise ValueError(f"{selector} persons must be a list")
    return {
        "item": DEFAULT_I5B_ITEM,
        "subitem": DEFAULT_I5B_SUBITEM,
        "targets": [str(person) for person in persons],
        "group": selector,
    }


def get_i5b_trial_targets() -> list[str]:
    return [str(person) for person in get_i5b_trial_config()["targets"]]


def get_i5b_expanded_batch1_targets() -> list[str]:
    selector = _default_i5b_group_selector("expanded_group")
    persons = get_i5b_group_persons(selector)
    if persons is None:
        raise ValueError(f"{selector} group is missing from project_config.yml")
    return persons


def get_i5b_net_evidence_targets() -> list[tuple[str, Path]]:
    selector = _default_i5b_group_selector("net_evidence_group")
    group = get_i5b_group(selector)
    if group is None:
        raise ValueError(f"{selector} group is missing from project_config.yml")

    persons = group.get("persons")
    if not isinstance(persons, list):
        raise ValueError(f"{selector} persons must be a list")
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
