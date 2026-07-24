from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Mapping, Sequence
from uuid import uuid4

import yaml

from emperor_v4.adapters.structured_output_contract import validate_payload_against_schema
from emperor_v4.evaluation.talent_grade_domain_equivalence import (
    SCALES,
    assess_domain_historic_path,
)


GRADE_ORDER = ("ordinary", "usable", "important", "top", "historic")
COUNTED_ROLES = {"exclusive", "lead"}
REALIZED_IMPLEMENTATION = {"implemented", "operated", "completed", "mixed"}
NATIONAL_BASES = {
    "national_core_subsystem",
    "national_public_result",
    "era_order_reconstruction",
}
REGIONAL_BASES = {
    "regional_governance_result",
    *NATIONAL_BASES,
}


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def validate_governance_achievement_registry(
    payload: Mapping[str, object],
    *,
    schema_path: Path,
) -> dict[str, object]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validate_payload_against_schema(payload, schema)
    achievements = payload["achievements"]
    refs = [str(row["achievement_ref"]) for row in achievements]
    keys = [str(row["independent_governance_key"]) for row in achievements]
    if len(refs) != len(set(refs)):
        raise ValueError("governance achievement_ref 重复")
    if len(keys) != len(set(keys)):
        raise ValueError("独立治理成果必须先合并，independent_governance_key 不得重复")
    participant_count = 0
    for achievement in achievements:
        scale = achievement["scale"]
        level = str(scale["level"])
        basis = str(scale["consequence_basis"])
        if level in {"national", "era_shaping"} and basis not in NATIONAL_BASES:
            raise ValueError("国家级治理成果必须由全国核心子系统或全国公共结果支持")
        if level == "regional" and basis not in REGIONAL_BASES:
            raise ValueError("区域级治理成果必须由主要区域治理结果支持")
        if achievement["implementation_status"] not in REALIZED_IMPLEMENTATION:
            if achievement["result_direction"] in {"positive", "mixed"}:
                raise ValueError("未落实治理事项不得登记正向实现结果")
        if achievement["result_direction"] == "positive" and not achievement[
            "positive_result_preserved"
        ]:
            raise ValueError("正向治理结果必须保留 positive_result_preserved")
        people = [str(row["person_ref"]) for row in achievement["participants"]]
        if len(people) != len(set(people)):
            raise ValueError("同一治理成果人物归责不得重复")
        rulers = [str(row["ruler_ref"]) for row in achievement["ruler_links"]]
        if len(rulers) != len(set(rulers)):
            raise ValueError("同一治理成果君主归责不得重复")
        if not people and not rulers:
            raise ValueError("治理成果必须至少有一名人物参与者或一条君主归责")
        participant_count += len(people)
        for key in ("neutral_fact_refs", "source_refs", "reuse_targets"):
            values = achievement[key]
            if len(values) != len(set(values)):
                raise ValueError(f"治理成果 {key} 不得重复")
    return {
        "schema_version": "governance-achievement-registry-validation-v1",
        "status": "passed",
        "achievement_count": len(achievements),
        "participant_count": participant_count,
        "scale_counts": dict(
            sorted(Counter(str(row["scale"]["level"]) for row in achievements).items())
        ),
    }


def _person_achievement_rows(
    person_ref: str,
    canonical_name: str,
    achievements: Sequence[Mapping[str, object]],
    *,
    ruler_name: str | None = None,
) -> list[dict[str, object]]:
    rows = []
    for achievement in achievements:
        if ruler_name is not None and ruler_name not in {
            str(row["ruler_name"]) for row in achievement["ruler_links"]
        }:
            continue
        matches = [
            row
            for row in achievement["participants"]
            if row["person_ref"] == person_ref
            or str(row["canonical_name"]) == canonical_name
        ]
        if len(matches) > 1:
            raise ValueError(f"治理成果人物身份匹配歧义: {canonical_name}")
        if not matches:
            continue
        participant = matches[0]
        status = str(achievement["implementation_status"])
        direction = str(achievement["result_direction"])
        result = "unclear"
        if status in REALIZED_IMPLEMENTATION and direction == "positive":
            result = "completed_positive" if status == "completed" else "implemented_positive"
        elif status in REALIZED_IMPLEMENTATION and direction == "mixed":
            result = "implemented_mixed"
        rows.append(
            {
                "achievement_ref": achievement["achievement_ref"],
                "registry_person_ref": participant["person_ref"],
                "independent_key": achievement["independent_governance_key"],
                "scale": achievement["scale"]["level"],
                "responsibility_role": participant["responsibility_role"],
                "result": result,
                "positive_result_preserved": achievement["positive_result_preserved"],
                "foundational": achievement["foundational"],
                "durable_cross_stage": achievement["durable_cross_stage"],
                "stable_delivery": achievement["stable_delivery"],
                "important_method_or_legacy": achievement["important_method_or_legacy"],
            }
        )
    return rows


