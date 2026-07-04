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

from scripts.build.i5b_item_result_calculator import DEFAULT_CLUSTER_FORMULA, DEFAULT_ITEM_CODE  # noqa: E402
from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.i5b_pending_factor_patch import build_report, flatten_batch_materials, read_json, read_jsonl  # noqa: E402


DEFAULT_OUTPUT = ROOT / ".tmp" / "i5b" / "i5b_pending_factor_patch_apply_report.json"


class PendingFactorPatchApplyError(ValueError):
    pass


def _int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, int)]


def _append_unique(values: list[int], item: int) -> list[int]:
    return list(dict.fromkeys([*values, item]))


def _remove_id(values: list[int], item: int) -> list[int]:
    return [value for value in values if value != item]


def _patch_row_note(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "obj_src_id": row.get("obj_src_id"),
        "target_action": row.get("target_action"),
        "side": row.get("side"),
        "patch_note": row.get("patch_note") or "",
    }


def material_entry_from_patch(row: Mapping[str, object], material: Mapping[str, object]) -> dict[str, object]:
    return {
        "obj_src_id": int(row["obj_src_id"]),
        "obj_key": str(material.get("obj_id") or ""),
        "obj_id": material.get("obj_id"),
        "obj_name": material.get("obj_name") or "",
        "side": row.get("side") or material.get("direction") or "",
        "factor_refs": dict(row.get("factor_refs") if isinstance(row.get("factor_refs"), Mapping) else {}),
        "patch_note": row.get("patch_note") or "",
    }


