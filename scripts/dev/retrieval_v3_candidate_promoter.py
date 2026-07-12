from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import ImportPlanError, json_param, stable_hash  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_ITEM_CODE = "I5B"
SCOPES = ("accepted-packs", "active-targets")
FORMAL_RULES = {
    "appointment_delegation",
    "team_building",
    "talent_discovery",
    "tolerate_talent",
    "anti_nepotism",
}
PROMOTABLE_HINT_STATUSES = {"", "formal_candidate", "current_rule_candidate"}
APPOINTMENT_DELEGATION_REQUIRED_CHAIN_KEYS = (
    "has_appointment_or_authorization",
    "has_named_actor",
    "has_task_or_responsibility",
)
APPOINTMENT_DELEGATION_FEEDBACK_CHAIN_KEYS = ("has_result_or_feedback", "has_continuity_or_reuse")
APPOINTMENT_DELEGATION_OBJECT_ROLES = {
    "appointed_actor",
    "entrusted_actor",
    "delegated_actor",
    "strategic_advisor",
    "military_commander",
    "civil_official",
    "authority_revoked_target",
    "misappointed_actor",
    "misdelegated_actor",
    "misentrusted_actor",
}


class CandidatePromoterError(ImportPlanError):
    pass


@dataclass(frozen=True)
class PromotionSpec:
    predicate: str
    object_role: str
    direction: str
    reason_code: str
    reason_note: str
    object_name_override: str = ""


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def contains_any(value: str, terms: Sequence[str]) -> tuple[str, ...]:
    return tuple(term for term in terms if term and term in value)


def payload_haystack(row: Mapping[str, Any]) -> str:
    source = source_binding(row)
    payload = as_mapping(row.get("candidate_payload"))
    claim_payload = as_mapping(row.get("claim_payload"))
    fact_payload = as_mapping(claim_payload.get("fact_payload"))
    if text(payload.get("created_from")) == "retrieval_v3_cross_rule_router":
        parts = [
            text(row.get("claim_summary")),
            text(row.get("object_name")),
            stable_json(fact_payload) if fact_payload else "",
        ]
        return " ".join(part for part in parts if part)
    parts = [
        text(row.get("candidate_reason")),
        text(row.get("claim_summary")),
        text(row.get("object_name")),
        stable_json(source),
    ]
    return " ".join(part for part in parts if part)


