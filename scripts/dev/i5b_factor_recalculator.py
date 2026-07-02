from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import DEFAULT_FORMULA_CODE, RuleSignals, calculate_formula
from scripts.build.i5b_item_result_calculator import calculate_item_results as write_item_results
from scripts.dev.evidence_cluster_workbench import (
    ClusterInput,
    fetch_cluster_calc_detail_rows,
    render_cluster_note,
    resolve_dsn,
    upsert_clusters,
)
from scripts.dev.i5b_factor_consistency_audit import (
    I5BFactorConsistencyAuditError,
    assert_no_factor_consistency_errors,
    build_audit_report_from_inputs,
)
from scripts.dev.i5b_rule_object_coverage_audit import attr_value, fetch_emp_object_rows


DEFAULT_ITEM_CODE = "I5B"
DEFAULT_CLUSTER_FORMULA = "evidence_cluster_signal_v3"
DEFAULT_FACTOR_DOCS = (
    ROOT / "docs" / "\u5206\u9879\u89c4\u5219" / "\u7b2c\u4e94\u9879\u7edf\u6cbb\u8005\u653f\u6cbb\u7d20\u8d28" / "B\u7528\u4eba\u4e0e\u6388\u6743.md",
    ROOT / "docs" / "\u8bc1\u636e\u89c4\u5219" / "\u8bc1\u636e\u7c07\u8ba1\u7b97\u516c\u5f0f.md",
)
TEAM_BUILDING_RULE_CODE = "team_building"
TEAM_BUILDING_SOURCE_FORMULA = "evidence_cluster_signal_v2"
TEAM_BUILDING_RANK_DECAYS = (
    Decimal("1.00"),
    Decimal("0.90"),
    Decimal("0.80"),
    Decimal("0.45"),
    Decimal("0.45"),
    Decimal("0.45"),
)


class I5BFactorRecalculatorError(ValueError):
    pass


@dataclass(frozen=True)
class FactorRow:
    value: Decimal
    label: str


@dataclass(frozen=True)
class MaterialScore:
    material_id: int | None
    obj_key: str
    obj_name: str
    side: str
    raw_score: Decimal
    abs_score: Decimal
    factor_values: dict[str, str]
    factor_refs: dict[str, Any]


