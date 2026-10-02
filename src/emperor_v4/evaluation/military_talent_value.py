"""Current-record net-value calculation and same-value reading view.

This module never discovers people, compiles battle facts, or adjudicates grades.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.talent_registry_store import load_talent_registry, write_talent_registry, talent_profiles_by_ref
from emperor_v4.evaluation.profile_m1_stability import verify_failure_aliases
from emperor_v4.evaluation.military_public_text import registered_military_display

TIER_VALUE = {"C": 0.15, "B": 0.4, "A": 1.0, "S-": 2.2, "S": 3.6, "S+": 4.5}
TIER_ORDER = {tier: i for i, tier in enumerate(TIER_VALUE)}
DIFFICULTY = {"D0": 0.55, "D1": 0.75, "D2": 1.0, "D3": 1.25, "D4": 1.55}
CONTRIBUTION = {"decisive_creator": 1.0, "decisive_successor": 1.0, "co_decisive": 0.85,
                "terminal_finisher": 0.5, "stage_executor": 0.35}
CAPABILITY_MODES = {"integrated_command", "independent_direction", "operational_design",
                    "tactical_execution", "authorization_only", "nominal_only", "unresolved"}
PENDING_STATUSES = {"person_result_required", "failure_review_required", "source_conflict_unresolved"}
POSITIVE_WEIGHTS = (1.0, 0.8, 0.6, 0.4)
POSITIVE_TAIL_WEIGHT = 0.2
GRADE_ORDER = ("ordinary", "usable", "capable", "important", "elite", "top", "historic")
ROLE_LABELS = {"commander_in_chief": "主帅", "principal_commander": "主将",
               "supporting_commander": "从攻", "participant": "参与者",
               "not_in_command_chain": "非前线指挥链", "command_unresolved": "指挥未决"}
ABILITY_LABELS = {"high_ceiling_with_major_adverse": "高峰伴重大败绩",
                  "high_peak_with_major_failure": "高峰伴重大败绩",
                  "single_strategic_peak": "单一战略高峰",
                  "sustained_multi_campaign_command": "持续多战役统帅",
                  "multi_campaign_validation": "多战役复验",
                  "multi_campaign_validated": "多战役复验",
                  "operational_architect": "战争统筹型",
                  "single_major_command_result": "单项重大成果",
                  "limited_realized_evidence": "已实现证据有限"}


def source_conflict(row: Mapping[str, Any]) -> bool:
    return "SOURCE_CONFLICT" in str(row.get("causal_fault") or "").upper()


def is_pending(row: Mapping[str, Any]) -> bool:
    review = row.get("operational_role_review")
    if review is not None and row.get("result_direction") in {"positive", "negative", "mixed_review"}:
        if review.get("status") != "QUALIFIED" or review.get("implemented") is not True or review.get("outcome_established") is not True:
            return True
        if row.get("result_direction") in {"negative", "mixed_review"} and review.get("failure_established") is not True:
            return True
    return str(row.get("detail_status") or "") in PENDING_STATUSES or source_conflict(row)


def episode_ref(row: Mapping[str, Any]) -> str:
    value = row.get("capability_episode_ref") or row.get("achievement_group_ref") or row.get("campaign_ref")
    if not value:
        raise ValueError("军事人才结果缺少能力情境和战役引用")
    return str(value)


def adverse_responsibility(row: Mapping[str, Any]) -> float:
    explicit = CONTRIBUTION.get(str(row.get("decisive_relation")), 0.0)
    if explicit:
        return explicit
    return {"integrated_command": 1.0, "independent_direction": 0.85,
            "operational_design": 1.0, "tactical_execution": 0.35,
            "authorization_only": 0.0, "nominal_only": 0.0, "unresolved": 0.0}.get(
                str(row.get("capability_mode")), 0.0)


def outcome_rows(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project adjudicated sides; mixed is a description, never a discount."""
    if row.get("result_direction") != "mixed_review" or is_pending(row):
        return [dict(row)]
    validate_mixed_result(row)
    result = []
    for component in row["mixed_result_review"]["components"]:
        item = {**row, **component}
        item["campaign_tier"] = component["effect_tier"]
        item["result_direction"] = component["direction"]
        if item["consumption_mode"] == "operational_result":
            review = dict(item["operational_role_review"])
            review["major_result"] = component["direction"] == "positive" and TIER_ORDER[component["effect_tier"]] >= TIER_ORDER["A"]
            review["failure_effect_tier"] = component["effect_tier"] if component["direction"] == "negative" else None
            item["operational_role_review"] = review
        result.append(item)
    return result