def source_binding(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = as_mapping(row.get("candidate_payload"))
    return as_mapping(payload.get("source_binding"))


def candidate_payload_variants(row: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    payload = as_mapping(row.get("candidate_payload"))
    source = source_binding(row)
    claim_payload = as_mapping(row.get("claim_payload"))
    fact_payload = as_mapping(claim_payload.get("fact_payload"))
    variants = [
        payload,
        as_mapping(payload.get("candidate_payload")),
        source,
        as_mapping(source.get("candidate_payload")),
        claim_payload,
        fact_payload,
    ]
    return tuple(variant for variant in variants if variant)


def candidate_hint_status(row: Mapping[str, Any]) -> str:
    payload = as_mapping(row.get("candidate_payload"))
    raw = text(row.get("hint_status") or payload.get("hint_status") or payload.get("route_status"))
    return raw


def target_object_index(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("target_object_index")
    return value if isinstance(value, Mapping) else {}


def claim_object_target(row: Mapping[str, Any]) -> Mapping[str, Any]:
    object_name = text(row.get("object_name"))
    if not object_name:
        return {}
    return as_mapping(target_object_index(row).get(object_name))


def explicit_talent_object_name(row: Mapping[str, Any]) -> str:
    keys = (
        "talent_object",
        "talent_name",
        "target_talent",
        "target_object",
        "recommended_talent",
        "recommended_object",
        "recognized_talent",
        "recognized_object",
        "discovered_talent",
        "discovered_object",
    )
    current = text(row.get("object_name"))
    for payload in candidate_payload_variants(row):
        for key in keys:
            value = text(payload.get(key))
            if value and value != current:
                return value
    return ""


def infer_named_talent_object(row: Mapping[str, Any], *, reason_code: str) -> str:
    explicit = explicit_talent_object_name(row)
    if explicit:
        return explicit
    names = sorted(
        (name for name in target_object_index(row) if text(name) and text(name) != text(row.get("object_name"))),
        key=len,
        reverse=True,
    )
    if not names:
        return ""
    haystack = payload_haystack(row)
    if reason_code == "recommended_talent":
        markers = ("推荐", "荐举", "举荐", "荐", "追还", "言", "称")
    elif reason_code == "recognized_talent":
        markers = ("识别", "识才", "知其才", "知人", "赏识", "认为", "怪其", "见而")
    else:
        markers = ("拔擢", "提拔", "简拔", "擢用", "擢任", "延揽", "访求", "征辟")
    for name in names:
        escaped = re.escape(name)
        for marker in markers:
            if re.search(re.escape(marker) + rf"[^，。；;：:、]{{0,18}}{escaped}", haystack):
                return name
            if re.search(rf"{escaped}[^，。；;：:、]{{0,18}}" + re.escape(marker), haystack):
                return name
    return ""


def harmed_talent_object_name(row: Mapping[str, Any]) -> str:
    current = text(row.get("object_name"))
    for payload in candidate_payload_variants(row):
        value = text(payload.get("harmed_talent") or payload.get("harmed_object") or payload.get("victim_talent") or payload.get("victim_object"))
        if value and value != current and value in target_object_index(row):
            return value
        fact_object = text(payload.get("object"))
        if fact_object and fact_object != current and fact_object in target_object_index(row):
            return fact_object
    return ""


def promotion_object_fields(row: Mapping[str, Any], spec: PromotionSpec) -> tuple[dict[str, Any] | None, str]:
    if not spec.object_name_override:
        if not row.get("object_id"):
            candidate = claim_object_target(row)
            if not candidate:
                return None, "missing_source_object_link"
            return {
                "object_name": text(candidate.get("canonical_name")) or text(row.get("object_name")),
                "object_id": candidate.get("object_id"),
                "target_object_id": candidate.get("target_object_id"),
                "object_identity_key": text(candidate.get("object_identity_key")),
                "object_canonical_name": text(candidate.get("canonical_name")) or text(row.get("object_name")),
            }, ""
        return {
            "object_name": text(row.get("object_name")),
            "object_id": row.get("object_id"),
            "target_object_id": row.get("target_object_id"),
            "object_identity_key": text(row.get("object_identity_key")),
            "object_canonical_name": text(row.get("object_canonical_name")),
        }, ""
    candidate = as_mapping(target_object_index(row).get(spec.object_name_override))
    if not candidate:
        return None, "missing_talent_target_object_link"
    return {
        "object_name": text(candidate.get("canonical_name")) or spec.object_name_override,
        "object_id": candidate.get("object_id"),
        "target_object_id": candidate.get("target_object_id"),
        "object_identity_key": text(candidate.get("object_identity_key")),
        "object_canonical_name": text(candidate.get("canonical_name")) or spec.object_name_override,
    }, ""


def appointment_delegation_protocol_payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    for payload in candidate_payload_variants(row):
        if (
            "appointment_delegation_chain" in payload
            or "scoring_candidate" in payload
            or "candidate_role" in payload
            or "same_chain_outcome_summary" in payload
        ):
            return payload
    return {}


def appointment_delegation_protocol_direction(row: Mapping[str, Any]) -> str:
    payload = appointment_delegation_protocol_payload(row)
    direction = text(payload.get("direction"))
    if direction:
        return direction
    direction = text(row.get("candidate_direction") or row.get("claim_direction"))
    if direction:
        return direction
    for nested_payload in candidate_payload_variants(row):
        direction = text(nested_payload.get("direction"))
        if direction:
            return direction
    return ""


def appointment_delegation_object_role(row: Mapping[str, Any], default_role: str) -> str:
    role = text(appointment_delegation_protocol_payload(row).get("candidate_role"))
    if role in APPOINTMENT_DELEGATION_OBJECT_ROLES:
        return role
    return default_role


def appointment_delegation_protocol_allows_scoring(row: Mapping[str, Any]) -> bool:
    payload = appointment_delegation_protocol_payload(row)
    if payload.get("scoring_candidate") is not True:
        return False
    if payload.get("usable_for_scoring_cluster") is not True:
        return False
    direction = appointment_delegation_protocol_direction(row)
    if direction and direction not in {"positive", "negative"}:
        return False
    chain = as_mapping(payload.get("appointment_delegation_chain"))
    return all(chain.get(key) is True for key in APPOINTMENT_DELEGATION_REQUIRED_CHAIN_KEYS) and any(
        chain.get(key) is True for key in APPOINTMENT_DELEGATION_FEEDBACK_CHAIN_KEYS
    )


def skip_reason(row: Mapping[str, Any]) -> str:
    if row.get("candidate_id") is None:
        return "missing_candidate_id"
    if text(row.get("candidate_rule_code")) not in FORMAL_RULES:
        return "non_formal_rule"
    if row.get("candidate_contract_rule_id") is None:
        return "missing_candidate_contract_rule"
    hint_status = candidate_hint_status(row)
    if hint_status not in PROMOTABLE_HINT_STATUSES:
        return hint_status
    candidate_item_code = text(row.get("candidate_item_code"))
    if candidate_item_code and candidate_item_code != DEFAULT_ITEM_CODE:
        return "candidate_item_not_supported"
    if text(row.get("review_status")) not in {"pending", "accepted", "resolved"}:
        return "candidate_status_not_promotable"
    payload = appointment_delegation_protocol_payload(row)
    if text(row.get("candidate_rule_code")) == "appointment_delegation" and payload.get("formal_binding_allowed") is False:
        return "formal_binding_not_allowed"
    if (
        text(row.get("candidate_rule_code")) == "appointment_delegation"
        and not appointment_delegation_protocol_allows_scoring(row)
    ):
        return "appointment_delegation_not_scoring_candidate"
    if not row.get("object_id") and not claim_object_target(row):
        return "missing_source_object_link"
    if row.get("object_id") and text(row.get("source_link_review_status")) != "accepted":
        return "source_object_link_not_accepted"
    return ""


def resolve_appointment_delegation(row: Mapping[str, Any]) -> PromotionSpec | None:
    if not appointment_delegation_protocol_allows_scoring(row):
        return None
    direction = appointment_delegation_protocol_direction(row)
    if direction == "positive":
        role = appointment_delegation_object_role(row, "appointed_actor")
        return PromotionSpec("appointed_or_delegated_authority", role, "positive", "item_wide_appointment_delegation", "I5B-wide 材料显示人物获得任用、委任、信任或实质授权，可进入任用授权质量因子化。")
    if direction == "negative":
        role = appointment_delegation_object_role(row, "misappointed_actor")
        return PromotionSpec("misappointed_or_misdelegated_authority", role, "negative", "item_wide_misappointment_delegation", "I5B-wide 材料标为负向任用、错授或授权后果，可进入任用授权质量因子化复核。")
    return None


def resolve_team_building(row: Mapping[str, Any]) -> PromotionSpec | None:
    source = source_binding(row)
    source_direction = text(source.get("direction")) or text(row.get("claim_direction"))
    if source_direction not in {"positive", "negative"}:
        return None
    if source_direction == "negative":
        return PromotionSpec("team_member", "team_member", "negative", "team_pool_member", "规则表要求皇帝对象池全部人才对象参与团队聚合；该负向对象可作为团队质量负贡献候选。")
    return PromotionSpec("team_member", "team_member", "positive", "team_pool_member", "规则表要求皇帝对象池全部人才对象参与团队聚合；该对象可作为建立团队成员候选。")


def resolve_talent_discovery(row: Mapping[str, Any]) -> PromotionSpec | None:
    haystack = payload_haystack(row)
    if contains_any(haystack, ("荐", "推荐", "举荐")):
        return PromotionSpec(
            "recommended_talent",
            "recommended_talent",
            "positive",
            "recommended_talent",
            "材料明确出现荐举或推荐人才线索，可作为发现人才正向候选。",
            infer_named_talent_object(row, reason_code="recommended_talent"),
        )
    recognized_override = infer_named_talent_object(row, reason_code="recognized_talent")
    if contains_any(haystack, ("识才", "知其才", "知人善任", "赏识其才")) or (
        recognized_override and contains_any(haystack, ("识别", "见而", "认为", "怪其"))
    ):
        return PromotionSpec(
            "recognized_talent",
            "recognized_talent",
            "positive",
            "recognized_talent",
            "材料明确出现识才或知人线索，可作为发现人才正向候选。",
            recognized_override,
        )
    if contains_any(haystack, ("拔擢", "提拔", "简拔", "擢用", "擢任", "延揽", "访求", "征辟")):
        return PromotionSpec(
            "discovered_talent",
            "discovered_talent",
            "positive",
            "discovered_talent",
            "材料明确出现拔擢、延揽或访求人材线索，可作为发现人才正向候选。",
            infer_named_talent_object(row, reason_code="discovered_talent"),
        )
    return None


def resolve_tolerate_talent(row: Mapping[str, Any]) -> PromotionSpec | None:
    haystack = payload_haystack(row)
    source = source_binding(row)
    source_direction = text(source.get("direction")) or text(row.get("claim_direction"))
    if source_direction != "positive":
        if text(row.get("source_rule_code")) == "i5b_item_wide":
            object_name = text(row.get("object_name"))
            harm_terms = contains_any(haystack, ("诛", "杀", "斩", "击", "执", "废", "黜", "夷", "恐惧", "起疑", "亡入", "反乱"))
            if object_name and object_name in haystack and harm_terms:
                return PromotionSpec(
                    "harmed_talent",
                    "harmed_talent",
                    "negative",
                    "item_wide_harmed_talent",
                    "I5B-wide 材料提示处置、疑忌或伤害人才链条，可进入容人保全负向因子化复核。",
                    harmed_talent_object_name(row),
                )
        return None
    if contains_any(haystack, ("纳谏", "进谏", "直言", "言事", "诤", "谏")):
        return PromotionSpec("accepted_remonstrance_actor", "remonstrance_actor", "positive", "accepted_remonstrance", "材料明确出现纳谏、直言或进谏互动，可作为容人保全正向候选。")
    return None


def resolve_anti_nepotism(row: Mapping[str, Any]) -> PromotionSpec | None:
    haystack = payload_haystack(row)
    source = source_binding(row)
    source_direction = text(source.get("direction")) or text(row.get("claim_direction"))
    if contains_any(haystack, ("抑制亲", "不私", "禁私", "惩治外戚", "抑外戚", "防朋党")):
        return PromotionSpec("resisted_nepotism", "anti_nepotism_resisted_actor", "positive", "resisted_nepotism", "材料明确指向抑制亲私、外戚或朋党干预，可作为反亲私正向候选。")
    if source_direction != "negative":
        return None
    if contains_any(haystack, ("外戚受宠", "宗室受宠", "亲族受宠", "任亲", "亲族贪纵", "家族骄纵", "家族党羽", "外戚专权", "宗室专权")):
        return PromotionSpec("favored_kin", "nepotistic_beneficiary", "negative", "favored_kin", "材料明确出现外戚、宗室或亲族受益线索，可作为反亲私负向候选。")
    if contains_any(haystack, ("近臣", "私爱", "私宠", "受宠", "幸臣", "纳贿", "受贿", "贿赂")):
        return PromotionSpec("favored_private_person", "favorite_beneficiary", "negative", "favored_private_person", "材料明确出现近臣、私宠或贿赂受益线索，可作为反亲私负向候选。")
    if contains_any(haystack, ("朋党", "结党", "谮害", "谮毁", "谮告", "干预任用", "专擅政务")):
        return PromotionSpec("interfered_appointment", "appointment_interferer", "negative", "appointment_interference", "材料明确出现朋党、结党或干预任用线索，可作为反亲私负向候选。")
    return None


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
    raise CandidatePromoterError(f"unsupported scope: {scope}")


def source_pack_predicate(scope: str, source_pack_codes: Sequence[str] = ()) -> str:
    codes = [text(code) for code in source_pack_codes if text(code)]
    if codes:
        return "sp.pack_code = any(%s) and sp.coverage_status = 'passed'"
    return scope_predicate(scope)


RESOLVERS = {
    "appointment_delegation": resolve_appointment_delegation,
    "team_building": resolve_team_building,
    "talent_discovery": resolve_talent_discovery,
    "tolerate_talent": resolve_tolerate_talent,
    "anti_nepotism": resolve_anti_nepotism,
}


def resolve_candidate(row: Mapping[str, Any]) -> tuple[PromotionSpec | None, str]:
    reason = skip_reason(row)
    if reason:
        return None, reason
    rule_code = text(row.get("candidate_rule_code"))
    resolver = RESOLVERS.get(rule_code)
    if resolver is None:
        return None, "unsupported_rule"
    spec = resolver(row)
    if spec is None:
        return None, f"unresolved_{rule_code}"
    return spec, ""


def candidate_payload_allows_scoring(row: Mapping[str, Any]) -> bool:
    payload = as_mapping(row.get("candidate_payload"))
    if payload.get("usable_for_scoring_cluster") is False:
        return False
    source = source_binding(row)
    if source.get("usable_for_scoring_cluster") is False:
        return False
    source_payload = as_mapping(source.get("candidate_payload"))
    if source_payload.get("usable_for_scoring_cluster") is False:
        return False
    return True


def promotion_usable_for_scoring(row: Mapping[str, Any], spec: PromotionSpec) -> bool:
    if row.get("candidate_id") is None:
        return False
    if "review" in spec.reason_code:
        return False
    if text(row.get("source_rule_code")) == "i5b_item_wide" and text(row.get("candidate_rule_code")) == "appointment_delegation":
        return candidate_payload_allows_scoring(row) and appointment_delegation_protocol_allows_scoring(row)
    return candidate_payload_allows_scoring(row)


def binding_code_for(row: Mapping[str, Any], spec: PromotionSpec) -> str:
    return "CRB-PROM-" + stable_hash(
        [text(row.get("candidate_code")), text(row.get("candidate_rule_code")), spec.predicate, spec.direction, spec.object_role],
        length=20,
    )


def material_link_code_for(row: Mapping[str, Any], role: str, *, object_identity_key: str = "") -> str:
    object_key = text(object_identity_key) or text(row.get("object_identity_key"))
    return "MOL-" + stable_hash([text(row.get("claim_code")), object_key, role], length=16)


def fetch_candidate_rows(
    cur: Any,
    *,
    item_code: str,
    source_rule_code: str,
    scope: str,
    candidate_rule_codes: Sequence[str],
    emperors: Sequence[str],
    source_pack_codes: Sequence[str] = (),
) -> list[dict[str, Any]]:
    clauses = [
        "c.source_item_code = %s",
        "c.source_rule_code = %s",
        "c.candidate_contract_rule_id is not null",
        "c.hint_status in ('formal_candidate', 'current_rule_candidate')",
        "coalesce(c.candidate_payload->>'hint_status', '') <> 'future_rule_hint'",
        "coalesce(c.candidate_payload->>'route_status', '') <> 'future_rule_hint'",
    ]
    params: list[Any] = [item_code, source_rule_code]
    if candidate_rule_codes:
        clauses.append("c.candidate_rule_code = any(%s)")
        params.append(list(candidate_rule_codes))
    if emperors:
        clauses.append("rt.emperor_name = any(%s)")
        params.append(list(emperors))
    codes = [text(code) for code in source_pack_codes if text(code)]
    source_pack_params: list[Any] = [codes] if codes else []
    cur.execute(
        f"""
        select
            c.id as candidate_id,
            c.candidate_code,
            c.claim_id,
            c.source_contract_rule_id,
            c.candidate_contract_rule_id,
            c.source_item_code,
            c.source_rule_code,
            c.candidate_item_code,
            c.candidate_rule_code,
            c.candidate_lane,
            c.hint_status,
            c.required_facts_present,
            c.routed_by_profile,
            c.candidate_reason,
            c.confidence as candidate_confidence,
            c.review_status::text as review_status,
            c.resolved_binding_id,
            c.candidate_payload,
            mc.claim_code,
            mc.claim_summary,
            mc.claim_payload,
            mc.object_name,
            mc.object_group_key,
            mc.direction::text as claim_direction,
            sp.id as source_pack_id,
            sp.pack_code as source_pack_code,
            rt.id as target_id,
            rt.target_code,
            rt.emperor_name,
            rt.item_code,
            mol.id as source_link_id,
            mol.object_id,
            mol.target_object_id,
            mol.role as source_link_role,
            mol.confidence as source_link_confidence,
            mol.review_status::text as source_link_review_status,
            o.object_identity_key,
            o.canonical_name as object_canonical_name,
            coalesce(target_object_index.target_object_index, '{{}}'::jsonb) as target_object_index,
            exists (
                select 1
                  from retrieval_v3.material_review_queue mrq
                 where mrq.claim_id = c.claim_id
                   and mrq.queue_status in ('ready', 'needs_review', 'running', 'blocked')
            ) as has_open_material_review
          from retrieval_v3.claim_rule_binding_candidates c
          join retrieval_v3.material_claims mc on mc.id = c.claim_id
          join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v3.retrieval_targets rt on rt.id = sp.target_id
          left join lateral (
              select mol1.*
                from retrieval_v3.material_object_links mol1
               where mol1.claim_id = c.claim_id
                 and (
                     nullif(c.candidate_payload->'source_binding'->>'object_role', '') is null
                     or mol1.role = c.candidate_payload->'source_binding'->>'object_role'
                 )
               order by
                   case
                       when nullif(c.candidate_payload->'source_binding'->>'object_role', '') is not null
                        and mol1.role = c.candidate_payload->'source_binding'->>'object_role' then 0
                       when mol1.role = 'claim_object' then 1
                       else 2
                   end,
                   mol1.id
               limit 1
          ) mol on true
          left join retrieval_v3.objects o on o.id = mol.object_id
          left join lateral (
              select jsonb_object_agg(
                         o2.canonical_name,
                         jsonb_build_object(
                             'object_id', o2.id,
                             'target_object_id', tob2.id,
                             'object_identity_key', o2.object_identity_key,
                             'canonical_name', o2.canonical_name
                         )
                     ) as target_object_index
                from retrieval_v3.target_objects tob2
                join retrieval_v3.objects o2 on o2.id = tob2.object_id
               where tob2.target_id = rt.id
                 and tob2.review_status = 'accepted'
          ) target_object_index on true
         where {" and ".join(clauses)}
           and {source_pack_predicate(scope, codes)}
         order by rt.emperor_name, c.candidate_rule_code, c.id
        """,
        [*params, *source_pack_params],
    )
    return [dict(row) for row in cur.fetchall()]


def build_plan(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    promotions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in rows:
        if row.get("has_open_material_review"):
            skipped.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "candidate_code": text(row.get("candidate_code")),
                    "candidate_rule_code": text(row.get("candidate_rule_code")),
                    "emperor_name": text(row.get("emperor_name")),
                    "object_name": text(row.get("object_name")),
                    "reason": "material_review_pending",
                    "claim_summary": text(row.get("claim_summary")),
                }
            )
            continue
        spec, reason = resolve_candidate(row)
        if spec is None:
            skipped.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "candidate_code": text(row.get("candidate_code")),
                    "candidate_rule_code": text(row.get("candidate_rule_code")),
                    "emperor_name": text(row.get("emperor_name")),
                    "object_name": text(row.get("object_name")),
                    "reason": reason,
                    "claim_summary": text(row.get("claim_summary")),
                }
            )
            continue
        object_fields, object_reason = promotion_object_fields(row, spec)
        if object_fields is None:
            skipped.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "candidate_code": text(row.get("candidate_code")),
                    "candidate_rule_code": text(row.get("candidate_rule_code")),
                    "emperor_name": text(row.get("emperor_name")),
                    "object_name": spec.object_name_override,
                    "reason": object_reason,
                    "claim_summary": text(row.get("claim_summary")),
                }
            )
            continue
        promotions.append(
            {
                "candidate_id": row.get("candidate_id"),
                "candidate_code": text(row.get("candidate_code")),
                "candidate_rule_code": text(row.get("candidate_rule_code")),
                "claim_id": row.get("claim_id"),
                "claim_code": text(row.get("claim_code")),
                "source_pack_id": row.get("source_pack_id"),
                "source_pack_code": text(row.get("source_pack_code")),
                "target_id": row.get("target_id"),
                "target_code": text(row.get("target_code")),
                "emperor_name": text(row.get("emperor_name")),
                "object_name": object_fields["object_name"],
                "object_id": object_fields["object_id"],
                "target_object_id": object_fields["target_object_id"],
                "object_identity_key": object_fields["object_identity_key"],
                "object_canonical_name": object_fields["object_canonical_name"],
                "source_object_name": text(row.get("object_name")),
                "source_link_id": row.get("source_link_id"),
                "source_link_role": text(row.get("source_link_role")),
                "source_link_confidence": row.get("source_link_confidence"),
                "candidate_contract_rule_id": row.get("candidate_contract_rule_id"),
                "candidate_confidence": row.get("candidate_confidence"),
                "binding_code": binding_code_for(row, spec),
                "link_code": material_link_code_for(row, spec.object_role, object_identity_key=text(object_fields["object_identity_key"])),
                "predicate": spec.predicate,
                "object_role": spec.object_role,
                "direction": spec.direction,
                "reason_code": spec.reason_code,
                "reason_note": spec.reason_note,
                "object_name_override": spec.object_name_override,
                "usable_for_scoring_cluster": promotion_usable_for_scoring(row, spec),
                "claim_summary": text(row.get("claim_summary")),
                "candidate_payload": row.get("candidate_payload") or {},
            }
        )
    promoted_by_rule = Counter(text(row.get("candidate_rule_code")) for row in promotions)
    skipped_by_reason = Counter(text(row.get("reason")) for row in skipped)
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_candidate_promoter.py",
        "write_db": False,
        "executed": False,
        "totals": {
            "candidate_rows": len(rows),
            "promotions": len(promotions),
            "skipped": len(skipped),
        },
        "promoted_by_rule": dict(sorted(promoted_by_rule.items())),
        "skipped_by_reason": dict(sorted(skipped_by_reason.items())),
        "sample_promotions": promotions[:20],
        "sample_skipped": skipped[:20],
        "promotions": promotions,
        "skipped": skipped,
    }


