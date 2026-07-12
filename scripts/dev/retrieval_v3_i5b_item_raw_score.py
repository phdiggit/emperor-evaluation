from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import (  # noqa: E402
    DEFAULT_CLUSTER_FORMULA,
    DEFAULT_FORMULA_CODE,
    DEFAULT_ITEM_CODE,
    RuleSignals,
    RULE_ORDER,
    calculate_formula,
)
from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


def fetch_v3_appointment_signal(
    cur: Any, *, emperor: str, item_code: str, formula_code: str
) -> tuple[RuleSignals, dict[str, Any]]:
    cur.execute(
        """
        select c.id, c.rule_score_code, c.positive_signal, c.negative_signal,
               c.scored_judgment_count, c.updated_at, rt.target_code
          from retrieval_v3.target_rule_score_clusters c
          join retrieval_v3.retrieval_targets rt on rt.id = c.target_id
         where rt.emperor_name = %s and c.item_code = %s
           and c.rule_code = 'appointment_delegation' and c.formula_code = %s
           and c.review_status::text = 'accepted'
         order by c.updated_at desc, c.id desc
         limit 1
        """,
        (emperor, item_code, formula_code),
    )
    raw = cur.fetchone()
    if raw is None:
        raise ValueError(f"missing v3 appointment_delegation score cluster: {emperor}")
    keys = ("id", "rule_score_code", "positive_signal", "negative_signal", "scored_judgment_count", "updated_at", "target_code")
    payload = dict(zip(keys, raw))
    signal = RuleSignals(
        Decimal(str(payload["positive_signal"])), Decimal(str(payload["negative_signal"])), int(payload["id"]))
    return signal, payload


def fetch_v3_rule_signals(cur: Any, *, emperor: str, item_code: str, cluster_formula: str) -> dict[str, RuleSignals]:
    rows = fetch_v3_rule_cluster_rows(
        cur, emperor=emperor, item_code=item_code, cluster_formula=cluster_formula
    )
    return {
        rule: RuleSignals(
            Decimal(str(payload["positive_signal"] or 0)),
            Decimal(str(payload["negative_signal"] or 0)),
            int(payload["id"]) if payload["id"] else None,
        )
        for rule, payload in rows.items()
    }


def fetch_v3_rule_cluster_rows(
    cur: Any, *, emperor: str, item_code: str, cluster_formula: str
) -> dict[str, dict[str, Any]]:
    cur.execute(
        """
        select distinct on (c.rule_code)
               c.rule_code, c.id, c.rule_score_code, c.positive_signal, c.negative_signal,
               c.scored_judgment_count, c.updated_at, rt.target_code, c.calc_detail
          from retrieval_v3.target_rule_score_clusters c
          join retrieval_v3.retrieval_targets rt on rt.id = c.target_id
         where rt.emperor_name = %s
           and c.formula_code = %s
           and c.item_code = %s
           and c.review_status::text = 'accepted'
         order by c.rule_code, c.updated_at desc, c.id desc
        """,
        (emperor, cluster_formula, item_code),
    )
    return {
        str(rule): {
            "id": cluster_id,
            "rule_score_code": rule_score_code,
            "positive_signal": positive,
            "negative_signal": negative,
            "scored_judgment_count": scored_judgment_count,
            "updated_at": updated_at,
            "target_code": target_code,
            "calc_detail": calc_detail or {},
        }
        for rule, cluster_id, rule_score_code, positive, negative, scored_judgment_count, updated_at, target_code, calc_detail
        in cur.fetchall()
    }


