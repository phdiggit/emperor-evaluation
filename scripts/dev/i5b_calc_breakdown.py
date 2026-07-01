from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import (  # noqa: E402
    DEFAULT_CLUSTER_FORMULA,
    DEFAULT_FORMULA_CODE,
    DEFAULT_ITEM_CODE,
    RULE_ORDER,
    fetch_item_result_calc_detail_rows,
)
from scripts.dev.evidence_cluster_workbench import (  # noqa: E402
    EvidenceClusterWorkbenchError,
    fetch_cluster_calc_detail_rows,
    resolve_dsn,
)


KEY_FACTOR_ORDER = (
    "talent_quality_factor",
    "trust_validity",
    "authorization_intensity",
    "result_feedback",
    "disposition_severity",
    "spillover_factor",
    "object_weight",
    "favoritism_intensity",
    "displacement_harm",
)

RULE_LABELS = {
    "talent_discovery": "发现人才",
    "appointment_trust": "任人信任",
    "delegation": "合理授权",
    "team_building": "建立团队",
    "tolerate_talent": "容人保全",
    "anti_nepotism": "避免任人唯亲",
}

FACTOR_LABELS = {
    "talent_quality_factor": "人才质量",
    "trust_validity": "信任合理性",
    "authorization_intensity": "授权强度",
    "result_feedback": "结果反馈",
    "disposition_severity": "处置严重度",
    "spillover_factor": "外溢影响",
    "object_weight": "对象权重",
    "favoritism_intensity": "亲私强度",
    "displacement_harm": "排挤损害",
}


class I5BCalcBreakdownError(ValueError):
    pass


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _factor_label(ref: Any) -> str:
    if isinstance(ref, dict):
        return _text(ref.get("label") or ref.get("code") or ref.get("value"))
    return _text(ref)


def rule_label(rule_code: str) -> str:
    return RULE_LABELS.get(rule_code, rule_code)


def rule_display(rule: dict[str, Any]) -> str:
    code = str(rule["rule_code"])
    label = str(rule.get("rule_label") or rule_label(code))
    if label == code:
        return code
    return f"{label} (`{code}`)"


def factor_brief(material: dict[str, Any]) -> str:
    refs = material.get("factor_refs") or {}
    values = material.get("factor_values") or {}
    if not isinstance(refs, dict) or not isinstance(values, dict):
        return ""
    parts: list[str] = []
    for key in KEY_FACTOR_ORDER:
        if key not in refs and key not in values:
            continue
        label = _factor_label(refs.get(key)) or "-"
        value = values.get(key)
        display_key = FACTOR_LABELS.get(key, key)
        if value is None:
            parts.append(f"{display_key}={label}")
        else:
            parts.append(f"{display_key}={label}:{value}")
    return "; ".join(parts)


def material_brief(material: dict[str, Any]) -> str:
    obj_name = material.get("obj_name") or material.get("object_name") or material.get("obj_key") or "UNKNOWN"
    obj_src_id = material.get("obj_src_id")
    suffix = f"#{obj_src_id}" if obj_src_id is not None else ""
    return f"{obj_name}{suffix}({_text(material.get('raw_score'))}/{_text(material.get('abs_score'))})"


def normalize_material(material: dict[str, Any]) -> dict[str, Any]:
    return {
        "obj_src_id": material.get("obj_src_id"),
        "obj_key": material.get("obj_key"),
        "obj_name": material.get("obj_name") or material.get("object_name") or material.get("obj_key"),
        "side": material.get("side"),
        "raw_score": material.get("raw_score"),
        "abs_score": material.get("abs_score"),
        "factor_values": material.get("factor_values") or {},
        "factor_refs": material.get("factor_refs") or {},
        "brief": material_brief(material),
        "factor_brief": factor_brief(material),
    }