def upsert_binding(cur: Any, row: Mapping[str, Any]) -> int:
    payload = {
        "source": "retrieval_v3_candidate_promoter",
        "assessment_lane": "exception_resolved",
        "candidate_required": True,
        "candidate_id": row.get("candidate_id"),
        "candidate_code": text(row.get("candidate_code")),
        "source_link_id": row.get("source_link_id"),
        "source_link_role": text(row.get("source_link_role")),
        "reason_code": text(row.get("reason_code")),
        "reason_note": text(row.get("reason_note")),
        "usable_for_scoring_cluster": bool(row.get("usable_for_scoring_cluster")),
    }
    cur.execute(
        """
        insert into retrieval_v3.claim_rule_bindings (
            claim_id, contract_rule_id, rule_code, predicate, direction, object_role,
            usable_for_object_payload, usable_for_scoring_cluster, confidence, review_status,
            binding_payload, binding_code, raw_binding_code
        )
        values (%s, %s, %s, %s, %s, %s, false, %s, %s, 'pending', %s::jsonb, %s, '')
        on conflict on constraint rv3_claim_rule_bindings_uk do update set
            usable_for_scoring_cluster = (
                retrieval_v3.claim_rule_bindings.usable_for_scoring_cluster
                or excluded.usable_for_scoring_cluster
            ),
            confidence = coalesce(retrieval_v3.claim_rule_bindings.confidence, excluded.confidence),
            review_status = case
                when retrieval_v3.claim_rule_bindings.review_status in ('rejected', 'retired') then retrieval_v3.claim_rule_bindings.review_status
                else retrieval_v3.claim_rule_bindings.review_status
            end,
            binding_payload = retrieval_v3.claim_rule_bindings.binding_payload || excluded.binding_payload,
            binding_code = case
                when btrim(retrieval_v3.claim_rule_bindings.binding_code) = '' then excluded.binding_code
                else retrieval_v3.claim_rule_bindings.binding_code
            end,
            updated_at = now()
        returning id
        """,
        (
            int(row["claim_id"]),
            int(row["candidate_contract_rule_id"]),
            text(row.get("candidate_rule_code")),
            text(row.get("predicate")),
            text(row.get("direction")),
            text(row.get("object_role")),
            bool(row.get("usable_for_scoring_cluster")),
            row.get("candidate_confidence"),
            json_param(payload),
            text(row.get("binding_code")),
        ),
    )
    fetched = cur.fetchone()
    if not fetched or fetched.get("id") is None:
        raise CandidatePromoterError(f"failed to upsert binding for {row.get('candidate_code')}")
    return int(fetched["id"])