def positive_results(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [item for row in [*profile.get("consumed_achievements", []),
                            *profile.get("negative_or_mixed_command_records", [])]
            for item in outcome_rows(row) if item.get("result_direction") == "positive"]


def adverse_results(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [item for row in profile.get("negative_or_mixed_command_records", profile.get("failure_accountability", []))
            for item in outcome_rows(row) if item.get("result_direction") == "negative"]


def result_value(row: Mapping[str, Any]) -> float:
    if is_pending(row):
        return 0.0
    tier = TIER_VALUE.get(str(row.get("campaign_tier")), 0.0)
    direction = row.get("result_direction")
    if direction == "mixed_review":
        return float(sum(Decimal(str(result_value(item))) for item in outcome_rows(row)))
    if direction == "negative":
        review = row.get("adverse_result_review") or {}
        if review.get("effect_tier") not in TIER_VALUE:
            raise ValueError("已闭败果缺少本人实际后果档")
        tier = TIER_VALUE[review["effect_tier"]]
        responsibility = review.get("responsibility_coefficient")
        if responsibility not in CONTRIBUTION.values():
            raise ValueError("已闭败果缺少已裁结果责任系数")
        return _product(tier, 0.4 if row.get("consumption_mode") == "operational_result" else 1,
                        responsibility, -0.8)
    if row.get("consumption_mode") == "operational_result":
        return _product(tier, 0.4, 1.0 if direction == "positive" else 0.0)
    # An ungraded difficulty is not a D2 capability gate; the existing net-value
    # convention only applies the unmodified result base, without a difficulty premium.
    multiplier = DIFFICULTY.get(str(row.get("combat_difficulty")), 1.0)
    if direction == "positive":
        return _product(tier, multiplier, CONTRIBUTION.get(str(row.get("decisive_relation")), 0.0))
    return 0.0


def _product(*factors: float) -> float:
    value = Decimal(1)
    for factor in factors:
        value *= Decimal(str(factor))
    return float(value)


def episode_anchors(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if not is_pending(row):
            groups[episode_ref(row)].append(row)
    anchors = []
    for ref, group in groups.items():
        def key(row: Mapping[str, Any]) -> tuple:
            if row.get("result_direction") == "negative":
                return (abs(result_value(row)), 0, 0, 0, str(row.get("campaign_ref")))
            primary = row.get("decisive_relation") in {"decisive_creator", "decisive_successor", "co_decisive"} and row.get("capability_mode") not in {"operational_design", "authorization_only", "nominal_only", "unresolved"}
            return (primary, TIER_ORDER.get(str(row.get("campaign_tier")), -1),
                    list(DIFFICULTY).index(row["combat_difficulty"]) if row.get("combat_difficulty") in DIFFICULTY else -1,
                    result_value(row), str(row.get("campaign_ref")))
        anchor = dict(max(group, key=key))
        anchor.update(capability_episode_ref=ref, episode_result_count=len(group))
        anchors.append(anchor)
    return sorted(anchors, key=episode_ref)


def positive_breakdown(rows: Sequence[Mapping[str, Any]]) -> tuple[Decimal, Decimal]:
    """One strongest result per episode, one queue and one shared tail cap."""
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if not is_pending(row) and row.get("result_direction") == "positive":
            groups[episode_ref(row)].append(row)
    def representative_key(row: Mapping[str, Any]) -> tuple:
        return (result_value(row), str(row.get("campaign_ref")), str(row.get("consumption_mode")))
    representatives = [max(group, key=representative_key) for group in groups.values()]
    representatives.sort(key=lambda row: (-result_value(row), episode_ref(row), str(row.get("campaign_ref"))))
    if not representatives:
        return Decimal(0), Decimal(0)
    frontline = operational = Decimal(0)
    for i, row in enumerate(representatives[:len(POSITIVE_WEIGHTS)]):
        credit = Decimal(str(result_value(row))) * Decimal(str(POSITIVE_WEIGHTS[i]))
        if row.get("consumption_mode") == "operational_result":
            operational += credit
        else:
            frontline += credit
    tail = representatives[len(POSITIVE_WEIGHTS):]
    tail_front = sum((Decimal(str(result_value(row))) for row in tail
                      if row.get("consumption_mode") != "operational_result"), Decimal(0))
    tail_org = sum((Decimal(str(result_value(row))) for row in tail
                    if row.get("consumption_mode") == "operational_result"), Decimal(0))
    tail_raw = tail_front + tail_org
    if tail_raw:
        budget = min(Decimal(str(POSITIVE_TAIL_WEIGHT)) * tail_raw, Decimal(str(result_value(representatives[0]))))
        front_credit = budget * tail_front / tail_raw
        frontline += front_credit
        operational += budget - front_credit
    return frontline, operational


def net_value(profile: Mapping[str, Any]) -> dict[str, float]:
    adverse = episode_anchors(adverse_results(profile))
    frontline, operational = positive_breakdown(positive_results(profile))
    debit = sum((Decimal(str(result_value(r))) for r in adverse), Decimal(0))
    return {"frontline_positive": float(round(frontline, 2)), "operational_positive": float(round(operational, 2)),
            "command_adverse": float(round(debit, 2)), "net": float(round(frontline + operational + debit, 2))}


def stability_counts(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Count declared independent major contexts, without adjudicating a grade."""
    def major(row: Mapping[str, Any]) -> bool:
        return TIER_ORDER.get(str(row.get("campaign_tier")), -1) >= TIER_ORDER["A"] and row.get("combat_difficulty") in {"D2", "D3", "D4"}
    front_positive = episode_anchors([r for r in positive_results(profile)
        if major(r) and r.get("decisive_relation") in {"decisive_creator", "decisive_successor", "co_decisive"}
        and r.get("capability_mode") not in {"operational_design", "authorization_only", "nominal_only", "unresolved"}])
    front_adverse = episode_anchors([r for r in adverse_results(profile)
        if TIER_ORDER.get(str(r.get("adverse_result_review", {}).get("effect_tier")), -1) >= TIER_ORDER["A"]
        and r.get("consumption_mode") != "operational_result"
        and r.get("role_code") in {"commander_in_chief", "principal_commander"}
        and r.get("adverse_result_review", {}).get("responsibility_coefficient", 0) >= 0.85
        and not str(r.get("causal_fault") or "").upper().startswith("NO_FAULT")
        and r.get("causal_fault") != "NOT_RESPONSIBLE"])
    def operational(row: Mapping[str, Any], adverse: bool = False) -> bool:
        review = row.get("operational_role_review") or {}
        if row.get("consumption_mode") != "operational_result" or review.get("status") != "QUALIFIED" or is_pending(row):
            return False
        if adverse:
            return (row.get("result_direction") in {"negative", "mixed_review"}
                    and review.get("failure_established") is True
                    and TIER_ORDER.get(str(review.get("failure_effect_tier")), -1) >= TIER_ORDER["A"]
                    and not str(row.get("causal_fault") or "").upper().startswith("NO_FAULT")
                    and row.get("causal_fault") != "NOT_RESPONSIBLE")
        return review.get("major_result") is True and TIER_ORDER.get(str(row.get("campaign_tier")), -1) >= TIER_ORDER["A"]
    op_positive = episode_anchors([r for r in positive_results(profile) if operational(r)])
    op_adverse = episode_anchors([r for r in adverse_results(profile) if operational(r, True)
        and r.get("adverse_result_review", {}).get("responsibility_coefficient", 0) >= 0.85])
    positive = episode_anchors([*front_positive, *op_positive])
    adverse = episode_anchors([*front_adverse, *op_adverse])
    hard = sum(r.get("result_direction") == "negative" for r in adverse)
    peaks = sum(TIER_ORDER.get(str(r.get("campaign_tier")), -1) >= TIER_ORDER["S"] and r.get("combat_difficulty") in {"D3", "D4"} for r in front_positive)
    counts = {"major_positive_context_count": len(positive), "major_adverse_context_count": len(adverse),
            "commander_responsibility_major_failure_count": hard, "high_peak_count": peaks,
            "abundant_peak_exception": len(front_positive) >= 5 and peaks >= 2 and hard <= 1}
    if any(row.get("operational_role_review") for field in ("consumed_achievements", "negative_or_mixed_command_records", "pending_person_command_results", "objective_shortfalls", "excluded_command_records") for row in profile.get(field, [])):
        counts.update({"frontline_major_positive_context_count": len(front_positive),
            "frontline_major_adverse_context_count": len(front_adverse),
            "operational_major_positive_context_count": len(op_positive),
            "operational_major_adverse_context_count": len(op_adverse),
            "operational_major_adverse_episode_refs": [episode_ref(r) for r in op_adverse],
            "combined_major_adverse_episode_refs": [episode_ref(r) for r in adverse],
            "operational_responsibility_major_failure_count": sum(r.get("result_direction") == "negative" for r in op_adverse)})
    return counts


def positive_evidence_paths(profile: Mapping[str, Any]) -> dict[str, list[str]]:
    """Deterministic positive eligibility; reliability and final grade stay adjudicated."""
    anchors = episode_anchors(positive_results(profile))
    front = [r for r in anchors if r.get("capability_mode") not in
             {"operational_design", "authorization_only", "nominal_only", "unresolved"}
             and r.get("decisive_relation") in {"decisive_creator", "decisive_successor", "co_decisive"}]
    op = [r for r in anchors if r.get("consumption_mode") == "operational_result"
          and r.get("operational_role_review", {}).get("status") == "QUALIFIED"
          and r.get("operational_role_review", {}).get("major_result") is True]
    def count(tier: str, difficulty: str) -> int:
        return sum(TIER_ORDER[r["campaign_tier"]] >= TIER_ORDER[tier]
                   and r.get("combat_difficulty") in set(list(DIFFICULTY)[list(DIFFICULTY).index(difficulty):]) for r in front)
    a2, a3, sm2, sm3, s2, s3, s4, sp3 = (count(t,d) for t,d in
        [("A","D2"),("A","D3"),("S-","D2"),("S-","D3"),("S","D2"),("S","D3"),("S","D4"),("S+","D3")])
    op_a = sum(TIER_ORDER[r["campaign_tier"]] >= TIER_ORDER["A"] for r in op)
    op_s = sum(TIER_ORDER[r["campaign_tier"]] >= TIER_ORDER["S"] for r in op)
    paths = {"elite": [], "top": [], "historic": []}
    if sm2: paths["elite"].append("frontline_strategic_peak")
    if a3 >= 2: paths["elite"].append("frontline_independent_hard_solutions")
    if a2 >= 3: paths["elite"].append("frontline_reliable_major_command")
    if op_s >= 1 and op_a + a2 >= 2: paths["elite"].append("operational_peak_with_independent_validation")
    if sp3: paths["top"].append("frontline_era_scale_peak")
    if s3 and a2 >= 2: paths["top"].append("frontline_s_peak_with_validation")
    if sm3 and (sm2 >= 2 or a2 >= 3): paths["top"].append("frontline_s_minus_peak_with_validation")
    if s2 and op_s and a2 >= 2: paths["top"].append("frontline_peak_with_independent_design")
    if a2 >= 4 and (a3 or sm2): paths["top"].append("frontline_sustained_major_command")
    if op_s >= 2 and op_a + a2 >= 3: paths["top"].append("operational_system_with_independent_validation")
    if paths["top"]:
        if sp3 and sm3 >= 2 and a2 >= 3: paths["historic"].append("era_terminal_peak_with_hard_validation")
        if (s3 >= 2 or (s4 and sm3 >= 2)) and a2 >= 3: paths["historic"].append("independent_extreme_strategic_peaks")
        independent_hard_rechecks = any(
            sum(TIER_ORDER[r["campaign_tier"]] >= TIER_ORDER["A"] and r.get("combat_difficulty") in {"D3", "D4"}
                for r in front if episode_ref(r) != episode_ref(peak)) >= 2
            for peak in front if TIER_ORDER[peak["campaign_tier"]] >= TIER_ORDER["S"]
            and peak.get("combat_difficulty") in {"D2", "D3", "D4"})
        if s2 and ((a2 >= 4 and a3 >= 2) or independent_hard_rechecks):
            paths["historic"].append("sustained_grand_command_with_strategic_peak")
    return paths


def refresh_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Refresh derived values from already adjudicated records, preserving identities."""
    result = deepcopy(dict(payload))
    profiles = result["profiles"]
    for p in profiles:
        p["net_strategic_value_breakdown"] = net_value(p)
        p["net_strategic_value"] = p["net_strategic_value_breakdown"]["net"]
        p["capability_episode_anchors"] = episode_anchors(positive_results(p))
        p["capability_episode_count"] = len(p["capability_episode_anchors"])
        p["positive_evidence_paths"] = positive_evidence_paths(p)
        counts = stability_counts(p)
        p["stability_gate"] = {**p.get("stability_gate", {}), **counts}
        if p.get("stability_status") in {"no_comparable_major_failure_established", "major_adverse_established"}:
            p["stability_status"] = ("major_adverse_established" if counts["major_adverse_context_count"]
                                     else "no_comparable_major_failure_established")
        if "combined_major_adverse_episode_refs" in counts:
            p["major_adverse_episode_refs"] = counts["combined_major_adverse_episode_refs"]
    result["profile_count"] = len(profiles)
    for output, field in [("grade_counts", "military_grade"), ("grade_status_counts", "grade_status"), ("stability_status_counts", "stability_status")]:
        result[output] = dict(Counter(p[field] for p in profiles))
    result["evidence_lower_bound_profile_count"] = sum(p["grade_status"] == "evidence_lower_bound" for p in profiles)
    result["identity_alias_group_count"] = sum(len(p.get("actor_ref_aliases") or []) > 1 for p in profiles)
    return result


def _cell(value: Any) -> str:
    return str(value or "—").replace("|", "\\|").replace("\n", " ")


def display_entries(profile: Mapping[str, Any]) -> list[tuple[str, str]]:
    entries = []
    rows = [*profile.get("consumed_achievements", []), *profile.get("failure_accountability", profile.get("negative_or_mixed_command_records", []))]
    rows.extend(profile.get("pending_person_command_results") or [])
    rows.extend(profile.get("objective_shortfalls") or [])
    rows.extend(profile.get("excluded_command_records") or [])
    rows = [item for row in rows for item in outcome_rows(row)]
    seen = set()
    for row in rows:
        identity = (row.get("campaign_ref"), row.get("result_direction"))
        if identity in seen:
            continue
        seen.add(identity)
        operational = row.get("consumption_mode") == "operational_result"
        kind = "统筹" if operational else "前线"
        direction = row.get("result_direction")
        if direction == "objective_shortfall":
            marker = "目标未成"
        elif direction == "not_applicable":
            marker = "不计军事"
        elif is_pending(row) or direction not in {"positive", "negative", "mixed_review"}:
            marker = "待核"
        else:
            marker = {"positive": "+", "negative": "−", "mixed_review": "±"}[direction]
        role = "统筹" if operational else ROLE_LABELS.get(str(row.get("role_code")), str(row.get("role_code") or "—"))
        text = f"{_cell(row.get('canonical_label') or row.get('campaign_ref'))}／{role}"
        if direction in {"negative", "mixed_review"}:
            text += f"／结果责任={_cell(row.get('outcome_responsibility'))}／致败责任={_cell(row.get('causal_fault'))}"
        if direction == "negative" and row.get("adverse_result_review"):
            text += f"／本人败果={row['adverse_result_review']['effect_tier']}（难度不作扣减乘数）"
        if is_pending(row):
            text += "／史源或本人结果未决，不计净值"
        if direction == "objective_shortfall":
            text += "／仅目标短缺，未闭本人损害，不计净值或稳定性败责"
        if direction == "not_applicable":
            text += "／非军事结果，不计净值或稳定性败责"
        entries.append((f"{kind}{marker} `{row.get('campaign_tier') or '—'}/{row.get('combat_difficulty') or '—'}`", registered_military_display(text)))
    return entries


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = ["# 秦至清武将人才等级", "",
             "本表消费当前已闭人物结果及其有效父战役、史源连接；旧引用只作保留别名，不重复计入。",
             "按等级从高到低、同级净值从高到低展示；等级与净值均相同时按朝代、姓名及稳定ID排序。净值是成果与实际损害余额，不是军事能力分；解释人物差异时仍须核对角色、履历机会和史料覆盖。S+基础值为 `4.5`；正向每个能力情境取最高代表，前线与统筹共用 `1、0.8、0.6、0.4` 递减队列，第五项起按 `0.2` 计，尾部合计不超过首项单项值。统筹仍乘 `0.4`，不继承前线难度。混合结果分别消费已裁正果和败果，取消半额扣减；败果按本人后果档、结果责任与 `-0.8` 计算，不乘难度、不递减。正负分别去重，同周期只形成一次独立复验；可靠性另裁，明确史源冲突不计确定净值。", "",
             "有界档位按当前下限统计，同时展示待证上界；下端不代表已经完成全生涯无能力判定。", "",
             f"- 人物档案：{payload['profile_count']}", f"- 身份别名归并组：{payload['identity_alias_group_count']}", "", "## 档位统计", "",
             "| 档位 | 数量 |", "| --- | ---: |"]
    for grade in GRADE_ORDER:
        lines.append(f"| `{grade}` | {payload['grade_counts'].get(grade, 0)} |")
    lines += ["", "## 人物总表", "", "| 朝代 | 人物 | 档位 | 履历结构 | 净值 | 战役成果等级/难度组合 | 战役群名称/武将角色 |", "| --- | --- | --- | --- | ---: | --- | --- |"]
    profiles = sorted(payload["profiles"], key=lambda p: (-GRADE_ORDER.index(p["military_grade"]), -p["net_strategic_value"], p["dynasty"], p["person"], p["profile_ref"]))
    for p in profiles:
        entries = display_entries(p)
        combinations = "<br>".join(f"<nobr>{i}) {a}</nobr>" for i, (a, _) in enumerate(entries, 1)) or "—"
        campaigns = "<br>".join(f"{i}) {b}" for i, (_, b) in enumerate(entries, 1)) or "—"
        ability = ABILITY_LABELS.get(p["ability_profile"], p["ability_profile"])
        interval = p.get("military_grade_interval")
        grade_display = (f"{interval['lower']}—{interval['upper']}（{interval.get('pending_label', '统筹支撑待证')}）" if interval else p['military_grade'])
        if p.get("military_grade_boundary") and not interval:
            grade_display = ("未定档（当前材料下限ordinary）" if p["military_grade"] == "ordinary"
                             else f"{p['military_grade']}（现有史料下限；更高档待证）")
        elif p.get("grade_status") == "evidence_lower_bound" and not interval:
            grade_display = f"{p['military_grade']}（现有史料下限）"
        lines.append(f"| {_cell(p['dynasty'])} | {_cell(p['person'])} | `{grade_display}` | {ability} | {p['net_strategic_value']:.2f} | {combinations} | {campaigns} |")
    return "\n".join(lines) + "\n"


def validate_mixed_result(row: Mapping[str, Any]) -> None:
    if row.get("result_direction") != "mixed_review" or is_pending(row):
        return
    review = row.get("mixed_result_review") or {}
    if review.get("decision") != "mixed_review":
        raise ValueError("已裁混合结果缺少同方向的正负结果审查")
    for field in ("positive_result", "adverse_result", "retention", "personal_scope"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            raise ValueError(f"已裁混合结果缺少 {field}")
    if not review.get("source_refs"):
        raise ValueError("已裁混合结果缺少史源")
    components = review.get("components", [])
    if len(components) != 2 or {c.get("direction") for c in components} != {"positive", "negative"}:
        raise ValueError("已裁混合结果必须分别核定一份正果与败果")
    for component in components:
        if component.get("effect_tier") not in TIER_VALUE or not component.get("basis") or not component.get("source_refs"):
            raise ValueError("混合单边缺少本人结果尺度或史源")
        if component.get("direction") == "positive" and (component.get("combat_difficulty") not in {None, *DIFFICULTY}
                or component.get("decisive_relation") not in CONTRIBUTION):
            raise ValueError("混合正果缺少本人难度与贡献")
        if component.get("direction") == "negative":
            if component.get("adverse_result_review", {}).get("effect_tier") != component["effect_tier"]:
                raise ValueError("混合败果尺度与后果审查不同值")
            validate_adverse_result({**row, **component, "result_direction": "negative"})


def validate_adverse_result(row: Mapping[str, Any]) -> None:
    if row.get("result_direction") != "negative" or is_pending(row):
        return
    review = row.get("adverse_result_review") or {}
    if (review.get("effect_tier") not in TIER_VALUE or not review.get("basis")
            or not review.get("personal_scope") or not review.get("source_refs")
            or type(review.get("responsibility_coefficient")) not in {int, float}
            or review.get("responsibility_coefficient") not in CONTRIBUTION.values()):
        raise ValueError("已闭败果缺少本人后果、控制范围、结果责任或史源")


def validate_operational_grade(profile: Mapping[str, Any]) -> None:
    """Check declared design-path gates, without assigning a person's grade."""
    review = profile.get("operational_grade_review")
    if not review:
        return
    anchors = {episode_ref(r): r for r in episode_anchors(positive_results(profile))}
    refs = review.get("episode_refs", [])
    if len(refs) != len(set(refs)) or any(ref not in anchors for ref in refs):
        raise ValueError("统筹定档引用重复或未闭正向情境")
    rows = [anchors[ref] for ref in refs]
    operational = [r for r in rows if r.get("consumption_mode") == "operational_result"
                   and r.get("operational_role_review", {}).get("status") == "QUALIFIED"
                   and r.get("operational_role_review", {}).get("major_result") is True]
    frontier = [r for r in rows if r.get("consumption_mode") != "operational_result"
                and r.get("combat_difficulty") in {"D2", "D3", "D4"}
                and r.get("decisive_relation") in {"decisive_creator", "decisive_successor", "co_decisive"}]
    major = [r for r in [*operational, *frontier] if TIER_ORDER[r["campaign_tier"]] >= TIER_ORDER["A"]]
    peaks = [r for r in operational if TIER_ORDER[r["campaign_tier"]] >= TIER_ORDER["S"]]
    path = review.get("path")
    valid = ((path == "elite_operational_peak_with_independent_validation" and len(peaks) >= 1 and len(major) >= 2)
             or (path == "top_operational_system_with_independent_validation" and len(peaks) >= 2 and len(major) >= 3))
    expected = "elite" if path == "elite_operational_peak_with_independent_validation" else "top"
    if not valid or review.get("published_grade") != profile["military_grade"] or profile["military_grade"] != expected:
        raise ValueError("统筹定档路径与已闭情境或发布档位不符")
    for field in ("constraint_resolution", "implementation_result", "independence_basis", "reliability_basis", "source_refs"):
        if not review.get(field):
            raise ValueError(f"统筹高档缺少 {field}")
    if len(review.get("comparators", [])) < 2:
        raise ValueError("统筹高档缺少相邻档横向比较")


def validate_operational_role(row: Mapping[str, Any]) -> None:
    if row.get("consumption_mode") != "operational_result" and row.get("capability_mode") != "operational_design":
        return
    if str(row.get("detail_status") or "") in PENDING_STATUSES or source_conflict(row) or row.get("result_direction") not in {"positive", "negative", "mixed_review"}:
        return
    review = row.get("operational_role_review") or {}
    if review.get("status") != "QUALIFIED":
        raise ValueError("已消费统筹缺少合格操作链")
    if review.get("implemented") is not True or review.get("outcome_established") is not True:
        raise ValueError("统筹操作尚未实施或本人结果未闭")
    for key in ("constraint", "operation", "implementation", "result_link", "personal_scope"):
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise ValueError(f"已消费统筹缺少 {key}")
    if not review.get("source_refs"):
        raise ValueError("已消费统筹缺少史源")
    if row.get("combat_difficulty") is not None:
        raise ValueError("统筹不得继承前线难度")
    if row.get("result_direction") == "positive" and TIER_ORDER.get(str(row.get("campaign_tier")), -1) >= TIER_ORDER["A"] and review.get("major_result") is not True:
        raise ValueError("A级以上统筹必须闭合本人重大成果，不得仅复制国家结果")
    if row.get("result_direction") in {"negative", "mixed_review"}:
        if review.get("failure_established") is not True or review.get("failure_effect_tier") not in TIER_ORDER:
            raise ValueError("统筹不利结果缺少本人实际败果及后果档")


def _validate_records(payload: Mapping[str, Any]) -> None:
    talent_profiles_by_ref(payload)
    ids = [p["person_ref"] for p in payload["profiles"]]
    if len(ids) != len(set(ids)):
        raise ValueError("军事人才存在重复稳定person_ref")
    for p in payload["profiles"]:
        validate_operational_grade(p)
        if p.get("operational_grade_review"):
            comparators = [c.get("person") for c in p["operational_grade_review"]["comparators"]]
            names = {r["person"] for r in payload["profiles"]}
            if len(comparators) != len(set(comparators)) or not set(comparators) <= names or p["person"] in comparators:
                raise ValueError("统筹定档比较对象重复、缺失或指向本人")
        if (p["military_grade"] == "ordinary" and p.get("grade_status") != "evidence_lower_bound"
                and (p.get("career_coverage_review", {}).get("status") != "COMPLETE"
                     or not all(p.get("career_coverage_review", {}).get(key) for key in ("basis", "source_refs", "reviewed_periods")))):
            raise ValueError("确定ordinary必须闭合全生涯覆盖、时段及史源；缺证只能发布材料下限")
        interval = p.get("military_grade_interval")
        if interval:
            lower, upper = interval.get("lower"), interval.get("upper")
            if lower not in GRADE_ORDER or upper not in GRADE_ORDER or GRADE_ORDER.index(lower) > GRADE_ORDER.index(upper):
                raise ValueError("统筹待证档位区间无效")
            if p["military_grade"] != lower or p.get("grade_status") != "evidence_lower_bound" or not interval.get("basis") or not interval.get("source_refs"):
                raise ValueError("统筹待证区间与证据下限不同值或缺少依据")
        for rows in (p.get("consumed_achievements") or [], p.get("negative_or_mixed_command_records") or []):
            for row in rows:
                validate_mixed_result(row)
                validate_adverse_result(row)
                validate_operational_role(row)
                if row.get("capability_mode") not in CAPABILITY_MODES:
                    raise ValueError(f"{p['person']}: 未定义能力模式 {row.get('capability_mode')}")
                if row.get("combat_difficulty") not in {None, *DIFFICULTY}:
                    raise ValueError(f"{p['person']}: 未定义难度 {row.get('combat_difficulty')}")
                if row.get("result_direction") == "positive" and not is_pending(row) and result_value(row) <= 0:
                    raise ValueError(f"{p['person']}: 已消费正向结果没有本人能力信用")
        try:
            verify_failure_aliases(p.get("failure_accountability") or [])
        except AssertionError as exc:
            raise ValueError(f"{p['person']}: 失败别名重复计数或包含自身引用") from exc


def verify(root: Path) -> dict[str, int]:
    path = root / "docs/公共成果/军事/02-武将人才等级.json"
    payload = load_talent_registry(path)
    _validate_records(payload)
    for p in payload["profiles"]:
        value = net_value(p)
        if p["net_strategic_value"] != value["net"] or p["net_strategic_value_breakdown"] != value:
            raise ValueError(f"{p['person']}: 当前记录与净值分解不同值")
        if any(p.get("stability_gate", {}).get(k) != value for k, value in stability_counts(p).items()):
            raise ValueError(f"{p['person']}: 稳定性独立情境计数不同值")
        if p.get("positive_evidence_paths") != positive_evidence_paths(p):
            raise ValueError(f"{p['person']}: 正向事实准入路径不同值")
    refreshed = refresh_values(payload)
    for field in ["profile_count", "grade_counts", "grade_status_counts", "stability_status_counts", "identity_alias_group_count", "evidence_lower_bound_profile_count"]:
        if payload[field] != refreshed[field]:
            raise ValueError(f"军事人才统计不同值: {field}")
    if path.with_suffix(".md").read_text(encoding="utf-8") != render_markdown(payload):
        raise ValueError("军事人才JSON与Markdown阅读视图不同值")
    return {"profiles": len(payload["profiles"]), "net_mismatches": 0, "reading_view_mismatches": 0}


def write_views(root: Path) -> dict[str, Any]:
    """Refresh current-record arithmetic and views; never generate people or grades."""
    path = root / "docs/公共成果/军事/02-武将人才等级.json"
    before = load_talent_registry(path)
    _validate_records(before)
    payload = refresh_values(before)
    episode_path = root / str(payload.get("capability_episode_registry_ref") or "config/military/military-capability-episodes.json")
    if episode_path.is_file():
        payload["capability_episode_count"] = len(json.loads(episode_path.read_text(encoding="utf-8")).get("episodes") or [])
    identities_before = [(p["profile_ref"], p["person_ref"], p["military_grade"]) for p in before["profiles"]]
    identities_after = [(p["profile_ref"], p["person_ref"], p["military_grade"]) for p in payload["profiles"]]
    if identities_before != identities_after:
        raise ValueError("净值刷新不得改变稳定身份或人才档位")
    markdown = render_markdown(payload)
    write_talent_registry(path, payload)
    reading_path = path.with_suffix(".md")
    temporary = reading_path.with_name(f".{reading_path.name}.write-tmp")
    temporary.write_bytes(markdown.encode("utf-8"))
    temporary.replace(reading_path)
    return {**verify(root), "identity_and_grade_changes": 0}
