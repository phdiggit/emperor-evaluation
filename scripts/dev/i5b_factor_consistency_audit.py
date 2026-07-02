from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import psycopg


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import DEFAULT_CLUSTER_FORMULA, DEFAULT_ITEM_CODE  # noqa: E402
from scripts.dev.evidence_cluster_workbench import (  # noqa: E402
    EvidenceClusterWorkbenchError,
    fetch_cluster_calc_detail_rows,
    resolve_dsn,
)


HANDLING_SEVERITY_FACTOR = "handling_severity"
LEGACY_DISPOSITION_FACTOR = "disposition_severity"
HIGH_SEVERITY_FACTORS = (HANDLING_SEVERITY_FACTOR, LEGACY_DISPOSITION_FACTOR)
HIGH_DISPOSITION_THRESHOLD = Decimal("2.5")
TOLERATE_TALENT_RULE_CODE = "tolerate_talent"
NEGATIVE_TALENT_QUALITY_VALUES = {"佞臣", "大佞臣", "历史级佞臣"}

LOW_SEVERITY_NOTE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"不等同于[^。；;]*系统清洗",
        r"不等同于[^。；;]*杀戮",
        r"不属于[^。；;]*系统清洗",
        r"并非[^。；;]*系统清洗",
        r"象征性信用撤销",
        r"轻处分",
        r"身后信用反转",
    )
)

HIGH_SEVERITY_SUPPORT_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"大规模",
        r"系统清洗",
        r"系统性",
        r"长期人才生态",
        r"人才生态破坏",
        r"连坐",
        r"株连",
        r"族诛",
        r"牵连",
        r"功臣集团",
        r"核心能臣",
        r"核心武臣",
        r"核心将帅",
        r"下狱赐死",
        r"表达压制",
        r"寒蝉",
        r"跨群体",
        r"十余人",
        r"数十",
        r"数百",
        r"数千",
        r"灾难级",
    )
)


class I5BFactorConsistencyAuditError(ValueError):
    pass


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _factor_label(ref: Any) -> str:
    if isinstance(ref, dict):
        return str(ref.get("label") or ref.get("code") or ref.get("value") or "")
    if ref is None:
        return ""
    return str(ref)


