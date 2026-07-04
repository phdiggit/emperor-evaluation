from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import DEFAULT_CLUSTER_FORMULA, DEFAULT_FORMULA_CODE, DEFAULT_ITEM_CODE  # noqa: E402
from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.i5b_factor_table_sync import dump_db_factor_options  # noqa: E402
from scripts.dev.i5b_pending_factor_patch import (  # noqa: E402
    build_report as build_material_patch_report,
    flatten_batch_materials,
    read_json,
    read_jsonl,
)
from scripts.dev.i5b_pending_material_worklist import (  # noqa: E402
    ACTION_OPTIONS,
    build_factor_option_catalog,
    factor_option_candidates,
    factor_patch_template,
    row_to_dict,
    suggest_batches,
    PendingMaterialRow,
)


DEFAULT_OUTPUT = ROOT / ".tmp" / "i5b" / "i5b_initial_factor_worklist.json"
DEFAULT_PROFILE_OUTPUT = ROOT / ".tmp" / "i5b" / "i5b_initial_factor_profile.json"
TEAM_BUILDING_RULE_CODE = "team_building"
TALENT_DISCOVERY_RULE_CODE = "talent_discovery"
TEAM_BUILDING_CLUSTER_FACTORS = ("role_complementarity_factor", "long_term_stability_factor")


class InitialFactorProfileError(ValueError):
    pass


def _text(value: object) -> str:
    return str(value or "").strip()


def _factor_option_catalog(rows: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], list[dict[str, object]]]:
    return build_factor_option_catalog(rows)


