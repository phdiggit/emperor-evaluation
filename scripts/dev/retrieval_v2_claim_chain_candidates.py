from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_claim_quality as claim_quality  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_claim_event_groups import owner_scope_values  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_STATUSES = ("active",)
CHAIN_MIN_MEMBERS = 3

SETUP_ACTION_TYPES = {"任命", "授权"}
POWER_ACTION_TYPES = {"授权", "任命"}
DAMAGE_ACTION_TYPES = {"处置", "战役", "其他"}
TERMINAL_ACTION_TYPES = {"处置"}
EVALUATION_FACT_TYPES = {"evaluation"}

SETUP_TERMS = ("拜", "任", "授", "封", "擢", "迁", "命", "诏")
POWER_TERMS = ("独相", "独专", "专权", "专擅", "擅权", "宠任", "宠遇", "总", "领", "同知")
DAMAGE_TERMS = (
    "不奏",
    "径行",
    "隐匿",
    "匿",
    "不上闻",
    "生杀",
    "黜陟",
    "乱",
    "杀伤",
    "溺死",
    "薄义",
    "重利",
)
TERMINAL_TERMS = ("诛", "伏诛", "被诛", "坐叛逆", "叛逆罪", "谋反", "斩")
RELATIVE_TIME_TERMS = ("后", "既而", "寻", "俄", "久", "期间", "最终", "卒", "薨", "初", "以前", "以后")
EXPLICIT_TIME_TERMS = (
    "元年",
    "二年",
    "三年",
    "四年",
    "五年",
    "六年",
    "七年",
    "八年",
    "九年",
    "十年",
    "十一年",
    "十二年",
    "十三年",
    "十四年",
    "十五年",
    "十六年",
    "十七年",
    "十八年",
    "十九年",
    "二十年",
    "正月",
    "二月",
    "三月",
    "四月",
    "五月",
    "六月",
    "七月",
    "八月",
    "九月",
    "十月",
    "十一月",
    "十二月",
    "春",
    "夏",
    "秋",
    "冬",
)


class ClaimChainCandidateError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def stable_chain_key(payload: Mapping[str, Any]) -> str:
    return "CCG-" + claim_quality.sha256_text(stable_json(payload), length=20)


def json_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def claim_fact(claim: Mapping[str, Any]) -> dict[str, Any]:
    return json_mapping(claim.get("fact_payload"))


def claim_atomic(claim: Mapping[str, Any]) -> dict[str, str]:
    payload = json_mapping(claim.get("atomic_fact_payload"))
    if payload:
        return {str(key): text(value) for key, value in payload.items()}
    return claim_quality.atomic_fact_payload(claim)


def claim_quality_value(claim: Mapping[str, Any], key: str) -> str:
    if text(claim.get(key)):
        return text(claim.get(key))
    atomic = claim_atomic(claim)
    return text(atomic.get(key))


def claim_body_text(claim: Mapping[str, Any]) -> str:
    atomic = claim_atomic(claim)
    parts = [
        claim.get("claim_summary"),
        claim.get("action_type"),
        claim.get("event_scope"),
        claim.get("office_or_domain"),
        claim.get("time_context"),
        claim.get("outcome"),
        atomic.get("actor"),
        atomic.get("fact_object"),
        atomic.get("outcome"),
        atomic.get("cost_or_damage"),
    ]
    return " ".join(text(part) for part in parts if text(part))


