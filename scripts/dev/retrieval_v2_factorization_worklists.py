from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import ImportPlanError  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import repo_relative, text  # noqa: E402


DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
DEFAULT_ITEM_CODE = "I5B"
DEFAULT_RULE_CODE = "delegation"
DEFAULT_FORMULA_CODE = "evidence_cluster_signal_v3"
SCOPES = ("accepted-packs", "active-targets")
ACTION_OPTIONS = ("score", "supporting_only", "exclude")
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


class FactorizationWorklistError(ImportPlanError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FactorizationWorklistError(f"{path}: expected JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise FactorizationWorklistError(f"{path}:{line_no}: expected JSON object")
        payload["_line_no"] = line_no
        rows.append(payload)
    return rows


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8")


def scope_predicate(scope: str) -> str:
    if scope == "accepted-packs":
        return """
           sp.id in (
                select distinct on (sp2.target_id, sp2.contract_id) sp2.id
                  from retrieval_v2.source_packs sp2
                 where sp2.status = 'accepted'
                   and sp2.coverage_status = 'passed'
                 order by sp2.target_id, sp2.contract_id, sp2.updated_at desc, sp2.id desc
           )
        """
    if scope == "active-targets":
        return "rt.target_status = 'active'"
    raise FactorizationWorklistError(f"unsupported scope: {scope}")


def factor_keys_for_material(rule_code: str, direction: str) -> tuple[str, ...]:
    by_direction = RULE_FACTOR_KEYS.get(rule_code, {})
    if direction in by_direction:
        return by_direction[direction]
    if direction == "mixed":
        return tuple(dict.fromkeys((*by_direction.get("positive", ()), *by_direction.get("negative", ()))))
    return by_direction.get("positive", ())


def build_factor_option_catalog(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    catalog: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        factor_name = text(row.get("factor_name"))
        if not factor_name:
            continue
        key = (text(row.get("rule_code")), factor_name)
        catalog.setdefault(key, []).append(
            {
                "factor_option_id": row.get("factor_option_id"),
                "option_code": text(row.get("option_code")),
                "label": text(row.get("label")),
                "value_num": text(row.get("value_num")),
                "source_doc": text(row.get("source_doc")),
                "source_line": row.get("source_line"),
                "option_note": text(row.get("option_note")),
            }
        )
    for values in catalog.values():
        values.sort(key=lambda item: (text(item.get("source_doc")), int(item.get("source_line") or 0), text(item.get("value_num")), text(item.get("label"))))
    return catalog


def factor_option_candidates(catalog: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]], *, rule_code: str, factor_name: str) -> list[dict[str, Any]]:
    rows = [dict(row) for row in catalog.get(("", factor_name), ())]
    rows.extend(dict(row) for row in catalog.get((rule_code, factor_name), ()))
    return rows


def factor_patch_template(row: Mapping[str, Any], catalog: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    rule_code = text(row.get("rule_code"))
    direction = text(row.get("direction"))
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
    }


def fetch_factor_option_rows(cur: Any, *, item_code: str, formula_code: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
            f.rule_code,
            f.formula_code,
            f.factor_name,
            f.factor_scope,
            o.id as factor_option_id,
            o.option_code,
            o.label,
            o.value_num::text as value_num,
            o.source_doc,
            o.source_line,
            o.option_note
          from retrieval_v2.eval_rule_factors f
          join retrieval_v2.eval_rule_factor_options o on o.factor_id = f.id
         where f.item_code = %s
           and f.formula_code = %s
           and f.factor_status = 'active'
           and o.option_status = 'active'
         order by f.rule_code, f.factor_name, o.sort_no, o.id
        """,
        (item_code, formula_code),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_material_rows(cur: Any, *, item_code: str, rule_code: str, scope: str) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        with passage_agg as (
            select
                csp.claim_id,
                jsonb_agg(
                    jsonb_build_object(
                        'passage_code', spg.passage_code,
                        'document_code', sd.document_code,
                        'source_title', sd.source_title,
                        'title', sd.title,
                        'locator', coalesce(nullif(spg.locator, ''), sd.locator),
                        'quote', spg.raw_text
                    )
                    order by csp.id
                ) as source_passages
              from retrieval_v2.claim_source_passages csp
              join retrieval_v2.source_passages spg on spg.id = csp.source_passage_id
              join retrieval_v2.source_documents sd on sd.id = spg.source_document_id
             group by csp.claim_id
        ),
        role_agg as (
            select
                pr.object_id,
                jsonb_agg(
                    distinct jsonb_build_object(
                        'role_kind', pr.role_kind::text,
                        'dynasty_label', pr.dynasty_label,
                        'role_title', pr.role_title,
                        'review_status', pr.review_status::text
                    )
                ) as person_roles
              from retrieval_v2.person_roles pr
             where pr.review_status in ('pending', 'accepted')
             group by pr.object_id
        ),
        affiliation_agg as (
            select
                pa.object_id,
                jsonb_agg(
                    distinct jsonb_build_object(
                        'affiliation_kind', pa.affiliation_kind::text,
                        'dynasty_label', pa.dynasty_label,
                        'polity_label', pa.polity_label,
                        'affiliation_label', pa.affiliation_label,
                        'review_status', pa.review_status::text
                    )
                ) as person_affiliations
              from retrieval_v2.person_affiliations pa
             where pa.review_status in ('pending', 'accepted')
             group by pa.object_id
        )
        select
            rt.target_code,
            rt.emperor_name,
            rt.item_code,
            sp.pack_code as source_pack_code,
            mc.id as claim_id,
            mc.claim_code,
            mc.raw_claim_code,
            mc.object_name as claim_object_name,
            mc.object_type::text as claim_object_type,
            mc.direction::text as claim_direction,
            mc.claim_summary,
            crb.id as binding_id,
            crb.binding_code,
            crb.raw_binding_code,
            crb.rule_code,
            crb.predicate,
            crb.direction::text as direction,
            crb.object_role,
            crb.confidence as binding_confidence,
            crb.review_status as binding_review_status,
            mol.id as material_object_link_id,
            mol.link_code,
            mol.role as material_role,
            mol.confidence as object_link_confidence,
            tob.id as target_object_id,
            tob.target_object_code,
            o.id as object_id,
            o.object_code,
            o.canonical_name,
            o.normalized_name,
            o.object_type::text as object_type,
            pp.talent_grade::text as talent_grade,
            pp.talent_grade_basis,
            coalesce(ra.person_roles, '[]'::jsonb) as person_roles,
            coalesce(aa.person_affiliations, '[]'::jsonb) as person_affiliations,
            coalesce(pa.source_passages, '[]'::jsonb) as source_passages
          from retrieval_v2.claim_rule_bindings crb
          join retrieval_v2.material_claims mc on mc.id = crb.claim_id
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
          join retrieval_v2.material_object_links mol
            on mol.claim_id = mc.id
           and mol.role = crb.object_role
           and mol.review_status = 'accepted'
          join retrieval_v2.objects o on o.id = mol.object_id
          left join retrieval_v2.target_objects tob on tob.id = mol.target_object_id
          left join retrieval_v2.person_profiles pp on pp.object_id = o.id
          left join role_agg ra on ra.object_id = o.id
          left join affiliation_agg aa on aa.object_id = o.id
          left join passage_agg pa on pa.claim_id = mc.id
         where crb.rule_code = %s
           and crb.usable_for_scoring_cluster
           and crb.review_status in ('pending', 'accepted')
           and {scope_predicate(scope)}
           and (%s = '' or rt.item_code = %s)
         order by rt.emperor_name, crb.direction::text desc, o.canonical_name, crb.id
        """,
        (rule_code, item_code, item_code),
    )
    return [dict(row) for row in cur.fetchall()]


def material_item(row: Mapping[str, Any], catalog: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    item = {
        "binding_code": text(row.get("binding_code")),
        "binding_id": row.get("binding_id"),
        "claim_code": text(row.get("claim_code")),
        "claim_id": row.get("claim_id"),
        "material_object_link_id": row.get("material_object_link_id"),
        "target_object_id": row.get("target_object_id"),
        "target_code": text(row.get("target_code")),
        "emperor_name": text(row.get("emperor_name")),
        "source_pack_code": text(row.get("source_pack_code")),
        "rule_code": text(row.get("rule_code")),
        "predicate": text(row.get("predicate")),
        "direction": text(row.get("direction")),
        "object_role": text(row.get("object_role")),
        "binding_confidence": text(row.get("binding_confidence")),
        "binding_review_status": text(row.get("binding_review_status")),
        "object": {
            "object_id": row.get("object_id"),
            "object_code": text(row.get("object_code")),
            "canonical_name": text(row.get("canonical_name")),
            "normalized_name": text(row.get("normalized_name")),
            "object_type": text(row.get("object_type")),
            "talent_grade": text(row.get("talent_grade")),
            "talent_grade_basis": text(row.get("talent_grade_basis")),
            "person_roles": row.get("person_roles") or [],
            "person_affiliations": row.get("person_affiliations") or [],
        },
        "claim": {
            "raw_claim_code": text(row.get("raw_claim_code")),
            "object_name": text(row.get("claim_object_name")),
            "object_type": text(row.get("claim_object_type")),
            "direction": text(row.get("claim_direction")),
            "summary": text(row.get("claim_summary")),
            "source_passages": row.get("source_passages") or [],
        },
    }
    item["factor_patch_template"] = factor_patch_template(item, catalog)
    return item


def group_materials(materials: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in materials:
        key = (text(row.get("emperor_name")), text(row.get("target_code")), text(row.get("rule_code")))
        groups.setdefault(key, []).append(row)
    result: list[dict[str, Any]] = []
    for (emperor_name, target_code, rule_code), rows in sorted(groups.items()):
        result.append(
            {
                "emperor_name": emperor_name,
                "target_code": target_code,
                "rule_code": rule_code,
                "material_count": len(rows),
                "binding_codes": [text(row.get("binding_code")) for row in rows],
                "materials": [dict(row) for row in rows],
            }
        )
    return result


def suggest_batches(groups: Sequence[Mapping[str, Any]], *, batch_size: int) -> list[dict[str, Any]]:
    if batch_size <= 0:
        return []
    batches: list[dict[str, Any]] = []
    current_groups: list[dict[str, Any]] = []
    current_count = 0
    for group in groups:
        material_count = int(group.get("material_count") or 0)
        if current_groups and current_count + material_count > batch_size:
            batches.append({"batch_id": f"rv2_factor_batch_{len(batches) + 1:02d}", "material_count": current_count, "groups": current_groups})
            current_groups = []
            current_count = 0
        current_groups.append(dict(group))
        current_count += material_count
    if current_groups:
        batches.append({"batch_id": f"rv2_factor_batch_{len(batches) + 1:02d}", "material_count": current_count, "groups": current_groups})
    return batches


def build_worklist_from_rows(
    material_rows: Sequence[Mapping[str, Any]],
    factor_option_rows: Sequence[Mapping[str, Any]],
    *,
    item_code: str,
    rule_code: str,
    formula_code: str,
    scope: str,
    batch_size: int,
) -> dict[str, Any]:
    catalog = build_factor_option_catalog(factor_option_rows)
    materials = [material_item(row, catalog) for row in material_rows]
    groups = group_materials(materials)
    batches = suggest_batches(groups, batch_size=batch_size)
    direction_counts = Counter(text(row.get("direction")) for row in materials)
    return {
        "generated_by": "scripts/dev/retrieval_v2_factorization_worklists.py",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ok": True,
        "item_code": item_code,
        "rule_code": rule_code,
        "formula_code": formula_code,
        "scope": scope,
        "totals": {
            "materials": len(materials),
            "groups": len(groups),
            "suggested_batches": len(batches),
            "factor_options": len(factor_option_rows),
        },
        "direction_counts": dict(sorted(direction_counts.items())),
        "groups": groups,
        "suggested_batches": batches,
    }


def filter_material_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    target_names: Sequence[str] = (),
    target_codes: Sequence[str] = (),
) -> list[Mapping[str, Any]]:
    names = {text(name) for name in target_names if text(name)}
    codes = {text(code) for code in target_codes if text(code)}
    if not names and not codes:
        return list(rows)
    return [
        row
        for row in rows
        if (not names or text(row.get("emperor_name")) in names)
        and (not codes or text(row.get("target_code")) in codes)
    ]


def build_worklist(
    *,
    env_file: Path | None,
    dsn_env: str,
    item_code: str,
    rule_code: str,
    formula_code: str,
    scope: str,
    batch_size: int,
    target_names: Sequence[str] = (),
    target_codes: Sequence[str] = (),
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            factor_rows = fetch_factor_option_rows(cur, item_code=item_code, formula_code=formula_code)
            material_rows = fetch_material_rows(cur, item_code=item_code, rule_code=rule_code, scope=scope)
    material_rows = filter_material_rows(material_rows, target_names=target_names, target_codes=target_codes)
    return build_worklist_from_rows(
        material_rows,
        factor_rows,
        item_code=item_code,
        rule_code=rule_code,
        formula_code=formula_code,
        scope=scope,
        batch_size=batch_size,
    )


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 factorization worklist",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- item_code: `{payload.get('item_code', '')}`",
        f"- rule_code: `{payload.get('rule_code', '')}`",
        f"- formula_code: `{payload.get('formula_code', '')}`",
        f"- scope: `{payload.get('scope', '')}`",
        f"- materials: `{payload.get('totals', {}).get('materials', 0)}`",
        f"- groups: `{payload.get('totals', {}).get('groups', 0)}`",
        f"- suggested_batches: `{payload.get('totals', {}).get('suggested_batches', 0)}`",
        "",
        "## Groups",
        "",
        "| emperor | rule | materials | positive | negative |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for group in payload.get("groups") or []:
        materials = group.get("materials") or []
        counts = Counter(text(row.get("direction")) for row in materials)
        lines.append(f"| {group.get('emperor_name')} | `{group.get('rule_code')}` | {len(materials)} | {counts.get('positive', 0)} | {counts.get('negative', 0)} |")
    lines.extend(["", "## Batches", "", "| batch | materials | groups |", "| --- | ---: | --- |"])
    for batch in payload.get("suggested_batches") or []:
        labels = "；".join(f"{group.get('emperor_name')}/{group.get('rule_code')}" for group in batch.get("groups") or [])
        lines.append(f"| `{batch.get('batch_id')}` | {batch.get('material_count')} | {labels} |")
    return "\n".join(lines).rstrip() + "\n"


def write_batch_files(output_dir: Path, batches: Sequence[Mapping[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for batch in batches:
        batch_id = text(batch.get("batch_id"))
        if not batch_id:
            continue
        write_json(output_dir / f"{batch_id}.json", batch)


def flatten_batch_materials(batch: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    materials: dict[str, dict[str, Any]] = {}
    for group in batch.get("groups") or []:
        if not isinstance(group, Mapping):
            continue
        for row in group.get("materials") or []:
            if not isinstance(row, Mapping):
                continue
            binding_code = text(row.get("binding_code"))
            if binding_code:
                materials[binding_code] = dict(row)
    return materials


def patch_template_rows(batch: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for material in flatten_batch_materials(batch).values():
        template = material.get("factor_patch_template") if isinstance(material.get("factor_patch_template"), Mapping) else {}
        rows.append(
            {
                "binding_code": material.get("binding_code"),
                "target_action": "review",
                "side": template.get("side") or material.get("direction") or "",
                "factor_refs": template.get("factor_refs") or {},
                "patch_note": "",
            }
        )
    return rows


def candidate_labels(material: Mapping[str, Any], factor_name: str) -> set[str]:
    template = material.get("factor_patch_template")
    if not isinstance(template, Mapping):
        return set()
    candidates = template.get("factor_option_candidates")
    if not isinstance(candidates, Mapping):
        return set()
    rows = candidates.get(factor_name)
    if not isinstance(rows, list):
        return set()
    return {text(row.get("label")) for row in rows if isinstance(row, Mapping) and text(row.get("label"))}


def candidate_option_by_label(material: Mapping[str, Any], factor_name: str, label: str) -> dict[str, Any] | None:
    template = material.get("factor_patch_template")
    if not isinstance(template, Mapping):
        return None
    candidates = template.get("factor_option_candidates")
    if not isinstance(candidates, Mapping):
        return None
    rows = candidates.get(factor_name)
    if not isinstance(rows, list):
        return None
    matches = [dict(row) for row in rows if isinstance(row, Mapping) and text(row.get("label")) == label]
    return matches[0] if len(matches) == 1 else None


def decimal_or_none(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def result_feedback_sign_issue(*, side: str, value: Decimal | None) -> str:
    if value is None or value == 0:
        return ""
    if side == "positive" and value < 0:
        return "positive_side_negative_result_feedback"
    if side == "negative" and value > 0:
        return "negative_side_positive_result_feedback"
    return ""


def expected_factor_keys(material: Mapping[str, Any]) -> list[str]:
    template = material.get("factor_patch_template")
    if not isinstance(template, Mapping):
        return []
    keys = template.get("factor_keys")
    if not isinstance(keys, list):
        return []
    return [text(key) for key in keys if text(key)]


def high_information_chinese(value: Any) -> bool:
    note = text(value)
    return len(note) >= 12 and any("\u4e00" <= char <= "\u9fff" for char in note)


def validate_patch_row(row: Mapping[str, Any], material: Mapping[str, Any]) -> list[dict[str, Any]]:
    binding_code = text(row.get("binding_code"))
    base = {
        "binding_code": binding_code,
        "emperor_name": material.get("emperor_name"),
        "rule_code": material.get("rule_code"),
        "object_name": (material.get("object") or {}).get("canonical_name") if isinstance(material.get("object"), Mapping) else "",
        "line_no": row.get("_line_no"),
    }
    issues: list[dict[str, Any]] = []
    action = text(row.get("target_action"))
    if action not in ACTION_OPTIONS:
        return [{**base, "severity": "error", "status": "invalid_target_action", "value": action}]
    if not high_information_chinese(row.get("patch_note")):
        issues.append({**base, "severity": "error", "status": "missing_high_information_patch_note", "value": action})
    if action in {"supporting_only", "exclude"}:
        return issues

    side = text(row.get("side"))
    if side not in {"positive", "negative"}:
        issues.append({**base, "severity": "error", "status": "invalid_side", "value": side})
    expected_keys = expected_factor_keys(material)
    if not expected_keys:
        issues.append({**base, "severity": "error", "status": "score_without_factor_template"})
        return issues
    factor_refs = row.get("factor_refs")
    if not isinstance(factor_refs, Mapping):
        issues.append({**base, "severity": "error", "status": "missing_factor_refs"})
        return issues
    for factor_name in expected_keys:
        ref = factor_refs.get(factor_name)
        if not isinstance(ref, Mapping):
            issues.append({**base, "severity": "error", "status": "missing_factor_ref", "factor": factor_name})
            continue
        label = text(ref.get("label"))
        if not label:
            issues.append({**base, "severity": "error", "status": "missing_factor_label", "factor": factor_name})
            continue
        labels = candidate_labels(material, factor_name)
        if labels and label not in labels:
            issues.append({**base, "severity": "error", "status": "unknown_factor_label", "factor": factor_name, "label": label})
            continue
        if text(material.get("rule_code")) == "delegation" and factor_name == "result_feedback":
            option = candidate_option_by_label(material, factor_name, label)
            value = decimal_or_none(option.get("value_num")) if option else None
            status = result_feedback_sign_issue(side=side, value=value)
            if status:
                issues.append(
                    {
                        **base,
                        "severity": "error",
                        "status": "side_result_feedback_sign_mismatch",
                        "detail": status,
                        "factor": factor_name,
                        "label": label,
                        "side": side,
                        "value_num": str(value),
                    }
                )
    return issues


def validate_patch(batch: Mapping[str, Any], patch_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    materials = flatten_batch_materials(batch)
    issues: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for row in patch_rows:
        binding_code = text(row.get("binding_code"))
        if not binding_code:
            issues.append({"severity": "error", "status": "missing_binding_code", "line_no": row.get("_line_no")})
            continue
        if binding_code in seen:
            issues.append({"severity": "error", "status": "duplicate_patch_row", "binding_code": binding_code, "line_no": row.get("_line_no"), "first_line_no": seen[binding_code]})
            continue
        seen[binding_code] = int(row.get("_line_no") or 0)
        material = materials.get(binding_code)
        if material is None:
            issues.append({"severity": "error", "status": "unknown_binding_code", "binding_code": binding_code, "line_no": row.get("_line_no")})
            continue
        issues.extend(validate_patch_row(row, material))
    for binding_code, material in materials.items():
        if binding_code not in seen:
            issues.append(
                {
                    "severity": "error",
                    "status": "missing_patch_row",
                    "binding_code": binding_code,
                    "emperor_name": material.get("emperor_name"),
                    "rule_code": material.get("rule_code"),
                    "object_name": (material.get("object") or {}).get("canonical_name") if isinstance(material.get("object"), Mapping) else "",
                }
            )
    action_counts = Counter(text(row.get("target_action")) for row in patch_rows if text(row.get("target_action")))
    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    return {
        "generated_by": "scripts/dev/retrieval_v2_factorization_worklists.py",
        "command": "validate-patch",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ok": error_count == 0,
        "batch_id": text(batch.get("batch_id")),
        "expected_materials": len(materials),
        "patch_rows": len(patch_rows),
        "error_count": error_count,
        "warning_count": warning_count,
        "action_counts": dict(sorted(action_counts.items())),
        "issues": issues,
    }


def render_validation_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 factorization patch validation",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- batch_id: `{payload.get('batch_id', '')}`",
        f"- expected_materials: `{payload.get('expected_materials', 0)}`",
        f"- patch_rows: `{payload.get('patch_rows', 0)}`",
        f"- errors: `{payload.get('error_count', 0)}`",
        "",
        "## Issues",
        "",
    ]
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    if not issues:
        lines.append("- 无")
    else:
        lines.extend(["| status | binding | material | detail |", "| --- | --- | --- | --- |"])
        for issue in issues:
            material = f"{issue.get('emperor_name') or ''}/{issue.get('rule_code') or ''}/{issue.get('object_name') or ''}"
            detail = issue.get("factor") or issue.get("label") or issue.get("value") or ""
            lines.append(f"| `{issue.get('status')}` | `{issue.get('binding_code') or ''}` | {material} | {detail} |")
    return "\n".join(lines).rstrip() + "\n"


def task_code(batch: Mapping[str, Any]) -> str:
    return "RV2F-" + stable_hash([batch.get("batch_id"), [row.get("binding_code") for row in flatten_batch_materials(batch).values()]], length=16)


def prompt_passage(row: Mapping[str, Any]) -> dict[str, Any]:
    quote = text(row.get("quote"))
    if len(quote) > 420:
        quote = quote[:420] + "..."
    return {
        "source_title": text(row.get("source_title")),
        "title": text(row.get("title")),
        "locator": text(row.get("locator")),
        "quote": quote,
    }


def prompt_material(row: Mapping[str, Any]) -> dict[str, Any]:
    obj = row.get("object") if isinstance(row.get("object"), Mapping) else {}
    claim = row.get("claim") if isinstance(row.get("claim"), Mapping) else {}
    template = row.get("factor_patch_template") if isinstance(row.get("factor_patch_template"), Mapping) else {}
    return {
        "binding_code": text(row.get("binding_code")),
        "emperor_name": text(row.get("emperor_name")),
        "target_code": text(row.get("target_code")),
        "rule_code": text(row.get("rule_code")),
        "direction": text(row.get("direction")),
        "object_role": text(row.get("object_role")),
        "predicate": text(row.get("predicate")),
        "confidence": text(row.get("binding_confidence")),
        "object": {
            "canonical_name": text(obj.get("canonical_name")),
            "object_type": text(obj.get("object_type")),
            "talent_grade": text(obj.get("talent_grade")),
            "talent_grade_basis": text(obj.get("talent_grade_basis")),
            "person_roles": obj.get("person_roles") or [],
            "person_affiliations": obj.get("person_affiliations") or [],
        },
        "claim": {
            "summary": text(claim.get("summary")),
            "source_passages": [prompt_passage(item) for item in (claim.get("source_passages") or [])[:4] if isinstance(item, Mapping)],
        },
        "required_patch": {
            "binding_code": text(row.get("binding_code")),
            "target_action": "score | supporting_only | exclude",
            "side": template.get("side") or text(row.get("direction")),
            "factor_refs": template.get("factor_refs") or {},
            "patch_note": "中文高信息判断",
        },
    }


def slim_batch_for_prompt(batch: Mapping[str, Any]) -> dict[str, Any]:
    factor_options: dict[str, list[dict[str, Any]]] = {}
    materials = list(flatten_batch_materials(batch).values())
    for material in materials:
        template = material.get("factor_patch_template") if isinstance(material.get("factor_patch_template"), Mapping) else {}
        candidates = template.get("factor_option_candidates") if isinstance(template.get("factor_option_candidates"), Mapping) else {}
        for factor_name, rows in candidates.items():
            key = text(factor_name)
            if key and key not in factor_options:
                factor_options[key] = [dict(row) for row in rows if isinstance(row, Mapping)]
    return {
        "batch_id": text(batch.get("batch_id")),
        "material_count": len(materials),
        "factor_options_by_factor": dict(sorted(factor_options.items())),
        "materials": [prompt_material(row) for row in materials],
    }


def prompt_for_batch(*, batch: Mapping[str, Any], patch_path: Path) -> str:
    prompt_payload = slim_batch_for_prompt(batch)
    rule_codes = {
        text(material.get("rule_code"))
        for material in flatten_batch_materials(batch).values()
        if text(material.get("rule_code"))
    }
    skill_instruction = ""
    if "delegation" in rule_codes:
        skill_instruction = (
            "delegation 轻量校准：包内 direction 就是本轮 side，不重新判断正负；"
            "positive 行不得选择负值 `result_feedback`，negative 行不得选择正值 `result_feedback`；"
            "`authorization_intensity` 只看授权范围；`result_feedback` 只看本材料证明的具体履职反馈。\n"
        )
    return (
        "# retrieval_v2 factorization task\n\n"
        "你是消费侧因子化判断子进程。不要修改代码、数据库或 schema；唯一允许写入的是指定 JSONL patch 文件。\n"
        "你可以只读查看仓库内已生成材料；不得执行破坏性命令。必须覆盖本 batch 的每一条 material。\n\n"
        + skill_instruction
        + f"- patch_path: `{repo_relative(patch_path)}`\n"
        "- target_action 只能是 `score`、`supporting_only` 或 `exclude`。\n"
        "- `score` 必须填写 side 和所有 factor_refs；factor_refs.*.label 必须严格使用 factor_options_by_factor 中的 label。\n"
        "- `supporting_only` 表示材料有上下文价值但不单独入分；`exclude` 表示不应进入本 rule 计分。\n"
        "- patch_note 必须是中文高信息判断，说明为什么 score/supporting_only/exclude；不要写模板句。\n\n"
        "输出要求：每行一个 JSON object，字段为 `binding_code`、`target_action`、`side`、`factor_refs`、`patch_note`。不要输出 Markdown。\n\n"
        "## Batch\n\n"
        "```json\n"
        + json.dumps(prompt_payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n```\n"
    )


def load_batch_files(batch_dir: Path | None, batch_json: Sequence[Path]) -> list[Path]:
    paths = list(batch_json)
    if batch_dir is not None:
        paths.extend(sorted(batch_dir.glob("*.json")))
    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path)] = path
    return list(unique.values())


def build_codex_tasks(*, batch_paths: Sequence[Path], output_root: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for batch_path in batch_paths:
        batch = read_json(batch_path)
        code = task_code(batch)
        prompt_path = output_root / "prompts" / f"{code}.md"
        patch_path = output_root / "patches" / f"{code}.jsonl"
        last_message_path = output_root / "logs" / f"{code}.last.md"
        log_path = output_root / "logs" / f"{code}.jsonl"
        task = {
            "task_code": code,
            "task_kind": "retrieval_v2_factorization",
            "batch_id": text(batch.get("batch_id")),
            "batch_path": repo_relative(batch_path),
            "material_count": int(batch.get("material_count") or len(flatten_batch_materials(batch))),
            "prompt_path": repo_relative(prompt_path),
            "patch_path": repo_relative(patch_path),
            "last_message_path": repo_relative(last_message_path),
            "log_path": repo_relative(log_path),
            "argv": [
                "codex",
                "exec",
                "-C",
                str(ROOT),
                "--dangerously-bypass-approvals-and-sandbox",
                "--output-last-message",
                str(last_message_path),
                "--json",
                "-",
            ],
        }
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        last_message_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt_for_batch(batch=batch, patch_path=patch_path), encoding="utf-8")
        tasks.append(task)
    return tasks


def write_task_outputs(*, batch_paths: Sequence[Path], output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    tasks = build_codex_tasks(batch_paths=batch_paths, output_root=output_root)
    tasks_path = output_root / "factorization_tasks.jsonl"
    summary_path = output_root / "factorization_task_summary.json"
    md_path = output_root / "factorization_tasks.md"
    write_jsonl(tasks_path, tasks)
    summary = {
        "generated_by": "scripts/dev/retrieval_v2_factorization_worklists.py",
        "totals": {
            "tasks": len(tasks),
            "materials": sum(int(task.get("material_count") or 0) for task in tasks),
        },
        "files": {
            "tasks_jsonl": repo_relative(tasks_path),
            "markdown": repo_relative(md_path),
        },
        "tasks": [
            {
                "task_code": task["task_code"],
                "batch_id": task["batch_id"],
                "material_count": task["material_count"],
                "patch_path": task["patch_path"],
            }
            for task in tasks
        ],
    }
    write_json(summary_path, summary)
    lines = [
        "# retrieval_v2 factorization Codex tasks",
        "",
        f"- tasks: `{summary['totals']['tasks']}`",
        f"- materials: `{summary['totals']['materials']}`",
        "",
        "| task | batch | materials | patch |",
        "| --- | --- | ---: | --- |",
    ]
    for task in tasks:
        lines.append(f"| `{task['task_code']}` | `{task['batch_id']}` | {task['material_count']} | `{task['patch_path']}` |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def run_codex_tasks(
    *,
    tasks_path: Path,
    execute: bool,
    background: bool,
    limit: int,
    output: Path | None,
    agent_output_root: Path | None = None,
    codex_win_bin: str = "codex-win",
    max_workers: int = 4,
    timeout_seconds: int = 1800,
    sandbox_profile: str = "local-write",
    respect_task_argv: bool = False,
    search: bool = False,
) -> dict[str, Any]:
    agent_root = agent_output_root or (tasks_path.parent / "agent_run")
    agent_root.mkdir(parents=True, exist_ok=True)
    tasks_for_agent = tasks_path
    if limit > 0:
        tasks = read_jsonl(tasks_path)[:limit]
        tasks_for_agent = agent_root / "limited_tasks.jsonl"
        write_jsonl(tasks_for_agent, tasks)

    argv = [
        codex_win_bin,
        "agent",
        "run-plan",
        "--tasks-jsonl",
        str(tasks_for_agent),
        "--output-root",
        str(agent_root),
        "--cwd",
        str(ROOT),
        "--max-workers",
        str(max(1, max_workers)),
        "--timeout-seconds",
        str(max(1, timeout_seconds)),
        "--sandbox-profile",
        sandbox_profile,
    ]
    if background:
        argv.append("--background")
    if not execute:
        argv.append("--dry-run")
    if respect_task_argv:
        argv.append("--respect-task-argv")
    if search:
        argv.append("--search")

    completed = subprocess.run(
        argv,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        agent_payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise FactorizationWorklistError(
            f"codex-win agent run-plan returned non-JSON stdout rc={completed.returncode}: {completed.stdout[:400]}"
        ) from exc
    payload = {
        "generated_by": "scripts/dev/retrieval_v2_factorization_worklists.py",
        "runner": "codex-win agent run-plan",
        "execute": execute,
        "background": background,
        "returncode": completed.returncode,
        "agent_output_root": repo_relative(agent_root),
        "tasks_jsonl": repo_relative(tasks_for_agent),
        "command": argv,
        "results": agent_payload.get("tasks", []),
        "totals": agent_payload.get("totals", {}),
        "agent": agent_payload,
    }
    if completed.stderr:
        payload["stderr"] = completed.stderr
    if output:
        write_json(output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", end="")
    return payload


def resolve_repo_path(value: Any) -> Path:
    path = Path(text(value))
    if path.is_absolute():
        return path
    return ROOT / path


def iter_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        rows: list[str] = []
        for item in value.values():
            rows.extend(iter_text_values(item))
        return rows
    if isinstance(value, list):
        rows = []
        for item in value:
            rows.extend(iter_text_values(item))
        return rows
    return []


def extract_patch_rows_from_text(raw_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in raw_text.splitlines():
        candidate = line.strip()
        if not (candidate.startswith("{") and "binding_code" in candidate):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        binding_code = text(payload.get("binding_code"))
        if not binding_code or binding_code in seen:
            continue
        seen.add(binding_code)
        rows.append(payload)
    return rows


def recover_rows_for_task(task: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    sources: list[str] = []

    def add_rows(candidates: Sequence[Mapping[str, Any]], source: Path) -> None:
        added = 0
        for payload in candidates:
            binding_code = text(payload.get("binding_code"))
            if not binding_code or binding_code in seen:
                continue
            seen.add(binding_code)
            rows.append(dict(payload))
            added += 1
        if added:
            sources.append(repo_relative(source))

    last_message_path = resolve_repo_path(task.get("last_message_path"))
    if last_message_path.exists():
        add_rows(extract_patch_rows_from_text(last_message_path.read_text(encoding="utf-8")), last_message_path)

    log_path = resolve_repo_path(task.get("log_path"))
    if log_path.exists() and int(task.get("material_count") or 0) != len(rows):
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            for value in iter_text_values(event):
                if "binding_code" not in value:
                    continue
                add_rows(extract_patch_rows_from_text(value), log_path)
    return rows, sources


def patch_status(rows: Sequence[Mapping[str, Any]], *, expected: int) -> str:
    if not rows:
        return "missing"
    if expected > 0 and len(rows) == expected:
        return "complete"
    return "partial"


def recover_task_patches(*, tasks_path: Path, output_json: Path | None, output_md: Path | None) -> dict[str, Any]:
    tasks = read_jsonl(tasks_path)
    recovered: list[dict[str, Any]] = []
    for task in tasks:
        rows, sources = recover_rows_for_task(task)
        patch_path = resolve_repo_path(task.get("patch_path"))
        expected = int(task.get("material_count") or 0)
        existing_rows = read_jsonl(patch_path) if patch_path.exists() else []
        existing_status = patch_status(existing_rows, expected=expected)
        recovered_status = patch_status(rows, expected=expected)
        written = False
        if existing_status == "complete":
            status = "complete"
            final_count = len(existing_rows)
            source_mode = "existing_preserved"
        elif recovered_status == "complete":
            write_jsonl(patch_path, rows)
            status = "complete"
            final_count = len(rows)
            source_mode = "recovered_complete"
            written = True
        elif existing_rows and len(existing_rows) >= len(rows):
            status = existing_status
            final_count = len(existing_rows)
            source_mode = "existing_partial_preserved"
        elif rows:
            write_jsonl(patch_path, rows)
            status = "partial"
            final_count = len(rows)
            source_mode = "recovered_partial"
            written = True
        else:
            status = "missing"
            final_count = 0
            source_mode = "missing"
        recovered.append(
            {
                "task_code": text(task.get("task_code")),
                "batch_id": text(task.get("batch_id")),
                "expected": expected,
                "recovered": final_count,
                "recovered_from_logs": len(rows),
                "existing": len(existing_rows),
                "status": status,
                "source_mode": source_mode,
                "written": written,
                "patch_path": repo_relative(patch_path),
                "sources": sources,
            }
        )
    totals = Counter(row["status"] for row in recovered)
    payload = {
        "generated_by": "scripts/dev/retrieval_v2_factorization_worklists.py",
        "command": "recover-patches",
        "ok": all(row["status"] == "complete" for row in recovered),
        "tasks_jsonl": repo_relative(tasks_path),
        "totals": dict(sorted(totals.items())),
        "tasks": recovered,
    }
    if output_json is not None:
        write_json(output_json, payload)
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_recovery_markdown(payload), encoding="utf-8")
    return payload


def render_recovery_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 factorization patch recovery",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- tasks_jsonl: `{payload.get('tasks_jsonl', '')}`",
        "",
        "| task | batch | status | recovered | patch |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for task in payload.get("tasks") or []:
        lines.append(
            f"| `{task.get('task_code')}` | `{task.get('batch_id')}` | `{task.get('status')}` | "
            f"{task.get('recovered')}/{task.get('expected')} | `{task.get('patch_path')}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build read-only retrieval_v2 material factorization worklists.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    worklist = subparsers.add_parser("worklist", help="Build DB-backed factorization worklist.")
    worklist.add_argument("--env-file", type=Path)
    worklist.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    worklist.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    worklist.add_argument("--rule-code", default=DEFAULT_RULE_CODE)
    worklist.add_argument("--formula-code", default=DEFAULT_FORMULA_CODE)
    worklist.add_argument("--scope", choices=SCOPES, default="accepted-packs")
    worklist.add_argument("--batch-size", type=int, default=40)
    worklist.add_argument("--target-name", action="append", default=[], help="Restrict worklist to this emperor/person target name. Repeatable.")
    worklist.add_argument("--target-code", action="append", default=[], help="Restrict worklist to this retrieval target code. Repeatable.")
    worklist.add_argument("--output-json", type=Path, required=True)
    worklist.add_argument("--output-md", type=Path, required=True)
    worklist.add_argument("--batch-output-dir", type=Path)

    template = subparsers.add_parser("template", help="Write a blank factorization patch JSONL for a batch.")
    template.add_argument("--batch-json", type=Path, required=True)
    template.add_argument("--output-jsonl", type=Path, required=True)

    validate = subparsers.add_parser("validate-patch", help="Validate a factorization patch JSONL against a batch.")
    validate.add_argument("--batch-json", type=Path, required=True)
    validate.add_argument("--patch-jsonl", type=Path, required=True)
    validate.add_argument("--output-json", type=Path, required=True)
    validate.add_argument("--output-md", type=Path, required=True)
    validate.add_argument("--fail-on-issue", action="store_true")

    tasks = subparsers.add_parser("tasks", help="Build Codex task prompts from factorization batch JSON files.")
    tasks.add_argument("--batch-dir", type=Path)
    tasks.add_argument("--batch-json", type=Path, action="append", default=[])
    tasks.add_argument("--output-root", type=Path, required=True)

    run_plan = subparsers.add_parser("run-plan", help="Run or start Codex factorization tasks via codex-win agent.")
    run_plan.add_argument("--tasks-jsonl", type=Path, required=True)
    run_plan.add_argument("--execute", action="store_true")
    run_plan.add_argument("--background", action="store_true")
    run_plan.add_argument("--limit", type=int, default=0)
    run_plan.add_argument("--output", type=Path)
    run_plan.add_argument("--agent-output-root", type=Path)
    run_plan.add_argument("--codex-win-bin", default="codex-win")
    run_plan.add_argument("--max-workers", type=int, default=4)
    run_plan.add_argument("--timeout-seconds", type=int, default=1800)
    run_plan.add_argument("--sandbox-profile", choices=("read-only", "local-write", "bypass"), default="local-write")
    run_plan.add_argument("--respect-task-argv", action="store_true")
    run_plan.add_argument("--search", action="store_true")

    recover = subparsers.add_parser("recover-patches", help="Recover JSONL patches from Codex task last-message/log files.")
    recover.add_argument("--tasks-jsonl", type=Path, required=True)
    recover.add_argument("--output-json", type=Path, required=True)
    recover.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "template":
        batch = read_json(args.batch_json)
        rows = patch_template_rows(batch)
        write_jsonl(args.output_jsonl, rows)
        print(json.dumps({"ok": True, "rows": len(rows), "output_jsonl": repo_relative(args.output_jsonl)}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "validate-patch":
        payload = validate_patch(read_json(args.batch_json), read_jsonl(args.patch_jsonl))
        write_json(args.output_json, payload)
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_validation_markdown(payload), encoding="utf-8")
        print(json.dumps({"ok": payload["ok"], "error_count": payload["error_count"], "output_json": repo_relative(args.output_json)}, ensure_ascii=False, sort_keys=True))
        return 1 if args.fail_on_issue and not payload["ok"] else 0
    if args.command == "tasks":
        batch_paths = load_batch_files(args.batch_dir, args.batch_json)
        summary = write_task_outputs(batch_paths=batch_paths, output_root=args.output_root)
        print(json.dumps({"ok": True, "tasks": summary["totals"]["tasks"], "materials": summary["totals"]["materials"], "tasks_jsonl": summary["files"]["tasks_jsonl"]}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "run-plan":
        payload = run_codex_tasks(
            tasks_path=args.tasks_jsonl,
            execute=args.execute,
            background=args.background,
            limit=args.limit,
            output=args.output,
            agent_output_root=args.agent_output_root,
            codex_win_bin=args.codex_win_bin,
            max_workers=args.max_workers,
            timeout_seconds=args.timeout_seconds,
            sandbox_profile=args.sandbox_profile,
            respect_task_argv=args.respect_task_argv,
            search=args.search,
        )
        return 0 if payload.get("returncode") == 0 else 1
    if args.command == "recover-patches":
        payload = recover_task_patches(tasks_path=args.tasks_jsonl, output_json=args.output_json, output_md=args.output_md)
        print(json.dumps({"ok": payload["ok"], "totals": payload["totals"], "output_json": repo_relative(args.output_json)}, ensure_ascii=False, sort_keys=True))
        return 0 if payload["ok"] else 1
    if args.command != "worklist":
        raise FactorizationWorklistError(f"unsupported command: {args.command}")
    payload = build_worklist(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        item_code=args.item_code,
        rule_code=args.rule_code,
        formula_code=args.formula_code,
        scope=args.scope,
        batch_size=args.batch_size,
        target_names=args.target_name,
        target_codes=args.target_code,
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if args.batch_output_dir:
        write_batch_files(args.batch_output_dir, payload.get("suggested_batches") or [])
    print(
        json.dumps(
            {
                "ok": payload["ok"],
                "output_json": repo_relative(args.output_json),
                "materials": payload["totals"]["materials"],
                "suggested_batches": payload["totals"]["suggested_batches"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