def project_civil_talent_impact(
    registry: Mapping[str, object],
    current_profiles: Sequence[Mapping[str, object]],
    *,
    ruler_name: str | None = None,
) -> dict[str, object]:
    profile_by_person = {
        str(row["person_ref"]): row for row in current_profiles
    }
    impacts = []
    for person_ref, profile in sorted(profile_by_person.items()):
        canonical_name = str(profile.get("canonical_name") or "")
        if not canonical_name:
            raise ValueError("current profile 缺少 canonical_name")
        rows = _person_achievement_rows(
            person_ref,
            canonical_name,
            registry["achievements"],
            ruler_name=ruler_name,
        )
        if not rows:
            continue
        registry_person_refs = {str(row["registry_person_ref"]) for row in rows}
        if len(registry_person_refs) > 1:
            raise ValueError(f"治理成果规范名映射到多个人物 ID: {canonical_name}")
        assessment = assess_domain_historic_path("civil_governance", rows)
        rank = {value: index for index, value in enumerate(SCALES)}
        counted = [
            row
            for row in rows
            if row["responsibility_role"] in COUNTED_ROLES
            and row["result"] in {"implemented_positive", "completed_positive"}
        ]
        national = [row for row in counted if rank[str(row["scale"])] >= rank["national"]]
        important = [row for row in counted if rank[str(row["scale"])] >= rank["important"]]
        top_fallback = bool(national) and (
            len(national) >= 2
            or any(row["stable_delivery"] for row in counted)
            or any(row["important_method_or_legacy"] for row in counted)
        )
        registry_floor = "top" if top_fallback else "important" if important else "usable"
        current_grade = str(profile.get("talent_grade") or "")
        if current_grade not in GRADE_ORDER:
            raise ValueError("current profile talent_grade 非法")
        effective = max((current_grade, registry_floor), key=GRADE_ORDER.index)
        impacts.append(
            {
                "person_ref": person_ref,
                "canonical_name": canonical_name,
                "registry_fact_floor": registry_floor,
                "talent_grade": effective,
                "grade_change_candidate": effective != current_grade,
                "achievement_refs": [str(row["achievement_ref"]) for row in rows],
                "registry_person_refs": sorted(
                    registry_person_refs
                ),
                "historic_fact_path_status": assessment["historic_fact_path_status"],
                "historic_matched_path": assessment["matched_path"],
                "authority_calibration_required": True,
            }
        )
    return {
        "schema_version": "governance-achievement-talent-impact-v1",
        "status": "accepted_shadow",
        "impact_count": len(impacts),
        "grade_change_candidate_count": sum(
            bool(row["grade_change_candidate"]) for row in impacts
        ),
        "impacts": impacts,
    }


