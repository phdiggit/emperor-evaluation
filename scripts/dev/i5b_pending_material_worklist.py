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

from scripts.build.i5b_item_result_calculator import DEFAULT_CLUSTER_FORMULA, DEFAULT_ITEM_CODE  # noqa: E402
from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.i5b_factor_table_sync import dump_db_factor_options  # noqa: E402


DEFAULT_OUTPUT = ROOT / ".tmp" / "i5b" / "i5b_pending_material_worklist.json"
COMMON_FACTOR_KEYS = ("attribution_factor", "source_factor", "context_factor")
RULE_FACTOR_KEYS: dict[str, dict[str, tuple[str, ...]]] = {
    "talent_discovery": {
        "positive": ("discovery_level", "talent_quality_factor", "channel_factor", *COMMON_FACTOR_KEYS),
        "negative": ("discovery_level", "talent_quality_factor", "channel_factor", *COMMON_FACTOR_KEYS),
    },
    "appointment_trust": {
        "positive": ("trust_depth", "object_weight", "trust_validity", "continuity_factor", *COMMON_FACTOR_KEYS),
        "negative": ("trust_depth", "object_weight", "trust_validity", "continuity_factor", *COMMON_FACTOR_KEYS),
    },
    "delegation": {
        "positive": ("authorization_intensity", "person_post_fit", "result_feedback", *COMMON_FACTOR_KEYS),
        "negative": ("authorization_intensity", "person_post_fit", "result_feedback", *COMMON_FACTOR_KEYS),
    },
    "team_building": {
        "positive": (),
        "negative": (),
        "mixed": (),
        "neutral": (),
    },
    "tolerate_talent": {
        "positive": ("feedback_entry", "expression_safety", "protection_repair", "object_weight", *COMMON_FACTOR_KEYS),
        "negative": ("handling_severity", "target_fault_factor", "object_weight", *COMMON_FACTOR_KEYS),
    },
    "anti_nepotism": {
        "positive": ("selection_openness", "institutionalization", "office_weight", *COMMON_FACTOR_KEYS),
        "negative": ("favoritism_intensity", "office_weight", "displacement_harm", *COMMON_FACTOR_KEYS),
    },
}
ACTION_OPTIONS = ("score", "supporting_only", "exclude")


@dataclass(frozen=True)
class PendingMaterialRow:
    emperor: str
    rule_code: str
    obj_src_id: int
    direction: str
    emp_obj_id: int
    obj_id: int
    obj_type: str
    obj_period: str
    obj_name: str
    src_key: str
    title: str
    author: str
    dynasty: str
    volume: str
    locator: str
    source_url: str
    obj_src_note: str
    source_note: str


def row_to_dict(row: PendingMaterialRow) -> dict[str, object]:
    return {
        "emperor": row.emperor,
        "rule_code": row.rule_code,
        "obj_src_id": row.obj_src_id,
        "direction": row.direction,
        "emp_obj_id": row.emp_obj_id,
        "obj_id": row.obj_id,
        "obj_type": row.obj_type,
        "obj_period": row.obj_period,
        "obj_name": row.obj_name,
        "src_key": row.src_key,
        "title": row.title,
        "author": row.author,
        "dynasty": row.dynasty,
        "volume": row.volume,
        "locator": row.locator,
        "source_url": row.source_url,
        "obj_src_note": row.obj_src_note,
        "source_note": row.source_note,
    }


def group_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        emperor = str(row.get("emperor") or "")
        rule_code = str(row.get("rule_code") or "")
        groups.setdefault((emperor, rule_code), []).append(dict(row))
    result: list[dict[str, object]] = []
    for (emperor, rule_code), items in sorted(groups.items()):
        items.sort(key=lambda row: int(row.get("obj_src_id") or 0))
        result.append(
            {
                "emperor": emperor,
                "rule_code": rule_code,
                "material_count": len(items),
                "pending_material_ids": [int(row["obj_src_id"]) for row in items],
                "materials": items,
            }
        )
    return result


