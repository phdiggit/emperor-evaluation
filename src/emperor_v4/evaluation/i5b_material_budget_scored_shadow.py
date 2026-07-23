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


def _factor_label_catalog(rule_code: str) -> dict[str, str]:
    display = yaml.safe_load(
        (ROOT / "config/i5b-scoring-detail-display.yml").read_text(encoding="utf-8")
    )
    labels = {
        str(code): str(value["label_zh"])
        for code, value in (display.get("common_factors") or {}).items()
    }
    labels.update(
        {
            str(code): str(value["label_zh"])
            for code, value in (
                ((display.get("rules") or {}).get(rule_code) or {}).get("factors")
                or {}
            ).items()
        }
    )
    return labels


def _factor_value_text(rule_code: str, row: Mapping[str, Any]) -> str:
    labels = _factor_label_catalog(rule_code)
    if rule_code == "appointment_delegation":
        factor_order = APPOINTMENT_FACTORS
    else:
        side = str(row.get("side") or "")
        if not side:
            side = (
                "negative"
                if (row.get("factor_option_codes") or {}).get("direction_sign")
                == "negative"
                else "positive"
            )
        factor_order = FACTOR_NAMES[rule_code][side]
    values = row.get("factor_values") or {}
    return "；".join(
        f"{labels.get(code, code)} {_rounded(_decimal(values[code]))}"
        for code in factor_order
        if code in values
    )


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
        row = {
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
        if material.get("projection_observations"):
            row["projection_observations"] = [
                dict(value) for value in material["projection_observations"]
            ]
        if material.get("projection_coverage"):
            row["projection_coverage"] = dict(material["projection_coverage"])
        rows.append(row)
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
        if material.get("projection_observations"):
            row["projection_observations"] = [
                dict(value) for value in material["projection_observations"]
            ]
        if material.get("projection_coverage"):
            row["projection_coverage"] = dict(material["projection_coverage"])
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
        "factor_values": {
            key: _rounded(_decimal(value))
            for key, value in (material.get("factor_values") or {}).items()
        },
        "factor_option_codes": material["factor_option_codes"],
        "override_reasons": list(material.get("override_reasons") or []),
        "fact": str(decision.get("fact_override") or material["fact"]),
        "source_refs": material["source_refs"],
    }
    if material.get("settlement_object_ref"):
        row["settlement_object_ref"] = str(material["settlement_object_ref"])
    if material.get("v4_factor_projection"):
        row["v4_factor_projection"] = material["v4_factor_projection"]
    if material.get("projection_observations"):
        row["projection_observations"] = [
            dict(value) for value in material["projection_observations"]
        ]
    if material.get("projection_coverage"):
        row["projection_coverage"] = dict(material["projection_coverage"])
    if material.get("talent_quality_basis"):
        row["talent_quality_basis"] = material["talent_quality_basis"]
    return row


def _object_density_projection(
    selected: Sequence[Mapping[str, Any]],
) -> tuple[Decimal, dict[str, Decimal], dict[str, Decimal]]:
    by_object: dict[str, list[Mapping[str, Any]]] = {}
    for material in selected:
        settlement_object_ref = str(
            material.get("settlement_object_ref") or material["object_ref"]
        )
        by_object.setdefault(settlement_object_ref, []).append(material)
    total = Decimal("0")
    object_values: dict[str, Decimal] = {}
    material_contributions: dict[str, Decimal] = {}
    for settlement_object_ref, materials in by_object.items():
        ordered = sorted(
            materials,
            key=lambda row: (-row["material_magnitude"], row["material_id"]),
        )
        strongest = ordered[0]["material_magnitude"]
        raw_contributions = {
            str(row["material_id"]): (
                row["material_magnitude"]
                if index == 0
                else Decimal("0.35") * row["material_magnitude"]
            )
            for index, row in enumerate(ordered)
        }
        raw_value = sum(raw_contributions.values(), Decimal("0"))
        object_value = min(
            raw_value,
            strongest * Decimal("1.5"),
            Decimal("4"),
        )
        scale = object_value / raw_value if raw_value else Decimal("0")
        object_values[settlement_object_ref] = object_value
        material_contributions.update(
            {
                material_id: contribution * scale
                for material_id, contribution in raw_contributions.items()
            }
        )
        total += object_value
    return total, object_values, material_contributions