def project_i5b_team_building_impact(
    registry: Mapping[str, object],
    *,
    team_report: Mapping[str, object],
    material_budget_report: Mapping[str, object],
    scoring_policy: Mapping[str, object],
) -> dict[str, object]:
    """Project governance facts into an I5B roster review without choosing a member."""
    ruler = str(team_report.get("ruler") or "")
    if not ruler:
        raise ValueError("team report 缺少 ruler")
    profiles = [
        {
            "person_ref": row["person_ref"],
            "canonical_name": row["person"],
            "talent_grade": row["effective_talent_grade"],
        }
        for row in team_report.get("members") or ()
    ]
    talent_impact = project_civil_talent_impact(
        registry,
        profiles,
        ruler_name=ruler,
    )
    budget_rule = next(
        (
            row
            for row in material_budget_report.get("rules") or ()
            if row.get("rule_code") == "team_building"
        ),
        None,
    )
    if budget_rule is None:
        raise ValueError("material budget report 缺少 team_building")
    selected = {
        str(row["person"]): row for row in budget_rule.get("positive_members") or ()
    }
    if not selected:
        raise ValueError("team_building 正池为空")
    talent_values = scoring_policy["rules"]["team_building"]["talent_quality_factor"]
    boundary = min(Decimal(str(row["talent_value"])) for row in selected.values())
    multiplier = Decimal(str(budget_rule["functional_complementarity_factor"])) * Decimal(
        str(budget_rule["long_term_stability_factor"])
    )
    affected = []
    for impact in talent_impact["impacts"]:
        if not impact["grade_change_candidate"]:
            continue
        name = str(impact["canonical_name"])
        projected_value = Decimal(
            str(talent_values[str(impact["talent_grade"])])
        )
        if name in selected:
            disposition = "selected_member_grade_review_required"
            pool_delta = projected_value - Decimal(str(selected[name]["talent_value"]))
        elif projected_value > boundary:
            disposition = "positive_pool_reselection_required"
            pool_delta = projected_value - boundary
        elif projected_value == boundary:
            disposition = "positive_pool_boundary_tie_review_required"
            pool_delta = Decimal("0")
        else:
            disposition = "supporting_member_no_pool_change"
            pool_delta = Decimal("0")
        affected.append(
            {
                **impact,
                "positive_pool_member": name in selected,
                "i5b_disposition": disposition,
                "counterfactual_positive_pool_delta": str(pool_delta),
                "counterfactual_rule_raw_net_delta": str(pool_delta * multiplier),
            }
        )
    return {
        "schema_version": "governance-achievement-i5b-team-impact-v1",
        "status": "accepted_shadow",
        "ruler": ruler,
        "positive_member_count": len(selected),
        "positive_pool_boundary_value": str(boundary),
        "factor_multiplier": str(multiplier),
        "affected_member_count": len(affected),
        "reselection_required": any(
            row["i5b_disposition"] == "positive_pool_reselection_required"
            for row in affected
        ),
        "affected_members": affected,
        "automatic_roster_mutation_allowed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="治理成果登记表校验与人才影响影子投影")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--team-report", type=Path)
    parser.add_argument("--material-budget-report", type=Path)
    parser.add_argument("--scoring-policy", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registry_payload = json.loads(args.registry.read_text(encoding="utf-8"))
    registry = (
        registry_payload.get("registry", registry_payload)
        if isinstance(registry_payload, Mapping)
        else registry_payload
    )
    validation = validate_governance_achievement_registry(
        registry, schema_path=args.schema
    )
    profiles_payload = json.loads(args.profiles.read_text(encoding="utf-8"))
    if isinstance(profiles_payload, Mapping):
        profiles = profiles_payload.get("profiles")
        if profiles is None:
            raise ValueError("profiles 输入对象必须包含 profiles")
    else:
        profiles = profiles_payload
    projection = project_civil_talent_impact(registry, profiles)
    report = {"validation": validation, "projection": projection}
    team_inputs = (
        args.team_report,
        args.material_budget_report,
        args.scoring_policy,
    )
    if any(team_inputs) and not all(team_inputs):
        raise ValueError("I5B 影响投影必须同时提供 team report、material budget report 和 policy")
    if all(team_inputs):
        report["i5b_team_building_impact"] = project_i5b_team_building_impact(
            registry,
            team_report=json.loads(args.team_report.read_text(encoding="utf-8")),
            material_budget_report=json.loads(
                args.material_budget_report.read_text(encoding="utf-8")
            ),
            scoring_policy=yaml.safe_load(
                args.scoring_policy.read_text(encoding="utf-8")
            ),
        )
    _atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
