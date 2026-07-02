from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import (  # noqa: E402
    DEFAULT_CLUSTER_FORMULA,
    DEFAULT_ITEM_CODE,
)
from scripts.dev.evidence_cluster_workbench import (  # noqa: E402
    fetch_cluster_calc_detail_rows,
    fetch_materials,
    resolve_dsn,
)
from scripts.dev.i5b_rule_evidence_unit_preview import (  # noqa: E402
    build_preview,
    render_markdown as render_preview_markdown,
)


SOURCE_METHOD = "candidate_from_calc_detail"
REVIEW_STATUS = "needs_review"


def _text(value: object) -> str:
    return str(value or "").strip()


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _material_id(material: Mapping[str, object]) -> int | None:
    return _int_or_none(material.get("obj_src_id") or material.get("material_id"))


def _material_side(material: Mapping[str, object], source_row: Mapping[str, object]) -> str:
    side = _text(material.get("side"))
    if side in {"positive", "negative", "neutral", "mixed"}:
        return side
    direction = _text(source_row.get("direction"))
    if direction in {"positive", "negative", "neutral", "mixed"}:
        return direction
    return "mixed"


def _obj_type(material: Mapping[str, object], source_row: Mapping[str, object]) -> str:
    return _text(source_row.get("obj_type") or material.get("obj_type"))


def _obj_name(material: Mapping[str, object], source_row: Mapping[str, object]) -> str:
    return _text(source_row.get("obj_name") or material.get("obj_name") or material.get("object_name") or material.get("obj_key"))


def _obj_id(material: Mapping[str, object], source_row: Mapping[str, object]) -> int | None:
    return _int_or_none(source_row.get("obj_id") or material.get("obj_id") or material.get("obj_key"))


def _source_lookup(materials_report: Mapping[str, object]) -> dict[int, dict[str, object]]:
    lookup: dict[int, dict[str, object]] = {}
    rules = materials_report.get("rules")
    if not isinstance(rules, Mapping):
        return lookup
    for rows in rules.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            material_id = _int_or_none(row.get("obj_src_id"))
            if material_id is not None:
                lookup[material_id] = row
    return lookup


def candidate_scoring_role(*, rule_code: str, side: str, obj_type: str, obj_name: str) -> str:
    if obj_type == "mechanism":
        return "mechanism_context"
    if obj_type == "event":
        return "event_context"
    if obj_type == "group":
        return "group_context"

    if rule_code == "anti_nepotism":
        if side == "positive":
            return "anti_nepotism_resisted_actor"
        if obj_type == "person" and obj_name.startswith("武"):
            return "nepotistic_beneficiary"
        if obj_type == "person" and obj_name in {"张易之", "张昌宗", "薛怀义"}:
            return "favorite_beneficiary"
        return "appointment_interferer"

    if rule_code == "tolerate_talent":
        if side == "positive":
            return "protected_talent" if obj_type == "person" else "source_context"
        return "harmed_talent" if obj_type == "person" else "expression_safety_unit"

    if rule_code == "talent_discovery":
        return "discovered_talent" if side != "negative" else "missed_talent"
    if rule_code == "appointment_trust":
        return "trusted_minister" if side != "negative" else "misappointed_person"
    if rule_code == "delegation":
        return "delegated_actor" if side != "negative" else "misdelegated_actor"
    if rule_code == "team_building":
        return "team_member" if side != "negative" else "negative_team_member"
    return "source_context"


def candidate_warnings(*, rule_code: str, obj_type: str, scoring_role: str) -> list[str]:
    warnings = ["chain_key_defaults_to_obj_src; review and merge same causal chain manually"]
    if scoring_role.endswith("_context"):
        warnings.append("context_role_is_currently_scored; likely needs carrier reassignment")
    if rule_code == "anti_nepotism" and obj_type in {"event", "group", "mechanism"}:
        warnings.append("anti_nepotism_should_use_person_carrier")
    if rule_code == "tolerate_talent" and obj_type in {"event", "group", "mechanism"}:
        warnings.append("tolerate_talent_should_use_person_carrier")
    return warnings