def apply_patch_rows_to_detail(
    calc_detail: Mapping[str, object],
    patch_rows: Sequence[Mapping[str, object]],
    materials_by_id: Mapping[int, Mapping[str, object]],
) -> dict[str, object]:
    detail = dict(calc_detail)
    materials = [dict(row) for row in detail.get("materials", []) if isinstance(row, Mapping)]
    covered = _int_list(detail.get("covered_material_ids"))
    scored = _int_list(detail.get("scored_material_ids"))
    supporting = _int_list(detail.get("supporting_material_ids"))
    pending = _int_list(detail.get("pending_material_ids"))
    excluded = _int_list(detail.get("excluded_material_ids"))
    review_rows = [dict(row) for row in detail.get("pending_factor_patch_reviews", []) if isinstance(row, Mapping)]

    for row in patch_rows:
        obj_src_id = int(row["obj_src_id"])
        material = materials_by_id[obj_src_id]
        action = str(row.get("target_action") or "")
        covered = _append_unique(covered, obj_src_id)
        pending = _remove_id(pending, obj_src_id)
        scored = _remove_id(scored, obj_src_id)
        supporting = _remove_id(supporting, obj_src_id)
        excluded = _remove_id(excluded, obj_src_id)
        materials = [item for item in materials if item.get("obj_src_id") != obj_src_id]

        if action == "score":
            materials.append(material_entry_from_patch(row, material))
            scored = _append_unique(scored, obj_src_id)
        elif action == "supporting_only":
            supporting = _append_unique(supporting, obj_src_id)
        elif action == "exclude":
            excluded = _append_unique(excluded, obj_src_id)
        else:
            raise PendingFactorPatchApplyError(f"{obj_src_id}: unsupported target_action {action}")
        review_rows = [item for item in review_rows if item.get("obj_src_id") != obj_src_id]
        review_rows.append(_patch_row_note(row))

    materials.sort(key=lambda item: int(item.get("obj_src_id") or 0))
    detail["materials"] = materials
    detail["covered_material_ids"] = list(dict.fromkeys(covered))
    detail["scored_material_ids"] = list(dict.fromkeys(scored))
    detail["supporting_material_ids"] = list(dict.fromkeys(supporting))
    detail["pending_material_ids"] = list(dict.fromkeys(pending))
    if excluded:
        detail["excluded_material_ids"] = list(dict.fromkeys(excluded))
    elif "excluded_material_ids" in detail:
        detail["excluded_material_ids"] = []
    detail["pending_factor_patch_reviews"] = review_rows
    detail["pending_factor_patch_apply"] = {
        "status": "applied",
        "applied_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return detail


def load_batch_patch_pairs(batch_paths: Sequence[Path], patch_paths: Sequence[Path]) -> list[tuple[Path, dict[str, Any], list[dict[str, Any]]]]:
    if len(batch_paths) != len(patch_paths):
        raise PendingFactorPatchApplyError("--batch and --patch counts must match")
    pairs: list[tuple[Path, dict[str, Any], list[dict[str, Any]]]] = []
    for batch_path, patch_path in zip(batch_paths, patch_paths, strict=True):
        batch = read_json(batch_path)
        patch_rows = read_jsonl(patch_path)
        validation = build_report(batch, patch_rows)
        if not validation["ok"]:
            raise PendingFactorPatchApplyError(f"{patch_path}: patch validation failed")
        pairs.append((batch_path, batch, patch_rows))
    return pairs


def _group_patch_rows(batch: Mapping[str, Any], patch_rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    materials = flatten_batch_materials(batch)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in patch_rows:
        obj_src_id = int(row["obj_src_id"])
        material = materials[obj_src_id]
        grouped[(str(material["emperor"]), str(material["rule_code"]))].append(dict(row))
    return grouped


def _fetch_detail_row(cur: psycopg.Cursor, *, item_code: str, cluster_formula: str, emperor: str, rule_code: str) -> dict[str, Any]:
    cur.execute(
        """
        select d.cluster_id, d.material_ids, d.calc_note, d.calc_detail
          from evd_cluster_calc_details d
          join evd_clusters c on c.id = d.cluster_id
          join emps e on e.id = c.emp_id
          join eval_items i on i.id = c.item_id
          join eval_rules r on r.id = c.rule_id
         where i.item_code = %s
           and c.formula_code = %s
           and d.formula_code = %s
           and e.name = %s
           and r.rule_code = %s
        """,
        (item_code, cluster_formula, cluster_formula, emperor, rule_code),
    )
    row = cur.fetchone()
    if row is None:
        raise PendingFactorPatchApplyError(f"missing calc_detail row: {emperor}/{rule_code}")
    return {"cluster_id": int(row[0]), "material_ids": list(row[1] or []), "calc_note": row[2] or "", "calc_detail": dict(row[3] or {})}


def apply_patches(
    *,
    dsn: str,
    pairs: Sequence[tuple[Path, Mapping[str, Any], Sequence[Mapping[str, Any]]]],
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    write: bool = False,
) -> dict[str, object]:
    updates: list[dict[str, object]] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for batch_path, batch, patch_rows in pairs:
                materials_by_id = flatten_batch_materials(batch)
                for (emperor, rule_code), rows in sorted(_group_patch_rows(batch, patch_rows).items()):
                    detail_row = _fetch_detail_row(
                        cur,
                        item_code=item_code,
                        cluster_formula=cluster_formula,
                        emperor=emperor,
                        rule_code=rule_code,
                    )
                    calc_detail = apply_patch_rows_to_detail(detail_row["calc_detail"], rows, materials_by_id)
                    material_ids = list(dict.fromkeys(_int_list(calc_detail.get("covered_material_ids"))))
                    scored_ids = _int_list(calc_detail.get("scored_material_ids"))
                    supporting_ids = _int_list(calc_detail.get("supporting_material_ids"))
                    calc_note = str(detail_row["calc_note"] or "")
                    if "pending factor patch applied" not in calc_note:
                        calc_note = (calc_note + " | " if calc_note else "") + "pending factor patch applied"
                    if write:
                        cur.execute(
                            """
                            update evd_cluster_calc_details
                               set material_ids = %s,
                                   covered_material_ids = %s,
                                   scored_material_ids = %s,
                                   supporting_material_ids = %s,
                                   calc_note = %s,
                                   calc_detail = %s::jsonb,
                                   updated_at = now()
                             where cluster_id = %s
                            """,
                            (
                                material_ids,
                                material_ids,
                                scored_ids,
                                supporting_ids,
                                calc_note,
                                json.dumps(calc_detail, ensure_ascii=False, sort_keys=True),
                                detail_row["cluster_id"],
                            ),
                        )
                    updates.append(
                        {
                            "batch": str(batch_path),
                            "emperor": emperor,
                            "rule_code": rule_code,
                            "cluster_id": detail_row["cluster_id"],
                            "patch_rows": len(rows),
                            "pending_remaining": len(_int_list(calc_detail.get("pending_material_ids"))),
                            "scored_materials": len(scored_ids),
                            "supporting_materials": len(supporting_ids),
                            "excluded_materials": len(_int_list(calc_detail.get("excluded_material_ids"))),
                        }
                    )
        if write:
            conn.commit()
        else:
            conn.rollback()
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dry_run": not write,
        "updated_clusters": len(updates),
        "updates": updates,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply validated I5B pending factor patches into calc_detail rows.")
    parser.add_argument("--batch", type=Path, action="append", required=True)
    parser.add_argument("--patch", type=Path, action="append", required=True)
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--write", action="store_true", help="Commit calc_detail updates. Omit for rollback dry-run.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = apply_patches(
        dsn=args.dsn or resolve_dsn(args.dsn_env),
        pairs=load_batch_patch_pairs(args.batch, args.patch),
        item_code=args.item_code,
        cluster_formula=args.cluster_formula,
        write=args.write,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "dry_run": report["dry_run"],
                "output": str(args.output),
                "updated_clusters": report["updated_clusters"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