def unique_strings(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = text(value)
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def contains_any(value: str, terms: Sequence[str]) -> bool:
    return any(term in value for term in terms)


def time_anchor_role(time_context: str, summary: str = "") -> str:
    body = f"{time_context} {summary}"
    if contains_any(body, EXPLICIT_TIME_TERMS):
        return "explicit_anchor"
    if contains_any(body, RELATIVE_TIME_TERMS):
        return "relative_or_duration_anchor"
    return "none"


def member_role(claim: Mapping[str, Any]) -> str:
    atomic = claim_atomic(claim)
    fact_type = text(atomic.get("fact_type") or claim.get("fact_type") or claim.get("claim_type"))
    action_type = text(atomic.get("action_type") or claim.get("action_type"))
    actor = text(atomic.get("actor"))
    object_name = text(claim.get("object_name"))
    emperor_name = text(claim.get("emperor_name"))
    fact_object = text(atomic.get("fact_object"))
    outcome = text(atomic.get("outcome") or claim.get("outcome"))
    cost_or_damage = text(atomic.get("cost_or_damage"))
    body = claim_body_text(claim)

    if fact_type in EVALUATION_FACT_TYPES:
        return "evaluation_context"
    if contains_any(body, TERMINAL_TERMS) and action_type in TERMINAL_ACTION_TYPES | {"其他"}:
        return "terminal_negative_outcome"
    if cost_or_damage or contains_any(body, DAMAGE_TERMS):
        if actor and object_name and actor == object_name and fact_object != emperor_name:
            return "unauthorized_governance_action"
        return "actual_damage_or_risk"
    if contains_any(body, POWER_TERMS):
        return "delegated_power_concentration"
    if action_type in POWER_ACTION_TYPES and contains_any(body, POWER_TERMS + ("宠", "独", "总")):
        return "ruler_trust_or_authorization_context"
    if action_type in SETUP_ACTION_TYPES:
        return "setup_appointment"
    if actor == emperor_name and fact_object == object_name and contains_any(body, SETUP_TERMS):
        return "setup_appointment"
    if outcome or cost_or_damage:
        return "direct_material_candidate"
    return "supporting_context"


def role_family(role: str) -> str:
    if role in {"setup_appointment", "ruler_trust_or_authorization_context"}:
        return "setup_or_authorization"
    if role == "delegated_power_concentration":
        return "power_concentration"
    if role in {"actual_damage_or_risk", "unauthorized_governance_action"}:
        return "damage"
    if role == "terminal_negative_outcome":
        return "terminal"
    if role == "evaluation_context":
        return "evaluation"
    return "context"


def sequence_rank_for_role(role: str) -> int:
    order = {
        "setup_appointment": 10,
        "ruler_trust_or_authorization_context": 20,
        "delegated_power_concentration": 30,
        "actual_damage_or_risk": 40,
        "unauthorized_governance_action": 45,
        "terminal_negative_outcome": 60,
        "evaluation_context": 70,
        "direct_material_candidate": 80,
        "supporting_context": 90,
    }
    return order.get(role, 99)


def claim_member(claim: Mapping[str, Any]) -> dict[str, Any]:
    atomic = claim_atomic(claim)
    summary = text(claim.get("claim_summary"))
    role = member_role(claim)
    time_role = time_anchor_role(text(atomic.get("time_context") or claim.get("time_context")), summary)
    return {
        "claim_key": text(claim.get("claim_key")),
        "event_group_key": text(claim.get("event_group_key")),
        "member_role": role,
        "role_family": role_family(role),
        "sequence_rank": sequence_rank_for_role(role),
        "time_anchor_role": time_role,
        "time_context": text(atomic.get("time_context") or claim.get("time_context")),
        "action_type": text(atomic.get("action_type") or claim.get("action_type")),
        "event_scope": text(atomic.get("event_scope") or claim.get("event_scope")),
        "office_or_domain": text(atomic.get("office_or_domain") or claim.get("office_or_domain")),
        "actor": text(atomic.get("actor")),
        "fact_object": text(atomic.get("fact_object")),
        "outcome": text(atomic.get("outcome") or claim.get("outcome")),
        "cost_or_damage": text(atomic.get("cost_or_damage")),
        "outcome_support": text(atomic.get("outcome_support") or claim.get("outcome_support")),
        "negative_support": text(atomic.get("negative_support") or claim.get("negative_support")),
        "claim_summary": summary,
        "source_slice_refs": unique_strings(claim.get("source_slice_refs") or []),
        "document_codes": unique_strings(claim.get("document_codes") or []),
        "quote_previews": unique_strings(claim.get("quote_previews") or []),
    }


def time_model(members: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    anchors = [
        {
            "claim_key": member.get("claim_key"),
            "time_text": member.get("time_context"),
            "role": member.get("time_anchor_role"),
            "sequence_rank": member.get("sequence_rank"),
        }
        for member in members
        if text(member.get("time_context")) and member.get("time_anchor_role") != "none"
    ]
    explicit = [row for row in anchors if row["role"] == "explicit_anchor"]
    relative = [row for row in anchors if row["role"] == "relative_or_duration_anchor"]
    precision = "none"
    if explicit and relative:
        precision = "mixed"
    elif explicit:
        precision = "explicit"
    elif relative:
        precision = "relative"
    role_families = {text(member.get("role_family")) for member in members}
    ordered_enough = bool(explicit or len(relative) >= 2) and (
        len(role_families & {"setup_or_authorization", "power_concentration"}) > 0
        and len(role_families & {"damage", "terminal", "evaluation"}) > 0
    )
    if len(explicit) >= 2 and len(relative) >= 1:
        basis = "explicit_dates_and_relative_or_duration_phrases"
        confidence = 0.82
    elif len(explicit) >= 2:
        basis = "explicit_dates"
        confidence = 0.76
    elif len(explicit) == 1 and relative:
        basis = "single_explicit_date_with_relative_phrases"
        confidence = 0.68
    elif len(relative) >= 2:
        basis = "relative_or_duration_phrases"
        confidence = 0.58
    else:
        basis = "weak_or_missing_time_context"
        confidence = 0.35
    return {
        "precision": precision,
        "ordered_enough": ordered_enough,
        "time_anchors": sorted(anchors, key=lambda row: (int(row.get("sequence_rank") or 99), text(row.get("claim_key")))),
        "timeline_conflict": False,
        "ordering_basis": basis,
        "ordering_confidence": confidence,
    }


def chain_type_for_members(members: Sequence[Mapping[str, Any]]) -> str:
    families = Counter(text(member.get("role_family")) for member in members)
    if families["setup_or_authorization"] and families["power_concentration"] and (families["damage"] or families["terminal"]):
        return "delegated_power_abuse_chain"
    if families["setup_or_authorization"] and families["damage"]:
        return "appointment_to_outcome_chain"
    if families["damage"] and families["terminal"]:
        return "damage_to_terminal_outcome_chain"
    if families["evaluation"] and (families["damage"] or families["setup_or_authorization"]):
        return "evaluation_supported_chain"
    return "multi_claim_context_bundle"


def chain_strength(
    members: Sequence[Mapping[str, Any]],
    model: Mapping[str, Any],
    *,
    chain_type: str,
    group_kind: str,
) -> str:
    if chain_type == "multi_claim_context_bundle":
        return "context_bundle"
    families = Counter(text(member.get("role_family")) for member in members)
    has_progression = families["setup_or_authorization"] + families["power_concentration"] >= 2
    has_negative_tail = families["damage"] + families["terminal"] >= 1
    strong = len(members) >= 4 and has_progression and has_negative_tail and model.get("ordered_enough")
    if strong and group_kind != "same_document" and chain_type == "delegated_power_abuse_chain":
        return "strong_chain"
    if (strong or len(members) >= 3 and has_negative_tail and (has_progression or model.get("ordered_enough"))):
        return "probable_chain"
    return "context_bundle"


def chain_readiness(strength: str, model: Mapping[str, Any]) -> str:
    if strength == "strong_chain" and model.get("ordered_enough"):
        return "ready_for_chain_route_review"
    if strength == "probable_chain":
        return "needs_light_chain_judge"
    return "context_only_do_not_route_as_chain"


def chain_payload_basis(claims: Sequence[Mapping[str, Any]], group_kind: str, group_value: str) -> dict[str, Any]:
    first = claims[0]
    return {
        "emperor_name": text(first.get("emperor_name")),
        "object_name": text(first.get("object_name")),
        "candidate_basis": group_kind,
        "candidate_value": group_value,
    }


def candidate_from_claims(claims: Sequence[Mapping[str, Any]], *, group_kind: str, group_value: str) -> dict[str, Any]:
    sorted_claims = sorted(claims, key=lambda row: text(row.get("claim_key")))
    members = sorted((claim_member(claim) for claim in sorted_claims), key=lambda row: (int(row["sequence_rank"]), text(row["claim_key"])))
    model = time_model(members)
    chain_type = chain_type_for_members(members)
    strength = chain_strength(members, model, chain_type=chain_type, group_kind=group_kind)
    basis_payload = chain_payload_basis(sorted_claims, group_kind, group_value)
    chain_key = stable_chain_key(
        {
            **basis_payload,
            "claim_keys": sorted(member["claim_key"] for member in members),
            "chain_type": chain_type,
        }
    )
    role_counts = Counter(text(member["member_role"]) for member in members)
    family_counts = Counter(text(member["role_family"]) for member in members)
    evidence_refs = unique_strings(ref for member in members for ref in member.get("source_slice_refs") or [])
    documents = unique_strings(doc for member in members for doc in member.get("document_codes") or [])
    return {
        "chain_key": chain_key,
        **basis_payload,
        "chain_type": chain_type,
        "chain_strength": strength,
        "route_readiness": chain_readiness(strength, model),
        "member_count": len(members),
        "role_counts": dict(sorted(role_counts.items())),
        "role_family_counts": dict(sorted(family_counts.items())),
        "time_model": model,
        "source_slice_refs": evidence_refs,
        "document_codes": documents,
        "members": members,
    }


def append_group(groups: dict[tuple[str, str, str, str], list[Mapping[str, Any]]], key: tuple[str, str, str, str], claim: Mapping[str, Any]) -> None:
    if not key[2]:
        return
    groups[key].append(claim)


def collect_candidate_groups(claims: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str, str], list[Mapping[str, Any]]]:
    groups: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for claim in claims:
        emperor = text(claim.get("emperor_name"))
        object_name = text(claim.get("object_name"))
        if not emperor or not object_name:
            continue
        for ref in unique_strings(claim.get("source_slice_refs") or []):
            append_group(groups, ("same_source_slice", ref, emperor, object_name), claim)
        for doc in unique_strings(claim.get("document_codes") or []):
            append_group(groups, ("same_document", doc, emperor, object_name), claim)
        office = claim_quality_value(claim, "office_or_domain")
        event_scope = claim_quality_value(claim, "event_scope")
        if office:
            append_group(groups, ("same_office_or_domain", f"{event_scope}|{office}", emperor, object_name), claim)
    return groups


def dedupe_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    best_by_claim_set: dict[tuple[str, ...], Mapping[str, Any]] = {}
    basis_rank = {"same_source_slice": 0, "same_office_or_domain": 1, "same_document": 2}
    strength_rank = {"strong_chain": 0, "probable_chain": 1, "context_bundle": 2}
    for candidate in candidates:
        claim_set = tuple(sorted(text(member.get("claim_key")) for member in candidate.get("members") or []))
        if len(claim_set) < CHAIN_MIN_MEMBERS:
            continue
        previous = best_by_claim_set.get(claim_set)
        if previous is None:
            best_by_claim_set[claim_set] = candidate
            continue
        current_key = (
            strength_rank.get(text(candidate.get("chain_strength")), 9),
            basis_rank.get(text(candidate.get("candidate_basis")), 9),
            -int(candidate.get("member_count") or 0),
        )
        previous_key = (
            strength_rank.get(text(previous.get("chain_strength")), 9),
            basis_rank.get(text(previous.get("candidate_basis")), 9),
            -int(previous.get("member_count") or 0),
        )
        if current_key < previous_key:
            best_by_claim_set[claim_set] = candidate
    return [dict(row) for row in best_by_claim_set.values()]


def build_chain_candidates(claims: Sequence[Mapping[str, Any]], *, min_members: int = CHAIN_MIN_MEMBERS) -> list[dict[str, Any]]:
    raw_candidates: list[dict[str, Any]] = []
    for (kind, value, _emperor, _object_name), grouped_claims in collect_candidate_groups(claims).items():
        unique_by_key = {text(claim.get("claim_key")): claim for claim in grouped_claims if text(claim.get("claim_key"))}
        if len(unique_by_key) < min_members:
            continue
        raw_candidates.append(candidate_from_claims(list(unique_by_key.values()), group_kind=kind, group_value=value))
    candidates = dedupe_candidates(raw_candidates)
    return sorted(
        candidates,
        key=lambda row: (
            {"strong_chain": 0, "probable_chain": 1, "context_bundle": 2}.get(text(row.get("chain_strength")), 9),
            -int(row.get("member_count") or 0),
            text(row.get("emperor_name")),
            text(row.get("object_name")),
            text(row.get("chain_key")),
        ),
    )


def summarize_candidates(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    strength_counts = Counter(text(row.get("chain_strength")) for row in candidates)
    type_counts = Counter(text(row.get("chain_type")) for row in candidates)
    readiness_counts = Counter(text(row.get("route_readiness")) for row in candidates)
    by_object: Counter[tuple[str, str]] = Counter((text(row.get("emperor_name")), text(row.get("object_name"))) for row in candidates)
    return {
        "totals": {
            "chain_candidates": len(candidates),
            "strong_chain": strength_counts.get("strong_chain", 0),
            "probable_chain": strength_counts.get("probable_chain", 0),
            "context_bundle": strength_counts.get("context_bundle", 0),
        },
        "chain_strength_counts": dict(sorted(strength_counts.items())),
        "chain_type_counts": dict(sorted(type_counts.items())),
        "route_readiness_counts": dict(sorted(readiness_counts.items())),
        "top_objects": [
            {"emperor_name": emperor, "object_name": object_name, "candidate_count": count}
            for (emperor, object_name), count in by_object.most_common(30)
        ],
    }


def sample_candidates(candidates: Sequence[Mapping[str, Any]], *, sample_limit: int) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for candidate in candidates:
        if len(samples) >= sample_limit:
            break
        samples.append(
            {
                key: candidate.get(key)
                for key in (
                    "chain_key",
                    "emperor_name",
                    "object_name",
                    "candidate_basis",
                    "candidate_value",
                    "chain_type",
                    "chain_strength",
                    "route_readiness",
                    "member_count",
                    "role_family_counts",
                    "time_model",
                )
            }
            | {
                "members": [
                    {
                        "claim_key": member.get("claim_key"),
                        "member_role": member.get("member_role"),
                        "time_context": member.get("time_context"),
                        "action_type": member.get("action_type"),
                        "summary": member.get("claim_summary"),
                    }
                    for member in candidate.get("members", [])
                ]
            }
        )
    return samples


def build_report(claims: Sequence[Mapping[str, Any]], *, sample_limit: int = 20, min_members: int = CHAIN_MIN_MEMBERS) -> dict[str, Any]:
    candidates = build_chain_candidates(claims, min_members=min_members)
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v2_claim_chain_candidates.py",
        "mode": "dry_run_claim_chain_candidates",
        "write_db": False,
        "input_claim_count": len(claims),
        **summarize_candidates(candidates),
        "sample_candidates": sample_candidates(candidates, sample_limit=sample_limit),
        "chain_candidates": candidates,
    }


def fetch_claim_rows(
    cur: Any,
    *,
    emperor_names: Sequence[str],
    statuses: Sequence[str],
    owner_scopes: Sequence[str],
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    clean_emperors = [text(name) for name in emperor_names if text(name)]
    clean_statuses = [text(status) for status in statuses if text(status)]
    clean_owner_scopes = owner_scope_values(owner_scopes)
    if clean_emperors:
        clauses.append("c.emperor_name = any(%s)")
        params.append(clean_emperors)
    if clean_statuses:
        clauses.append("c.status::text = any(%s)")
        params.append(clean_statuses)
    clauses.append("os.owner_scope = any(%s)")
    params.append(clean_owner_scopes)
    cur.execute(
        f"""
        select
            c.claim_key,
            c.emperor_name,
            c.object_name,
            c.object_type::text as object_type,
            c.claim_type::text as claim_type,
            c.fact_schema::text as fact_schema,
            c.fact_type,
            c.action_type,
            c.event_scope,
            c.office_or_domain,
            c.time_context,
            c.outcome,
            c.claim_summary,
            c.fact_payload,
            c.atomic_fact_payload,
            c.event_group_key,
            c.claim_grain,
            c.status::text as status,
            os.owner_scope,
            array_remove(array_agg(distinct e.source_slice_ref), null) as source_slice_refs,
            array_remove(array_agg(distinct e.document_code), null) as document_codes,
            array_remove(array_agg(distinct e.quote_preview), null) as quote_previews
          from retrieval_v2.claim_atomic_facts c
          join retrieval_v2.claim_owner_scopes os on os.claim_key = c.claim_key
          left join retrieval_v2.claim_evidence e on e.claim_key = c.claim_key
          {'where ' + ' and '.join(clauses) if clauses else ''}
         group by
            c.claim_key, c.emperor_name, c.object_name, c.object_type, c.claim_type,
            c.fact_schema, c.fact_type, c.action_type, c.event_scope, c.office_or_domain,
            c.time_context, c.outcome, c.claim_summary, c.fact_payload, c.atomic_fact_payload,
            c.event_group_key, c.claim_grain, c.status, os.owner_scope
         order by c.emperor_name, c.object_name, c.claim_key
        """,
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def report_from_pg(
    *,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    emperor_names: Sequence[str],
    statuses: Sequence[str],
    owner_scopes: Sequence[str],
    sample_limit: int,
    min_members: int,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            claims = fetch_claim_rows(cur, emperor_names=emperor_names, statuses=statuses, owner_scopes=owner_scopes)
        conn.rollback()
    report = build_report(claims, sample_limit=sample_limit, min_members=min_members)
    report["schema_name"] = schema_name
    report["filters"] = {
        "emperor_names": [text(name) for name in emperor_names if text(name)],
        "statuses": [text(status) for status in statuses if text(status)],
        "owner_scopes": owner_scope_values(owner_scopes),
        "min_members": min_members,
    }
    return report


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def markdown_report(payload: Mapping[str, Any]) -> str:
    totals = payload.get("totals") if isinstance(payload.get("totals"), Mapping) else {}
    lines = [
        "# Claim Chain Candidate Report",
        "",
        f"- mode: `{payload.get('mode')}`",
        f"- write_db: `{payload.get('write_db')}`",
        f"- input_claim_count: `{payload.get('input_claim_count')}`",
        f"- chain_candidates: `{totals.get('chain_candidates', 0)}`",
        f"- strong_chain: `{totals.get('strong_chain', 0)}`",
        f"- probable_chain: `{totals.get('probable_chain', 0)}`",
        f"- context_bundle: `{totals.get('context_bundle', 0)}`",
        "",
        "## Strength Counts",
        "",
        "| chain_strength | count |",
        "| --- | ---: |",
    ]
    for key, count in (payload.get("chain_strength_counts") or {}).items():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## Candidate Samples", ""])
    for candidate in payload.get("sample_candidates") or []:
        lines.extend(
            [
                f"### {candidate.get('emperor_name')} - {candidate.get('object_name')} - {candidate.get('chain_strength')}",
                "",
                f"- chain_key: `{candidate.get('chain_key')}`",
                f"- chain_type: `{candidate.get('chain_type')}`",
                f"- basis: `{candidate.get('candidate_basis')}` / `{candidate.get('candidate_value')}`",
                f"- route_readiness: `{candidate.get('route_readiness')}`",
                f"- member_count: `{candidate.get('member_count')}`",
                f"- time_model: `{json.dumps(candidate.get('time_model'), ensure_ascii=False, sort_keys=True, default=str)}`",
                "",
                "| role | time | claim_key | summary |",
                "| --- | --- | --- | --- |",
            ]
        )
        for member in candidate.get("members") or []:
            summary = text(member.get("summary")).replace("|", "\\|")
            lines.append(
                f"| {member.get('member_role')} | {member.get('time_context')} | `{member.get('claim_key')}` | {summary} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_report(payload), encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run claim chain candidate builder for the retrieval_v3 middle layer.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--emperor-name", action="append", default=[])
    parser.add_argument("--status", action="append", default=list(DEFAULT_STATUSES))
    parser.add_argument("--owner-scope", action="append", default=[], help="Owner scope to include; defaults to target_emperor only.")
    parser.add_argument("--min-members", type=int, default=CHAIN_MIN_MEMBERS)
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = report_from_pg(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        emperor_names=args.emperor_name or [],
        statuses=args.status or [],
        owner_scopes=args.owner_scope or [],
        sample_limit=max(0, int(args.sample_limit)),
        min_members=max(2, int(args.min_members)),
    )
    if args.output_json is not None:
        write_json(args.output_json, report)
    if args.output_md is not None:
        write_markdown(args.output_md, report)
    print(json.dumps({"ok": True, "mode": report["mode"], "totals": report["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClaimChainCandidateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
