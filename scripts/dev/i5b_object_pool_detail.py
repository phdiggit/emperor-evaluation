from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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
    resolve_dsn,
)


RULE_LABELS = {
    "talent_discovery": "发现人才",
    "appointment_trust": "任人信任",
    "delegation": "合理授权",
    "team_building": "建立团队",
    "tolerate_talent": "容人保全",
    "anti_nepotism": "避免任人唯亲",
}


class I5BObjectPoolDetailError(ValueError):
    pass


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _dedupe_rows(rows: list[dict[str, Any]], *, key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _normalize_attr(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "attr_code": row.get("attr_code"),
        "value_text": row.get("value_text"),
        "value_num": row.get("value_num"),
        "value_unit": row.get("value_unit"),
        "confidence": row.get("confidence"),
        "note": row.get("note"),
    }


def _normalize_link(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "obj_src_id": row.get("obj_src_id"),
        "rule_code": row.get("rule_code"),
        "rule_label": RULE_LABELS.get(str(row.get("rule_code") or ""), str(row.get("rule_code") or "")),
        "direction": row.get("direction"),
        "src_key": row.get("src_key"),
        "source_title": row.get("source_title"),
        "locator": row.get("locator"),
        "note": row.get("note"),
    }


def _normalize_object(row: dict[str, Any], *, rule_filter: set[str] | None = None) -> dict[str, Any]:
    attrs = _dedupe_rows(
        [_normalize_attr(attr) for attr in _as_list(row.get("attrs"))],
        key_fields=("attr_code", "value_text", "value_num", "value_unit", "note"),
    )
    links = _dedupe_rows(
        [_normalize_link(link) for link in _as_list(row.get("rule_links"))],
        key_fields=("obj_src_id", "rule_code", "direction", "src_key", "note"),
    )
    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in links:
        rule_code = str(link.get("rule_code") or "")
        if not rule_code:
            continue
        if rule_filter is not None and rule_code not in rule_filter:
            continue
        by_rule[rule_code].append(link)

    rules = [
        {
            "rule_code": rule_code,
            "rule_label": RULE_LABELS.get(rule_code, rule_code),
            "material_count": len(materials),
            "directions": sorted({str(item.get("direction") or "") for item in materials if item.get("direction")}),
            "materials": materials,
        }
        for rule_code, materials in sorted(by_rule.items())
    ]
    return {
        "emp_obj_id": row.get("emp_obj_id"),
        "obj_id": row.get("obj_id"),
        "obj_name": row.get("obj_name"),
        "obj_type": row.get("obj_type"),
        "obj_period": row.get("obj_period"),
        "emp_obj_note": row.get("emp_obj_note"),
        "obj_note": row.get("obj_note"),
        "attrs": attrs,
        "rule_count": len(rules),
        "material_count": sum(len(materials) for materials in by_rule.values()),
        "rules": rules,
    }


def _int_set(value: Any) -> set[int]:
    if not isinstance(value, list):
        return set()
    result: set[int] = set()
    for item in value:
        if isinstance(item, int):
            result.add(item)
        elif isinstance(item, str) and item.isdigit():
            result.add(int(item))
    return result


def _calc_detail_ids(row: dict[str, Any], key: str) -> set[int]:
    direct = _int_set(row.get(key))
    if direct:
        return direct
    detail = row.get("cluster_calc_detail")
    if not isinstance(detail, dict):
        return set()
    return _int_set(detail.get(key))


def _score_status(row: dict[str, Any], material: dict[str, Any]) -> str:
    obj_src_id = row.get("obj_src_id")
    if not isinstance(obj_src_id, int):
        return "no_material"
    if material:
        return "scored"
    if obj_src_id in _calc_detail_ids(row, "supporting_material_ids"):
        return "supporting"
    if obj_src_id in _calc_detail_ids(row, "excluded_material_ids"):
        return "excluded"
    if obj_src_id in _calc_detail_ids(row, "pending_material_ids"):
        return "pending"
    if obj_src_id in _calc_detail_ids(row, "covered_material_ids"):
        return "covered_unscored"
    return "unscored"


def _decimal_sum(rows: list[dict[str, Any]], key: str) -> str:
    total = Decimal("0")
    found = False
    for row in rows:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            total += Decimal(str(value))
        except (InvalidOperation, TypeError):
            continue
        found = True
    return str(total) if found else ""


def _normalize_object_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "obj_id": row.get("obj_id"),
        "obj_name": row.get("obj_name"),
        "obj_type": row.get("obj_type"),
        "obj_period": row.get("obj_period"),
        "obj_note": row.get("obj_note"),
        "attrs": _dedupe_rows(
            [_normalize_attr(attr) for attr in _as_list(row.get("attrs"))],
            key_fields=("attr_code", "value_text", "value_num", "value_unit", "note"),
        ),
    }


