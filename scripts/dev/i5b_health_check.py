from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import (  # noqa: E402
    DEFAULT_CLUSTER_FORMULA,
    DEFAULT_FORMULA_CODE,
    DEFAULT_ITEM_CODE,
)
from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.i5b_calc_breakdown import build_breakdown_report  # noqa: E402
from scripts.dev.i5b_factor_consistency_audit import build_audit_report  # noqa: E402
from scripts.dev.i5b_fact_relation_candidate_sync import DEFAULT_RULE_CODES as DEFAULT_FACT_RULE_CODES  # noqa: E402
from scripts.dev.i5b_fact_relation_gap_summary import build_gap_summary_from_db  # noqa: E402
from scripts.dev.i5b_rule_evidence_unit_db_sync import build_payloads  # noqa: E402
from scripts.dev.i5b_rule_evidence_unit_issue_summary import build_issue_summary  # noqa: E402


DEFAULT_REPORT_PATH = ROOT / ".tmp" / "i5b" / "i5b_health_check.md"


class I5BHealthCheckError(ValueError):
    pass


def _text(value: object) -> str:
    return str(value or "").strip()


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _int(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def fetch_emperors_with_results(
    *,
    dsn: str,
    item_code: str = DEFAULT_ITEM_CODE,
    result_formula: str = DEFAULT_FORMULA_CODE,
) -> tuple[str, ...]:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select e.name
                  from emp_item_results r
                  join emps e on e.id = r.emp_id
                  join eval_items i on i.id = r.item_id
                 where i.item_code = %s
                   and r.formula_code = %s
                 order by r.score desc, e.id
                """,
                (item_code, result_formula),
            )
            return tuple(str(row[0]) for row in cur.fetchall())


def score_rows_from_breakdown(breakdown: Mapping[str, object]) -> list[dict[str, object]]:
    emperor_rows = breakdown.get("emperors")
    if not isinstance(emperor_rows, list):
        raise I5BHealthCheckError("calc breakdown report missing emperors")
    rows: list[dict[str, object]] = []
    for emperor in emperor_rows:
        if not isinstance(emperor, Mapping):
            continue
        rows.append(
            {
                "emperor": _text(emperor.get("emperor")),
                "score": _text(emperor.get("score")),
                "tier": _text(emperor.get("tier")),
                "tier_band": _text(emperor.get("tier_band")),
                "base_core": _text(emperor.get("base_core")),
                "score_rate": _text(emperor.get("score_rate")),
            }
        )
    return rows


def _gate_status(*, ok: bool, errors: int = 0, warnings: int = 0, details: Mapping[str, object] | None = None) -> dict[str, object]:
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "details": dict(details or {}),
    }


def build_health_report(
    *,
    dsn: str,
    emperors: Sequence[str],
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    result_formula: str = DEFAULT_FORMULA_CODE,
    rule_codes: Sequence[str] = (),
    fact_rule_codes: Sequence[str] = DEFAULT_FACT_RULE_CODES,
) -> dict[str, object]:
    names = _ordered_unique(tuple(emperors))
    if not names:
        names = fetch_emperors_with_results(dsn=dsn, item_code=item_code, result_formula=result_formula)
    if not names:
        raise I5BHealthCheckError("no emperors selected")

    breakdown = build_breakdown_report(
        dsn=dsn,
        emperors=names,
        item_code=item_code,
        cluster_formula=cluster_formula,
        result_formula=result_formula,
        rule_codes=tuple(rule_codes),
    )
    score_rows = score_rows_from_breakdown(breakdown)
    factor_report = build_audit_report(
        dsn=dsn,
        item_code=item_code,
        cluster_formula=cluster_formula,
        emperors=names,
        rule_codes=tuple(rule_codes),
    )
    unit_payloads = build_payloads(
        dsn=dsn,
        emperors=names,
        item_code=item_code,
        cluster_formula=cluster_formula,
        rule_codes=tuple(rule_codes),
    )
    unit_summary = build_issue_summary(unit_payloads)
    fact_summary = build_gap_summary_from_db(
        dsn=dsn,
        item_code=item_code,
        emperors=names,
        rule_codes=tuple(fact_rule_codes),
    )

    unit_totals = unit_summary.get("totals") if isinstance(unit_summary.get("totals"), Mapping) else {}
    fact_totals = fact_summary.get("totals") if isinstance(fact_summary.get("totals"), Mapping) else {}
    breakdown_warnings = breakdown.get("warnings") if isinstance(breakdown.get("warnings"), list) else []
    gates = {
        "factor_consistency": _gate_status(
            ok=bool(factor_report.get("ok")),
            errors=_int(factor_report, "error_count"),
            warnings=_int(factor_report, "warning_count"),
        ),
        "rule_evidence_unit_preview": _gate_status(
            ok=_int(unit_totals, "issues") == 0,
            errors=_int(unit_totals, "blocks"),
            warnings=_int(unit_totals, "warnings"),
            details={"issues": _int(unit_totals, "issues"), "units": _int(unit_totals, "units")},
        ),
        "fact_relation_gap": _gate_status(
            ok=_int(fact_totals, "total") == 0,
            errors=_int(fact_totals, "total"),
            warnings=0,
            details={
                "non_person": _int(fact_totals, "non_person"),
                "direction_mismatch": _int(fact_totals, "direction_mismatch"),
                "missing_relation": _int(fact_totals, "missing_relation"),
            },
        ),
        "calc_breakdown": _gate_status(
            ok=not breakdown_warnings,
            errors=len(breakdown_warnings),
            warnings=0,
        ),
    }
    ok = all(bool(gate["ok"]) for gate in gates.values())
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ok": ok,
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "result_formula": result_formula,
        "emperors": list(names),
        "score_rows": score_rows,
        "gates": gates,
        "factor_consistency": factor_report,
        "rule_evidence_unit_preview": unit_summary,
        "fact_relation_gap": fact_summary,
        "calc_breakdown_warnings": breakdown_warnings,
    }


def render_markdown(report: Mapping[str, object]) -> str:
    gates = report.get("gates") if isinstance(report.get("gates"), Mapping) else {}
    score_rows = report.get("score_rows") if isinstance(report.get("score_rows"), list) else []
    lines = [
        "# I5B 健康检查",
        "",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- ok: `{str(bool(report.get('ok'))).lower()}`",
        f"- emperors: `{len(report.get('emperors') if isinstance(report.get('emperors'), list) else [])}`",
        f"- cluster_formula: `{report.get('cluster_formula') or ''}`",
        f"- result_formula: `{report.get('result_formula') or ''}`",
        "",
        "## 阀门",
        "",
        "| gate | ok | errors | warnings | details |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for name, gate in gates.items():
        if not isinstance(gate, Mapping):
            continue
        details = gate.get("details") if isinstance(gate.get("details"), Mapping) else {}
        detail_text = "；".join(f"{key}={value}" for key, value in details.items()) or "-"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(name),
                    str(bool(gate.get("ok"))).lower(),
                    str(gate.get("errors", 0)),
                    str(gate.get("warnings", 0)),
                    detail_text,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 评分简表",
            "",
            "| 排名 | 皇帝 | 分数 | 档位 | base_core | score_rate |",
            "| ---: | --- | ---: | --- | ---: | ---: |",
        ]
    )
    for rank, row in enumerate(score_rows, start=1):
        if not isinstance(row, Mapping):
            continue
        tier = f"{row.get('tier') or ''}{row.get('tier_band') or ''}"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(rank),
                    _text(row.get("emperor")),
                    _text(row.get("score")),
                    tier,
                    _text(row.get("base_core")),
                    _text(row.get("score_rate")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_output(text: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run read-only I5B health checks after recalculation or data changes.")
    parser.add_argument("--emperor", action="append", default=[], help="Emperor name; repeatable. Defaults to all I5B results.")
    parser.add_argument("--rule-code", action="append", default=[], help="Limit calc-detail based checks to one I5B rule_code; repeatable.")
    parser.add_argument("--fact-rule-code", action="append", default=[], help="Limit fact relation gap check; defaults to high-risk rules.")
    parser.add_argument("--fact-all-rules", action="store_true", help="Run fact relation gap check against all predicate catalog rules.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA)
    parser.add_argument("--result-formula", default=DEFAULT_FORMULA_CODE)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--fail-on-issue", action="store_true", help="Exit non-zero when any hard health gate fails.")
    parser.add_argument("--fail-on-warning", action="store_true", help="Exit non-zero when any gate reports warnings.")
    return parser.parse_args(argv)


def _fact_rule_codes(args: argparse.Namespace) -> tuple[str, ...]:
    if args.fact_all_rules:
        return ()
    if args.fact_rule_code:
        return tuple(dict.fromkeys(args.fact_rule_code))
    if args.rule_code:
        return tuple(dict.fromkeys(args.rule_code))
    return DEFAULT_FACT_RULE_CODES


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_health_report(
        dsn=args.dsn or resolve_dsn(args.dsn_env),
        emperors=tuple(args.emperor),
        item_code=args.item_code,
        cluster_formula=args.cluster_formula,
        result_formula=args.result_formula,
        rule_codes=tuple(args.rule_code),
        fact_rule_codes=_fact_rule_codes(args),
    )
    if args.format == "json":
        text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n"
    else:
        text = render_markdown(report)
    write_output(text, args.output)
    print(json.dumps({"output": str(args.output) if args.output else None, "ok": report["ok"]}, ensure_ascii=False, sort_keys=True))
    warning_count = sum(_int(gate, "warnings") for gate in report["gates"].values() if isinstance(gate, Mapping))
    if args.fail_on_issue and not report["ok"]:
        return 1
    if args.fail_on_warning and warning_count:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
