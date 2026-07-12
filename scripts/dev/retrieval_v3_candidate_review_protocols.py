from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ReviewProtocol:
    rule_code: str
    fact_keys: tuple[str, ...]
    roles: tuple[str, ...]
    prompt: str
    alternative_fact_groups: tuple[tuple[str, ...], ...] = ()
    optional_fact_keys: tuple[str, ...] = ()

    def allows_scoring(self, facts: Mapping[str, bool]) -> bool:
        alternative_keys = {key for group in self.alternative_fact_groups for key in group}
        required = (key for key in self.fact_keys if key not in alternative_keys and key not in self.optional_fact_keys)
        return all(facts.get(key) is True for key in required) and all(
            any(facts.get(key) is True for key in group) for group in self.alternative_fact_groups
        )


PROTOCOLS = {
    "appointment_delegation": ReviewProtocol(
        rule_code="appointment_delegation",
        fact_keys=(
            "has_appointment_or_authorization", "has_named_actor", "has_task_or_responsibility",
            "has_result_or_feedback", "has_continuity_or_reuse",
        ),
        alternative_fact_groups=(("has_result_or_feedback", "has_continuity_or_reuse"),),
        roles=(
            "", "appointed_actor", "entrusted_actor", "delegated_actor", "strategic_advisor",
            "military_commander", "civil_official", "misappointed_actor", "misdelegated_actor",
            "misentrusted_actor", "authority_revoked_target",
        ),
        prompt="必须有具名对象、任用或授权动作、具体任务或职责，并有结果反馈或持续复用。",
    ),
    "talent_discovery": ReviewProtocol(
        rule_code="talent_discovery",
        fact_keys=(
            "has_named_talent", "has_discovery_or_recommendation", "has_entry_into_view_or_appointment",
            "has_emperor_attribution", "has_high_difficulty_background",
        ),
        roles=("", "discovered_talent", "recommended_talent", "recognized_talent", "missed_talent"),
        optional_fact_keys=("has_high_difficulty_background",),
        prompt=(
            "必须显示具名人才被发现、荐举、召见、试用或破格拔擢，并进入皇帝视野或任用链。"
            "普通升迁、已知重臣任命、单纯授权不算发现；高识别难度只影响档位，不是入分必需条件。"
        ),
    ),
    "tolerate_talent": ReviewProtocol(
        rule_code="tolerate_talent",
        fact_keys=(
            "has_named_talent", "has_emperor_handling_action", "has_talent_or_expression_safety_relevance",
            "has_concrete_protection_or_harm", "has_fault_boundary",
        ),
        roles=("", "protected_talent", "remonstrance_actor", "expression_safety_unit", "harmed_talent"),
        optional_fact_keys=("has_fault_boundary",),
        prompt=(
            "必须是皇帝对具名人才的容谏、保全、保护、处置或伤害，并具体影响人才安全、表达安全或授权信用。"
            "战役中的杀伤、一般刑罚词或人物政治结局不能仅凭关键词入分；负向必须辨明对象过错边界。"
        ),
    ),
    "anti_nepotism": ReviewProtocol(
        rule_code="anti_nepotism",
        fact_keys=(
            "has_named_actor", "has_selection_or_interference_action", "has_public_private_selection_basis",
            "has_office_or_displacement_effect", "has_emperor_attribution",
        ),
        roles=("", "anti_nepotism_resisted_actor", "nepotistic_beneficiary", "favorite_beneficiary", "appointment_interferer"),
        prompt=(
            "必须有具名对象和任用、择才或干预任免事实，并能判断公开择才还是亲旧近幸污染，以及岗位或排挤后果。"
            "亲属、外戚、宦官、党派身份本身不是负证；没有实际任免干预或公共岗位损害不得入分。"
        ),
    ),
}


def protocol(rule_code: str) -> ReviewProtocol:
    try:
        return PROTOCOLS[rule_code]
    except KeyError as exc:
        raise ValueError(f"unsupported candidate review rule: {rule_code}") from exc
