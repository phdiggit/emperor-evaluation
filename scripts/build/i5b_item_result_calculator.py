from __future__ import annotations

import argparse
import json
import math
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
DEFAULT_FORMULA_CODE = "item_result_formula_i5b_v6"
DEFAULT_LOG_PATH = ROOT / "logs" / "item_results" / "i5b_item_results_calc.jsonl"
MAX_SCORE = Decimal("45.000")
POSITIVE_RESPONSE_CAP = Decimal("5.5")
POSITIVE_RESPONSE_TAU = Decimal("3.5")
NEGATIVE_RESPONSE_CAP = Decimal("7.0")
NEGATIVE_RESPONSE_TAU = Decimal("4.0")

RULE_ORDER = (
    "talent_discovery",
    "appointment_trust",
    "delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
)
RULE_WEIGHTS = {
    "talent_discovery": Decimal("0.19"),
    "appointment_trust": Decimal("0.22"),
    "delegation": Decimal("0.20"),
    "team_building": Decimal("0.15"),
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


def rule_response(signal: Decimal, *, cap: Decimal, tau: Decimal) -> Decimal:
    if signal < 0:
        raise I5BItemResultError("rule signals must be non-negative")
    effect = Decimal(str(float(cap) * (1 - math.exp(-float(signal) / float(tau)))))
    return quant(effect, "0.001")


def positive_rule_response(signal: Decimal) -> Decimal:
    return rule_response(signal, cap=POSITIVE_RESPONSE_CAP, tau=POSITIVE_RESPONSE_TAU)


def negative_rule_response(signal: Decimal) -> Decimal:
    return rule_response(signal, cap=NEGATIVE_RESPONSE_CAP, tau=NEGATIVE_RESPONSE_TAU)


def tier_for_rate(rate: Decimal) -> tuple[str, str]:
    ranges = (
        ("历史极限", Decimal("0.96"), Decimal("0.98")),
        ("历史顶级", Decimal("0.90"), Decimal("0.96")),
        ("优秀", Decimal("0.80"), Decimal("0.90")),
        ("良好", Decimal("0.70"), Decimal("0.80")),
        ("合格", Decimal("0.60"), Decimal("0.70")),
        ("一般", Decimal("0.50"), Decimal("0.60")),
        ("较差", Decimal("0.40"), Decimal("0.50")),
        ("很差", Decimal("0.30"), Decimal("0.40")),
        ("极差", Decimal("0.00"), Decimal("0.30")),
    )
    for tier, low, high in ranges:
        if rate >= low:
            span = high - low
            if span <= 0:
                return tier, ""
            first = low + span / Decimal("3")
            second = low + span * Decimal("2") / Decimal("3")
            if rate < first:
                return tier, "低段"
            if rate < second:
                return tier, "正常"
            return tier, "高段"
    raise I5BItemResultError(f"score_rate {rate} does not match a configured tier interval")


def _zero_signals() -> dict[str, RuleSignals]:
    return {rule: RuleSignals(Decimal("0.000"), Decimal("0.000")) for rule in RULE_ORDER}


def calculate_formula(
    *,
    signals: dict[str, RuleSignals],
) -> dict[str, Any]:
    normalized = _zero_signals()
    normalized.update(signals)

    rule_inputs: dict[str, dict[str, str | bool | None]] = {}
    base_core = Decimal("0.000")

    for rule in RULE_ORDER:
        rule_signal = normalized[rule]
        positive_effect = positive_rule_response(rule_signal.positive_signal)
        negative_effect = negative_rule_response(rule_signal.negative_signal)
        net_effect = positive_effect - negative_effect
        base_core += RULE_WEIGHTS[rule] * net_effect

        rule_inputs[rule] = {
            "cluster_id": rule_signal.cluster_id,
            "no_material": rule_signal.cluster_id is None
            and rule_signal.positive_signal == 0
            and rule_signal.negative_signal == 0,
            "positive_signal": str(quant(rule_signal.positive_signal, "0.001")),
            "negative_signal": str(quant(rule_signal.negative_signal, "0.001")),
            "positive_effect": str(positive_effect),
            "negative_effect": str(negative_effect),
            "rule_net_effect": str(quant(net_effect, "0.001")),
            "rule_weight": str(quant(RULE_WEIGHTS[rule], "0.001")),
        }

    base_core = quant(base_core, "0.001")
    base_rate = quant(Decimal("0.50") + base_core / Decimal("7.5"), "0.0001")
    score_rate = quant(max(Decimal("0"), min(Decimal("0.98"), base_rate)), "0.0001")
    score = quant(MAX_SCORE * score_rate, "0.001")
    tier, tier_band = tier_for_rate(score_rate)

    return {
        "positive_response_cap": str(POSITIVE_RESPONSE_CAP),
        "positive_response_tau": str(POSITIVE_RESPONSE_TAU),
        "negative_response_cap": str(NEGATIVE_RESPONSE_CAP),
        "negative_response_tau": str(NEGATIVE_RESPONSE_TAU),
        "rules": rule_inputs,
        "base_core": str(base_core),
        "base_rate": str(base_rate),
        "score_rate": str(score_rate),
        "score": str(score),
        "tier": tier,
        "tier_band": tier_band,
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


def _upsert_result(
    cur: Any,
    *,
    emp_id: int,
    item_id: int,
    cluster_formula: str,
    formula_code: str,
    formula: dict[str, Any],
) -> int:
    note = f"v6公式自动计算；规则输入来自 {cluster_formula}；无材料规则按0处理。"
    cur.execute(
        """
        insert into emp_item_results (emp_id, item_id, formula_code, max_score, score, tier, tier_band, note)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (emp_id, item_id) do update set
            formula_code = excluded.formula_code,
            max_score = excluded.max_score,
            score = excluded.score,
            tier = excluded.tier,
            tier_band = excluded.tier_band,
            note = excluded.note,
            updated_at = now()
        returning id
        """,
        (
            emp_id,
            item_id,
            formula_code,
            MAX_SCORE,
            Decimal(str(formula["score"])),
            str(formula["tier"]),
            str(formula["tier_band"]),
            note,
        ),
    )
    return int(cur.fetchone()[0])


def _jsonb(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _upsert_result_calc_detail(
    cur: Any,
    *,
    result_id: int,
    item_code: str,
    cluster_formula: str,
    formula_code: str,
    formula: dict[str, Any],
) -> None:
    cur.execute(
        """
        insert into emp_item_result_calc_details (
            result_id, item_code, cluster_formula, formula_code,
            base_core, score_rate, calc_detail
        )
        values (%s, %s, %s, %s, %s, %s, %s::jsonb)
        on conflict (result_id) do update set
            item_code = excluded.item_code,
            cluster_formula = excluded.cluster_formula,
            formula_code = excluded.formula_code,
            base_core = excluded.base_core,
            score_rate = excluded.score_rate,
            calc_detail = excluded.calc_detail,
            updated_at = now()
        """,
        (
            result_id,
            item_code,
            cluster_formula,
            formula_code,
            Decimal(str(formula["base_core"])),
            Decimal(str(formula["score_rate"])),
            _jsonb(formula),
        ),
    )


def append_calc_log(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append legacy item result calculation logs.

    Current I5B tooling writes result calculation details to PostgreSQL tables
    instead of JSONL logs. This helper remains for historical fixtures only.
    """
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def calculate_item_results(
    *,
    dsn: str,
    emperors: tuple[str, ...],
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    formula_code: str = DEFAULT_FORMULA_CODE,
    dry_run: bool = False,
    log_path: Path | None = None,
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
                result_id = _upsert_result(
                    cur,
                    emp_id=emp_id,
                    item_id=item_id,
                    cluster_formula=cluster_formula,
                    formula_code=formula_code,
                    formula=formula,
                )
                _upsert_result_calc_detail(
                    cur,
                    result_id=result_id,
                    item_code=item_code,
                    cluster_formula=cluster_formula,
                    formula_code=formula_code,
                    formula=formula,
                )
                rows.append(
                    {
                        "generated_at": generated_at,
                        "result_id": result_id,
                        "emperor": emperor,
                        "item_code": item_code,
                        "cluster_formula": cluster_formula,
                        "formula_code": formula_code,
                        **formula,
                    }
                )

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

    return {
        "dry_run": dry_run,
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
    parser = argparse.ArgumentParser(description="Calculate formal I5B item results from evd_clusters.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV, help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Required evd_clusters formula_code.")
    parser.add_argument("--formula-code", default=DEFAULT_FORMULA_CODE, help="emp_item_results formula_code to write.")
    parser.add_argument("--log", type=Path, default=None, help="Deprecated; calculation details are stored in DB.")
    parser.add_argument("--emperor", action="append", required=True, help="Emperor name; repeat for batch runs.")
    parser.add_argument("--dry-run", action="store_true", help="Rollback database writes.")
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
        log_path=args.log,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
