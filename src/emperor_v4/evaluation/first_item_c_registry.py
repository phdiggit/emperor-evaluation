from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.first_item_a_registry import (
    load_qin_qing_first_item_roster,
)
from emperor_v4.evaluation.first_item_settlement import (
    build_first_item_formal_settlement,
    render_first_item_formal_settlement_markdown,
    render_first_item_summary as render_first_item_summary_analysis,
)
from emperor_v4.evaluation.battle_registry_store import load_battle_registry
from emperor_v4.evaluation.talent_registry_store import load_talent_registry


def validate_first_item_c_territorial_control(
    *,
    battle_registry: Mapping[str, Any],
    window_config: Mapping[str, Any],
    control_registry: Mapping[str, Any],
) -> dict[str, Any]:
    if window_config.get("schema_version") != "first-item-c-acquisition-windows-v1":
        raise ValueError("第一项C创业窗口输入schema_version不正确")
    if window_config.get("status") != "CURRENT":
        raise ValueError("第一项C创业窗口输入状态不正确")
    if control_registry.get("schema_version") != (
        "first-item-c-territorial-control-adjudications-v2"
    ):
        raise ValueError("第一项C区域控制输入schema_version不正确")
    if control_registry.get("status") != "CURRENT_C_INPUT":
        raise ValueError("第一项C区域控制输入状态不正确")
    catalog_rows = list(control_registry.get("region_catalog") or ())
    catalog = {str(row["region_id"]): row for row in catalog_rows}
    if len(catalog) != len(catalog_rows):
        raise ValueError("第一项C区域目录存在重复region_id")

    era_rows = list(control_registry.get("value_era_catalog") or ())
    eras = {str(row["era_id"]): row for row in era_rows}
    if len(eras) != len(era_rows):
        raise ValueError("第一项C价值时代目录存在重复era_id")
    if not eras:
        raise ValueError("第一项C价值时代目录为空")

    baseline_rows = list(control_registry.get("era_region_value_profiles") or ())
    baselines: dict[tuple[str, str], Mapping[str, Any]] = {}
    baseline_ids: set[str] = set()
    baseline_profile_status_counts: Counter[str] = Counter()
    for profile in baseline_rows:
        era_id = str(profile["era_id"])
        region_id = str(profile["region_id"])
        key = (era_id, region_id)
        profile_id = str(profile["value_profile_id"])
        if key in baselines or profile_id in baseline_ids:
            raise ValueError(f"第一项C时代区域基线重复: {profile_id}")
        if era_id not in eras or region_id not in catalog:
            raise ValueError(f"第一项C时代区域基线引用未知目录项: {profile_id}")
        expected_profile_id = f"{era_id}:{region_id}"
        if profile_id != expected_profile_id:
            raise ValueError(f"第一项C时代区域基线标识不稳定: {profile_id}")
        if profile.get("region_name") != catalog[region_id].get("region_name"):
            raise ValueError(f"第一项C时代区域基线名称不一致: {profile_id}")
        if (
            profile.get("profile_status") in {"CALIBRATED", "PARTIAL_SOURCE"}
            and not profile.get("source_refs")
        ):
            raise ValueError(f"第一项C时代区域基线缺少史源: {profile_id}")
        baselines[key] = profile
        baseline_ids.add(profile_id)
        baseline_profile_status_counts[
            str(profile.get("profile_status") or "MISSING_STATUS")
        ] += 1
    expected_baselines = {(era_id, region_id) for era_id in eras for region_id in catalog}
    if set(baselines) != expected_baselines:
        raise ValueError(
            "第一项C时代区域基线覆盖不一致: "
            f"missing={sorted(expected_baselines - set(baselines))}; "
            f"extra={sorted(set(baselines) - expected_baselines)}"
        )

    public_portfolios = {
        str(row["portfolio_ref"]): row
        for row in battle_registry.get("unification_portfolios") or ()
    }
    control_rows = list(control_registry.get("portfolio_adjudications") or ())
    controls = {str(row["portfolio_ref"]): row for row in control_rows}
    if len(controls) != len(control_rows):
        raise ValueError("第一项C创业组合区域控制存在重复portfolio_ref")
    if set(controls) != set(public_portfolios):
        raise ValueError(
            "第一项C创业组合区域控制覆盖不一致: "
            f"missing={sorted(set(public_portfolios) - set(controls))}; "
            f"extra={sorted(set(controls) - set(public_portfolios))}"
        )

    manual_rows = list(control_registry.get("manual_window_adjudications") or ())
    manual_controls = {str(row["ruler_name"]): row for row in manual_rows}
    if len(manual_controls) != len(manual_rows):
        raise ValueError("第一项C手工创业窗口区域控制存在重复ruler_name")
    expected_manual = {
        str(row["ruler_name"]): row
        for row in window_config.get("manual_windows") or ()
    }
    extra_manual = set(manual_controls) - set(expected_manual)
    if extra_manual:
        raise ValueError(f"第一项C区域控制包含未知手工窗口: {sorted(extra_manual)}")
    missing_manual = set(expected_manual) - set(manual_controls)
    if missing_manual:
        raise ValueError(f"第一项C区域控制缺少手工窗口: {sorted(missing_manual)}")

    pending_portfolio_refs: list[str] = []
    missing_profile_refs: dict[str, list[str]] = {}
    raw_net_control: dict[str, float] = {}
    profile_status_counts: Counter[str] = Counter()

    def validate_window(
        *,
        window_ref: str,
        control: Mapping[str, Any],
        expected_group_refs: set[str],
    ) -> None:
        group_rows = list(control.get("group_control_results") or ())
        groups = {str(row["campaign_group_id"]): row for row in group_rows}
        if len(groups) != len(group_rows) or set(groups) != expected_group_refs:
            raise ValueError(
                f"第一项C区域控制战役群覆盖不一致: {window_ref}; "
                f"missing={sorted(expected_group_refs - set(groups))}; "
                f"extra={sorted(set(groups) - expected_group_refs)}"
            )
        snapshots: dict[str, dict[str, float]] = {}
        for field in ("baseline_snapshot", "terminal_snapshot"):
            rows = list(control.get(field) or ())
            values = {
                str(row["region_id"]): float(row["control_fraction"])
                for row in rows
            }
            if len(values) != len(rows):
                raise ValueError(f"第一项C区域控制快照重复: {window_ref}/{field}")
            unknown = set(values) - set(catalog)
            if unknown:
                raise ValueError(f"第一项C区域控制引用未知区域: {sorted(unknown)}")
            snapshots[field] = values
        expected_net = {
            region_id
            for region_id in (
                set(snapshots["baseline_snapshot"])
                | set(snapshots["terminal_snapshot"])
            )
            if snapshots["terminal_snapshot"].get(region_id, 0.0)
            > snapshots["baseline_snapshot"].get(region_id, 0.0)
        }
        declared_net = set(control.get("net_first_control_regions") or ())
        if declared_net != expected_net:
            raise ValueError(f"第一项C区域净控制清单与起终快照不一致: {window_ref}")
        changed_regions = {
            region_id
            for region_id in (
                set(snapshots["baseline_snapshot"])
                | set(snapshots["terminal_snapshot"])
            )
            if snapshots["terminal_snapshot"].get(region_id, 0.0)
            != snapshots["baseline_snapshot"].get(region_id, 0.0)
        }

        value_era_id = str(control.get("value_era_id") or "")
        if value_era_id not in eras:
            raise ValueError(f"第一项C窗口引用未知价值时代: {window_ref}/{value_era_id}")

        first_credit_regions: list[str] = []
        for group in groups.values():
            for effect in group.get("control_effects") or ():
                region_id = str(effect["region_id"])
                if region_id not in catalog:
                    raise ValueError(f"第一项C战役群引用未知区域: {window_ref}/{region_id}")
                if effect.get("region_name") != catalog[region_id].get("region_name"):
                    raise ValueError(f"第一项C战役群区域名称不一致: {window_ref}/{region_id}")
                if effect.get("first_net_control_credit"):
                    if region_id not in declared_net:
                        raise ValueError(f"第一项C错误声明首次净控制: {window_ref}/{region_id}")
                    first_credit_regions.append(region_id)
        if len(first_credit_regions) != len(set(first_credit_regions)):
            raise ValueError(f"第一项C同一区域重复声明首次净控制: {window_ref}")

        override_rows = list(control.get("region_value_overrides") or ())
        overrides = {str(row["region_id"]): row for row in override_rows}
        if len(overrides) != len(override_rows):
            raise ValueError(f"第一项C窗口区域价值覆盖重复: {window_ref}")
        for region_id, profile in overrides.items():
            if region_id not in catalog:
                raise ValueError(f"第一项C窗口区域价值覆盖引用未知区域: {window_ref}/{region_id}")
            if region_id not in changed_regions:
                raise ValueError(f"第一项C窗口区域价值覆盖超出控制变化区域: {window_ref}/{region_id}")
            if profile.get("region_name") != catalog[region_id].get("region_name"):
                raise ValueError(f"第一项C窗口区域价值覆盖名称不一致: {window_ref}/{region_id}")
            if (
                profile.get("profile_status") in {"CALIBRATED", "PARTIAL_SOURCE"}
                and not profile.get("source_refs")
            ):
                raise ValueError(f"第一项C窗口区域价值覆盖缺少史源: {window_ref}/{region_id}")
        effective_profiles = {
            region_id: overrides.get(region_id) or baselines[(value_era_id, region_id)]
            for region_id in changed_regions
        }
        for profile in effective_profiles.values():
            profile_status_counts[
                str(profile.get("profile_status") or "MISSING_STATUS")
            ] += 1
        missing_profiles = sorted(
            region_id
            for region_id in changed_regions
            if effective_profiles[region_id].get("profile_status") != "CALIBRATED"
        )
        if missing_profiles:
            missing_profile_refs[window_ref] = missing_profiles
        raw_net_control[window_ref] = round(
            sum(snapshots["terminal_snapshot"].values())
            - sum(snapshots["baseline_snapshot"].values()),
            2,
        )

    for portfolio_ref, control in controls.items():
        expected_groups = {
            str(row["campaign_group_id"])
            for row in public_portfolios[portfolio_ref].get("campaign_groups") or ()
        }
        validate_window(
            window_ref=portfolio_ref,
            control=control,
            expected_group_refs=expected_groups,
        )
        if (
            control.get("calibration_status")
            == "PENDING_NON_FULL_REALM_CALIBRATION"
            or portfolio_ref in missing_profile_refs
        ):
            pending_portfolio_refs.append(portfolio_ref)

    pending_manual_rulers: list[str] = []
    for ruler_name, control in manual_controls.items():
        expected_refs = set(expected_manual[ruler_name].get("campaign_refs") or ())
        if set(control.get("campaign_refs") or ()) != expected_refs:
            raise ValueError(f"第一项C手工窗口战役引用不一致: {ruler_name}")
        validate_window(
            window_ref=f"MANUAL:{ruler_name}",
            control=control,
            expected_group_refs=expected_refs,
        )
        if (
            control.get("calibration_status") == "PENDING_C_WINDOW_CALIBRATION"
            or f"MANUAL:{ruler_name}" in missing_profile_refs
        ):
            pending_manual_rulers.append(ruler_name)

    return {
        "portfolio_count": len(controls),
        "manual_window_count": len(expected_manual),
        "pending_portfolio_refs": sorted(pending_portfolio_refs),
        "pending_manual_rulers": sorted(set(pending_manual_rulers)),
        "missing_profile_refs": dict(sorted(missing_profile_refs.items())),
        "raw_net_control": dict(sorted(raw_net_control.items())),
        "profile_status_counts": dict(sorted(profile_status_counts.items())),
        "baseline_profile_status_counts": dict(
            sorted(baseline_profile_status_counts.items())
        ),
        "pending_window_count": len(set(pending_portfolio_refs))
        + len(set(pending_manual_rulers)),
    }