def _factor_option_key(row: Mapping[str, object]) -> tuple[str, str]:
    return (str(row.get("rule_code") or ""), str(row.get("factor_name") or ""))


def build_factor_option_catalog(rows: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], list[dict[str, object]]]:
    catalog: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        key = _factor_option_key(row)
        if not key[1]:
            continue
        catalog.setdefault(key, []).append(
            {
                "factor_option_id": row.get("factor_option_id"),
                "label": row.get("label"),
                "value_num": row.get("value_num"),
                "source_doc": row.get("source_doc"),
                "source_line": row.get("source_line"),
            }
        )
    for values in catalog.values():
        values.sort(key=lambda item: (str(item.get("source_doc") or ""), int(item.get("source_line") or 0), str(item.get("value_num") or ""), str(item.get("label") or "")))
    return catalog


def factor_keys_for_material(rule_code: str, direction: str) -> tuple[str, ...]:
    by_direction = RULE_FACTOR_KEYS.get(rule_code, {})
    if direction in by_direction:
        return by_direction[direction]
    if direction == "mixed":
        return tuple(dict.fromkeys((*by_direction.get("positive", ()), *by_direction.get("negative", ()))))
    return by_direction.get("positive", ())


def factor_option_candidates(
    catalog: Mapping[tuple[str, str], Sequence[Mapping[str, object]]],
    *,
    rule_code: str,
    factor_name: str,
) -> list[dict[str, object]]:
    rows = [dict(row) for row in catalog.get(("", factor_name), ())]
    rows.extend(dict(row) for row in catalog.get((rule_code, factor_name), ()))
    return rows


