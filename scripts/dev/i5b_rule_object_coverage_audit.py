from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import (  # noqa: E402
    DEFAULT_CLUSTER_FORMULA,
    DEFAULT_FORMULA_CODE,
    DEFAULT_ITEM_CODE,
    fetch_item_result_calc_detail_rows,
)
from scripts.dev.evidence_cluster_workbench import (  # noqa: E402
    EvidenceClusterWorkbenchError,
    fetch_cluster_calc_detail_rows,
    resolve_dsn,
)


class I5BRuleObjectCoverageAuditError(ValueError):
    pass


TEAM_BUILDING_RULE_CODE = "team_building"


def strip_note(value: str) -> str:
    value = re.sub(r"[（(].*?[）)]", "", value)
    return value.strip().strip("；;，,。")


def split_names(value: str) -> tuple[str, ...]:
    if ":" in value:
        value = value.split(":", 1)[1]
    elif "：" in value:
        value = value.split("：", 1)[1]
    names: list[str] = []
    for part in re.split(r"\s*/\s*|、|，|,", value):
        name = strip_note(part)
        if name:
            names.append(name)
    return tuple(dict.fromkeys(names))


def parse_accepted_missing(values: tuple[str, ...]) -> frozenset[tuple[str, str, str]]:
    accepted: set[tuple[str, str, str]] = set()
    for value in values:
        if ":" in value:
            emperor, names_text = value.split(":", 1)
        elif "：" in value:
            emperor, names_text = value.split("：", 1)
        else:
            raise I5BRuleObjectCoverageAuditError(f"accepted missing must be EMPEROR:NAME, got: {value}")
        emperor = emperor.strip()
        names = split_names(names_text)
        if not emperor or not names:
            raise I5BRuleObjectCoverageAuditError(f"accepted missing must include emperor and name: {value}")
        for name in names:
            accepted.add((emperor, name, ""))
    return frozenset(accepted)


def default_emperors(
    *,
    dsn: str,
    item_code: str,
    cluster_formula: str,
    result_formula: str,
) -> tuple[str, ...]:
    rows = fetch_item_result_calc_detail_rows(
        dsn=dsn,
        item_code=item_code,
        cluster_formula=cluster_formula,
        formula_code=result_formula,
    )
    return tuple(rows)


def attr_value(attrs: list[dict[str, Any]], attr_code: str) -> str:
    for attr in attrs:
        if attr.get("attr_code") == attr_code:
            value = attr.get("value_text")
            if value not in (None, ""):
                return str(value)
            value_num = attr.get("value_num")
            if value_num is not None:
                return str(value_num)
    return ""


def _matches_filters(
    row: dict[str, Any],
    *,
    obj_types: set[str],
    require_attrs: set[str],
) -> bool:
    if obj_types and str(row.get("obj_type") or "") not in obj_types:
        return False
    attrs = row.get("attrs")
    if not isinstance(attrs, list):
        attrs = []
    if require_attrs:
        present = {str(attr.get("attr_code")) for attr in attrs if isinstance(attr, dict)}
        if not require_attrs.issubset(present):
            return False
    return True