REGION_STRATEGIC_SCORE = {
    "ordinary": 1,
    "important": 2,
    "major": 3,
    "core": 4,
    "decisive": 5,
    "unknown": 3,
}
REGION_POPULATION_SCORE = {
    "sparse": 1,
    "limited": 2,
    "substantial": 3,
    "dense": 4,
    "population_core": 5,
    "unknown": 3,
}
REGION_FISCAL_SCORE = {
    "low": 1,
    "moderate": 2,
    "high": 3,
    "fiscal_core": 4,
    "unknown": 2.5,
}
PERSON_CONSUMPTION_WEIGHT = {
    "full_parent": 1.0,
    "joint_parent": 0.8,
    "scoped_projection": 0.65,
    "operational_result": 0.6,
    "person_result": 0.6,
    "none": 0.0,
}
PERSON_SCOPE_WEIGHT = {
    "full_campaign": 1.0,
    "opposed_full_campaign": 0.8,
    "operational_strategy": 0.8,
    "independent_direction": 0.8,
    "supporting_participation": 0.25,
    "no_person_command_credit": 0.0,
}
PORTFOLIO_SCOPE_MULTIPLIER = {
    "FULL_REALM_UNIFICATION": 1.15,
    "REGIONAL_REGIME_FOUNDATION": 1.0,
    "REGIONAL_ANNEXATION": 0.9,
}
FRONTLINE_MODES = {
    "integrated_command",
    "independent_direction",
    "tactical_execution",
}
TIER_SCORE = {"C": 1, "B": 2, "A": 3, "S-": 4, "S": 5, "S+": 6}
C1_RESULT_VALUE = {"C": 1, "B": 2, "A": 4, "S-": 6, "S": 9, "S+": 18}
DIFFICULTY_SCORE = {f"D{index}": index for index in range(6)}
RATE_TABLE = {
    0: {"LOW": 0, "MID": 15, "HIGH": 29},
    1: {"LOW": 30, "MID": 37, "HIGH": 44},
    2: {"LOW": 45, "MID": 52, "HIGH": 59},
    3: {"LOW": 60, "MID": 67, "HIGH": 74},
    4: {"LOW": 75, "MID": 82, "HIGH": 89},
    5: {"LOW": 90, "MID": 95, "HIGH": 100},
}
C2_RATE_TABLE = {
    0: {"LOW": 0, "MID": 8, "HIGH": 16},
    1: {"LOW": 20, "MID": 25, "HIGH": 30},
    2: {"LOW": 34, "MID": 40, "HIGH": 46},
    3: {"LOW": 50, "MID": 57, "HIGH": 64},
    4: {"LOW": 68, "MID": 74, "HIGH": 80},
    5: {"LOW": 84, "MID": 92, "HIGH": 100},
}


def _region_value_index(profile: Mapping[str, Any]) -> float:
    if profile.get("profile_status") != "CALIBRATED":
        raise ValueError(
            "第一项C区域价值画像尚未校准: "
            f"{profile.get('value_profile_id') or profile.get('region_id')}"
        )
    strategic = REGION_STRATEGIC_SCORE[str(profile["strategic_importance"])] / 5
    population = REGION_POPULATION_SCORE[str(profile["population_capacity"])] / 5
    fiscal = REGION_FISCAL_SCORE[str(profile["fiscal_supply_capacity"])] / 4
    return round(100 * (0.5 * strategic + 0.3 * population + 0.2 * fiscal), 2)


def _member_weight(member: Mapping[str, Any]) -> float:
    index = member.get("person_command_index") or {}
    consumption = PERSON_CONSUMPTION_WEIGHT.get(
        str(index.get("consumption_mode") or "none"), 0.0
    )
    scope = PERSON_SCOPE_WEIGHT.get(str(index.get("command_scope") or ""), 0.0)
    return round((consumption + scope) / 2, 4)


