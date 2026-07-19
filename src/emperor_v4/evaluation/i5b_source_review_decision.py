from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


EVENT_RULES = (
    "talent_discovery",
    "appointment_delegation",
    "tolerate_talent",
    "anti_nepotism",
)


def _indexed(rows: Sequence[Mapping[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for raw in rows:
        value = str(raw.get(key) or "").strip()
        if not value or value in indexed:
            raise ValueError(f"{label} 缺少或重复 {key}")
        indexed[value] = deepcopy(dict(raw))
    return indexed


def _dispositions(rule: Mapping[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    rows: dict[str, tuple[str, dict[str, Any]]] = {}
    eligible = rule.get("eligible") or {}
    for side in ("positive", "negative"):
        for raw in eligible.get(side) or ():
            material_id = str(raw.get("material_id") or "").strip()
            if not material_id or material_id in rows:
                raise ValueError("I5B eligible disposition 缺少或重复 material_id")
            rows[material_id] = (side, deepcopy(dict(raw)))
    for raw in rule.get("excluded") or ():
        material_id = str(raw.get("material_id") or "").strip()
        if not material_id or material_id in rows:
            raise ValueError("I5B excluded disposition 缺少或重复 material_id")
        rows[material_id] = ("excluded", deepcopy(dict(raw)))
    return rows


def merge_i5b_source_review_decisions(
    baseline: Mapping[str, Any], increment: Mapping[str, Any]
) -> dict[str, Any]:
    """Retain every baseline material unless the increment explicitly replaces its disposition."""
    for key in ("ruler", "ruler_ref", "window"):
        if str(baseline.get(key) or "") != str(increment.get(key) or ""):
            raise ValueError(f"I5B baseline 与 increment 的 {key} 不一致")
    baseline_rules = baseline.get("rules")
    increment_rules = increment.get("rules")
    if not isinstance(baseline_rules, Mapping) or not isinstance(increment_rules, Mapping):
        raise ValueError("I5B baseline 或 increment 缺少 rules")

    merged = deepcopy(dict(increment))
    merged_rules = deepcopy(dict(increment_rules))
    for rule_code in EVENT_RULES:
        old_rule = baseline_rules.get(rule_code)
        new_rule = increment_rules.get(rule_code)
        if not isinstance(old_rule, Mapping) or not isinstance(new_rule, Mapping):
            raise ValueError(f"I5B baseline 或 increment 缺少 {rule_code}")
        old_materials = _indexed(old_rule.get("materials") or (), "material_id", rule_code)
        new_materials = _indexed(new_rule.get("materials") or (), "material_id", rule_code)
        material_order = [*old_materials, *(key for key in new_materials if key not in old_materials)]
        materials = {**old_materials, **new_materials}

        dispositions = _dispositions(old_rule)
        dispositions.update(_dispositions(new_rule))
        if set(dispositions) != set(materials):
            missing = sorted(set(materials) - set(dispositions))
            unknown = sorted(set(dispositions) - set(materials))
            raise ValueError(
                f"{rule_code} 合并后候选处置不闭合: missing={missing}, unknown={unknown}"
            )
        eligible = {"positive": [], "negative": []}
        excluded = []
        for material_id in material_order:
            side, row = dispositions[material_id]
            if side == "excluded":
                excluded.append(row)
            else:
                material_side = str(materials[material_id].get("side") or "")
                if material_side != side:
                    raise ValueError(f"{material_id} material side 与 eligible side 不一致")
                eligible[side].append(row)
        merged_rules[rule_code] = {
            **deepcopy(dict(new_rule)),
            "materials": [materials[key] for key in material_order],
            "eligible": eligible,
            "excluded": excluded,
            "baseline_material_ids": list(old_materials),
        }

    old_team = baseline_rules.get("team_building")
    new_team = increment_rules.get("team_building")
    if not isinstance(old_team, Mapping) or not isinstance(new_team, Mapping):
        raise ValueError("I5B baseline 或 increment 缺少 team_building")
    old_members = _indexed(old_team.get("members") or (), "person_ref", "team_building")
    new_members = _indexed(new_team.get("members") or (), "person_ref", "team_building")
    member_order = [*old_members, *(key for key in new_members if key not in old_members)]
    members = {**old_members, **new_members}
    positive = [str(value) for value in new_team.get("positive_members") or ()]
    negative = [str(value) for value in new_team.get("negative_members") or ()]
    if len(positive) > 8 or len(negative) > 3:
        raise ValueError("团队建设冻结选择超过正8负3")
    if len(set(positive)) != len(positive) or len(set(negative)) != len(negative):
        raise ValueError("团队建设冻结选择存在重复人物")
    member_selection_keys = set(members) | {
        str(row.get("person") or "") for row in members.values()
    }
    if not set(positive + negative) <= member_selection_keys:
        raise ValueError("团队建设冻结选择引用了候选池外人物")
    merged_rules["team_building"] = {
        **deepcopy(dict(new_team)),
        "members": [members[key] for key in member_order],
        "positive_members": positive,
        "negative_members": negative,
        "baseline_member_refs": list(old_members),
    }
    retrieved = [str(value) for value in increment.get("retrieved_person_refs") or ()]
    if len(retrieved) > 12 or len(set(retrieved)) != len(retrieved):
        raise ValueError("I5B retrieved_person_refs 必须去重且不超过12人")
    if retrieved and not set(retrieved) <= set(members):
        raise ValueError("I5B 团队候选池未覆盖全部检索人物")
    merged["rules"] = merged_rules
    merged["baseline_retention"] = {
        "status": "closed",
        "event_material_count": sum(
            len(merged_rules[code]["baseline_material_ids"]) for code in EVENT_RULES
        ),
        "team_member_count": len(merged_rules["team_building"]["baseline_member_refs"]),
    }
    return merged