def _normalize_object_binding_material(row: dict[str, Any]) -> dict[str, Any]:
    material = row.get("score_material")
    if not isinstance(material, dict):
        material = {}
    return {
        "obj_src_id": row.get("obj_src_id"),
        "rule_code": row.get("rule_code"),
        "rule_label": RULE_LABELS.get(str(row.get("rule_code") or ""), str(row.get("rule_code") or "")),
        "direction": row.get("direction"),
        "src_key": row.get("src_key"),
        "source_title": row.get("source_title"),
        "locator": row.get("locator"),
        "note": row.get("note"),
        "score_status": _score_status(row, material),
        "side": material.get("side"),
        "raw_score": material.get("raw_score"),
        "abs_score": material.get("abs_score"),
        "factor_values": material.get("factor_values") or {},
        "factor_refs": material.get("factor_refs") or {},
    }


def _build_object_report_rows(
    *,
    object_names: tuple[str, ...],
    object_rows: list[dict[str, Any]],
    link_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    object_by_id = {int(row["obj_id"]): _normalize_object_identity(row) for row in object_rows}
    links_by_obj: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in link_rows:
        obj_id = row.get("obj_id")
        if not isinstance(obj_id, int):
            continue
        links_by_obj[obj_id].append(row)

    objects: list[dict[str, Any]] = []
    for obj_id, obj in sorted(object_by_id.items(), key=lambda item: (str(item[1].get("obj_name") or ""), item[0])):
        binding_index: dict[tuple[str, int], dict[str, Any]] = {}
        for row in links_by_obj.get(obj_id, []):
            emp_obj_id = int(row.get("emp_obj_id") or 0)
            emperor = str(row.get("emperor") or "")
            binding = binding_index.setdefault(
                (emperor, emp_obj_id),
                {
                    "emperor": emperor,
                    "emp_id": row.get("emp_id"),
                    "emp_obj_id": emp_obj_id,
                    "emp_obj_note": row.get("emp_obj_note"),
                    "rules": [],
                },
            )
            rules_by_code = {rule["rule_code"]: rule for rule in binding["rules"]}
            rule_code = str(row.get("rule_code") or "")
            if not rule_code:
                continue
            rule = rules_by_code.get(rule_code)
            if rule is None:
                rule = {
                    "rule_code": rule_code,
                    "rule_label": RULE_LABELS.get(rule_code, rule_code),
                    "materials": [],
                }
                binding["rules"].append(rule)
            rule["materials"].append(_normalize_object_binding_material(row))

        bindings = list(binding_index.values())
        for binding in bindings:
            binding["rules"].sort(key=lambda item: str(item.get("rule_code") or ""))
            for rule in binding["rules"]:
                materials = rule["materials"]
                rule["material_count"] = len(materials)
                rule["scored_material_count"] = sum(1 for material in materials if material.get("score_status") == "scored")
                rule["raw_score_total"] = _decimal_sum(materials, "raw_score")
                rule["abs_score_total"] = _decimal_sum(materials, "abs_score")
        bindings.sort(key=lambda item: (str(item.get("emperor") or ""), int(item.get("emp_obj_id") or 0)))

        obj.update(
            {
                "binding_count": len(bindings),
                "rule_count": sum(len(binding["rules"]) for binding in bindings),
                "material_count": sum(rule["material_count"] for binding in bindings for rule in binding["rules"]),
                "scored_material_count": sum(
                    rule["scored_material_count"] for binding in bindings for rule in binding["rules"]
                ),
                "bindings": bindings,
            }
        )
        objects.append(obj)

    found_names = {str(row.get("obj_name") or "") for row in object_rows}
    missing = [name for name in object_names if name not in found_names]
    return {"objects": objects, "missing_objects": missing}


def fetch_object_pool_rows(
    *,
    dsn: str,
    item_code: str,
    emperors: tuple[str, ...],
    include_all_subitems: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    if not emperors:
        raise I5BObjectPoolDetailError("at least one --emperor is required")
    subitem_filter = ""
    if not include_all_subitems:
        subitem_filter = """
           and eo.subitem in (
               select item_code from target_item
               union
               select item_name from target_item
           )
        """
    query = f"""
        with target_item as (
            select id, item_code, item_name
            from eval_items
            where item_code = %s
        )
        select
            e.name as emperor,
            e.id as emp_id,
            eo.id as emp_obj_id,
            eo.subitem as emp_obj_subitem,
            eo.note as emp_obj_note,
            ro.id as obj_id,
            ro.name as obj_name,
            ro.obj_type,
            ro.period as obj_period,
            ro.note as obj_note,
            coalesce(
                jsonb_agg(
                    distinct jsonb_build_object(
                        'attr_code', oa.attr_code,
                        'value_text', oa.value_text,
                        'value_num', oa.value_num,
                        'value_unit', oa.value_unit,
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
                        'src_key', sd.src_key,
                        'source_title', sd.title,
                        'locator', sd.locator,
                        'note', os.note
                    )
                ) filter (
                    where os.id is not null
                      and (
                          exists (select 1 from target_item)
                          and os.item_id = (select id from target_item)
                      )
                ),
                '[]'::jsonb
            ) as rule_links
          from emps e
          join emp_objs eo on eo.emp_id = e.id
          join raw_objs ro on ro.id = eo.obj_id
          left join obj_attrs oa on oa.obj_id = ro.id
          left join obj_srcs os on os.emp_obj_id = eo.id
          left join eval_rules r on r.id = os.rule_id
          left join src_docs sd on sd.id = os.doc_id
         where e.name = any(%s)
         {subitem_filter}
         group by e.name, e.id, eo.id, eo.subitem, eo.note, ro.id, ro.name, ro.obj_type, ro.period, ro.note
         order by e.name, ro.name, eo.id
    """
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (item_code, list(emperors)))
            columns = [desc.name for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    grouped: dict[str, list[dict[str, Any]]] = {emperor: [] for emperor in emperors}
    for row in rows:
        grouped.setdefault(str(row["emperor"]), []).append(row)
    return grouped


def fetch_object_name_rows(
    *,
    dsn: str,
    item_code: str,
    cluster_formula: str,
    object_names: tuple[str, ...],
    emperors: tuple[str, ...] = (),
    rule_codes: tuple[str, ...] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not object_names:
        raise I5BObjectPoolDetailError("at least one --object is required")
    object_filter = sorted({name for name in object_names if name})
    emperor_filter = sorted({name for name in emperors if name})
    rule_filter = sorted({rule for rule in rule_codes if rule})

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    ro.id as obj_id,
                    ro.name as obj_name,
                    ro.obj_type,
                    ro.period as obj_period,
                    ro.note as obj_note,
                    coalesce(
                        jsonb_agg(
                            distinct jsonb_build_object(
                                'attr_code', oa.attr_code,
                                'value_text', oa.value_text,
                                'value_num', oa.value_num,
                                'value_unit', oa.value_unit,
                                'confidence', oa.confidence,
                                'note', oa.note
                            )
                        ) filter (where oa.id is not null),
                        '[]'::jsonb
                    ) as attrs
                  from raw_objs ro
                  left join obj_attrs oa on oa.obj_id = ro.id
                 where ro.name = any(%s)
                 group by ro.id, ro.name, ro.obj_type, ro.period, ro.note
                 order by ro.name, ro.id
                """,
                (object_filter,),
            )
            object_columns = [desc.name for desc in cur.description]
            object_rows = [dict(zip(object_columns, row)) for row in cur.fetchall()]

            clauses = ["ro.name = any(%s)"]
            params: list[Any] = [item_code, cluster_formula, cluster_formula, object_filter]
            if emperor_filter:
                clauses.append("e.name = any(%s)")
                params.append(emperor_filter)
            if rule_filter:
                clauses.append("r.rule_code = any(%s)")
                params.append(rule_filter)
            where_sql = " and ".join(clauses)
            cur.execute(
                f"""
                select
                    ro.id as obj_id,
                    e.id as emp_id,
                    e.name as emperor,
                    eo.id as emp_obj_id,
                    eo.note as emp_obj_note,
                    os.id as obj_src_id,
                    r.rule_code,
                    os.direction,
                    sd.src_key,
                    sd.title as source_title,
                    sd.locator,
                    os.note,
                    c.id as cluster_id,
                    d.covered_material_ids,
                    d.scored_material_ids,
                    d.supporting_material_ids,
                    d.calc_detail as cluster_calc_detail,
                    scored.material as score_material
                  from raw_objs ro
                  join emp_objs eo on eo.obj_id = ro.id
                  join emps e on e.id = eo.emp_id
                  join obj_srcs os on os.emp_obj_id = eo.id
                  join eval_items i on i.id = os.item_id and i.item_code = %s
                  join eval_rules r on r.id = os.rule_id
                  left join src_docs sd on sd.id = os.doc_id
                  left join evd_clusters c
                    on c.emp_id = e.id
                   and c.item_id = os.item_id
                   and c.rule_id = os.rule_id
                   and c.formula_code = %s
                  left join evd_cluster_calc_details d
                    on d.cluster_id = c.id
                   and d.formula_code = %s
                  left join lateral (
                      select material
                        from jsonb_array_elements(coalesce(d.calc_detail->'materials', '[]'::jsonb)) as material
                       where (material->>'obj_src_id') ~ '^\\d+$'
                         and (material->>'obj_src_id')::bigint = os.id
                       limit 1
                  ) scored on true
                 where {where_sql}
                 order by ro.name, e.name, r.rule_code, os.id
                """,
                tuple(params),
            )
            link_columns = [desc.name for desc in cur.description]
            link_rows = [dict(zip(link_columns, row)) for row in cur.fetchall()]
    return object_rows, link_rows


def build_detail_report(
    *,
    emperors: tuple[str, ...],
    item_code: str = DEFAULT_ITEM_CODE,
    dsn: str | None = None,
    rows_by_emperor: dict[str, list[dict[str, Any]]] | None = None,
    include_empty: bool = True,
    rule_codes: tuple[str, ...] = (),
) -> dict[str, Any]:
    if not emperors:
        raise I5BObjectPoolDetailError("at least one emperor is required")
    if rows_by_emperor is None:
        if dsn is None:
            raise I5BObjectPoolDetailError("dsn is required when rows are not supplied")
        rows_by_emperor = fetch_object_pool_rows(dsn=dsn, item_code=item_code, emperors=emperors)

    rule_filter = {rule_code for rule_code in rule_codes if rule_code}
    emperor_reports: list[dict[str, Any]] = []
    missing: list[str] = []
    for emperor in emperors:
        raw_rows = rows_by_emperor.get(emperor, [])
        objects = [
            obj
            for obj in (
                _normalize_object(row, rule_filter=rule_filter or None)
                for row in raw_rows
            )
            if not rule_filter or obj["rules"]
        ]
        if not raw_rows:
            missing.append(emperor)
        if not objects:
            if not include_empty:
                continue
        rule_codes = sorted(
            {
                str(rule.get("rule_code"))
                for obj in objects
                for rule in obj.get("rules", [])
                if rule.get("rule_code")
            }
        )
        emperor_reports.append(
            {
                "emperor": emperor,
                "object_count": len(objects),
                "rule_count": len(rule_codes),
                "material_count": sum(int(obj.get("material_count") or 0) for obj in objects),
                "rule_codes": rule_codes,
                "objects": objects,
            }
        )

    return {
        "report_type": "emperor_object_pool",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "postgres" if dsn else "in_memory",
        "item_code": item_code,
        "rule_filter": sorted(rule_filter),
        "missing_emperors": missing,
        "emperors": emperor_reports,
    }


def build_object_report(
    *,
    objects: tuple[str, ...],
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    dsn: str | None = None,
    emperors: tuple[str, ...] = (),
    rule_codes: tuple[str, ...] = (),
    object_rows: list[dict[str, Any]] | None = None,
    link_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not objects:
        raise I5BObjectPoolDetailError("at least one object is required")
    if object_rows is None or link_rows is None:
        if dsn is None:
            raise I5BObjectPoolDetailError("dsn is required when rows are not supplied")
        object_rows, link_rows = fetch_object_name_rows(
            dsn=dsn,
            item_code=item_code,
            cluster_formula=cluster_formula,
            object_names=objects,
            emperors=emperors,
            rule_codes=rule_codes,
        )
    row_report = _build_object_report_rows(object_names=objects, object_rows=object_rows, link_rows=link_rows)
    return {
        "report_type": "object_binding_score",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "postgres" if dsn else "in_memory",
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "object_names": list(objects),
        "emperor_filter": list(emperors),
        "rule_filter": sorted({rule for rule in rule_codes if rule}),
        "missing_objects": row_report["missing_objects"],
        "objects": row_report["objects"],
    }


def _attr_text(attrs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for attr in attrs:
        code = _text(attr.get("attr_code"))
        if not code:
            continue
        value = attr.get("value_text")
        if value in (None, ""):
            value = attr.get("value_num")
        display = f"{code}={_text(value)}" if value not in (None, "") else code
        parts.append(display)
    return "；".join(parts) or "-"


def _rule_summary(rules: list[dict[str, Any]]) -> str:
    if not rules:
        return "-"
    parts: list[str] = []
    for rule in rules:
        directions = ",".join(rule.get("directions") or [])
        suffix = f"/{directions}" if directions else ""
        parts.append(f"{rule['rule_label']}(`{rule['rule_code']}`){suffix}×{rule['material_count']}")
    return "；".join(parts)


def _material_line(material: dict[str, Any]) -> str:
    source = _text(material.get("src_key") or material.get("source_title") or "-")
    locator = _text(material.get("locator"))
    locator_text = f" {locator}" if locator else ""
    direction = _text(material.get("direction") or "-")
    note = _text(material.get("note")).replace("\n", " ").strip()
    return f"    - #{material.get('obj_src_id')} `{direction}` {source}{locator_text}: {note or '-'}"


def render_emperor_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# I5B 对象池详情",
        "",
        f"- item_code: `{report['item_code']}`",
        f"- source: `{report['source']}`",
        f"- generated_at: `{report['generated_at']}`",
    ]
    if report.get("missing_emperors"):
        lines.append(f"- missing_emperors: `{', '.join(report['missing_emperors'])}`")
    if report.get("rule_filter"):
        lines.append(f"- rule_filter: `{', '.join(report['rule_filter'])}`")
    lines.extend([""])

    for emperor in report["emperors"]:
        lines.extend(
            [
                f"## {emperor['emperor']}",
                "",
                f"- objects: `{emperor['object_count']}`",
                f"- rules: `{emperor['rule_count']}`",
                f"- materials: `{emperor['material_count']}`",
                "",
                "| 对象 | 类型/时期 | 属性 | rule 汇总 |",
                "|---|---|---|---|",
            ]
        )
        for obj in emperor["objects"]:
            type_period = "/".join(part for part in [_text(obj.get("obj_type")), _text(obj.get("obj_period"))] if part)
            lines.append(
                f"| {obj.get('obj_name')} `obj:{obj.get('obj_id')}` `emp_obj:{obj.get('emp_obj_id')}` | "
                f"{type_period or '-'} | {_attr_text(obj.get('attrs') or [])} | {_rule_summary(obj.get('rules') or [])} |"
            )
        if not emperor["objects"]:
            lines.append("| - | - | - | - |")
        lines.append("")
        for obj in emperor["objects"]:
            lines.append(f"### {obj.get('obj_name')} `obj:{obj.get('obj_id')}`")
            lines.append("")
            if obj.get("obj_note"):
                lines.append(f"- obj_note: {obj['obj_note']}")
            if obj.get("emp_obj_note"):
                lines.append(f"- emp_obj_note: {obj['emp_obj_note']}")
            if not obj.get("rules"):
                lines.append("- rules: -")
            for rule in obj.get("rules") or []:
                lines.append(f"- {rule['rule_label']} (`{rule['rule_code']}`), materials={rule['material_count']}")
                for material in rule.get("materials") or []:
                    lines.append(_material_line(material))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _score_text(rule: dict[str, Any]) -> str:
    raw_score = _text(rule.get("raw_score_total"))
    abs_score = _text(rule.get("abs_score_total"))
    if not raw_score and not abs_score:
        return "-"
    return f"raw={raw_score or '-'} / abs={abs_score or '-'}"


def _object_score_material_line(material: dict[str, Any]) -> str:
    source = _text(material.get("src_key") or material.get("source_title") or "-")
    locator = _text(material.get("locator"))
    locator_text = f" {locator}" if locator else ""
    status = _text(material.get("score_status") or "-")
    side = _text(material.get("side") or material.get("direction") or "-")
    raw_score = _text(material.get("raw_score") or "-")
    abs_score = _text(material.get("abs_score") or "-")
    note = _text(material.get("note")).replace("\n", " ").strip()
    return (
        f"    - #{material.get('obj_src_id')} `{status}` `{side}` raw={raw_score} abs={abs_score} "
        f"{source}{locator_text}: {note or '-'}"
    )


def render_object_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# I5B 对象绑定与 rule 计分",
        "",
        f"- item_code: `{report['item_code']}`",
        f"- cluster_formula: `{report['cluster_formula']}`",
        f"- source: `{report['source']}`",
        f"- generated_at: `{report['generated_at']}`",
    ]
    if report.get("missing_objects"):
        lines.append(f"- missing_objects: `{', '.join(report['missing_objects'])}`")
    if report.get("emperor_filter"):
        lines.append(f"- emperor_filter: `{', '.join(report['emperor_filter'])}`")
    if report.get("rule_filter"):
        lines.append(f"- rule_filter: `{', '.join(report['rule_filter'])}`")
    lines.append("")

    for obj in report["objects"]:
        lines.extend(
            [
                f"## {obj.get('obj_name')} `obj:{obj.get('obj_id')}`",
                "",
                f"- type/period: `{_text(obj.get('obj_type')) or '-'}/{_text(obj.get('obj_period')) or '-'}`",
                f"- attrs: {_attr_text(obj.get('attrs') or [])}",
                f"- bindings: `{obj.get('binding_count')}`",
                f"- rules: `{obj.get('rule_count')}`",
                f"- scored_materials: `{obj.get('scored_material_count')}` / materials: `{obj.get('material_count')}`",
            ]
        )
        if obj.get("obj_note"):
            lines.append(f"- obj_note: {obj['obj_note']}")
        lines.extend(
            [
                "",
                "| 皇帝 | emp_obj | rule | materials | scored | score |",
                "|---|---:|---|---:|---:|---|",
            ]
        )
        for binding in obj.get("bindings") or []:
            for rule in binding.get("rules") or []:
                lines.append(
                    f"| {binding.get('emperor')} | {binding.get('emp_obj_id')} | "
                    f"{rule.get('rule_label')}(`{rule.get('rule_code')}`) | "
                    f"{rule.get('material_count')} | {rule.get('scored_material_count')} | {_score_text(rule)} |"
                )
        if not obj.get("bindings"):
            lines.append("| - | - | - | - | - | - |")
        lines.append("")
        for binding in obj.get("bindings") or []:
            lines.append(f"### {binding.get('emperor')} `emp_obj:{binding.get('emp_obj_id')}`")
            if binding.get("emp_obj_note"):
                lines.append(f"- emp_obj_note: {binding['emp_obj_note']}")
            for rule in binding.get("rules") or []:
                lines.append(f"- {rule.get('rule_label')} (`{rule.get('rule_code')}`), score={_score_text(rule)}")
                for material in rule.get("materials") or []:
                    lines.append(_object_score_material_line(material))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    if report.get("report_type") == "object_binding_score":
        return render_object_markdown(report)
    return render_emperor_markdown(report)


def write_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_markdown(report), encoding="utf-8")
        return
    raise I5BObjectPoolDetailError(f"unknown output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show I5B object-pool details by emperor or object name.")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN", help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code; defaults to I5B.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Evidence cluster formula_code for object scoring.")
    parser.add_argument("--emperor", action="append", default=None, help="Emperor name; repeatable.")
    parser.add_argument("--object", action="append", default=None, help="Object name; repeatable. Enables object-centric output.")
    parser.add_argument(
        "--rules",
        nargs="+",
        action="append",
        default=None,
        metavar="RULE",
        help="Only show materials linked to these rule_code values; repeatable.",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown", help="Output format.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output path; stdout when omitted.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rule_codes = tuple(rule for group in (args.rules or []) for rule in group)
        if args.object:
            report = build_object_report(
                objects=tuple(args.object),
                item_code=args.item_code,
                cluster_formula=args.cluster_formula,
                dsn=resolve_dsn(args.dsn_env),
                emperors=tuple(args.emperor or ()),
                rule_codes=rule_codes,
            )
        else:
            if not args.emperor:
                parser.error("--emperor is required unless --object is supplied")
            report = build_detail_report(
                emperors=tuple(args.emperor),
                item_code=args.item_code,
                dsn=resolve_dsn(args.dsn_env),
                rule_codes=rule_codes,
            )
    except (EvidenceClusterWorkbenchError, I5BObjectPoolDetailError) as exc:
        parser.error(str(exc))

    if args.output:
        write_report(args.output, report, output_format=args.format)
    elif args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
