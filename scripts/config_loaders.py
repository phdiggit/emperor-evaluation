from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
I5B_PERSON_POOL_PATH = ROOT / "data" / "configs" / "视图配置" / "第五项B_人物池.json"
I5B_VIEW_GROUPS_PATH = ROOT / "data" / "configs" / "视图配置" / "第五项B_视图分组.json"
DEFAULT_I5B_ITEM = "第五项"
DEFAULT_I5B_SUBITEM = "第五项B"
DEFAULT_I5B_NET_EVIDENCE_PATH_TEMPLATE = "exports/markdown_views/第五项B_{person}净证据池.md"
I5B_CANDIDATE_POOL_REQUIRED_FIELDS = [
    "person",
    "candidate_type",
    "why_selected",
    "expected_rule_pressure",
    "required_evidence_focus",
    "adjacent_item_risk",
    "negative_scan_focus",
    "recommended_priority",
]


def load_json_array(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a top-level JSON array")

    rows: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError(f"{path} array items must be JSON objects")
        rows.append(row)
    return rows


def load_i5b_person_pool() -> list[dict[str, Any]]:
    return load_json_array(I5B_PERSON_POOL_PATH)


def load_i5b_view_groups() -> list[dict[str, Any]]:
    return load_json_array(I5B_VIEW_GROUPS_PATH)


def get_i5b_group(group_id: str) -> dict[str, Any] | None:
    for row in load_i5b_view_groups():
        if row.get("group_id") == group_id:
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
    group = get_i5b_group("第五项B_三人试点")
    if group is None:
        raise ValueError("第五项B_三人试点 group is missing from 第五项B_视图分组.json")

    persons = group.get("persons")
    if not isinstance(persons, list):
        raise ValueError("第五项B_三人试点 persons must be a list")
    return {
        "item": DEFAULT_I5B_ITEM,
        "subitem": str(group.get("subitem", DEFAULT_I5B_SUBITEM)),
        "targets": [str(person) for person in persons],
        "note": str(group.get("note", "")),
    }


def get_i5b_trial_targets() -> list[str]:
    return [str(person) for person in get_i5b_trial_config()["targets"]]


def get_i5b_expanded_batch1_targets() -> list[str]:
    persons = get_i5b_group_persons("第五项B_扩展第一批")
    if persons is None:
        raise ValueError("第五项B_扩展第一批 group is missing from 第五项B_视图分组.json")
    return persons


def get_i5b_net_evidence_targets() -> list[tuple[str, Path]]:
    group = get_i5b_group("第五项B_净证据导出目标")
    if group is None:
        raise ValueError("第五项B_净证据导出目标 group is missing from 第五项B_视图分组.json")

    persons = group.get("persons")
    if not isinstance(persons, list):
        raise ValueError("第五项B_净证据导出目标 persons must be a list")
    path_template = group.get("path_template")
    if not isinstance(path_template, str) or not path_template.strip():
        raise ValueError("第五项B_净证据导出目标 path_template must be a non-empty string")
    return [(str(person), ROOT / path_template.format(person=person)) for person in persons]


def get_i5b_expanded_candidate_pool_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in load_i5b_person_pool():
        if all(row.get(field) for field in I5B_CANDIDATE_POOL_REQUIRED_FIELDS):
            rows.append(row)
    return rows
