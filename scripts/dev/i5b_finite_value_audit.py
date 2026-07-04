from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.i5b_finite_values import (  # noqa: E402
    ALLOWED_DIRECTIONS,
    CANONICAL_PERIODS,
    CANONICAL_TALENT_QUALITY_VALUES,
    I5B_RULE_CODES,
    I5B_SUBITEMS,
    OBJECT_ATTR_CODES,
    normalize_period_alias,
)


DEFAULT_OUTPUT = ROOT / ".tmp" / "i5b" / "i5b_finite_value_audit.json"


@dataclass(frozen=True)
class ValueSpec:
    field: str
    choices: tuple[str, ...]
    normalizer: str = ""


VALUE_SPECS = {
    "emps.period": ValueSpec("emps.period", CANONICAL_PERIODS, "period"),
    "raw_objs.period": ValueSpec("raw_objs.period", CANONICAL_PERIODS, "period"),
    "obj_attrs.region": ValueSpec("obj_attrs.region", CANONICAL_PERIODS, "period"),
    "obj_attrs.attr_code": ValueSpec("obj_attrs.attr_code", OBJECT_ATTR_CODES),
    "obj_attrs.talent_quality": ValueSpec("obj_attrs.talent_quality", CANONICAL_TALENT_QUALITY_VALUES),
    "obj_srcs.direction": ValueSpec("obj_srcs.direction", ALLOWED_DIRECTIONS),
    "emp_objs.subitem": ValueSpec("emp_objs.subitem", I5B_SUBITEMS),
    "eval_rules.rule_code": ValueSpec("eval_rules.rule_code", I5B_RULE_CODES),
}


class I5BFiniteValueAuditError(ValueError):
    pass


def _normalize(spec: ValueSpec, value: object) -> str:
    text = str(value or "").strip()
    if spec.normalizer == "period":
        return normalize_period_alias(text)
    return text


def audit_value_rows(field: str, rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    spec = VALUE_SPECS[field]
    issues: list[dict[str, object]] = []
    choices = set(spec.choices)
    for row in rows:
        value = str(row.get("value") or "").strip()
        count = int(row.get("count") or 0)
        normalized = _normalize(spec, value)
        if normalized not in choices:
            issues.append(
                {
                    "field": field,
                    "value": value,
                    "count": count,
                    "severity": "error",
                    "status": "non_canonical_value",
                }
            )
            continue
        if normalized != value:
            issues.append(
                {
                    "field": field,
                    "value": value,
                    "normalized": normalized,
                    "count": count,
                    "severity": "error",
                    "status": "alias_value",
                }
            )
    return issues


def _object_id_list(values: object) -> list[object]:
    if isinstance(values, Sequence) and not isinstance(values, str | bytes):
        return list(values)
    if values is None:
        return []
    return [values]


def audit_normalized_emperor_keys(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for row in rows:
        period = str(row.get("period") or "").strip()
        name = str(row.get("name") or "").strip()
        if not period or not name:
            continue
        groups.setdefault((normalize_period_alias(period), name), []).append(row)
    issues: list[dict[str, object]] = []
    for (period, name), items in sorted(groups.items()):
        if len(items) < 2:
            continue
        issues.append(
            {
                "field": "emps.normalized_period_name",
                "value": name,
                "normalized": f"{period}/{name}",
                "count": len(items),
                "ids": [row.get("id") for row in items],
                "periods": [row.get("period") for row in items],
                "severity": "error",
                "status": "normalized_key_collision",
            }
        )
    return issues


def audit_normalized_raw_object_keys(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, object]]] = {}
    for row in rows:
        obj_type = str(row.get("obj_type") or "").strip()
        period = str(row.get("period") or "").strip()
        name = str(row.get("name") or "").strip()
        if not obj_type or not period or not name:
            continue
        groups.setdefault((obj_type, normalize_period_alias(period), name), []).append(row)
    issues: list[dict[str, object]] = []
    for (obj_type, period, name), items in sorted(groups.items()):
        if len(items) < 2:
            continue
        issues.append(
            {
                "field": "raw_objs.normalized_type_period_name",
                "value": name,
                "normalized": f"{obj_type}/{period}/{name}",
                "count": len(items),
                "ids": [row.get("id") for row in items],
                "periods": [row.get("period") for row in items],
                "severity": "error",
                "status": "normalized_key_collision",
            }
        )
    return issues


def build_report_from_snapshots(
    snapshots: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    duplicate_emps: Sequence[Mapping[str, object]] = (),
    normalized_key_rows: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    distinct_values: dict[str, list[dict[str, object]]] = {}
    for field in VALUE_SPECS:
        rows = [dict(row) for row in snapshots.get(field, ())]
        distinct_values[field] = rows
        issues.extend(audit_value_rows(field, rows))
    for row in duplicate_emps:
        issues.append(
            {
                "field": "emps.name",
                "value": str(row.get("name") or ""),
                "count": int(row.get("count") or 0),
                "ids": list(row.get("ids") or []),
                "periods": list(row.get("periods") or []),
                "severity": "error",
                "status": "duplicate_emperor_name",
            }
        )
    key_rows = normalized_key_rows or {}
    issues.extend(audit_normalized_emperor_keys(key_rows.get("emps", ())))
    issues.extend(audit_normalized_raw_object_keys(key_rows.get("raw_objs", ())))
    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ok": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
        "distinct_values": distinct_values,
    }


