from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from emperor_v4.persistence.canonical_refs import canonical_hashed_ref
from emperor_v4.evaluation.battle_outcome_worklist import (
    _DECISIVE_RELATIONS,
    _MILITARY_CAPABILITY_MODES,
    _military_capability_contribution,
    _validate_campaign_command_topology,
    derive_person_command_index,
    load_military_settlements,
)


SCHEMA_VERSION = "battle-parent-contract-registry-v1"
CURRENT_SCHEMA_VERSION = "battle-parent-contract-registry-v2"
EVIDENCE_MATURITY = "REGISTERED_NOT_GOLD"
FORMAL_STATUS = "ADJUDICATED_SOURCE_BACKFILL_REQUIRED"
TIER_BY_RESULT_CLASS = {
    "local_tactical": "C",
    "important_objective": "B",
    "major_stage_or_crisis": "A",
    "independent_direction": "S-",
    "single_pole_decisive_defeat": "S",
    "external_hegemony_decisive_defeat": "S",
    "single_pole_or_state_terminal": "S",
    "composite_poles_terminal": "S+",
    "unification_terminal": "S+",
    "external_hegemony_terminal": "S+",
}


def _normalize_person_command_index(member: dict[str, Any]) -> None:
    existing_index = member.get("person_command_index")
    if not isinstance(existing_index, Mapping):
        return
    normalized_index = dict(existing_index)
    mode = str(normalized_index.get("consumption_mode") or "")
    normalized_index.setdefault(
        "capability_mode",
        {
            "full_parent": "integrated_command",
            "person_result": "independent_direction",
            "joint_parent": "integrated_command",
            "scoped_projection": "tactical_execution",
            "operational_result": "operational_design",
            "none": "nominal_only",
        }.get(mode, "unresolved"),
    )
    normalized_index.setdefault(
        "decisive_relation",
        {
            "full_parent": "decisive_creator",
            "person_result": "co_decisive",
            "joint_parent": "co_decisive",
            "scoped_projection": "stage_executor",
            "operational_result": "none",
            "none": "none",
        }.get(mode, "unresolved"),
    )
    member["person_command_index"] = normalized_index
VALID_LAND_AXIS = {
    "local_point",
    "important_region",
    "strategic_gateway",
    "core_heartland",
    "capital_or_state_survival",
}
_ADMINISTRATIVE_UNIT_COUNT_RE = re.compile(
    r"(?:[一二三四五六七八九十百千万数]+|\d+)(?:余|馀)?(?:州|郡|县|城)(?!军)"
)
_DECLARED_LAND_AXIS_RE = re.compile(r"土地轴\s*=\s*([a-z_]+)")
_LAND_FUNCTION_MARKERS = (
    "人口",
    "户口",
    "赋税",
    "财赋",
    "兵源",
    "军备",
    "供粮",
    "粮运",
    "仓储",
    "产马",
    "都城",
    "首都",
    "中枢",
    "核心",
    "腹地",
    "根据地",
    "关隘",
    "门户",
    "渡口",
    "通道",
    "走廊",
    "交通",
    "连片",
    "军政",
    "财政基地",
    "征兵",
    "征税",
    "驻军",
    "指挥",
    "战略方向",
    "统治结构",
)
VALID_OPPONENT_WEIGHT = {
    "minor",
    "regional_major",
    "first_tier_pole",
    "dominant_pole",
    "external_state",
    "external_hegemony",
}
VALID_OPPONENT_CONDITION = {
    "strong",
    "viable",
    "weakened",
    "residual",
    "unclear",
}
VALID_BATTLE_RESULT = {"victory", "mixed", "defeat", "unclear"}
VALID_OBJECTIVE_COMPLETION = {"complete", "partial", "failed", "unclear"}
VALID_OPPONENT_FORCE_EFFECT = {
    "none",
    "limited_attrition",
    "major_degradation",
    "main_force_destroyed",
    "military_system_collapsed",
}
VALID_COMBAT_DIFFICULTY = {"D0", "D1", "D2", "D3", "D4"}
DIFFICULTY_RANK = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4}
VALID_COMMAND_TOPOLOGY = {
    "single_integrated_command",
    "joint_integrated_command",
    "federated_directions",
    "distributed_response",
    "opposed_commands",
    "command_unresolved",
    "sequential_successor_command",
}
VALID_RULER_ROLE_STATUS = {"resolved", "unresolved"}
VALID_FAILURE_RESPONSIBILITY = {
    "primary",
    "shared",
    "subordinate_execution",
    "disobedience",
    "mitigated",
    "not_responsible",
}
VALID_FAILURE_SEVERITY = {0.2, 0.4, 0.6, 0.7, 1.0}
VALID_FAILURE_DOMAIN = {"command_failure", "war_conduct"}
VALID_CONTRACT_DISPOSITIONS = {
    "REGISTERED_CONTRACT",
    "SPLIT_CAMPAIGN_PORTFOLIO",
    "EVIDENCE_ONLY_TERMINAL",
    "REDIRECTED_MIXED_PARENT",
    "REDIRECTED_NON_BATTLE_OUTCOME",
    "MERGED_INTO_PARENT",
    "EXCLUDED_AGGREGATE_SECURITY_STATE",
    "EXCLUDED_BELOW_PUBLIC_THRESHOLD",
    "EXCLUDED_UNIFICATION",
}

_TERMINAL_DISPOSITIONS = {
    FORMAL_STATUS: "REGISTERED_FULL",
    "MERGED_INTO_CAMPAIGN_GROUP": "MERGED_INTO_PARENT",
    "BELOW_PUBLIC_OUTCOME_THRESHOLD": "EXCLUDED_BELOW_PUBLIC_THRESHOLD",
    "REDIRECT_NON_BATTLE_OUTCOME": "REDIRECTED_NON_BATTLE_OUTCOME",
    "HOLD_AGGREGATE_SECURITY_STATE": "EXCLUDED_AGGREGATE_SECURITY_STATE",
}


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _first_text(values: object) -> str:
    if isinstance(values, str):
        return values.strip()
    if isinstance(values, list):
        for value in values:
            text = _first_text(value)
            if text:
                return text
    return ""