def quant(value: Decimal, places: str = "0.001") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def decimal_value(value: Any, *, path: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise I5BFactorRecalculatorError(f"{path}: expected decimal") from exc


def optional_int_tuple(value: Any, *, path: str) -> tuple[int, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise I5BFactorRecalculatorError(f"{path}: expected list")
    ids: list[int] = []
    for index, item in enumerate(value):
        if not isinstance(item, int):
            raise I5BFactorRecalculatorError(f"{path}[{index}]: expected integer")
        ids.append(item)
    return tuple(ids)


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().strip("\u3002\uff1b;"))


def parse_factor_catalog(paths: tuple[Path, ...]) -> dict[str, list[FactorRow]]:
    catalog: dict[str, list[FactorRow]] = defaultdict(list)
    factor_name: str | None = None
    row_re = re.compile(r"^\|\s*`?([^`|]+?)`?\s*\|\s*(.*?)\s*\|")
    factor_re = re.compile(r"^`([^`]+)`[\uff1a:]")

    for path in paths:
        if not path.exists():
            raise I5BFactorRecalculatorError(f"factor doc not found: {path}")
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            stripped = raw.strip()
            match = factor_re.match(stripped)
            if match:
                factor_name = match.group(1).strip()
                continue
            if factor_name is None or not stripped.startswith("|"):
                continue
            row_match = row_re.match(stripped)
            if not row_match:
                continue
            first_cell = row_match.group(1).strip()
            second_cell = re.sub(r"<[^>]+>", "", row_match.group(2)).strip()
            if first_cell in {"\u503c", "---"} or not second_cell or set(first_cell) == {"-"}:
                continue
            try:
                parsed = Decimal(first_cell)
                label = second_cell
            except InvalidOperation:
                second_parts = [part.strip().strip("`") for part in second_cell.split("|")]
                try:
                    parsed = Decimal(second_parts[0])
                except (InvalidOperation, IndexError):
                    continue
                label = first_cell.strip().strip("`")
            catalog[factor_name].append(FactorRow(parsed, label))
    return dict(catalog)


def lookup_factor(catalog: dict[str, list[FactorRow]], factor_name: str, label: str) -> Decimal:
    if factor_name not in catalog:
        raise I5BFactorRecalculatorError(f"factor table not found: {factor_name}")
    wanted = normalize_label(label)
    exact_matches: list[FactorRow] = []
    fuzzy_matches: list[tuple[int, FactorRow]] = []
    for row in catalog[factor_name]:
        current = normalize_label(row.label)
        if wanted == current:
            exact_matches.append(row)
            continue
        if wanted in current or current in wanted:
            fuzzy_matches.append((len(current), row))
    if exact_matches:
        return exact_matches[0].value
    if fuzzy_matches:
        fuzzy_matches.sort(key=lambda item: item[0], reverse=True)
        return fuzzy_matches[0][1].value
    raise I5BFactorRecalculatorError(f"factor row not found: {factor_name} / {label}")


def resolve_factor(
    value: Any,
    *,
    factor_name: str,
    catalog: dict[str, list[FactorRow]],
    path: str,
) -> tuple[Decimal, Any]:
    if isinstance(value, dict):
        if "value" in value:
            return decimal_value(value["value"], path=f"{path}.value"), value
        label = value.get("label")
        ref_name = str(value.get("factor", factor_name))
        if not isinstance(label, str) or not label.strip():
            raise I5BFactorRecalculatorError(f"{path}.label: expected non-empty string")
        return lookup_factor(catalog, ref_name, label), value
    return decimal_value(value, path=path), value


def material_side(raw_score: Decimal, configured: str | None, path: str) -> str:
    if configured is not None:
        if configured not in {"positive", "negative"}:
            raise I5BFactorRecalculatorError(f"{path}.direction: expected positive or negative")
        return configured
    if raw_score > 0:
        return "positive"
    if raw_score < 0:
        return "negative"
    raise I5BFactorRecalculatorError(f"{path}: zero material needs explicit non-zero factors")


def compute_material(
    row: dict[str, Any],
    *,
    catalog: dict[str, list[FactorRow]],
    path: str,
) -> MaterialScore:
    factors = row.get("factors")
    if not isinstance(factors, dict) or not factors:
        raise I5BFactorRecalculatorError(f"{path}.factors: expected non-empty object")

    factor_values: dict[str, str] = {}
    factor_refs: dict[str, Any] = {}
    raw_score = Decimal("1")
    for name, raw_factor in factors.items():
        factor_value, factor_ref = resolve_factor(
            raw_factor,
            factor_name=str(name),
            catalog=catalog,
            path=f"{path}.factors.{name}",
        )
        factor_values[str(name)] = str(factor_value)
        factor_refs[str(name)] = factor_ref
        raw_score *= factor_value

    direction = row.get("direction")
    if direction is not None and not isinstance(direction, str):
        raise I5BFactorRecalculatorError(f"{path}.direction: expected string")
    side = material_side(raw_score, direction, path)
    material_id = row.get("obj_src_id", row.get("material_id"))
    if material_id is not None and not isinstance(material_id, int):
        raise I5BFactorRecalculatorError(f"{path}.obj_src_id: expected integer")
    obj_key_value = row.get("obj_id") or row.get("obj_key")
    if obj_key_value is None or not str(obj_key_value).strip():
        raise I5BFactorRecalculatorError(f"{path}: expected obj_id or obj_key for same-object aggregation")
    obj_key = str(obj_key_value)
    return MaterialScore(
        material_id=material_id,
        obj_key=obj_key,
        obj_name=str(row.get("obj_name") or row.get("name") or obj_key),
        side=side,
        raw_score=quant(raw_score),
        abs_score=quant(min(abs(raw_score), Decimal("4.0"))),
        factor_values=factor_values,
        factor_refs=factor_refs,
    )


def object_side_score(scores: list[Decimal]) -> Decimal:
    if not scores:
        return Decimal("0.000")
    ordered = sorted(scores, reverse=True)
    strongest = ordered[0]
    total = strongest + Decimal("0.35") * sum(ordered[1:], Decimal("0"))
    capped = min(total, strongest * Decimal("1.5"), Decimal("4.0"))
    return quant(capped)


def side_signal(object_scores: list[Decimal], coverage: Decimal) -> Decimal:
    if not object_scores:
        return Decimal("0.000")
    raw = math.sqrt(sum(float(score) ** 2 for score in object_scores)) * float(coverage)
    return quant(Decimal(str(raw)))


def team_rank_decay(rank_index: int) -> Decimal:
    if rank_index < len(TEAM_BUILDING_RANK_DECAYS):
        return TEAM_BUILDING_RANK_DECAYS[rank_index]
    return Decimal("0.25")


def signed_side_signal(scores: list[Decimal]) -> Decimal:
    if not scores:
        return Decimal("0.000")
    raw = math.sqrt(sum(float(abs(score)) ** 2 for score in scores))
    return quant(Decimal(str(raw)))


def require_text(row: dict[str, Any], key: str, path: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise I5BFactorRecalculatorError(f"{path}.{key}: expected non-empty string")
    return value.strip()


def compute_cluster(
    row: dict[str, Any],
    *,
    item_code: str,
    formula_code: str,
    catalog: dict[str, list[FactorRow]],
    path: str,
) -> ClusterInput:
    if row.get("rule_code") == TEAM_BUILDING_RULE_CODE:
        return compute_team_building_cluster(
            row,
            item_code=item_code,
            formula_code=formula_code,
            catalog=catalog,
            path=path,
        )

    materials_value = row.get("materials")
    if not isinstance(materials_value, list) or not materials_value:
        raise I5BFactorRecalculatorError(f"{path}.materials: expected non-empty list")

    materials = [
        compute_material(material, catalog=catalog, path=f"{path}.materials[{index}]")
        for index, material in enumerate(materials_value)
        if isinstance(material, dict)
    ]
    if len(materials) != len(materials_value):
        raise I5BFactorRecalculatorError(f"{path}.materials: every item must be an object")

    coverage_value = row.get("coverage", {})
    if coverage_value is None:
        coverage_value = {}
    if not isinstance(coverage_value, dict):
        raise I5BFactorRecalculatorError(f"{path}.coverage: expected object")
    coverage = {
        "positive": decimal_value(coverage_value.get("positive", "1.0"), path=f"{path}.coverage.positive"),
        "negative": decimal_value(coverage_value.get("negative", "1.0"), path=f"{path}.coverage.negative"),
    }

    grouped: dict[str, dict[str, list[Decimal]]] = {
        "positive": defaultdict(list),
        "negative": defaultdict(list),
    }
    for material in materials:
        grouped[material.side][material.obj_key].append(material.abs_score)

    object_scores = {
        side: {obj_key: object_side_score(scores) for obj_key, scores in side_groups.items()}
        for side, side_groups in grouped.items()
    }
    positive_signal = side_signal(list(object_scores["positive"].values()), coverage["positive"])
    negative_signal = side_signal(list(object_scores["negative"].values()), coverage["negative"])
    scored_material_ids = tuple(material.material_id for material in materials if material.material_id is not None)
    explicit_material_ids = optional_int_tuple(row.get("material_ids"), path=f"{path}.material_ids")
    material_ids = tuple(dict.fromkeys((*explicit_material_ids, *scored_material_ids)))
    supporting_material_ids = [material_id for material_id in material_ids if material_id not in scored_material_ids]

    detail = {
        "item_code": item_code,
        "formula_code": formula_code,
        "materials": [
            {
                "obj_src_id": material.material_id,
                "obj_key": material.obj_key,
                "obj_name": material.obj_name,
                "side": material.side,
                "raw_score": str(material.raw_score),
                "abs_score": str(material.abs_score),
                "factor_values": material.factor_values,
                "factor_refs": material.factor_refs,
            }
            for material in materials
        ],
        "object_side_scores": {
            side: {obj_key: str(score) for obj_key, score in side_scores.items()}
            for side, side_scores in object_scores.items()
        },
        "coverage": {side: str(value) for side, value in coverage.items()},
        "covered_material_ids": list(material_ids),
        "scored_material_ids": list(scored_material_ids),
        "positive_signal": str(positive_signal),
        "negative_signal": str(negative_signal),
    }
    detail["supporting_material_ids"] = supporting_material_ids
    return ClusterInput(
        emperor=require_text(row, "emperor", path),
        rule_code=require_text(row, "rule_code", path),
        positive_signal=positive_signal,
        negative_signal=negative_signal,
        formula_code=str(row.get("formula_code") or formula_code),
        note=require_text(row, "note", path),
        material_ids=material_ids,
        calc_note=str(row.get("calc_note") or "structured factor recalculation"),
        calc_detail=detail,
    )


def material_id_and_object(row: dict[str, Any], *, path: str) -> tuple[int | None, str, str]:
    material_id = row.get("obj_src_id", row.get("material_id"))
    if material_id is not None and not isinstance(material_id, int):
        raise I5BFactorRecalculatorError(f"{path}.obj_src_id: expected integer")
    obj_key_value = row.get("obj_id") or row.get("obj_key")
    if obj_key_value is None or not str(obj_key_value).strip():
        raise I5BFactorRecalculatorError(f"{path}: expected obj_id or obj_key for same-object aggregation")
    obj_key = str(obj_key_value)
    obj_name = str(row.get("obj_name") or row.get("name") or obj_key)
    return material_id, obj_key, obj_name


def team_building_side(row: dict[str, Any], *, path: str) -> str:
    side = row.get("direction", row.get("side"))
    if side not in {"positive", "negative"}:
        raise I5BFactorRecalculatorError(f"{path}.direction: expected positive or negative")
    return str(side)


def resolve_team_factor(
    team_factors: dict[str, Any],
    factor_name: str,
    *,
    catalog: dict[str, list[FactorRow]],
    path: str,
) -> tuple[Decimal, Any]:
    if factor_name not in team_factors:
        raise I5BFactorRecalculatorError(f"{path}.team_factors.{factor_name}: expected factor")
    return resolve_factor(
        team_factors[factor_name],
        factor_name=factor_name,
        catalog=catalog,
        path=f"{path}.team_factors.{factor_name}",
    )


def compute_team_building_cluster(
    row: dict[str, Any],
    *,
    item_code: str,
    formula_code: str,
    catalog: dict[str, list[FactorRow]],
    path: str,
) -> ClusterInput:
    materials_value = row.get("materials")
    if not isinstance(materials_value, list) or not materials_value:
        raise I5BFactorRecalculatorError(f"{path}.materials: expected non-empty list")
    if any(not isinstance(material, dict) for material in materials_value):
        raise I5BFactorRecalculatorError(f"{path}.materials: every item must be an object")

    team_factors = row.get("team_factors")
    if not isinstance(team_factors, dict) or not team_factors:
        raise I5BFactorRecalculatorError(f"{path}.team_factors: expected non-empty object")
    complementarity_value, complementarity_ref = resolve_team_factor(
        team_factors,
        "role_complementarity_factor",
        catalog=catalog,
        path=path,
    )
    stability_value, stability_ref = resolve_team_factor(
        team_factors,
        "long_term_stability_factor",
        catalog=catalog,
        path=path,
    )

    positive_candidates: dict[str, dict[str, Any]] = {}
    calc_materials: list[dict[str, Any]] = []
    negative_materials: list[MaterialScore] = []

    for index, material in enumerate(materials_value):
        material_path = f"{path}.materials[{index}]"
        side = team_building_side(material, path=material_path)
        if side == "negative":
            scored = compute_material(material, catalog=catalog, path=material_path)
            negative_materials.append(scored)
            calc_materials.append(
                {
                    "obj_src_id": scored.material_id,
                    "obj_key": scored.obj_key,
                    "obj_name": scored.obj_name,
                    "side": scored.side,
                    "raw_score": str(scored.raw_score),
                    "abs_score": str(scored.abs_score),
                    "factor_values": scored.factor_values,
                    "factor_refs": scored.factor_refs,
                }
            )
            continue

        material_id, obj_key, obj_name = material_id_and_object(material, path=material_path)
        factors = material.get("factors")
        if not isinstance(factors, dict):
            raise I5BFactorRecalculatorError(f"{material_path}.factors: expected object")
        if factors.get("team_quality_excluded"):
            reason = str(factors["team_quality_excluded"])
            calc_materials.append(
                {
                    "obj_src_id": material_id,
                    "obj_key": obj_key,
                    "obj_name": obj_name,
                    "side": "positive",
                    "raw_score": "0.000",
                    "abs_score": "0.000",
                    "factor_values": {"team_quality_excluded": reason},
                    "factor_refs": {"team_quality_excluded": reason},
                    "team_quality_included": False,
                }
            )
            continue
        if "talent_quality_factor" not in factors:
            raise I5BFactorRecalculatorError(f"{material_path}.factors.talent_quality_factor: expected factor")
        talent_value, talent_ref = resolve_factor(
            factors["talent_quality_factor"],
            factor_name="talent_quality_factor",
            catalog=catalog,
            path=f"{material_path}.factors.talent_quality_factor",
        )
        candidate = {
            "obj_src_id": material_id,
            "emp_obj_id": material.get("emp_obj_id"),
            "obj_id": material.get("obj_id"),
            "obj_key": obj_key,
            "obj_name": obj_name,
            "talent_quality_factor": talent_value,
            "talent_quality_ref": talent_ref,
        }
        current = positive_candidates.get(obj_key)
        if current is None or talent_value > current["talent_quality_factor"]:
            positive_candidates[obj_key] = candidate

    ranked = sorted(
        positive_candidates.values(),
        key=lambda item: (-abs(item["talent_quality_factor"]), item["obj_name"], item["obj_key"]),
    )
    team_quality_components: list[dict[str, Any]] = []
    positive_object_scores: dict[str, Decimal] = {}
    for index, item in enumerate(ranked):
        decay = team_rank_decay(index)
        contribution = quant(item["talent_quality_factor"] * decay)
        positive_object_scores[str(item["obj_key"])] = contribution
        component = {
            "rank": index + 1,
            "obj_src_id": item["obj_src_id"],
            "emp_obj_id": item.get("emp_obj_id"),
            "obj_id": item.get("obj_id"),
            "obj_key": item["obj_key"],
            "obj_name": item["obj_name"],
            "talent_quality_factor": str(item["talent_quality_factor"]),
            "talent_quality_ref": item["talent_quality_ref"],
            "rank_decay": str(decay),
            "quality_contribution": str(contribution),
        }
        team_quality_components.append(component)
        calc_materials.append(
            {
                "obj_src_id": item["obj_src_id"],
                "emp_obj_id": item.get("emp_obj_id"),
                "obj_id": item.get("obj_id"),
                "obj_key": item["obj_key"],
                "obj_name": item["obj_name"],
                "side": "positive",
                "raw_score": str(contribution),
                "abs_score": str(contribution),
                "factor_values": {
                    "talent_quality_factor": str(item["talent_quality_factor"]),
                    "rank_decay": str(decay),
                },
                "factor_refs": {
                    "talent_quality_factor": item["talent_quality_ref"],
                },
                "team_quality_included": True,
                "team_quality_rank": index + 1,
            }
        )

    if positive_object_scores:
        positive_quality_signal = signed_side_signal([score for score in positive_object_scores.values() if score > 0])
        negative_quality_signal = signed_side_signal([score for score in positive_object_scores.values() if score < 0])
        team_quality_signal = quant(positive_quality_signal - negative_quality_signal)
    else:
        positive_quality_signal = Decimal("0.000")
        negative_quality_signal = Decimal("0.000")
        team_quality_signal = Decimal("0.000")
    team_effect_signal = quant(team_quality_signal * complementarity_value * stability_value)
    positive_signal = max(team_effect_signal, Decimal("0.000"))
    team_negative_signal = abs(min(team_effect_signal, Decimal("0.000")))

    negative_grouped: dict[str, list[Decimal]] = defaultdict(list)
    for material in negative_materials:
        negative_grouped[material.obj_key].append(material.abs_score)
    negative_object_scores = {obj_key: object_side_score(scores) for obj_key, scores in negative_grouped.items()}
    coverage_value = row.get("coverage", {})
    if coverage_value is None:
        coverage_value = {}
    if not isinstance(coverage_value, dict):
        raise I5BFactorRecalculatorError(f"{path}.coverage: expected object")
    negative_coverage = decimal_value(coverage_value.get("negative", "1.0"), path=f"{path}.coverage.negative")
    explicit_negative_signal = side_signal(list(negative_object_scores.values()), negative_coverage)
    negative_signal = quant(team_negative_signal + explicit_negative_signal)

    explicit_material_ids = optional_int_tuple(row.get("material_ids"), path=f"{path}.material_ids")
    scored_material_ids = tuple(
        material["obj_src_id"] for material in calc_materials if isinstance(material.get("obj_src_id"), int)
    )
    material_ids = tuple(dict.fromkeys((*explicit_material_ids, *scored_material_ids)))
    supporting_material_ids = [material_id for material_id in material_ids if material_id not in scored_material_ids]

    detail = {
        "item_code": item_code,
        "formula_code": formula_code,
        "team_formula": "(sqrt(sum(positive_weighted_i^2)) - sqrt(sum(abs(negative_weighted_i)^2))) * role_complementarity_factor * long_term_stability_factor",
        "materials": calc_materials,
        "team_quality_components": team_quality_components,
        "positive_quality_signal": str(positive_quality_signal),
        "negative_quality_signal": str(negative_quality_signal),
        "team_quality_signal": str(team_quality_signal),
        "team_effect_signal": str(team_effect_signal),
        "team_negative_signal": str(team_negative_signal),
        "explicit_negative_signal": str(explicit_negative_signal),
        "team_factors": {
            "factor_values": {
                "role_complementarity_factor": str(complementarity_value),
                "long_term_stability_factor": str(stability_value),
            },
            "factor_refs": {
                "role_complementarity_factor": complementarity_ref,
                "long_term_stability_factor": stability_ref,
            },
        },
        "object_side_scores": {
            "positive": {obj_key: str(score) for obj_key, score in positive_object_scores.items()},
            "negative": {obj_key: str(score) for obj_key, score in negative_object_scores.items()},
        },
        "coverage": {"positive": "1.0", "negative": str(negative_coverage)},
        "covered_material_ids": list(material_ids),
        "scored_material_ids": list(scored_material_ids),
        "positive_signal": str(positive_signal),
        "negative_signal": str(negative_signal),
        "supporting_material_ids": supporting_material_ids,
    }
    return ClusterInput(
        emperor=require_text(row, "emperor", path),
        rule_code=TEAM_BUILDING_RULE_CODE,
        positive_signal=positive_signal,
        negative_signal=negative_signal,
        formula_code=str(row.get("formula_code") or formula_code),
        note=require_text(row, "note", path),
        material_ids=material_ids,
        calc_note=str(row.get("calc_note") or "team_quality_aggregate_recalculation"),
        calc_detail=detail,
    )


def load_profile_raw(
    raw: dict[str, Any],
    *,
    factor_docs: tuple[Path, ...],
    source_name: str = "profile",
) -> tuple[str, str, tuple[ClusterInput, ...]]:
    if not isinstance(raw, dict):
        raise I5BFactorRecalculatorError(f"{source_name}: expected object")
    item_code = str(raw.get("item_code") or DEFAULT_ITEM_CODE)
    formula_code = str(raw.get("formula_code") or DEFAULT_CLUSTER_FORMULA)
    profile_docs = tuple(ROOT / p if not Path(p).is_absolute() else Path(p) for p in raw.get("factor_docs", []))
    catalog = parse_factor_catalog(profile_docs or factor_docs)
    clusters_value = raw.get("clusters")
    if not isinstance(clusters_value, list) or not clusters_value:
        raise I5BFactorRecalculatorError(f"{source_name}.clusters: expected non-empty list")
    clusters = tuple(
        compute_cluster(
            cluster,
            item_code=item_code,
            formula_code=formula_code,
            catalog=catalog,
            path=f"{source_name}.clusters[{index}]",
        )
        for index, cluster in enumerate(clusters_value)
        if isinstance(cluster, dict)
    )
    if len(clusters) != len(clusters_value):
        raise I5BFactorRecalculatorError(f"{source_name}.clusters: every item must be an object")
    return item_code, formula_code, clusters


def load_profile(path: Path, *, factor_docs: tuple[Path, ...]) -> tuple[str, str, tuple[ClusterInput, ...]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return load_profile_raw(raw, factor_docs=factor_docs)


def material_profile_from_calc_detail(row: dict[str, Any], *, path: str) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise I5BFactorRecalculatorError(f"{path}: expected object")
    factor_refs = row.get("factor_refs")
    if not isinstance(factor_refs, dict) or not factor_refs:
        raise I5BFactorRecalculatorError(f"{path}.factor_refs: expected non-empty object")
    side = row.get("side")
    if side not in {"positive", "negative"}:
        raise I5BFactorRecalculatorError(f"{path}.side: expected positive or negative")
    material: dict[str, Any] = {
        "obj_name": str(row.get("obj_name") or row.get("obj_key") or path),
        "direction": side,
        "factors": factor_refs,
    }
    obj_src_id = row.get("obj_src_id")
    if obj_src_id is not None:
        if not isinstance(obj_src_id, int):
            raise I5BFactorRecalculatorError(f"{path}.obj_src_id: expected integer")
        material["obj_src_id"] = obj_src_id
    obj_key = row.get("obj_key")
    if obj_key is not None:
        material["obj_key"] = str(obj_key)
    return material


def cluster_profile_from_calc_detail_row(row: dict[str, Any], *, path: str) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise I5BFactorRecalculatorError(f"{path}: expected object")
    calc_detail = row.get("calc_detail")
    if not isinstance(calc_detail, dict):
        raise I5BFactorRecalculatorError(f"{path}.calc_detail: expected object")
    materials_value = calc_detail.get("materials")
    if not isinstance(materials_value, list) or not materials_value:
        raise I5BFactorRecalculatorError(f"{path}.calc_detail.materials: expected non-empty list")
    coverage = calc_detail.get("coverage", {})
    if coverage is None:
        coverage = {}
    if not isinstance(coverage, dict):
        raise I5BFactorRecalculatorError(f"{path}.calc_detail.coverage: expected object")
    profile = {
        "emperor": require_text(row, "emperor", path),
        "rule_code": require_text(row, "rule_code", path),
        "formula_code": str(row.get("formula_code") or calc_detail.get("formula_code") or DEFAULT_CLUSTER_FORMULA),
        "note": str(row.get("note") or "replayed from evidence cluster calc_detail"),
        "calc_note": f"replay_calc_detail: {row.get('calc_note') or ''}".strip(),
        "material_ids": optional_int_tuple(row.get("material_ids"), path=f"{path}.material_ids"),
        "coverage": {
            "positive": str(coverage.get("positive", "1.0")),
            "negative": str(coverage.get("negative", "1.0")),
        },
        "materials": [
            material_profile_from_calc_detail(material, path=f"{path}.calc_detail.materials[{index}]")
            for index, material in enumerate(materials_value)
        ],
    }
    team_factors = calc_detail.get("team_factors")
    if profile["rule_code"] == TEAM_BUILDING_RULE_CODE and isinstance(team_factors, dict):
        factor_refs = team_factors.get("factor_refs")
        if isinstance(factor_refs, dict) and factor_refs:
            profile["team_factors"] = factor_refs
    return profile


def _team_building_obj_src_id(row: dict[str, Any]) -> int | None:
    obj_srcs = row.get("i5b_obj_srcs")
    if not isinstance(obj_srcs, list):
        return None
    for obj_src in obj_srcs:
        if not isinstance(obj_src, dict):
            continue
        if obj_src.get("rule_code") != TEAM_BUILDING_RULE_CODE:
            continue
        obj_src_id = obj_src.get("obj_src_id")
        if isinstance(obj_src_id, int):
            return obj_src_id
    return None


def team_building_materials_from_emp_objs(
    *,
    dsn: str,
    item_code: str,
    emperors: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    rows_by_emperor = fetch_emp_object_rows(
        dsn=dsn,
        item_code=item_code,
        rule_code=TEAM_BUILDING_RULE_CODE,
        emperors=emperors,
        obj_types=("person",),
        require_attrs=("talent_quality",),
    )
    materials_by_emperor: dict[str, list[dict[str, Any]]] = {}
    for emperor, rows in rows_by_emperor.items():
        materials: list[dict[str, Any]] = []
        for row in rows:
            talent_quality = attr_value(list(row.get("attrs") or []), "talent_quality")
            if not talent_quality:
                continue
            material: dict[str, Any] = {
                "obj_src_id": _team_building_obj_src_id(row),
                "emp_obj_id": row.get("emp_obj_id"),
                "obj_id": row.get("obj_id"),
                "obj_name": row.get("obj_name"),
                "direction": "positive",
                "factors": {
                    "talent_quality_factor": {
                        "label": talent_quality,
                    }
                },
            }
            if material["obj_src_id"] is None:
                material.pop("obj_src_id")
            materials.append(material)
        materials_by_emperor[emperor] = materials
    return materials_by_emperor


def apply_team_building_emp_obj_materials(
    profiles: list[dict[str, Any]],
    *,
    dsn: str,
    item_code: str,
) -> None:
    emperors = tuple(
        dict.fromkeys(
            profile["emperor"]
            for profile in profiles
            if profile.get("rule_code") == TEAM_BUILDING_RULE_CODE and isinstance(profile.get("emperor"), str)
        )
    )
    if not emperors:
        return
    materials_by_emperor = team_building_materials_from_emp_objs(
        dsn=dsn,
        item_code=item_code,
        emperors=emperors,
    )
    for profile in profiles:
        if profile.get("rule_code") != TEAM_BUILDING_RULE_CODE:
            continue
        materials = materials_by_emperor.get(str(profile.get("emperor")), [])
        if not materials:
            raise I5BFactorRecalculatorError(
                f"{profile.get('emperor')}/{TEAM_BUILDING_RULE_CODE}: no emp_objs with talent_quality found"
            )
        profile["materials"] = materials
        profile["calc_note"] = "team_building_materials_from_emp_objs"


def load_profile_from_details(
    *,
    dsn: str,
    item_code: str,
    factor_docs: tuple[Path, ...],
    formula_code: str = DEFAULT_CLUSTER_FORMULA,
    emperors: tuple[str, ...] = (),
    rule_codes: tuple[str, ...] = (),
) -> tuple[str, str, tuple[ClusterInput, ...]]:
    latest = fetch_cluster_calc_detail_rows(
        dsn=dsn,
        item_code=item_code,
        formula_code=formula_code,
        emperors=emperors,
        rule_codes=rule_codes,
    )

    if not latest:
        raise I5BFactorRecalculatorError(f"evd_cluster_calc_details: no rows found for {formula_code}")
    profiles = [
        cluster_profile_from_calc_detail_row(row, path=f"evd_cluster_calc_details:{index}")
        for index, row in enumerate(latest.values())
    ]
    apply_team_building_emp_obj_materials(
        profiles,
        dsn=dsn,
        item_code=item_code,
    )
    raw = {
        "item_code": item_code,
        "formula_code": formula_code,
        "clusters": profiles,
    }
    return load_profile_raw(raw, factor_docs=factor_docs, source_name="calc_details")


def summarize_from_clusters(clusters: tuple[ClusterInput, ...]) -> list[dict[str, Any]]:
    by_emperor: dict[str, dict[str, RuleSignals]] = defaultdict(dict)
    for cluster in clusters:
        by_emperor[cluster.emperor][cluster.rule_code] = RuleSignals(
            positive_signal=cluster.positive_signal,
            negative_signal=cluster.negative_signal,
        )
    rows: list[dict[str, Any]] = []
    for emperor, signals in by_emperor.items():
        formula = calculate_formula(signals=signals)
        rows.append(
            {
                "emperor": emperor,
                "score": formula["score"],
                "score_rate": formula["score_rate"],
                "tier": formula["tier"],
                "tier_band": formula["tier_band"],
                "base_core": formula["base_core"],
            }
        )
    return rows


def clusters_payload(item_code: str, formula_code: str, clusters: tuple[ClusterInput, ...]) -> dict[str, Any]:
    return {
        "item_code": item_code,
        "formula_code": formula_code,
        "clusters": [
            {
                "emperor": cluster.emperor,
                "rule_code": cluster.rule_code,
                "positive_signal": str(cluster.positive_signal),
                "negative_signal": str(cluster.negative_signal),
                "note": render_cluster_note(cluster),
                "material_ids": list(cluster.material_ids),
                "calc_note": cluster.calc_note,
                "calc_detail": cluster.calc_detail,
            }
            for cluster in clusters
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recalculate I5B evidence clusters from structured material factors.")
    parser.add_argument("--input", type=Path, default=None, help="Structured UTF-8 JSON factor profile.")
    parser.add_argument("--from-details", action="store_true", help="Replay latest calc_detail rows from DB detail table.")
    parser.add_argument("--factor-doc", type=Path, action="append", default=None, help="Markdown doc containing factor tables.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code for --from-details.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Evidence cluster formula_code to replay.")
    parser.add_argument("--emperor", action="append", default=None, help="Optional emperor filter; repeatable.")
    parser.add_argument("--rule-code", action="append", default=None, help="Optional rule_code filter; repeatable.")
    parser.add_argument("--output", type=Path, default=None, help="Optional computed cluster payload JSON path.")
    parser.add_argument("--write-clusters", action="store_true", help="Upsert computed evd_clusters.")
    parser.add_argument("--write-results", action="store_true", help="Recalculate emp_item_results after cluster writes.")
    parser.add_argument("--dry-run", action="store_true", help="Rollback database writes; still prints in-memory result summary.")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN", help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument(
        "--allow-partial-material-coverage",
        action="store_true",
        help="Allow replay/upsert to omit DB obj_srcs from material_ids or calc_detail.materials.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source_count = sum(1 for enabled in (bool(args.input), bool(args.from_details)) if enabled)
    if source_count != 1:
        parser.error("exactly one of --input or --from-details is required")
    factor_docs = tuple(args.factor_doc) if args.factor_doc else DEFAULT_FACTOR_DOCS
    dsn: str | None = None
    if args.from_details:
        dsn = resolve_dsn(args.dsn_env)
        item_code, formula_code, clusters = load_profile_from_details(
            dsn=dsn,
            item_code=args.item_code,
            factor_docs=factor_docs,
            formula_code=args.cluster_formula,
            emperors=tuple(args.emperor or ()),
            rule_codes=tuple(args.rule_code or ()),
        )
    else:
        item_code, formula_code, clusters = load_profile(args.input, factor_docs=factor_docs)
    payload = clusters_payload(item_code, formula_code, clusters)
    summary = summarize_from_clusters(clusters)
    factor_audit_summary: dict[str, Any] | None = None

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_report: dict[str, Any] | None = None
    if args.write_clusters or args.write_results:
        if dsn is None:
            dsn = resolve_dsn(args.dsn_env)
        try:
            factor_audit = build_audit_report_from_inputs(
                dsn=dsn,
                item_code=item_code,
                cluster_formula=formula_code,
                clusters=clusters,
            )
            assert_no_factor_consistency_errors(factor_audit)
        except I5BFactorConsistencyAuditError as exc:
            parser.error(str(exc))
        factor_audit_summary = {
            "ok": factor_audit["ok"],
            "error_count": factor_audit["error_count"],
            "warning_count": factor_audit["warning_count"],
        }
        if args.write_clusters:
            write_report = upsert_clusters(
                dsn=dsn,
                item_code=item_code,
                clusters=clusters,
                dry_run=args.dry_run,
                require_full_material_coverage=not args.allow_partial_material_coverage,
            )
        if args.write_results and not args.dry_run:
            write_item_results(
                dsn=dsn,
                emperors=tuple(dict.fromkeys(cluster.emperor for cluster in clusters)),
                item_code=item_code,
                cluster_formula=formula_code,
                formula_code=DEFAULT_FORMULA_CODE,
                dry_run=False,
            )

    print(
        json.dumps(
            {
                "dry_run": args.dry_run,
                "item_code": item_code,
                "cluster_formula": formula_code,
                "cluster_count": len(clusters),
                "summary": summary,
                "factor_consistency_audit": factor_audit_summary,
                "write_report": write_report,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