def fetch_emp_object_rows(
    *,
    dsn: str,
    item_code: str,
    rule_code: str,
    emperors: tuple[str, ...],
    obj_types: tuple[str, ...] = (),
    require_attrs: tuple[str, ...] = (),
) -> dict[str, list[dict[str, Any]]]:
    if not emperors:
        raise I5BRuleObjectCoverageAuditError("no emperors found; pass --emperor or check result detail table")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with target_item as (
                    select id, item_code, item_name
                    from eval_items
                    where item_code = %s
                )
                select
                    e.name as emperor,
                    eo.id as emp_obj_id,
                    ro.id as obj_id,
                    ro.name as obj_name,
                    ro.obj_type,
                    eo.note as emp_obj_note,
                    ro.note as obj_note,
                    coalesce(
                        jsonb_agg(
                            distinct jsonb_build_object(
                                'attr_code', oa.attr_code,
                                'value_text', oa.value_text,
                                'value_num', oa.value_num,
                                'confidence', oa.confidence,
                                'note', oa.note
                            )
                        ) filter (where oa.id is not null),
                        '[]'::jsonb
                    ) as attrs,
                    coalesce(
                        jsonb_agg(
                            distinct jsonb_build_object(
                                'obj_src_id', os.id,
                                'rule_code', r.rule_code,
                                'direction', os.direction,
                                'note', os.note
                            )
                        ) filter (where os.id is not null and os.item_id = (select id from target_item)),
                        '[]'::jsonb
                    ) as i5b_obj_srcs,
                    coalesce(
                        bool_or(os.item_id = (select id from target_item) and r.rule_code = %s),
                        false
                    ) as has_rule
                  from emps e
                  join emp_objs eo on eo.emp_id = e.id
                  join raw_objs ro on ro.id = eo.obj_id
                  left join obj_attrs oa on oa.obj_id = ro.id
                  left join obj_srcs os on os.emp_obj_id = eo.id
                  left join eval_items i on i.id = os.item_id
                  left join eval_rules r on r.id = os.rule_id
                 where e.name = any(%s)
                   and eo.subitem in (
                       select item_code from target_item
                       union
                       select item_name from target_item
                   )
                 group by e.name, eo.id, ro.id, ro.name, ro.obj_type, eo.note, ro.note
                 order by e.name, ro.name, eo.id
                """,
                (item_code, rule_code, list(emperors)),
            )
            columns = [desc.name for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    grouped: dict[str, list[dict[str, Any]]] = {emperor: [] for emperor in emperors}
    obj_type_filter = {value for value in obj_types if value}
    attr_filter = {value for value in require_attrs if value}
    for row in rows:
        row["attrs"] = list(row.get("attrs") or [])
        row["i5b_obj_srcs"] = list(row.get("i5b_obj_srcs") or [])
        if not _matches_filters(row, obj_types=obj_type_filter, require_attrs=attr_filter):
            continue
        grouped.setdefault(str(row["emperor"]), []).append(row)
    return grouped


def _team_building_current_keys(cluster_row: dict[str, Any] | None) -> set[tuple[str, str]]:
    if cluster_row is None:
        return set()
    detail = cluster_row.get("calc_detail")
    if not isinstance(detail, dict):
        return set()
    raw_components = detail.get("team_quality_components")
    if not isinstance(raw_components, list):
        raw_components = detail.get("materials")
    if not isinstance(raw_components, list):
        return set()
    keys: set[tuple[str, str]] = set()
    for item in raw_components:
        if not isinstance(item, dict):
            continue
        obj_id = item.get("obj_id")
        if obj_id is not None:
            keys.add(("obj_id", str(obj_id)))
        emp_obj_id = item.get("emp_obj_id")
        if emp_obj_id is not None:
            keys.add(("emp_obj_id", str(emp_obj_id)))
    return keys


def apply_team_building_calc_detail_coverage(
    emp_object_rows: dict[str, list[dict[str, Any]]],
    *,
    cluster_rows: dict[tuple[str, str], dict[str, Any]],
) -> None:
    for emperor, rows in emp_object_rows.items():
        current_keys = _team_building_current_keys(cluster_rows.get((emperor, TEAM_BUILDING_RULE_CODE)))
        for row in rows:
            row["has_rule"] = (
                ("obj_id", str(row.get("obj_id"))) in current_keys
                or ("emp_obj_id", str(row.get("emp_obj_id"))) in current_keys
            )


def build_audit_report(
    *,
    dsn: str | None = None,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    result_formula: str = DEFAULT_FORMULA_CODE,
    rule_code: str,
    emperors: tuple[str, ...] = (),
    obj_types: tuple[str, ...] = (),
    require_attrs: tuple[str, ...] = (),
    accepted_missing: frozenset[tuple[str, str, str]] = frozenset(),
    emp_object_rows: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if rule_code == TEAM_BUILDING_RULE_CODE:
        if not obj_types:
            obj_types = ("person",)
        if not require_attrs:
            require_attrs = ("talent_quality",)
    if emp_object_rows is None:
        if dsn is None:
            raise I5BRuleObjectCoverageAuditError("dsn is required when rows are not supplied")
        targets = emperors or default_emperors(
            dsn=dsn,
            item_code=item_code,
            cluster_formula=cluster_formula,
            result_formula=result_formula,
        )
        emp_object_rows = fetch_emp_object_rows(
            dsn=dsn,
            item_code=item_code,
            rule_code=rule_code,
            emperors=targets,
            obj_types=obj_types,
            require_attrs=require_attrs,
        )
        if rule_code == TEAM_BUILDING_RULE_CODE:
            cluster_rows = fetch_cluster_calc_detail_rows(
                dsn=dsn,
                item_code=item_code,
                formula_code=cluster_formula,
                emperors=targets,
                rule_codes=(TEAM_BUILDING_RULE_CODE,),
            )
            apply_team_building_calc_detail_coverage(emp_object_rows, cluster_rows=cluster_rows)
    else:
        targets = emperors or tuple(emp_object_rows)
        obj_type_filter = {value for value in obj_types if value}
        attr_filter = {value for value in require_attrs if value}
        emp_object_rows = {
            emperor: [
                row
                for row in rows
                if _matches_filters(row, obj_types=obj_type_filter, require_attrs=attr_filter)
            ]
            for emperor, rows in emp_object_rows.items()
        }
    if not targets:
        raise I5BRuleObjectCoverageAuditError("no emperors found; pass --emperor or check result detail table")

    rows: list[dict[str, Any]] = []
    for emperor in targets:
        objects = emp_object_rows.get(emperor, [])
        current = [row for row in objects if row.get("has_rule")]
        raw_missing = [row for row in objects if not row.get("has_rule")]
        accepted: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for row in raw_missing:
            key = (emperor, str(row.get("obj_name") or ""), "")
            if key in accepted_missing:
                accepted.append(row)
            else:
                missing.append(row)
        rows.append(
            {
                "emperor": emperor,
                "candidate_count": len(objects),
                "current_count": len(current),
                "missing_count": len(missing),
                "accepted_missing_count": len(accepted),
                "current": current,
                "missing": missing,
                "accepted_missing": accepted,
                "ok": not missing,
            }
        )

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "postgres" if dsn else "in_memory",
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "result_formula": result_formula,
        "rule_code": rule_code,
        "obj_types": list(obj_types),
        "require_attrs": list(require_attrs),
        "ok": all(row["ok"] for row in rows),
        "rows": rows,
    }


def object_display(row: dict[str, Any]) -> str:
    name = str(row.get("obj_name") or "-")
    obj_type = str(row.get("obj_type") or "-")
    attrs = row.get("attrs") if isinstance(row.get("attrs"), list) else []
    quality = attr_value(attrs, "talent_quality")
    suffixes = [obj_type]
    if quality:
        suffixes.append(quality)
    return f"{name}（{'/'.join(suffixes)}）"


def names_text(rows: list[dict[str, Any]]) -> str:
    return "、".join(object_display(row) for row in rows) or "-"


def render_markdown(report: dict[str, Any]) -> str:
    filters = []
    if report.get("obj_types"):
        filters.append("obj_type=" + ",".join(report["obj_types"]))
    if report.get("require_attrs"):
        filters.append("require_attr=" + ",".join(report["require_attrs"]))
    filter_text = "；".join(filters) or "none"
    lines = [
        "# I5B rule 对象覆盖审计",
        "",
        f"- cluster_formula: `{report['cluster_formula']}`",
        f"- result_formula: `{report['result_formula']}`",
        f"- rule_code: `{report['rule_code']}`",
        f"- filters: `{filter_text}`",
        f"- ok: `{report['ok']}`",
        "",
        "| 皇帝 | emp_objs候选 | 当前覆盖 | 缺口 | 审定不入 |",
        "|---|---:|---:|---|---|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['emperor']} | {row['candidate_count']} | {row['current_count']}：{names_text(row['current'])} | "
            f"{row['missing_count']}：{names_text(row['missing'])} | "
            f"{row['accepted_missing_count']}：{names_text(row['accepted_missing'])} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_markdown(report), encoding="utf-8")
        return
    raise I5BRuleObjectCoverageAuditError(f"unknown output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit I5B rule object coverage against emp_objs.")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN", help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Evidence cluster formula_code.")
    parser.add_argument("--result-formula", default=DEFAULT_FORMULA_CODE, help="Item result formula_code.")
    parser.add_argument("--rule-code", required=True, help="Target rule_code.")
    parser.add_argument("--emperor", action="append", default=None, help="Optional emperor filter; repeatable.")
    parser.add_argument("--obj-type", action="append", default=None, help="Optional raw_objs.obj_type filter; repeatable.")
    parser.add_argument("--require-attr", action="append", default=None, help="Optional obj_attrs.attr_code required filter; repeatable.")
    parser.add_argument(
        "--accepted-missing",
        action="append",
        default=None,
        metavar="EMPEROR:NAME",
        help="Reviewed object that should not enter this rule; repeatable.",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown", help="Output format.")
    parser.add_argument("--output", type=Path, default=None, help="Optional report path; stdout if omitted.")
    parser.add_argument("--fail-on-gap", action="store_true", help="Exit non-zero when any emp_obj candidate lacks this rule.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = build_audit_report(
            dsn=resolve_dsn(args.dsn_env),
            item_code=args.item_code,
            cluster_formula=args.cluster_formula,
            result_formula=args.result_formula,
            rule_code=args.rule_code,
            emperors=tuple(args.emperor or ()),
            obj_types=tuple(args.obj_type or ()),
            require_attrs=tuple(args.require_attr or ()),
            accepted_missing=parse_accepted_missing(tuple(args.accepted_missing or ())),
        )
    except (EvidenceClusterWorkbenchError, I5BRuleObjectCoverageAuditError) as exc:
        parser.error(str(exc))

    if args.output:
        write_report(args.output, report, output_format=args.format)
    elif args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")

    if args.fail_on_gap and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
