from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_factorization_tasks import (  # noqa: E402
    expected_output_contract,
    expected_output_contracts_path,
    flatten_batch_materials,
    patch_path_for_task,
    prompt_for_batch,
    slim_batch_for_prompt,
    task_code,
)
from scripts.dev.retrieval_v3_import_plan import ImportPlanError  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import repo_relative, text  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev import retrieval_v3_factorization_task_runner as task_runner  # noqa: E402
from scripts.shared import agent_runtime_config  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_ITEM_CODE = "I5B"
DEFAULT_RULE_CODE = "appointment_delegation"
DEFAULT_FORMULA_CODE = "evidence_cluster_signal_v3"
SCOPES = ("accepted-packs", "active-targets")
ACTION_OPTIONS = ("score", "supporting_only", "exclude")
AUTO_SCORER_FACTOR_NAMES = {"rank_decay"}
TEAM_FACTOR_SCOPE = "team"
SHARED_FACTOR_SCOPES = {"default", "shared"}
RULE_FACTOR_SCOPES = {"rule", "attribute_mapping"}
APPOINTMENT_DELEGATION_HINT_PAYLOAD_KEY = "appointment_delegation_factor_hints"
APPOINTMENT_DELEGATION_HINT_TO_FACTOR_VALUE = {
    "importance_hint": {
        "factor_name": "appointment_importance",
        "values": {
            "nominal_light": "0.6000",
            "real_duty": "1.0000",
            "key_military_political": "1.2500",
            "state_level_long_term": "1.4000",
        },
    },
    "effect_hint": {
        "factor_name": "appointment_effect",
        "values": {
            "weak_feedback": "0.4000",
            "normal_success": "1.0000",
            "strong_success": "1.5000",
            "bad_result": "-0.8000",
            "major_bad": "-1.8000",
            "structural_bad": "-2.6000",
        },
    },
    "continuity_hint": {
        "factor_name": "continuity_factor",
        "values": {
            "single_short": "0.8500",
            "stable": "1.0000",
            "long_multi_stage": "1.1500",
        },
    },
}
APPOINTMENT_DELEGATION_HINT_BLOCKING_FLAGS = {
    "appointment_importance": set(),
    "appointment_effect": {"effect_strength_needs_review", "same_chain_result_unclear", "negative_causality_needs_review"},
    "continuity_factor": {"continuity_needs_review"},
}
HINT_PREFILL_CONFIDENCES = {"high", "medium"}
APPOINTMENT_DELEGATION_HINT_CONFIDENCE_KEYS = {
    "importance_hint": ("importance", "importance_hint", "appointment_importance"),
    "effect_hint": ("effect", "effect_hint", "appointment_effect"),
    "continuity_hint": ("continuity", "continuity_hint", "continuity_factor"),
}

recover_task_patches = task_runner.recover_task_patches


def run_codex_tasks(**kwargs: Any) -> dict[str, Any]:
    try:
        return task_runner.run_codex_tasks(**kwargs)
    except task_runner.FactorizationTaskRunnerError as exc:
        raise FactorizationWorklistError(str(exc)) from exc