def _band_axis(
    *,
    axis: str,
    raw_value: float,
    bands: Mapping[int, tuple[float, float]],
    weight: int,
    zero_position: str = "LOW",
    position_cutoffs: Mapping[int, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    if raw_value <= 0:
        grade = 0
        position = zero_position
    else:
        grade = max(bands)
        low, high = bands[grade]
        for candidate in sorted(bands):
            candidate_low, candidate_high = bands[candidate]
            if raw_value < candidate_high:
                grade = candidate
                low, high = candidate_low, candidate_high
                break
        if position_cutoffs and grade in position_cutoffs:
            mid_cutoff, high_cutoff = position_cutoffs[grade]
            position = (
                "LOW"
                if raw_value < mid_cutoff
                else "MID"
                if raw_value < high_cutoff
                else "HIGH"
            )
        else:
            ratio = min(1.0, max(0.0, (raw_value - low) / (high - low)))
            position = (
                "LOW" if ratio < 1 / 3 else "MID" if ratio < 2 / 3 else "HIGH"
            )
    rate = RATE_TABLE[grade][position]
    return {
        "axis": axis,
        "raw_index": round(raw_value, 2),
        "grade": grade,
        "position": position,
        "rate": rate,
        "weight": weight,
        "points": round(weight * rate / 100, 1),
    }


def _c2_axis(
    results: Mapping[str, Mapping[str, Any]],
    failures: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    positive = sorted(
        (
            row
            for row in results.values()
            if row["result_direction"] in {"positive", "mixed_review"}
        ),
        key=lambda row: (
            -float(row["quality_index"]),
            str(row["capability_episode_ref"]),
        ),
    )
    negative = sorted(
        (
            row
            for row in results.values()
            if row["result_direction"] == "negative"
        ),
        key=lambda row: (
            -float(row["quality_index"]),
            str(row["capability_episode_ref"]),
        ),
    )

    def tier_rank(row: Mapping[str, Any]) -> int:
        return TIER_SCORE.get(str(row.get("personal_result_tier") or ""), 0)

    def difficulty_rank(row: Mapping[str, Any]) -> int:
        return DIFFICULTY_SCORE.get(str(row.get("combat_difficulty") or "D0"), 0)

    peak = positive[0] if positive else None
    peak_quality = float(peak["quality_index"]) if peak else 0.0
    positive_a = [row for row in positive if tier_rank(row) >= TIER_SCORE["A"]]
    positive_b = [row for row in positive if tier_rank(row) >= TIER_SCORE["B"]]
    positive_s_minus = [
        row for row in positive if tier_rank(row) >= TIER_SCORE["S-"]
    ]
    high_difficulty = [
        row
        for row in positive_a
        if difficulty_rank(row) >= 3
    ]

    grade = 0
    grade_path = "NO_POSITIVE_FRONTLINE_RESULT"
    if positive:
        grade = 1
        grade_path = "C_OR_B_FRONTLINE_RESULT"
    if positive_a or len(positive_b) >= 2:
        grade = 2
        grade_path = "A_RESULT_OR_TWO_B_RESULTS"
    if any(
        (tier_rank(row) >= TIER_SCORE["A"] and difficulty_rank(row) >= 2)
        or tier_rank(row) >= TIER_SCORE["S-"]
        for row in positive
    ):
        grade = 3
        grade_path = "A_D2_OR_S_MINUS_PEAK"
    if any(
        (tier_rank(row) >= TIER_SCORE["S-"] and difficulty_rank(row) >= 2)
        or tier_rank(row) >= TIER_SCORE["S"]
        for row in positive
    ) or len(high_difficulty) >= 2:
        grade = 4
        grade_path = "S_MINUS_D2_OR_MULTI_A_D3"

    path_s_plus = bool(
        peak
        and tier_rank(peak) >= TIER_SCORE["S+"]
        and difficulty_rank(peak) >= 3
        and len(positive_s_minus) >= 2
    )
    path_s = bool(
        peak
        and tier_rank(peak) >= TIER_SCORE["S"]
        and difficulty_rank(peak) >= 3
        and len(high_difficulty) >= 2
    )
    path_sustained = bool(
        len(
            [
                row
                for row in positive_s_minus
                if difficulty_rank(row) >= 3
            ]
        )
        >= 2
        and len(high_difficulty) >= 3
    )
    if path_s_plus or path_s or path_sustained:
        grade = 5
        grade_path = (
            "S_PLUS_WITH_STRONG_REVALIDATION"
            if path_s_plus
            else "S_WITH_INDEPENDENT_HIGH_DIFFICULTY_REVALIDATION"
            if path_s
            else "SUSTAINED_MULTI_CONTEXT_HIGH_COMMAND"
        )

    severe_negative = [row for row in negative if tier_rank(row) >= TIER_SCORE["S-"]]
    major_negative = [row for row in negative if tier_rank(row) >= TIER_SCORE["A"]]
    severe_failures = [
        row
        for row in failures.values()
        if TIER_SCORE.get(str(row.get("failure_impact_tier") or ""), 0)
        >= TIER_SCORE["S-"]
    ]
    major_failures = [
        row
        for row in failures.values()
        if TIER_SCORE.get(str(row.get("failure_impact_tier") or ""), 0)
        >= TIER_SCORE["A"]
    ]
    grade_cap = 5
    cap_reasons: list[str] = []
    if severe_negative:
        grade_cap = min(grade_cap, 4)
        cap_reasons.append("S_MINUS_OR_HIGHER_FRONTLINE_DEFEAT_BLOCKS_GRADE_5")
    if severe_failures:
        grade_cap = min(grade_cap, 3)
        cap_reasons.append("S_MINUS_OR_HIGHER_PRIMARY_COMMAND_FAILURE_CAPS_GRADE_3")
    elif len(major_failures) >= 2:
        grade_cap = min(grade_cap, 4)
        cap_reasons.append("REPEATED_A_OR_HIGHER_COMMAND_FAILURES_BLOCK_GRADE_5")
    if grade > grade_cap:
        grade = grade_cap
        grade_path = f"CAPPED_FROM_{grade_path}"

    if grade == 0:
        position = "MID" if negative or failures else "LOW"
    elif grade == 5:
        position = (
            "HIGH"
            if peak
            and tier_rank(peak) >= TIER_SCORE["S+"]
            and difficulty_rank(peak) >= 4
            and len(positive_s_minus) >= 3
            and len(high_difficulty) >= 3
            else "MID"
            if (
                peak
                and tier_rank(peak) >= TIER_SCORE["S"]
                and difficulty_rank(peak) >= 4
                and len(high_difficulty) >= 2
            )
            else "LOW"
        )
    elif grade == 4:
        position = (
            "HIGH"
            if peak_quality >= 6.2 or len(high_difficulty) >= 3
            else "MID"
            if peak_quality >= 5.2 or len(positive_a) >= 2
            else "LOW"
        )
    elif grade == 3:
        position = (
            "HIGH"
            if peak_quality >= 4.2 or len(positive_a) >= 3
            else "MID"
            if len(positive_a) >= 2 or peak_quality >= 3.9
            else "LOW"
        )
    elif grade == 2:
        position = (
            "HIGH"
            if peak_quality >= 3.6 or len(positive_b) >= 3
            else "MID"
            if len(positive_b) >= 2 or peak_quality >= 3.3
            else "LOW"
        )
    else:
        position = (
            "HIGH"
            if peak_quality >= 2.9
            else "MID"
            if peak_quality >= 2.3 or len(positive) >= 2
            else "LOW"
        )

    position_order = ["LOW", "MID", "HIGH"]
    negative_steps = 0
    abundant_grade_5_validation = bool(
        grade == 5
        and len(positive_s_minus) >= 2
        and len(high_difficulty) >= 2
        and len(positive_a) >= 3
        and not severe_negative
        and not severe_failures
    )
    if major_negative and not abundant_grade_5_validation:
        negative_steps += 1
    if severe_negative or len(major_negative) >= 2:
        negative_steps += 1
    if major_failures and not abundant_grade_5_validation:
        negative_steps += 1
    if severe_failures or len(major_failures) >= 2:
        negative_steps += 1
    if grade > 0 and negative_steps:
        position = position_order[
            max(0, position_order.index(position) - min(2, negative_steps))
        ]

    rate = C2_RATE_TABLE[grade][position]
    return {
        "axis": "C2",
        "raw_index": round(peak_quality, 2),
        "peak_quality_index": round(peak_quality, 2),
        "grade": grade,
        "position": position,
        "rate": rate,
        "weight": 30,
        "points": round(30 * rate / 100, 1),
        "grade_path": grade_path,
        "grade_cap": grade_cap,
        "cap_reasons": cap_reasons,
        "positive_context_count": len(positive),
        "high_difficulty_context_count": len(high_difficulty),
        "negative_context_count": len(negative),
        "command_failure_count": len(failures),
        "negative_position_steps": min(2, negative_steps),
        "abundant_grade_5_validation": abundant_grade_5_validation,
    }


def build_first_item_c_registry(
    *,
    battle_registry: Mapping[str, Any],
    talent_registry: Mapping[str, Any],
    roster: Mapping[str, Any],
    scope_inputs: Mapping[str, Any],
    window_config: Mapping[str, Any],
    control_registry: Mapping[str, Any],
) -> dict[str, Any]:
    control_summary = validate_first_item_c_territorial_control(
        battle_registry=battle_registry,
        window_config=window_config,
        control_registry=control_registry,
    )
    pending_control = int(control_summary["pending_window_count"])
    if pending_control:
        raise ValueError(
            "第一项C canonical结算已关闭：仍有"
            f"{pending_control}个创业窗口未完成区域控制与价值校准"
        )

    roster_rows = list(roster.get("records") or ())
    roster_names = {str(row["ruler_name"]) for row in roster_rows}
    if len(roster_names) != len(roster_rows):
        raise ValueError("第一项C名册存在重复ruler_name")
    applicable_names = {
        str(row["ruler_name"]) for row in scope_inputs.get("records") or ()
    }
    if not applicable_names or not applicable_names <= roster_names:
        raise ValueError("第一项C奠基者范围与评价名册不一致")
    aliases = {name: name for name in roster_names}
    talent_profiles_by_name: dict[str, list[Mapping[str, Any]]] = {}
    talent_profiles_by_ref: dict[str, Mapping[str, Any]] = {}
    for row in talent_registry.get("profiles") or ():
        talent_profiles_by_ref[str(row.get("profile_ref") or "")] = row
        for surface in [str(row["person"]), *(str(x) for x in row.get("name_aliases") or ())]:
            bucket = talent_profiles_by_name.setdefault(surface, [])
            if all(existing.get("profile_ref") != row.get("profile_ref") for existing in bucket):
                bucket.append(row)
    founder_metadata = {
        str(row["ruler_name"]): row
        for row in scope_inputs.get("founder_roster") or ()
    }

    def talent_profile_for(ruler_name: str) -> Mapping[str, Any]:
        candidates = talent_profiles_by_name.get(ruler_name) or []
        expected_ref = str(
            (founder_metadata.get(ruler_name) or {}).get("talent_profile_ref") or ""
        )
        if expected_ref:
            matched = talent_profiles_by_ref.get(expected_ref)
            if matched is None:
                raise ValueError(
                    f"第一项C指定人才画像不存在或不唯一: {ruler_name}/{expected_ref}"
                )
            return matched
        return candidates[0] if len(candidates) == 1 else {}
    for ruler_name in roster_names:
        profile = talent_profile_for(ruler_name)
        for alias in profile.get("name_aliases") or ():
            aliases[str(alias)] = ruler_name

    profiles = {
        (str(row["era_id"]), str(row["region_id"])): row
        for row in control_registry["era_region_value_profiles"]
    }
    profile_indexes = {
        key: _region_value_index(row)
        for key, row in profiles.items()
        if row.get("profile_status") == "CALIBRATED"
    }
    portfolio_lookup = {
        str(row["portfolio_ref"]): row
        for row in battle_registry.get("unification_portfolios") or ()
    }
    ordinary_lookup = {
        str(row["war_event_id"]): row for row in battle_registry.get("records") or ()
    }
    incomplete = {
        str(row["ruler_name"]): str(row["gap"])
        for row in window_config.get("evidence_incomplete_rulers") or ()
    }
    manual_window_inputs = {
        str(row["ruler_name"]): row
        for row in window_config.get("manual_windows") or ()
    }
    for ruler_name, window_input in manual_window_inputs.items():
        c1_refs = [str(value) for value in window_input.get("campaign_refs") or ()]
        c2_refs = [
            str(value)
            for value in window_input.get("c2_campaign_refs") or c1_refs
        ]
        if len(c2_refs) != len(set(c2_refs)):
            raise ValueError(f"第一项C2手工窗口存在重复战役引用: {ruler_name}")
        missing_c1_refs = set(c1_refs) - set(c2_refs)
        if missing_c1_refs:
            raise ValueError(
                f"第一项C2手工窗口遗漏C1战役: {ruler_name}: "
                f"{sorted(missing_c1_refs)}"
            )
        unknown_refs = set(c2_refs) - set(ordinary_lookup)
        if unknown_refs:
            raise ValueError(
                f"第一项C2手工窗口引用未知公共战役: {ruler_name}: "
                f"{sorted(unknown_refs)}"
            )
    metrics: dict[str, dict[str, Any]] = {
        name: {
            "c1_results": {},
            "c2_results": {},
            "c2_failures": {},
            "window_refs": set(),
        }
        for name in roster_names
    }
    window_metrics: list[dict[str, Any]] = []

    def public_group(
        window: Mapping[str, Any], group_id: str, *, manual: bool
    ) -> Mapping[str, Any]:
        if manual:
            if group_id not in ordinary_lookup:
                raise ValueError(f"第一项C手工窗口找不到公共战役: {group_id}")
            return ordinary_lookup[group_id]
        portfolio = portfolio_lookup[str(window["portfolio_ref"])]
        group = next(
            (
                row
                for row in portfolio.get("campaign_groups") or ()
                if str(row["campaign_group_id"]) == group_id
            ),
            None,
        )
        if group is None:
            raise ValueError(f"第一项C组合窗口找不到公共战役群: {group_id}")
        return group

    for section in ("portfolio_adjudications", "manual_window_adjudications"):
        for window in control_registry[section]:
            manual = section == "manual_window_adjudications"
            window_ref = (
                f"MANUAL:{window['ruler_name']}"
                if manual
                else str(window["portfolio_ref"])
            )
            scope_kind = "MANUAL_C_WINDOW" if manual else str(window["scope_kind"])
            scope_multiplier = (
                1.0 if manual else PORTFOLIO_SCOPE_MULTIPLIER[scope_kind]
            )
            era_id = str(window["value_era_id"])
            overrides = {
                str(row["region_id"]): row
                for row in window.get("region_value_overrides") or ()
            }
            baseline = {
                str(row["region_id"]): float(row["control_fraction"])
                for row in window.get("baseline_snapshot") or ()
            }
            terminal = {
                str(row["region_id"]): float(row["control_fraction"])
                for row in window.get("terminal_snapshot") or ()
            }
            deltas = {
                region_id: terminal.get(region_id, 0.0) - baseline.get(region_id, 0.0)
                for region_id in sorted(set(baseline) | set(terminal))
                if terminal.get(region_id, 0.0) != baseline.get(region_id, 0.0)
            }
            value_indexes = {
                region_id: _region_value_index(overrides[region_id])
                if region_id in overrides
                else profile_indexes[(era_id, region_id)]
                for region_id in deltas
            }
            raw_window_value = sum(
                delta * value_indexes[region_id]
                for region_id, delta in deltas.items()
            )
            weighted_window_value = raw_window_value * scope_multiplier
            group_controls = {
                str(row["campaign_group_id"]): row
                for row in window.get("group_control_results") or ()
            }
            if manual:
                c1_ref_set = {
                    str(value)
                    for value in (
                        manual_window_inputs[str(window["ruler_name"])].get(
                            "campaign_refs"
                        )
                        or window.get("campaign_refs")
                        or ()
                    )
                }
                c2_refs = (
                    manual_window_inputs[str(window["ruler_name"])].get(
                        "c2_campaign_refs"
                    )
                    or window.get("campaign_refs")
                    or ()
                )
                c2_groups = [
                    (group_id, public_group(window, group_id, manual=True))
                    for group_id in c2_refs
                ]
            else:
                c2_groups = [
                    (str(row["campaign_group_id"]), row)
                    for row in portfolio_lookup[str(window["portfolio_ref"])].get(
                        "campaign_groups"
                    )
                    or ()
                ]
                c1_ref_set = {group_id for group_id, _ in c2_groups}
            attributed_regions: set[str] = set()

            for region_id, total_delta in deltas.items():
                candidates: list[tuple[str, float]] = []
                for group_id, group_control in group_controls.items():
                    for effect in group_control.get("control_effects") or ():
                        if str(effect["region_id"]) != region_id:
                            continue
                        if total_delta > 0:
                            amount = max(
                                0.0,
                                min(
                                    float(effect["post_control_fraction"]),
                                    float(effect["window_end_control_fraction"]),
                                )
                                - float(effect["pre_control_fraction"]),
                            )
                        else:
                            amount = max(
                                0.0,
                                float(effect["pre_control_fraction"])
                                - float(effect["post_control_fraction"]),
                            )
                        if amount:
                            candidates.append((group_id, amount))
                amount_sum = sum(amount for _, amount in candidates)
                if not amount_sum:
                    continue
                attributed_regions.add(region_id)

            for group_id, group in c2_groups:
                negative_rulers_in_group: set[str] = set()
                for member in group.get("members") or ():
                    actor_name = str(
                        member.get("actor_name") or member.get("person_name") or ""
                    )
                    ruler_name = aliases.get(actor_name)
                    if ruler_name not in metrics:
                        continue
                    if manual and ruler_name != str(window["ruler_name"]):
                        continue
                    if not _member_weight(member):
                        continue
                    index = member.get("person_command_index") or {}
                    command_result = member.get("person_command_result") or {}
                    if not isinstance(command_result, Mapping):
                        command_result = {}
                    capability = member.get("military_capability_contribution") or {}
                    if not isinstance(capability, Mapping):
                        capability = {}
                    if not capability:
                        capability = (
                            command_result.get("military_capability_contribution") or {}
                        )
                    if not isinstance(capability, Mapping):
                        capability = {}
                    capability_mode = str(
                        index.get("capability_mode")
                        or capability.get("capability_mode")
                        or ""
                    )
                    relation = str(member.get("ruler_campaign_relation") or "")
                    tier = str(index.get("projected_result_tier") or "")
                    difficulty = str(
                        index.get("projected_combat_difficulty") or "D0"
                    )
                    direction = str(index.get("result_direction") or "")
                    if tier not in TIER_SCORE or direction not in {
                        "positive",
                        "negative",
                        "mixed_review",
                    }:
                        continue
                    episode_ref = str(
                        index.get("capability_episode_ref")
                        or f"{window_ref}:{group_id}:{ruler_name}"
                    )
                    if group_id in c1_ref_set:
                        result_value = float(C1_RESULT_VALUE[tier])
                        if direction == "negative":
                            result_value = -result_value
                        c1_result = {
                            "result_ref": episode_ref,
                            "window_ref": window_ref,
                            "campaign_group_id": group_id,
                            "result_direction": direction,
                            "personal_result_tier": tier,
                            "result_value": result_value,
                            "basis": str(index.get("basis") or ""),
                            "source_refs": list(index.get("source_refs") or ()),
                        }
                        current_c1 = metrics[ruler_name]["c1_results"].get(
                            episode_ref
                        )
                        if current_c1 is None or abs(result_value) > abs(
                            float(current_c1["result_value"])
                        ):
                            metrics[ruler_name]["c1_results"][episode_ref] = c1_result
                            metrics[ruler_name]["window_refs"].add(window_ref)
                    if (
                        capability_mode not in FRONTLINE_MODES
                        and relation != "frontline_command"
                    ):
                        continue
                    quality = TIER_SCORE[tier] + 0.3 * DIFFICULTY_SCORE.get(
                        difficulty, 0
                    )
                    result = {
                        "capability_episode_ref": episode_ref,
                        "window_ref": window_ref,
                        "campaign_group_id": group_id,
                        "result_direction": direction,
                        "personal_result_tier": tier,
                        "combat_difficulty": difficulty,
                        "quality_index": round(quality, 2),
                        "basis": str(index.get("basis") or ""),
                        "source_refs": list(index.get("source_refs") or ()),
                    }
                    if direction == "negative":
                        negative_rulers_in_group.add(ruler_name)
                    current = metrics[ruler_name]["c2_results"].get(episode_ref)
                    if current is None or quality > float(current["quality_index"]):
                        metrics[ruler_name]["c2_results"][episode_ref] = result
                        metrics[ruler_name]["window_refs"].add(window_ref)

                for failure_index, failure in enumerate(
                    group.get("attributable_failures") or ()
                ):
                    actor_name = str(failure.get("actor_name") or "")
                    ruler_name = aliases.get(actor_name)
                    if ruler_name not in metrics:
                        continue
                    if manual and ruler_name != str(window["ruler_name"]):
                        continue
                    if ruler_name in negative_rulers_in_group:
                        continue
                    failure_domain = str(failure.get("failure_domain") or "")
                    if failure_domain and failure_domain not in {
                        "command_failure",
                        "operational_failure",
                        "battlefield_command_failure",
                    }:
                        continue
                    responsibility = str(failure.get("responsibility") or "")
                    if responsibility not in {"primary", "co_primary"}:
                        continue
                    failure_tier = str(failure.get("failure_impact_tier") or "")
                    if failure_tier not in TIER_SCORE:
                        continue
                    failure_ref = f"{window_ref}:{group_id}:failure:{failure_index}"
                    metrics[ruler_name]["c2_failures"][failure_ref] = {
                        "failure_ref": failure_ref,
                        "window_ref": window_ref,
                        "campaign_group_id": group_id,
                        "failure_impact_tier": failure_tier,
                        "responsibility": responsibility,
                        "severity_index": float(
                            failure.get("severity_index") or 0.0
                        ),
                        "failure_domain": failure_domain or "command_failure",
                        "basis": str(failure.get("basis") or ""),
                        "source_refs": list(failure.get("source_refs") or ()),
                    }
                    metrics[ruler_name]["window_refs"].add(window_ref)

            window_metrics.append(
                {
                    "window_ref": window_ref,
                    "scope_kind": scope_kind,
                    "value_era_id": era_id,
                    "raw_net_control": round(sum(deltas.values()), 2),
                    "raw_weighted_net_control": round(raw_window_value, 2),
                    "scope_multiplier": scope_multiplier,
                    "calibrated_weighted_net_control": round(
                        weighted_window_value, 2
                    ),
                    "changed_region_count": len(deltas),
                    "unattributed_region_ids": sorted(set(deltas) - attributed_regions),
                }
            )

    for supplement in window_config.get("talent_episode_supplements") or ():
        ruler_name = str(supplement.get("ruler_name") or "")
        if ruler_name not in applicable_names:
            raise ValueError(f"第一项C人才窗口补充对象不适用: {ruler_name}")
        profile = talent_profile_for(ruler_name)
        if not profile:
            raise ValueError(f"第一项C人才窗口补充缺少人才画像: {ruler_name}")
        positive_by_ref = {
            str(row.get("campaign_ref") or ""): row
            for row in profile.get("consumed_achievements") or ()
        }
        adverse_by_ref = {
            str(row.get("campaign_ref") or ""): row
            for row in profile.get("negative_or_mixed_command_records") or ()
        }
        for row in profile.get("failure_accountability") or ():
            adverse_by_ref.setdefault(str(row.get("campaign_ref") or ""), row)

        requested_positive = [
            str(value) for value in supplement.get("positive_campaign_refs") or ()
        ]
        requested_adverse = [
            str(value) for value in supplement.get("adverse_campaign_refs") or ()
        ]
        if len(requested_positive) != len(set(requested_positive)) or len(
            requested_adverse
        ) != len(set(requested_adverse)):
            raise ValueError(f"第一项C人才窗口补充存在重复引用: {ruler_name}")
        missing = (set(requested_positive) - set(positive_by_ref)) | (
            set(requested_adverse) - set(adverse_by_ref)
        )
        if missing:
            raise ValueError(
                f"第一项C人才窗口补充引用不存在: {ruler_name}: {sorted(missing)}"
            )

        for direction, requested, lookup in (
            ("positive", requested_positive, positive_by_ref),
            ("negative", requested_adverse, adverse_by_ref),
        ):
            for campaign_ref in requested:
                source = lookup[campaign_ref]
                tier = str(source.get("campaign_tier") or "")
                if tier not in TIER_SCORE:
                    raise ValueError(
                        f"第一项C人才窗口补充缺少有效人物结果档: {ruler_name}/{campaign_ref}"
                    )
                result_value = float(C1_RESULT_VALUE[tier])
                if direction == "negative":
                    result_value = -result_value
                result_ref = f"TALENT-SUPPLEMENT:{campaign_ref}:{direction}"
                metrics[ruler_name]["c1_results"][result_ref] = {
                    "result_ref": result_ref,
                    "window_ref": f"TALENT-SUPPLEMENT:{ruler_name}",
                    "campaign_group_id": campaign_ref,
                    "result_direction": direction,
                    "personal_result_tier": tier,
                    "result_value": result_value,
                    "basis": str(source.get("basis") or supplement.get("basis") or ""),
                    "source_refs": list(source.get("source_refs") or ()),
                }
                metrics[ruler_name]["window_refs"].add(
                    f"TALENT-SUPPLEMENT:{ruler_name}"
                )
                capability_mode = str(source.get("capability_mode") or "")
                difficulty = str(source.get("combat_difficulty") or "")
                if capability_mode not in FRONTLINE_MODES or difficulty not in DIFFICULTY_SCORE:
                    continue
                quality = TIER_SCORE[tier] + 0.3 * DIFFICULTY_SCORE[difficulty]
                metrics[ruler_name]["c2_results"][result_ref] = {
                    "capability_episode_ref": result_ref,
                    "window_ref": f"TALENT-SUPPLEMENT:{ruler_name}",
                    "campaign_group_id": campaign_ref,
                    "result_direction": direction,
                    "personal_result_tier": tier,
                    "combat_difficulty": difficulty,
                    "quality_index": round(quality, 2),
                    "basis": str(source.get("basis") or supplement.get("basis") or ""),
                    "source_refs": list(source.get("source_refs") or ()),
                }
    for supplement in window_config.get("public_person_result_supplements") or ():
        ruler_name = str(supplement.get("ruler_name") or "")
        if ruler_name not in applicable_names:
            raise ValueError(f"第一项C公共人物结果补充对象不适用: {ruler_name}")
        result_ref = str(supplement.get("result_ref") or "")
        parent_ref = str(supplement.get("parent_war_ref") or "")
        parent = ordinary_lookup.get(parent_ref)
        if not result_ref or parent is None or not parent.get("public_outcome_registered"):
            raise ValueError(f"第一项C公共人物结果补充缺少有效父战役: {ruler_name}/{parent_ref}")
        tier = str(supplement.get("campaign_tier") or "")
        difficulty = str(supplement.get("combat_difficulty") or "")
        direction = str(supplement.get("result_direction") or "")
        capability_mode = str(supplement.get("capability_mode") or "")
        source_refs = list(supplement.get("source_refs") or ())
        basis = str(supplement.get("basis") or "")
        if (
            tier not in TIER_SCORE
            or difficulty not in DIFFICULTY_SCORE
            or direction not in {"positive", "negative"}
            or not source_refs
            or not basis
        ):
            raise ValueError(f"第一项C公共人物结果补充字段无效: {ruler_name}/{result_ref}")
        result_value = float(C1_RESULT_VALUE[tier]) * (1 if direction == "positive" else -1)
        window_ref = f"PUBLIC-PERSON-SUPPLEMENT:{ruler_name}"
        metrics[ruler_name]["c1_results"][result_ref] = {
            "result_ref": result_ref,
            "window_ref": window_ref,
            "campaign_group_id": parent_ref,
            "result_direction": direction,
            "personal_result_tier": tier,
            "result_value": result_value,
            "basis": basis,
            "source_refs": source_refs,
        }
        metrics[ruler_name]["window_refs"].add(window_ref)
        if capability_mode in FRONTLINE_MODES:
            quality = TIER_SCORE[tier] + 0.3 * DIFFICULTY_SCORE[difficulty]
            metrics[ruler_name]["c2_results"][result_ref] = {
                "capability_episode_ref": result_ref,
                "window_ref": window_ref,
                "campaign_group_id": parent_ref,
                "result_direction": direction,
                "personal_result_tier": tier,
                "combat_difficulty": difficulty,
                "quality_index": round(quality, 2),
                "basis": basis,
                "source_refs": source_refs,
            }
    # A ruler can enter the same canonical campaign through both a unification
    # portfolio and a talent supplement.  The campaign parent, rather than the
    # source window or synthetic episode id, is the scoring unit.  Preserve a
    # separately evidenced positive and negative result in the same parent, but
    # never let parallel windows duplicate the same directional result.
    for metric in metrics.values():
        c1_by_parent_direction: dict[tuple[str, str], dict[str, Any]] = {}
        for row in metric["c1_results"].values():
            key = (
                str(row["campaign_group_id"]),
                str(row["result_direction"]),
            )
            current = c1_by_parent_direction.get(key)
            if current is None or abs(float(row["result_value"])) > abs(
                float(current["result_value"])
            ):
                c1_by_parent_direction[key] = row
        metric["c1_results"] = {
            str(row["result_ref"]): row
            for row in c1_by_parent_direction.values()
        }

        c2_by_parent_direction: dict[tuple[str, str], dict[str, Any]] = {}
        for row in metric["c2_results"].values():
            key = (
                str(row["campaign_group_id"]),
                str(row["result_direction"]),
            )
            current = c2_by_parent_direction.get(key)
            if current is None or float(row["quality_index"]) > float(
                current["quality_index"]
            ):
                c2_by_parent_direction[key] = row
        metric["c2_results"] = {
            str(row["capability_episode_ref"]): row
            for row in c2_by_parent_direction.values()
        }

    c1_bands = {
        1: (0.0, 4.0),
        2: (4.0, 9.0),
        3: (9.0, 16.0),
        4: (16.0, 28.0),
        5: (28.0, 50.0),
    }
    c1_position_cutoffs = {5: (36.0, 42.0)}
    records: list[dict[str, Any]] = []
    for ruler in roster_rows:
        ruler_name = str(ruler["ruler_name"])
        if ruler_name not in applicable_names:
            metadata = founder_metadata.get(ruler_name) or {}
            pending = str(metadata.get("eligibility_decision") or "") in {
                "PENDING",
                "UNKNOWN",
            }
            records.append(
                {
                    "ruler_id": ruler["ruler_id"],
                    "ruler_name": ruler_name,
                    "polity": ruler.get("polity"),
                    "scope_status": (
                        "PENDING_FOUNDER_EVIDENCE"
                        if pending
                        else "NOT_APPLICABLE_NON_FOUNDER"
                    ),
                    "score_applicable": False,
                    "C1": None,
                    "C2": None,
                    "C_score_points": None,
                    "window_refs": [],
                    "military_talent_grade": (
                        talent_profile_for(ruler_name)
                    ).get("military_grade"),
                    "coverage_status": (
                        "PENDING_FOUNDER_EVIDENCE"
                        if pending
                        else "NOT_APPLICABLE_NON_FOUNDER"
                    ),
                    "default_applied": False,
                    "default_basis": str(
                        metadata.get("eligibility_basis")
                        or (
                            "存在统一链贡献可能，但人物归责或窗口证据尚未闭合。"
                            if pending
                            else "本对象未对所属王朝或独立政权统一链形成可归责贡献，第一项不适用。"
                        )
                    ),
                    "unresolved_gaps": [],
                    "score_ready": not pending,
                }
            )
            continue
        metric = metrics[ruler_name]
        c1_results = list(metric["c1_results"].values())
        c1_positive = sum(
            float(row["result_value"])
            for row in c1_results
            if float(row["result_value"]) > 0
        )
        c1_negative = sum(
            float(row["result_value"])
            for row in c1_results
            if float(row["result_value"]) < 0
        )
        c1_raw = round(c1_positive + c1_negative, 2)
        c2 = _c2_axis(metric["c2_results"], metric["c2_failures"])
        c2_raw = float(c2["raw_index"])
        has_evidence = bool(
            metric["c1_results"]
            or metric["c2_results"]
            or metric["c2_failures"]
        )
        default_gap = incomplete.get(ruler_name) if not has_evidence else None
        if c1_raw < 0:
            c1_zero_position = "MID"
        elif c1_raw == 0 and has_evidence:
            c1_zero_position = "HIGH"
        else:
            c1_zero_position = "LOW"
        c1 = _band_axis(
            axis="C1",
            raw_value=c1_raw,
            bands=c1_bands,
            weight=50,
            zero_position=c1_zero_position,
            position_cutoffs=c1_position_cutoffs,
        )
        if default_gap:
            coverage_status = "DEFAULT_ZERO_EVIDENCE_GAP"
            default_basis = (
                f"当前材料缺口：{default_gap}按canonical完整结算合同，"
                "C1、C2采用保守默认0档LOW；该默认不等同于史实确认无军事贡献。"
            )
        elif has_evidence:
            coverage_status = "CALIBRATED_C_WINDOW_RESULT"
            default_basis = None
        else:
            coverage_status = "NO_PERSONAL_MILITARY_CONTRIBUTION"
            default_basis = "当前已覆盖创业窗口中没有可归于本人的合格军事贡献。"
        record = {
            "ruler_id": ruler["ruler_id"],
            "ruler_name": ruler_name,
            "polity": ruler.get("polity"),
            "scope_status": "APPLICABLE_DYNASTY_FOUNDER",
            "score_applicable": True,
            "C1": {
                **c1,
                "positive_result_value": round(c1_positive, 2),
                "negative_result_value": round(c1_negative, 2),
                "campaign_results": sorted(
                    c1_results,
                    key=lambda row: (
                        -abs(float(row["result_value"])),
                        str(row["window_ref"]),
                        str(row["campaign_group_id"]),
                    ),
                ),
            },
            "C2": {
                **c2,
                "frontline_results": sorted(
                    metric["c2_results"].values(),
                    key=lambda row: (
                        -float(row["quality_index"]),
                        str(row["capability_episode_ref"]),
                    ),
                ),
                "command_failures": sorted(
                    metric["c2_failures"].values(),
                    key=lambda row: (
                        -TIER_SCORE.get(str(row["failure_impact_tier"]), 0),
                        str(row["failure_ref"]),
                    ),
                ),
            },
            "C_score_points": round(c1["points"] + c2["points"], 1),
            "window_refs": sorted(metric["window_refs"]),
            "military_talent_grade": (
                talent_profile_for(ruler_name)
            ).get("military_grade"),
            "coverage_status": coverage_status,
            "default_applied": bool(default_gap),
            "default_basis": default_basis,
            "unresolved_gaps": [],
            "score_ready": True,
        }
        records.append(record)

    records.sort(
        key=lambda row: (
            row["C_score_points"] is None,
            -float(row["C_score_points"] or 0),
            -float((row["C1"] or {}).get("raw_index") or 0),
            str(row["ruler_name"]),
        )
    )
    rank = 0
    for record in records:
        if record["score_applicable"]:
            rank += 1
            record["canonical_rank"] = rank
        else:
            record["canonical_rank"] = None
    payload: dict[str, Any] = {
        "schema_version": "first-item-c-registry-v3",
        "canonical_status": "CURRENT",
        "status": "CURRENT_NOT_FORMAL_DATABASE_WRITE",
        "formal_score_write": False,
        "database_write": False,
        "ranking_write": False,
        "method": {
            "net_control_policy": "project-level net control is consumed by A only; C window metrics are non-scoring audit context",
            "C1_result_values": C1_RESULT_VALUE,
            "C1_formula": "sum(non-overlapping accepted personal campaign result values); negative results subtract at the same tier value",
            "parent_cycle_deduplication": "per ruler + campaign_group_id + result_direction; parallel source windows consume one directional personal result",
            "C1_bands": {str(key): list(value) for key, value in c1_bands.items()},
            "C1_position_cutoffs": {
                str(key): list(value) for key, value in c1_position_cutoffs.items()
            },
            "C2_rate_table": {
                str(key): value for key, value in C2_RATE_TABLE.items()
            },
            "C2_peak_formula": "tier_score + 0.3*difficulty; the peak is bounded by the S+/D5 natural maximum of 7.5 and is not summed across battles",
            "C2_grade_policy": "hard-gate adjudication from peak, independent high-difficulty revalidation, sustained contexts, and defeat/failure caps; support results determine sufficiency but cannot overflow into a higher grade",
            "C2_negative_policy": "all in-window negative person results and primary command failures are consumed; same-group negative result and attributable failure are deduplicated",
            "default_policy": "evidence gap uses grade 0 LOW; documented no contribution uses grade 0 LOW",
        },
        "source_refs": {
            "roster": "config/所有君主.yml + config/first-item-a-strategic-efficiency-inputs.json#founder_roster",
            "scope_inputs": "config/first-item-a-strategic-efficiency-inputs.json",
            "battle_registry": "docs/公共成果/军事/01-战役登记.json",
            "talent_registry": "docs/公共成果/军事/02-武将人才等级.json",
            "window_config": "config/first-item-c-acquisition-windows.json",
            "territorial_control": "config/first-item-c-territorial-control-adjudications.json",
        },
        "source_registry_fingerprints": {
            "battle": battle_registry.get("semantic_fingerprint"),
            "talent": talent_registry.get("registry_fingerprint"),
        },
        "control_validation": control_summary,
        "window_metrics": sorted(
            window_metrics,
            key=lambda row: (
                -float(row["calibrated_weighted_net_control"]),
                str(row["window_ref"]),
            ),
        ),
        "record_count": len(records),
        "eligible_count": sum(bool(row["score_applicable"]) for row in records),
        "pending_count": sum(
            row["scope_status"] == "PENDING_FOUNDER_EVIDENCE" for row in records
        ),
        "excluded_count": sum(
            row["scope_status"] == "NOT_APPLICABLE_NON_FOUNDER" for row in records
        ),
        "score_ready_count": sum(
            bool(row["score_ready"])
            and row["scope_status"] != "PENDING_FOUNDER_EVIDENCE"
            for row in records
        ),
        "default_count": sum(bool(row["default_applied"]) for row in records),
        "coverage_status_counts": dict(
            sorted(Counter(str(row["coverage_status"]) for row in records).items())
        ),
        "records": records,
    }
    return payload


def render_first_item_c_registry_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 第一项C军事夺取能力结算",
        "",
        "> 当前值只用于规则校准；不写正式评分数据库，不形成正式排名。C1为50分，累计本人不重复的创业战役成果；C2为30分，评价本人前线指挥能力。净控制量只进入A，以下窗口表仅供边界审计。",
        "",
        f"- 对象：{payload['record_count']} 人",
        f"- 适用统一贡献者：{payload['eligible_count']} 人；待补：{payload['pending_count']} 人；不适用：{payload['excluded_count']} 人",
        f"- 完整结算：{payload['score_ready_count']} 人",
        "- canonical状态：CURRENT；本文件是C项当前唯一有效结果",
        f"- 证据缺口保守默认：{payload['default_count']} 人",
        "",
        "| C项序 | 对象 | 政权 | C1战役成果指数（非得分率） | C1实际得分 | C2能力峰值指数（非得分率） | 败绩/过失 | C2实际得分 | C结算 | 覆盖状态 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload.get("records") or ():
        if not row["score_applicable"]:
            continue
        c1, c2 = row["C1"], row["C2"]
        lines.append(
            f"| {row['canonical_rank']} | {row['ruler_name']} | {row.get('polity') or '—'} | "
            f"{c1['raw_index']:.2f} | {c1['points']:.1f}（C1-{c1['grade']}-{c1['position']}） | "
            f"{c2['peak_quality_index']:.2f} | "
            f"{c2['negative_context_count']}/{c2['command_failure_count']} | "
            f"{c2['points']:.1f}（C2-{c2['grade']}-{c2['position']}） | "
            f"{row['C_score_points']:.1f} | {row['coverage_status']} |"
        )
    lines.extend(["", "## 证据缺口默认", ""])
    defaults = [row for row in payload.get("records") or () if row["default_applied"]]
    lines.extend(
        (f"- {row['ruler_name']}：{row['default_basis']}" for row in defaults)
        if defaults
        else ["- 无。"]
    )
    lines.extend(["", "## 创业窗口净控制（仅审计，不进入C分）", ""])
    lines.append("| 窗口 | 原始净控制 | 加权净控制 | 范围系数 | 未绑定本人贡献区域 |")
    lines.append("|---|---:|---:|---:|---|")
    for row in payload.get("window_metrics") or ():
        missing = "、".join(row["unattributed_region_ids"]) or "—"
        lines.append(
            f"| {row['window_ref']} | {row['raw_net_control']:.2f} | "
            f"{row['calibrated_weighted_net_control']:.2f} | {row['scope_multiplier']:.2f} | {missing} |"
        )
    lines.extend(
        [
            "",
            "## C2败绩与指挥过失",
            "",
            "败绩表示本人前线负向结果；指挥过失只收主责且与同卡负向结果去重。二者均限定在创业窗口内。",
            "",
            "| 对象 | 败绩 | 指挥过失 | 档位封顶 | 档内降位 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    negative_rows = [
        row
        for row in payload.get("records") or ()
        if row["score_applicable"]
        and (
            row["C2"]["negative_context_count"]
            or row["C2"]["command_failure_count"]
        )
    ]
    lines.extend(
        (
            f"| {row['ruler_name']} | {row['C2']['negative_context_count']} | "
            f"{row['C2']['command_failure_count']} | C2-{row['C2']['grade_cap']} | "
            f"{row['C2']['negative_position_steps']} |"
            for row in negative_rows
        )
        if negative_rows
        else ["| — | 0 | 0 | C2-5 | 0 |"]
    )
    lines.extend(
        [
            "",
            "## 机器读取",
            "",
            "同目录JSON是唯一机器读取源；本文件仅为同值阅读视图。",
            "",
        ]
    )
    return "\n".join(lines)


def render_first_item_summary(
    *,
    a_payload: Mapping[str, Any],
    b_payload: Mapping[str, Any],
    c_payload: Mapping[str, Any],
) -> str:
    by_b = {str(row["ruler_name"]): row for row in b_payload.get("records") or ()}
    by_c = {str(row["ruler_name"]): row for row in c_payload.get("records") or ()}
    ac_rows = []
    totals = []
    for a_row in a_payload.get("records") or ():
        if not a_row.get("score_applicable"):
            continue
        name = str(a_row["ruler_name"])
        c_row = by_c[name]
        ac_rows.append(
            {
                "ruler_name": name,
                "polity": a_row.get("polity") or "—",
                "A": float(a_row["A_score_points"]),
                "C": float(c_row["C_score_points"]),
                "AC": round(
                    float(a_row["A_score_points"])
                    + float(c_row["C_score_points"]),
                    1,
                ),
            }
        )
        b_row = by_b.get(name)
        if not b_row or not b_row.get("score_applicable"):
            continue
        total = round(
            float(a_row["A_score_points"])
            + float(b_row["B_score_points"])
            + float(c_row["C_score_points"]),
            1,
        )
        totals.append(
            {
                "ruler_name": name,
                "polity": a_row.get("polity") or "—",
                "A": float(a_row["A_score_points"]),
                "B": float(b_row["B_score_points"]),
                "C": float(c_row["C_score_points"]),
                "total": total,
            }
        )
    totals.sort(key=lambda row: (-row["total"], row["ruler_name"]))
    ac_rows.sort(key=lambda row: (-row["AC"], row["ruler_name"]))
    lines = [
        "# 第一大项创业与政权取得能力结算总结分析",
        "",
        "## 一、当前结构与去重",
        "",
        f"秦至清名册共{a_payload['record_count']}人；{len(ac_rows)}名统一或建国主链实际贡献者进入A/B/C结算。",
        "",
        "- A1以个人起点30%和项目起点70%合成起点难度，再按对手压力70%、起点难度30%形成纯难度，以85%为历史极高难度锚；60分上限依次乘项目终点完成率、本人战略责任强度和校准难度，不设基础分。A2将战争新增控制按100%、既有控制恢复按50%形成计分控制量，以1000为固定前沿并开平方计算规模得分，客观结果最多36分，再直接加减具名正向决策和误判；",
        "- B结算非本人团队实际完成的开国成果与创业窗口贡献者质量；",
        "- C1为50分、C2为30分，分别结算本人不重复的创业战役成果与前线指挥能力；",
        "- 王朝级净控制量只在A2作为土地控制兑现量换分，A1不读取；它不能单独解释为国家机器创建或综合创业贡献。C中的窗口净控制表仅用于边界审计；全生涯军事人才档只作B/C越界复核，不直接换分。",
        "",
        "## 二、秦至清A/C结算表",
        "",
        "| A/C序 | 对象 | 政权 | A/100 | C/80 | A+C/180 |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for rank, row in enumerate(ac_rows, start=1):
        lines.append(
            f"| {rank} | {row['ruler_name']} | {row['polity']} | "
            f"{row['A']:.1f} | {row['C']:.1f} | {row['AC']:.1f} |"
        )
    qing_a = {
        str(row["ruler_name"]): row
        for row in a_payload.get("records") or ()
        if row.get("score_applicable")
        and str(row["ruler_name"]) in {"努尔哈赤", "皇太极", "多尔衮"}
    }
    if set(qing_a) == {"努尔哈赤", "皇太极", "多尔衮"}:
        lines.extend(
            [
                "",
                "### 清朝跨代结果解释",
                "",
                "多尔衮的"
                f"{qing_a['多尔衮']['A2']['created_net_control_value']:.0f}是入关后内地土地控制兑现，"
                f"努尔哈赤的{qing_a['努尔哈赤']['A2']['created_net_control_value']:.0f}和"
                f"皇太极的{qing_a['皇太极']['A2']['created_net_control_value']:.0f}主要受14宏区目录边界约束。"
                "三项控制不得跨代回拨，但也不得据此断言多尔衮是清朝综合创业贡献最大者："
                "努尔哈赤主要创建女真—后金军政机器，皇太极主要完成复合国家机器转型，"
                "多尔衮主要把既成机器转换为全国性土地控制。当前表稳定支持的是三种不同贡献，而不是单轴总贡献排序。",
            ]
        )
    leaders = "、".join(
        f"{row['ruler_name']}（{row['total']:.1f}）" for row in totals[:5]
    )
    lines.extend(
        [
            "",
            "## 三、秦至清完整第一项（含B）",
            "",
            f"当前A/B/C共同范围前五为{leaders}。",
            "",
            "B1取非本人团队最强的两个不重叠成果群并按绝对成果质量结算，不以团队份额反向扣减本人C；B2按并行执行、连续替补与异质整合三个组织轴结算。贡献者名单长度、全生涯名将档和成果证据条数均没有直接计分入口。",
            "",
            "## 四、当前状态",
            "",
            f"- A/B/C均覆盖秦至清{a_payload['record_count']}名册对象，适用统一主链贡献者{len(totals)}人；",
            f"- C创业主链证据缺口保守默认{c_payload['default_count']}人；",
            "- 当前结果不写正式数据库、不形成跨七大项总排名。",
            "",
            "机器明细分别见[A结算JSON](战略决策能力/01-第一项A战略决策能力结算.json)、[B结算JSON](政治整合能力/01-第一项B政治整合能力结算.json)和[C结算JSON](军事夺取能力/01-第一项C军事夺取能力结算.json)。",
            "",
        ]
    )
    return "\n".join(lines)


def write_first_item_c_registry(workspace_root: Path) -> dict[str, Path]:
    def load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    efficiency_inputs = load(
        workspace_root / "config/first-item-a-strategic-efficiency-inputs.json"
    )
    payload = build_first_item_c_registry(
        battle_registry=load_battle_registry(
            workspace_root / "docs/公共成果/军事/01-战役登记.json"
        ),
        talent_registry=load_talent_registry(
            workspace_root / "docs/公共成果/军事/02-武将人才等级.json"
        ),
        roster=load_qin_qing_first_item_roster(workspace_root, efficiency_inputs),
        scope_inputs=efficiency_inputs,
        window_config=load(
            workspace_root / "config/first-item-c-acquisition-windows.json"
        ),
        control_registry=load(
            workspace_root
            / "config/first-item-c-territorial-control-adjudications.json"
        ),
    )
    output_dir = (
        workspace_root
        / "docs/评分结算/第一项创业与政权取得能力/军事夺取能力"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "01-第一项C军事夺取能力结算.json"
    markdown_path = output_dir / "01-第一项C军事夺取能力结算.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(
        render_first_item_c_registry_markdown(payload), encoding="utf-8"
    )
    a_payload = load(
        workspace_root
        / "docs/评分结算/第一项创业与政权取得能力/战略决策能力/01-第一项A战略决策能力结算.json"
    )
    b_payload = load(
        workspace_root
        / "docs/评分结算/第一项创业与政权取得能力/政治整合能力/01-第一项B政治整合能力结算.json"
    )
    formal_payload = build_first_item_formal_settlement(
        a_payload=a_payload, b_payload=b_payload, c_payload=payload
    )
    settlement_dir = (
        workspace_root
        / "docs/评分结算/第一项创业与政权取得能力"
    )
    formal_json_path = settlement_dir / "01-第一项创业与政权取得能力正式结算.json"
    formal_markdown_path = settlement_dir / "01-第一项创业与政权取得能力正式结算.md"
    formal_json_path.write_text(
        json.dumps(formal_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    formal_markdown_path.write_text(
        render_first_item_formal_settlement_markdown(formal_payload),
        encoding="utf-8",
    )
    summary_path = settlement_dir / "02-第一项结算总结分析.md"
    summary_path.write_text(
        render_first_item_summary_analysis(
            formal_payload=formal_payload,
            a_payload=a_payload,
            b_payload=b_payload,
            c_payload=payload,
        ),
        encoding="utf-8",
    )
    return {
        "json": json_path,
        "markdown": markdown_path,
        "formal_json": formal_json_path,
        "formal_markdown": formal_markdown_path,
        "summary": summary_path,
    }
