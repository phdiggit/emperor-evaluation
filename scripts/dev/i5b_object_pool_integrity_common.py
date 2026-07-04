from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.i5b_finite_values import (  # noqa: E402
    ALLOWED_DIRECTIONS,
    CANONICAL_TALENT_QUALITY_VALUES,
    I5B_RULE_CODES,
    I5B_SUBITEMS,
    OBJECT_ATTR_CODES,
)


DEFAULT_OUTPUT = ROOT / ".tmp" / "i5b" / "i5b_object_pool_integrity_audit.md"
MAX_RENDERED_ROWS = 8

CORE_TABLES = (
    "emps",
    "raw_objs",
    "raw_obj_aliases",
    "emp_objs",
    "obj_srcs",
    "obj_attrs",
    "src_docs",
    "eval_items",
    "eval_rules",
)
POLICY_TABLES = (
    "eval_rule_material_policies",
    "fact_relation_predicate_options",
)
SHADOW_TABLES = (
    "fact_relations",
    "rule_evidence_units",
    "rule_evidence_unit_members",
)
CALC_TABLES = (
    "evd_clusters",
    "evd_cluster_calc_details",
    "emp_item_result_calc_details",
)
REQUIRED_TABLES = CORE_TABLES + POLICY_TABLES + SHADOW_TABLES + CALC_TABLES

RAW_NOTE_FORBIDDEN_RE = "(第五项|I5B|评分|规则|正向|负向|另切|切分)"
GENERIC_OBJ_SRC_NOTE_RE = "(该记录是对象池|支撑规则维度|事实方向为|I5B回源关联|TODO|TODO_RULE_CODE|TODO_TALENT_QUALITY|TODO-SRC)"
AMBIGUOUS_OBJ_SRC_NOTE_RE = (
    "(另切|不入|不加|不计|回填|额外收益|结果反馈|授权合理性|只作|只作为|只计|只保留|不得直接|不能充分验证)"
)
LIFECYCLE_STATUSES = ("active", "inactive", "retired")
REVIEW_STATUSES = ("draft", "needs_review", "accepted", "rejected")
SOURCE_METHODS = ("manual", "candidate_from_obj_srcs", "candidate_from_calc_detail", "candidate_from_payload", "db_backfill")
SCORE_MODES = ("shadow", "scoring", "rejected")
POLICY_MATERIAL_SOURCES = ("obj_srcs", "emp_objs")


class ObjectPoolIntegrityAuditError(ValueError):
    pass


@dataclass(frozen=True)
class RowCheck:
    table: str
    status: str
    severity: str
    message: str
    sql: str
    params: tuple[Any, ...] = ()
    hint: str = ""


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _issue(
    issues: list[dict[str, Any]],
    *,
    table: str,
    status: str,
    severity: str,
    message: str,
    count: int | None = None,
    sample_rows: Sequence[Mapping[str, Any]] = (),
    hint: str = "",
) -> None:
    row: dict[str, Any] = {
        "table": table,
        "status": status,
        "severity": severity,
        "message": message,
    }
    if count is not None:
        row["count"] = count
    if sample_rows:
        row["sample_rows"] = [dict(item) for item in sample_rows]
    if hint:
        row["hint"] = hint
    issues.append(row)