def _materials(calc_detail: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    raw = calc_detail.get("materials")
    if isinstance(raw, list):
        return tuple(item for item in raw if isinstance(item, dict))
    if isinstance(raw, dict):
        materials: list[dict[str, Any]] = []
        for side, items in raw.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    copied = dict(item)
                    copied.setdefault("side", side)
                    materials.append(copied)
        return tuple(materials)
    return ()


def _obj_src_ids(cluster_rows: dict[tuple[str, str], dict[str, Any]]) -> tuple[int, ...]:
    ids: list[int] = []
    for row in cluster_rows.values():
        calc_detail = row.get("calc_detail")
        if not isinstance(calc_detail, dict):
            continue
        for material in _materials(calc_detail):
            obj_src_id = material.get("obj_src_id")
            if isinstance(obj_src_id, int):
                ids.append(obj_src_id)
    return tuple(dict.fromkeys(ids))


def _high_severity_factor(material: dict[str, Any]) -> tuple[str, Decimal] | None:
    values = material.get("factor_values")
    if not isinstance(values, dict):
        return None
    for factor in HIGH_SEVERITY_FACTORS:
        severity = _decimal(values.get(factor))
        if severity is not None and severity >= HIGH_DISPOSITION_THRESHOLD:
            return factor, severity
    return None


def _has_high_disposition(cluster_rows: dict[tuple[str, str], dict[str, Any]]) -> bool:
    for row in cluster_rows.values():
        calc_detail = row.get("calc_detail")
        if not isinstance(calc_detail, dict):
            continue
        for material in _materials(calc_detail):
            if _high_severity_factor(material):
                return True
    return False


def _has_negative_tolerate_talent_material(cluster_rows: dict[tuple[str, str], dict[str, Any]]) -> bool:
    for (_, rule_code), row in cluster_rows.items():
        if rule_code != TOLERATE_TALENT_RULE_CODE:
            continue
        calc_detail = row.get("calc_detail")
        if not isinstance(calc_detail, dict):
            continue
        for material in _materials(calc_detail):
            if material.get("side") == "negative" and isinstance(material.get("obj_src_id"), int):
                return True
    return False


def fetch_obj_src_notes(*, dsn: str, obj_src_ids: tuple[int, ...]) -> dict[int, dict[str, Any]]:
    if not obj_src_ids:
        return {}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    osrc.id as obj_src_id,
                    osrc.note as obj_src_note,
                    ro.name as obj_name,
                    ro.note as obj_note,
                    sd.src_key,
                    sd.title,
                    sd.volume,
                    sd.locator,
                    coalesce(
                        jsonb_agg(
                            jsonb_build_object(
                                'attr_code', oa.attr_code,
                                'value_text', oa.value_text,
                                'value_num', oa.value_num
                            )
                        ) filter (where oa.id is not null),
                        '[]'::jsonb
                    ) as attrs
                  from obj_srcs osrc
                  join raw_objs ro on ro.id = osrc.obj_id
                  join src_docs sd on sd.id = osrc.doc_id
                  left join obj_attrs oa on oa.obj_id = ro.id
                 where osrc.id = any(%s)
                 group by osrc.id, ro.name, ro.note, sd.src_key, sd.title, sd.volume, sd.locator
                 order by osrc.id
                """,
                (list(obj_src_ids),),
            )
            columns = [desc.name for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    return {int(row["obj_src_id"]): row for row in rows}


def _combined_note(material: dict[str, Any], note_row: dict[str, Any] | None) -> str:
    parts = [
        material.get("obj_src_note"),
        material.get("note"),
    ]
    if note_row:
        parts.extend([note_row.get("obj_src_note"), note_row.get("obj_note")])
    return "\n".join(str(part) for part in parts if part)


def _attr_rows(note_row: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not note_row:
        return ()
    raw = note_row.get("attrs")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return ()
        raw = parsed
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, dict))


def _negative_talent_quality(note_row: dict[str, Any] | None) -> str | None:
    for attr in _attr_rows(note_row):
        if attr.get("attr_code") != "talent_quality":
            continue
        value_text = str(attr.get("value_text") or "")
        if value_text in NEGATIVE_TALENT_QUALITY_VALUES:
            return value_text
    return None


def _matched_patterns(patterns: tuple[re.Pattern[str], ...], text: str) -> tuple[str, ...]:
    return tuple(pattern.pattern for pattern in patterns if pattern.search(text))


def audit_cluster_rows(
    *,
    cluster_rows: dict[tuple[str, str], dict[str, Any]],
    material_notes: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    material_notes = material_notes or {}
    issues: list[dict[str, Any]] = []
    for (emperor, rule_code), row in cluster_rows.items():
        calc_detail = row.get("calc_detail")
        if not isinstance(calc_detail, dict):
            continue
        for material in _materials(calc_detail):
            obj_src_id = material.get("obj_src_id")
            note_row = material_notes.get(obj_src_id) if isinstance(obj_src_id, int) else None
            negative_talent_quality = _negative_talent_quality(note_row)
            if (
                rule_code == TOLERATE_TALENT_RULE_CODE
                and material.get("side") == "negative"
                and negative_talent_quality is not None
            ):
                issues.append(
                    {
                        "severity": "error",
                        "code": "tolerate_talent_negative_actor_material",
                        "message": "容人保全负向材料必须绑定受损人才或人才安全对象，不能把佞臣、酷吏等施害者本人作为本规则受损对象。",
                        "emperor": emperor,
                        "rule_code": rule_code,
                        "obj_name": material.get("obj_name")
                        or material.get("object_name")
                        or (note_row or {}).get("obj_name"),
                        "obj_src_id": obj_src_id,
                        "side": material.get("side"),
                        "factor": "talent_quality",
                        "factor_value": negative_talent_quality,
                        "factor_label": negative_talent_quality,
                        "obj_src_note": (note_row or {}).get("obj_src_note")
                        or material.get("obj_src_note")
                        or material.get("note")
                        or "",
                    }
                )
            values = material.get("factor_values")
            refs = material.get("factor_refs")
            if not isinstance(values, dict) or not isinstance(refs, dict):
                continue
            high_severity = _high_severity_factor(material)
            if high_severity is None:
                continue
            severity_factor, severity = high_severity
            note = _combined_note(material, note_row)
            low_matches = _matched_patterns(LOW_SEVERITY_NOTE_PATTERNS, note)
            support_matches = _matched_patterns(HIGH_SEVERITY_SUPPORT_PATTERNS, note)
            base = {
                "severity": "error" if low_matches else "warning",
                "emperor": emperor,
                "rule_code": rule_code,
                "obj_name": material.get("obj_name") or material.get("object_name") or (note_row or {}).get("obj_name"),
                "obj_src_id": obj_src_id,
                "side": material.get("side"),
                "factor": severity_factor,
                "factor_value": str(severity),
                "factor_label": _factor_label(refs.get(severity_factor)),
                "obj_src_note": (note_row or {}).get("obj_src_note") or material.get("obj_src_note") or material.get("note") or "",
            }
            if low_matches:
                issue = dict(base)
                issue.update(
                    {
                        "code": "high_disposition_contradicted_by_note",
                        "message": "高处置严重度与材料注释中的低严重度/非系统清洗表述冲突。",
                        "matched_patterns": list(low_matches),
                    }
                )
                issues.append(issue)
                continue
            if not support_matches:
                issue = dict(base)
                issue.update(
                    {
                        "code": "high_disposition_without_explicit_support",
                        "message": "高处置严重度缺少明确的大规模牵连、系统清洗或长期人才生态破坏标记。",
                        "matched_patterns": [],
                    }
                )
                issues.append(issue)
    return issues


def build_audit_report(
    *,
    dsn: str | None = None,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    emperors: tuple[str, ...] = (),
    rule_codes: tuple[str, ...] = (),
    cluster_rows: dict[tuple[str, str], dict[str, Any]] | None = None,
    material_notes: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if cluster_rows is None:
        if dsn is None:
            raise I5BFactorConsistencyAuditError("dsn is required when cluster_rows are not supplied")
        cluster_rows = fetch_cluster_calc_detail_rows(
            dsn=dsn,
            item_code=item_code,
            formula_code=cluster_formula,
            emperors=emperors,
            rule_codes=rule_codes,
        )
    if material_notes is None:
        if not _has_high_disposition(cluster_rows) and not _has_negative_tolerate_talent_material(cluster_rows):
            material_notes = {}
        elif dsn is None:
            raise I5BFactorConsistencyAuditError("dsn is required when material_notes are not supplied")
        else:
            material_notes = fetch_obj_src_notes(dsn=dsn, obj_src_ids=_obj_src_ids(cluster_rows))
    issues = audit_cluster_rows(cluster_rows=cluster_rows, material_notes=material_notes)
    errors = [issue for issue in issues if issue["severity"] == "error"]
    warnings = [issue for issue in issues if issue["severity"] == "warning"]
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "postgres" if dsn else "in_memory",
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "ok": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": issues,
    }


def cluster_rows_from_inputs(clusters: tuple[Any, ...]) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for cluster in clusters:
        emperor = str(getattr(cluster, "emperor"))
        rule_code = str(getattr(cluster, "rule_code"))
        rows[(emperor, rule_code)] = {
            "emperor": emperor,
            "rule_code": rule_code,
            "formula_code": str(getattr(cluster, "formula_code", "")),
            "calc_detail": getattr(cluster, "calc_detail", None) or {},
        }
    return rows


def build_audit_report_from_inputs(
    *,
    dsn: str,
    item_code: str,
    cluster_formula: str,
    clusters: tuple[Any, ...],
) -> dict[str, Any]:
    cluster_rows = cluster_rows_from_inputs(clusters)
    return build_audit_report(
        dsn=dsn,
        item_code=item_code,
        cluster_formula=cluster_formula,
        cluster_rows=cluster_rows,
    )


def assert_no_factor_consistency_errors(report: dict[str, Any]) -> None:
    if report.get("ok"):
        return
    first = next((issue for issue in report.get("issues", []) if issue.get("severity") == "error"), None)
    if first is None:
        return
    raise I5BFactorConsistencyAuditError(
        "I5B factor consistency audit failed: "
        f"{first.get('emperor')}/{first.get('rule_code')}/"
        f"{first.get('obj_name')}#{first.get('obj_src_id')} "
        f"{first.get('code')} ({first.get('message')})"
    )


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# I5B 因子一致性审计",
        "",
        f"- cluster_formula: `{report['cluster_formula']}`",
        f"- ok: `{report['ok']}`",
        f"- errors: `{report['error_count']}`",
        f"- warnings: `{report['warning_count']}`",
        "",
        "| 级别 | 皇帝 | 指标 | 对象 | obj_src_id | 因子 | 材料注释 | 问题 |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for issue in report["issues"]:
        note = str(issue.get("obj_src_note") or "-").replace("\n", " ")
        if len(note) > 80:
            note = note[:77] + "..."
        factor = f"{issue['factor']}={issue['factor_value']} ({issue.get('factor_label') or '-'})"
        lines.append(
            "| "
            f"{issue['severity']} | {issue['emperor']} | {issue['rule_code']} | "
            f"{issue.get('obj_name') or '-'} | {issue.get('obj_src_id') or '-'} | "
            f"{factor} | {note} | {issue['message']} |"
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
    raise I5BFactorConsistencyAuditError(f"unknown output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit I5B factor assignments against material notes.")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN", help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Evidence cluster formula_code.")
    parser.add_argument("--emperor", action="append", default=None, help="Optional emperor filter; repeatable.")
    parser.add_argument("--rule-code", action="append", default=None, help="Optional rule_code filter; repeatable.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown", help="Output format.")
    parser.add_argument("--output", type=Path, default=None, help="Optional report path; stdout if omitted.")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit non-zero when hard consistency errors exist.")
    parser.add_argument("--fail-on-warning", action="store_true", help="Exit non-zero when warnings exist.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = build_audit_report(
            dsn=resolve_dsn(args.dsn_env),
            item_code=args.item_code,
            cluster_formula=args.cluster_formula,
            emperors=tuple(args.emperor or ()),
            rule_codes=tuple(args.rule_code or ()),
        )
    except (EvidenceClusterWorkbenchError, I5BFactorConsistencyAuditError) as exc:
        parser.error(str(exc))

    if args.output:
        write_report(args.output, report, output_format=args.format)
    elif args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")

    if args.fail_on_error and report["error_count"]:
        return 1
    if args.fail_on_warning and report["warning_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
