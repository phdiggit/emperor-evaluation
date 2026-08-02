from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.historical_outcome_cluster import (
    cluster_semantic_fingerprint,
    outcome_episode_ref,
)
from emperor_v4.evaluation.historical_outcome_registry import (
    validate_dynasty_outcome_pack,
)


FORMAL_STATUS = "ADJUDICATED_SOURCE_BACKFILL_REQUIRED"
PACK_SCHEMA_VERSION = "dynasty-battle-outcome-pack-v1"
EXACT_SCHEMA_VERSION = "battle-exact-evidence-current-v1"
DYNASTY_TOKEN = {
    "秦": "QIN",
    "三国": "THREE-KINGDOMS",
    "两晋": "JIN-SIXTEEN-KINGDOMS",
    "南北朝": "SOUTHERN-NORTHERN",
    "隋": "SUI",
    "唐": "TANG",
}
TOKEN_DYNASTY = {
    "QIN": "秦",
    "HAN": "西汉",
    "EASTERN-HAN": "东汉及汉末",
    "THREE-KINGDOMS": "三国",
    "JIN-SIXTEEN-KINGDOMS": "两晋十六国",
    "SOUTHERN-NORTHERN": "南北朝",
    "SUI": "隋",
    "TANG": "唐",
}
SCALE_BY_RESULT_CLASS = {
    "local_tactical": ("local", "local_tactical", "supporting"),
    "important_objective": ("important", "important_objective", "major"),
    "major_stage_or_crisis": ("regional", "regional_theater_control", "major"),
    "independent_direction": ("national", "national_war_outcome", "major"),
    "single_pole_decisive_defeat": (
        "national",
        "national_core_force_defeat",
        "decisive",
    ),
    "external_hegemony_decisive_defeat": (
        "national",
        "external_hegemony_core_force_defeat",
        "decisive",
    ),
    "single_pole_or_state_terminal": ("national", "state_conquest", "decisive"),
    "composite_poles_terminal": ("national", "state_conquest", "decisive"),
    "unification_terminal": ("national", "unification", "decisive"),
    "external_hegemony_terminal": (
        "era_shaping",
        "era_order_reconstruction",
        "decisive",
    ),
}


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _as_rows(value: object) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    return [dict(row) for row in value]  # type: ignore[arg-type]


def _token_for(adjudication: Mapping[str, Any]) -> str:
    dynasty = str(adjudication["dynasty"])
    if dynasty != "汉":
        return DYNASTY_TOKEN[dynasty]
    period = adjudication.get("period") or {}
    return "HAN" if "前" in str(period.get("start") or "") else "EASTERN-HAN"


def _evidence_roles(fields: Sequence[str]) -> list[str]:
    roles: set[str] = set()
    field_set = set(fields)
    if field_set & {"battle_process", "participating_scale_or_cost_facts"}:
        roles.add("implementation_or_operation")
    if "participating_scale_or_cost_facts" in field_set:
        roles.add("public_cost_or_harm")
    if field_set & {
        "observable_result",
        "territorial_or_security_result",
        "objective_completion_or_shortfall",
    }:
        roles.add("public_result")
    if field_set & {"command_and_role_attribution", "attributable_failure"}:
        roles.add("responsibility_or_attribution")
    return sorted(roles or {"implementation_or_operation"})