def summarize_issues(issues: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    errors = sum(1 for issue in issues if issue.get("severity") == "error")
    warnings = sum(1 for issue in issues if issue.get("severity") == "warning")
    return {"errors": errors, "warnings": warnings, "total": len(issues)}


def per_table_summary(
    table_counts: Mapping[str, int],
    issues: Sequence[Mapping[str, Any]],
    *,
    required_tables: Sequence[str] = REQUIRED_TABLES,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in required_tables:
        table_issues = [issue for issue in issues if issue.get("table") == table]
        rows.append(
            {
                "table": table,
                "rows": table_counts.get(table),
                "exists": table in table_counts,
                "errors": sum(1 for issue in table_issues if issue.get("severity") == "error"),
                "warnings": sum(1 for issue in table_issues if issue.get("severity") == "warning"),
                "issue_count": len(table_issues),
            }
        )
    return rows


def build_report_from_counts(
    *,
    table_counts: Mapping[str, int],
    issues: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    totals = summarize_issues(issues)
    return {
        "report_type": "i5b_object_pool_integrity_audit",
        "generated_at": generated_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "ok": totals["errors"] == 0,
        "error_count": totals["errors"],
        "warning_count": totals["warnings"],
        "issue_count": totals["total"],
        "tables": per_table_summary(table_counts, issues),
        "table_counts": dict(sorted(table_counts.items())),
        "issues": [dict(issue) for issue in issues],
    }


def _table_counts(cur: psycopg.Cursor, table_names: Sequence[str]) -> dict[str, int]:
    cur.execute(
        """
        select table_name
          from information_schema.tables
         where table_schema = 'public'
           and table_name = any(%s)
         order by table_name
        """,
        (list(table_names),),
    )
    existing = [str(row[0]) for row in cur.fetchall()]
    counts: dict[str, int] = {}
    for table in existing:
        cur.execute(f"select count(*) from public.{table}")
        counts[table] = int(cur.fetchone()[0])
    return counts


def _dict_rows(cur: psycopg.Cursor) -> list[dict[str, Any]]:
    names = [desc.name for desc in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _run_row_check(cur: psycopg.Cursor, issues: list[dict[str, Any]], check: RowCheck, *, limit: int) -> None:
    count_sql = f"select count(*) from ({check.sql}) issue_rows"
    cur.execute(count_sql, check.params)
    count = int(cur.fetchone()[0])
    if count == 0:
        return
    sample_sql = f"select * from ({check.sql}) issue_rows limit %s"
    cur.execute(sample_sql, (*check.params, limit))
    _issue(
        issues,
        table=check.table,
        status=check.status,
        severity=check.severity,
        message=check.message,
        count=count,
        sample_rows=_dict_rows(cur),
        hint=check.hint,
    )


def _run_checks(cur: psycopg.Cursor, issues: list[dict[str, Any]], checks: Sequence[RowCheck], *, limit: int) -> None:
    for check in checks:
        _run_row_check(cur, issues, check, limit=limit)


def _has(table_counts: Mapping[str, int], *tables: str) -> bool:
    return all(table in table_counts for table in tables)


def _missing_table_issues(table_counts: Mapping[str, int]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for table in REQUIRED_TABLES:
        if table not in table_counts:
            _issue(
                issues,
                table=table,
                status="missing_required_table",
                severity="error",
                message=f"required object-pool table is missing: {table}",
            )
    return issues




def all_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    from scripts.dev.i5b_object_pool_integrity_core import core_checks
    from scripts.dev.i5b_object_pool_integrity_shadow import shadow_checks

    return [*core_checks(table_counts), *shadow_checks(table_counts)]


def build_report(*, dsn: str, sample_limit: int = 20) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            table_counts = _table_counts(cur, REQUIRED_TABLES)
            issues = _missing_table_issues(table_counts)
            _run_checks(cur, issues, all_checks(table_counts), limit=sample_limit)
    return build_report_from_counts(table_counts=table_counts, issues=issues)


def _compact_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list | tuple):
        return ",".join(_compact_cell(item) for item in value)
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default)
    return str(value).replace("\n", " ").strip()


def _sample_text(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "-"
    parts: list[str] = []
    for row in rows[:MAX_RENDERED_ROWS]:
        pairs = [f"{key}={_compact_cell(value)}" for key, value in row.items()]
        parts.append("; ".join(pairs))
    return "<br>".join(parts)


def render_markdown(report: Mapping[str, Any]) -> str:
    tables = report.get("tables") if isinstance(report.get("tables"), list) else []
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    lines = [
        "# I5B 对象池完整性审计",
        "",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- ok: `{str(bool(report.get('ok'))).lower()}`",
        f"- errors: `{report.get('error_count') or 0}`",
        f"- warnings: `{report.get('warning_count') or 0}`",
        "",
        "## 表总览",
        "",
        "| table | exists | rows | errors | warnings |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for table in tables:
        if not isinstance(table, Mapping):
            continue
        rows = "-" if table.get("rows") is None else str(table.get("rows"))
        lines.append(
            "| "
            + " | ".join(
                [
                    str(table.get("table") or ""),
                    str(bool(table.get("exists"))).lower(),
                    rows,
                    str(table.get("errors") or 0),
                    str(table.get("warnings") or 0),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Issues", ""])
    if not issues:
        lines.append("- 无")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "| severity | table | status | count | message | sample |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for issue in issues:
        if not isinstance(issue, Mapping):
            continue
        sample_rows = issue.get("sample_rows") if isinstance(issue.get("sample_rows"), list) else []
        lines.append(
            "| "
            + " | ".join(
                [
                    str(issue.get("severity") or ""),
                    str(issue.get("table") or ""),
                    str(issue.get("status") or ""),
                    str(issue.get("count") or ""),
                    str(issue.get("message") or ""),
                    _sample_text([row for row in sample_rows if isinstance(row, Mapping)]),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_output(path: Path | None, text: str) -> None:
    if path is None:
        sys.stdout.write(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


