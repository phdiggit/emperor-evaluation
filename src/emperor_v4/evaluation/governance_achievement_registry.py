from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from typing import Mapping, Sequence
from uuid import uuid4

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
        "formal_score_write_allowed": False,
    }


def _person_achievement_rows(
    person_ref: str,
    achievements: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = []
    for achievement in achievements:
        participant = next(
            (
                row
                for row in achievement["participants"]
                if row["person_ref"] == person_ref
            ),
            None,
        )
        if participant is None:
            continue
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
) -> dict[str, object]:
    profile_by_person = {
        str(row["person_ref"]): row for row in current_profiles
    }
    impacts = []
    for person_ref, profile in sorted(profile_by_person.items()):
        rows = _person_achievement_rows(person_ref, registry["achievements"])
        if not rows:
            continue
        assessment = assess_domain_historic_path("civil_governance", rows)
        rank = {value: index for index, value in enumerate(SCALES)}
        counted = [
            row
            for row in rows
            if row["responsibility_role"] in COUNTED_ROLES
            and row["result"] in {"implemented_positive", "completed_positive", "implemented_mixed"}
            and (row["result"] != "implemented_mixed" or row["positive_result_preserved"])
        ]
        national = [row for row in counted if rank[str(row["scale"])] >= rank["national"]]
        important = [row for row in counted if rank[str(row["scale"])] >= rank["important"]]
        top_fallback = bool(national) and (
            len(national) >= 2
            or any(row["stable_delivery"] for row in counted)
            or any(row["important_method_or_legacy"] for row in counted)
        )
        registry_floor = "top" if top_fallback else "important" if important else "usable"
        current_grade = str(profile["talent_grade"])
        if current_grade not in GRADE_ORDER:
            raise ValueError("current profile talent_grade 非法")
        effective = max((current_grade, registry_floor), key=GRADE_ORDER.index)
        impacts.append(
            {
                "person_ref": person_ref,
                "canonical_name": str(profile["canonical_name"]),
                "current_grade": current_grade,
                "registry_fact_floor": registry_floor,
                "effective_shadow_grade": effective,
                "grade_change_candidate": effective != current_grade,
                "achievement_refs": [str(row["achievement_ref"]) for row in rows],
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
        "person_profile_writes": 0,
        "score_writes": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="治理成果登记表校验与人才影响影子投影")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    validation = validate_governance_achievement_registry(
        registry, schema_path=args.schema
    )
    profiles = json.loads(args.profiles.read_text(encoding="utf-8"))
    projection = project_civil_talent_impact(registry, profiles)
    report = {"validation": validation, "projection": projection}
    _atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
