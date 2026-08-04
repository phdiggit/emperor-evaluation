from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


SCHEMA_VERSION = "military-talent-grade-registry-v3"
GRADE_ORDER = (
    "ordinary",
    "usable",
    "capable",
    "important",
    "elite",
    "top",
    "historic",
)
TIER_RANK = {"C": 1, "B": 2, "A": 3, "S-": 4, "S": 5, "S+": 6}
DIFFICULTY_RANK = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4}
STRATEGIC_WEIGHT = {"A": 1, "S-": 2, "S": 3, "S+": 4}
NET_TIER_VALUE = {"C": 0.15, "B": 0.4, "A": 1.0, "S-": 2.2, "S": 3.6, "S+": 6.0}
NET_DIFFICULTY_MULTIPLIER = {
    "D0": 0.55,
    "D1": 0.75,
    "D2": 1.0,
    "D3": 1.25,
    "D4": 1.55,
}
CONTRIBUTION_COEFFICIENT = {
    "decisive_creator": 1.0,
    "decisive_successor": 1.0,
    "co_decisive": 0.85,
    "terminal_finisher": 0.5,
    "stage_executor": 0.35,
}
FRONTLINE_DIMINISHING_WEIGHTS = (1.0, 0.65, 0.35, 0.2, 0.1, 0.05)
OPERATIONAL_DIMINISHING_WEIGHTS = (1.0, 0.6, 0.35, 0.2, 0.1, 0.05)
OPERATIONAL_RESULT_COEFFICIENT = 0.4
NEGATIVE_COMMAND_COEFFICIENT = 0.8
MIXED_COMMAND_COEFFICIENT = 0.4
DYNASTY_ORDER = {
    "秦": 1,
    "汉": 2,
    "东汉": 3,
    "三国": 4,
    "两晋": 5,
    "南北朝": 6,
    "隋": 7,
    "唐": 8,
}
DIRECT_MODES = {
    "full_parent",
    "scoped_projection",
    "person_result",
    "operational_result",
}
SUPPORT_MODES = {"joint_parent"}
OPERATIONAL_MODES = {"operational_result"}
ANCHOR_DECISIVE_RELATIONS = {
    "decisive_creator",
    "decisive_successor",
    "co_decisive",
}
REALIZED_DECISIVE_RELATIONS = ANCHOR_DECISIVE_RELATIONS | {
    "terminal_finisher",
    "stage_executor",
}
REALIZED_CAPABILITY_MODES = {
    "integrated_command",
    "independent_direction",
    "operational_design",
    "tactical_execution",
}
PENDING_PERSON_RESULT_STATUSES = {
    "person_result_required",
    "failure_review_required",
}


def _is_pending_person_result(row: Mapping[str, Any]) -> bool:
    return str(row.get("detail_status") or "") in PENDING_PERSON_RESULT_STATUSES


def _digest(payload: Mapping[str, Any]) -> str:
    return sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _person_key(dynasty: str, name: str) -> str:
    return f"MIL-PER-{sha256(f'{dynasty}|{name}'.encode('utf-8')).hexdigest()[:16].upper()}"


def _decisive_relation(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("decisive_relation") or "")
    if explicit:
        return explicit
    mode = str(row.get("consumption_mode") or "")
    return {
        "full_parent": "decisive_creator",
        "person_result": "co_decisive",
        "joint_parent": "co_decisive",
        "scoped_projection": "stage_executor",
        "operational_result": "none",
        "none": "none",
    }.get(mode, "unresolved")


def _capability_mode(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("capability_mode") or "")
    if explicit:
        return explicit
    mode = str(row.get("consumption_mode") or "")
    return {
        "full_parent": "integrated_command",
        "person_result": "independent_direction",
        "joint_parent": "integrated_command",
        "scoped_projection": "tactical_execution",
        "operational_result": "operational_design",
        "none": "nominal_only",
    }.get(mode, "unresolved")


def _is_anchor_result(row: Mapping[str, Any]) -> bool:
    return (
        _decisive_relation(row) in ANCHOR_DECISIVE_RELATIONS
        and _capability_mode(row)
        not in {"operational_design", "authorization_only", "nominal_only", "unresolved"}
    )


def _episode_ref(row: Mapping[str, Any]) -> str:
    return str(
        row.get("capability_episode_ref")
        or row.get("achievement_group_ref")
        or row["campaign_ref"]
    )