def _usable_result(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if normalized.startswith(("未知", "不详", "待后续")):
        return False
    if any(
        marker in normalized
        for marker in (
            "未发生这支",
            "这是未执行方案",
            "南征未执行",
            "不能当作已发生战争",
        )
    ):
        return False
    if (
        re.search(r"未.{0,20}终局|终局.{0,20}(?:未|不明)", normalized)
        or any(
            marker in normalized
            for marker in (
                "事件延续到后卷",
                "范围末开放",
                "范围仍开放",
                "不作推算",
                "本卡为阶段卡",
                "本卡是阶段卡",
            )
        )
    ):
        return False
    return True


def _first_usable_text(values: object) -> str:
    if isinstance(values, str):
        return values.strip() if _usable_result(values) else ""
    if isinstance(values, list):
        for value in values:
            text = _first_usable_text(value)
            if text:
                return text
    return ""


def _fact_result(fields: Mapping[str, Any]) -> str:
    key_markers = {
        "收束": 12,
        "终结": 12,
        "受降": 11,
        "控制": 11,
        "战后": 10,
        "戰後": 10,
        "后续": 9,
        "後續": 9,
        "结果": 9,
        "結果": 9,
        "战果": 9,
        "戰果": 9,
        "俘虏": 8,
        "俘虜": 8,
        "和解": 8,
        "决战": 7,
        "決戰": 7,
        "截击": 7,
        "截擊": 7,
        "破城": 7,
        "陷落": 7,
        "退兵": 6,
        "撤退": 6,
        "追击": 6,
        "追擊": 6,
    }
    text_markers = (
        "灭亡",
        "滅亡",
        "平定",
        "受降",
        "投降",
        "请降",
        "請降",
        "大败",
        "大敗",
        "击破",
        "擊破",
        "攻破",
        "克复",
        "克復",
        "陷落",
        "被俘",
        "俘获",
        "俘獲",
        "斩首",
        "斬首",
        "战死",
        "戰死",
        "解围",
        "解圍",
        "退军",
        "退軍",
        "撤军",
        "撤軍",
        "控制",
        "据有",
        "據有",
    )
    ranked: list[tuple[int, int, str]] = []
    for order, (key, value) in enumerate(fields.items()):
        text = _first_usable_text(value)
        if not text:
            continue
        key_score = max(
            (score for marker, score in key_markers.items() if marker in str(key)),
            default=0,
        )
        text_score = min(
            6,
            sum(2 for marker in text_markers if marker in text),
        )
        score = key_score + text_score
        if score >= 8 or (score >= 6 and text_score > 0):
            ranked.append((score, order, text))
    if not ranked:
        return ""
    return max(ranked)[2]


def _candidate_result(candidate: Mapping[str, Any]) -> str:
    for node in candidate.get("terminal_nodes") or ():
        text = str(node.get("outcome") or "").strip()
        if _usable_result(text):
            return text
        fields = node.get("source_fact_fields") or {}
        for key in (
            "⑥收束与后续控制",
            "⑥结果与后续",
            "④阶段序列与攻守转换",
            "当前状态",
            "战果",
            "结果",
            "六环节展开",
        ):
            text = _first_usable_text(fields.get(key))
            if text:
                return text
        for key, value in fields.items():
            if any(
                marker in str(key)
                for marker in ("收束", "结果", "战果", "阶段", "六环节")
            ):
                text = _first_usable_text(value)
                if text:
                    return text
        text = _fact_result(fields)
        if text:
            return text
    return ""


def _source_lineage(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_card_ids": list(candidate.get("source_card_ids") or ()),
        "source_files": list(candidate.get("source_files") or ()),
        "source_revision_refs": list(candidate.get("source_revision_refs") or ()),
        "lineage_basis": (
            "父群合同裁决直接消费已验收战争卡；固定revision存在时保留，"
            "缺少revision不阻断中性父群处置。"
        ),
    }


def _validate_external_hegemony_terminal_assessment(
    *,
    war_event_id: str,
    fields: Mapping[str, Any],
    assessment: Any,
    prewar_assessment: Any = None,
) -> None:
    result_class = str(fields.get("result_class") or "")
    is_external_hegemony = (
        fields.get("opponent_strategic_weight") == "external_hegemony"
    )
    if is_external_hegemony:
        if not isinstance(prewar_assessment, Mapping):
            raise ValueError(
                f"{war_event_id} 外部霸权对手缺少战前身份裁定"
            )
        required_prewar_conditions = (
            "sustained_core_pressure",
            "national_security_order_reoriented",
            "existential_capability",
        )
        if (
            any(prewar_assessment.get(key) is not True for key in required_prewar_conditions)
            or not str(prewar_assessment.get("basis") or "").strip()
        ):
            raise ValueError(
                f"{war_event_id} 外部霸权战前身份必须闭合核心压迫、全国安全重排和存亡级威胁"
            )
    elif result_class in {
        "external_hegemony_decisive_defeat",
        "external_hegemony_terminal",
    }:
        raise ValueError(
            f"{war_event_id} 外部霸权结果类必须面对external_hegemony对手"
        )
    is_external_hegemony_victory = (
        is_external_hegemony
        and fields.get("battle_result") == "victory"
        and fields.get("objective_completion") == "complete"
    )
    if (
        not is_external_hegemony_victory
        and result_class != "external_hegemony_terminal"
    ):
        return
    if not isinstance(assessment, Mapping):
        raise ValueError(
            f"{war_event_id} 外部霸权完整胜利缺少终局语义裁定"
        )
    structure_collapsed = assessment.get("ruling_structure_collapsed")
    order_reversed = assessment.get(
        "security_order_persistently_reversed"
    )
    if (
        type(structure_collapsed) is not bool
        or type(order_reversed) is not bool
        or not str(assessment.get("basis") or "").strip()
    ):
        raise ValueError(
            f"{war_event_id} 外部霸权终局裁定必须明确两项硬条件及依据"
        )
    hard_path_closed = structure_collapsed and order_reversed
    selected_hard_path = result_class == "external_hegemony_terminal"
    if hard_path_closed != selected_hard_path:
        raise ValueError(
            f"{war_event_id} 外部霸权终局事实与结果类别矛盾: "
            f"hard_path_closed={hard_path_closed}, "
            f"result_class={result_class}"
        )

    if result_class == "external_hegemony_decisive_defeat":
        if not is_external_hegemony_victory:
            raise ValueError(
                f"{war_event_id} 外部霸权决定性击溃必须是完整胜利"
            )
        if fields.get("opponent_force_effect") not in {
            "main_force_destroyed",
            "military_system_collapsed",
        }:
            raise ValueError(
                f"{war_event_id} 外部霸权决定性击溃必须至少摧毁当次方向主力"
            )


def _validate_residual_opponent_result_ceiling(
    *,
    war_event_id: str,
    fields: Mapping[str, Any],
) -> None:
    if fields.get("opponent_condition") != "residual":
        return
    result_class = str(fields.get("result_class") or "")
    if result_class in {
        "independent_direction",
        "single_pole_decisive_defeat",
        "external_hegemony_decisive_defeat",
        "single_pole_or_state_terminal",
        "composite_poles_terminal",
        "unification_terminal",
        "external_hegemony_terminal",
    }:
        raise ValueError(
            f"{war_event_id} 残余对手不得仅凭完整收束登记为S-以上: "
            f"result_class={result_class}"
        )


def _validate_problem_difficulty(
    *,
    war_event_id: str,
    fields: Mapping[str, Any],
) -> None:
    """Keep task difficulty independent from how cleanly it was executed."""

    if (
        fields.get("opponent_strategic_weight") == "external_hegemony"
        and fields.get("result_class")
        in {
            "external_hegemony_decisive_defeat",
            "external_hegemony_terminal",
        }
        and fields.get("battle_result") == "victory"
        and fields.get("objective_completion") == "complete"
        and DIFFICULTY_RANK.get(str(fields.get("combat_difficulty")), -1)
        < DIFFICULTY_RANK["D3"]
    ):
        raise ValueError(
            f"{war_event_id} 外部霸权核心摧毁任务不得因执行顺利降至D2以下"
        )


def _validate_land_axis_basis(
    *, war_event_id: str, fields: Mapping[str, Any]
) -> None:
    basis = str(
        fields.get("tier_basis")
        or fields.get("campaign_tier_basis")
        or ""
    )
    declared_axis = _DECLARED_LAND_AXIS_RE.search(basis)
    field_axis = str(fields.get("land_strategic_value") or "")
    if declared_axis and field_axis and declared_axis.group(1) != field_axis:
        raise ValueError(
            f"{war_event_id} 土地轴说明与结构字段不一致: "
            f"basis={declared_axis.group(1)} field={field_axis}"
        )
    tier = str(fields.get("campaign_tier") or "")
    if tier not in {"S-", "S", "S+"}:
        return
    if not _ADMINISTRATIVE_UNIT_COUNT_RE.search(basis):
        return
    if any(marker in basis for marker in _LAND_FUNCTION_MARKERS):
        return
    raise ValueError(
        f"{war_event_id} A以上土地轴仅列行政单位数量，"
        "必须补充人口财赋、军政基地、战略节点或体系影响依据"
    )


def _validate_internal_independent_direction_scale(
    *,
    war_event_id: str,
    fields: Mapping[str, Any],
) -> None:
    if fields.get("result_class") != "independent_direction":
        return
    if fields.get("opponent_strategic_weight") == "minor":
        raise ValueError(
            f"{war_event_id} 弱小力量不得仅凭相对核心根据地或复国结果登记S-；"
            "必须证明至少达到区域主要对手及中大型独立方向门槛"
        )


def _validate_single_pole_decisive_defeat(
    *,
    war_event_id: str,
    fields: Mapping[str, Any],
) -> None:
    if fields.get("result_class") != "single_pole_decisive_defeat":
        return
    if fields.get("opponent_strategic_weight") not in {
        "first_tier_pole",
        "dominant_pole",
    }:
        raise ValueError(
            f"{war_event_id} 单一竞争极决定性击溃必须面对战前第一梯队竞争极"
        )
    if (
        fields.get("battle_result") != "victory"
        or fields.get("objective_completion") != "complete"
        or fields.get("opponent_force_effect") not in {
            "main_force_destroyed",
            "military_system_collapsed",
        }
    ):
        raise ValueError(
            f"{war_event_id} 单一竞争极决定性击溃必须完成对主力或军事体系的完整胜利"
        )


def _validate_talent_method_validation(
    *,
    war_event_id: str,
    member: Mapping[str, Any],
    source_refs: Sequence[str],
) -> None:
    assessment = member.get("talent_method_validation")
    if assessment is None:
        return
    if (
        not isinstance(assessment, Mapping)
        or assessment.get("level") != "important"
        or not str(assessment.get("basis") or "").strip()
        or not assessment.get("source_refs")
        or not set(assessment["source_refs"]).issubset(set(source_refs))
    ):
        raise ValueError(
            f"{war_event_id} 重要军事方法复验字段不完整或史源越界"
        )


def _full_row(
    candidate: Mapping[str, Any],
    adjudication: Mapping[str, Any],
    settlement: Mapping[str, Any],
) -> dict[str, Any]:
    payload = adjudication.get("payload") or {}
    members = [dict(member) for member in adjudication.get("members") or ()]
    for member in members:
        _validate_talent_method_validation(
            war_event_id=str(candidate["war_event_id"]),
            member=member,
            source_refs=list(adjudication.get("source_refs") or ()),
        )
    attributable_failures = [
        dict(failure) for failure in payload.get("attributable_failures") or ()
    ]
    ruler_members = [
        member for member in members if member.get("actor_kind") == "ruler"
    ]
    ruler_role_status = adjudication.get("ruler_role_status") or (
        "resolved" if ruler_members else "unresolved"
    )
    ruler_role_basis = adjudication.get("ruler_role_basis") or (
        "；".join(
            str(member.get("contribution_scope") or "").strip()
            for member in ruler_members
            if str(member.get("contribution_scope") or "").strip()
        )
        if ruler_members
        else "当前完整裁决未闭合在位统治者与父战役的具体关系，保持未决。"
    )
    result_class = str(payload.get("strategic_result_class") or "")
    tier = payload.get("campaign_tier")
    if TIER_BY_RESULT_CLASS.get(result_class) != tier:
        raise ValueError(
            f"{candidate['war_event_id']} 完整裁决结果类别与档位不一致: "
            f"{result_class}/{tier}"
        )
    field_contracts = {
        "land_strategic_value": VALID_LAND_AXIS,
        "opponent_strategic_weight": VALID_OPPONENT_WEIGHT,
        "opponent_condition": VALID_OPPONENT_CONDITION,
        "battle_result": VALID_BATTLE_RESULT,
        "objective_completion": VALID_OBJECTIVE_COMPLETION,
    }
    for field_name, allowed in field_contracts.items():
        if payload.get(field_name) not in allowed:
            raise ValueError(
                f"{candidate['war_event_id']} 完整裁决合同字段非法或缺失: "
                f"{field_name}={payload.get(field_name)}"
            )
    if (
        payload.get("opponent_force_effect") is not None
        and payload.get("opponent_force_effect")
        not in VALID_OPPONENT_FORCE_EFFECT
    ):
        raise ValueError(
            f"{candidate['war_event_id']} 完整裁决敌军战力结果轴非法: "
            f"{payload.get('opponent_force_effect')}"
        )
    force_effect = payload.get("opponent_force_effect")
    if force_effect is not None and (
        f"敌军轴={force_effect}"
        not in str(payload.get("campaign_tier_basis") or "")
        or (
            force_effect
            in {
                "major_degradation",
                "main_force_destroyed",
                "military_system_collapsed",
            }
            and (
                payload.get("battle_result") not in {"victory", "mixed"}
                or payload.get("objective_completion")
                not in {"complete", "partial"}
            )
        )
    ):
        raise ValueError(
            f"{candidate['war_event_id']} 敌军战力结果轴与结果或档位依据矛盾"
        )
    _validate_external_hegemony_terminal_assessment(
        war_event_id=str(candidate["war_event_id"]),
        fields={**payload, "result_class": result_class},
        assessment=payload.get(
            "external_hegemony_terminal_assessment"
        ),
        prewar_assessment=payload.get(
            "external_hegemony_prewar_assessment"
        ),
    )
    _validate_residual_opponent_result_ceiling(
        war_event_id=str(candidate["war_event_id"]),
        fields={**payload, "result_class": result_class},
    )
    _validate_land_axis_basis(
        war_event_id=str(candidate["war_event_id"]),
        fields={**payload, "result_class": result_class},
    )
    _validate_internal_independent_direction_scale(
        war_event_id=str(candidate["war_event_id"]),
        fields={**payload, "result_class": result_class},
    )
    _validate_single_pole_decisive_defeat(
        war_event_id=str(candidate["war_event_id"]),
        fields={**payload, "result_class": result_class},
    )
    if (
        not adjudication.get("observable_result")
        or not payload.get("campaign_tier_basis")
        or not adjudication.get("source_refs")
    ):
        raise ValueError(
            f"{candidate['war_event_id']} 完整裁决缺少结果、档位依据或史源"
        )
    return {
        "war_event_id": candidate["war_event_id"],
        "dynasty": candidate["dynasty"],
        "disposition": "REGISTERED_FULL",
        "public_outcome_registered": True,
        "canonical_label": adjudication.get("canonical_label"),
        "period": adjudication.get("period"),
        "observable_result": adjudication.get("observable_result"),
        "result_direction": {
            "victory": "positive",
            "mixed": "mixed",
            "defeat": "negative",
            "unclear": "mixed",
        }.get(str(payload.get("battle_result")), "mixed"),
        "campaign_tier": tier,
        "result_class": result_class,
        "land_strategic_value": payload.get("land_strategic_value"),
        "opponent_strategic_weight": payload.get(
            "opponent_strategic_weight"
        ),
        "opponent_condition": payload.get("opponent_condition"),
        "battle_result": payload.get("battle_result"),
        "objective_completion": payload.get("objective_completion"),
        "objective_shortfalls": list(payload.get("objective_shortfalls") or ()),
        "opponent_force_effect": payload.get("opponent_force_effect"),
        "external_hegemony_prewar_assessment": payload.get(
            "external_hegemony_prewar_assessment"
        ),
        "external_hegemony_terminal_assessment": payload.get(
            "external_hegemony_terminal_assessment"
        ),
        "tier_basis": payload.get("campaign_tier_basis"),
        "combat_difficulty": payload.get("combat_difficulty"),
        "combat_difficulty_basis": payload.get("combat_difficulty_basis"),
        "command_status": "FULL_CONTRACT",
        "campaign_command_topology": adjudication.get(
            "campaign_command_topology"
        ),
        "ruler_role_status": ruler_role_status,
        "ruler_role_basis": ruler_role_basis,
        "members": members,
        "attributable_failures": attributable_failures,
        "detail_expansion_status": "COMPLETE",
        "wc_grade": settlement.get("wc_consistency_grade")
        or (settlement.get("cost_axes") or {}).get("WC"),
        "security_grade": settlement.get("strategic_security_grade"),
        "source_lineage": _source_lineage(candidate),
        "source_refs": list(adjudication.get("source_refs") or ()),
        "basis": adjudication.get("basis"),
        "limitations": [],
    }


def _contract_row(
    candidate: Mapping[str, Any],
    settlement: Mapping[str, Any],
    adjudication: Mapping[str, Any],
) -> dict[str, Any]:
    disposition = str(adjudication["disposition"])
    if disposition not in VALID_CONTRACT_DISPOSITIONS:
        raise ValueError(
            f"{candidate['war_event_id']} 合同处置非法: {disposition}"
        )
    registered = disposition == "REGISTERED_CONTRACT"
    tier = adjudication.get("campaign_tier")
    if registered and tier not in set(TIER_BY_RESULT_CLASS.values()):
        raise ValueError(
            f"{candidate['war_event_id']} 合同登记缺少合法campaign_tier"
        )
    if not registered and tier is not None:
        raise ValueError(
            f"{candidate['war_event_id']} 非登记处置不得携带campaign_tier"
        )
    if registered:
        result_class = adjudication.get("result_class")
        if TIER_BY_RESULT_CLASS.get(str(result_class)) != tier:
            raise ValueError(
                f"{candidate['war_event_id']} 结果类别与档位不一致: "
                f"{result_class}/{tier}"
            )
        field_contracts = {
            "land_strategic_value": VALID_LAND_AXIS,
            "opponent_strategic_weight": VALID_OPPONENT_WEIGHT,
            "opponent_condition": VALID_OPPONENT_CONDITION,
            "battle_result": VALID_BATTLE_RESULT,
            "objective_completion": VALID_OBJECTIVE_COMPLETION,
        }
        for field_name, allowed in field_contracts.items():
            if adjudication.get(field_name) not in allowed:
                raise ValueError(
                    f"{candidate['war_event_id']} 合同字段非法或缺失: "
                    f"{field_name}={adjudication.get(field_name)}"
                )
        if (
            adjudication.get("opponent_force_effect") is not None
            and adjudication.get("opponent_force_effect")
            not in VALID_OPPONENT_FORCE_EFFECT
        ):
            raise ValueError(
                f"{candidate['war_event_id']} 合同敌军战力结果轴非法: "
                f"{adjudication.get('opponent_force_effect')}"
            )
        force_effect = adjudication.get("opponent_force_effect")
        if force_effect is not None and (
            f"敌军轴={force_effect}"
            not in str(adjudication.get("tier_basis") or "")
            or (
                force_effect
                in {
                    "major_degradation",
                    "main_force_destroyed",
                    "military_system_collapsed",
                }
                and (
                    adjudication.get("battle_result")
                    not in {"victory", "mixed"}
                    or adjudication.get("objective_completion")
                    not in {"complete", "partial"}
                )
            )
        ):
            raise ValueError(
                f"{candidate['war_event_id']} 敌军战力结果轴与结果或档位依据矛盾"
            )
        _validate_external_hegemony_terminal_assessment(
            war_event_id=str(candidate["war_event_id"]),
            fields=adjudication,
            assessment=adjudication.get(
                "external_hegemony_terminal_assessment"
            ),
            prewar_assessment=adjudication.get(
                "external_hegemony_prewar_assessment"
            ),
        )
        _validate_residual_opponent_result_ceiling(
            war_event_id=str(candidate["war_event_id"]),
            fields=adjudication,
        )
        _validate_land_axis_basis(
            war_event_id=str(candidate["war_event_id"]),
            fields=adjudication,
        )
        _validate_internal_independent_direction_scale(
            war_event_id=str(candidate["war_event_id"]),
            fields=adjudication,
        )
        _validate_single_pole_decisive_defeat(
            war_event_id=str(candidate["war_event_id"]),
            fields=adjudication,
        )
        if not adjudication.get("source_refs"):
            raise ValueError(
                f"{candidate['war_event_id']} 合同登记缺少source_refs"
            )
        if not adjudication.get("observable_result"):
            raise ValueError(
                f"{candidate['war_event_id']} 合同登记缺少observable_result"
            )
        if not adjudication.get("tier_basis"):
            raise ValueError(
                f"{candidate['war_event_id']} 合同登记缺少tier_basis"
            )
        detail_fields = (
            adjudication.get("combat_difficulty"),
            adjudication.get("combat_difficulty_basis"),
            adjudication.get("campaign_command_topology"),
            adjudication.get("members"),
        )
        if any(value is not None for value in detail_fields):
            if adjudication.get("combat_difficulty") not in VALID_COMBAT_DIFFICULTY:
                raise ValueError(
                    f"{candidate['war_event_id']} 合同人物展开缺少合法combat_difficulty"
                )
            if not adjudication.get("combat_difficulty_basis"):
                raise ValueError(
                    f"{candidate['war_event_id']} 合同人物展开缺少combat_difficulty_basis"
                )
            if adjudication.get("campaign_command_topology") not in VALID_COMMAND_TOPOLOGY:
                raise ValueError(
                    f"{candidate['war_event_id']} 合同人物展开缺少合法campaign_command_topology"
                )
            if adjudication.get("ruler_role_status") not in VALID_RULER_ROLE_STATUS:
                raise ValueError(
                    f"{candidate['war_event_id']} 合同人物展开缺少合法ruler_role_status"
                )
            if not adjudication.get("ruler_role_basis"):
                raise ValueError(
                    f"{candidate['war_event_id']} 合同人物展开缺少ruler_role_basis"
                )
            members = adjudication.get("members")
            if not isinstance(members, list):
                raise ValueError(
                    f"{candidate['war_event_id']} 合同人物展开members必须为列表"
                )
            for member in members:
                required_member_fields = (
                    "actor_kind",
                    "actor_name",
                    "actor_ref",
                    "role_code",
                    "contribution_scope",
                )
                if not isinstance(member, Mapping) or any(
                    not member.get(field) for field in required_member_fields
                ):
                    raise ValueError(
                        f"{candidate['war_event_id']} 合同人物展开member字段不完整"
                    )
                actor_prefix = (
                    "RULER-BATTLE"
                    if member.get("actor_kind") == "ruler"
                    else "PER-BATTLE"
                )
                expected_actor_ref = canonical_hashed_ref(
                    actor_prefix,
                    f"{candidate['dynasty']}|{member['actor_name']}",
                    length=16,
                )
                if member.get("actor_ref") != expected_actor_ref:
                    raise ValueError(
                        f"{candidate['war_event_id']} 人物actor_ref不符合当前规范: "
                        f"{member.get('actor_name')}"
                    )
                if member.get("command_result_direction") not in {
                    None,
                    "positive",
                    "mixed_review",
                    "negative",
                }:
                    raise ValueError(
                        f"{candidate['war_event_id']} 人物指挥结果方向非法"
                    )
                strategic_relation = member.get("strategic_command_relation")
                if strategic_relation not in {None, "operational_direction"}:
                    raise ValueError(
                        f"{candidate['war_event_id']} 非皇帝战略控制关系非法"
                    )
                if strategic_relation is not None and (
                    member.get("actor_kind") == "ruler"
                    or member.get("role_code") != "not_in_command_chain"
                ):
                    raise ValueError(
                        f"{candidate['war_event_id']} 非皇帝战略统筹不得冒充前线指挥"
                    )
                if (
                    member.get("actor_kind") == "ruler"
                    and member.get("ruler_campaign_relation")
                    not in {
                        "authorization_only",
                        "operational_direction",
                        "frontline_command",
                    }
                ):
                    raise ValueError(
                        f"{candidate['war_event_id']} 皇帝成员缺少合法控制关系"
                    )
                if member.get("actor_kind") == "ruler":
                    relation = member.get("ruler_campaign_relation")
                    if (
                        relation == "authorization_only"
                        and member.get("role_code") != "not_in_command_chain"
                    ):
                        raise ValueError(
                            f"{candidate['war_event_id']} 仅授权皇帝不得进入指挥链"
                        )
                    if (
                        relation == "operational_direction"
                        and member.get("role_code") == "participant"
                    ):
                        raise ValueError(
                            f"{candidate['war_event_id']} 皇帝战略指导不得登记为从攻"
                        )
                    if (
                        relation == "frontline_command"
                        and member.get("role_code")
                        not in {"commander_in_chief", "principal_commander"}
                    ):
                        raise ValueError(
                            f"{candidate['war_event_id']} 皇帝亲征必须处于最高实际指挥层"
                        )
                person_result = member.get("person_command_result")
                _validate_talent_method_validation(
                    war_event_id=str(candidate["war_event_id"]),
                    member=member,
                    source_refs=list(adjudication.get("source_refs") or ()),
                )
                if person_result is not None:
                    person_results = (
                        person_result if isinstance(person_result, list) else [person_result]
                    )
                    if not person_results:
                        raise ValueError(f"{candidate['war_event_id']} 人物子成果列表不得为空")
                    result_refs: set[str] = set()
                    tier_order = ("C", "B", "A", "S-", "S", "S+")
                    for result in person_results:
                        result_contribution = (
                            result.get("military_capability_contribution")
                            if isinstance(result, Mapping)
                            else None
                        )
                        if not isinstance(result_contribution, Mapping):
                            result_contribution = member.get(
                                "military_capability_contribution"
                            )
                        is_operational_result = (
                            isinstance(result_contribution, Mapping)
                            and result_contribution.get("capability_mode")
                            == "operational_design"
                        )
                        if (
                                not isinstance(result, Mapping)
                            or (
                                member.get("role_code")
                                not in {
                                    "commander_in_chief",
                                    "principal_commander",
                                    "participant",
                                }
                                and not (
                                    is_operational_result
                                    and member.get("role_code")
                                    == "not_in_command_chain"
                                )
                            )
                            or result.get("result_direction")
                            not in {"positive", "mixed_review", "negative"}
                            or result.get("result_tier")
                            not in {"C", "B", "A", "S-", "S", "S+"}
                                or (
                                    result.get("combat_difficulty")
                                    not in VALID_COMBAT_DIFFICULTY
                                    and not (
                                        is_operational_result
                                        and result.get("combat_difficulty") is None
                                    )
                                )
                            or not result.get("basis")
                            or not result.get("source_refs")
                        ):
                            raise ValueError(
                                f"{candidate['war_event_id']} 人物子成果字段不完整或非法"
                            )
                        if isinstance(person_result, list):
                            result_ref = str(result.get("result_ref") or "")
                            if not result_ref or not result.get("result_label"):
                                raise ValueError(
                                    f"{candidate['war_event_id']} 多项人物子成果必须提供result_ref/result_label"
                                )
                            if result_ref in result_refs:
                                raise ValueError(
                                    f"{candidate['war_event_id']} 人物子成果result_ref重复: {result_ref}"
                                )
                            result_refs.add(result_ref)
                        declared_direction = member.get("command_result_direction")
                        result_direction = result.get("result_direction")
                        if isinstance(person_result, list):
                            list_directions = {
                                item.get("result_direction") for item in person_results
                            }
                            expected_direction = (
                                next(iter(list_directions))
                                if len(list_directions) == 1
                                else "mixed_review"
                            )
                        else:
                            expected_direction = result_direction
                        if declared_direction and declared_direction != expected_direction:
                            raise ValueError(
                                f"{candidate['war_event_id']} 人物子成果与指挥结果方向矛盾"
                            )
                        if not set(result["source_refs"]).issubset(
                            set(adjudication.get("source_refs") or ())
                        ):
                            raise ValueError(
                                f"{candidate['war_event_id']} 人物子成果史源越界"
                            )
                        child_tier_index = tier_order.index(result["result_tier"])
                        parent_tier_index = tier_order.index(tier)
                        if child_tier_index > parent_tier_index:
                            parent_direction = {
                                "victory": "positive",
                                "defeat": "negative",
                                "mixed": "mixed_review",
                            }.get(str(adjudication.get("battle_result")))
                            independently_adjudicated_opposed_result = (
                                adjudication.get("campaign_command_topology")
                                == "opposed_commands"
                                and member.get("command_side")
                                and member.get("command_result_direction")
                                == result.get("result_direction")
                                and result.get("result_direction") != parent_direction
                            )
                            if not independently_adjudicated_opposed_result:
                                raise ValueError(
                                    f"{candidate['war_event_id']} 人物子成果不得高于父结果档位；"
                                    "仅敌对指挥链的反向人物结果允许独立定级"
                                )
            failures = adjudication.get("attributable_failures")
            if failures is not None and not isinstance(failures, list):
                raise ValueError(
                    f"{candidate['war_event_id']} attributable_failures必须为列表"
                )
            for failure in failures or ():
                if (
                    not isinstance(failure, Mapping)
                    or failure.get("actor_kind", "person")
                    not in {"person", "ruler"}
                    or not failure.get("actor_name")
                    or not failure.get("actor_ref")
                    or not failure.get("basis")
                    or failure.get("responsibility")
                    not in VALID_FAILURE_RESPONSIBILITY
                    or failure.get("severity_index")
                    not in VALID_FAILURE_SEVERITY
                    or failure.get("failure_domain", "command_failure")
                    not in VALID_FAILURE_DOMAIN
                    or (
                        failure.get("failure_impact_tier") is not None
                        and failure.get("failure_impact_tier")
                        not in {"C", "B", "A", "S-", "S", "S+"}
                    )
                    or not failure.get("source_refs")
                ):
                    raise ValueError(
                        f"{candidate['war_event_id']} 可归责失败字段不完整或非法"
                    )
                matching_member = next(
                    (
                        member
                        for member in members
                        if member.get("actor_name") == failure.get("actor_name")
                    ),
                    None,
                )
                failure_prefix = (
                    "RULER-BATTLE"
                    if failure.get("actor_kind") == "ruler"
                    or (
                        matching_member
                        and matching_member.get("actor_kind") == "ruler"
                    )
                    else "PER-BATTLE"
                )
                expected_failure_ref = canonical_hashed_ref(
                    failure_prefix,
                    f"{candidate['dynasty']}|{failure['actor_name']}",
                    length=16,
                )
                if failure.get("actor_ref") != expected_failure_ref:
                    raise ValueError(
                        f"{candidate['war_event_id']} 失败人物actor_ref不符合当前规范: "
                        f"{failure.get('actor_name')}"
                    )
            institutional_default_rulers = [
                member
                for member in members
                if member.get("actor_kind") == "ruler"
                and member.get("authorization_mode") == "institutional_default"
            ]
            for member in institutional_default_rulers:
                if tier not in {"C", "B", "A"}:
                    raise ValueError(
                        f"{candidate['war_event_id']} S-以上不得使用皇帝制度性默认授权"
                    )
                if (
                    member.get("role_code") != "not_in_command_chain"
                    or member.get("ruler_campaign_relation")
                    != "authorization_only"
                    or "制度性默认" not in str(adjudication.get("ruler_role_basis"))
                ):
                    raise ValueError(
                        f"{candidate['war_event_id']} 皇帝制度性默认授权不得进入指挥链"
                    )
                if any(
                    failure.get("actor_ref") == member.get("actor_ref")
                    for failure in failures or ()
                ):
                    raise ValueError(
                        f"{candidate['war_event_id']} 皇帝制度性默认授权不得单独承接失败"
                    )
    if disposition == "MERGED_INTO_PARENT" and not adjudication.get(
        "merged_into"
    ):
        raise ValueError(
            f"{candidate['war_event_id']} 合并处置缺少merged_into"
        )
    result_direction = {
        "victory": "positive",
        "mixed": "mixed",
        "defeat": "negative",
        "unclear": "mixed",
    }.get(str(adjudication.get("battle_result")))
    adjudicated_period = adjudication.get("period")
    if adjudicated_period is not None and (
        not isinstance(adjudicated_period, Mapping)
        or not adjudicated_period.get("start")
        or not adjudicated_period.get("end")
    ):
        raise ValueError(
            f"{candidate['war_event_id']} 合同period必须同时包含start/end"
        )
    period = adjudicated_period or {
        "start": _first_text(candidate.get("time_ranges"))
        or "通读卡未精确拆分",
        "end": _first_text(candidate.get("time_ranges"))
        or "通读卡未精确拆分",
    }
    expanded_members: list[dict[str, Any]] = []
    if registered and adjudication.get("combat_difficulty"):
        for raw_member in adjudication.get("members") or ():
            member = dict(raw_member)
            person_result = member.get("person_command_result")
            if person_result:
                person_results = (
                    person_result if isinstance(person_result, list) else [person_result]
                )
                projected_result = max(
                    person_results,
                    key=lambda result: (
                        ("C", "B", "A", "S-", "S", "S+").index(result["result_tier"]),
                        (
                            ("D0", "D1", "D2", "D3", "D4").index(
                                result["combat_difficulty"]
                            )
                            if result.get("combat_difficulty") is not None
                            else -1
                        ),
                    ),
                )
                result_contribution = projected_result.get(
                    "military_capability_contribution"
                )
                if isinstance(result_contribution, Mapping):
                    capability_mode = str(
                        result_contribution.get("capability_mode") or "unresolved"
                    )
                    decisive_relation = str(
                        result_contribution.get("decisive_relation") or "unresolved"
                    )
                    if (
                        capability_mode not in _MILITARY_CAPABILITY_MODES
                        or decisive_relation not in _DECISIVE_RELATIONS
                        or (
                            capability_mode
                            in {
                                "operational_design",
                                "authorization_only",
                                "nominal_only",
                            }
                            and decisive_relation not in {"none", "unresolved"}
                        )
                    ):
                        raise ValueError(
                            f"{candidate['war_event_id']} 人物子成果军事贡献两轴非法"
                        )
                else:
                    capability_mode, decisive_relation, _, _ = (
                        _military_capability_contribution(member)
                    )
                    if capability_mode == "unresolved":
                        # 旧裁决在逐项复核前保持原可消费性，但角色不再是新合同的充分证据。
                        if member.get("role_code") == "commander_in_chief":
                            capability_mode = "integrated_command"
                            decisive_relation = "decisive_creator"
                        else:
                            capability_mode = "independent_direction"
                            decisive_relation = "co_decisive"
                explicit_full_parent = (
                    adjudication["campaign_command_topology"]
                    in {
                        "single_integrated_command",
                        "sequential_successor_command",
                    }
                    and capability_mode == "integrated_command"
                    and decisive_relation
                    in {"decisive_creator", "decisive_successor"}
                    and projected_result.get("result_direction") == "positive"
                    and projected_result.get("result_tier") == tier
                    and projected_result.get("combat_difficulty")
                    == adjudication["combat_difficulty"]
                )
                explicit_person_result_mode = projected_result.get(
                    "consumption_mode"
                )
                if explicit_person_result_mode not in {None, "person_result"}:
                    raise ValueError(
                        f"{candidate['war_event_id']} 人物子成果只允许显式降窄为person_result"
                    )
                operational_person_result = capability_mode == "operational_design"
                member["person_command_index"] = {
                    "consumption_mode": (
                        "person_result"
                        if explicit_person_result_mode == "person_result"
                        else "full_parent"
                        if explicit_full_parent
                        else "operational_result"
                        if operational_person_result
                        else "person_result"
                    ),
                    "command_scope": (
                        "independent_direction"
                        if explicit_person_result_mode == "person_result"
                        else "full_campaign"
                        if explicit_full_parent
                        else "operational_strategy"
                        if operational_person_result
                        else "opposed_full_campaign"
                        if adjudication["campaign_command_topology"] == "opposed_commands"
                        else "independent_direction"
                    ),
                    "capability_mode": capability_mode,
                    "decisive_relation": decisive_relation,
                    "result_direction": projected_result["result_direction"],
                    "projected_result_tier": projected_result["result_tier"],
                    "projected_combat_difficulty": projected_result[
                        "combat_difficulty"
                    ],
                    "detail_status": (
                        "operational_direction_resolved"
                        if operational_person_result
                        else "resolved_person_result"
                    ),
                    "basis": projected_result["basis"],
                    "source_refs": list(projected_result["source_refs"]),
                }
            else:
                member["person_command_index"] = derive_person_command_index(
                    member,
                    campaign_tier=str(tier),
                    combat_difficulty=str(adjudication["combat_difficulty"]),
                    battle_result=str(adjudication["battle_result"]),
                    source_refs=list(adjudication.get("source_refs") or ()),
                    attributable_failures=list(
                        adjudication.get("attributable_failures") or ()
                    ),
                    campaign_command_topology=str(
                        adjudication["campaign_command_topology"]
                    ),
                )
            expanded_members.append(member)
        _validate_campaign_command_topology(
            Path("contract-adjudications"),
            str(candidate["war_event_id"]),
            adjudication["campaign_command_topology"],
            expanded_members,
        )
        military_leads = [
            member
            for member in expanded_members
            if member.get("role_code")
            in {"commander_in_chief", "principal_commander"}
        ]
        if (
            tier in {"S-", "S", "S+"}
            or adjudication["combat_difficulty"] in {"D3", "D4"}
        ) and not military_leads:
            raise ValueError(
                f"{candidate['war_event_id']} 高价值战役缺少明确军事负责人"
            )
        if tier in {"S-", "S", "S+"}:
            uncredited_commanders = [
                member.get("actor_name")
                for member in expanded_members
                if member.get("role_code") == "commander_in_chief"
                and (
                    member["person_command_index"].get("consumption_mode") == "none"
                    or member["person_command_index"].get("command_scope")
                    == "no_person_command_credit"
                )
            ]
            if uncredited_commanders:
                raise ValueError(
                    f"{candidate['war_event_id']} S-以上实质主帅不得悬空人物指挥信用: "
                    + "、".join(str(name) for name in uncredited_commanders)
                )
        ruler_members = [
            member
            for member in expanded_members
            if member.get("actor_kind") == "ruler"
        ]
        if adjudication["ruler_role_status"] == "resolved" and not ruler_members:
            raise ValueError(
                f"{candidate['war_event_id']} 皇帝角色已闭合但缺少ruler成员"
            )
        if adjudication["ruler_role_status"] == "unresolved" and ruler_members:
            raise ValueError(
                f"{candidate['war_event_id']} 皇帝角色未闭合时不得补造ruler成员"
            )
    return {
        "war_event_id": candidate["war_event_id"],
        "dynasty": candidate["dynasty"],
        "disposition": disposition,
        "public_outcome_registered": registered,
        "canonical_label": adjudication.get("canonical_label")
        or _first_text(candidate.get("titles"))
        or candidate["war_event_id"],
        "period": period,
        "observable_result": adjudication.get("observable_result")
        or _candidate_result(candidate),
        "result_direction": result_direction if registered else None,
        "campaign_tier": tier,
        "result_class": adjudication.get("result_class"),
        "land_strategic_value": adjudication.get(
            "land_strategic_value"
        ),
        "opponent_strategic_weight": adjudication.get(
            "opponent_strategic_weight"
        ),
        "opponent_condition": adjudication.get("opponent_condition"),
        "battle_result": adjudication.get("battle_result"),
        "objective_completion": adjudication.get(
            "objective_completion"
        ),
        "objective_shortfalls": (
            list(adjudication.get("objective_shortfalls") or ())
            if registered
            else []
        ),
        "opponent_force_effect": adjudication.get(
            "opponent_force_effect"
        ),
        "external_hegemony_prewar_assessment": adjudication.get(
            "external_hegemony_prewar_assessment"
        ),
        "external_hegemony_terminal_assessment": adjudication.get(
            "external_hegemony_terminal_assessment"
        ),
        "tier_basis": adjudication.get("tier_basis") if registered else None,
        "combat_difficulty": (
            adjudication.get("combat_difficulty")
            if registered and adjudication.get("combat_difficulty")
            else "D_NOT_REQUIRED"
        ),
        "combat_difficulty_basis": (
            adjudication.get("combat_difficulty_basis")
            if registered
            else None
        ),
        "command_status": (
            "DETAIL_COMPLETE"
            if registered and adjudication.get("combat_difficulty")
            else "PARENT_RESULT_ONLY"
            if registered
            else "NOT_REQUIRED"
        ),
        "campaign_command_topology": (
            adjudication.get("campaign_command_topology")
            if registered and adjudication.get("combat_difficulty")
            else "NOT_REQUIRED_FOR_PARENT_ONLY"
            if registered
            else None
        ),
        "ruler_role_status": (
            adjudication.get("ruler_role_status")
            if registered and adjudication.get("combat_difficulty")
            else "REQUIRED"
            if registered
            else "NOT_APPLICABLE"
        ),
        "ruler_role_basis": (
            adjudication.get("ruler_role_basis")
            if registered and adjudication.get("combat_difficulty")
            else None
        ),
        "members": expanded_members,
        "attributable_failures": (
            list(adjudication.get("attributable_failures") or ())
            if registered and adjudication.get("combat_difficulty")
            else []
        ),
        "detail_expansion_status": (
            "COMPLETE"
            if registered and adjudication.get("combat_difficulty")
            else "REQUIRED_BEFORE_GOLD_OR_TALENT_CONSUMPTION"
            if registered
            else "NOT_APPLICABLE"
        ),
        "wc_grade": settlement.get("wc_consistency_grade")
        or (settlement.get("cost_axes") or {}).get("WC"),
        "security_grade": settlement.get("strategic_security_grade"),
        "source_lineage": _source_lineage(candidate),
        "source_refs": list(adjudication.get("source_refs") or ()),
        "basis": adjudication.get("reason")
        or adjudication.get("basis")
        or adjudication.get("tier_basis"),
        "merged_into": adjudication.get("merged_into"),
        "limitations": (
            [
                "人物归责、指挥拓扑与D轴后置；父结果不得整体复制给单个人物。"
            ]
            if registered and not adjudication.get("combat_difficulty")
            else []
        ),
        "contract_adjudication": True,
    }


def build_battle_parent_contract_registry(
    *,
    worklist: Mapping[str, Any],
    ordinary_adjudications: Mapping[str, Any],
    military_settlements: Mapping[str, Mapping[str, Any]],
    contract_adjudications: Mapping[str, Any],
) -> dict[str, Any]:
    adjudications = {
        str(row["war_event_id"]): row
        for row in ordinary_adjudications.get("adjudications") or ()
    }
    ordinary_candidates = [
        candidate
        for candidate in worklist.get("candidates") or ()
        if "UNIFICATION_ONLY" not in set(candidate.get("account_routing") or ())
    ]
    candidate_ids = {str(row["war_event_id"]) for row in ordinary_candidates}
    extra_adjudications = set(adjudications) - candidate_ids
    if extra_adjudications:
        raise ValueError(
            "普通裁决包含不属于当前普通候选的战役: "
            f"candidates={len(ordinary_candidates)}, "
            f"extra={sorted(extra_adjudications)}"
        )
    contract_rows = {
        str(row["war_event_id"]): row
        for row in contract_adjudications.get("adjudications") or ()
    }
    if len(contract_rows) != len(
        contract_adjudications.get("adjudications") or ()
    ):
        raise ValueError("父战役合同裁决存在重复war_event_id")
    contract_extra = set(contract_rows) - candidate_ids
    if contract_extra:
        raise ValueError(
            f"父战役合同裁决包含非普通候选: {sorted(contract_extra)}"
        )
    preclosed_statuses = {FORMAL_STATUS, *_TERMINAL_DISPOSITIONS.keys()}
    expected_contract_ids = {
        str(candidate["war_event_id"])
        for candidate in ordinary_candidates
        if str(
            adjudications.get(
                str(candidate["war_event_id"]),
                {"status": "NO_PRIOR_ORDINARY_ADJUDICATION"},
            )["status"]
        )
        not in preclosed_statuses
    }
    contract_missing = expected_contract_ids - set(contract_rows)
    contract_unexpected = set(contract_rows) - expected_contract_ids
    if contract_missing or contract_unexpected:
        raise ValueError(
            "父战役合同裁决与当前待裁集合不一致: "
            f"missing={sorted(contract_missing)}, "
            f"unexpected={sorted(contract_unexpected)}"
        )

    records: list[dict[str, Any]] = []
    for candidate in sorted(
        ordinary_candidates, key=lambda row: str(row["war_event_id"])
    ):
        event_id = str(candidate["war_event_id"])
        adjudication = adjudications.get(
            event_id,
            {
                "war_event_id": event_id,
                "status": "NO_PRIOR_ORDINARY_ADJUDICATION",
                "basis": "现有战争卡已进入普通三账路由，但旧普通裁决表尚无单列。",
            },
        )
        settlement = military_settlements.get(event_id) or {}
        status = str(adjudication["status"])
        if status == FORMAL_STATUS:
            records.append(_full_row(candidate, adjudication, settlement))
            continue
        contract_adjudication = contract_rows.get(event_id)
        if contract_adjudication is not None:
            if contract_adjudication.get("disposition") == "SPLIT_CAMPAIGN_PORTFOLIO":
                split_campaigns = contract_adjudication.get("split_campaigns")
                if not isinstance(split_campaigns, list) or len(split_campaigns) < 2:
                    raise ValueError(f"{event_id} 战争组合至少需要两个独立战役群")
                split_ids: set[str] = set()
                assigned_child_cards: set[str] = set()
                assigned_source_partitions: set[str] = set()
                source_card_use_counts = Counter(
                    str(source_card_id)
                    for child in split_campaigns
                    for source_card_id in (child.get("source_card_ids") or ())
                )
                parent_card_ids = set(candidate.get("source_card_ids") or ())
                parent_files = set(candidate.get("source_files") or ())
                parent_revisions = set(candidate.get("source_revision_refs") or ())
                portfolio_record = _contract_row(
                    candidate,
                    settlement,
                    contract_adjudication,
                )
                portfolio_record["split_campaign_ids"] = [
                    str(child.get("war_event_id") or "") for child in split_campaigns
                ]
                records.append(portfolio_record)
                for child in split_campaigns:
                    child_id = str(child.get("war_event_id") or "")
                    child_cards = set(child.get("source_card_ids") or ())
                    child_files = set(child.get("source_files") or ())
                    child_revisions = set(child.get("source_revision_refs") or ())
                    source_partition = str(child.get("source_partition") or "")
                    overlapping_cards = child_cards & assigned_child_cards
                    reuses_source_card = any(
                        source_card_use_counts[source_card_id] > 1
                        for source_card_id in child_cards
                    )
                    if (
                        not child_id
                        or child_id in split_ids
                        or child_id in candidate_ids
                        or not child_cards
                        or (reuses_source_card and not source_partition)
                        or (
                            bool(overlapping_cards)
                            and (
                                not source_partition
                                or source_partition in assigned_source_partitions
                            )
                        )
                        or not child_cards.issubset(parent_card_ids)
                        or not child_files.issubset(parent_files)
                        or not child_revisions.issubset(parent_revisions)
                    ):
                        raise ValueError(f"{event_id} 拆分战役群边界或lineage非法: {child_id}")
                    split_ids.add(child_id)
                    assigned_child_cards.update(child_cards)
                    if source_partition:
                        assigned_source_partitions.add(source_partition)
                    synthetic_candidate = {
                        **candidate,
                        "war_event_id": child_id,
                        "source_card_ids": sorted(child_cards),
                        "source_files": sorted(child_files),
                        "source_revision_refs": sorted(child_revisions),
                    }
                    split_record = _contract_row(
                        synthetic_candidate,
                        {},
                        {**child, "disposition": "REGISTERED_CONTRACT"},
                    )
                    split_record["war_portfolio_ref"] = event_id
                    records.append(split_record)
            else:
                records.append(
                    _contract_row(
                        candidate,
                        settlement,
                        contract_adjudication,
                    )
                )
            continue

        disposition = _TERMINAL_DISPOSITIONS.get(status)
        if disposition is not None:
            records.append(
                {
                    "war_event_id": event_id,
                    "dynasty": candidate["dynasty"],
                    "disposition": disposition,
                    "public_outcome_registered": False,
                    "canonical_label": _first_text(candidate.get("titles"))
                    or event_id,
                    "observable_result": _candidate_result(candidate),
                    "campaign_tier": None,
                    "combat_difficulty": "D_NOT_REQUIRED",
                    "command_status": "NOT_REQUIRED",
                    "wc_grade": settlement.get("wc_consistency_grade")
                    or (settlement.get("cost_axes") or {}).get("WC"),
                    "security_grade": settlement.get("strategic_security_grade"),
                    "source_lineage": _source_lineage(candidate),
                    "basis": adjudication.get("basis"),
                    "limitations": [],
                }
            )
            continue

        raise ValueError(f"{event_id} 缺少合同裁决: previous_status={status}")

    for record in records:
        for member in record.get("members") or ():
            _normalize_person_command_index(member)
        if record.get("public_outcome_registered"):
            _validate_problem_difficulty(
                war_event_id=str(record["war_event_id"]),
                fields=record,
            )

    records_by_id = {
        str(record["war_event_id"]): record for record in records
    }
    if len(records_by_id) != len(records):
        raise ValueError("父战役合同生成结果存在重复war_event_id")
    for record in records:
        if (
            record.get("contract_adjudication")
            and record["disposition"] == "MERGED_INTO_PARENT"
        ):
            parent_id = str(record["merged_into"])
            parent = records_by_id.get(parent_id)
            if (
                parent_id == record["war_event_id"]
                or parent is None
                or not parent["public_outcome_registered"]
            ):
                raise ValueError(
                    f"{record['war_event_id']} 合并父项未闭合: {parent_id}"
                )
            parent.setdefault("absorbed_event_ids", []).append(
                str(record["war_event_id"])
            )
            parent_lineage = parent["source_lineage"]
            child_lineage = record["source_lineage"]
            for lineage_field in (
                "source_card_ids",
                "source_files",
                "source_revision_refs",
            ):
                parent_lineage[lineage_field] = sorted(
                    set(parent_lineage.get(lineage_field) or ())
                    | set(child_lineage.get(lineage_field) or ())
                )
    for record in records:
        if record.get("absorbed_event_ids"):
            record["absorbed_event_ids"] = sorted(record["absorbed_event_ids"])

    dispositions = Counter(str(row["disposition"]) for row in records)
    tier_counts = Counter(
        str(row["campaign_tier"])
        for row in records
        if row.get("campaign_tier")
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "evidence_maturity": EVIDENCE_MATURITY,
        "formal_score_write": False,
        "ordinary_candidate_count": len(ordinary_candidates),
        "ordinary_record_count": len(records),
        "prior_adjudication_count": len(adjudications),
        "new_direct_compile_count": len(candidate_ids - set(adjudications)),
        "contract_adjudication_count": len(contract_rows),
        "pending_count": 0,
        "public_outcome_count": sum(
            bool(row["public_outcome_registered"]) for row in records
        ),
        "disposition_counts": dict(sorted(dispositions.items())),
        "tier_counts": dict(sorted(tier_counts.items())),
        "records": records,
    }
    payload["semantic_fingerprint"] = _digest(payload)
    return payload


def render_battle_parent_contract_registry_markdown(
    payload: Mapping[str, Any],
) -> str:
    lines = [
        "# 秦至唐父战役合同总登记",
        "",
        "本表合并普通父战役与六条开国统一链；普通候选未能闭合三轴者进入"
        "证据终态、合并或转域，统一链同时保留正式战役群和中性上下文节点。",
        "",
        f"- 普通候选：{payload['ordinary_candidate_count']}",
        f"- 普通登记父结果：{payload.get('ordinary_public_outcome_count', payload['public_outcome_count'])}",
        f"- 统一链正式结果：{payload.get('unification_public_outcome_count', 0)}",
        f"- 正式结果合计：{payload['public_outcome_count']}",
        f"- 待审：{payload['pending_count']}",
        "",
        "## 处置统计",
        "",
        "| 处置 | 数量 |",
        "| --- | ---: |",
    ]
    for disposition, count in payload["disposition_counts"].items():
        lines.append(f"| `{disposition}` | {count} |")
    lines.extend(
        [
            "",
            "## 战役等级统计",
            "",
            "| 等级 | 数量 |",
            "| --- | ---: |",
        ]
    )
    for tier, count in payload["tier_counts"].items():
        lines.append(f"| {tier} | {count} |")
    lines.extend(
        [
            "",
            "## 全量登记",
            "",
            "| 战役ID | 朝代 | 处置 | 等级 | D | 结果 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["records"]:
        result = str(row.get("observable_result") or "—").replace("|", "｜")
        lines.append(
            f"| `{row['war_event_id']}` | {row['dynasty']} | "
            f"`{row['disposition']}` | {row.get('campaign_tier') or '—'} | "
            f"{row['combat_difficulty']} | {result} |"
        )
    if payload.get("unification_portfolios"):
        lines.extend(["", "## 开国统一链", ""])
        for portfolio in payload["unification_portfolios"]:
            lines.extend(
                [
                    f"### `{portfolio['portfolio_ref']}`",
                    "",
                    "| 战役群 | 登记角色 | 等级 | D | 结果 |",
                    "| --- | --- | --- | --- | --- |",
                ]
            )
            for group in portfolio.get("campaign_groups") or []:
                group_payload = group.get("payload") or {}
                result = str(
                    group_payload.get("strategic_objective")
                    or group.get("basis")
                    or "—"
                ).replace("|", "｜")
                lines.append(
                    f"| `{group['campaign_group_id']}` | "
                    f"`{group['registration_role']}` | "
                    f"{group_payload.get('campaign_tier') or '—'} | "
                    f"{group_payload.get('combat_difficulty') or '—'} | {result} |"
                )
    lines.extend(
        ["", "## 指纹", "", f"`{payload['semantic_fingerprint']}`", ""]
    )
    return "\n".join(lines)


def _merge_unification_registry(
    ordinary_payload: Mapping[str, Any],
    unification_payload: Mapping[str, Any],
    *,
    scope_payload: Mapping[str, Any] | None = None,
    dynasty_by_war_event: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    dynasty_by_portfolio = {
        "UCP-QIN-YINGZHENG-230-221": "秦",
        "UCP-HAN-LIUBANG-BCE207-BCE202": "汉",
        "UCP-HAN-LIUXIU-23-36": "东汉",
        "UCP-JIN-SIMAYAN-279-280": "两晋",
        "UCP-SUI-YANGJIAN-587-591": "隋",
        "UCP-TANG-LIYUAN-617-628": "唐",
    }
    portfolios = list(unification_payload.get("adjudications") or [])
    unification_records: list[dict[str, Any]] = []
    unification_tiers: Counter[str] = Counter()
    for portfolio in portfolios:
        portfolio_ref = str(portfolio["portfolio_ref"])
        dynasty = str(
            portfolio.get("dynasty")
            or dynasty_by_portfolio.get(portfolio_ref, "未知")
        )
        for group in portfolio.get("campaign_groups") or []:
            group_payload = group.get("payload") or {}
            registered = group.get("registration_role") == "CAMPAIGN_GROUP"
            tier = group_payload.get("campaign_tier") if registered else None
            if tier:
                unification_tiers[str(tier)] += 1
            members: list[dict[str, Any]] = []
            for raw_member in group.get("members") or []:
                member = dict(raw_member)
                existing_index = member.get("person_command_index")
                if registered and isinstance(existing_index, Mapping):
                    _normalize_person_command_index(member)
                if (
                    registered
                    and member.get("actor_kind") == "ruler"
                    and member.get("ruler_campaign_relation")
                    == "operational_direction"
                    and member.get("role_code") == "not_in_command_chain"
                    and not member.get("person_command_result")
                ):
                    member["person_command_index"] = derive_person_command_index(
                        member,
                        campaign_tier=str(tier),
                        combat_difficulty=str(
                            group_payload.get("combat_difficulty")
                        ),
                        battle_result=str(group_payload.get("battle_result")),
                        source_refs=list(group.get("source_refs") or ()),
                        attributable_failures=list(
                            group_payload.get("attributable_failures") or ()
                        ),
                        campaign_command_topology=str(
                            group.get("campaign_command_topology")
                        ),
                    )
                members.append(member)
            unification_records.append(
                {
                    "war_event_id": group["campaign_group_id"],
                    "dynasty": dynasty,
                    "disposition": (
                        "REGISTERED_UNIFICATION"
                        if registered
                        else str(group.get("registration_role") or "UNIFICATION_CONTEXT")
                    ),
                    "public_outcome_registered": registered,
                    "canonical_label": group_payload.get("strategic_objective")
                    or group["campaign_group_id"],
                    "period": {"start": "未知", "end": "未知"},
                    "observable_result": group.get("basis")
                    or group_payload.get("strategic_objective"),
                    "result_direction": group_payload.get("battle_result"),
                    "campaign_tier": tier,
                    "result_class": group_payload.get("strategic_result_class"),
                    "land_strategic_value": group_payload.get("land_strategic_value"),
                    "opponent_strategic_weight": group_payload.get("opponent_strategic_weight"),
                    "opponent_condition": group_payload.get("opponent_condition"),
                    "battle_result": group_payload.get("battle_result"),
                    "objective_completion": group_payload.get("objective_completion"),
                    "objective_shortfalls": list(
                        group_payload.get("objective_shortfalls") or []
                    ),
                    "opponent_force_effect": group_payload.get(
                        "opponent_force_effect"
                    ),
                    "tier_basis": group_payload.get("campaign_tier_basis"),
                    "combat_difficulty": group_payload.get("combat_difficulty")
                    or "D_NOT_REQUIRED",
                    "combat_difficulty_basis": group_payload.get("combat_difficulty_basis"),
                    "command_status": "UNIFICATION_CONTRACT" if registered else "NOT_REQUIRED",
                    "campaign_command_topology": group.get("campaign_command_topology"),
                    "ruler_role_status": "resolved"
                    if any(member.get("sovereign_at_event") for member in members)
                    else "unresolved",
                    "ruler_role_basis": group.get("basis"),
                    "members": members,
                    "attributable_failures": list(group_payload.get("attributable_failures") or []),
                    "detail_expansion_status": "COMPLETE" if registered else "NOT_APPLICABLE",
                    "wc_grade": None,
                    "security_grade": None,
                    "source_lineage": {
                        "source_card_ids": list(group.get("war_event_refs") or []),
                        "source_files": [],
                        "source_revision_refs": [],
                        "lineage_basis": "开国统一链合同裁决。",
                    },
                    "source_refs": list(group.get("source_refs") or []),
                    "basis": group.get("basis"),
                    "merged_into": None,
                    "limitations": [],
                    "contract_adjudication": True,
                    "unification_portfolio_ref": portfolio_ref,
                }
            )
    covered_war_refs = {
        str(ref)
        for portfolio in portfolios
        for ref in portfolio.get("war_event_refs") or ()
    }
    unresolved_scope_records: list[dict[str, Any]] = []
    for scope in (scope_payload or {}).get("adjudications") or ():
        scope_kind = str(scope.get("scope_kind") or "")
        if scope_kind == "FULL_REALM_UNIFICATION":
            continue
        for raw_ref in scope.get("war_event_refs") or ():
            war_ref = str(raw_ref)
            if war_ref in covered_war_refs:
                continue
            unresolved_scope_records.append(
                {
                    "war_event_id": war_ref,
                    "dynasty": str(
                        (dynasty_by_war_event or {}).get(war_ref) or "未知"
                    ),
                    "disposition": (
                        "REGIONAL_TIER_ADJUDICATION_REQUIRED"
                        if scope_kind
                        in {"REGIONAL_REGIME_FOUNDATION", "REGIONAL_ANNEXATION"}
                        else "SCOPE_ROUTE_CORRECTION_REQUIRED"
                    ),
                    "public_outcome_registered": False,
                    "canonical_label": war_ref,
                    "period": {"start": "未知", "end": "未知"},
                    "observable_result": scope.get("basis"),
                    "result_direction": None,
                    "campaign_tier": None,
                    "result_class": None,
                    "combat_difficulty": "D_NOT_REQUIRED",
                    "command_status": "TIER_ADJUDICATION_REQUIRED",
                    "members": [],
                    "attributable_failures": [],
                    "detail_expansion_status": "REQUIRED_BEFORE_TALENT_CONSUMPTION",
                    "source_lineage": {
                        "source_card_ids": [war_ref],
                        "source_files": [],
                        "source_revision_refs": [],
                        "lineage_basis": "统一范围裁决已闭合，但档位与人物合同尚未完成；显式保留，禁止静默丢弃。",
                    },
                    "source_refs": [],
                    "basis": scope.get("basis"),
                    "limitations": [
                        "未完成统一侧档位与人物裁决前不得进入人才消费。"
                    ],
                    "contract_adjudication": False,
                    "unification_portfolio_ref": scope.get("portfolio_ref"),
                    "unification_scope_kind": scope_kind,
                }
            )
    combined = dict(ordinary_payload)
    ordinary_tiers = Counter(
        {str(key): int(value) for key, value in ordinary_payload["tier_counts"].items()}
    )
    combined_tiers = ordinary_tiers + unification_tiers
    ordinary_count = int(ordinary_payload["public_outcome_count"])
    unification_count = sum(
        bool(record["public_outcome_registered"]) for record in unification_records
    )
    combined.update(
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "ordinary_public_outcome_count": ordinary_count,
            "unification_campaign_group_count": len(unification_records),
            "unification_scope_unresolved_count": len(unresolved_scope_records),
            "unification_public_outcome_count": unification_count,
            "public_outcome_count": ordinary_count + unification_count,
            "ordinary_tier_counts": dict(sorted(ordinary_tiers.items())),
            "unification_tier_counts": dict(sorted(unification_tiers.items())),
            "tier_counts": dict(sorted(combined_tiers.items())),
            "unification_portfolios": portfolios,
            "records": (
                list(ordinary_payload["records"])
                + unification_records
                + unresolved_scope_records
            ),
        }
    )
    _validate_materialized_person_results(combined["records"])
    combined["semantic_fingerprint"] = _digest(combined)
    return combined


def _validate_materialized_person_results(
    records: Sequence[Mapping[str, Any]],
) -> None:
    """已结案的人物成果必须有实体，不能只靠轻量索引直接计分。"""

    tier_rank = {tier: rank for rank, tier in enumerate(("C", "B", "A", "S-", "S", "S+"))}
    for record in records:
        if not record.get("public_outcome_registered"):
            continue
        parent_tier = record.get("campaign_tier")
        for member in record.get("members") or ():
            index = member.get("person_command_index") or {}
            person_result = member.get("person_command_result")
            mode = index.get("consumption_mode")
            direction = index.get("result_direction")
            detail_status = index.get("detail_status")
            person_tier = index.get("projected_result_tier")
            if (
                mode == "full_parent"
                and direction == "positive"
                and parent_tier in tier_rank
                and person_tier in tier_rank
                and tier_rank[person_tier] > tier_rank[parent_tier]
            ):
                raise ValueError(
                    f"{record.get('war_event_id')} / {member.get('actor_name')} "
                    f"正向人物成果{person_tier}不得越过父级{parent_tier}"
                )
            missing_result = not person_result
            if missing_result and mode == "person_result":
                raise ValueError(
                    f"{record.get('war_event_id')} / {member.get('actor_name')} "
                    "person_result 缺少显式人物子成果"
                )
            if (
                missing_result
                and mode == "full_parent"
                and direction in {"negative", "mixed_review"}
                and detail_status == "resolved_person_result"
            ):
                raise ValueError(
                    f"{record.get('war_event_id')} / {member.get('actor_name')} "
                    "负向或混合父级消费缺少显式人物子成果"
                )
            if isinstance(person_result, Mapping):
                expected_pairs = (
                    ("result_direction", "result_direction"),
                    ("result_tier", "projected_result_tier"),
                )
                if mode != "operational_result":
                    expected_pairs += (
                        ("combat_difficulty", "projected_combat_difficulty"),
                    )
                for result_field, index_field in expected_pairs:
                    if person_result.get(result_field) != index.get(index_field):
                        raise ValueError(
                            f"{record.get('war_event_id')} / {member.get('actor_name')} "
                            f"人物成果与消费索引不一致: {result_field}"
                        )
                contribution_rows = [
                    value
                    for value in (
                        member.get("military_capability_contribution"),
                        person_result.get("military_capability_contribution"),
                        index,
                    )
                    if isinstance(value, Mapping)
                    and value.get("capability_mode") is not None
                ]
                for field in ("capability_mode", "decisive_relation"):
                    values = {
                        str(value.get(field))
                        for value in contribution_rows
                        if value.get(field) is not None
                    }
                    if len(values) > 1:
                        raise ValueError(
                            f"{record.get('war_event_id')} / {member.get('actor_name')} "
                            f"人物成果贡献轴不一致: {field}"
                        )
            record_source_refs = {
                str(value) for value in record.get("source_refs") or ()
            }
            lineage = record.get("source_lineage") or {}
            record_source_refs.update(
                str(value)
                for field in ("source_revision_refs", "source_files")
                for value in lineage.get(field) or ()
            )
            index_source_refs = {
                str(value) for value in index.get("source_refs") or ()
            }
            if (
                index_source_refs
                and record_source_refs
                and not index_source_refs.issubset(record_source_refs)
            ):
                raise ValueError(
                    f"{record.get('war_event_id')} / {member.get('actor_name')} "
                    "人物消费索引引用了父战役以外的史源"
                )


def write_battle_parent_contract_registry(
    workspace_root: Path,
) -> dict[str, Path]:
    worklist = json.loads(
        (
            workspace_root / "tmp/战役登记/公共成果候选/current.json"
        ).read_text(encoding="utf-8")
    )
    adjudications = json.loads(
        (
            workspace_root / "config/ordinary-campaign-adjudications.json"
        ).read_text(encoding="utf-8")
    )
    contract_adjudications = json.loads(
        (
            workspace_root
            / "config/battle-parent-contract-adjudications.json"
        ).read_text(encoding="utf-8")
    )
    settlements = load_military_settlements(
        workspace_root
        / "tmp/治理/正式底账/04-军事与边疆/02-成本收益结算/军事成本收益结算底账.jsonl"
    )
    payload = build_battle_parent_contract_registry(
        worklist=worklist,
        ordinary_adjudications=adjudications,
        military_settlements=settlements,
        contract_adjudications=contract_adjudications,
    )
    unification_payload = json.loads(
        (
            workspace_root
            / "config/unification-campaign-tier-adjudications.json"
        ).read_text(encoding="utf-8")
    )
    scope_payload = json.loads(
        (
            workspace_root
            / "config/unification-campaign-scope-adjudications.json"
        ).read_text(encoding="utf-8")
    )
    dynasty_by_war_event = {
        str(candidate["war_event_id"]): str(candidate.get("dynasty") or "未知")
        for candidate in worklist.get("candidates") or ()
    }
    payload = _merge_unification_registry(
        payload,
        unification_payload,
        scope_payload=scope_payload,
        dynasty_by_war_event=dynasty_by_war_event,
    )
    target = workspace_root / "docs/公共成果/军事"
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "01-秦至唐战役登记.json"
    markdown_path = target / "01-秦至唐战役登记.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_battle_parent_contract_registry_markdown(payload),
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": markdown_path}