def scored_obj_payload(
    *,
    material: Mapping[str, object],
    source_row: Mapping[str, object],
) -> dict[str, object]:
    material_id = _material_id(material)
    payload: dict[str, object] = {
        "obj_id": _obj_id(material, source_row),
        "name": _obj_name(material, source_row),
        "obj_type": _obj_type(material, source_row),
        "obj_src_id": material_id,
        "emp_obj_id": _int_or_none(source_row.get("emp_obj_id")),
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def supporting_member_payload(
    *,
    row: Mapping[str, object],
    member_role: str = "source_context",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "role": member_role,
        "obj_id": _int_or_none(row.get("obj_id")),
        "name": _text(row.get("obj_name")),
        "obj_type": _text(row.get("obj_type")),
        "obj_src_id": _int_or_none(row.get("obj_src_id")),
        "source_method": SOURCE_METHOD,
        "review_status": REVIEW_STATUS,
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def _cluster_detail(row: Mapping[str, object]) -> Mapping[str, object]:
    detail = row.get("calc_detail")
    return detail if isinstance(detail, Mapping) else {}


def _scored_materials(row: Mapping[str, object]) -> list[Mapping[str, object]]:
    detail = _cluster_detail(row)
    materials = detail.get("materials")
    if not isinstance(materials, list):
        return []
    return [material for material in materials if isinstance(material, Mapping)]


def _supporting_material_ids(row: Mapping[str, object]) -> set[int]:
    detail = _cluster_detail(row)
    raw_ids = detail.get("supporting_material_ids") or row.get("supporting_material_ids") or []
    if not isinstance(raw_ids, list):
        return set()
    return {material_id for value in raw_ids if (material_id := _int_or_none(value)) is not None}


def build_candidate_payload(
    *,
    emperor: str,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    cluster_rows: Mapping[tuple[str, str], Mapping[str, object]],
    materials_report: Mapping[str, object],
    rule_codes: Sequence[str] = (),
) -> dict[str, object]:
    material_lookup = _source_lookup(materials_report)
    rule_filter = {rule for rule in rule_codes if rule}
    units: list[dict[str, object]] = []
    supporting_materials: list[dict[str, object]] = []

    for (row_emperor, rule_code), cluster_row in sorted(cluster_rows.items()):
        if row_emperor != emperor:
            continue
        if rule_filter and rule_code not in rule_filter:
            continue
        supporting_ids = _supporting_material_ids(cluster_row)
        scored_obj_ids_by_unit: dict[int, list[dict[str, object]]] = {}
        for material in _scored_materials(cluster_row):
            material_id = _material_id(material)
            source_row = material_lookup.get(material_id or -1, {})
            side = _material_side(material, source_row)
            obj_type = _obj_type(material, source_row)
            obj_name = _obj_name(material, source_row)
            scoring_role = candidate_scoring_role(
                rule_code=rule_code,
                side=side,
                obj_type=obj_type,
                obj_name=obj_name,
            )
            obj_id = _obj_id(material, source_row)
            unit = {
                "rule_code": rule_code,
                "causal_chain_key": f"i5b:{rule_code}:obj_src:{material_id or 'unknown'}",
                "direction": side,
                "scoring_role": scoring_role,
                "score_mode": "shadow",
                "source_method": SOURCE_METHOD,
                "review_status": REVIEW_STATUS,
                "review_note": "",
                "scored_obj": scored_obj_payload(material=material, source_row=source_row),
                "current_calc": {
                    "obj_src_id": material_id,
                    "raw_score": _text(material.get("raw_score")),
                    "abs_score": _text(material.get("abs_score")),
                    "side": side,
                    "factor_refs": material.get("factor_refs") or {},
                    "factor_values": material.get("factor_values") or {},
                },
                "members": [],
                "candidate_warnings": candidate_warnings(
                    rule_code=rule_code,
                    obj_type=obj_type,
                    scoring_role=scoring_role,
                ),
            }
            if obj_id is not None:
                scored_obj_ids_by_unit.setdefault(obj_id, []).append(unit)
            units.append(unit)

        for material_id in sorted(supporting_ids):
            row = material_lookup.get(material_id)
            if row is None:
                supporting_materials.append({"obj_src_id": material_id, "review_status": REVIEW_STATUS})
                continue
            member = supporting_member_payload(row=row)
            obj_id = _int_or_none(row.get("obj_id"))
            attached = False
            if obj_id is not None:
                for unit in scored_obj_ids_by_unit.get(obj_id, []):
                    unit["members"].append(member)
                    attached = True
            if not attached:
                supporting_materials.append(member)

    payload: dict[str, object] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "postgres_calc_detail",
        "source_method": SOURCE_METHOD,
        "review_status": REVIEW_STATUS,
        "emperor": emperor,
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "units": units,
        "supporting_materials": supporting_materials,
    }
    payload["preview"] = build_preview(payload)
    return payload


def render_candidate_markdown(payload: Mapping[str, object]) -> str:
    lines = [
        "# I5B 规则证据单元候选",
        "",
        f"- 皇帝：{payload.get('emperor') or ''}",
        f"- 子项：{payload.get('item_code') or 'I5B'}",
        f"- 来源：{payload.get('source_method') or ''}",
        f"- 审核状态：{payload.get('review_status') or ''}",
        f"- 候选单元数：{len(payload.get('units') if isinstance(payload.get('units'), list) else [])}",
        "",
        "## 候选提示",
        "",
    ]
    units = payload.get("units") if isinstance(payload.get("units"), list) else []
    warnings: list[str] = []
    for unit in units:
        if isinstance(unit, Mapping):
            for warning in unit.get("candidate_warnings", []):
                if isinstance(warning, str):
                    warnings.append(warning)
    for warning in sorted(set(warnings)):
        lines.append(f"- {warning}")
    if not warnings:
        lines.append("无。")

    preview = payload.get("preview")
    if isinstance(preview, Mapping):
        lines.extend(["", "## 预览审计", ""])
        lines.extend(render_preview_markdown(preview).splitlines())
    return "\n".join(lines) + "\n"


def write_output(text: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build I5B rule evidence unit candidates from calc_detail.")
    parser.add_argument("--emperor", required=True, help="Emperor name.")
    parser.add_argument("--rule-code", action="append", default=[], help="Limit to one I5B rule_code; repeatable.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN")
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--fail-on-preview-issue", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dsn = args.dsn or resolve_dsn(args.dsn_env)
    rules = tuple(args.rule_code)
    materials_report = fetch_materials(
        dsn=dsn,
        emperor=args.emperor,
        item_code=args.item_code,
        rule_code=None,
    )
    cluster_rows = fetch_cluster_calc_detail_rows(
        dsn=dsn,
        item_code=args.item_code,
        formula_code=args.cluster_formula,
        emperors=(args.emperor,),
        rule_codes=rules,
    )
    payload = build_candidate_payload(
        emperor=args.emperor,
        item_code=args.item_code,
        cluster_formula=args.cluster_formula,
        cluster_rows=cluster_rows,
        materials_report=materials_report,
        rule_codes=rules,
    )
    if args.format == "markdown":
        text = render_candidate_markdown(payload)
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    write_output(text, args.output)
    preview = payload.get("preview")
    issue_count = int(preview.get("issue_count", 0)) if isinstance(preview, Mapping) else 0
    return 1 if args.fail_on_preview_issue and issue_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
