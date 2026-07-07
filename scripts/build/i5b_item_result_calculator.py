from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import psycopg


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DSN_ENV = "EMPEROR_EVAL_PG_DSN"
DEFAULT_ITEM_CODE = "I5B"
DEFAULT_CLUSTER_FORMULA = "evidence_cluster_signal_v3"
DEFAULT_FORMULA_CODE = "item_raw_signal_i5b_v1"
MAX_SCORE = Decimal("45.000")

RULE_ORDER = (
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
)
RULE_WEIGHTS = {
    "talent_discovery": Decimal("0.19"),
    "appointment_delegation": Decimal("0.36"),
    "team_building": Decimal("0.21"),
    "tolerate_talent": Decimal("0.18"),
    "anti_nepotism": Decimal("0.06"),
}


class I5BItemResultError(ValueError):
    pass


@dataclass(frozen=True)
class RuleSignals:
    positive_signal: Decimal
    negative_signal: Decimal
    cluster_id: int | None = None


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def resolve_dsn(env_name: str) -> str:
    if os.environ.get(env_name):
        return str(os.environ[env_name])
    env = load_env()
    if env_name not in env:
        raise I5BItemResultError(f"missing PostgreSQL DSN env var {env_name}")
    return env[env_name]


def quant(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _zero_signals() -> dict[str, RuleSignals]:
    return {rule: RuleSignals(Decimal("0.000"), Decimal("0.000")) for rule in RULE_ORDER}


def calculate_formula(
    *,
    signals: dict[str, RuleSignals],
) -> dict[str, Any]:
    normalized = _zero_signals()
    normalized.update(signals)

    rule_inputs: dict[str, dict[str, str | bool | None]] = {}
    weighted_raw_signal = Decimal("0.000")

    for rule in RULE_ORDER:
        rule_signal = normalized[rule]
        rule_raw_net = quant(rule_signal.positive_signal - rule_signal.negative_signal, "0.001")
        rule_weighted_raw_signal = quant(RULE_WEIGHTS[rule] * rule_raw_net, "0.001")
        weighted_raw_signal += RULE_WEIGHTS[rule] * rule_raw_net

        rule_inputs[rule] = {
            "cluster_id": rule_signal.cluster_id,
            "no_material": rule_signal.cluster_id is None
            and rule_signal.positive_signal == 0
            and rule_signal.negative_signal == 0,
            "positive_signal": str(quant(rule_signal.positive_signal, "0.001")),
            "negative_signal": str(quant(rule_signal.negative_signal, "0.001")),
            "rule_raw_net": str(rule_raw_net),
            "rule_weight": str(quant(RULE_WEIGHTS[rule], "0.001")),
            "weighted_raw_signal": str(rule_weighted_raw_signal),
        }

    weighted_raw_signal = quant(weighted_raw_signal, "0.001")

    return {
        "formula_stage": "raw_signal_only",
        "dynamic_mapping_required": True,
        "max_score": str(MAX_SCORE),
        "rules": rule_inputs,
        "weighted_raw_signal": str(weighted_raw_signal),
        "score_rate": None,
        "score": None,
        "tier": None,
        "tier_band": None,
    }


def _fetch_item_id(cur: Any, item_code: str) -> int:
    cur.execute("select id from eval_items where item_code = %s", (item_code,))
    row = cur.fetchone()
    if row is None:
        raise I5BItemResultError(f"eval_items missing item_code: {item_code}")
    return int(row[0])


def _fetch_emp_id(cur: Any, emperor: str) -> int:
    cur.execute("select id from emps where name = %s", (emperor,))
    row = cur.fetchone()
    if row is None:
        raise I5BItemResultError(f"emps missing name: {emperor}")
    return int(row[0])


def _fetch_signals(cur: Any, *, emp_id: int, item_id: int, cluster_formula: str) -> dict[str, RuleSignals]:
    cur.execute(
        """
        select er.rule_code, ec.id, ec.positive_signal, ec.negative_signal
          from eval_rules er
          left join evd_clusters ec
            on ec.rule_id = er.id
           and ec.emp_id = %s
           and ec.item_id = %s
           and ec.formula_code = %s
         where er.item_id = %s
        """,
        (emp_id, item_id, cluster_formula, item_id),
    )
    signals: dict[str, RuleSignals] = {}
    for rule_code, cluster_id, positive_signal, negative_signal in cur.fetchall():
        signals[str(rule_code)] = RuleSignals(
            Decimal(str(positive_signal or 0)),
            Decimal(str(negative_signal or 0)),
            int(cluster_id) if cluster_id is not None else None,
        )
    return signals


def calculate_item_results(
    *,
    dsn: str,
    emperors: tuple[str, ...],
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    formula_code: str = DEFAULT_FORMULA_CODE,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not emperors:
        raise I5BItemResultError("at least one emperor is required")

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            item_id = _fetch_item_id(cur, item_code)
            for emperor in emperors:
                emp_id = _fetch_emp_id(cur, emperor)
                formula = calculate_formula(
                    signals=_fetch_signals(cur, emp_id=emp_id, item_id=item_id, cluster_formula=cluster_formula),
                )
                rows.append(
                    {
                        "generated_at": generated_at,
                        "result_id": None,
                        "emperor": emperor,
                        "item_code": item_code,
                        "cluster_formula": cluster_formula,
                        "formula_code": formula_code,
                        **formula,
                    }
                )

        conn.rollback()

    return {
        "dry_run": True,
        "writes_db": False,
        "write_status": "skipped_dynamic_mapping_required",
        "requested_write": not dry_run,
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "formula_code": formula_code,
        "results": rows,
    }


def _filters(values: tuple[str, ...]) -> set[str]:
    return {value for value in values if value}


def fetch_item_result_calc_detail_rows(
    *,
    dsn: str,
    item_code: str,
    cluster_formula: str,
    formula_code: str,
    emperors: tuple[str, ...] = (),
) -> dict[str, dict[str, Any]]:
    emperor_filter = _filters(emperors)
    clauses = [
        "i.item_code = %s",
        "r.formula_code = %s",
        "d.formula_code = %s",
        "d.cluster_formula = %s",
    ]
    params: list[Any] = [item_code, formula_code, formula_code, cluster_formula]
    if emperor_filter:
        clauses.append("e.name = any(%s)")
        params.append(sorted(emperor_filter))
    where_sql = " and ".join(clauses)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select
                    r.id as result_id,
                    e.name as emperor,
                    i.item_code,
                    d.cluster_formula,
                    r.formula_code,
                    r.score,
                    r.tier,
                    r.tier_band,
                    d.calc_detail
                  from emp_item_results r
                  join emp_item_result_calc_details d on d.result_id = r.id
                  join emps e on e.id = r.emp_id
                  join eval_items i on i.id = r.item_id
                 where {where_sql}
                 order by e.name
                """,
                tuple(params),
            )
            columns = [desc.name for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        detail = row.get("calc_detail")
        if not isinstance(detail, dict):
            detail = {}
        payload = {
            "result_id": int(row["result_id"]),
            "emperor": str(row["emperor"]),
            "item_code": str(row["item_code"]),
            "cluster_formula": str(row["cluster_formula"]),
            "formula_code": str(row["formula_code"]),
            **detail,
            "score": str(row["score"]),
            "tier": str(row["tier"]),
            "tier_band": str(row["tier_band"]),
        }
        latest[payload["emperor"]] = payload
    return latest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report I5B raw item signals from evd_clusters without final scoring.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV, help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Required evd_clusters formula_code.")
    parser.add_argument("--formula-code", default=DEFAULT_FORMULA_CODE, help="Raw signal formula code to include in the report.")
    parser.add_argument("--emperor", action="append", required=True, help="Emperor name; repeat for batch runs.")
    parser.add_argument("--dry-run", action="store_true", help="Compatibility flag; this command is read-only.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = calculate_item_results(
        dsn=resolve_dsn(args.dsn_env),
        emperors=tuple(args.emperor),
        item_code=args.item_code,
        cluster_formula=args.cluster_formula,
        formula_code=args.formula_code,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
