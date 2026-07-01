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
    DEFAULT_LOG_PATH as DEFAULT_CLUSTER_LOG_PATH,
    ClusterInput,
    resolve_dsn,
    upsert_clusters,
)
from scripts.dev.i5b_calc_logs import latest_cluster_log_rows


DEFAULT_ITEM_CODE = "I5B"
DEFAULT_CLUSTER_FORMULA = "evidence_cluster_signal_v2"
DEFAULT_FACTOR_DOCS = (
    ROOT / "docs" / "\u5206\u9879\u89c4\u5219" / "\u7b2c\u4e94\u9879\u7edf\u6cbb\u8005\u653f\u6cbb\u7d20\u8d28" / "B\u7528\u4eba\u4e0e\u6388\u6743.md",
    ROOT / "docs" / "\u8bc1\u636e\u89c4\u5219" / "\u8bc1\u636e\u7c07\u8ba1\u7b97\u516c\u5f0f.md",
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
    for row in catalog[factor_name]:
        current = normalize_label(row.label)
        if wanted == current or wanted in current or current in wanted:
            return row.value
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


def cluster_profile_from_log_row(row: dict[str, Any], *, path: str) -> dict[str, Any]:
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
    return {
        "emperor": require_text(row, "emperor", path),
        "rule_code": require_text(row, "rule_code", path),
        "formula_code": str(row.get("formula_code") or calc_detail.get("formula_code") or DEFAULT_CLUSTER_FORMULA),
        "note": str(row.get("note") or "replayed from evidence cluster calc_detail log"),
        "calc_note": f"replay_calc_detail_log: {row.get('calc_note') or ''}".strip(),
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


def load_profile_from_log(
    path: Path,
    *,
    factor_docs: tuple[Path, ...],
    formula_code: str = DEFAULT_CLUSTER_FORMULA,
    emperors: tuple[str, ...] = (),
    rule_codes: tuple[str, ...] = (),
) -> tuple[str, str, tuple[ClusterInput, ...]]:
    latest = latest_cluster_log_rows(
        path,
        formula_code=formula_code,
        emperors=emperors,
        rule_codes=rule_codes,
        require_calc_detail=True,
    )

    if not latest:
        raise I5BFactorRecalculatorError(f"{path}: no replayable calc_detail rows found for {formula_code}")
    profiles = [
        cluster_profile_from_log_row(row, path=f"{path}:{index}")
        for index, row in enumerate(latest.values())
    ]
    item_code = str(
        next(
            (
                row.get("calc_detail", {}).get("item_code")
                for row in latest.values()
                if isinstance(row.get("calc_detail"), dict) and row.get("calc_detail", {}).get("item_code")
            ),
            DEFAULT_ITEM_CODE,
        )
    )
    raw = {
        "item_code": item_code,
        "formula_code": formula_code,
        "clusters": profiles,
    }
    return load_profile_raw(raw, factor_docs=factor_docs, source_name="calc_log")


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
                "note": cluster.note,
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
    parser.add_argument("--from-log", type=Path, default=None, help="Replay latest calc_detail rows from an evidence cluster JSONL log.")
    parser.add_argument("--factor-doc", type=Path, action="append", default=None, help="Markdown doc containing factor tables.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Evidence cluster formula_code to replay from log.")
    parser.add_argument("--emperor", action="append", default=None, help="Optional emperor filter for --from-log; repeatable.")
    parser.add_argument("--rule-code", action="append", default=None, help="Optional rule_code filter for --from-log; repeatable.")
    parser.add_argument("--output", type=Path, default=None, help="Optional computed cluster payload JSON path.")
    parser.add_argument("--write-clusters", action="store_true", help="Upsert computed evd_clusters.")
    parser.add_argument("--write-results", action="store_true", help="Recalculate emp_item_results after cluster writes.")
    parser.add_argument("--dry-run", action="store_true", help="Rollback database writes; still prints in-memory result summary.")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN", help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--cluster-log", type=Path, default=DEFAULT_CLUSTER_LOG_PATH, help="Cluster JSONL calculation log path.")
    parser.add_argument(
        "--allow-partial-material-coverage",
        action="store_true",
        help="Allow replay/upsert to omit DB obj_srcs from material_ids or calc_detail.materials.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if bool(args.input) == bool(args.from_log):
        parser.error("exactly one of --input or --from-log is required")
    factor_docs = tuple(args.factor_doc) if args.factor_doc else DEFAULT_FACTOR_DOCS
    if args.from_log:
        item_code, formula_code, clusters = load_profile_from_log(
            args.from_log,
            factor_docs=factor_docs,
            formula_code=args.cluster_formula,
            emperors=tuple(args.emperor or ()),
            rule_codes=tuple(args.rule_code or ()),
        )
    else:
        item_code, formula_code, clusters = load_profile(args.input, factor_docs=factor_docs)
    payload = clusters_payload(item_code, formula_code, clusters)
    summary = summarize_from_clusters(clusters)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_report: dict[str, Any] | None = None
    if args.write_clusters or args.write_results:
        dsn = resolve_dsn(args.dsn_env)
        if args.write_clusters:
            write_report = upsert_clusters(
                dsn=dsn,
                item_code=item_code,
                clusters=clusters,
                dry_run=args.dry_run,
                log_path=args.cluster_log,
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
