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


def fetch_base_rule_signals(cur: Any, *, emperor: str, item_code: str, cluster_formula: str) -> dict[str, RuleSignals]:
    cur.execute(
        """
        select er.rule_code, ec.id, ec.positive_signal, ec.negative_signal
          from public.eval_rules er
          join public.eval_items i on i.id = er.item_id
          left join public.evd_clusters ec on ec.rule_id = er.id
           and ec.emp_id = (select id from public.emps where name = %s)
           and ec.item_id = i.id and ec.formula_code = %s
         where i.item_code = %s
        """,
        (emperor, cluster_formula, item_code),
    )
    return {
        str(rule): RuleSignals(Decimal(str(positive or 0)), Decimal(str(negative or 0)), int(cluster_id) if cluster_id else None)
        for rule, cluster_id, positive, negative in cur.fetchall()
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
                signals = fetch_base_rule_signals(
                    raw_cur, emperor=emperor, item_code=item_code, cluster_formula=cluster_formula)
                appointment, lineage = fetch_v3_appointment_signal(
                    v3_cur, emperor=emperor, item_code=item_code, formula_code=cluster_formula)
                signals["appointment_delegation"] = appointment
                formula = calculate_formula(signals=signals)
                rows.append({
                    "emperor": emperor, "item_code": item_code, "formula_code": formula_code,
                    "cluster_formula": cluster_formula, **formula,
                    "appointment_delegation_source": "retrieval_v3.target_rule_score_clusters",
                    "appointment_delegation_lineage": lineage,
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
        "> appointment_delegation 使用 retrieval_v3 最新正式 cluster；其余 rule 使用现有公共证据簇。",
        "> 本报告只产出 weighted_raw_signal；最终 0–45 分和档位仍需批量动态映射。", "",
        "| 皇帝 | weighted raw signal | appointment + | appointment - | appointment net |", "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("results") or []:
        rule = row["rules"]["appointment_delegation"]
        lines.append(
            f"| {row['emperor']} | {row['weighted_raw_signal']} | {rule['positive_signal']} | "
            f"{rule['negative_signal']} | {rule['rule_raw_net']} |")
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
