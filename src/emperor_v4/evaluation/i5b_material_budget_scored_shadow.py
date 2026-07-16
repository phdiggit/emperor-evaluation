from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[3]
REPORT_SCHEMA_VERSION = "i5b-material-budget-shadow-report-v1"
Q = Decimal("0.000001")
RULE_ORDER = (
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
)
RULE_LABELS = {
    "talent_discovery": "发现人才",
    "appointment_delegation": "任用授权",
    "team_building": "团队建设",
    "tolerate_talent": "容人保全",
    "anti_nepotism": "避免任人唯亲",
}
FACTOR_NAMES = {
    "talent_discovery": {
        "positive": (
            "direction_sign",
            "discovery_level",
            "talent_quality_factor",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
        "negative": (
            "direction_sign",
            "discovery_level",
            "talent_quality_factor",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
    },
    "tolerate_talent": {
        "positive": (
            "feedback_entry",
            "expression_safety",
            "protection_repair",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
        "negative": (
            "handling_severity",
            "target_fault_factor",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
    },
    "anti_nepotism": {
        "positive": (
            "selection_openness",
            "institutionalization",
            "office_weight",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
        "negative": (
            "favoritism_intensity",
            "office_weight",
            "displacement_harm",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
    },
}
APPOINTMENT_FACTORS = (
    "appointment_importance",
    "appointment_effect",
    "continuity_factor",
    "attribution_factor",
    "source_factor",
    "context_factor",
)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _rounded(value: Decimal) -> str:
    return format(value.quantize(Q, rounding=ROUND_HALF_UP), "f")


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML 顶层必须是对象: {path}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return payload


def _factor_product(
    values: Mapping[str, Any], names: Sequence[str], material_id: str
) -> tuple[Decimal, dict[str, str]]:
    missing = [name for name in names if name not in values]
    if missing:
        raise ValueError(f"{material_id} 缺少因子: {missing}")
    product = Decimal("1")
    rendered: dict[str, str] = {}
    for name in names:
        value = abs(_decimal(values[name]))
        product *= value
        rendered[name] = _rounded(value)
    return min(product, Decimal("4")), rendered


def _projected_materials(
    source: Mapping[str, Any], ruler: str, rule_code: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for material in source.get("materials") or []:
        if material.get("ruler") != ruler:
            continue
        material_id = str(material["unit_ref"])
        side = str(material["side"])
        projection = material.get("numeric_projection") or {}
        magnitude, factor_values = _factor_product(
            projection.get("deterministic_dimension_values") or {},
            FACTOR_NAMES[rule_code][side],
            material_id,
        )
        row = {
                "material_id": material_id,
                "subject": str(material.get("subject") or material.get("object_ref") or "—"),
                "object_ref": str(material.get("object_ref") or material.get("subject") or material_id),
                "side": side,
                "material_magnitude": magnitude,
                "factor_values": factor_values,
                "factor_option_codes": dict(projection.get("factor_option_codes") or {}),
                "fact": str(material.get("projection_basis") or ""),
                "rule_evidence_unit_ref": str(
                    material.get("rule_evidence_unit_ref") or material_id
                ),
                "source_refs": list(material.get("source_refs") or []),
            }
        if projection.get("v4_factor_projection"):
            row["v4_factor_projection"] = dict(projection["v4_factor_projection"])
        if material.get("talent_quality_basis"):
            row["talent_quality_basis"] = dict(material["talent_quality_basis"])
        rows.append(row)
    return rows


def _appointment_materials(
    source: Mapping[str, Any], ruler: str
) -> list[dict[str, Any]]:
    episode_facts: dict[str, list[str]] = {}
    for episode in (source.get("assertion_episode_reu_trace") or {}).get("episodes") or []:
        unit_ref = str((episode.get("lineage") or {}).get("unit_ref") or "")
        parts = [str(episode.get("action") or "").strip()]
        parts.extend(str(value).strip() for value in episode.get("outcome") or [])
        fact = "；".join(part for part in parts if part)
        if unit_ref and fact and fact not in episode_facts.setdefault(unit_ref, []):
            episode_facts[unit_ref].append(fact)

    rows: list[dict[str, Any]] = []
    for judgment in source.get("judgments") or []:
        if judgment.get("ruler") != ruler:
            continue
        unit_ref = str(judgment["rule_evidence_unit_ref"])
        for material in judgment.get("factor_materials") or []:
            material_id = str(material["material_code"])
            choices = material.get("factor_choices") or {}
            values = {
                name: (choices.get(name) or {}).get("deterministic_value")
                for name in APPOINTMENT_FACTORS
            }
            magnitude, factor_values = _factor_product(
                values, APPOINTMENT_FACTORS, material_id
            )
            rows.append(
                {
                    "material_id": material_id,
                    "subject": str(judgment.get("person") or "—"),
                    "object_ref": str(judgment.get("person_ref") or judgment.get("person") or unit_ref),
                    "side": str(material["side"]),
                    "material_magnitude": magnitude,
                    "factor_values": factor_values,
                    "factor_option_codes": {
                        name: str(choices[name]["option_code"])
                        for name in APPOINTMENT_FACTORS
                    },
                    "fact": "；".join(episode_facts.get(unit_ref, []))
                    or str(judgment.get("review_basis") or ""),
                    "rule_evidence_unit_ref": unit_ref,
                    "source_refs": sorted(
                        {
                            str(ref)
                            for name in APPOINTMENT_FACTORS
                            for ref in choices[name].get("assertion_refs") or []
                        }
                    ),
                }
            )
    return rows


def _appointment_responsibility_materials(
    source: Mapping[str, Any], ruler: str
) -> list[dict[str, Any]]:
    if source.get("schema_version") != "i5b-appointment-responsibility-projection-v1":
        raise ValueError("任用责任链补充源 schema_version 不匹配")
    if source.get("ruler") != ruler:
        raise ValueError("任用责任链补充源 ruler 不匹配")
    rows: list[dict[str, Any]] = []
    for material in source.get("materials") or ():
        values = {
            factor: _decimal(material["factor_values"][factor])
            for factor in APPOINTMENT_FACTORS
        }
        rows.append(
            {
                "material_id": str(material["material_id"]),
                "side": str(material["side"]),
                "subject": str(material["subject"]),
                "object_ref": str(material["object_ref"]),
                "rule_evidence_unit_ref": str(material["rule_evidence_unit_ref"]),
                "factor_values": values,
                "factor_option_codes": dict(material["factor_option_codes"]),
                "material_magnitude": _decimal(material["material_magnitude"]),
                "fact": str(material["fact"]),
                "source_refs": list(material.get("source_refs") or ()),
            }
        )
    return rows


def _direct_materials(
    *, rule_code: str, rule_manifest: Mapping[str, Any]
) -> list[dict[str, Any]]:
    names_by_side = (
        {"positive": APPOINTMENT_FACTORS, "negative": APPOINTMENT_FACTORS}
        if rule_code == "appointment_delegation"
        else FACTOR_NAMES[rule_code]
    )
    rows = []
    for material in rule_manifest.get("direct_materials") or ():
        material_id = str(material["material_id"])
        side = str(material["side"])
        if side not in names_by_side:
            raise ValueError(f"{material_id} direct material 方向非法")
        magnitude, rendered_values = _factor_product(
            material.get("factor_values") or {}, names_by_side[side], material_id
        )
        row = {
                "material_id": material_id,
                "subject": str(material["subject"]),
                "object_ref": str(material.get("object_ref") or material["subject"]),
                "side": side,
                "material_magnitude": magnitude,
                "factor_values": rendered_values,
                "factor_option_codes": dict(material.get("factor_option_codes") or {}),
                "fact": str(material["fact"]),
                "rule_evidence_unit_ref": str(
                    material.get("rule_evidence_unit_ref") or material_id
                ),
                "source_refs": list(material.get("source_refs") or ()),
            }
        if material.get("talent_quality_basis"):
            row["talent_quality_basis"] = dict(material["talent_quality_basis"])
        if material.get("v4_factor_projection"):
            row["v4_factor_projection"] = dict(material["v4_factor_projection"])
        rows.append(row)
    return rows


def _apply_overrides(
    materials: list[dict[str, Any]], overrides: Mapping[str, Any]
) -> None:
    by_id = {row["material_id"]: row for row in materials}
    unknown = sorted(set(overrides) - set(by_id))
    if unknown:
        raise ValueError(f"factor override 指向未知材料: {unknown}")
    for material_id, factor_overrides in overrides.items():
        material = by_id[material_id]
        reasons: list[str] = []
        for factor_name, override in factor_overrides.items():
            if factor_name not in material["factor_values"]:
                raise ValueError(f"{material_id} 无法覆盖因子 {factor_name}")
            material["factor_values"][factor_name] = _rounded(
                _decimal(override["value"])
            )
            material["factor_option_codes"][factor_name] = str(
                override["option_code"]
            )
            reasons.append(str(override["reason"]))
        magnitude = Decimal("1")
        for value in material["factor_values"].values():
            magnitude *= _decimal(value)
        material["material_magnitude"] = min(magnitude, Decimal("4"))
        material["override_reasons"] = reasons


def _material_view(
    material: Mapping[str, Any], decision: Mapping[str, Any]
) -> dict[str, Any]:
    row = {
        "material_id": material["material_id"],
        "side": material["side"],
        "subject": material["subject"],
        "object_ref": material["object_ref"],
        "rule_evidence_unit_ref": material["rule_evidence_unit_ref"],
        "independence_key": str(decision["independence_key"]),
        "judge_reason": str(decision["judge_reason"]),
        "material_magnitude": _rounded(material["material_magnitude"]),
        "factor_values": material["factor_values"],
        "factor_option_codes": material["factor_option_codes"],
        "override_reasons": list(material.get("override_reasons") or []),
        "fact": str(decision.get("fact_override") or material["fact"]),
        "source_refs": material["source_refs"],
    }
    if material.get("v4_factor_projection"):
        row["v4_factor_projection"] = material["v4_factor_projection"]
    if material.get("talent_quality_basis"):
        row["talent_quality_basis"] = material["talent_quality_basis"]
    return row


def _object_density(selected: Sequence[Mapping[str, Any]]) -> Decimal:
    by_object: dict[str, list[Decimal]] = {}
    for material in selected:
        by_object.setdefault(str(material["object_ref"]), []).append(
            material["material_magnitude"]
        )
    total = Decimal("0")
    for values in by_object.values():
        ordered = sorted(values, reverse=True)
        strongest = ordered[0]
        object_value = min(
            strongest + Decimal("0.35") * sum(ordered[1:], Decimal("0")),
            strongest * Decimal("1.5"),
            Decimal("4"),
        )
        total += object_value
    return total


def _appointment_density(selected: Sequence[Mapping[str, Any]], side: str) -> Decimal:
    object_values: dict[str, Decimal] = {}
    for material in selected:
        object_ref = str(material["object_ref"])
        object_values[object_ref] = object_values.get(object_ref, Decimal("0")) + material[
            "material_magnitude"
        ]
    scale = Decimal("1.5") if side == "positive" else Decimal("1")
    total = Decimal("0")
    ordered = sorted(object_values.values(), reverse=True)
    rank = 0
    previous: Decimal | None = None
    for index, value in enumerate(ordered, start=1):
        if previous is None or value != previous:
            rank = index
        total += value / _decimal(rank).sqrt()
        previous = value
    return scale * total


def _build_material_rule(
    *,
    rule_code: str,
    rule_manifest: Mapping[str, Any],
    policy: Mapping[str, Any],
    ruler: str,
) -> dict[str, Any]:
    source_path = _resolve(str(rule_manifest["source"]))
    source = _load_json(source_path)
    supplemental_paths = [
        _resolve(str(value)) for value in rule_manifest.get("supplemental_sources") or ()
    ]
    supplemental_sources = [_load_json(path) for path in supplemental_paths]
    if rule_code == "appointment_delegation":
        materials = _appointment_materials(source, ruler)
        for supplemental in supplemental_sources:
            materials.extend(_appointment_responsibility_materials(supplemental, ruler))
    else:
        if supplemental_sources:
            raise ValueError(f"{rule_code} 不支持 supplemental_sources")
        materials = _projected_materials(source, ruler, rule_code)
    materials.extend(
        _direct_materials(rule_code=rule_code, rule_manifest=rule_manifest)
    )
    _apply_overrides(materials, rule_manifest.get("factor_overrides") or {})
    by_id = {row["material_id"]: row for row in materials}
    if len(by_id) != len(materials):
        raise ValueError(f"{rule_code} material_id 重复")

    budget = policy["settlement_budget"]["event_rules"][rule_code]
    selected_by_side: dict[str, list[dict[str, Any]]] = {}
    selected_views: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    eligible_ids: set[str] = set()
    for side in ("positive", "negative"):
        decisions = list((rule_manifest.get("eligible") or {}).get(side) or [])
        keys = [str(row["independence_key"]) for row in decisions]
        if len(keys) != len(set(keys)):
            raise ValueError(f"{rule_code}.{side} independence_key 重复")
        candidates: list[tuple[dict[str, Any], Mapping[str, Any]]] = []
        for decision in decisions:
            material_id = str(decision["material_id"])
            if material_id not in by_id:
                raise ValueError(f"{rule_code} 未知合格材料: {material_id}")
            material = by_id[material_id]
            if material["side"] != side:
                raise ValueError(f"{material_id} 方向与结算池不一致")
            eligible_ids.add(material_id)
            candidates.append((material, decision))
        candidates.sort(
            key=lambda row: (-row[0]["material_magnitude"], row[0]["material_id"])
        )
        selected_candidates = candidates[: int(budget[side])]
        selected = [row[0] for row in selected_candidates]
        for material, decision in selected_candidates:
            material_id = str(material["material_id"])
            selected_ids.add(material_id)
            view = _material_view(material, decision)
            view["selection_basis"] = "eligibility_gate_then_strongest_n"
            selected_views.append(view)
        selected_by_side[side] = selected

    exclusion_decisions = {
        str(row["material_id"]): str(row["judge_reason"])
        for row in rule_manifest.get("excluded") or []
    }
    undisposed = sorted(set(by_id) - eligible_ids - set(exclusion_decisions))
    unknown_exclusions = sorted(set(exclusion_decisions) - set(by_id))
    overlap = sorted(eligible_ids & set(exclusion_decisions))
    if undisposed or unknown_exclusions or overlap:
        raise ValueError(
            f"{rule_code} 候选处置不闭合: undisposed={undisposed}, "
            f"unknown={unknown_exclusions}, overlap={overlap}"
        )

    supporting_rows = []
    for material_id in sorted(eligible_ids - selected_ids):
        material = by_id[material_id]
        side = str(material["side"])
        boundary = min(
            (
                row["material_magnitude"]
                for row in selected_by_side[side]
            ),
            default=Decimal("0"),
        )
        supporting_rows.append(
            {
                "material_id": material_id,
                "subject": material["subject"],
                "rule_evidence_unit_ref": material["rule_evidence_unit_ref"],
                "material_magnitude": _rounded(material["material_magnitude"]),
                "factor_values": {
                    key: _rounded(_decimal(value))
                    for key, value in (material.get("factor_values") or {}).items()
                },
                "factor_option_codes": dict(
                    material.get("factor_option_codes") or {}
                ),
                "fact": str(material.get("fact") or ""),
                "judge_reason": (
                    "已通过适用性、归责、独立性和去重 Gate；"
                    f"材料分低于当前{'正向' if side == 'positive' else '负向'}"
                    f"预算边界 {_rounded(boundary)}，本版不计分。"
                ),
                "selection_status": "eligible_below_budget_boundary",
            }
        )
    supporting_rows.extend(
        {
            "material_id": material_id,
            "subject": by_id[material_id]["subject"],
            "rule_evidence_unit_ref": by_id[material_id]["rule_evidence_unit_ref"],
            "material_magnitude": _rounded(by_id[material_id]["material_magnitude"]),
            "factor_values": {
                key: _rounded(_decimal(value))
                for key, value in (
                    by_id[material_id].get("factor_values") or {}
                ).items()
            },
            "factor_option_codes": dict(
                by_id[material_id].get("factor_option_codes") or {}
            ),
            "fact": str(by_id[material_id].get("fact") or ""),
            "judge_reason": reason,
            "selection_status": "excluded_by_eligibility_gate",
        }
        for material_id, reason in sorted(exclusion_decisions.items())
    )
    for row in supporting_rows:
        material = by_id.get(str(row["material_id"]))
        if material and material.get("talent_quality_basis"):
            row["talent_quality_basis"] = material["talent_quality_basis"]
    for supplemental in supplemental_sources:
        supporting_rows.extend(
            {
                "material_id": str(row["material_id"]),
                "subject": str(row["subject"]),
                "rule_evidence_unit_ref": str(row["rule_evidence_unit_ref"]),
                "material_magnitude": None,
                "judge_reason": str(row["judge_reason"]),
                "selection_status": "insufficient_contract_evidence",
            }
            for row in supplemental.get("insufficient_units") or ()
        )

    if rule_code == "appointment_delegation":
        positive = _appointment_density(selected_by_side["positive"], "positive")
        negative = _appointment_density(selected_by_side["negative"], "negative")
    else:
        positive = _object_density(selected_by_side["positive"])
        negative = _object_density(selected_by_side["negative"])
    result = {
        "rule_code": rule_code,
        "rule_label": RULE_LABELS[rule_code],
        "source_ref": str(rule_manifest["source"]),
        "source_sha256": _sha256(source_path.read_bytes()),
        "supplemental_source_refs": [
            str(value) for value in rule_manifest.get("supplemental_sources") or ()
        ],
        "supplemental_source_sha256s": [
            _sha256(path.read_bytes()) for path in supplemental_paths
        ],
        "source_candidate_count": len(materials),
        "eligible_candidate_count": len(eligible_ids),
        "positive_budget": int(budget["positive"]),
        "negative_budget": int(budget["negative"]),
        "settled_materials": selected_views,
        "supporting_only_materials": supporting_rows,
        "positive_signal": _rounded(positive),
        "negative_signal": _rounded(negative),
        "rule_raw_net": _rounded(positive - negative),
        "candidate_disposition_complete": True,
    }
    candidate_inventory_ref = rule_manifest.get("candidate_inventory_ref")
    if rule_code == "talent_discovery" and candidate_inventory_ref:
        result["candidate_boundary_audit"] = _talent_candidate_boundary_audit(
            inventory_path=_resolve(str(candidate_inventory_ref)),
            positive_boundary=min(
                (
                    row["material_magnitude"]
                    for row in selected_by_side["positive"]
                ),
                default=Decimal("0"),
            ),
        )
    return result


def _team_profile_members(
    source: Mapping[str, Any],
    team_policy: Mapping[str, Any],
    current_profiles: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    rows = list(source.get("members") or ())
    if source.get("schema_version") != "i5b-team-member-profile-pool-v1":
        members = {str(row["person"]): dict(row) for row in rows}
        if any(not row.get("profile_ref") for row in members.values()):
            raise ValueError("team source member 缺少版本化人物画像")
        talent_values = team_policy["talent_quality_factor"]
        severity_values = team_policy["negative_talent_severity_value"]
        for row in members.values():
            if current_profiles is not None:
                person_ref = str(row["person_ref"])
                current = current_profiles.get(person_ref)
                if current is None:
                    raise ValueError(
                        f"{row['person']} 不在唯一人物画像表 person_profiles"
                    )
                if current.get("review_status") != "human_frozen":
                    raise ValueError(f"{row['person']} 唯一人物画像尚未人工冻结")
                row["effective_talent_grade"] = str(current["talent_grade"])
                row["talent_grade_basis"] = str(
                    current.get("talent_grade_basis") or ""
                )
                row["profile_ref"] = str(current["profile_ref"])
                row["profile_snapshot_version"] = str(current["profile_version"])
                if current.get("negative_risk_status") == "established":
                    row["negative_talent_class"] = current.get(
                        "negative_talent_class"
                    )
                    row["negative_talent_severity"] = current.get(
                        "negative_talent_severity"
                    )
                    if (
                        not row["negative_talent_class"]
                        or row["negative_talent_severity"] not in severity_values
                    ):
                        raise ValueError(
                            f"{row['person']} 唯一人物画像政治风险档位不完整"
                        )
                else:
                    row["negative_talent_class"] = None
                    row["negative_talent_severity"] = None
            grade = str(row["effective_talent_grade"])
            row["talent_value"] = str(talent_values[grade])
            severity = row.get("negative_talent_severity")
            row["negative_value"] = (
                "0" if severity is None else str(severity_values[str(severity)])
            )
        return members, {
            name
            for name, row in members.items()
            if row.get("negative_talent_severity") is not None
        }

    if source.get("frozen_member_set_complete") is not True:
        raise ValueError("team profile pool 必须冻结完整成员集合")
    talent_values = team_policy["talent_quality_factor"]
    severity_values = team_policy["negative_talent_severity_value"]
    members: dict[str, dict[str, Any]] = {}
    exposed: set[str] = set()
    for profile in rows:
        name = str(profile["person"])
        if name in members:
            raise ValueError("team profile pool 人物重复")
        if (
            profile.get("review_status") != "human_frozen"
            or not profile.get("profile_ref")
            or not profile.get("profile_snapshot_version")
        ):
            raise ValueError(f"{name} 缺少人工冻结版本化人物画像")
        person_ref = str(profile["person_ref"])
        negative = profile.get("negative_profile") or {}
        if negative.get("review_completed") is not True:
            raise ValueError(f"{name} 政治风险画像尚未审完")
        finding = str(negative.get("finding_status") or "")
        risk_class = negative.get("class")
        risk_severity = negative.get("severity")
        if finding == "established":
            if not risk_class or risk_severity not in severity_values:
                raise ValueError(f"{name} 政治风险画像不完整")
        elif finding == "reviewed_no_finding":
            if risk_class is not None or risk_severity is not None:
                raise ValueError(f"{name} 无负类画像不得携带风险档位")
        else:
            raise ValueError(f"{name} 政治风险画像状态不可计分: {finding}")
        grade = str(profile["effective_talent_grade"])
        profile_ref = str(profile["profile_ref"])
        profile_version = str(profile["profile_snapshot_version"])
        grade_basis = str(profile.get("talent_grade_basis") or "")
        if current_profiles is not None:
            current = current_profiles.get(person_ref)
            if current is None:
                raise ValueError(f"{name} 不在唯一人物画像表 person_profiles")
            if current.get("review_status") != "human_frozen":
                raise ValueError(f"{name} 唯一人物画像尚未人工冻结")
            current_finding = str(current.get("negative_risk_status") or "")
            if current_finding not in {"established", "no_established_class"}:
                raise ValueError(f"{name} 唯一人物画像政治风险状态非法")
            current_class = current.get("negative_talent_class")
            current_severity = current.get("negative_talent_severity")
            if current_finding == "established" and (
                not current_class or current_severity not in severity_values
            ):
                raise ValueError(f"{name} 唯一人物画像政治风险档位不完整")
            grade = str(current["talent_grade"])
            grade_basis = str(current.get("talent_grade_basis") or "")
            profile_ref = str(current["profile_ref"])
            profile_version = str(current["profile_version"])
            finding = (
                "established"
                if current_finding == "established"
                else "reviewed_no_finding"
            )
            risk_class = current_class
            risk_severity = current_severity

        exposure = profile.get("window_exposure") or {}
        exposure_status = str(exposure.get("status") or "")
        if exposure_status not in {"exposed", "not_observed"}:
            raise ValueError(f"{name} 缺少当前皇帝窗口政治风险暴露判断")
        if exposure_status == "exposed":
            if finding == "established" and not list(exposure.get("source_refs") or ()):
                raise ValueError(f"{name} 窗口风险暴露缺少画像负类或史源")
            if finding == "established":
                exposed.add(name)
            elif current_profiles is None:
                raise ValueError(f"{name} 窗口风险暴露缺少画像负类或史源")
        if grade not in talent_values:
            raise ValueError(f"{name} 人才档位不在当前画像映射")
        risk_is_exposed = exposure_status == "exposed" and finding == "established"
        members[name] = {
            "person": name,
            "person_ref": person_ref,
            "profile_ref": profile_ref,
            "profile_snapshot_version": profile_version,
            "effective_talent_grade": grade,
            "talent_value": str(talent_values[grade]),
            "talent_grade_basis": grade_basis,
            "role_families": list(profile.get("role_families") or ()),
            "supporting_unit_refs": list(profile.get("supporting_unit_refs") or ()),
            "negative_talent_class": risk_class if risk_is_exposed else None,
            "negative_talent_severity": (
                risk_severity if risk_is_exposed else None
            ),
            "negative_value": (
                str(severity_values[str(risk_severity)])
                if risk_is_exposed
                else "0"
            ),
        }
    return members, exposed


def _build_team_rule(
    *,
    rule_manifest: Mapping[str, Any],
    policy: Mapping[str, Any],
    ruler: str,
    current_profiles: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    source_path = _resolve(str(rule_manifest["source"]))
    source = _load_json(source_path)
    if source.get("ruler") != ruler:
        raise ValueError("team source ruler 不匹配")
    team_policy = policy["rules"]["team_building"]
    members, exposed_risk_names = _team_profile_members(
        source,
        team_policy,
        current_profiles,
    )
    positive_names = [str(name) for name in rule_manifest.get("positive_members") or []]
    negative_names = [str(name) for name in rule_manifest.get("negative_members") or []]
    if current_profiles is not None:
        negative_names = sorted(exposed_risk_names)
    budget = policy["settlement_budget"]["team_building"]
    if len(positive_names) > int(budget["positive_member_budget"]):
        raise ValueError("team_building 正池超出预算")
    if len(negative_names) > int(budget["negative_member_budget"]):
        raise ValueError("team_building 负池超出预算")
    if source.get("schema_version") == "i5b-team-member-profile-pool-v1":
        if set(positive_names) != set(members):
            raise ValueError("team_building 正池必须消费完整冻结画像成员集合")
        if set(negative_names) != exposed_risk_names:
            raise ValueError("team_building 负池必须等于画像确认的窗口风险成员")
    if len(positive_names) != len(set(positive_names)) or len(negative_names) != len(
        set(negative_names)
    ):
        raise ValueError("team_building 成员重复")
    unknown = sorted((set(positive_names) | set(negative_names)) - set(members))
    if unknown:
        raise ValueError(f"team_building 未知成员: {unknown}")

    positive_rows = sorted(
        (members[name] for name in positive_names),
        key=lambda row: (-_decimal(row["talent_value"]), str(row["person"])),
    )
    negative_rows = sorted(
        (members[name] for name in negative_names),
        key=lambda row: (-_decimal(row["negative_value"]), str(row["person"])),
    )
    positive_pool = sum(
        (_decimal(row["talent_value"]) for row in positive_rows), Decimal("0")
    )
    negative_pool = sum(
        (_decimal(row["negative_value"]) for row in negative_rows), Decimal("0")
    )
    complementarity_option = str(rule_manifest["functional_complementarity"])
    stability_option = str(rule_manifest["long_term_stability"])
    complementarity = _decimal(
        team_policy["role_complementarity_factor"][complementarity_option]
    )
    stability = _decimal(team_policy["long_term_stability_factor"][stability_option])
    positive = positive_pool * complementarity * stability
    negative = negative_pool
    support_reason = str(rule_manifest["remaining_member_judge_reason"])
    supporting = sorted(set(members) - set(positive_names) - set(negative_names))
    return {
        "rule_code": "team_building",
        "rule_label": RULE_LABELS["team_building"],
        "source_ref": str(rule_manifest["source"]),
        "source_sha256": _sha256(source_path.read_bytes()),
        "source_candidate_count": len(members),
        "positive_member_budget": int(budget["positive_member_budget"]),
        "negative_member_budget": int(budget["negative_member_budget"]),
        "positive_members": [
            {
                "person": row["person"],
                "profile_ref": row["profile_ref"],
                "profile_snapshot_version": row.get("profile_snapshot_version"),
                "talent_grade": row["effective_talent_grade"],
                "talent_value": str(row["talent_value"]),
                "talent_grade_basis": str(row.get("talent_grade_basis") or ""),
                "role_families": list(row.get("role_families") or []),
                "supporting_unit_refs": list(row.get("supporting_unit_refs") or []),
            }
            for row in positive_rows
        ],
        "negative_members": [
            {
                "person": row["person"],
                "profile_ref": row["profile_ref"],
                "profile_snapshot_version": row.get("profile_snapshot_version"),
                "negative_class": row["negative_talent_class"],
                "negative_severity": row["negative_talent_severity"],
                "negative_value": str(row["negative_value"]),
                "talent_grade": row["effective_talent_grade"],
                "talent_value": str(row["talent_value"]),
                "talent_grade_basis": str(row.get("talent_grade_basis") or ""),
                "role_families": list(row.get("role_families") or []),
                "supporting_unit_refs": list(row.get("supporting_unit_refs") or []),
            }
            for row in negative_rows
        ],
        "supporting_only_members": [
            {"person": name, "judge_reason": support_reason} for name in supporting
        ],
        "governance_results": list(rule_manifest.get("governance_results") or ()),
        "functional_complementarity": complementarity_option,
        "functional_complementarity_factor": _rounded(complementarity),
        "long_term_stability": stability_option,
        "long_term_stability_factor": _rounded(stability),
        "positive_pool": _rounded(positive_pool),
        "negative_pool": _rounded(negative_pool),
        "positive_signal": _rounded(positive),
        "negative_signal": _rounded(negative),
        "rule_raw_net": _rounded(positive - negative),
        "candidate_disposition_complete": True,
        "profile_source_enforced": all(
            bool(row.get("profile_ref")) for row in members.values()
        ),
        "profile_source": (
            "v4_person_profile.person_profiles"
            if current_profiles is not None
            else str(rule_manifest["source"])
        ),
    }


def _amplitude_diagnostic(policy: Mapping[str, Any]) -> dict[str, Any]:
    material_max = _decimal(policy["material_layer"]["material_score_max"])
    event_budget = policy["settlement_budget"]["event_rules"]
    generic_event_max = material_max * _decimal(
        event_budget["talent_discovery"]["positive"]
    )
    appointment_rank_sum = sum(
        (
            Decimal("1") / _decimal(rank).sqrt()
            for rank in range(
                1, int(event_budget["appointment_delegation"]["positive"]) + 1
            )
        ),
        Decimal("0"),
    )
    team_budget = policy["settlement_budget"]["team_building"]
    team_policy = policy["rules"]["team_building"]
    positive_member_count = _decimal(team_budget["positive_member_budget"])
    negative_member_count = _decimal(team_budget["negative_member_budget"])
    structure_max = max(
        _decimal(value)
        for value in team_policy["role_complementarity_factor"].values()
    ) * max(
        _decimal(value)
        for value in team_policy["long_term_stability_factor"].values()
    )
    return {
        "decision_status": "insufficient_cross_ruler_distribution",
        "cohort_ruler_count": 1,
        "amplitude_change_recommended": None,
        "reason": "理论包络未因材料预算失去量级；须在证据合同和 strongest-N 稳定后使用多皇帝分布判断实测压缩。",
        "theoretical_positive_envelope": {
            "talent_discovery": _rounded(generic_event_max),
            "appointment_delegation": _rounded(
                Decimal("1.5") * material_max * appointment_rank_sum
            ),
            "team_building": _rounded(
                max(
                    _decimal(value)
                    for value in team_policy["talent_quality_factor"].values()
                )
                * positive_member_count
                * structure_max
            ),
            "tolerate_talent": _rounded(generic_event_max),
            "anti_nepotism": _rounded(generic_event_max),
        },
        "theoretical_negative_envelope": {
            "talent_discovery": _rounded(generic_event_max),
            "appointment_delegation": _rounded(material_max * appointment_rank_sum),
            "team_building": _rounded(
                max(
                    _decimal(value)
                    for value in team_policy["negative_talent_severity_value"].values()
                )
                * negative_member_count
            ),
            "tolerate_talent": _rounded(generic_event_max),
            "anti_nepotism": _rounded(generic_event_max),
        },
    }


def build_i5b_material_budget_shadow(
    manifest_path: Path,
    *,
    current_profiles: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = _load_yaml(manifest_path)
    if manifest.get("schema_version") != "i5b-material-budget-shadow-manifest-v1":
        raise ValueError("材料预算 manifest schema_version 不匹配")
    policy_path = _resolve(str(manifest["policy"]))
    policy = _load_yaml(policy_path)
    if policy.get("status") != "v3_scoring_skeleton_with_v4_settlement_budget_shadow":
        raise ValueError("计分政策未启用材料结算预算")
    ruler = str(manifest["ruler"])
    rules: list[dict[str, Any]] = []
    for rule_code in RULE_ORDER:
        rule_manifest = manifest["rules"][rule_code]
        if rule_code == "team_building":
            rules.append(
                _build_team_rule(
                    rule_manifest=rule_manifest,
                    policy=policy,
                    ruler=ruler,
                    current_profiles=current_profiles,
                )
            )
        else:
            rules.append(
                _build_material_rule(
                    rule_code=rule_code,
                    rule_manifest=rule_manifest,
                    policy=policy,
                    ruler=ruler,
                )
            )
    weights = policy["item_raw_signal"]["rule_weights"]
    weighted = sum(
        (
            _decimal(rule["rule_raw_net"]) * _decimal(weights[rule["rule_code"]])
            for rule in rules
        ),
        Decimal("0"),
    )
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "material_budget_scored_shadow_complete",
        "task_code": str(manifest["task_code"]),
        "ruler": ruler,
        "ruler_ref": str(manifest["ruler_ref"]),
        "window": str(manifest["window"]),
        "policy_ref": str(manifest["policy"]),
        "policy_sha256": _sha256(policy_path.read_bytes()),
        "rules": rules,
        "summary": {
            "rule_count": len(rules),
            "weighted_raw_signal": _rounded(weighted),
            "settled_event_positive_count": sum(
                len(
                    [
                        row
                        for row in rule.get("settled_materials") or []
                        if row["side"] == "positive"
                    ]
                )
                for rule in rules
            ),
            "settled_event_negative_count": sum(
                len(
                    [
                        row
                        for row in rule.get("settled_materials") or []
                        if row["side"] == "negative"
                    ]
                )
                for rule in rules
            ),
            "team_positive_member_count": len(
                next(
                    rule for rule in rules if rule["rule_code"] == "team_building"
                )["positive_members"]
            ),
            "team_negative_member_count": len(
                next(
                    rule for rule in rules if rule["rule_code"] == "team_building"
                )["negative_members"]
            ),
        },
        "amplitude_diagnostic": _amplitude_diagnostic(policy),
        "declarations": {
            "existing_formal_facts_only": True,
            "context_labels_used_as_scoring_slots": False,
            "numeric_top_k_selection_used": True,
            "numeric_top_k_applied_after_eligibility_gate": True,
            "domain_representation_quota_used": False,
            "unfilled_budget_penalty_used": False,
            "candidate_disposition_complete": all(
                row.get("candidate_disposition_complete") is True for row in rules
            ),
            "team_profile_source_enforced": next(
                row for row in rules if row["rule_code"] == "team_building"
            ).get("profile_source_enforced") is True,
            "external_retrieval_count": 0,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "score": None,
            "tier": None,
            "ranking": None,
        },
    }
    report["report_sha256"] = _sha256(_canonical_bytes(report))
    return report


def render_i5b_material_budget_shadow_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        f"# {report['ruler']}第五项B材料预算计分验证",
        "",
        f"- 计分窗口：`{report['window']}`",
        "- 沿用材料级因子和原聚合公式；不使用领域固定槽位。",
        "- 事件材料先通过人工 Gate，再按同侧最终材料分结算 strongest-N；未用满预算不扣分。",
        "- 本报告不生成45分、tier或排名。",
        "",
        "## 汇总",
        "",
        "| Rule | 正向信号 | 负向信号 | 净信号 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for rule in report["rules"]:
        lines.append(
            f"| {rule['rule_label']} | {rule['positive_signal']} | "
            f"{rule['negative_signal']} | {rule['rule_raw_net']} |"
        )
    lines.extend(
        [
            "",
            f"加权 raw signal：`{report['summary']['weighted_raw_signal']}`。",
            "",
            "## 振幅诊断",
            "",
            f"- 状态：`{report['amplitude_diagnostic']['decision_status']}`",
            "- 当前是否建议修改振幅：`待定`",
            f"- 判断：{report['amplitude_diagnostic']['reason']}",
        ]
    )
    for rule in report["rules"]:
        lines.extend(["", f"## {rule['rule_label']}", ""])
        if rule["rule_code"] == "team_building":
            lines.extend(
                [
                    f"正池 `{len(rule['positive_members'])}/{rule['positive_member_budget']}`，"
                    f"负池 `{len(rule['negative_members'])}/{rule['negative_member_budget']}`。",
                    "",
                    "| 方向 | 对象 | 档位/风险 | 数值 | 支撑REU |",
                    "| --- | --- | --- | ---: | --- |",
                ]
            )
            for row in rule["positive_members"]:
                lines.append(
                    f"| 正向 | {row['person']} | {row['talent_grade']} | "
                    f"{row['talent_value']} | {'、'.join(row['supporting_unit_refs'])} |"
                )
            for row in rule["negative_members"]:
                lines.append(
                    f"| 负向 | {row['person']} | {row['negative_class']} / "
                    f"{row['negative_severity']} | {row['negative_value']} | "
                    f"{'、'.join(row['supporting_unit_refs'])} |"
                )
            lines.extend(
                [
                    "",
                    f"团队结构系数：`{rule['functional_complementarity_factor']} × "
                    f"{rule['long_term_stability_factor']}`。",
                    "",
                    "未计分成员均保留为团队 lineage，不因领域空缺扣分。",
                ]
            )
            continue
        positive_count = sum(
            row["side"] == "positive" for row in rule["settled_materials"]
        )
        negative_count = sum(
            row["side"] == "negative" for row in rule["settled_materials"]
        )
        lines.extend(
            [
                f"正向结算 `{positive_count}/{rule['positive_budget']}`，"
                f"负向结算 `{negative_count}/{rule['negative_budget']}`。",
                "",
                "| 方向 | 对象 | REU | 材料值 | Judge理由 | 计分事实 |",
                "| --- | --- | --- | ---: | --- | --- |",
            ]
        )
        for row in rule["settled_materials"]:
            direction = "正向" if row["side"] == "positive" else "负向"
            fact = str(row["fact"]).replace("|", "｜").replace("\n", " ")
            lines.append(
                f"| {direction} | {row['subject']} | {row['rule_evidence_unit_ref']} | "
                f"{row['material_magnitude']} | {row['judge_reason']} | {fact} |"
            )
        if rule["supporting_only_materials"]:
            lines.extend(
                [
                    "",
                    "### 未计分支持材料",
                    "",
                    "| 对象 | REU | Judge理由 |",
                    "| --- | --- | --- |",
                ]
            )
            for row in rule["supporting_only_materials"]:
                lines.append(
                    f"| {row['subject']} | {row['rule_evidence_unit_ref']} | "
                    f"{row['judge_reason']} |"
                )
    lines.extend(["", f"报告指纹：`{report['report_sha256']}`", ""])
    return "\n".join(lines)


def write_i5b_material_budget_shadow(
    *, manifest_path: Path, output_json: Path, output_markdown: Path
) -> dict[str, Any]:
    report = build_i5b_material_budget_shadow(manifest_path)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_markdown.write_text(
        render_i5b_material_budget_shadow_markdown(report), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()
    write_i5b_material_budget_shadow(
        manifest_path=args.manifest,
        output_json=args.output_json,
        output_markdown=args.output_md,
    )


if __name__ == "__main__":
    main()