def _team_cluster_template(
    catalog: Mapping[tuple[str, str], Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    return {
        "required": True,
        "factor_keys": list(TEAM_BUILDING_CLUSTER_FACTORS),
        "team_factors": {factor_name: {"label": ""} for factor_name in TEAM_BUILDING_CLUSTER_FACTORS},
        "factor_option_candidates": {
            factor_name: factor_option_candidates(
                catalog,
                rule_code=TEAM_BUILDING_RULE_CODE,
                factor_name=factor_name,
            )
            for factor_name in TEAM_BUILDING_CLUSTER_FACTORS
        },
        "cluster_note": "",
    }


def _initial_factor_template(
    row: Mapping[str, object],
    catalog: Mapping[tuple[str, str], Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    rule_code = _text(row.get("rule_code"))
    if rule_code == TALENT_DISCOVERY_RULE_CODE:
        template = factor_patch_template(row, catalog)
        label = _text(row.get("talent_quality"))
        factor_refs = template.get("factor_refs")
        if label and isinstance(factor_refs, dict) and "talent_quality_factor" in factor_refs:
            factor_refs["talent_quality_factor"] = {"label": label}
        return template
    if rule_code != TEAM_BUILDING_RULE_CODE:
        return factor_patch_template(row, catalog)
    factor_name = "talent_quality_factor"
    label = _text(row.get("talent_quality"))
    return {
        "target_action": "review",
        "action_options": list(ACTION_OPTIONS),
        "side": "positive",
        "side_options": ["positive", "negative"],
        "factor_keys": [factor_name],
        "factor_refs": {factor_name: {"label": label}},
        "factor_option_candidates": {
            factor_name: factor_option_candidates(
                catalog,
                rule_code=TEAM_BUILDING_RULE_CODE,
                factor_name=factor_name,
            )
        },
        "patch_note": "",
        "remove_from_pending": False,
    }


def attach_initial_templates(
    rows: Sequence[Mapping[str, object]],
    factor_options: Sequence[Mapping[str, object]] = (),
) -> list[dict[str, object]]:
    catalog = _factor_option_catalog(factor_options)
    result: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        item["factor_patch_template"] = _initial_factor_template(item, catalog)
        result.append(item)
    return result


def group_rows(
    rows: Sequence[Mapping[str, object]],
    factor_options: Sequence[Mapping[str, object]] = (),
) -> list[dict[str, object]]:
    catalog = _factor_option_catalog(factor_options)
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        emperor = _text(row.get("emperor"))
        rule_code = _text(row.get("rule_code"))
        groups.setdefault((emperor, rule_code), []).append(dict(row))
    result: list[dict[str, object]] = []
    for (emperor, rule_code), items in sorted(groups.items()):
        items.sort(key=lambda row: int(row.get("obj_src_id") or 0))
        group: dict[str, object] = {
            "emperor": emperor,
            "rule_code": rule_code,
            "material_count": len(items),
            "pending_material_ids": [int(row["obj_src_id"]) for row in items],
            "materials": items,
        }
        if rule_code == TEAM_BUILDING_RULE_CODE:
            group["cluster_patch_template"] = _team_cluster_template(catalog)
        result.append(group)
    return result


def build_report_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    batch_size: int = 40,
    factor_options: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    templated_rows = attach_initial_templates(rows, factor_options)
    ordered_rows = sorted(
        (dict(row) for row in templated_rows),
        key=lambda row: (_text(row.get("emperor")), _text(row.get("rule_code")), int(row.get("obj_src_id") or 0)),
    )
    groups = group_rows(ordered_rows, factor_options=factor_options)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ok": True,
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "initial_cluster_count": len(groups),
        "initial_material_count": len(ordered_rows),
        "groups": groups,
        "suggested_batches": suggest_batches(groups, batch_size=batch_size),
    }


def fetch_initial_material_rows(
    *,
    dsn: str,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    emperors: Sequence[str] = (),
    rule_codes: Sequence[str] = (),
    missing_calc_detail_only: bool = True,
    missing_result_only: bool = False,
    result_formula: str = DEFAULT_FORMULA_CODE,
) -> list[dict[str, object]]:
    clauses = ["i.item_code = %s"]
    params: list[object] = [item_code]
    if emperors:
        clauses.append("e.name = any(%s)")
        params.append(list(emperors))
    if rule_codes:
        clauses.append("r.rule_code = any(%s)")
        params.append(list(rule_codes))
    if missing_calc_detail_only:
        clauses.append("d.cluster_id is null")
    if missing_result_only:
        clauses.append("res.id is null")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select
                    e.name as emperor,
                    r.rule_code,
                    os.id as obj_src_id,
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
                    sd.note as source_note,
                    tq.value_text as talent_quality
                  from obj_srcs os
                  join emp_objs eo on eo.id = os.emp_obj_id
                  join emps e on e.id = eo.emp_id
                  join eval_items i on i.id = os.item_id
                  join eval_rules r on r.id = os.rule_id
                  join raw_objs ro on ro.id = os.obj_id
                  join src_docs sd on sd.id = os.doc_id
                  left join evd_clusters c
                    on c.emp_id = e.id
                   and c.item_id = i.id
                   and c.rule_id = r.id
                   and c.formula_code = %s
                  left join evd_cluster_calc_details d
                    on d.cluster_id = c.id
                   and d.formula_code = %s
                  left join emp_item_results res
                    on res.emp_id = e.id
                   and res.item_id = i.id
                   and res.formula_code = %s
                  left join lateral (
                      select oa.value_text
                        from obj_attrs oa
                       where oa.obj_id = ro.id
                         and oa.attr_code = 'talent_quality'
                         and btrim(oa.value_text) <> ''
                       order by
                         (oa.obj_src_id = os.id) desc,
                         oa.updated_at desc,
                         oa.id desc
                       limit 1
                  ) tq on true
                 where {' and '.join(clauses)}
                 order by e.sort_no nulls last, e.name, r.rule_code, os.id
                """,
                (cluster_formula, cluster_formula, result_formula, *params),
            )
            rows = []
            for row in cur.fetchall():
                item = row_to_dict(
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
                item["talent_quality"] = str(row[18] or "")
                rows.append(item)
    return rows


def build_worklist(
    *,
    dsn: str,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    emperors: Sequence[str] = (),
    rule_codes: Sequence[str] = (),
    batch_size: int = 40,
    missing_calc_detail_only: bool = True,
    missing_result_only: bool = False,
    result_formula: str = DEFAULT_FORMULA_CODE,
) -> dict[str, object]:
    rows = fetch_initial_material_rows(
        dsn=dsn,
        item_code=item_code,
        cluster_formula=cluster_formula,
        emperors=tuple(emperors),
        rule_codes=tuple(rule_codes),
        missing_calc_detail_only=missing_calc_detail_only,
        missing_result_only=missing_result_only,
        result_formula=result_formula,
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
        "# I5B Initial Factor Worklist",
        "",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- item_code: `{report.get('item_code') or ''}`",
        f"- cluster_formula: `{report.get('cluster_formula') or ''}`",
        f"- initial_clusters: `{report.get('initial_cluster_count') or 0}`",
        f"- initial_materials: `{report.get('initial_material_count') or 0}`",
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
            labels = "；".join(
                f"{item.get('emperor')}/{item.get('rule_code')}"
                for item in batch_groups
                if isinstance(item, Mapping)
            )
            lines.append(f"| `{batch.get('batch_id')}` | {batch.get('material_count') or 0} | {labels} |")
    else:
        lines.append("- 无")
    lines.extend(["", "## Initial Groups", ""])
    if groups:
        for group in groups:
            if not isinstance(group, Mapping):
                continue
            lines.extend(
                [
                    f"### {group.get('emperor')}/{group.get('rule_code')}",
                    "",
                    "| obj_src_id | direction | object | source | talent_quality | note |",
                    "| ---: | --- | --- | --- | --- | --- |",
                ]
            )
            materials = group.get("materials") if isinstance(group.get("materials"), list) else []
            for row in materials:
                if not isinstance(row, Mapping):
                    continue
                source = " ".join(str(row.get(key) or "") for key in ("title", "volume", "locator")).strip()
                obj = f"{row.get('obj_name') or ''}({row.get('obj_id') or ''})"
                note = _text(row.get("obj_src_note")).replace("|", " / ")
                lines.append(
                    f"| {row.get('obj_src_id')} | {row.get('direction') or ''} | {obj} | {source} | {row.get('talent_quality') or ''} | {note} |"
                )
            if group.get("cluster_patch_template"):
                lines.extend(["", "- team_building 需要额外填写 `team_factors`。"])
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
        batch_id = _text(batch.get("batch_id"))
        if not batch_id:
            continue
        (output_dir / f"{batch_id}.json").write_text(
            json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (output_dir / "initial_factor_batches.md").write_text(render_markdown(report), encoding="utf-8")


def write_output(path: Path | None, text: str) -> None:
    if path is None:
        sys.stdout.write(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _cluster_key(emperor: object, rule_code: object) -> tuple[str, str]:
    return (_text(emperor), _text(rule_code))


def _team_factor_labels(
    batch: Mapping[str, Any],
    patch_rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    groups = batch.get("groups") if isinstance(batch.get("groups"), list) else []
    required = {
        _cluster_key(group.get("emperor"), group.get("rule_code"))
        for group in groups
        if isinstance(group, Mapping) and group.get("rule_code") == TEAM_BUILDING_RULE_CODE
    }
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in patch_rows:
        if row.get("patch_type") != "cluster":
            continue
        key = _cluster_key(row.get("emperor"), row.get("rule_code"))
        result[key] = dict(row)
    missing = sorted(required - set(result))
    if missing:
        labels = ", ".join(f"{emperor}/{rule_code}" for emperor, rule_code in missing)
        raise InitialFactorProfileError(f"missing team_building cluster patch row(s): {labels}")
    return result


def _cluster_candidate_labels(group: Mapping[str, Any], factor_name: str) -> set[str]:
    template = group.get("cluster_patch_template")
    if not isinstance(template, Mapping):
        return set()
    candidates = template.get("factor_option_candidates")
    if not isinstance(candidates, Mapping):
        return set()
    rows = candidates.get(factor_name)
    if not isinstance(rows, list):
        return set()
    return {_text(row.get("label")) for row in rows if isinstance(row, Mapping) and _text(row.get("label"))}


def _validate_team_cluster_patch(group: Mapping[str, Any], patch: Mapping[str, Any]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    factors = patch.get("team_factors")
    if not isinstance(factors, Mapping):
        return [
            {
                "severity": "error",
                "status": "missing_team_factors",
                "emperor": group.get("emperor"),
                "rule_code": group.get("rule_code"),
            }
        ]
    for factor_name in TEAM_BUILDING_CLUSTER_FACTORS:
        ref = factors.get(factor_name)
        if not isinstance(ref, Mapping):
            issues.append(
                {
                    "severity": "error",
                    "status": "missing_team_factor_ref",
                    "factor": factor_name,
                    "emperor": group.get("emperor"),
                    "rule_code": group.get("rule_code"),
                }
            )
            continue
        label = _text(ref.get("label"))
        if not label:
            issues.append(
                {
                    "severity": "error",
                    "status": "missing_team_factor_label",
                    "factor": factor_name,
                    "emperor": group.get("emperor"),
                    "rule_code": group.get("rule_code"),
                }
            )
            continue
        labels = _cluster_candidate_labels(group, factor_name)
        if labels and label not in labels:
            issues.append(
                {
                    "severity": "error",
                    "status": "unknown_team_factor_label",
                    "factor": factor_name,
                    "label": label,
                    "emperor": group.get("emperor"),
                    "rule_code": group.get("rule_code"),
                }
            )
    return issues


def validate_initial_patch(batch: Mapping[str, Any], patch_rows: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    material_rows = [row for row in patch_rows if row.get("patch_type") != "cluster"]
    report = build_material_patch_report(batch, material_rows)
    issues = [dict(issue) for issue in report.get("issues", []) if isinstance(issue, Mapping)]
    team_patches = _team_factor_labels(batch, patch_rows)
    groups = batch.get("groups") if isinstance(batch.get("groups"), list) else []
    for group in groups:
        if not isinstance(group, Mapping) or group.get("rule_code") != TEAM_BUILDING_RULE_CODE:
            continue
        issues.extend(_validate_team_cluster_patch(group, team_patches[_cluster_key(group.get("emperor"), group.get("rule_code"))]))
    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    return {
        **report,
        "ok": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
        "cluster_patch_rows": len(team_patches),
    }


def _profile_material(row: Mapping[str, Any], material: Mapping[str, Any]) -> dict[str, object]:
    return {
        "obj_src_id": int(row["obj_src_id"]),
        "obj_id": material.get("obj_id"),
        "obj_key": str(material.get("obj_id") or ""),
        "obj_name": material.get("obj_name") or "",
        "obj_period": material.get("obj_period") or "",
        "direction": row.get("side") or material.get("direction") or "",
        "factors": dict(row.get("factor_refs") if isinstance(row.get("factor_refs"), Mapping) else {}),
    }


def _coverage_by_action(
    patch_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[int], list[int], list[int], list[int]]:
    covered: list[int] = []
    scored: list[int] = []
    supporting: list[int] = []
    excluded: list[int] = []
    for row in patch_rows:
        obj_src_id = int(row.get("obj_src_id") or 0)
        if not obj_src_id:
            continue
        covered.append(obj_src_id)
        action = _text(row.get("target_action"))
        if action == "score":
            scored.append(obj_src_id)
        elif action == "supporting_only":
            supporting.append(obj_src_id)
        elif action == "exclude":
            excluded.append(obj_src_id)
    return (
        list(dict.fromkeys(covered)),
        list(dict.fromkeys(scored)),
        list(dict.fromkeys(supporting)),
        list(dict.fromkeys(excluded)),
    )


def _cluster_note(emperor: str, rule_code: str, rows: Sequence[Mapping[str, Any]], team_patch: Mapping[str, Any] | None) -> str:
    patch_notes = [_text(row.get("patch_note")) for row in rows if _text(row.get("patch_note"))]
    cluster_note = _text(team_patch.get("cluster_note")) if isinstance(team_patch, Mapping) else ""
    notes = [cluster_note, *patch_notes]
    suffix = "；".join(note for note in notes if note)
    base = f"I5B initial factor profile: {emperor}/{rule_code}"
    return f"{base}；{suffix}" if suffix else base


def build_profile_from_patches(
    pairs: Sequence[tuple[Path, Mapping[str, Any], Sequence[Mapping[str, Any]]]],
    *,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
) -> dict[str, object]:
    grouped_rows: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    materials_by_id: dict[int, dict[str, Any]] = {}
    team_patches: dict[tuple[str, str], dict[str, Any]] = {}
    validations: list[dict[str, object]] = []
    for batch_path, batch, patch_rows in pairs:
        validation = validate_initial_patch(batch, patch_rows)
        validations.append({"batch": str(batch_path), **validation})
        if not validation["ok"]:
            raise InitialFactorProfileError(f"{batch_path}: initial factor patch validation failed")
        materials_by_id.update(flatten_batch_materials(batch))
        team_patches.update(_team_factor_labels(batch, patch_rows))
        for row in patch_rows:
            if row.get("patch_type") == "cluster":
                continue
            obj_src_id = int(row.get("obj_src_id") or 0)
            material = materials_by_id[obj_src_id]
            grouped_rows[(str(material["emperor"]), str(material["rule_code"]))].append(dict(row))

    clusters: list[dict[str, object]] = []
    skipped_groups: list[dict[str, object]] = []
    for (emperor, rule_code), rows in sorted(grouped_rows.items()):
        material_rows = {int(row["obj_src_id"]): materials_by_id[int(row["obj_src_id"])] for row in rows}
        covered, scored, supporting, excluded = _coverage_by_action(rows)
        scored_rows = [row for row in rows if _text(row.get("target_action")) == "score"]
        if not scored_rows:
            skipped_groups.append(
                {
                    "emperor": emperor,
                    "rule_code": rule_code,
                    "covered_material_ids": covered,
                    "reason": "no_scored_materials",
                }
            )
            continue
        team_patch = team_patches.get((emperor, rule_code))
        cluster: dict[str, object] = {
            "emperor": emperor,
            "rule_code": rule_code,
            "formula_code": cluster_formula,
            "note": _cluster_note(emperor, rule_code, rows, team_patch),
            "calc_note": "initial_factor_profile_from_object_chain",
            "material_ids": covered,
            "supporting_material_ids": supporting,
            "excluded_material_ids": excluded,
            "materials": [_profile_material(row, material_rows[int(row["obj_src_id"])]) for row in scored_rows],
        }
        if rule_code == TEAM_BUILDING_RULE_CODE:
            if not isinstance(team_patch, Mapping):
                raise InitialFactorProfileError(f"{emperor}/{rule_code}: missing team_building cluster patch")
            cluster["team_factors"] = dict(team_patch["team_factors"])
        clusters.append(cluster)

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "item_code": item_code,
        "formula_code": cluster_formula,
        "factor_source": "table",
        "clusters": clusters,
        "skipped_groups": skipped_groups,
        "source_batches": [str(path) for path, _, _ in pairs],
        "validation_count": len(validations),
    }


def load_batch_patch_pairs(batch_paths: Sequence[Path], patch_paths: Sequence[Path]) -> list[tuple[Path, dict[str, Any], list[dict[str, Any]]]]:
    if len(batch_paths) != len(patch_paths):
        raise InitialFactorProfileError("--batch and --patch counts must match")
    pairs: list[tuple[Path, dict[str, Any], list[dict[str, Any]]]] = []
    for batch_path, patch_path in zip(batch_paths, patch_paths, strict=True):
        pairs.append((batch_path, read_json(batch_path), read_jsonl(patch_path)))
    return pairs


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build initial I5B factor worklists and factor profiles from object-chain patches.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    worklist = subparsers.add_parser("worklist", help="Build read-only initial factorization worklist from obj_srcs.")
    worklist.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    worklist.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA)
    worklist.add_argument("--result-formula", default=DEFAULT_FORMULA_CODE)
    worklist.add_argument("--emperor", action="append", default=[], help="Limit to one emperor; repeatable.")
    worklist.add_argument("--rule-code", action="append", default=[], help="Limit to one rule_code; repeatable.")
    worklist.add_argument("--batch-size", type=int, default=40)
    worklist.add_argument("--include-existing-details", action="store_true", help="Include rows whose emperor/rule already has calc_detail.")
    worklist.add_argument("--missing-result-only", action="store_true", help="Only include emperors missing the I5B item result.")
    worklist.add_argument("--format", choices=("json", "markdown"), default="json")
    worklist.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    worklist.add_argument("--batch-output-dir", type=Path, help="Optional directory for suggested batch JSON files.")

    profile = subparsers.add_parser("patch-to-profile", help="Validate initial patches and write an i5b_factor_recalculator input profile.")
    profile.add_argument("--batch", type=Path, action="append", required=True)
    profile.add_argument("--patch", type=Path, action="append", required=True)
    profile.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    profile.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA)
    profile.add_argument("--output", type=Path, default=DEFAULT_PROFILE_OUTPUT)
    profile.add_argument("--validation-output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "worklist":
        report = build_worklist(
            dsn=args.dsn or resolve_dsn(args.dsn_env),
            item_code=args.item_code,
            cluster_formula=args.cluster_formula,
            emperors=tuple(args.emperor),
            rule_codes=tuple(args.rule_code),
            batch_size=args.batch_size,
            missing_calc_detail_only=not args.include_existing_details,
            missing_result_only=args.missing_result_only,
            result_formula=args.result_formula,
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
                    "initial_clusters": report["initial_cluster_count"],
                    "initial_materials": report["initial_material_count"],
                    "suggested_batches": len(report["suggested_batches"]),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "patch-to-profile":
        pairs = load_batch_patch_pairs(args.batch, args.patch)
        profile = build_profile_from_patches(
            pairs,
            item_code=args.item_code,
            cluster_formula=args.cluster_formula,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.validation_output:
            validations = []
            for batch_path, batch, patch_rows in pairs:
                validations.append({"batch": str(batch_path), **validate_initial_patch(batch, patch_rows)})
            args.validation_output.parent.mkdir(parents=True, exist_ok=True)
            args.validation_output.write_text(
                json.dumps(validations, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "clusters": len(profile["clusters"]),
                    "skipped_groups": len(profile["skipped_groups"]),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    raise InitialFactorProfileError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