def _object_density(selected: Sequence[Mapping[str, Any]]) -> Decimal:
    total, _, _ = _object_density_projection(selected)
    return total


def _appointment_object_projection(
    materials: Sequence[Mapping[str, Any]], object_cap: Decimal
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    grouped: dict[str, dict[str, list[Mapping[str, Any]]]] = {}
    for material in materials:
        object_ref = str(material["object_ref"])
        event_ref = str(
            material.get("rule_evidence_unit_ref") or material["material_id"]
        )
        grouped.setdefault(object_ref, {}).setdefault(event_ref, []).append(material)

    object_values: dict[str, Decimal] = {}
    material_contributions: dict[str, Decimal] = {}
    for object_ref, events in grouped.items():
        event_rows = []
        for event_ref, event_materials in events.items():
            ordered_materials = sorted(
                event_materials,
                key=lambda row: (-row["material_magnitude"], row["material_id"]),
            )
            contributions = {
                str(material["material_id"]): material["material_magnitude"]
                / Decimal(rank)
                for rank, material in enumerate(ordered_materials, start=1)
            }
            event_rows.append((event_ref, sum(contributions.values()), contributions))
        event_rows.sort(key=lambda row: (-row[1], row[0]))
        raw_contributions: dict[str, Decimal] = {}
        for event_rank, (_, _, contributions) in enumerate(event_rows, start=1):
            for material_id, value in contributions.items():
                raw_contributions[material_id] = value / Decimal(event_rank)
        raw_object_value = sum(raw_contributions.values(), Decimal("0"))
        capped_object_value = min(raw_object_value, object_cap)
        cap_scale = (
            capped_object_value / raw_object_value
            if raw_object_value > 0
            else Decimal("0")
        )
        object_values[object_ref] = capped_object_value
        material_contributions.update(
            {
                material_id: value * cap_scale
                for material_id, value in raw_contributions.items()
            }
        )
    return object_values, material_contributions


def _appointment_density(
    selected: Sequence[Mapping[str, Any]],
    side: str,
    object_cap: Decimal,
    rank_factors: Sequence[Mapping[str, Any]],
) -> Decimal:
    object_values, _ = _appointment_object_projection(selected, object_cap)
    scale = Decimal("1.5") if side == "positive" else Decimal("1")
    total = Decimal("0")
    ordered = sorted(object_values.values(), reverse=True)
    rank = 0
    previous: Decimal | None = None
    for index, value in enumerate(ordered, start=1):
        if previous is None or value != previous:
            rank = index
        total += value * _event_rank_factor(rank_factors, rank)
        previous = value
    return scale * total


def _event_rank_factor(
    rank_factors: Sequence[Mapping[str, Any]], rank: int
) -> Decimal:
    if rank < 1 or not rank_factors:
        raise ValueError("事件材料尾部折减合同无效")
    for row in rank_factors:
        if rank <= int(row["through_rank"]):
            return _decimal(row["factor"])
    return _decimal(rank_factors[-1]["factor"])


def _build_material_rule(
    *,
    rule_code: str,
    rule_manifest: Mapping[str, Any],
    policy: Mapping[str, Any],
    ruler: str,
    settlement_mode: str,
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
    rank_factors = policy["settlement_budget"]["event_rank_factors"]
    appointment_object_cap = Decimal("0")
    if rule_code == "appointment_delegation":
        aggregation_code = str(policy["rules"][rule_code]["aggregation_policy"])
        appointment_object_cap = _decimal(
            policy["aggregation_policies"][aggregation_code][
                "same_object_value_cap"
            ]
        )
    selected_by_side: dict[str, list[dict[str, Any]]] = {}
    selected_views: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    eligible_ids: set[str] = set()
    object_aggregate_by_side: dict[str, dict[str, Decimal]] = {}
    object_material_contribution_by_side: dict[str, dict[str, Decimal]] = {}
    object_boundary_by_side: dict[str, Decimal] = {}
    object_rank_by_side: dict[str, dict[str, int]] = {}
    material_rank_by_side: dict[str, dict[str, int]] = {}
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
            if rule_code == "anti_nepotism":
                material["settlement_object_ref"] = str(
                    decision.get("aggregation_key")
                    or decision["independence_key"]
                )
            candidates.append((material, decision))
        if rule_code == "appointment_delegation":
            grouped: dict[
                str, list[tuple[dict[str, Any], Mapping[str, Any]]]
            ] = {}
            for candidate in candidates:
                grouped.setdefault(str(candidate[0]["object_ref"]), []).append(
                    candidate
                )
            object_totals, material_contributions = _appointment_object_projection(
                [row[0] for row in candidates], appointment_object_cap
            )
            ranked_objects = sorted(
                grouped,
                key=lambda object_ref: (-object_totals[object_ref], object_ref),
            )
            selected_objects = (
                ranked_objects
                if settlement_mode == "all_eligible_shadow"
                else ranked_objects[: int(budget[side])]
            )
            object_aggregate_by_side[side] = object_totals
            object_material_contribution_by_side[side] = material_contributions
            ranks: dict[str, int] = {}
            previous_value: Decimal | None = None
            competition_rank = 0
            for index, object_ref in enumerate(ranked_objects, start=1):
                value = object_totals[object_ref]
                if previous_value is None or value != previous_value:
                    competition_rank = index
                ranks[object_ref] = competition_rank
                previous_value = value
            object_rank_by_side[side] = ranks
            object_boundary_by_side[side] = min(
                (object_totals[object_ref] for object_ref in selected_objects),
                default=Decimal("0"),
            )
            selected_candidates = [
                candidate
                for object_ref in selected_objects
                for candidate in sorted(
                    grouped[object_ref],
                    key=lambda row: (
                        -row[0]["material_magnitude"],
                        row[0]["material_id"],
                    ),
                )
            ]
        else:
            candidates.sort(
                key=lambda row: (
                    -row[0]["material_magnitude"], row[0]["material_id"]
                )
            )
            selected_candidates = (
                candidates
                if settlement_mode == "all_eligible_shadow"
                else candidates[: int(budget[side])]
            )
            ranks: dict[str, int] = {}
            previous_value: Decimal | None = None
            competition_rank = 0
            for index, (material, _) in enumerate(selected_candidates, start=1):
                value = material["material_magnitude"]
                if previous_value is None or value != previous_value:
                    competition_rank = index
                ranks[str(material["material_id"])] = competition_rank
                previous_value = value
            material_rank_by_side[side] = ranks
        selected = [row[0] for row in selected_candidates]
        for material, decision in selected_candidates:
            material_id = str(material["material_id"])
            selected_ids.add(material_id)
            view = _material_view(material, decision)
            if rule_code == "appointment_delegation":
                object_ref = str(material["object_ref"])
                view["selection_basis"] = (
                    "eligibility_gate_then_object_merge_all_eligible_shadow"
                    if settlement_mode == "all_eligible_shadow"
                    else "eligibility_gate_then_object_merge_then_strongest_n_objects"
                )
                view["object_aggregate_magnitude"] = _rounded(
                    object_aggregate_by_side[side][object_ref]
                )
                view["object_internal_contribution"] = _rounded(
                    object_material_contribution_by_side[side][material_id]
                )
                view["actual_signal_contribution"] = _rounded(
                    (Decimal("1.5") if side == "positive" else Decimal("1"))
                    * object_material_contribution_by_side[side][material_id]
                    * _event_rank_factor(
                        rank_factors, object_rank_by_side[side][object_ref]
                    )
                )
                view["settlement_rank"] = object_rank_by_side[side][object_ref]
                view["settlement_rank_factor"] = _rounded(
                    _event_rank_factor(
                        rank_factors, object_rank_by_side[side][object_ref]
                    )
                )
            else:
                view["selection_basis"] = (
                    "eligibility_gate_all_eligible_shadow"
                    if settlement_mode == "all_eligible_shadow"
                    else "eligibility_gate_then_strongest_n"
                )
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
        boundary = (
            object_boundary_by_side[side]
            if rule_code == "appointment_delegation"
            else min(
                (row["material_magnitude"] for row in selected_by_side[side]),
                default=Decimal("0"),
            )
        )
        comparison_label = (
            "同一责任对象材料合并分"
            if rule_code == "appointment_delegation"
            else "材料分"
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
                **(
                    {
                        "object_aggregate_magnitude": _rounded(
                            object_aggregate_by_side[side][
                                str(material["object_ref"])
                            ]
                        )
                    }
                    if rule_code == "appointment_delegation"
                    else {}
                ),
                "judge_reason": (
                    "已通过适用性、归责、独立性和去重 Gate；"
                    f"{comparison_label}低于当前{'正向' if side == 'positive' else '负向'}"
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
        positive = _appointment_density(
            selected_by_side["positive"],
            "positive",
            appointment_object_cap,
            rank_factors,
        )
        negative = _appointment_density(
            selected_by_side["negative"],
            "negative",
            appointment_object_cap,
            rank_factors,
        )
    else:
        positive, positive_objects, positive_contributions = _object_density_projection(
            selected_by_side["positive"]
        )
        negative, negative_objects, negative_contributions = _object_density_projection(
            selected_by_side["negative"]
        )
        object_values = {**positive_objects, **negative_objects}
        contributions = {**positive_contributions, **negative_contributions}
        positive = sum(
            (
                contribution
                * _event_rank_factor(
                    rank_factors, material_rank_by_side["positive"][material_id]
                )
                for material_id, contribution in positive_contributions.items()
            ),
            Decimal("0"),
        )
        negative = sum(
            (
                contribution
                * _event_rank_factor(
                    rank_factors, material_rank_by_side["negative"][material_id]
                )
                for material_id, contribution in negative_contributions.items()
            ),
            Decimal("0"),
        )
        for view in selected_views:
            material_id = str(view["material_id"])
            side = str(view["side"])
            settlement_object_ref = str(
                view.get("settlement_object_ref") or view["object_ref"]
            )
            view["object_aggregate_magnitude"] = _rounded(
                object_values[settlement_object_ref]
            )
            view["object_internal_contribution"] = _rounded(
                contributions[material_id]
            )
            rank = material_rank_by_side[side][material_id]
            rank_factor = _event_rank_factor(rank_factors, rank)
            view["settlement_rank"] = rank
            view["settlement_rank_factor"] = _rounded(rank_factor)
            view["actual_signal_contribution"] = _rounded(
                contributions[material_id] * rank_factor
            )
    settled_objects: list[dict[str, Any]] = []
    if rule_code == "appointment_delegation":
        grouped_views: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for view in selected_views:
            grouped_views.setdefault(
                (str(view["side"]), str(view["object_ref"])), []
            ).append(view)
        for (side, object_ref), rows in sorted(
            grouped_views.items(),
            key=lambda item: (
                0 if item[0][0] == "positive" else 1,
                int(item[1][0]["settlement_rank"]),
                str(item[1][0]["subject"]),
            ),
        ):
            settled_objects.append(
                {
                    "side": side,
                    "object_ref": object_ref,
                    "subject": str(rows[0]["subject"]),
                    "supporting_chain_count": len(rows),
                    "supporting_material_ids": sorted(
                        str(row["material_id"]) for row in rows
                    ),
                    "object_aggregate_magnitude": str(
                        rows[0]["object_aggregate_magnitude"]
                    ),
                    "settlement_rank": int(rows[0]["settlement_rank"]),
                    "settlement_rank_factor": str(
                        rows[0]["settlement_rank_factor"]
                    ),
                    "actual_signal_contribution": _rounded(
                        sum(
                            (
                                _decimal(row["actual_signal_contribution"])
                                for row in rows
                            ),
                            Decimal("0"),
                        )
                    ),
                }
            )
    result = {
        "rule_code": rule_code,
        "rule_label": RULE_LABELS[rule_code],
        "source_ref": str(
            rule_manifest.get("source_ref") or rule_manifest["source"]
        ),
        "source_sha256": _sha256(source_path.read_bytes()),
        "supplemental_source_refs": [
            str(value) for value in rule_manifest.get("supplemental_sources") or ()
        ],
        "supplemental_source_sha256s": [
            _sha256(path.read_bytes()) for path in supplemental_paths
        ],
        "source_candidate_count": len(materials),
        "eligible_candidate_count": len(eligible_ids),
        "settlement_mode": settlement_mode,
        "configured_positive_budget": int(budget["positive"]),
        "configured_negative_budget": int(budget["negative"]),
        "positive_budget": (
            sum(row["side"] == "positive" for row in selected_views)
            if settlement_mode == "all_eligible_shadow"
            else int(budget["positive"])
        ),
        "negative_budget": (
            sum(row["side"] == "negative" for row in selected_views)
            if settlement_mode == "all_eligible_shadow"
            else int(budget["negative"])
        ),
        "settlement_budget_unit": str(budget["unit"]),
        "settlement_rank_factors": [dict(row) for row in rank_factors],
        **(
            {"same_object_value_cap": _rounded(appointment_object_cap)}
            if rule_code == "appointment_delegation"
            else {}
        ),
        "settled_materials": selected_views,
        **(
            {
                "settled_objects": settled_objects,
                "positive_settled_unit_count": sum(
                    row["side"] == "positive" for row in settled_objects
                ),
                "negative_settled_unit_count": sum(
                    row["side"] == "negative" for row in settled_objects
                ),
            }
            if rule_code == "appointment_delegation"
            else {}
        ),
        "supporting_only_materials": supporting_rows,
        "positive_signal": _rounded(positive),
        "negative_signal": _rounded(negative),
        "rule_raw_net": _rounded(positive - negative),
        "candidate_disposition_complete": True,
        "source_projection_coverage_complete": all(
            (by_id[material_id].get("projection_coverage") or {}).get(
                "coverage_complete", True
            )
            is True
            for material_id in eligible_ids
        ),
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
                if current.get("review_status") not in {
                    "human_frozen",
                    "provisional_current",
                }:
                    raise ValueError(f"{row['person']} 唯一人物画像状态非法")
                row["effective_talent_grade"] = str(current["talent_grade"])
                row["talent_grade_basis"] = str(
                    current.get("talent_grade_basis") or ""
                )
                row["profile_ref"] = str(current["profile_ref"])
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
            profile_review = row.get("profile_review") or {}
            row["talent_profile_basis"] = dict(
                profile_review.get("talent_grade") or {}
            )
            row["political_risk"] = dict(
                profile_review.get("political_risk") or {}
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
        ):
            raise ValueError(f"{name} 缺少人工冻结人物画像")
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
        grade_basis = str(profile.get("talent_grade_basis") or "")
        if current_profiles is not None:
            current = current_profiles.get(person_ref)
            if current is None:
                raise ValueError(f"{name} 不在唯一人物画像表 person_profiles")
            if current.get("review_status") not in {
                "human_frozen",
                "provisional_current",
            }:
                raise ValueError(f"{name} 唯一人物画像状态非法")
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
    settlement_mode: str,
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
        "source_ref": str(
            rule_manifest.get("source_ref") or rule_manifest["source"]
        ),
        "source_sha256": _sha256(source_path.read_bytes()),
        "source_candidate_count": len(members),
        "settlement_mode": settlement_mode,
        "configured_positive_member_budget": int(budget["positive_member_budget"]),
        "configured_negative_member_budget": int(budget["negative_member_budget"]),
        "positive_member_budget": int(budget["positive_member_budget"]),
        "negative_member_budget": int(budget["negative_member_budget"]),
        "positive_members": [
            {
                "person": row["person"],
                "profile_ref": row["profile_ref"],
                "talent_grade": row["effective_talent_grade"],
                "talent_value": str(row["talent_value"]),
                "talent_grade_basis": str(row.get("talent_grade_basis") or ""),
                "talent_profile_basis": dict(row.get("talent_profile_basis") or {}),
                "political_risk": dict(row.get("political_risk") or {}),
                "role_families": list(row.get("role_families") or []),
                "supporting_unit_refs": list(row.get("supporting_unit_refs") or []),
            }
            for row in positive_rows
        ],
        "negative_members": [
            {
                "person": row["person"],
                "profile_ref": row["profile_ref"],
                "negative_class": row["negative_talent_class"],
                "negative_severity": row["negative_talent_severity"],
                "negative_value": str(row["negative_value"]),
                "talent_grade": row["effective_talent_grade"],
                "talent_value": str(row["talent_value"]),
                "talent_grade_basis": str(row.get("talent_grade_basis") or ""),
                "talent_profile_basis": dict(row.get("talent_profile_basis") or {}),
                "political_risk": dict(row.get("political_risk") or {}),
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
    appointment_policy = policy["rules"]["appointment_delegation"]
    appointment_object_cap = _decimal(
        policy["aggregation_policies"][appointment_policy["aggregation_policy"]][
            "same_object_value_cap"
        ]
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
                Decimal("1.5")
                * appointment_object_cap
                * _decimal(event_budget["appointment_delegation"]["positive"])
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
            "appointment_delegation": _rounded(
                appointment_object_cap
                * _decimal(event_budget["appointment_delegation"]["negative"])
            ),
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
    manifest_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = dict(manifest_payload) if manifest_payload is not None else _load_yaml(manifest_path)
    if manifest.get("schema_version") != "i5b-material-budget-shadow-manifest-v1":
        raise ValueError("材料预算 manifest schema_version 不匹配")
    policy_path = _resolve(str(manifest["policy"]))
    policy = _load_yaml(policy_path)
    if policy.get("status") != "current_report_only":
        raise ValueError("计分政策未启用材料结算预算")
    settlement_mode = str(manifest.get("settlement_mode") or "policy_budget")
    if settlement_mode not in {"policy_budget", "all_eligible_shadow"}:
        raise ValueError("材料结算模式只允许 policy_budget 或 all_eligible_shadow")
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
                    settlement_mode=settlement_mode,
                )
            )
        else:
            rules.append(
                _build_material_rule(
                    rule_code=rule_code,
                    rule_manifest=rule_manifest,
                    policy=policy,
                    ruler=ruler,
                    settlement_mode=settlement_mode,
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
        "settlement_mode": settlement_mode,
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
        "amplitude_diagnostic": (
            {
                "decision_status": "not_applicable_all_eligible_shadow",
                "cohort_ruler_count": 1,
                "amplitude_change_recommended": None,
                "reason": "本轮暂时取消材料数量上限，政策预算理论包络不适用于该影子结果。",
            }
            if settlement_mode == "all_eligible_shadow"
            else _amplitude_diagnostic(policy)
        ),
        "declarations": {
            "existing_formal_facts_only": True,
            "context_labels_used_as_scoring_slots": False,
            "numeric_top_k_selection_used": settlement_mode == "policy_budget",
            "numeric_top_k_applied_after_eligibility_gate": settlement_mode
            == "policy_budget",
            "all_eligible_materials_settled": settlement_mode
            == "all_eligible_shadow",
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
        "- 沿用材料级因子和聚合公式，不使用领域固定槽位。",
        "- 事件材料先通过 Judge，再按独立结算对象聚合。",
        "- 未用满预算不扣分。",
        "- 本报告不生成45分、tier或排名，只展示 shadow raw signal。",
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
                    "| 对象 | 方向 | 数值 | 档位 / 风险 | 计分事实 |",
                    "| --- | --- | ---: | --- | --- |",
                ]
            )
            for row in rule["positive_members"]:
                lines.append(
                    f"| {row['person']} | 正向 | {row['talent_value']} | "
                    f"{row['talent_grade']} | {row['talent_grade_basis']} |"
                )
            for row in rule["negative_members"]:
                political_risk = row.get("political_risk") or {}
                risk_events = political_risk.get("event_assessments") or ()
                risk_fact = (
                    str(risk_events[0].get("summary") or "")
                    if risk_events
                    else str(political_risk.get("basis") or "")
                )
                lines.append(
                    f"| {row['person']} | 负向 | {row['negative_value']} | "
                    f"{row['negative_class']} / {row['negative_severity']} | "
                    f"{risk_fact} |"
                )
            lines.extend(
                [
                    "",
                    f"团队结构系数：`{rule['functional_complementarity_factor']} × "
                    f"{rule['long_term_stability_factor']}`。",
                    "",
                    "未进入正8或负3的成员不计分，不因领域空缺另行扣分。",
                ]
            )
            continue
        positive_count = sum(
            row["side"] == "positive" for row in rule["settled_materials"]
        )
        negative_count = sum(
            row["side"] == "negative" for row in rule["settled_materials"]
        )
        if rule["rule_code"] == "appointment_delegation":
            lines.extend(
                [
                    f"正向结算对象 `{rule['positive_settled_unit_count']}/"
                    f"{rule['configured_positive_budget']}`，负向结算对象 "
                    f"`{rule['negative_settled_unit_count']}/"
                    f"{rule['configured_negative_budget']}`；内部责任链 "
                    f"`{positive_count}` 正、`{negative_count}` 负。",
                    "",
                    "| 任用对象 | 方向 | 内部责任链 | 对象聚合值 | 名次系数 | 实际计入信号 |",
                    "| --- | --- | ---: | ---: | ---: | ---: |",
                ]
            )
            for row in rule["settled_objects"]:
                direction = "正向" if row["side"] == "positive" else "负向"
                lines.append(
                    f"| {row['subject']} | {direction} | "
                    f"{row['supporting_chain_count']} | "
                    f"{row['object_aggregate_magnitude']} | "
                    f"{row['settlement_rank_factor']} | "
                    f"{row['actual_signal_contribution']} |"
                )
            lines.extend(
                [
                    "",
                    "### 对象内责任链展开",
                    "",
                    "| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 | 计分事实 |",
                    "| --- | --- | ---: | ---: | --- | --- |",
                ]
            )
        else:
            lines.extend(
                [
                    f"正向材料 `{positive_count}`，负向材料 `{negative_count}`。",
                    "",
                    "| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 | 计分事实 |",
                    "| --- | --- | ---: | ---: | --- | --- |",
                ]
            )
        for row in rule["settled_materials"]:
            direction = "正向" if row["side"] == "positive" else "负向"
            fact = str(row["fact"]).replace("|", "｜").replace("\n", " ")
            actual_signal = row.get(
                "actual_signal_contribution",
                row.get("object_internal_contribution", row["material_magnitude"]),
            )
            lines.append(
                f"| {row['subject']} | {direction} | {row['material_magnitude']} | "
                f"{actual_signal} | {_factor_value_text(rule['rule_code'], row)} | "
                f"{fact} |"
            )
        if rule["supporting_only_materials"]:
            lines.extend(
                [
                    "",
                    "### 未计分支持材料",
                    "",
                    "| 对象 | 判定 | 因子取值 | 事实 |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for row in rule["supporting_only_materials"]:
                lines.append(
                    f"| {row['subject']} | 未计入 | {_factor_value_text(rule['rule_code'], row)} | "
                    f"{str(row.get('fact') or '').replace('|', '｜').replace(chr(10), ' ')} |"
                )
    lines.append("")
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