def normalize_cluster(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    detail = row.get("calc_detail") or {}
    if not isinstance(detail, dict):
        detail = {}
    grouped = {"positive": [], "negative": []}
    materials = detail.get("materials") or []
    if isinstance(materials, list):
        for material in materials:
            if not isinstance(material, dict):
                continue
            normalized = normalize_material(material)
            side = normalized.get("side")
            if side in grouped:
                grouped[side].append(normalized)
    return {
        "cluster_id": row.get("cluster_id"),
        "rule_code": row.get("rule_code"),
        "positive_signal": row.get("positive_signal"),
        "negative_signal": row.get("negative_signal"),
        "cluster_direction": row.get("cluster_direction"),
        "coverage": detail.get("coverage"),
        "object_side_scores": detail.get("object_side_scores"),
        "covered_material_ids": detail.get("covered_material_ids") or row.get("material_ids") or [],
        "scored_material_ids": detail.get("scored_material_ids") or [
            material.get("obj_src_id") for material in materials if isinstance(material, dict)
        ],
        "supporting_material_ids": detail.get("supporting_material_ids") or [],
        "materials": grouped,
    }


def ordered_rule_codes(result_row: dict[str, Any]) -> list[str]:
    rules = result_row.get("rules") or {}
    if not isinstance(rules, dict):
        return []
    known = [rule for rule in RULE_ORDER if rule in rules]
    extra = sorted(rule for rule in rules if rule not in known)
    return known + extra


def build_breakdown_report(
    *,
    emperors: tuple[str, ...],
    dsn: str | None = None,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    result_formula: str = DEFAULT_FORMULA_CODE,
    rule_codes: tuple[str, ...] = (),
    result_rows: dict[str, dict[str, Any]] | None = None,
    cluster_rows: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not emperors:
        raise I5BCalcBreakdownError("at least one emperor is required")

    if result_rows is None or cluster_rows is None:
        if dsn is None:
            raise I5BCalcBreakdownError("dsn is required when rows are not supplied")
        result_rows = fetch_item_result_calc_detail_rows(
            dsn=dsn,
            item_code=item_code,
            cluster_formula=cluster_formula,
            formula_code=result_formula,
            emperors=emperors,
        )
        cluster_rows = fetch_cluster_calc_detail_rows(
            dsn=dsn,
            item_code=item_code,
            formula_code=cluster_formula,
            emperors=emperors,
            rule_codes=rule_codes,
        )

    missing_results = [emperor for emperor in emperors if emperor not in result_rows]
    if missing_results:
        raise I5BCalcBreakdownError(f"missing item result log rows: {', '.join(missing_results)}")

    emperor_reports: list[dict[str, Any]] = []
    warnings: list[str] = []
    rule_filter = set(rule_codes)
    for emperor in emperors:
        result_row = result_rows[emperor]
        rules = result_row.get("rules") or {}
        if not isinstance(rules, dict):
            raise I5BCalcBreakdownError(f"{emperor}: result row rules must be an object")
        rule_reports: list[dict[str, Any]] = []
        for rule_code in ordered_rule_codes(result_row):
            if rule_filter and rule_code not in rule_filter:
                continue
            rule_result = rules[rule_code]
            if not isinstance(rule_result, dict):
                raise I5BCalcBreakdownError(f"{emperor}.{rule_code}: rule result must be an object")
            cluster = normalize_cluster(cluster_rows.get((emperor, rule_code)))
            if cluster is None and not rule_result.get("no_material"):
                warnings.append(f"{emperor}.{rule_code}: missing replayable cluster calc_detail row")
            rule_reports.append(
                {
                    "rule_code": rule_code,
                    "rule_label": rule_label(rule_code),
                    "result": rule_result,
                    "cluster": cluster,
                }
            )
        emperor_reports.append(
            {
                "emperor": emperor,
                "score": result_row.get("score"),
                "tier": result_row.get("tier"),
                "tier_band": result_row.get("tier_band"),
                "base_core": result_row.get("base_core"),
                "score_rate": result_row.get("score_rate"),
                "positive_response_cap": result_row.get("positive_response_cap"),
                "positive_response_tau": result_row.get("positive_response_tau"),
                "negative_response_cap": result_row.get("negative_response_cap"),
                "negative_response_tau": result_row.get("negative_response_tau"),
                "rules": rule_reports,
            }
        )

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "postgres",
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "result_formula": result_formula,
        "emperors": emperor_reports,
        "warnings": warnings,
    }


def _join_materials(materials: list[dict[str, Any]]) -> str:
    if not materials:
        return "-"
    return "；".join(str(material["brief"]) for material in materials)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# I5B 计算拆解",
        "",
        f"- cluster_formula: `{report['cluster_formula']}`",
        f"- result_formula: `{report['result_formula']}`",
        "- 材料括号为 `raw_score/abs_score`；`abs_score` 已体现单条材料封顶。",
        "",
    ]
    if report.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")

    for emperor in report["emperors"]:
        tier = " ".join(part for part in [emperor.get("tier"), emperor.get("tier_band")] if part)
        lines.extend(
            [
                f"## {emperor['emperor']}",
                "",
                f"- score: `{emperor.get('score')}`；tier: `{tier}`；base_core: `{emperor.get('base_core')}`；score_rate: `{emperor.get('score_rate')}`",
                f"- response cap/tau: positive `{emperor.get('positive_response_cap')}/{emperor.get('positive_response_tau')}`；negative `{emperor.get('negative_response_cap')}/{emperor.get('negative_response_tau')}`",
                "",
                "| 指标 | 权重 | 正向信号 | 正向响应 | 负向信号 | 负向响应 | 净效应 |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for rule in emperor["rules"]:
            result = rule["result"]
            lines.append(
                "| {rule} | {weight} | {p_signal} | {p_effect} | {n_signal} | {n_effect} | {net} |".format(
                    rule=rule_display(rule),
                    weight=result.get("rule_weight"),
                    p_signal=result.get("positive_signal"),
                    p_effect=result.get("positive_effect"),
                    n_signal=result.get("negative_signal"),
                    n_effect=result.get("negative_effect"),
                    net=result.get("rule_net_effect"),
                )
            )
        lines.extend(
            [
                "",
                "| 指标 | 证据簇正/负 | 计分/覆盖/补源 | 正向具体对象 | 负向具体对象 |",
                "|---|---:|---|---|---|",
            ]
        )
        for rule in emperor["rules"]:
            cluster = rule.get("cluster")
            if cluster is None:
                lines.append(f"| {rule_display(rule)} | - | - | - | - |")
                continue
            materials = cluster["materials"]
            lines.append(
                "| {rule} | {p}/{n} | {ids} | {pos} | {neg} |".format(
                    rule=rule_display(rule),
                    p=cluster.get("positive_signal"),
                    n=cluster.get("negative_signal"),
                    ids=(
                        f"{cluster.get('scored_material_ids')}"
                        f"/{cluster.get('covered_material_ids')}"
                        f"/{cluster.get('supporting_material_ids')}"
                    ),
                    pos=_join_materials(materials["positive"]),
                    neg=_join_materials(materials["negative"]),
                )
            )
        lines.extend(["", "### 关键负向材料因子", ""])
        has_negative = False
        for rule in emperor["rules"]:
            cluster = rule.get("cluster")
            if cluster is None:
                continue
            negatives = cluster["materials"]["negative"]
            if not negatives:
                continue
            has_negative = True
            lines.append(f"- {rule_display(rule)}:")
            for material in negatives:
                detail = f"：{material['factor_brief']}" if material.get("factor_brief") else ""
                lines.append(f"  - {material['brief']}{detail}")
        if not has_negative:
            lines.append("- 无")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_markdown(report), encoding="utf-8")
        return
    raise I5BCalcBreakdownError(f"unknown output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show I5B evidence-cluster and item-result calculations from DB detail tables.")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN", help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code.")
    parser.add_argument("--emperor", action="append", required=True, help="Emperor name; repeat for multiple people.")
    parser.add_argument("--rule-code", action="append", default=None, help="Optional rule_code filter; repeatable.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Evidence cluster formula_code.")
    parser.add_argument("--result-formula", default=DEFAULT_FORMULA_CODE, help="Item result formula_code.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown", help="Output format.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output path. Without it, write report to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = build_breakdown_report(
            emperors=tuple(args.emperor),
            dsn=resolve_dsn(args.dsn_env),
            item_code=args.item_code,
            cluster_formula=args.cluster_formula,
            result_formula=args.result_formula,
            rule_codes=tuple(args.rule_code or ()),
        )
    except (EvidenceClusterWorkbenchError, I5BCalcBreakdownError) as exc:
        parser.error(str(exc))

    if args.output:
        write_report(args.output, report, output_format=args.format)
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "format": args.format,
                    "emperors": [row["emperor"] for row in report["emperors"]],
                    "warnings": report["warnings"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