def _episode_anchor_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Keep one realized result per capability episode.

    Public battle results remain intact.  This collapse is only for talent
    thickness, difficulty and net-value consumption.
    """

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if _is_pending_person_result(row):
            continue
        grouped[_episode_ref(row)].append(row)
    anchors: list[dict[str, Any]] = []
    for episode_ref, episode_rows in grouped.items():
        anchor = max(
            episode_rows,
            key=lambda row: (
                _is_anchor_result(row),
                TIER_RANK.get(str(row.get("campaign_tier")), 0),
                DIFFICULTY_RANK.get(str(row.get("combat_difficulty")), -1),
                _net_result_value(row),
                str(row.get("campaign_ref")),
            ),
        )
        merged = dict(anchor)
        merged["capability_episode_ref"] = episode_ref
        merged["episode_result_count"] = len(episode_rows)
        anchors.append(merged)
    return sorted(anchors, key=lambda row: _episode_ref(row))


def _achievement(
    record: Mapping[str, Any],
    member: Mapping[str, Any],
    person_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    index = member.get("person_command_index") or {}
    member_person_result = member.get("person_command_result")
    resolved_person_result = (
        person_result
        if person_result is not None
        else member_person_result
        if isinstance(member_person_result, Mapping)
        else {}
    )
    capability_mode = (
        (resolved_person_result.get("military_capability_contribution") or {}).get(
            "capability_mode"
        )
        if isinstance(
            resolved_person_result.get("military_capability_contribution"), Mapping
        )
        else None
    ) or index.get("capability_mode") or _capability_mode(index)
    result_direction = resolved_person_result.get("result_direction") or index.get(
        "result_direction"
    )
    outcome_responsibility = resolved_person_result.get(
        "outcome_responsibility"
    ) or index.get("outcome_responsibility")
    if not outcome_responsibility and result_direction in {"negative", "mixed_review"}:
        outcome_responsibility = {
            "integrated_command": "actual_command_scope",
            "independent_direction": "independent_direction_scope",
            "operational_design": "operational_design_scope",
            "tactical_execution": "scoped_stage_scope",
            "authorization_only": "not_personally_responsible",
            "nominal_only": "not_personally_responsible",
            "unresolved": "responsibility_unknown",
        }.get(str(capability_mode), "responsibility_unknown")
    causal_fault = resolved_person_result.get("causal_fault") or index.get(
        "causal_fault"
    )
    if not causal_fault and result_direction in {"negative", "mixed_review"}:
        causal_fault = "UNKNOWN"
    return {
        "campaign_ref": str(
            resolved_person_result.get("result_ref") or record["war_event_id"]
        ),
        "capability_episode_ref": resolved_person_result.get("capability_episode_ref")
        or resolved_person_result.get("achievement_group_ref")
        or member.get("capability_episode_ref")
        or member.get("achievement_group_ref")
        or record.get("capability_episode_ref")
        or record.get("achievement_group_ref"),
        "canonical_label": resolved_person_result.get("result_label")
        or member.get("person_command_result_label")
        or record.get("canonical_label"),
        "role_code": member.get("role_code"),
        "consumption_mode": index.get("consumption_mode"),
        "capability_mode": capability_mode,
        "decisive_relation": (
            (resolved_person_result.get("military_capability_contribution") or {}).get(
                "decisive_relation"
            )
            if isinstance(
                resolved_person_result.get("military_capability_contribution"), Mapping
            )
            else None
        )
        or index.get("decisive_relation")
        or _decisive_relation(index),
        "result_direction": result_direction,
        "outcome_responsibility": outcome_responsibility,
        "causal_fault": causal_fault,
        "campaign_tier": resolved_person_result.get("result_tier")
        or index.get("projected_result_tier"),
        "combat_difficulty": resolved_person_result.get("combat_difficulty")
        or index.get("projected_combat_difficulty"),
        "outcome_durability": bool(
            resolved_person_result.get("stable_delivery")
            or member.get("talent_stability_validated")
        ),
        "detail_status": index.get("detail_status"),
        "basis": resolved_person_result.get("basis")
        or index.get("basis")
        or member.get("contribution_scope"),
        "source_refs": list(
            resolved_person_result.get("source_refs")
            or index.get("source_refs")
            or record.get("source_refs")
            or []
        ),
        "parent_campaign_tier": record.get("campaign_tier"),
        "parent_combat_difficulty": record.get("combat_difficulty"),
        "evidence_lower_bound": bool(record.get("post_tang_evidence_lower_bound")),
    }


def _achievements(
    record: Mapping[str, Any], member: Mapping[str, Any]
) -> list[dict[str, Any]]:
    person_result = member.get("person_command_result")
    if isinstance(person_result, list):
        return [_achievement(record, member, result) for result in person_result]
    return [_achievement(record, member)]


def _deduplicate(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_campaign: dict[str, dict[str, Any]] = {}
    mode_rank = {
        "none": 0,
        "person_result_required": 1,
        "joint_parent": 2,
        "scoped_projection": 3,
        "operational_result": 3,
        "full_parent": 4,
        "person_result": 5,
    }
    for row in rows:
        key = str(row["campaign_ref"])
        current = by_campaign.get(key)
        if current is None or mode_rank.get(str(row.get("consumption_mode")), -1) > mode_rank.get(
            str(current.get("consumption_mode")), -1
        ):
            by_campaign[key] = dict(row)
    return [by_campaign[key] for key in sorted(by_campaign)]


def _capability_episode_index(
    registry: Mapping[str, Any] | None,
) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}
    for episode in (registry or {}).get("episodes") or ():
        episode_ref = str(episode.get("episode_ref") or "")
        person = str(episode.get("person") or "")
        campaign_refs = [str(value) for value in episode.get("campaign_refs") or ()]
        if not episode_ref or not person or len(campaign_refs) < 2:
            raise ValueError("能力情境必须给出人物、episode_ref 和至少两个战役结果")
        for campaign_ref in campaign_refs:
            key = (person, campaign_ref)
            previous = index.setdefault(key, episode_ref)
            if previous != episode_ref:
                raise ValueError(
                    f"同一人物战役结果不得进入两个能力情境：{person}/{campaign_ref}"
                )
    return index


def _assign_capability_episodes(
    rows: Sequence[Mapping[str, Any]],
    *,
    person: str,
    episode_index: Mapping[tuple[str, str], str],
) -> list[dict[str, Any]]:
    assigned: list[dict[str, Any]] = []
    for row in rows:
        current = dict(row)
        configured = episode_index.get((person, str(row.get("campaign_ref") or "")))
        if configured:
            current["capability_episode_ref"] = configured
        elif not current.get("capability_episode_ref"):
            current["capability_episode_ref"] = str(current["campaign_ref"])
        assigned.append(current)
    return assigned


def _difficulty_at_least(row: Mapping[str, Any], threshold: str) -> bool:
    return DIFFICULTY_RANK.get(str(row.get("combat_difficulty")), -1) >= DIFFICULTY_RANK[
        threshold
    ]


def _tier_at_least(row: Mapping[str, Any], threshold: str) -> bool:
    return TIER_RANK.get(str(row.get("campaign_tier")), 0) >= TIER_RANK[threshold]


def _net_result_value(row: Mapping[str, Any]) -> float:
    tier_value = NET_TIER_VALUE.get(str(row.get("campaign_tier")), 0.0)
    if not tier_value:
        return 0.0
    result_direction = row.get("result_direction")
    if row.get("consumption_mode") == "operational_result":
        operational_value = tier_value * OPERATIONAL_RESULT_COEFFICIENT
        if result_direction == "positive":
            return operational_value
        if result_direction == "negative":
            return -operational_value * NEGATIVE_COMMAND_COEFFICIENT
        if result_direction == "mixed_review":
            return -operational_value * MIXED_COMMAND_COEFFICIENT
        return 0.0
    difficulty_multiplier = NET_DIFFICULTY_MULTIPLIER.get(
        str(row.get("combat_difficulty")), 1.0
    )
    contribution_coefficient = CONTRIBUTION_COEFFICIENT.get(
        _decisive_relation(row), 0.0
    )
    if result_direction == "negative":
        return (
            -tier_value
            * difficulty_multiplier
            * _adverse_responsibility_coefficient(row)
            * NEGATIVE_COMMAND_COEFFICIENT
        )
    if result_direction == "mixed_review":
        return (
            -tier_value
            * difficulty_multiplier
            * _adverse_responsibility_coefficient(row)
            * MIXED_COMMAND_COEFFICIENT
        )
    if result_direction == "positive":
        return tier_value * difficulty_multiplier * contribution_coefficient
    return 0.0


def _adverse_responsibility_coefficient(row: Mapping[str, Any]) -> float:
    """Measure actual command responsibility when no positive result exists."""

    explicit = CONTRIBUTION_COEFFICIENT.get(_decisive_relation(row), 0.0)
    if explicit:
        return explicit
    return {
        "integrated_command": 1.0,
        "independent_direction": 0.85,
        "operational_design": 1.0,
        "tactical_execution": 0.35,
        "authorization_only": 0.0,
        "nominal_only": 0.0,
        "unresolved": 0.0,
    }.get(_capability_mode(row), 0.0)


def _diminishing_sum(values: Sequence[float], weights: Sequence[float]) -> float:
    ordered = sorted(values, reverse=True)
    return sum(
        value * weights[min(index, len(weights) - 1)]
        for index, value in enumerate(ordered)
    )


def _net_strategic_value(
    positive: Sequence[Mapping[str, Any]],
    adverse: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    positive_episodes = _episode_anchor_rows(
        [row for row in positive if not _is_pending_person_result(row)]
    )
    adverse_episodes = _episode_anchor_rows(
        [row for row in adverse if not _is_pending_person_result(row)]
    )
    frontline_rows = [
        row
        for row in positive_episodes
        if row.get("consumption_mode") != "operational_result"
    ]
    operational_rows = [
        row
        for row in positive_episodes
        if row.get("consumption_mode") == "operational_result"
    ]
    frontline_positive = _diminishing_sum(
        [_net_result_value(row) for row in frontline_rows],
        FRONTLINE_DIMINISHING_WEIGHTS,
    )
    operational_positive = _diminishing_sum(
        [_net_result_value(row) for row in operational_rows],
        OPERATIONAL_DIMINISHING_WEIGHTS,
    )
    command_adverse = sum(_net_result_value(row) for row in adverse_episodes)
    net = (
        frontline_positive
        + operational_positive
        + command_adverse
    )
    return {
        "frontline_positive": round(frontline_positive, 2),
        "operational_positive": round(operational_positive, 2),
        "command_adverse": round(command_adverse, 2),
        "net": round(net, 2),
    }


def _historic_path(rows: Sequence[Mapping[str, Any]]) -> str | None:
    positive = _episode_anchor_rows(
        [row for row in rows if row.get("result_direction") == "positive"]
    )
    primary = [
        row
        for row in positive
        if _is_anchor_result(row)
        and row.get("consumption_mode") not in OPERATIONAL_MODES
        and _tier_at_least(row, "A")
    ]
    strategic = [row for row in primary if _tier_at_least(row, "A")]
    hard_s_minus = [
        row
        for row in primary
        if _tier_at_least(row, "S-") and _difficulty_at_least(row, "D3")
    ]
    hard_major = [
        row
        for row in primary
        if _tier_at_least(row, "A") and _difficulty_at_least(row, "D3")
    ]
    def pair_has_v11_difficulty(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
        return (
            _difficulty_at_least(left, "D3")
            and _difficulty_at_least(right, "D3")
        ) or (
            (_difficulty_at_least(left, "D4") and _difficulty_at_least(right, "D2"))
            or (_difficulty_at_least(right, "D4") and _difficulty_at_least(left, "D2"))
        )

    for index, left in enumerate(primary):
        for right in primary[index + 1 :]:
            if not pair_has_v11_difficulty(left, right):
                continue
            if (
                (_tier_at_least(left, "S+") and _tier_at_least(right, "A"))
                or (_tier_at_least(right, "S+") and _tier_at_least(left, "A"))
            ):
                return "historic_era_defining_peak"
            if _tier_at_least(left, "S") and _tier_at_least(right, "S"):
                return "historic_extreme_problem_solver"
    major_context_count = sum(
        _tier_at_least(row, "A") and _difficulty_at_least(row, "D2")
        for row in primary
    )
    for peak in primary:
        if not (
            _tier_at_least(peak, "S") and _difficulty_at_least(peak, "D4")
        ):
            continue
        if (
            major_context_count >= 3
            and any(
                _episode_ref(anchor) != _episode_ref(peak)
                and _tier_at_least(anchor, "S-")
                and _difficulty_at_least(anchor, "D3")
                for anchor in primary
            )
        ):
            return "historic_extreme_problem_solver"
    strategic_weight = sum(
        STRATEGIC_WEIGHT.get(str(row.get("campaign_tier")), 0)
        for row in strategic
    )
    sustained_difficulty = (
        len(hard_major) >= 2
        or (
            any(_difficulty_at_least(row, "D4") for row in strategic)
            and sum(_difficulty_at_least(row, "D2") for row in strategic) >= 3
        )
    )
    if (
        any(_tier_at_least(row, "S") for row in strategic)
        and strategic_weight >= 7
        and len(strategic) >= 3
        and sustained_difficulty
    ):
        return "historic_sustained_grand_command"
    return None


def _top_path(rows: Sequence[Mapping[str, Any]]) -> str | None:
    positive = _episode_anchor_rows(
        [row for row in rows if row.get("result_direction") == "positive"]
    )
    primary = [row for row in positive if _is_anchor_result(row)]
    major = [
        row
        for row in primary
        if _tier_at_least(row, "A")
        and _difficulty_at_least(row, "D2")
    ]
    major_count = len(major)
    strategic_contexts = [
        row
        for row in positive
        if _tier_at_least(row, "A")
        and (
            _is_anchor_result(row)
            or row.get("consumption_mode") in OPERATIONAL_MODES
        )
    ]
    # 重大败责独立进入稳定性画像，不得反写已经由正向实绩成立的能力峰值。
    # historic 的时代位置复核另有边界；top 及以下只在这里判断正向上限。
    reliable_major_count = major_count
    if any(
        _tier_at_least(row, "S+") and _difficulty_at_least(row, "D3")
        for row in primary
    ):
        return "top_national_strategic_peak"
    hard_peak = any(
        _tier_at_least(row, "S-") and _difficulty_at_least(row, "D3")
        for row in primary
    )
    second_high_anchor = sum(
        _tier_at_least(row, "S-") and _difficulty_at_least(row, "D2")
        for row in primary
    ) >= 2
    stable_high_anchor = any(
        _tier_at_least(row, "S-")
        and _difficulty_at_least(row, "D2")
        and bool(row.get("outcome_durability"))
        for row in primary
    )
    s_peak_pair = (
        any(
            _tier_at_least(row, "S") and _difficulty_at_least(row, "D2")
            for row in primary
        )
        and second_high_anchor
        and stable_high_anchor
    )
    hard_s_peak = any(
        _tier_at_least(row, "S") and _difficulty_at_least(row, "D3")
        for row in primary
    )
    frontline_s_peak = any(
        _tier_at_least(row, "S") and _difficulty_at_least(row, "D2")
        for row in primary
    )
    operational_s_peak = any(
        _tier_at_least(row, "S")
        and row.get("consumption_mode") in OPERATIONAL_MODES
        for row in strategic_contexts
    )
    if (
        s_peak_pair
        or (hard_peak and second_high_anchor)
        or (hard_s_peak and major_count >= 2)
        or (frontline_s_peak and operational_s_peak and major_count >= 2)
        or (hard_peak and major_count >= 3)
    ):
        return "top_national_strategic_peak"
    hard_major_pair = (
        hard_peak
        and sum(
            _tier_at_least(row, "A") and _difficulty_at_least(row, "D3")
            for row in primary
        )
        >= 2
    )
    if hard_major_pair:
        return "top_hard_problem_solver"
    creator_hard_major = [
        row
        for row in primary
        if _decisive_relation(row) in {"decisive_creator", "decisive_successor"}
        and _tier_at_least(row, "A")
        and _difficulty_at_least(row, "D3")
    ]
    if (
        any(_difficulty_at_least(row, "D4") for row in creator_hard_major)
        and len(creator_hard_major) >= 2
    ):
        return "top_hard_problem_solver"
    hard_breadth = [
        row
        for row in primary
        if _tier_at_least(row, "B") and _difficulty_at_least(row, "D3")
    ]
    if (
        hard_peak
        and major_count >= 2
        and len(hard_breadth) >= 2
        and len(primary) >= 3
    ):
        return "top_hard_problem_solver"
    if hard_peak and reliable_major_count >= 3:
        return "top_national_strategic_peak"
    sustained_top_validation = any(
        (
            _tier_at_least(row, "S-")
            and _difficulty_at_least(row, "D2")
        )
        or (
            _tier_at_least(row, "A")
            and _difficulty_at_least(row, "D3")
        )
        for row in primary
    )
    if reliable_major_count >= 4 and sustained_top_validation:
        return "top_sustained_first_line_command"
    return None


def _elite_path(rows: Sequence[Mapping[str, Any]]) -> str | None:
    """识别已经证明强将上限、但尚未通过top复验的能力组合。"""

    positive = _episode_anchor_rows(
        [row for row in rows if row.get("result_direction") == "positive"]
    )
    primary = [row for row in positive if _is_anchor_result(row)]
    major = [
        row
        for row in primary
        if _tier_at_least(row, "A") and _difficulty_at_least(row, "D2")
    ]
    if any(
        _tier_at_least(row, "S-") and _difficulty_at_least(row, "D2")
        for row in primary
    ):
        return "elite_strategic_peak"
    if sum(
        _tier_at_least(row, "A") and _difficulty_at_least(row, "D3")
        for row in primary
    ) >= 2:
        return "elite_hard_campaign_specialist"
    if sum(
        _tier_at_least(row, "A") and _difficulty_at_least(row, "D2")
        for row in primary
    ) >= 3:
        return "elite_reliable_major_command"
    operational = [
        row
        for row in positive
        if row.get("consumption_mode") in OPERATIONAL_MODES
        and _tier_at_least(row, "A")
    ]
    if (
        any(_tier_at_least(row, "S") for row in operational)
        and len(operational) + len(major) >= 2
        and major
    ):
        return "elite_reliable_major_command"
    return None


def _grade(rows: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    consumable_rows = [row for row in rows if not _is_pending_person_result(row)]
    historic = _historic_path(consumable_rows)
    if historic:
        return "historic", historic
    top = _top_path(consumable_rows)
    if top:
        return "top", top
    elite = _elite_path(consumable_rows)
    if elite:
        return "elite", elite
    eligible = _episode_anchor_rows([
        row
        for row in consumable_rows
        if _capability_mode(row) in REALIZED_CAPABILITY_MODES
        and (
            _decisive_relation(row) in REALIZED_DECISIVE_RELATIONS
            or _capability_mode(row) == "operational_design"
        )
        and row.get("consumption_mode") in DIRECT_MODES | SUPPORT_MODES
        and row.get("result_direction") == "positive"
        and row.get("campaign_tier") in TIER_RANK
    ])
    if any(
        _tier_at_least(row, "A") and _difficulty_at_least(row, "D2")
        for row in eligible
    ) or sum(_tier_at_least(row, "A") for row in eligible) >= 2:
        return "important", "one_hard_a_or_two_independent_a"
    if any(_tier_at_least(row, "A") for row in eligible) or sum(
        _tier_at_least(row, "B") for row in eligible
    ) >= 2:
        return "capable", "one_a_or_two_independent_b"
    if eligible:
        return "usable", "one_realized_command_result"
    return "ordinary", "no_consumable_positive_command_result"


def _stability_grade_cap(
    grade: str, rows: Sequence[Mapping[str, Any]]
) -> tuple[str, str | None, dict[str, Any]]:
    """Apply one reliability cap when major defeats crowd a thin positive record."""

    positive = _episode_anchor_rows([
        row
        for row in rows
        if row.get("result_direction") == "positive"
        and _is_anchor_result(row)
        and _tier_at_least(row, "A")
        and _difficulty_at_least(row, "D2")
    ])
    adverse = _episode_anchor_rows([
        row
        for row in rows
        if row.get("result_direction") in {"negative", "mixed_review"}
        and row.get("role_code") in {"commander_in_chief", "principal_commander"}
        and _adverse_responsibility_coefficient(row) >= 0.85
        and _tier_at_least(row, "A")
        and _difficulty_at_least(row, "D2")
        and not str(row.get("causal_fault") or "UNKNOWN").upper().startswith(
            "NO_FAULT"
        )
        and str(row.get("causal_fault") or "UNKNOWN").upper()
        != "NOT_RESPONSIBLE"
        and not str(row.get("causal_fault") or "UNKNOWN").upper().startswith(
            "NO_FAULT"
        )
        and str(row.get("causal_fault") or "UNKNOWN").upper()
        != "NOT_RESPONSIBLE"
    ])
    # A mixed result preserves a real adverse signal, but it is not equivalent
    # to a full defeat: one mixed campaign cannot by itself erase an otherwise
    # established high-tier portfolio. Two mixed contexts can still trigger
    # the adverse-density branch below.
    hard_faults = [
        row for row in adverse if row.get("result_direction") == "negative"
    ]
    positive_count = len(positive)
    adverse_count = len(adverse)
    hard_fault_count = len(hard_faults)
    high_peak_count = sum(
        _tier_at_least(row, "S") and _difficulty_at_least(row, "D3")
        for row in positive
    )
    abundant_exception = (
        positive_count >= 5 and high_peak_count >= 2 and hard_fault_count <= 1
    )
    sparse_block = (
        positive_count <= 2 and hard_fault_count >= 1
    ) or (
        positive_count <= 3 and adverse_count >= 2
    )
    crowded_block = positive_count >= 4 and (
        (hard_fault_count >= 2 and hard_fault_count * 2 >= positive_count)
        or (adverse_count >= 2 and adverse_count >= positive_count - 1)
    )
    blocked = (
        grade in {"elite", "top", "historic"}
        and not abundant_exception
        and (
            sparse_block
            or crowded_block
            or (grade == "historic" and hard_fault_count >= 2)
        )
    )
    detail = {
        "major_positive_context_count": positive_count,
        "major_adverse_context_count": adverse_count,
        "commander_responsibility_major_failure_count": hard_fault_count,
        "high_peak_count": high_peak_count,
        "abundant_peak_exception": abundant_exception,
        "stability_cap_applied": blocked,
    }
    if not blocked:
        return grade, None, detail
    current_index = GRADE_ORDER.index(grade)
    capped = GRADE_ORDER[max(GRADE_ORDER.index("important"), current_index - 1)]
    return capped, f"{grade}_blocked_by_failure_pressure", detail


def _close_elite_failure_responsibility(
    rows: Sequence[Mapping[str, Any]], initial_grade: str
) -> list[dict[str, Any]]:
    """Close unresolved actual-command defeat fault after elite review search."""

    if GRADE_ORDER.index(initial_grade) < GRADE_ORDER.index("elite"):
        return [dict(row) for row in rows]
    closed = []
    for row in rows:
        current = dict(row)
        if (
            current.get("result_direction") in {"negative", "mixed_review"}
            and (
                current.get("role_code")
                in {"commander_in_chief", "principal_commander"}
                or (
                    _capability_mode(current) == "operational_design"
                    and current.get("outcome_responsibility")
                    == "operational_design_scope"
                )
            )
            and "UNKNOWN"
            in str(current.get("causal_fault") or "UNKNOWN").upper()
        ):
            current["causal_fault"] = (
                "COMMANDER_RESPONSIBILITY_AFTER_UNRESOLVED_SEARCH"
            )
            current["responsibility_basis"] = (
                "elite以上实际主帅败绩经既有逐字锚与定向检索后仍不能免责；"
                "按主帅结果责任闭合，不保留过错未知。"
            )
        closed.append(current)
    return closed


def _ability_profile(
    positive_rows: Sequence[Mapping[str, Any]],
    adverse_rows: Sequence[Mapping[str, Any]],
) -> str:
    """描述同一能力档内的履历结构，不用净值反推等级。"""

    anchors = _episode_anchor_rows(positive_rows)
    primary = [row for row in anchors if _is_anchor_result(row)]
    major = [
        row
        for row in primary
        if _tier_at_least(row, "A") and _difficulty_at_least(row, "D2")
    ]
    strategic_peaks = [row for row in primary if _tier_at_least(row, "S-")]
    major_adverse = [
        row
        for row in adverse_rows
        if _tier_at_least(row, "A") and _difficulty_at_least(row, "D2")
    ]
    operational = [
        row for row in anchors if row.get("consumption_mode") in OPERATIONAL_MODES
    ]
    if strategic_peaks and major_adverse:
        return "high_ceiling_with_major_adverse"
    if len(strategic_peaks) == 1 and len(major) <= 1:
        return "single_strategic_peak"
    if len(major) >= 4:
        return "sustained_multi_campaign_command"
    if len(major) >= 2:
        return "multi_campaign_validation"
    if operational and not primary:
        return "operational_architect"
    if major:
        return "single_major_command_result"
    return "limited_realized_evidence"


def _failure_stability_rows(
    rows: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    *,
    person: str = "",
    episode_index: Mapping[tuple[str, str], str] | None = None,
) -> list[dict[str, Any]]:
    """Project only adjudicated major personal failures into grade stability checks."""

    explicit_adverse_campaigns = {
        str(row.get("campaign_ref") or "")
        for row in rows
        if row.get("result_direction") in {"negative", "mixed_review"}
        and not _is_pending_person_result(row)
        and row.get("campaign_ref")
    }
    by_campaign: dict[str, dict[str, Any]] = {}
    for failure in failures:
        campaign_ref = str(failure.get("campaign_ref") or "")
        if (
            not campaign_ref
            or campaign_ref in explicit_adverse_campaigns
            or failure.get("responsibility")
            not in {"primary", "shared", "disobedience"}
            or failure.get("failure_domain", "command_failure")
            != "command_failure"
            or float(failure.get("severity_index") or 0) < 0.7
            or TIER_RANK.get(str(failure.get("campaign_tier")), 0)
            < TIER_RANK["A"]
        ):
            continue
        projected = {
            "campaign_ref": campaign_ref,
            "canonical_label": failure.get("canonical_label"),
            "capability_episode_ref": (episode_index or {}).get(
                (person, campaign_ref), campaign_ref
            ),
            "consumption_mode": "none",
            "result_direction": "negative",
            "campaign_tier": failure.get("campaign_tier"),
            "combat_difficulty": failure.get("combat_difficulty"),
            "role_code": "commander_in_chief",
            "capability_mode": "integrated_command",
            "decisive_relation": "decisive_creator",
            "stable_delivery": False,
            "outcome_responsibility": "actual_command_scope",
            "causal_fault": "ATTRIBUTABLE_COMMAND_ERROR",
            "basis": failure.get("basis"),
            "source_refs": list(failure.get("source_refs") or []),
        }
        current = by_campaign.get(campaign_ref)
        if current is None or (
            TIER_RANK.get(str(projected["campaign_tier"]), 0),
            DIFFICULTY_RANK.get(str(projected["combat_difficulty"]), -1),
        ) > (
            TIER_RANK.get(str(current["campaign_tier"]), 0),
            DIFFICULTY_RANK.get(str(current["combat_difficulty"]), -1),
        ):
            by_campaign[campaign_ref] = projected
    return [by_campaign[key] for key in sorted(by_campaign)]


def _major_adverse_episode_refs(
    rows: Sequence[Mapping[str, Any]],
    failure_stability_rows: Sequence[Mapping[str, Any]],
) -> set[str]:
    """Return distinct major command-adverse contexts that can block historic."""

    explicit = _episode_anchor_rows([
        row
        for row in rows
        if row.get("result_direction") in {"negative", "mixed_review"}
        and row.get("role_code") in {"commander_in_chief", "principal_commander"}
        and _adverse_responsibility_coefficient(row) >= 0.85
        and _tier_at_least(row, "A")
        and _difficulty_at_least(row, "D2")
    ])
    refs = {_episode_ref(row) for row in explicit}
    refs.update(_episode_ref(row) for row in failure_stability_rows)
    return refs


def build_military_talent_grade_registry(
    battle_registry: Mapping[str, Any],
    identity_registry: Mapping[str, Any] | None = None,
    capability_episode_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    episode_index = _capability_episode_index(capability_episode_registry)
    occurrences: list[dict[str, Any]] = []
    for record in battle_registry.get("records") or []:
        if not record.get("public_outcome_registered"):
            continue
        dynasty = str(record.get("dynasty") or "未知")
        failures = list(record.get("attributable_failures") or [])
        matched_failure_indexes: set[int] = set()
        for member in record.get("members") or []:
            name = str(member.get("actor_name") or "")
            if not name:
                continue
            member_achievements = _achievements(record, member)
            occurrence = {
                "dynasty": dynasty,
                "name": name,
                "actor_ref": str(member.get("actor_ref") or ""),
                "actor_kind": str(member.get("actor_kind") or "person"),
                "rows": member_achievements,
                "failures": [],
            }
            for failure_index, failure in enumerate(failures):
                if failure.get("actor_ref") == member.get("actor_ref") or failure.get(
                    "actor_name"
                ) == name:
                    matched_failure_indexes.add(failure_index)
                    occurrence["failures"].append(
                        {
                            "campaign_ref": record["war_event_id"],
                            "canonical_label": record.get("canonical_label"),
                            "role_code": member.get("role_code"),
                            "campaign_tier": failure.get("failure_impact_tier"),
                            "combat_difficulty": record.get("combat_difficulty"),
                            **dict(failure),
                        }
                    )
            occurrences.append(occurrence)
        for failure_index, failure in enumerate(failures):
            if failure_index in matched_failure_indexes:
                continue
            failure_name = str(failure.get("actor_name") or "")
            if not failure_name:
                continue
            occurrences.append(
                {
                    "dynasty": dynasty,
                    "name": failure_name,
                    "actor_ref": str(failure.get("actor_ref") or ""),
                    "actor_kind": str(
                        failure.get("actor_kind")
                        or (
                            "ruler"
                            if str(failure.get("actor_ref") or "").startswith("RULER-")
                            else "person"
                        )
                    ),
                    "rows": [],
                    "failures": [
                        {
                            "campaign_ref": record["war_event_id"],
                            "canonical_label": record.get("canonical_label"),
                            "role_code": failure.get("role_code")
                            or "commander_in_chief",
                            "campaign_tier": failure.get("failure_impact_tier"),
                            "combat_difficulty": failure.get("combat_difficulty")
                            or record.get("combat_difficulty"),
                            **dict(failure),
                        }
                    ],
                }
            )

    parents = list(range(len(occurrences)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    by_dynasty_name: dict[tuple[str, str], int] = {}
    by_actor_ref: dict[str, int] = {}
    by_battle_identity_suffix: dict[str, int] = {}
    by_ruler_name: dict[str, int] = {}
    identity_by_surface: dict[tuple[str, str], tuple[str, str]] = {}
    identity_aliases_by_ref: dict[str, set[str]] = defaultdict(set)
    for entity in (identity_registry or {}).get("entities") or ():
        dynasty = str(entity.get("dynasty") or "")
        canonical_name = str(entity.get("canonical_name") or "")
        person_ref = str(entity.get("person_ref") or "")
        if not dynasty or not canonical_name or not person_ref:
            continue
        identity_aliases_by_ref[person_ref].add(canonical_name)
        identity_dynasties = {
            dynasty,
            *(str(value) for value in entity.get("dynasty_aliases") or () if value),
        }
        for identity_dynasty in identity_dynasties:
            identity_by_surface[(identity_dynasty, canonical_name)] = (
                person_ref,
                canonical_name,
            )
            for alias in entity.get("aliases") or ():
                surface = str(alias.get("surface") or "")
                if surface:
                    identity_aliases_by_ref[person_ref].add(surface)
                    identity_by_surface[(identity_dynasty, surface)] = (
                        person_ref,
                        canonical_name,
                    )
    by_identity_ref: dict[str, int] = {}
    canonical_name_by_root_candidate: dict[int, str] = {}
    identity_ref_by_index: dict[int, str] = {}
    for index, occurrence in enumerate(occurrences):
        dynasty_name = (str(occurrence["dynasty"]), str(occurrence["name"]))
        previous = by_dynasty_name.setdefault(dynasty_name, index)
        union(index, previous)
        actor_ref = str(occurrence["actor_ref"])
        if actor_ref:
            previous = by_actor_ref.setdefault(actor_ref, index)
            union(index, previous)
            if actor_ref.startswith(("PER-BATTLE-", "RULER-BATTLE-")):
                identity_suffix = actor_ref.rsplit("-", 1)[-1]
                previous = by_battle_identity_suffix.setdefault(
                    identity_suffix, index
                )
                union(index, previous)
        if occurrence["actor_kind"] == "ruler":
            previous = by_ruler_name.setdefault(str(occurrence["name"]), index)
            union(index, previous)
        identity = identity_by_surface.get(dynasty_name)
        if identity:
            identity_ref, canonical_name = identity
            previous = by_identity_ref.setdefault(identity_ref, index)
            union(index, previous)
            canonical_name_by_root_candidate[index] = canonical_name
            identity_ref_by_index[index] = identity_ref

    people: dict[int, dict[str, Any]] = {}
    for index, occurrence in enumerate(occurrences):
        root = find(index)
        person = people.setdefault(
            root,
            {
                "names": Counter(),
                "dynasties": set(),
                "actor_ref_aliases": set(),
                "actor_kinds": set(),
                "rows": [],
                "failures": [],
                "identity_refs": set(),
            },
        )
        person["names"][str(occurrence["name"])] += 1
        person["dynasties"].add(str(occurrence["dynasty"]))
        person["actor_ref_aliases"].add(str(occurrence["actor_ref"]))
        person["actor_kinds"].add(str(occurrence["actor_kind"]))
        person["rows"].extend(occurrence["rows"])
        person["failures"].extend(occurrence["failures"])
        canonical_name = canonical_name_by_root_candidate.get(index)
        if canonical_name:
            person.setdefault("canonical_names", Counter())[canonical_name] += 1
        identity_ref = identity_ref_by_index.get(index)
        if identity_ref:
            person["identity_refs"].add(identity_ref)

    profiles: list[dict[str, Any]] = []
    for person in people.values():
        canonical_names = person.get("canonical_names") or {}
        name = (
            sorted(
                canonical_names,
                key=lambda value: (-canonical_names[value], value),
            )[0]
            if canonical_names
            else sorted(
                person["names"],
                key=lambda value: (-person["names"][value], value),
            )[0]
        )
        dynasties = sorted(
            person["dynasties"], key=lambda value: (DYNASTY_ORDER.get(value, 99), value)
        )
        dynasty = "／".join(dynasties)
        person_ref = _person_key(dynasty, name)
        raw_rows = list(person["rows"])
        rows = _assign_capability_episodes(
            _deduplicate(raw_rows),
            person=name,
            episode_index=episode_index,
        )
        failure_stability_rows = _failure_stability_rows(
            rows,
            person["failures"],
            person=name,
            episode_index=episode_index,
        )
        initial_grade, initial_rule_path = _grade([*rows, *failure_stability_rows])
        closed_rows = _close_elite_failure_responsibility(
            [*rows, *failure_stability_rows], initial_grade
        )
        rows = closed_rows[: len(rows)]
        failure_stability_rows = closed_rows[len(rows) :]
        grade, stability_rule_path, stability_gate = _stability_grade_cap(
            initial_grade, closed_rows
        )
        rule_path = stability_rule_path or initial_rule_path
        pending = [
            row
            for row in raw_rows
            if row.get("role_code")
            in {"commander_in_chief", "principal_commander"}
            and _is_pending_person_result(row)
        ]
        high_failures = _major_adverse_episode_refs(rows, failure_stability_rows)
        failure_accountability = _episode_anchor_rows([
            row
            for row in [*rows, *failure_stability_rows]
            if row.get("result_direction") in {"negative", "mixed_review"}
        ])
        status = "current_battle_registry_grade"
        blocked_historic_path = (
            initial_rule_path
            if initial_grade == "historic" and grade != "historic"
            else None
        )
        if pending:
            status = "lower_bound_pending_person_result"
        elif any(row.get("evidence_lower_bound") for row in rows):
            status = "evidence_lower_bound"
        if len(high_failures) >= 2:
            stability_status = "stability_limited_repeated_major_failures"
        elif high_failures:
            stability_status = "stability_limited_major_failure"
        else:
            stability_status = "no_comparable_major_failure_established"
        positive = [
            row
            for row in rows
            if not _is_pending_person_result(row)
            if row.get("result_direction") == "positive"
            and row.get("consumption_mode") in DIRECT_MODES | SUPPORT_MODES
        ]
        adverse = [
            row
            for row in rows
            if not _is_pending_person_result(row)
            if row.get("result_direction") in {"negative", "mixed_review"}
        ]
        capability_episode_anchors = _episode_anchor_rows(positive)
        net_value = _net_strategic_value(positive, adverse)
        profiles.append(
            {
                "profile_ref": f"MIL-PROFILE-{person_ref.removeprefix('MIL-PER-')}",
                "person_ref": person_ref,
                "person": name,
                "name_aliases": sorted({
                    *person["names"],
                    *(
                        alias
                        for identity_ref in person["identity_refs"]
                        for alias in identity_aliases_by_ref.get(identity_ref, ())
                    ),
                }),
                "dynasty": dynasty,
                "dynasty_aliases": dynasties,
                "actor_ref_aliases": sorted(value for value in person["actor_ref_aliases"] if value),
                "actor_kinds": sorted(person["actor_kinds"]),
                "military_grade": grade,
                "ability_profile": _ability_profile(positive, adverse),
                "grade_status": status,
                "stability_status": stability_status,
                "major_adverse_episode_refs": sorted(high_failures),
                "stability_gate": stability_gate,
                "rule_path": rule_path,
                "blocked_historic_path": blocked_historic_path,
                "consumed_achievements": positive,
                "capability_episode_count": len(capability_episode_anchors),
                "capability_episode_anchors": capability_episode_anchors,
                "pending_person_command_results": pending,
                "negative_or_mixed_command_records": adverse,
                "failure_accountability": failure_accountability,
                "attributable_failures": sorted(
                    person["failures"], key=lambda row: str(row["campaign_ref"])
                ),
                "net_strategic_value": net_value["net"],
                "net_strategic_value_breakdown": net_value,
                "grade_basis": (
                    f"仅消费最新战役登记中的本人主帅或主将成果；按 {rule_path} "
                    + (
                        f"当前可证下限为 {grade}，覆盖增加后可复核升级，非冻结终值。"
                        if status in {"evidence_lower_bound", "lower_bound_pending_person_result"}
                        else f"当前定为 {grade}。"
                    )
                    + (
                        f" 稳定性状态={stability_status}。"
                        if high_failures
                        else ""
                    )
                ),
            }
        )
    profiles.sort(
        key=lambda profile: (
            -float(profile.get("net_strategic_value") or 0),
            -GRADE_ORDER.index(str(profile["military_grade"])),
            DYNASTY_ORDER.get(str(profile.get("dynasty")), 99),
            str(profile.get("person")),
        )
    )
    grade_counts = Counter(profile["military_grade"] for profile in profiles)
    status_counts = Counter(profile["grade_status"] for profile in profiles)
    stability_status_counts = Counter(profile["stability_status"] for profile in profiles)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "current_battle_registry_authoritative",
        "source_registry_ref": "docs/公共成果/军事/01-秦至唐战役登记.json",
        "source_registry_fingerprint": battle_registry.get("semantic_fingerprint"),
        "capability_episode_registry_ref": "config/military-capability-episodes.json",
        "capability_episode_count": len(
            (capability_episode_registry or {}).get("episodes") or ()
        ),
        "supersedes_prior_military_talent_grades": True,
        "formal_score_write": False,
        "profile_count": len(profiles),
        "identity_alias_group_count": sum(
            len(profile["actor_ref_aliases"]) > 1 for profile in profiles
        ),
        "grade_counts": dict(sorted(grade_counts.items())),
        "grade_status_counts": dict(sorted(status_counts.items())),
        "stability_status_counts": dict(sorted(stability_status_counts.items())),
        "evidence_lower_bound_profile_count": sum(
            profile["grade_status"] == "evidence_lower_bound"
            for profile in profiles
        ),
        "profiles": profiles,
    }
    payload["registry_fingerprint"] = _digest(payload)
    return payload


ROLE_LABELS = {
    "commander_in_chief": "主帅",
    "principal_commander": "主将",
    "supporting_commander": "从攻",
    "not_in_command_chain": "非前线指挥链",
}

ABILITY_PROFILE_LABELS = {
    "high_ceiling_with_major_adverse": "高峰伴重大败绩",
    "single_strategic_peak": "单一战略高峰",
    "sustained_multi_campaign_command": "持续多战役统帅",
    "multi_campaign_validation": "多战役复验",
    "operational_architect": "战争统筹型",
    "single_major_command_result": "单项重大成果",
    "limited_realized_evidence": "已实现证据有限",
}


def _markdown_cell(value: Any) -> str:
    return str(value or "—").replace("|", "\\|").replace("\n", " ")


def _profile_display_entries(
    profile: Mapping[str, Any],
) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for row in profile.get("consumed_achievements") or ():
        kind = (
            "统筹+"
            if row.get("consumption_mode") == "operational_result"
            else "前线+"
        )
        tier = row.get("campaign_tier") or "—"
        difficulty = row.get("combat_difficulty") or "—"
        role = (
            "统筹"
            if row.get("consumption_mode") == "operational_result"
            else ROLE_LABELS.get(str(row.get("role_code")), str(row.get("role_code") or "—"))
        )
        entries.append(
            (
                f"{kind} `{tier}/{difficulty}`",
                f"{_markdown_cell(row.get('canonical_label') or row.get('campaign_ref'))}／{role}",
            )
        )
    accountability_rows = profile.get("failure_accountability")
    if accountability_rows is None:
        accountability_rows = profile.get("negative_or_mixed_command_records") or ()
    for row in accountability_rows:
        campaign_ref = str(row.get("campaign_ref") or "")
        kind = "前线−" if row.get("result_direction") == "negative" else "前线±"
        tier = row.get("campaign_tier") or "—"
        difficulty = row.get("combat_difficulty") or "—"
        role = ROLE_LABELS.get(
            str(row.get("role_code")), str(row.get("role_code") or "—")
        )
        entries.append(
            (
                f"{kind} `{tier}/{difficulty}`",
                f"{_markdown_cell(row.get('canonical_label') or campaign_ref)}／{role}／"
                f"结果责任={_markdown_cell(row.get('outcome_responsibility'))}／"
                f"致败责任={_markdown_cell(row.get('causal_fault'))}",
            )
        )
    return entries


def render_military_talent_grade_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 秦至清武将人才等级",
        "",
        "本表只消费最新父战役总登记；既有军事人才等级与旧人物画像不参与计算。",
        "人才厚度按能力情境去重：同一情境只取一个最高人物结果；历史角色不决定信用，决定性关系决定主锚资格。净值只作同档校准，统筹按 `0.4` 分轨消费，负向按 `-0.8`、混合按 `-0.4`，不再叠加单项稳定、高难储备或方法奖励。",
        "",
        f"- 人物：{payload['profile_count']}",
        f"- 身份别名归并组：{payload['identity_alias_group_count']}",
        "",
        "## 档位统计",
        "",
        "| 档位 | 数量 |",
        "| --- | ---: |",
    ]
    for grade in GRADE_ORDER:
        lines.append(f"| `{grade}` | {payload['grade_counts'].get(grade, 0)} |")
    lines.extend(
        [
            "",
            "## 人物总表",
            "",
            "| 朝代 | 人物 | 档位 | 履历结构 | 净值 | 战役成果等级/难度组合 | 战役群名称/武将角色 |",
            "| --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    display_profiles = sorted(
        payload["profiles"],
        key=lambda profile: (
            -float(profile.get("net_strategic_value") or 0),
            -GRADE_ORDER.index(str(profile["military_grade"])),
            DYNASTY_ORDER.get(str(profile.get("dynasty")), 99),
            str(profile.get("person")),
        ),
    )
    for profile in display_profiles:
        entries = _profile_display_entries(profile)
        combinations = "<br>".join(
            f"{index}) {combination}"
            for index, (combination, _) in enumerate(entries, start=1)
        ) or "—"
        campaigns = "<br>".join(
            f"{index}) {campaign}"
            for index, (_, campaign) in enumerate(entries, start=1)
        ) or "—"
        lines.append(
            f"| {profile['dynasty']} | {profile['person']} | "
            f"`{profile['military_grade']}` | "
            f"{ABILITY_PROFILE_LABELS.get(str(profile.get('ability_profile')), str(profile.get('ability_profile') or '—'))} | "
            f"{profile['net_strategic_value']:.2f} | "
            f"{combinations} | {campaigns} |"
        )
    lines.extend(["", "## 指纹", "", f"`{payload['registry_fingerprint']}`", ""])
    return "\n".join(lines)


def write_military_talent_grade_registry(workspace_root: Path) -> dict[str, Path]:
    battle_path = workspace_root / "docs/公共成果/军事/01-秦至唐战役登记.json"
    battle_registry = json.loads(battle_path.read_text(encoding="utf-8"))
    identity_registry = yaml.safe_load(
        (workspace_root / "config/historical-entity-identities.yml").read_text(
            encoding="utf-8"
        )
    )
    capability_episode_registry = json.loads(
        (workspace_root / "config/military-capability-episodes.json").read_text(
            encoding="utf-8"
        )
    )
    payload = build_military_talent_grade_registry(
        battle_registry,
        identity_registry=identity_registry,
        capability_episode_registry=capability_episode_registry,
    )
    target = workspace_root / "docs/公共成果/军事"
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "02-秦至唐武将人才等级.json"
    markdown_path = target / "02-秦至唐武将人才等级.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(
        render_military_talent_grade_markdown(payload), encoding="utf-8"
    )
    return {"json": json_path, "markdown": markdown_path}