def factor_patch_template(
    row: Mapping[str, object],
    catalog: Mapping[tuple[str, str], Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    rule_code = str(row.get("rule_code") or "")
    direction = str(row.get("direction") or "")
    factor_keys = factor_keys_for_material(rule_code, direction)
    side = direction if direction in {"positive", "negative"} else ""
    return {
        "target_action": "review",
        "action_options": list(ACTION_OPTIONS),
        "side": side,
        "side_options": ["positive", "negative"],
        "factor_keys": list(factor_keys),
        "factor_refs": {factor_name: {"label": ""} for factor_name in factor_keys},
        "factor_option_candidates": {
            factor_name: factor_option_candidates(catalog, rule_code=rule_code, factor_name=factor_name)
            for factor_name in factor_keys
        },
        "patch_note": "",
        "remove_from_pending": True,
    }


def attach_factor_templates(
    rows: Sequence[Mapping[str, object]],
    factor_options: Sequence[Mapping[str, object]] = (),
) -> list[dict[str, object]]:
    catalog = build_factor_option_catalog(factor_options)
    result: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        item["factor_patch_template"] = factor_patch_template(item, catalog)
        result.append(item)
    return result


def suggest_batches(groups: Sequence[Mapping[str, object]], *, batch_size: int) -> list[dict[str, object]]:
    if batch_size <= 0:
        return []
    batches: list[dict[str, object]] = []
    current_groups: list[dict[str, object]] = []
    current_count = 0
    for group in groups:
        material_count = int(group.get("material_count") or 0)
        if current_groups and current_count + material_count > batch_size:
            batches.append(
                {
                    "batch_id": f"pending_material_batch_{len(batches) + 1:02d}",
                    "material_count": current_count,
                    "groups": current_groups,
                }
            )
            current_groups = []
            current_count = 0
        current_groups.append(dict(group))
        current_count += material_count
    if current_groups:
        batches.append(
            {
                "batch_id": f"pending_material_batch_{len(batches) + 1:02d}",
                "material_count": current_count,
                "groups": current_groups,
            }
        )
    return batches


def build_report_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    batch_size: int = 40,
    factor_options: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    templated_rows = attach_factor_templates(rows, factor_options)
    ordered_rows = sorted((dict(row) for row in templated_rows), key=lambda row: (str(row.get("emperor") or ""), str(row.get("rule_code") or ""), int(row.get("obj_src_id") or 0)))
    groups = group_rows(ordered_rows)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ok": True,
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "pending_cluster_count": len(groups),
        "pending_material_count": len(ordered_rows),
        "groups": groups,
        "suggested_batches": suggest_batches(groups, batch_size=batch_size),
    }


def fetch_pending_material_rows(
    *,
    dsn: str,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    emperors: Sequence[str] = (),
    rule_codes: Sequence[str] = (),
) -> list[dict[str, object]]:
    clauses = ["i.item_code = %s", "c.formula_code = %s", "d.formula_code = %s"]
    params: list[object] = [item_code, cluster_formula, cluster_formula]
    if emperors:
        clauses.append("e.name = any(%s)")
        params.append(list(emperors))
    if rule_codes:
        clauses.append("er.rule_code = any(%s)")
        params.append(list(rule_codes))
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                with pending as (
                    select
                        e.name as emperor,
                        er.rule_code,
                        (jsonb_array_elements_text(d.calc_detail->'pending_material_ids'))::int as obj_src_id
                      from evd_cluster_calc_details d
                      join evd_clusters c on c.id = d.cluster_id
                      join emps e on e.id = c.emp_id
                      join eval_items i on i.id = c.item_id
                      join eval_rules er on er.id = c.rule_id
                     where {' and '.join(clauses)}
                )
                select
                    p.emperor,
                    p.rule_code,
                    p.obj_src_id,
                    os.direction,
                    os.emp_obj_id,
                    ro.id as obj_id,
                    ro.obj_type,
                    ro.period as obj_period,
                    ro.name as obj_name,
                    sd.src_key,
                    sd.title,
                    sd.author,
                    sd.dynasty,
                    sd.volume,
                    sd.locator,
                    sd.url,
                    os.note as obj_src_note,
                    sd.note as source_note
                  from pending p
                  join obj_srcs os on os.id = p.obj_src_id
                  join raw_objs ro on ro.id = os.obj_id
                  join src_docs sd on sd.id = os.doc_id
                 order by p.emperor, p.rule_code, p.obj_src_id
                """,
                tuple(params),
            )
            rows = [
                row_to_dict(
                    PendingMaterialRow(
                        emperor=str(row[0]),
                        rule_code=str(row[1]),
                        obj_src_id=int(row[2]),
                        direction=str(row[3]),
                        emp_obj_id=int(row[4]),
                        obj_id=int(row[5]),
                        obj_type=str(row[6]),
                        obj_period=str(row[7]),
                        obj_name=str(row[8]),
                        src_key=str(row[9]),
                        title=str(row[10] or ""),
                        author=str(row[11] or ""),
                        dynasty=str(row[12] or ""),
                        volume=str(row[13] or ""),
                        locator=str(row[14] or ""),
                        source_url=str(row[15] or ""),
                        obj_src_note=str(row[16] or ""),
                        source_note=str(row[17] or ""),
                    )
                )
                for row in cur.fetchall()
            ]
    return rows


def build_report(
    *,
    dsn: str,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    emperors: Sequence[str] = (),
    rule_codes: Sequence[str] = (),
    batch_size: int = 40,
) -> dict[str, object]:
    rows = fetch_pending_material_rows(
        dsn=dsn,
        item_code=item_code,
        cluster_formula=cluster_formula,
        emperors=tuple(emperors),
        rule_codes=tuple(rule_codes),
    )
    factor_options = dump_db_factor_options(dsn, item_code=item_code, formula_code=cluster_formula)
    return build_report_from_rows(
        rows,
        item_code=item_code,
        cluster_formula=cluster_formula,
        batch_size=batch_size,
        factor_options=factor_options,
    )


def render_markdown(report: Mapping[str, object]) -> str:
    groups = report.get("groups") if isinstance(report.get("groups"), list) else []
    batches = report.get("suggested_batches") if isinstance(report.get("suggested_batches"), list) else []
    lines = [
        "# I5B Pending Material Worklist",
        "",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- item_code: `{report.get('item_code') or ''}`",
        f"- cluster_formula: `{report.get('cluster_formula') or ''}`",
        f"- pending_clusters: `{report.get('pending_cluster_count') or 0}`",
        f"- pending_materials: `{report.get('pending_material_count') or 0}`",
        "",
        "## Suggested Batches",
        "",
    ]
    if batches:
        lines.extend(["| batch | materials | groups |", "| --- | ---: | --- |"])
        for batch in batches:
            if not isinstance(batch, Mapping):
                continue
            batch_groups = batch.get("groups") if isinstance(batch.get("groups"), list) else []
            labels = "；".join(f"{item.get('emperor')}/{item.get('rule_code')}" for item in batch_groups if isinstance(item, Mapping))
            lines.append(f"| `{batch.get('batch_id')}` | {batch.get('material_count') or 0} | {labels} |")
    else:
        lines.append("- 无")
    lines.extend(["", "## Pending Groups", ""])
    if groups:
        for group in groups:
            if not isinstance(group, Mapping):
                continue
            lines.extend(
                [
                    f"### {group.get('emperor')}/{group.get('rule_code')}",
                    "",
                    "| obj_src_id | direction | object | source | note |",
                    "| ---: | --- | --- | --- | --- |",
                ]
            )
            materials = group.get("materials") if isinstance(group.get("materials"), list) else []
            for row in materials:
                if not isinstance(row, Mapping):
                    continue
                source = " ".join(str(row.get(key) or "") for key in ("title", "volume", "locator")).strip()
                obj = f"{row.get('obj_name') or ''}({row.get('obj_id') or ''})"
                note = str(row.get("obj_src_note") or "").replace("|", " / ")
                lines.append(
                    f"| {row.get('obj_src_id')} | {row.get('direction') or ''} | {obj} | {source} | {note} |"
                )
            lines.append("")
    else:
        lines.append("- 无")
    return "\n".join(lines).rstrip() + "\n"


def write_batch_files(output_dir: Path, report: Mapping[str, object]) -> None:
    batches = report.get("suggested_batches") if isinstance(report.get("suggested_batches"), list) else []
    output_dir.mkdir(parents=True, exist_ok=True)
    for batch in batches:
        if not isinstance(batch, Mapping):
            continue
        batch_id = str(batch.get("batch_id") or "")
        if not batch_id:
            continue
        (output_dir / f"{batch_id}.json").write_text(
            json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (output_dir / "pending_material_batches.md").write_text(render_markdown(report), encoding="utf-8")


def write_output(path: Path | None, text: str) -> None:
    if path is None:
        sys.stdout.write(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only I5B pending-material worklists for factorization.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA)
    parser.add_argument("--emperor", action="append", default=[], help="Limit to one emperor; repeatable.")
    parser.add_argument("--rule-code", action="append", default=[], help="Limit to one rule_code; repeatable.")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-output-dir", type=Path, help="Optional directory for suggested batch JSON files.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        dsn=args.dsn or resolve_dsn(args.dsn_env),
        item_code=args.item_code,
        cluster_formula=args.cluster_formula,
        emperors=tuple(args.emperor),
        rule_codes=tuple(args.rule_code),
        batch_size=args.batch_size,
    )
    if args.batch_output_dir:
        write_batch_files(args.batch_output_dir, report)
    text = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else render_markdown(report)
    )
    write_output(args.output, text)
    print(
        json.dumps(
            {
                "output": str(args.output) if args.output else None,
                "pending_clusters": report["pending_cluster_count"],
                "pending_materials": report["pending_material_count"],
                "suggested_batches": len(report["suggested_batches"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