def _member(
    member: Mapping[str, Any],
    identity_resolutions: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    command = member.get("person_command_index") or {}
    consumption_mode = str(command.get("consumption_mode") or "none")
    role_code = str(member.get("role_code") or "")
    relation = str(member.get("ruler_campaign_relation") or "")
    if role_code == "ruler_authorizer":
        role_code = "not_in_command_chain"
    if relation == "frontline_command":
        role_code = "commander_in_chief"
    talent_credit = {
        "full_parent": "independent",
        "none": "not_applicable",
    }.get(consumption_mode, "covered_by_child")
    original_ref = str(member["actor_ref"])
    identity = identity_resolutions.get(original_ref) or {}
    actor_ref = str(identity.get("canonical_ref") or original_ref)
    identity_ambiguous = identity.get("status") == "HOLD_AMBIGUOUS"
    result: dict[str, Any] = {
        "actor_ref": actor_ref,
        "actor_name": str(member["actor_name"]),
        "actor_kind": str(member["actor_kind"]),
        "role_code": role_code,
        "contribution_scope": str(member["contribution_scope"]),
        "talent_credit": talent_credit,
        "sovereign_at_event": bool(member.get("sovereign_at_event")),
    }
    if result["sovereign_at_event"]:
        result["ruler_campaign_relation"] = relation
        if relation == "authorization_only":
            result["authorization_mode"] = str(
                member.get("authorization_mode") or "explicit"
            )
        if relation in {"operational_direction", "frontline_command"}:
            result["control_extent"] = str(
                member.get("control_extent")
                or ("sustained" if consumption_mode == "full_parent" else "partial")
            )
        if member.get("obstruction_status"):
            result["obstruction_status"] = str(member["obstruction_status"])
    return result, identity_ambiguous


def _identity_resolutions(
    payload: Mapping[str, Any],
    *,
    formal_adjudications: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if (
        payload.get("schema_version")
        != "ordinary-battle-person-identities-v1"
        or payload.get("evidence_maturity") != "REGISTERED_NOT_GOLD"
    ):
        raise ValueError("普通战役人物身份裁决版本或成熟度不受支持")
    indexed: dict[str, dict[str, Any]] = {}
    for row in payload.get("resolutions") or ():
        status = str(row.get("status") or "")
        if status not in {
            "REUSED_EXISTING",
            "DETERMINISTIC_NEW",
            "HOLD_AMBIGUOUS",
        }:
            raise ValueError("普通战役人物身份裁决状态非法")
        if status != "HOLD_AMBIGUOUS" and not row.get("canonical_ref"):
            raise ValueError("已闭合人物身份缺少 canonical_ref")
        for draft_ref in row.get("draft_refs") or ():
            draft_ref = str(draft_ref)
            if draft_ref in indexed:
                raise ValueError(f"普通战役草稿人物重复裁决: {draft_ref}")
            indexed[draft_ref] = dict(row)
    formal_drafts = {
        str(member["actor_ref"])
        for adjudication in formal_adjudications
        for member in adjudication.get("members") or ()
        if "DRAFT" in str(member.get("actor_ref") or "")
    }
    if set(indexed) != formal_drafts:
        raise ValueError(
            "普通战役人物身份裁决未完整覆盖当前草稿引用: "
            f"missing={sorted(formal_drafts - set(indexed))}, "
            f"extra={sorted(set(indexed) - formal_drafts)}"
        )
    return indexed


def _source_refs_for(
    base_refs: Sequence[str], exact_source_refs: Sequence[str]
) -> list[str]:
    selected = [
        exact
        for exact in exact_source_refs
        if any(exact.startswith(f"{base}#") for base in base_refs)
    ]
    return selected or list(exact_source_refs)


def _payload(
    adjudication: Mapping[str, Any], exact_source_refs: Sequence[str]
) -> tuple[dict[str, Any], int]:
    payload = json.loads(
        json.dumps(adjudication.get("payload") or {}, ensure_ascii=False)
    )
    held_failures = 0
    for field in ("operational_costs", "objective_shortfalls"):
        normalized = []
        for row in _as_rows(payload.get(field)):
            row["source_refs"] = _source_refs_for(
                [str(value) for value in row.get("source_refs") or ()],
                exact_source_refs,
            )
            normalized.append(row)
        payload[field] = normalized
    normalized_failures = []
    for row in _as_rows(payload.get("attributable_failures")):
        if (
            row.get("severity_index") not in {0.2, 0.4, 0.6, 0.7, 1}
            or row.get("responsibility")
            not in {
                "primary",
                "shared",
                "subordinate_execution",
                "disobedience",
                "mitigated",
                "not_responsible",
            }
            or not row.get("actor_ref")
            or not row.get("actor_name")
        ):
            held_failures += 1
            continue
        row["source_refs"] = _source_refs_for(
            [str(value) for value in row.get("source_refs") or ()],
            exact_source_refs,
        )
        normalized_failures.append(row)
    payload["attributable_failures"] = normalized_failures
    required_axis_basis = (
        f"土地轴={payload['land_strategic_value']}；"
        f"对手轴={payload['opponent_strategic_weight']}/"
        f"{payload['opponent_condition']}；"
        f"结果轴={payload['battle_result']}/{payload['objective_completion']}；"
    )
    existing_basis = str(payload.get("campaign_tier_basis") or "")
    if not all(
        token in existing_basis
        for token in (
            f"土地轴={payload['land_strategic_value']}",
            f"对手轴={payload['opponent_strategic_weight']}/"
            f"{payload['opponent_condition']}",
            f"结果轴={payload['battle_result']}/{payload['objective_completion']}",
        )
    ):
        payload["campaign_tier_basis"] = required_axis_basis + existing_basis
    return payload, held_failures


def _fact_and_lineage(
    *,
    event_id: str,
    unit: Mapping[str, Any],
    index: int,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    page = str(unit["source_page"])
    revision = str(unit["revision_ref"])
    quote = str(unit["exact_quote"])
    identity = {
        "war_event_id": event_id,
        "source_page": page,
        "revision_ref": revision,
        "exact_quote": quote,
    }
    ref = "PFACT-BATTLE-" + _digest(identity)[:20].upper()
    assertion_ref = "PASS-BATTLE-" + _digest(
        {"fact_ref": ref, "index": index}
    )[:20].upper()
    fact = {
        "record_ref": ref,
        "record_type": "event",
        "source_page": page,
        "revision_ref": revision,
        "neutral_summary": str(unit["fact"]),
        "assertions": [
            {
                "assertion_ref": assertion_ref,
                "kind": "historical_event",
                "exact_quote": quote,
                "locator_anchor": quote[:60],
                "fact": str(unit["fact"]),
            }
        ],
    }
    lineage = {
        "fact_ref": ref,
        "evidence_roles": _evidence_roles(
            [str(value) for value in unit.get("supported_fields") or ()]
        ),
    }
    return fact, lineage, f"{page}@{revision}#{quote}"


def _cluster(
    adjudication: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    identity_resolutions: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    event_id = str(adjudication["war_event_id"])
    facts: list[dict[str, Any]] = []
    lineage: list[dict[str, Any]] = []
    source_refs: list[str] = []
    for index, unit in enumerate(evidence.get("evidence_units") or ()):
        fact, fact_lineage, source_ref = _fact_and_lineage(
            event_id=event_id,
            unit=unit,
            index=index,
        )
        facts.append(fact)
        lineage.append(fact_lineage)
        source_refs.append(source_ref)
    payload, held_failures = _payload(adjudication, source_refs)
    result_class = str(payload["strategic_result_class"])
    level, consequence_basis, decisiveness = SCALE_BY_RESULT_CLASS[result_class]
    battle_result = str(payload["battle_result"])
    result_status = {
        "victory": "completed",
        "mixed": "mixed",
        "defeat": "failed",
        "unclear": "unclear",
    }[battle_result]
    result_direction = {
        "victory": "positive",
        "mixed": "mixed",
        "defeat": "negative",
        "unclear": "unclear",
    }[battle_result]
    topology = str(adjudication["campaign_command_topology"])
    child_required = any(
        (member.get("person_command_index") or {}).get("consumption_mode")
        not in {"full_parent", "none"}
        for member in adjudication.get("members") or ()
    )
    limitations = []
    if topology in {"distributed_response", "command_unresolved"}:
        limitations.append("现有史源未闭合唯一统合指挥链，不据此补造人物信用。")
    if child_required:
        limitations.append("人物局部、共同或敌对方向另建子成果，不复制父战役档位。")
    if held_failures:
        limitations.append(
            f"{held_failures}条可归责失败仍使用旧严重度或缺少责任字段，"
            "本轮不做机械换算。"
        )
    members = []
    has_ambiguous_identity = False
    for member in adjudication.get("members") or ():
        normalized, ambiguous = _member(member, identity_resolutions)
        members.append(normalized)
        has_ambiguous_identity = has_ambiguous_identity or ambiguous
    if has_ambiguous_identity:
        limitations.append("存在爵号化表面名，人物规范身份尚未闭合。")
    independent_key = f"ordinary-campaign:{event_id}"
    cluster: dict[str, Any] = {
        "outcome_ref": "OUTCOME-BATTLE-" + _digest(independent_key)[:20].upper(),
        "outcome_kind": "campaign",
        "settlement_scope": "ruler_campaign_parent",
        "independent_key": independent_key,
        "canonical_label": str(adjudication["canonical_label"]),
        "origin": "dynasty_battle",
        "campaign_command_topology": topology,
        "period": dict(adjudication["period"]),
        "result_status": result_status,
        "result_direction": result_direction,
        "observable_result": str(adjudication["observable_result"]),
        "scale": {
            "level": level,
            "consequence_basis": consequence_basis,
            "decisiveness": decisiveness,
            "reason": str(adjudication["basis"]),
        },
        "stable_delivery": bool(adjudication.get("stable_delivery")),
        "important_method_or_legacy": (
            payload["campaign_tier"] in {"S", "S+"}
            or payload["combat_difficulty"] == "D4"
        ),
        "episode_refs": [],
        "ruler_window_status": "unresolved",
        "fact_refs": [str(row["record_ref"]) for row in facts],
        "source_refs": source_refs,
        "source_war_event_refs": list(
            dict.fromkeys(
                [
                    event_id,
                    *[
                        str(value)
                        for value in adjudication.get("source_war_event_refs") or ()
                    ],
                ]
            )
        ),
        "evidence_lineage": lineage,
        "members": members,
        "limitations": limitations,
        "payload": payload,
    }
    cluster["episode_refs"] = [outcome_episode_ref(cluster)]
    cluster["semantic_fingerprint"] = cluster_semantic_fingerprint(cluster)
    return cluster, facts


def build_ordinary_battle_outcome_packs(
    *,
    ordinary_adjudications: Mapping[str, Any],
    exact_evidence: Mapping[str, Any],
    person_identities: Mapping[str, Any],
    base_packs: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    if exact_evidence.get("schema_version") != EXACT_SCHEMA_VERSION:
        raise ValueError("普通战役成果包输入的逐字证据版本不受支持")
    evidence_by_id = {
        str(row["war_event_id"]): row for row in exact_evidence.get("items") or ()
    }
    formal_adjudications = [
        adjudication
        for adjudication in ordinary_adjudications.get("adjudications") or ()
        if adjudication.get("status") == FORMAL_STATUS
    ]
    identity_resolutions = _identity_resolutions(
        person_identities,
        formal_adjudications=formal_adjudications,
    )
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for adjudication in formal_adjudications:
        event_id = str(adjudication["war_event_id"])
        if event_id not in evidence_by_id:
            raise ValueError(f"{event_id} 缺少正式逐字证据")
        grouped.setdefault(_token_for(adjudication), []).append(adjudication)
    packs: dict[str, dict[str, Any]] = {}
    for token, adjudications in sorted(grouped.items()):
        base = json.loads(
            json.dumps((base_packs or {}).get(token) or {}, ensure_ascii=False)
        )
        base_clusters = list(
            (base.get("outcome_registry") or {}).get("clusters") or ()
        )
        existing_clusters = [
            row
            for row in base_clusters
            if not str(row.get("independent_key") or "").startswith(
                "ordinary-campaign:"
            )
        ]
        retained_fact_refs = {
            str(ref)
            for row in existing_clusters
            for ref in row.get("fact_refs") or ()
        }
        existing_facts = [
            row
            for row in base.get("facts") or ()
            if str(row.get("record_ref") or "") in retained_fact_refs
        ]
        new_facts: list[dict[str, Any]] = []
        new_clusters: list[dict[str, Any]] = []
        for adjudication in sorted(
            adjudications, key=lambda row: str(row["war_event_id"])
        ):
            cluster, facts = _cluster(
                adjudication,
                evidence_by_id[str(adjudication["war_event_id"])],
                identity_resolutions=identity_resolutions,
            )
            new_clusters.append(cluster)
            new_facts.extend(facts)
        pack = {
            "schema_version": PACK_SCHEMA_VERSION,
            "pack_scope": "dynasty_battle",
            "status": "current_human_adjudicated",
            "dynasty": str(base.get("dynasty") or TOKEN_DYNASTY[token]),
            "dynasty_token": token,
            "facts": [*existing_facts, *new_facts],
            "members": list(base.get("members") or ()),
            "outcome_registry": {
                "schema_version": "historical-outcome-cluster-registry-v3",
                "status": "human_frozen",
                "clusters": [*existing_clusters, *new_clusters],
            },
        }
        pack["source_pack_sha256"] = _digest(pack)
        packs[token] = pack
    return packs


def write_ordinary_battle_outcome_packs(workspace_root: Path) -> dict[str, Path]:
    adjudications = json.loads(
        (workspace_root / "config/ordinary-campaign-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    exact = json.loads(
        (workspace_root / "eval/battle_exact_evidence/current.json").read_text(
            encoding="utf-8"
        )
    )
    person_identities = json.loads(
        (
            workspace_root / "config/ordinary-battle-person-identities.json"
        ).read_text(encoding="utf-8")
    )
    packs = build_ordinary_battle_outcome_packs(
        ordinary_adjudications=adjudications,
        exact_evidence=exact,
        person_identities=person_identities,
        base_packs={},
    )
    written: dict[str, Path] = {}
    for token, pack in packs.items():
        validate_dynasty_outcome_pack(
            workspace_root,
            token=token,
            source_pack=pack,
        )
    for token, pack in packs.items():
        path = (
            workspace_root
            / "eval/ordinary_battle_outcomes"
            / token
            / "current.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written[token] = path
    return written