def calculate_v3_raw_scores(
    *, dsn: str, schema_name: str, emperors: Sequence[str], item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA, formula_code: str = DEFAULT_FORMULA_CODE,
) -> dict[str, Any]:
    if not emperors:
        raise ValueError("at least one emperor is required")
    psycopg, _ = import_psycopg(); rows: list[dict[str, Any]] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as raw_cur:
            v3_cur = schema_cursor(raw_cur, schema_name=schema_name)
            for emperor in emperors:
                cluster_rows = fetch_v3_rule_cluster_rows(
                    v3_cur, emperor=emperor, item_code=item_code, cluster_formula=cluster_formula)
                signals = {
                    rule: RuleSignals(
                        Decimal(str(payload["positive_signal"] or 0)),
                        Decimal(str(payload["negative_signal"] or 0)),
                        int(payload["id"]) if payload["id"] else None,
                    )
                    for rule, payload in cluster_rows.items()
                }
                appointment, lineage = fetch_v3_appointment_signal(
                    v3_cur, emperor=emperor, item_code=item_code, formula_code=cluster_formula)
                signals["appointment_delegation"] = appointment
                cluster_rows["appointment_delegation"] = lineage
                formula = calculate_formula(signals=signals)
                missing_rule_codes = [rule for rule in RULE_ORDER if rule not in signals]
                rows.append({
                    "emperor": emperor, "item_code": item_code, "formula_code": formula_code,
                    "cluster_formula": cluster_formula, **formula,
                    "appointment_delegation_source": "retrieval_v3.target_rule_score_clusters",
                    "appointment_delegation_lineage": lineage,
                    "rule_cluster_lineage": cluster_rows,
                    "complete_rule_coverage": not missing_rule_codes,
                    "missing_rule_codes": missing_rule_codes,
                })
        conn.rollback()
    return {
        "ok": True, "mode": "v3_item_raw_signal_only", "write_db": False,
        "dynamic_mapping_required": True, "final_score_generated": False,
        "results": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# I5B 三人最新原始分值报告", "",
        "> 所有 rule 只读取 retrieval_v3 正式 cluster；缺失 rule 会显式列出，不再回读 public 旧表。",
        "> 本报告只产出 weighted_raw_signal；最终 0–45 分和档位仍需批量动态映射。", "",
        "| 皇帝 | weighted raw signal | 规则覆盖 |", "| --- | ---: | --- |",
    ]
    for row in report.get("results") or []:
        coverage = "完整" if row.get("complete_rule_coverage", not row.get("missing_rule_codes")) else "缺失"
        lines.append(f"| {row['emperor']} | {row['weighted_raw_signal']} | {coverage} |")
    for row in report.get("results") or []:
        lines.extend([
            "", f"## {row['emperor']}", "",
            "| rule | cluster | judgments | positive | negative | net | weight | weighted contribution |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        lineage = row.get("rule_cluster_lineage") or {}
        contributions: list[str] = []
        for rule_code in RULE_ORDER:
            rule = row["rules"][rule_code]
            cluster = lineage.get(rule_code) or {}
            lines.append(
                f"| {rule_code} | {rule.get('cluster_id') or '—'} | "
                f"{cluster.get('scored_judgment_count') if cluster.get('scored_judgment_count') is not None else '—'} | "
                f"{rule['positive_signal']} | {rule['negative_signal']} | {rule['rule_raw_net']} | "
                f"{rule['rule_weight']} | {rule['weighted_raw_signal']} |"
            )
            contributions.append(rule["weighted_raw_signal"])
        lines.extend([
            "", "计算式：",
            "",
            f"`{' + '.join(contributions)} = {row['weighted_raw_signal']}`",
            "", "规则簇来源：", "",
        ])
        for rule_code in RULE_ORDER:
            cluster = lineage.get(rule_code)
            if not cluster:
                lines.append(f"- `{rule_code}`：无正式 cluster")
                continue
            lines.append(
                f"- `{rule_code}`：`{cluster.get('rule_score_code')}`，cluster_id={cluster.get('id')}，"
                f"target=`{cluster.get('target_code')}`，updated_at={cluster.get('updated_at')}"
            )
        lines.extend(["", "### 入分材料明细", ""])
        for rule_code in RULE_ORDER:
            cluster = lineage.get(rule_code) or {}
            materials = (cluster.get("calc_detail") or {}).get("materials") or []
            lines.extend([
                f"#### {rule_code}", "",
                "| object | claim | event groups | side | raw score | factors |",
                "| --- | --- | --- | --- | ---: | --- |",
            ])
            if not materials:
                lines.append("| — | — | — | — | 0.000 | 无可用入分材料 |")
                lines.append("")
                continue
            for material in materials:
                factor_values = material.get("factor_values") or {}
                factors = "; ".join(f"{key}={value}" for key, value in sorted(factor_values.items()))
                event_groups = ", ".join(material.get("event_group_keys") or []) or "—"
                lines.append(
                    f"| {material.get('object_name') or '—'} | `{material.get('claim_key') or '—'}` | "
                    f"{event_groups} | {material.get('side') or material.get('judgment_side') or '—'} | "
                    f"{material.get('raw_score') or material.get('abs_score') or '0.000'} | {factors or '—'} |"
                )
            lines.append("")
    missing_rows = [row for row in report.get("results") or [] if row.get("missing_rule_codes")]
    if missing_rows:
        lines.extend(["", "## 尚未生成的 v3 rule cluster", ""])
    for row in missing_rows:
        if row.get("missing_rule_codes"):
            lines.append(f"- {row['emperor']}: `{', '.join(row['missing_rule_codes'])}`")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build I5B raw item signals with v3 appointment score clusters.")
    parser.add_argument("--env-file", type=Path); parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA); parser.add_argument("--emperor", action="append", required=True)
    parser.add_argument("--output-json", type=Path, required=True); parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    report = calculate_v3_raw_scores(
        dsn=resolve_dsn(args.dsn_env),
        schema_name=args.pg_schema, emperors=args.emperor)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": True, "results": len(report["results"]), "output_json": str(args.output_json)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