def upsert_object_link(cur: Any, row: Mapping[str, Any]) -> int:
    payload = {
        "source": "retrieval_v3_candidate_promoter",
        "candidate_id": row.get("candidate_id"),
        "candidate_code": text(row.get("candidate_code")),
        "source_link_id": row.get("source_link_id"),
        "source_link_role": text(row.get("source_link_role")),
    }
    cur.execute(
        """
        insert into retrieval_v3.material_object_links (
            link_code, claim_id, object_id, target_object_id, role,
            confidence, review_status, link_payload
        )
        values (%s, %s, %s, %s, %s, %s, 'accepted', %s::jsonb)
        on conflict on constraint rv3_material_object_links_uk do update set
            target_object_id = coalesce(retrieval_v3.material_object_links.target_object_id, excluded.target_object_id),
            confidence = case
                when excluded.confidence is null then retrieval_v3.material_object_links.confidence
                when retrieval_v3.material_object_links.confidence is null then excluded.confidence
                else greatest(retrieval_v3.material_object_links.confidence, excluded.confidence)
            end,
            review_status = case
                when retrieval_v3.material_object_links.review_status in ('rejected', 'retired') then retrieval_v3.material_object_links.review_status
                else excluded.review_status
            end,
            link_payload = retrieval_v3.material_object_links.link_payload || excluded.link_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("link_code")),
            int(row["claim_id"]),
            int(row["object_id"]),
            row.get("target_object_id"),
            text(row.get("object_role")),
            row.get("source_link_confidence"),
            json_param(payload),
        ),
    )
    fetched = cur.fetchone()
    if not fetched or fetched.get("id") is None:
        raise CandidatePromoterError(f"failed to upsert material_object_link for {row.get('candidate_code')}")
    return int(fetched["id"])


def attach_promoted_link_to_binding(cur: Any, row: Mapping[str, Any], *, binding_id: int, link_id: int) -> int:
    payload = {
        "promoted_material_object_link_id": link_id,
        "promoted_object_id": row.get("object_id"),
        "promoted_target_object_id": row.get("target_object_id"),
        "promoted_object_name": text(row.get("object_name")),
        "promoted_object_role": text(row.get("object_role")),
    }
    cur.execute(
        """
        update retrieval_v3.claim_rule_bindings
           set binding_payload = binding_payload || %s::jsonb,
               updated_at = now()
         where id = %s
        returning id
        """,
        (json_param(payload), binding_id),
    )
    fetched = cur.fetchone()
    if not fetched or fetched.get("id") is None:
        raise CandidatePromoterError(f"failed to attach promoted link to binding for {row.get('candidate_code')}")
    return int(fetched["id"])


def mark_candidate_resolved(cur: Any, row: Mapping[str, Any], *, binding_id: int, link_id: int) -> int:
    if row.get("candidate_id") is None:
        return 0
    payload = {
        "promotion": {
            "source": "retrieval_v3_candidate_promoter",
            "binding_id": binding_id,
            "binding_code": text(row.get("binding_code")),
            "material_object_link_id": link_id,
            "predicate": text(row.get("predicate")),
            "object_role": text(row.get("object_role")),
            "direction": text(row.get("direction")),
            "reason_code": text(row.get("reason_code")),
            "reason_note": text(row.get("reason_note")),
        }
    }
    cur.execute(
        """
        update retrieval_v3.claim_rule_binding_candidates
           set resolved_binding_id = %s,
               review_status = 'resolved'::retrieval_v3.rv3_review_status,
               candidate_payload = candidate_payload || %s::jsonb,
               updated_at = now()
         where id = %s
        returning id
        """,
        (binding_id, json_param(payload), int(row["candidate_id"])),
    )
    fetched = cur.fetchone()
    if not fetched or fetched.get("id") is None:
        raise CandidatePromoterError(f"failed to mark candidate resolved: {row.get('candidate_code')}")
    return int(fetched["id"])


def execute_promotions(cur: Any, promotions: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in promotions:
        binding_id = upsert_binding(cur, row)
        counts["retrieval_v3.claim_rule_bindings"] += 1
        link_id = upsert_object_link(cur, row)
        counts["retrieval_v3.material_object_links"] += 1
        attach_promoted_link_to_binding(cur, row, binding_id=binding_id, link_id=link_id)
        if mark_candidate_resolved(cur, row, binding_id=binding_id, link_id=link_id):
            counts["retrieval_v3.claim_rule_binding_candidates"] += 1
    return dict(sorted(counts.items()))


def reconcile_scoring_gates(
    cur: Any,
    *,
    item_code: str,
    scope: str,
    emperors: Sequence[str],
    source_pack_codes: Sequence[str],
) -> int:
    codes = [text(code) for code in source_pack_codes if text(code)]
    source_pack_params: list[Any] = [codes] if codes else []
    filters = [
        source_pack_predicate(scope, codes),
        "(%s = '' or rt.item_code = %s)",
    ]
    params: list[Any] = [*source_pack_params, item_code, item_code]
    emperor_filters = [text(emperor) for emperor in emperors if text(emperor)]
    if emperor_filters:
        filters.append("rt.emperor_name = any(%s)")
        params.append(emperor_filters)
    cur.execute(
        f"""
        update retrieval_v3.claim_rule_bindings crb
           set usable_for_scoring_cluster = false,
               binding_payload = crb.binding_payload || jsonb_build_object(
                   'scoring_gate',
                   jsonb_build_object(
                       'source',
                       'retrieval_v3_candidate_promoter',
                       'reason',
                       case
                           when position('review' in lower(coalesce(crb.binding_payload->>'reason_code', ''))) > 0 then 'review_candidate'
                           else 'payload_blocks_scoring'
                       end
                   )
               ),
               updated_at = now()
          from retrieval_v3.material_claims mc
          join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v3.retrieval_targets rt on rt.id = sp.target_id
         where crb.claim_id = mc.id
           and crb.usable_for_scoring_cluster
           and crb.binding_payload->>'source' = 'retrieval_v3_candidate_promoter'
           and (
                position('review' in lower(coalesce(crb.binding_payload->>'reason_code', ''))) > 0
                or crb.binding_payload->>'usable_for_scoring_cluster' = 'false'
           )
           and {" and ".join(filters)}
        returning crb.id
        """,
        params,
    )
    return len(cur.fetchall())


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 candidate promoter",
        "",
        f"- mode: `{'execute' if payload.get('executed') else 'dry_run'}`",
        f"- write_db: `{bool(payload.get('write_db'))}`",
        "",
        "## Totals",
        "",
    ]
    for key, value in sorted((payload.get("totals") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Promoted By Rule", ""])
    for key, value in sorted((payload.get("promoted_by_rule") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Skipped By Reason", ""])
    for key, value in sorted((payload.get("skipped_by_reason") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Sample Promotions", ""])
    for row in payload.get("sample_promotions") or []:
        lines.append(
            f"- `{row.get('emperor_name')}` / `{row.get('candidate_rule_code')}` / `{row.get('object_name')}` -> `{row.get('predicate')}` `{row.get('direction')}`: {row.get('claim_summary')}"
        )
    return "\n".join(lines) + "\n"


def run_promoter(
    *,
    env_file: Path | None,
    dsn_env: str,
    item_code: str,
    source_rule_code: str,
    scope: str,
    candidate_rule_codes: Sequence[str],
    emperors: Sequence[str],
    source_pack_codes: Sequence[str],
    execute: bool,
    schema_name: str = DEFAULT_PG_SCHEMA,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            rows = fetch_candidate_rows(
                cur,
                item_code=item_code,
                source_rule_code=source_rule_code,
                scope=scope,
                candidate_rule_codes=candidate_rule_codes,
                emperors=emperors,
                source_pack_codes=source_pack_codes,
            )
            plan = build_plan(rows)
            plan["item_code"] = item_code
            plan["source_rule_code"] = source_rule_code
            plan["scope"] = scope
            plan["candidate_rule_codes"] = list(candidate_rule_codes)
            plan["emperor_filters"] = list(emperors)
            plan["source_pack_codes"] = [text(code) for code in source_pack_codes if text(code)]
            plan["write_db"] = execute
            if execute:
                executed_counts = Counter(execute_promotions(cur, plan["promotions"]))
                reconciled = reconcile_scoring_gates(
                    cur,
                    item_code=item_code,
                    scope=scope,
                    emperors=emperors,
                    source_pack_codes=source_pack_codes,
                )
                if reconciled:
                    executed_counts["retrieval_v3.claim_rule_bindings_scoring_gate"] += reconciled
                plan["executed_counts"] = dict(sorted(executed_counts.items()))
                plan["executed"] = True
                conn.commit()
            else:
                conn.rollback()
    return plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote deterministic claim_rule_binding_candidates into formal claim_rule_bindings.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--source-rule-code", default="i5b_item_wide")
    parser.add_argument("--scope", choices=SCOPES, default="accepted-packs")
    parser.add_argument("--candidate-rule-code", action="append", default=[])
    parser.add_argument("--emperor", action="append", default=[])
    parser.add_argument("--source-pack-code", action="append", default=[], help="Restrict promotion to explicit source pack code. Repeatable; allows passed draft/shadow packs.")
    parser.add_argument("--execute", action="store_true", help="Actually write bindings/object links and resolve candidates. Omit for dry-run.")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_promoter(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        item_code=args.item_code,
        source_rule_code=args.source_rule_code,
        scope=args.scope,
        candidate_rule_codes=tuple(args.candidate_rule_code or ()),
        emperors=tuple(args.emperor or ()),
        source_pack_codes=tuple(args.source_pack_code or ()),
        execute=args.execute,
        schema_name=args.pg_schema,
    )
    write_json(args.output_json, payload)
    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