def _value_rows(cur: psycopg.Cursor, sql: str) -> list[dict[str, object]]:
    cur.execute(sql)
    return [{"value": row[0], "count": row[1]} for row in cur.fetchall()]


def _duplicate_emps(cur: psycopg.Cursor) -> list[dict[str, object]]:
    cur.execute(
        """
        select
            name,
            count(*) as count,
            array_agg(id order by id) as ids,
            array_agg(period order by id) as periods
          from emps
         group by name
        having count(*) > 1
         order by name
        """
    )
    return [
        {
            "name": name,
            "count": count,
            "ids": list(ids or []),
            "periods": list(periods or []),
        }
        for name, count, ids, periods in cur.fetchall()
    ]


def _normalized_key_rows(cur: psycopg.Cursor) -> dict[str, list[dict[str, object]]]:
    cur.execute("select id, period, name from emps order by id")
    emps = [{"id": row[0], "period": row[1], "name": row[2]} for row in cur.fetchall()]
    cur.execute("select id, obj_type, period, name from raw_objs order by id")
    raw_objs = [{"id": row[0], "obj_type": row[1], "period": row[2], "name": row[3]} for row in cur.fetchall()]
    return {"emps": emps, "raw_objs": raw_objs}


def fetch_snapshots(
    dsn: str,
) -> tuple[dict[str, list[dict[str, object]]], list[dict[str, object]], dict[str, list[dict[str, object]]]]:
    snapshots: dict[str, list[dict[str, object]]] = {}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            snapshots["emps.period"] = _value_rows(cur, "select period, count(*) from emps group by period order by period")
            snapshots["raw_objs.period"] = _value_rows(
                cur, "select period, count(*) from raw_objs group by period order by period"
            )
            snapshots["obj_attrs.region"] = _value_rows(
                cur,
                """
                select region, count(*)
                  from obj_attrs
                 where btrim(coalesce(region, '')) <> ''
                 group by region
                 order by region
                """,
            )
            snapshots["obj_attrs.attr_code"] = _value_rows(
                cur,
                """
                select attr_code, count(*)
                  from obj_attrs
                 group by attr_code
                 order by attr_code
                """,
            )
            snapshots["obj_attrs.talent_quality"] = _value_rows(
                cur,
                """
                select value_text, count(*)
                  from obj_attrs
                 where attr_code = 'talent_quality'
                 group by value_text
                 order by value_text
                """,
            )
            snapshots["obj_srcs.direction"] = _value_rows(
                cur, "select direction, count(*) from obj_srcs group by direction order by direction"
            )
            snapshots["emp_objs.subitem"] = _value_rows(
                cur, "select subitem, count(*) from emp_objs group by subitem order by subitem"
            )
            snapshots["eval_rules.rule_code"] = _value_rows(
                cur,
                """
                select er.rule_code, count(*)
                  from eval_rules er
                  join eval_items i on i.id = er.item_id
                 where i.item_code = 'I5B'
                 group by er.rule_code
                 order by er.rule_code
                """,
            )
            duplicate_emps = _duplicate_emps(cur)
            normalized_key_rows = _normalized_key_rows(cur)
    return snapshots, duplicate_emps, normalized_key_rows


def build_report(*, dsn: str) -> dict[str, object]:
    snapshots, duplicate_emps, normalized_key_rows = fetch_snapshots(dsn)
    return build_report_from_snapshots(
        snapshots,
        duplicate_emps=duplicate_emps,
        normalized_key_rows=normalized_key_rows,
    )


def render_markdown(report: Mapping[str, object]) -> str:
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    values = report.get("distinct_values") if isinstance(report.get("distinct_values"), Mapping) else {}
    lines = [
        "# I5B 有限取值审计",
        "",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- ok: `{str(bool(report.get('ok'))).lower()}`",
        f"- errors: `{report.get('error_count') or 0}`",
        f"- warnings: `{report.get('warning_count') or 0}`",
        "",
        "## Issues",
        "",
    ]
    if issues:
        lines.extend(["| field | status | value | normalized | count |", "| --- | --- | --- | --- | ---: |"])
        for issue in issues:
            if not isinstance(issue, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(issue.get("field") or ""),
                        str(issue.get("status") or ""),
                        str(issue.get("value") or ""),
                        str(issue.get("normalized") or "-"),
                        str(issue.get("count") or 0),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- 无")
    lines.extend(["", "## Distinct Values", ""])
    for field, rows in values.items():
        if not isinstance(rows, list):
            continue
        display = "；".join(f"{row.get('value')}={row.get('count')}" for row in rows if isinstance(row, Mapping))
        lines.append(f"- `{field}`: {display or '-'}")
    return "\n".join(lines) + "\n"


def write_output(path: Path | None, text: str) -> None:
    if path is None:
        sys.stdout.write(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit finite/canonical I5B DB values.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-issue", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(dsn=args.dsn or resolve_dsn(args.dsn_env))
    if args.format == "json":
        text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        text = render_markdown(report)
    write_output(args.output, text)
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "output": str(args.output) if args.output else None,
                "error_count": report["error_count"],
                "warning_count": report["warning_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if args.fail_on_issue and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