FORMULA_FACTOR_KEYS: dict[str, dict[str, tuple[str, ...]]] = {
    "talent_discovery": {
        "positive": (
            "discovery_level",
            "talent_quality_factor",
            "channel_factor",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
        "negative": (
            "discovery_level",
            "talent_quality_factor",
            "channel_factor",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
    },
    "appointment_delegation": {
        "positive": (
            "appointment_importance",
            "appointment_effect",
            "continuity_factor",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
        "negative": (
            "appointment_importance",
            "appointment_effect",
            "continuity_factor",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
    },
    "tolerate_talent": {
        "positive": (
            "feedback_entry",
            "expression_safety",
            "protection_repair",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
        "negative": (
            "handling_severity",
            "target_fault_factor",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
    },
    "anti_nepotism": {
        "positive": (
            "selection_openness",
            "institutionalization",
            "office_weight",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
        "negative": (
            "favoritism_intensity",
            "office_weight",
            "displacement_harm",
            "attribution_factor",
            "source_factor",
            "context_factor",
        ),
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
                  from retrieval_v3.source_packs sp2
                 where sp2.status = 'accepted'
                   and sp2.coverage_status = 'passed'
                 order by sp2.target_id, sp2.contract_id, sp2.updated_at desc, sp2.id desc
           )
        """
    if scope == "active-targets":
        return "rt.target_status = 'active'"
    raise FactorizationWorklistError(f"unsupported scope: {scope}")


def build_factor_key_catalog(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    catalog: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in rows:
        rule_code = text(row.get("rule_code"))
        factor_name = text(row.get("factor_name"))
        if not factor_name or factor_name in AUTO_SCORER_FACTOR_NAMES:
            continue
        key = (rule_code, factor_name)
        if key in seen:
            continue
        seen.add(key)
        factor_scope = text(row.get("factor_scope"))
        if not factor_scope:
            factor_scope = "shared" if not rule_code else "rule"
        catalog[rule_code].append(
            {
                "factor_name": factor_name,
                "factor_scope": factor_scope,
                "source_line": row.get("source_line"),
                "sort_no": row.get("sort_no"),
            }
        )
    return {rule: rows for rule, rows in sorted(catalog.items())}


def factor_keys_for_material(
    rule_code: str,
    direction: str,
    factor_key_catalog: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[str, ...]:
    rule_rows = [dict(row) for row in factor_key_catalog.get(rule_code, ())]
    team_rows = [row for row in rule_rows if text(row.get("factor_scope")) == TEAM_FACTOR_SCOPE]
    if team_rows:
        return tuple(text(row.get("factor_name")) for row in team_rows)
    available = {
        text(row.get("factor_name"))
        for row in [*factor_key_catalog.get(rule_code, ()), *factor_key_catalog.get("", ())]
        if text(row.get("factor_name"))
    }
    by_direction = FORMULA_FACTOR_KEYS.get(rule_code, {})
    if by_direction:
        formula_keys = by_direction.get(direction) or by_direction.get("positive") or ()
        return tuple(factor_name for factor_name in formula_keys if factor_name in available)
    rule_keys = [
        text(row.get("factor_name"))
        for row in rule_rows
        if text(row.get("factor_scope")) in RULE_FACTOR_SCOPES
    ]
    shared_keys = [
        text(row.get("factor_name"))
        for row in factor_key_catalog.get("", ())
        if text(row.get("factor_scope")) in SHARED_FACTOR_SCOPES
    ]
    return tuple(dict.fromkeys([*rule_keys, *shared_keys]))


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


RULE_ROUTING_OPTION_MARKERS = ("相邻项", "相邻 rule", "相邻rule", "跨项切分", "跨 rule")


def is_rule_routing_option(row: Mapping[str, Any]) -> bool:
    text_fields = " ".join(
        text(row.get(key))
        for key in ("option_code", "label", "option_note")
        if text(row.get(key))
    ).lower()
    return any(marker.lower() in text_fields for marker in RULE_ROUTING_OPTION_MARKERS)


def factor_option_candidates(catalog: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]], *, rule_code: str, factor_name: str) -> list[dict[str, Any]]:
    rule_rows = [dict(row) for row in catalog.get((rule_code, factor_name), ())]
    rows = rule_rows or [dict(row) for row in catalog.get(("", factor_name), ())]
    return [row for row in rows if not is_rule_routing_option(row)]


def option_by_value(
    catalog: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    *,
    rule_code: str,
    factor_name: str,
    value_num: str,
) -> dict[str, Any] | None:
    normalized = text(value_num)
    for row in factor_option_candidates(catalog, rule_code=rule_code, factor_name=factor_name):
        if text(row.get("value_num")) == normalized:
            return dict(row)
    return None


def candidate_factor_hints(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("candidate_payload")
    if not isinstance(payload, Mapping):
        return {}
    hints = payload.get(APPOINTMENT_DELEGATION_HINT_PAYLOAD_KEY)
    return hints if isinstance(hints, Mapping) else {}


def confidence_for_hint(hints: Mapping[str, Any], hint_key: str, factor_name: str) -> str:
    confidence = hints.get("hint_confidence")
    if isinstance(confidence, Mapping):
        for key in APPOINTMENT_DELEGATION_HINT_CONFIDENCE_KEYS.get(hint_key, (hint_key, factor_name)):
            value = text(confidence.get(key))
            if value:
                return value
        return ""
    return text(confidence)


def uncertainty_flags(hints: Mapping[str, Any]) -> set[str]:
    raw = hints.get("uncertainty_flags")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return set()
    return {text(value) for value in raw if text(value)}


def build_appointment_delegation_hint_suggestions(
    row: Mapping[str, Any],
    catalog: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    if text(row.get("rule_code")) != "appointment_delegation":
        return {}
    hints = candidate_factor_hints(row)
    if not hints:
        return {}
    flags = uncertainty_flags(hints)
    suggestions: dict[str, Any] = {
        "source": APPOINTMENT_DELEGATION_HINT_PAYLOAD_KEY,
        "raw_hints": dict(hints),
        "mapped_refs": {},
        "withheld_refs": {},
        "uncertainty_flags": sorted(flags),
        "usage_note": "抓包端 hint 只作预填建议；消费端必须按规则表和 quote 独立确认，可覆盖或清空。",
    }
    for hint_key, config in APPOINTMENT_DELEGATION_HINT_TO_FACTOR_VALUE.items():
        hint_value = text(hints.get(hint_key))
        factor_name = text(config.get("factor_name"))
        confidence = confidence_for_hint(hints, hint_key, factor_name)
        values = config.get("values") if isinstance(config.get("values"), Mapping) else {}
        value_num = text(values.get(hint_value))
        blocking_flags = APPOINTMENT_DELEGATION_HINT_BLOCKING_FLAGS.get(factor_name, set()) & flags
        withheld_reason = ""
        if not hint_value or hint_value == "unknown":
            withheld_reason = "unknown_hint"
        elif not value_num:
            withheld_reason = "unsupported_hint"
        elif confidence not in HINT_PREFILL_CONFIDENCES:
            withheld_reason = "low_or_missing_confidence"
        elif blocking_flags:
            withheld_reason = "uncertainty_flag"
        option = option_by_value(catalog, rule_code="appointment_delegation", factor_name=factor_name, value_num=value_num) if value_num else None
        if not withheld_reason and option is None:
            withheld_reason = "missing_factor_option"
        entry = {
            "hint_key": hint_key,
            "hint_value": hint_value,
            "confidence": confidence,
            "factor_name": factor_name,
            "value_num": value_num,
            "uncertainty_flags": sorted(blocking_flags),
        }
        if withheld_reason:
            suggestions["withheld_refs"][factor_name] = {**entry, "reason": withheld_reason}
            continue
        suggestions["mapped_refs"][factor_name] = {
            **entry,
            "label": text(option.get("label")) if option else "",
            "option_code": text(option.get("option_code")) if option else "",
        }
    return suggestions


def factor_patch_template(
    row: Mapping[str, Any],
    catalog: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    factor_key_catalog: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    rule_code = text(row.get("rule_code"))
    direction = text(row.get("direction"))
    factor_keys = factor_keys_for_material(rule_code, direction, factor_key_catalog)
    side = direction if direction in {"positive", "negative"} else ""
    factor_refs = {factor_name: {"label": ""} for factor_name in factor_keys}
    obj = row.get("object")
    talent_label = text(obj.get("talent_quality_factor_label")) if isinstance(obj, Mapping) else text(row.get("talent_quality_factor_label"))
    if talent_label and "talent_quality_factor" in factor_refs:
        factor_refs["talent_quality_factor"] = {"label": talent_label}
    hint_suggestions = build_appointment_delegation_hint_suggestions(row, catalog)
    for factor_name, ref in (hint_suggestions.get("mapped_refs") or {}).items():
        if factor_name in factor_refs and text(ref.get("label")):
            factor_refs[factor_name] = {
                "label": text(ref.get("label")),
                "prefill_source": APPOINTMENT_DELEGATION_HINT_PAYLOAD_KEY,
                "prefill_confidence": text(ref.get("confidence")),
            }
    return {
        "target_action": "review",
        "action_options": list(ACTION_OPTIONS),
        "side": side,
        "side_options": ["positive", "negative"],
        "factor_keys": list(factor_keys),
        "factor_refs": factor_refs,
        "factor_option_candidates": {
            factor_name: factor_option_candidates(catalog, rule_code=rule_code, factor_name=factor_name)
            for factor_name in factor_keys
        },
        "factor_hint_suggestions": hint_suggestions,
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
            f.value_source,
            o.id as factor_option_id,
            o.option_code,
            o.label,
            o.value_num::text as value_num,
            o.source_doc,
            o.source_line,
            o.sort_no,
            o.option_note
          from retrieval_v3.eval_rule_factors f
          join retrieval_v3.eval_rule_factor_options o on o.factor_id = f.id
         where f.item_code = %s
           and f.formula_code = %s
           and f.factor_status = 'active'
           and o.option_status = 'active'
         order by f.rule_code, min(o.source_line) over (partition by f.id) nulls last, f.factor_name, o.sort_no, o.id
        """,
        (item_code, formula_code),
    )
    return [dict(row) for row in cur.fetchall()]


def source_pack_predicate(scope: str, source_pack_codes: Sequence[str] = ()) -> str:
    codes = [text(code) for code in source_pack_codes if text(code)]
    if codes:
        return "sp.pack_code = any(%s) and sp.coverage_status = 'passed'"
    return scope_predicate(scope)


def fetch_material_rows(
    cur: Any,
    *,
    item_code: str,
    rule_code: str,
    formula_code: str,
    scope: str,
    source_pack_codes: Sequence[str] = (),
    include_judged: bool = False,
) -> list[dict[str, Any]]:
    binding_scoring_predicate = "true" if include_judged else """
                crb.usable_for_scoring_cluster
                or (
                    crb.rule_code <> 'appointment_delegation'
                    and crb.binding_payload->>'source' = 'retrieval_v3_candidate_promoter'
                    and nullif(crb.binding_payload->>'candidate_id', '') is not null
                )
    """
    codes = [text(code) for code in source_pack_codes if text(code)]
    source_pack_params: list[Any] = [codes] if codes else []
    judgment_delta_predicate = "" if include_judged else """
           and not exists (
                select 1
                  from retrieval_v3.claim_rule_binding_factor_judgments existing_judgment
                 where existing_judgment.binding_id = crb.id
                   and existing_judgment.item_code = rt.item_code
                   and existing_judgment.rule_code = crb.rule_code
                   and existing_judgment.formula_code = %s
                   and existing_judgment.review_status::text not in ('rejected', 'retired')
           )
    """
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
              from retrieval_v3.claim_source_passages csp
              join retrieval_v3.source_passages spg on spg.id = csp.source_passage_id
              join retrieval_v3.source_documents sd on sd.id = spg.source_document_id
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
              from retrieval_v3.person_roles pr
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
              from retrieval_v3.person_affiliations pa
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
            crb.binding_payload,
            cand.candidate_payload,
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
            coalesce(tqfo.label, tbtc.talent_quality_label) as talent_quality_factor_label,
            coalesce(ra.person_roles, '[]'::jsonb) as person_roles,
            coalesce(aa.person_affiliations, '[]'::jsonb) as person_affiliations,
            coalesce(pa.source_passages, '[]'::jsonb) as source_passages
          from retrieval_v3.claim_rule_bindings crb
          join retrieval_v3.material_claims mc on mc.id = crb.claim_id
          join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v3.retrieval_targets rt on rt.id = sp.target_id
          join lateral (
              select mol1.*
                from retrieval_v3.material_object_links mol1
               where mol1.claim_id = mc.id
                 and mol1.review_status = 'accepted'
                 and (
                      (
                          coalesce(crb.binding_payload->>'promoted_material_object_link_id', '') ~ '^[0-9]+$'
                          and mol1.id = (crb.binding_payload->>'promoted_material_object_link_id')::bigint
                      )
                      or (
                          not (coalesce(crb.binding_payload->>'promoted_material_object_link_id', '') ~ '^[0-9]+$')
                          and mol1.role = crb.object_role
                      )
                 )
               order by case
                   when coalesce(crb.binding_payload->>'promoted_material_object_link_id', '') ~ '^[0-9]+$'
                    and mol1.id = (crb.binding_payload->>'promoted_material_object_link_id')::bigint
                       then 0
                   else 1
               end,
               mol1.id
               limit 1
          ) mol on true
          join retrieval_v3.objects o on o.id = mol.object_id
          left join retrieval_v3.target_objects tob on tob.id = mol.target_object_id
          left join retrieval_v3.person_profiles pp on pp.object_id = o.id
          left join retrieval_v3.v_team_building_talent_candidates tbtc
            on tbtc.target_id = rt.id
           and tbtc.object_id = o.id
           and tbtc.rule_code = crb.rule_code
          left join retrieval_v3.eval_rule_factors tqf
            on tqf.item_code = rt.item_code
           and tqf.rule_code = crb.rule_code
           and tqf.formula_code = %s
           and tqf.factor_name = 'talent_quality_factor'
           and tqf.factor_status = 'active'
          left join retrieval_v3.eval_rule_factor_options tqfo
            on tqfo.factor_id = tqf.id
           and tqfo.option_status = 'active'
           and trim(trailing '。' from tqfo.label) = trim(trailing '。' from tbtc.talent_quality_label)
          left join lateral (
              select c0.candidate_payload
                from retrieval_v3.claim_rule_binding_candidates c0
               where c0.resolved_binding_id = crb.id
                  or (
                      coalesce(crb.binding_payload->>'candidate_id', '') ~ '^[0-9]+$'
                      and c0.id = (crb.binding_payload->>'candidate_id')::bigint
                  )
               order by case when c0.resolved_binding_id = crb.id then 0 else 1 end, c0.id
               limit 1
          ) cand on true
          left join role_agg ra on ra.object_id = o.id
          left join affiliation_agg aa on aa.object_id = o.id
          left join passage_agg pa on pa.claim_id = mc.id
         where crb.rule_code = %s
           and ({binding_scoring_predicate})
           and crb.review_status in ('pending', 'accepted')
           and not exists (
                select 1
                  from retrieval_v3.material_review_queue mrq
                 where mrq.claim_id = mc.id
                   and mrq.queue_status in ('ready', 'needs_review', 'running', 'blocked')
           )
           and {source_pack_predicate(scope, codes)}
           and (%s = '' or rt.item_code = %s)
           {judgment_delta_predicate}
         order by rt.emperor_name, crb.direction::text desc, o.canonical_name, crb.id
        """,
        (formula_code, rule_code, *source_pack_params, item_code, item_code, *([] if include_judged else [formula_code])),
    )
    return [dict(row) for row in cur.fetchall()]


def material_item(
    row: Mapping[str, Any],
    catalog: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    factor_key_catalog: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
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
        "binding_payload": row.get("binding_payload") if isinstance(row.get("binding_payload"), Mapping) else {},
        "candidate_payload": row.get("candidate_payload") if isinstance(row.get("candidate_payload"), Mapping) else {},
        "object": {
            "object_id": row.get("object_id"),
            "object_code": text(row.get("object_code")),
            "canonical_name": text(row.get("canonical_name")),
            "normalized_name": text(row.get("normalized_name")),
            "object_type": text(row.get("object_type")),
            "talent_grade": text(row.get("talent_grade")),
            "talent_grade_basis": text(row.get("talent_grade_basis")),
            "talent_quality_factor_label": text(row.get("talent_quality_factor_label")),
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
    item["factor_patch_template"] = factor_patch_template(item, catalog, factor_key_catalog)
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

    def append_current() -> None:
        nonlocal current_groups, current_count
        if current_groups:
            batches.append({"batch_id": f"rv3_factor_batch_{len(batches) + 1:02d}", "material_count": current_count, "groups": current_groups})
            current_groups = []
            current_count = 0

    for group in groups:
        material_count = int(group.get("material_count") or 0)
        materials = [dict(row) for row in group.get("materials") or [] if isinstance(row, Mapping)]
        if material_count > batch_size and materials:
            append_current()
            for index in range(0, len(materials), batch_size):
                chunk = materials[index : index + batch_size]
                chunk_group = dict(group)
                chunk_group["materials"] = chunk
                chunk_group["material_count"] = len(chunk)
                chunk_group["binding_codes"] = [text(row.get("binding_code")) for row in chunk]
                batches.append({"batch_id": f"rv3_factor_batch_{len(batches) + 1:02d}", "material_count": len(chunk), "groups": [chunk_group]})
            continue
        if current_groups and current_count + material_count > batch_size:
            append_current()
        current_groups.append(dict(group))
        current_count += material_count
    append_current()
    return batches


def build_worklist_from_rows(
    material_rows: Sequence[Mapping[str, Any]],
    factor_option_rows: Sequence[Mapping[str, Any]],
    *,
    item_code: str,
    rule_code: str,
    formula_code: str,
    scope: str,
    source_pack_codes: Sequence[str] = (),
    batch_size: int,
) -> dict[str, Any]:
    if rule_code == "team_building":
        missing = [text(row.get("binding_code")) for row in material_rows if not text(row.get("talent_grade"))]
        if missing:
            raise FactorizationWorklistError(
                "team_building requires accepted person_profiles.talent_grade before factorization: "
                + ", ".join(missing[:20])
            )
    catalog = build_factor_option_catalog(factor_option_rows)
    factor_key_catalog = build_factor_key_catalog(factor_option_rows)
    materials = [material_item(row, catalog, factor_key_catalog) for row in material_rows]
    groups = group_materials(materials)
    batches = suggest_batches(groups, batch_size=batch_size)
    direction_counts = Counter(text(row.get("direction")) for row in materials)
    return {
        "generated_by": "scripts/dev/retrieval_v3_factorization_worklists.py",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ok": True,
        "item_code": item_code,
        "rule_code": rule_code,
        "formula_code": formula_code,
        "scope": scope,
        "source_pack_codes": [text(code) for code in source_pack_codes if text(code)],
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
    schema_name: str = DEFAULT_PG_SCHEMA,
    item_code: str,
    rule_code: str,
    formula_code: str,
    scope: str,
    batch_size: int,
    source_pack_codes: Sequence[str] = (),
    include_judged: bool = False,
    target_names: Sequence[str] = (),
    target_codes: Sequence[str] = (),
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            factor_rows = fetch_factor_option_rows(cur, item_code=item_code, formula_code=formula_code)
            material_rows = fetch_material_rows(
                cur,
                item_code=item_code,
                rule_code=rule_code,
                formula_code=formula_code,
                scope=scope,
                source_pack_codes=source_pack_codes,
                include_judged=include_judged,
            )
    material_rows = filter_material_rows(material_rows, target_names=target_names, target_codes=target_codes)
    payload = build_worklist_from_rows(
        material_rows,
        factor_rows,
        item_code=item_code,
        rule_code=rule_code,
        formula_code=formula_code,
        scope=scope,
        source_pack_codes=source_pack_codes,
        batch_size=batch_size,
    )
    payload["selection_mode"] = "all_bindings" if include_judged else "unjudged_delta"
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 factorization worklist",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- item_code: `{payload.get('item_code', '')}`",
        f"- rule_code: `{payload.get('rule_code', '')}`",
        f"- formula_code: `{payload.get('formula_code', '')}`",
        f"- scope: `{payload.get('scope', '')}`",
        f"- source_pack_codes: `{', '.join(payload.get('source_pack_codes') or [])}`",
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


def appointment_effect_sign_issue(*, side: str, value: Decimal | None) -> str:
    if value is None or value == 0:
        return ""
    if side == "positive" and value < 0:
        return "positive_side_negative_appointment_effect"
    if side == "negative" and value > 0:
        return "negative_side_positive_appointment_effect"
    return ""


def factor_hint_suggestions(material: Mapping[str, Any]) -> Mapping[str, Any]:
    template = material.get("factor_patch_template")
    if not isinstance(template, Mapping):
        return {}
    hints = template.get("factor_hint_suggestions")
    return hints if isinstance(hints, Mapping) else {}


def mapped_hint_ref(material: Mapping[str, Any], factor_name: str) -> Mapping[str, Any]:
    suggestions = factor_hint_suggestions(material)
    mapped = suggestions.get("mapped_refs")
    if not isinstance(mapped, Mapping):
        return {}
    ref = mapped.get(factor_name)
    return ref if isinstance(ref, Mapping) else {}


def strong_success_downgrade_issue(*, material: Mapping[str, Any], side: str, factor_name: str, value: Decimal | None) -> str:
    if text(material.get("rule_code")) != "appointment_delegation":
        return ""
    if side != "positive" or factor_name != "appointment_effect" or value is None:
        return ""
    hint_ref = mapped_hint_ref(material, "appointment_effect")
    if text(hint_ref.get("hint_value")) != "strong_success":
        return ""
    suggested_value = decimal_or_none(hint_ref.get("value_num"))
    if suggested_value is None or suggested_value <= 0:
        return ""
    if value > Decimal("0.4000"):
        return ""
    return "strong_success_hint_downgraded_to_weak_feedback"


def raw_score_sign_issue(*, side: str, raw_score: Decimal | None) -> str:
    if raw_score is None or raw_score == 0:
        return ""
    if side == "positive" and raw_score < 0:
        return "positive_side_negative_raw_score"
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


def source_quote_text(material: Mapping[str, Any]) -> str:
    claim = material.get("claim") if isinstance(material.get("claim"), Mapping) else {}
    raw_passages = material.get("source_passages") or claim.get("source_passages")
    passages = raw_passages if isinstance(raw_passages, list) else []
    return " ".join(text(row.get("quote")) for row in passages if isinstance(row, Mapping))


def tolerate_talent_factor_issue(
    *, material: Mapping[str, Any], factor_name: str, value: Decimal | None
) -> str:
    if text(material.get("rule_code")) != "tolerate_talent" or text(material.get("direction")) != "negative" or value is None:
        return ""
    quote = source_quote_text(material)
    if factor_name == "handling_severity":
        mass_harm = any(term in quote for term in (
            "株连", "株連", "连坐", "連坐", "族诛", "族誅", "族之", "宗族", "夷族", "尽诛", "盡誅",
            "七十余人", "七十餘人", "万人", "萬人", "千人", "百人", "三万余人", "三萬餘人", "一万五千人", "一萬五千人",
            "夷灭", "夷滅", "不可胜数", "不可勝數", "相继尽", "相繼盡", "元功宿将", "元功宿將",
            "群臣", "功臣集团", "功臣集團",
            "储备人才", "儲備人才", "表达对象", "表達對象", "人才生态", "人才生態", "系统清洗", "系統清洗",
        ))
        if value >= Decimal("3.2") and not mass_harm:
            return "catastrophic_severity_without_group_or_ecology_harm"
    if factor_name == "target_fault_factor" and value == Decimal("0.9"):
        disputed = any(term in quote for term in (
            "未具", "未坐实", "未坐實", "无验", "無驗", "无实", "無實", "不实", "不實",
            "争议", "爭議", "申辩", "申辯", "追悔", "悔之", "非其罪", "不罪", "冤", "疑",
        ))
        if not disputed:
            return "disputed_fault_factor_without_quote_support"
    return ""


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
        if text(row.get("side")):
            issues.append({**base, "severity": "error", "status": "non_score_side_must_be_null", "value": row.get("side")})
        factor_refs = row.get("factor_refs")
        if factor_refs not in (None, {}) and factor_refs != {}:
            issues.append({**base, "severity": "error", "status": "non_score_factor_refs_must_be_empty"})
        return issues

    side = text(row.get("side"))
    if side not in {"positive", "negative"}:
        issues.append({**base, "severity": "error", "status": "invalid_side", "value": side})
    if not source_quote_text(material):
        issues.append({**base, "severity": "error", "status": "score_without_source_quote"})
    expected_keys = expected_factor_keys(material)
    if not expected_keys:
        issues.append({**base, "severity": "error", "status": "score_without_factor_template"})
        return issues
    factor_refs = row.get("factor_refs")
    if not isinstance(factor_refs, Mapping):
        issues.append({**base, "severity": "error", "status": "missing_factor_refs"})
        return issues
    selected_values: list[Decimal] = []
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
        option = candidate_option_by_label(material, factor_name, label)
        value = decimal_or_none(option.get("value_num")) if option else None
        if value is not None:
            selected_values.append(value)
        if text(material.get("rule_code")) == "appointment_delegation" and factor_name == "appointment_effect":
            status = appointment_effect_sign_issue(side=side, value=value)
            if status:
                issues.append(
                    {
                        **base,
                        "severity": "error",
                        "status": "side_appointment_effect_sign_mismatch",
                        "detail": status,
                        "factor": factor_name,
                        "label": label,
                        "side": side,
                        "value_num": str(value),
                    }
                )
            downgrade_status = strong_success_downgrade_issue(
                material=material,
                side=side,
                factor_name=factor_name,
                value=value,
            )
            if downgrade_status:
                hint_ref = mapped_hint_ref(material, "appointment_effect")
                issues.append(
                    {
                        **base,
                        "severity": "error",
                        "status": downgrade_status,
                        "factor": factor_name,
                        "label": label,
                        "side": side,
                        "value_num": str(value),
                        "hint_value": text(hint_ref.get("hint_value")),
                        "hint_confidence": text(hint_ref.get("confidence")),
                        "hint_value_num": text(hint_ref.get("value_num")),
                    }
                )
        tolerate_issue = tolerate_talent_factor_issue(material=material, factor_name=factor_name, value=value)
        if tolerate_issue:
            issues.append({
                **base,
                "severity": "error",
                "status": tolerate_issue,
                "factor": factor_name,
                "label": label,
                "value_num": str(value),
            })
    if side in {"positive", "negative"} and len(selected_values) == len(expected_keys):
        raw_score = Decimal("1")
        for value in selected_values:
            raw_score *= value
        status = raw_score_sign_issue(side=side, raw_score=raw_score)
        if status:
            issues.append(
                {
                    **base,
                    "severity": "error",
                    "status": "side_raw_score_sign_mismatch",
                    "detail": status,
                    "side": side,
                    "raw_score": str(raw_score),
                }
            )
    return issues


def validate_patch(batch: Mapping[str, Any], patch_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    materials = flatten_batch_materials(batch)
    issues: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    team_factor_labels: dict[str, dict[str, tuple[str, int, str]]] = defaultdict(dict)
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
        if text(material.get("rule_code")) == "team_building" and text(row.get("target_action")) == "score":
            obj = material.get("object") if isinstance(material.get("object"), Mapping) else {}
            expected_talent_label = text(obj.get("talent_quality_factor_label"))
            factor_refs = row.get("factor_refs") if isinstance(row.get("factor_refs"), Mapping) else {}
            actual_ref = factor_refs.get("talent_quality_factor")
            actual_talent_label = text(actual_ref.get("label")) if isinstance(actual_ref, Mapping) else ""
            if not expected_talent_label or actual_talent_label != expected_talent_label:
                issues.append({
                    "severity": "error",
                    "status": "team_talent_grade_prefill_mismatch",
                    "binding_code": binding_code,
                    "expected_label": expected_talent_label,
                    "actual_label": actual_talent_label,
                })
            target_code = text(material.get("target_code"))
            if isinstance(factor_refs, Mapping):
                for factor_name in ("role_complementarity_factor", "long_term_stability_factor"):
                    ref = factor_refs.get(factor_name)
                    label = text(ref.get("label")) if isinstance(ref, Mapping) else ""
                    if not label:
                        continue
                    current = team_factor_labels[target_code].get(factor_name)
                    if current is None:
                        team_factor_labels[target_code][factor_name] = (label, int(row.get("_line_no") or 0), binding_code)
                    elif current[0] != label:
                        issues.append(
                            {
                                "severity": "error",
                                "status": "inconsistent_team_factor_label",
                                "binding_code": binding_code,
                                "line_no": row.get("_line_no"),
                                "target_code": target_code,
                                "factor": factor_name,
                                "label": label,
                                "first_label": current[0],
                                "first_line_no": current[1],
                                "first_binding_code": current[2],
                            }
                        )
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
        "generated_by": "scripts/dev/retrieval_v3_factorization_worklists.py",
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
        "# retrieval_v3 factorization patch validation",
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


def load_batch_files(batch_dir: Path | None, batch_json: Sequence[Path]) -> list[Path]:
    paths = list(batch_json)
    if batch_dir is not None:
        paths.extend(sorted(batch_dir.glob("*.json")))
    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path)] = path
    return list(unique.values())


def prompt_token_estimate(prompt_text: str) -> int:
    return (len(prompt_text) + 1) // 2


def json_char_count(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def batch_json_chars(prompt_text: str) -> int:
    marker = "## Batch\n\n```json\n"
    start = prompt_text.find(marker)
    if start < 0:
        return 0
    start += len(marker)
    end = prompt_text.find("\n```", start)
    if end < 0:
        return len(prompt_text) - start
    return end - start


def prompt_cost_attribution(payload: Mapping[str, Any], prompt_text: str) -> dict[str, Any]:
    materials = payload.get("materials") if isinstance(payload.get("materials"), list) else []
    factor_options = payload.get("factor_options_by_factor") if isinstance(payload.get("factor_options_by_factor"), Mapping) else {}
    batch_chars = batch_json_chars(prompt_text)
    factor_options_chars = json_char_count(factor_options)
    materials_chars = json_char_count(materials)
    source_passages_chars = 0
    source_quote_text_chars = 0
    factor_hints_chars = 0
    object_profile_chars = 0
    patch_requirements_chars = 0
    claim_summary_text_chars = 0
    for material in materials:
        if not isinstance(material, Mapping):
            continue
        claim = material.get("claim") if isinstance(material.get("claim"), Mapping) else {}
        passages = claim.get("source_passages") if isinstance(claim.get("source_passages"), list) else []
        source_passages_chars += json_char_count(passages)
        claim_summary_text_chars += len(text(claim.get("summary")))
        for passage in passages:
            if isinstance(passage, Mapping):
                source_quote_text_chars += len(text(passage.get("quote")))
        hints = material.get("factor_hint_suggestions")
        if isinstance(hints, Mapping) and hints:
            factor_hints_chars += json_char_count(hints)
        obj = material.get("object")
        if isinstance(obj, Mapping):
            object_profile_chars += json_char_count(obj)
        patch_requirements = material.get("patch_requirements")
        if isinstance(patch_requirements, Mapping):
            patch_requirements_chars += json_char_count(patch_requirements)
    return {
        "fixed_instruction_chars": max(0, len(prompt_text) - batch_chars),
        "batch_json_chars": batch_chars,
        "factor_options_json_chars": factor_options_chars,
        "materials_json_chars": materials_chars,
        "batch_json_overhead_chars": max(0, batch_chars - factor_options_chars - materials_chars),
        "material_breakdown_chars": {
            "source_passages_json_chars": source_passages_chars,
            "source_quote_text_chars": source_quote_text_chars,
            "factor_hints_json_chars": factor_hints_chars,
            "object_profile_json_chars": object_profile_chars,
            "patch_requirements_json_chars": patch_requirements_chars,
            "claim_summary_text_chars": claim_summary_text_chars,
        },
    }


def prompt_budget_snapshot(batch: Mapping[str, Any], prompt_text: str) -> dict[str, Any]:
    payload = slim_batch_for_prompt(batch)
    materials = payload.get("materials") if isinstance(payload.get("materials"), list) else []
    factor_options = payload.get("factor_options_by_factor") if isinstance(payload.get("factor_options_by_factor"), Mapping) else {}
    rule_counts = Counter(text(material.get("rule_code")) for material in materials if isinstance(material, Mapping) and text(material.get("rule_code")))
    hint_materials = 0
    hint_mapped_refs = 0
    hint_withheld_refs = 0
    for material in materials:
        if not isinstance(material, Mapping):
            continue
        hints = material.get("factor_hint_suggestions")
        if not isinstance(hints, Mapping) or not hints:
            continue
        hint_materials += 1
        mapped = hints.get("mapped_refs") if isinstance(hints.get("mapped_refs"), Mapping) else {}
        withheld = hints.get("withheld_refs") if isinstance(hints.get("withheld_refs"), Mapping) else {}
        hint_mapped_refs += len(mapped)
        hint_withheld_refs += len(withheld)
    option_counts = {
        text(factor_name): len(rows)
        for factor_name, rows in factor_options.items()
        if text(factor_name) and isinstance(rows, list)
    }
    calibration_sections = [
        rule_code
        for rule_code in ("appointment_delegation", "team_building", "talent_discovery")
        if rule_code in rule_counts
    ]
    return {
        "prompt_chars": len(prompt_text),
        "prompt_bytes_utf8": len(prompt_text.encode("utf-8")),
        "estimated_prompt_tokens": prompt_token_estimate(prompt_text),
        "estimated_prompt_tokens_method": "ceil(prompt_chars / 2)",
        "batch_material_count": len(materials),
        "rule_counts": dict(sorted(rule_counts.items())),
        "factor_option_factor_count": len(option_counts),
        "factor_option_count": sum(option_counts.values()),
        "factor_option_counts_by_factor": dict(sorted(option_counts.items())),
        "factor_hint_suggestion_materials": hint_materials,
        "factor_hint_mapped_refs": hint_mapped_refs,
        "factor_hint_withheld_refs": hint_withheld_refs,
        "calibration_prompt_injected": bool(calibration_sections),
        "calibration_sections": calibration_sections,
        "cost_attribution": prompt_cost_attribution(payload, prompt_text),
    }


def sum_nested_int(budgets: Sequence[Mapping[str, Any]], *keys: str) -> int:
    total = 0
    for budget in budgets:
        current: Any = budget
        for key in keys:
            current = current.get(key) if isinstance(current, Mapping) else None
        total += int(current or 0)
    return total


def summarize_prompt_budgets(tasks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    budgets = [task.get("prompt_budget") for task in tasks if isinstance(task.get("prompt_budget"), Mapping)]
    if not budgets:
        return {
            "prompt_chars_total": 0,
            "prompt_chars_max": 0,
            "estimated_prompt_tokens_total": 0,
            "estimated_prompt_tokens_max": 0,
            "estimated_prompt_tokens_method": "ceil(prompt_chars / 2)",
        }
    max_prompt = max(budgets, key=lambda item: int(item.get("prompt_chars") or 0))
    calibration_sections = sorted({section for budget in budgets for section in (budget.get("calibration_sections") or []) if text(section)})
    return {
        "prompt_chars_total": sum(int(budget.get("prompt_chars") or 0) for budget in budgets),
        "prompt_chars_max": int(max_prompt.get("prompt_chars") or 0),
        "estimated_prompt_tokens_total": sum(int(budget.get("estimated_prompt_tokens") or 0) for budget in budgets),
        "estimated_prompt_tokens_max": int(max_prompt.get("estimated_prompt_tokens") or 0),
        "estimated_prompt_tokens_method": "ceil(prompt_chars / 2)",
        "factor_option_count_total": sum(int(budget.get("factor_option_count") or 0) for budget in budgets),
        "factor_hint_suggestion_materials": sum(int(budget.get("factor_hint_suggestion_materials") or 0) for budget in budgets),
        "factor_hint_mapped_refs": sum(int(budget.get("factor_hint_mapped_refs") or 0) for budget in budgets),
        "factor_hint_withheld_refs": sum(int(budget.get("factor_hint_withheld_refs") or 0) for budget in budgets),
        "calibration_sections": calibration_sections,
        "cost_attribution": {
            "fixed_instruction_chars": sum_nested_int(budgets, "cost_attribution", "fixed_instruction_chars"),
            "batch_json_chars": sum_nested_int(budgets, "cost_attribution", "batch_json_chars"),
            "factor_options_json_chars": sum_nested_int(budgets, "cost_attribution", "factor_options_json_chars"),
            "materials_json_chars": sum_nested_int(budgets, "cost_attribution", "materials_json_chars"),
            "source_quote_text_chars": sum_nested_int(budgets, "cost_attribution", "material_breakdown_chars", "source_quote_text_chars"),
            "factor_hints_json_chars": sum_nested_int(budgets, "cost_attribution", "material_breakdown_chars", "factor_hints_json_chars"),
        },
    }


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
            "task_kind": "retrieval_v3_factorization",
            "batch_id": text(batch.get("batch_id")),
            "batch_path": repo_relative(batch_path),
            "material_count": int(batch.get("material_count") or len(flatten_batch_materials(batch))),
            "prompt_path": repo_relative(prompt_path),
            "last_message_path": repo_relative(last_message_path),
            "log_path": repo_relative(log_path),
            "expected_outputs": [expected_output_contract(patch_path)],
            "argv": agent_runtime_config.codex_task_argv(
                "factorization",
                exec_args=[
                    "-C", str(ROOT), "--dangerously-bypass-approvals-and-sandbox",
                    "--output-last-message", str(last_message_path), "--json", "-",
                ],
            ),
        }
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        last_message_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_text = prompt_for_batch(batch=batch, output_jsonl=patch_path)
        task["prompt_budget"] = prompt_budget_snapshot(batch, prompt_text)
        prompt_path.write_text(prompt_text, encoding="utf-8")
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
        "generated_by": "scripts/dev/retrieval_v3_factorization_worklists.py",
        "totals": {
            "tasks": len(tasks),
            "materials": sum(int(task.get("material_count") or 0) for task in tasks),
        },
        "prompt_budget_summary": summarize_prompt_budgets(tasks),
        "files": {
            "tasks_jsonl": repo_relative(tasks_path),
            "markdown": repo_relative(md_path),
        },
        "tasks": [
            {
                "task_code": task["task_code"],
                "batch_id": task["batch_id"],
                "material_count": task["material_count"],
                "patch_path": expected_output_contracts_path(task),
                "prompt_budget": task.get("prompt_budget") or {},
            }
            for task in tasks
        ],
    }
    write_json(summary_path, summary)
    lines = [
        "# retrieval_v3 factorization Codex tasks",
        "",
        f"- tasks: `{summary['totals']['tasks']}`",
        f"- materials: `{summary['totals']['materials']}`",
        f"- prompt_chars_total: `{summary['prompt_budget_summary']['prompt_chars_total']}`",
        f"- estimated_prompt_tokens_total: `{summary['prompt_budget_summary']['estimated_prompt_tokens_total']}`",
        f"- fixed_instruction_chars: `{summary['prompt_budget_summary']['cost_attribution']['fixed_instruction_chars']}`",
        f"- batch_json_chars: `{summary['prompt_budget_summary']['cost_attribution']['batch_json_chars']}`",
        f"- source_quote_text_chars: `{summary['prompt_budget_summary']['cost_attribution']['source_quote_text_chars']}`",
        "",
        "| task | batch | materials | prompt chars | est. tokens | factor options | hints | patch |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for task in tasks:
        budget = task.get("prompt_budget") if isinstance(task.get("prompt_budget"), Mapping) else {}
        hint_refs = int(budget.get("factor_hint_mapped_refs") or 0) + int(budget.get("factor_hint_withheld_refs") or 0)
        lines.append(
            f"| `{task['task_code']}` | `{task['batch_id']}` | {task['material_count']} | "
            f"{budget.get('prompt_chars', 0)} | {budget.get('estimated_prompt_tokens', 0)} | "
            f"{budget.get('factor_option_count', 0)} | {hint_refs} | `{expected_output_contracts_path(task)}` |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary






def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build read-only retrieval_v3 material factorization worklists.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    worklist = subparsers.add_parser("worklist", help="Build DB-backed factorization worklist.")
    worklist.add_argument("--env-file", type=Path)
    worklist.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    worklist.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    worklist.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    worklist.add_argument("--rule-code", default=DEFAULT_RULE_CODE)
    worklist.add_argument("--formula-code", default=DEFAULT_FORMULA_CODE)
    worklist.add_argument("--scope", choices=SCOPES, default="accepted-packs")
    worklist.add_argument("--batch-size", type=int)
    worklist.add_argument("--target-name", action="append", default=[], help="Restrict worklist to this emperor/person target name. Repeatable.")
    worklist.add_argument("--target-code", action="append", default=[], help="Restrict worklist to this retrieval target code. Repeatable.")
    worklist.add_argument("--source-pack-code", action="append", default=[], help="Restrict worklist to explicit source pack code. Repeatable; allows draft shadow packs.")
    worklist.add_argument("--include-judged", action="store_true", help="Explicit full re-review mode; include bindings that already have a live judgment for this formula.")
    for name in ("--output-json", "--output-md"):
        worklist.add_argument(name, type=Path, required=True)
    worklist.add_argument("--batch-output-dir", type=Path)
    template = subparsers.add_parser("template", help="Write a blank factorization patch JSONL for a batch.")
    for name in ("--batch-json", "--output-jsonl"):
        template.add_argument(name, type=Path, required=True)
    validate = subparsers.add_parser("validate-patch", help="Validate a factorization patch JSONL against a batch.")
    for name in ("--batch-json", "--patch-jsonl", "--output-json", "--output-md"):
        validate.add_argument(name, type=Path, required=True)
    validate.add_argument("--fail-on-issue", action="store_true")
    tasks = subparsers.add_parser("tasks", help="Build Codex task prompts from factorization batch JSON files.")
    tasks.add_argument("--batch-dir", type=Path)
    tasks.add_argument("--batch-json", type=Path, action="append", default=[])
    tasks.add_argument("--output-root", type=Path, required=True)
    run_plan = subparsers.add_parser("run-plan", help="Run or start Codex factorization tasks via codex-win agent.")
    run_plan.add_argument("--tasks-jsonl", type=Path, required=True)
    for name in ("--execute", "--background", "--respect-task-argv", "--search"):
        run_plan.add_argument(name, action="store_true")
    for name in ("--output", "--agent-output-root"):
        run_plan.add_argument(name, type=Path)
    for name, default in (("--limit", 0), ("--max-workers", None), ("--timeout-seconds", None)):
        run_plan.add_argument(name, type=int, default=default)
    run_plan.add_argument("--codex-win-bin", default="codex-win")
    run_plan.add_argument("--sandbox-profile", choices=("read-only", "local-write", "bypass"), default="local-write")
    run_plan.add_argument("--permission-profile", choices=("review-only", "tmp-jsonl-review", "local-write", "repo-editor", "bypass"))
    run_plan.add_argument("--deny-policy", choices=("fail", "continue-with-final", "deny-fail", "deny-continue", "deny-rewrite"))
    run_plan.add_argument("--write-root", type=Path, action="append", default=[])
    run_plan.add_argument("--git-snapshot", choices=("minimal", "full", "none"))
    recover = subparsers.add_parser("recover-patches", help="Recover JSONL patches from Codex task last-message/log files.")
    for name in ("--tasks-jsonl", "--output-json"):
        recover.add_argument(name, type=Path, required=True)
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
        runtime = agent_runtime_config.resolve_agent_stage("factorization")
        payload = run_codex_tasks(
            tasks_path=args.tasks_jsonl,
            execute=args.execute,
            background=args.background,
            limit=args.limit,
            output=args.output,
            agent_output_root=args.agent_output_root,
            codex_win_bin=args.codex_win_bin,
            max_workers=int(args.max_workers or runtime["max_workers"]),
            timeout_seconds=int(args.timeout_seconds or runtime["timeout_seconds"]),
            sandbox_profile=args.sandbox_profile,
            permission_profile=args.permission_profile,
            deny_policy=args.deny_policy,
            write_roots=args.write_root,
            git_snapshot=args.git_snapshot,
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
    runtime = agent_runtime_config.resolve_agent_stage("factorization")
    payload = build_worklist(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        item_code=args.item_code,
        rule_code=args.rule_code,
        formula_code=args.formula_code,
        scope=args.scope,
        batch_size=int(args.batch_size or runtime["batch_size"]),
        source_pack_codes=args.source_pack_code,
        include_judged=args.include_judged,
        target_names=args.target_name,
        target_codes=args.target_code,
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if args.batch_output_dir:
        write_batch_files(args.batch_output_dir, payload.get("suggested_batches") or [])
    result = {"ok": payload["ok"], "output_json": repo_relative(args.output_json), "materials": payload["totals"]["materials"], "suggested_batches": payload["totals"]["suggested_batches"]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
