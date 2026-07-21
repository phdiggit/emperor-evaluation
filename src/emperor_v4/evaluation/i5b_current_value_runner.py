from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.contracts.boundary import RuleEvidenceMember
from emperor_v4.contracts.episode import AssertionLink, EpisodeParticipant, HistoricalEpisodePacket
from emperor_v4.evaluation.i5b_material_budget_scored_shadow import (
    APPOINTMENT_FACTORS,
    FACTOR_NAMES,
    ROOT,
    build_i5b_material_budget_shadow,
    render_i5b_material_budget_shadow_markdown,
)
from emperor_v4.evaluation.historical_outcome_cluster import (
    CAMPAIGN_ROLES,
    GOVERNANCE_ROLES,
    assess_person_talent_grade,
    build_outcome_episode,
    validate_historical_outcome_registry,
)
from emperor_v4.persistence.core_registry import RuleEvidenceUnitRecord


SCHEMA_VERSION = "i5b-current-value-report-v5"
SOURCE_PACK_SCHEMA_VERSION = "i5b-current-value-source-pack-v5"
RULES = ("talent_discovery", "appointment_delegation", "tolerate_talent", "anti_nepotism")
STABILITY_CONTINUITY = {"initial", "continuous", "managed_turnover", "gap"}
APPOINTMENT_OUTCOME_ROLES = {
    "campaign": {"commander_in_chief", "principal_commander", "deputy_commander"},
    "governance": {"exclusive", "lead"},
}
TEAM_FUNCTION_ROLES = {
    "strategic_decision": {"decision", "strategy", "coordination", "crisis_management"},
    "public_governance": {
        "administration", "civil_governance", "regional_governance", "institution_building",
        "institution", "law", "judiciary", "finance", "personnel", "policy", "succession",
    },
    "specialist_execution": {
        "military", "regional_military", "theater_command", "border_command", "feudal_command",
        "long_term_command", "frontier", "cavalry", "mobile_warfare", "pacification", "pursuit",
        "supply_disruption", "logistics", "historiography", "history",
    },
    "correction_feedback": {"feedback", "correction", "court_supervision", "information_gatekeeping"},
}


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object, length: int | None = None) -> str:
    result = hashlib.sha256(_canonical(value)).hexdigest()
    return result[:length] if length else result


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return value


def _policy_values(policy: Mapping[str, Any], rule: str, options: Mapping[str, str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, option in options.items():
        catalog = policy["evidence_factor"].get(name)
        if catalog is None:
            catalog = policy["rules"][rule].get(name)
        if not isinstance(catalog, Mapping) or option not in catalog:
            raise ValueError(f"{rule}.{name} 未知语义选项: {option}")
        values[name] = catalog[option]
    return values


def _required_factor_names(rule: str, direction: str) -> tuple[str, ...]:
    if rule == "appointment_delegation":
        return APPOINTMENT_FACTORS
    return FACTOR_NAMES[rule][direction]


def derive_long_term_stability(team: Mapping[str, Any]) -> str:
    """Derive the factor option from current stage coverage, never from a free scalar."""

    required = {str(value) for value in team.get("stability_required_functions") or ()}
    stages = list(team.get("stability_stages") or ())
    if not required or len(stages) < 2:
        raise ValueError("团队长期稳定性必须声明至少两阶段及必需功能")
    stage_codes = [str(row.get("stage_code") or "") for row in stages]
    if "" in stage_codes or len(stage_codes) != len(set(stage_codes)):
        raise ValueError("团队长期稳定阶段身份缺失或重复")
    continuities = [str(row.get("continuity_from_prior") or "") for row in stages]
    if continuities[0] != "initial" or any(
        value not in STABILITY_CONTINUITY for value in continuities
    ):
        raise ValueError("团队长期稳定阶段连续性不合法")
    if any(
        not required.issubset(
            {str(value) for value in row.get("covered_function_groups") or ()}
        )
        for row in stages
    ):
        return "stable_but_narrow"
    if "gap" in continuities:
        return "forced_turnover_collapse"
    if "managed_turnover" in continuities:
        return "managed_turnover"
    if len(stages) >= 3:
        return "durable_multi_stage"
    return "stable_window"


def _member_function_groups(member: Mapping[str, Any]) -> set[str]:
    roles = {str(value) for value in member.get("role_families") or ()}
    return {
        function
        for function, aliases in TEAM_FUNCTION_ROLES.items()
        if roles & aliases
    }


def _independent_function_match_size(members: list[Mapping[str, Any]]) -> int:
    matched_people: dict[str, str] = {}

    def assign(function: str, seen: set[str]) -> bool:
        for member in members:
            person_ref = str(member["person_ref"])
            if person_ref in seen or function not in _member_function_groups(member):
                continue
            seen.add(person_ref)
            prior = matched_people.get(person_ref)
            if prior is None or assign(prior, seen):
                matched_people[person_ref] = function
                return True
        return False

    return sum(assign(function, set()) for function in TEAM_FUNCTION_ROLES)


def derive_functional_complementarity(members: list[Mapping[str, Any]]) -> str:
    size = _independent_function_match_size(members)
    return {4: "balanced_four", 3: "strong_three", 2: "ordinary_two"}.get(size, "homogeneous")


def _current_fact_text(
    material: Mapping[str, Any], facts: Mapping[str, Mapping[str, Any]]
) -> str:
    summaries = [
        str(facts[str(ref)]["neutral_summary"]).strip()
        for ref in material["fact_refs"]
    ]
    return "；".join(value for value in summaries if value)


def _appointment_outcome_options(
    cluster: Mapping[str, Any],
    member: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, str]:
    projection = policy["rules"]["appointment_delegation"]["outcome_registry_projection"]
    scale = str(cluster["scale"]["level"])
    responsibility = member.get("delegated_responsibility") or {}
    importance = str(responsibility.get("scope") or "")
    if not importance or not responsibility.get("basis") or not responsibility.get("authorization_refs"):
        raise ValueError(
            f"{cluster['outcome_ref']}:{member['actor_ref']} 缺少独立于成果规模的授权责任范围"
        )
    effect = str(projection["effect_by_result_scale"][scale])
    payload = cluster.get("payload") or {}
    continuity_projection = projection["continuity_by_delivery"]
    continuity = str(
        continuity_projection["durable_cross_stage"]
        if payload.get("durable_cross_stage") is True
        else continuity_projection["stable_delivery"]
        if cluster.get("stable_delivery") is True
        else continuity_projection["otherwise"]
    )
    return {
        "appointment_importance": importance,
        "appointment_effect": effect,
        "continuity_factor": continuity,
        "attribution_factor": "direct",
        "source_factor": "standard",
        "context_factor": "core_mechanism_direct",
    }


def _outcome_appointment_materials(
    *,
    clusters: list[Mapping[str, Any]],
    profile_by_ref: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[RuleEvidenceUnitRecord]]:
    materials: list[dict[str, Any]] = []
    decisions: list[dict[str, str]] = []
    units: list[RuleEvidenceUnitRecord] = []
    for cluster in sorted(clusters, key=lambda row: str(row["outcome_ref"])):
        if (
            cluster["result_direction"] != "positive"
            or cluster["result_status"] not in {"implemented", "operated", "completed", "mixed"}
        ):
            continue
        kind = str(cluster["outcome_kind"])
        for member in cluster["members"]:
            person_ref = str(member["actor_ref"])
            role = str(member["role_code"])
            if (
                member["actor_kind"] != "person"
                or person_ref not in profile_by_ref
                or role not in APPOINTMENT_OUTCOME_ROLES[kind]
            ):
                continue
            responsibility = member.get("delegated_responsibility") or {}
            if (
                not responsibility.get("scope")
                or not responsibility.get("basis")
                or not responsibility.get("authorization_refs")
            ):
                continue
            person = str(profile_by_ref[person_ref]["person"])
            options = _appointment_outcome_options(cluster, member, policy)
            values = _policy_values(policy, "appointment_delegation", options)
            identity = {
                "outcome_ref": cluster["outcome_ref"],
                "person_ref": person_ref,
                "role": role,
            }
            suffix = _digest(identity, 16).upper()
            material_id = f"MAT-AUTO-AD-{suffix}"
            unit_ref = f"REU-AUTO-AD-{suffix}"
            fact = (
                f"{person}以{(CAMPAIGN_ROLES if kind == 'campaign' else GOVERNANCE_ROLES)[role]}"
                f"身份承担“{cluster['canonical_label']}”；"
                f"已实现结果：{cluster['observable_result']}"
            )
            materials.append(
                {
                    "material_id": material_id,
                    "subject": person,
                    "object_ref": person_ref,
                    "side": "positive",
                    "factor_values": values,
                    "factor_option_codes": options,
                    "fact": fact,
                    "rule_evidence_unit_ref": unit_ref,
                    "source_refs": list(cluster["source_refs"]),
                }
            )
            decisions.append(
                {
                    "material_id": material_id,
                    "independence_key": (
                        f"appointment_delegation:{cluster['outcome_ref']}:{person_ref}"
                    ),
                    "judge_reason": "由当前成果登记的责任、规模、结果和持续性确定性派生。",
                }
            )
            semantic = _digest({"identity": identity, "options": options})
            units.append(
                RuleEvidenceUnitRecord(
                    unit_ref=unit_ref,
                    rule_code="appointment_delegation",
                    evaluation_context=person_ref,
                    direction="positive",
                    semantic_fingerprint=semantic,
                    status="accepted_shadow",
                    payload={
                        "outcome_ref": cluster["outcome_ref"],
                        "delegated_responsibility": dict(member["delegated_responsibility"]),
                        "ruler_context_refs": list(
                            cluster.get("ruler_context_refs") or ()
                        ),
                        "factor_option_codes": options,
                        "derivation": "historical_outcome_registry",
                    },
                    members=(
                        RuleEvidenceMember(
                            member_ref=str(cluster["episode_refs"][0]),
                            member_type="episode",
                            member_role="core_evidence",
                        ),
                    ),
                )
            )
    return materials, decisions, units


def _ruler_window_outcomes(
    clusters: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Project lifetime outcomes into the current ruler window.

    Existing current packs predate the explicit field and therefore default to
    within-window. Newly discovered ambiguous or later-reign outcomes must be
    marked and fail closed on the ruler side without disappearing from the
    person's lifetime registry.
    """

    return [
        cluster
        for cluster in clusters
        if cluster.get("ruler_window_status", "within_window") == "within_window"
    ]


def _neutral_episode_key(material: Mapping[str, Any]) -> str:
    return _digest(
        {
            "person_ref": material["person_ref"],
            "facts": material["fact_refs"],
            "action": material["episode_action"],
            "responsibility": material["episode_responsibility"],
            "outcomes": material["episode_outcomes"],
        }
    )


def _episode_and_reu(
    *,
    material: Mapping[str, Any],
    facts: Mapping[str, Mapping[str, Any]],
    ruler_contexts: Mapping[str, Mapping[str, Any]],
    ruler: str,
) -> tuple[HistoricalEpisodePacket, RuleEvidenceUnitRecord]:
    fact_rows = [facts[str(ref)] for ref in material["fact_refs"]]
    assertion_links: list[AssertionLink] = []
    source_refs: set[str] = set()
    for fact in fact_rows:
        page = str(fact["source_page"])
        revision = str(fact["revision_ref"])
        for index, assertion in enumerate(fact.get("assertions") or (), start=1):
            anchor = str(assertion.get("locator_anchor") or index)
            quote = str(assertion["exact_quote"])
            passage_ref = "SP-" + _digest(
                {"page": page, "revision": revision, "anchor": anchor, "quote": quote}, 20
            ).upper()
            assertion_ref = str(assertion.get("assertion_ref") or "AS-" + _digest({"passage": passage_ref, "fact": assertion["fact"]}, 20).upper())
            source_refs.add(f"{page}@{revision}#{anchor}")
            assertion_links.append(
                AssertionLink(
                    assertion_ref=assertion_ref,
                    source_passage_ref=passage_ref,
                    relation="supports",
                    supported_fields=("identity", "action", "responsibility", "outcome"),
                    evidence_status="accepted",
                    representative=index == 1,
                )
            )
    context_refs = tuple(str(ref) for ref in material.get("ruler_context_refs") or ())
    for context_ref in context_refs:
        context = ruler_contexts[context_ref]
        for source_ref in context.get("source_refs") or ():
            page_revision = str(source_ref)
            for index, anchor_value in enumerate(context.get("assertion_anchors") or (), start=1):
                anchor = str(anchor_value)
                source_refs.add(f"{page_revision}#{anchor}")
                passage_ref = "SP-" + _digest(
                    {"source_ref": page_revision, "anchor": anchor}, 20
                ).upper()
                assertion_links.append(
                    AssertionLink(
                        assertion_ref="AS-" + _digest(
                            {"passage": passage_ref, "context": context_ref}, 20
                        ).upper(),
                        source_passage_ref=passage_ref,
                        relation="corroborates",
                        supported_fields=("action", "responsibility", "outcome"),
                        evidence_status="accepted",
                        representative=index == 1,
                    )
                )
    if not assertion_links:
        raise ValueError(f"{material['material_id']} 没有可接受 Assertion")
    uncertainties: tuple[str, ...] = ()
    episode_semantic = _digest(
        {"neutral_episode": _neutral_episode_key(material), "ruler_context_refs": context_refs}
    )
    reu_semantic = _digest(
        {
            "episode_semantic": episode_semantic,
            "rule": material["rule_code"],
            "direction": material["direction"],
            "settlement_event_key": material.get("settlement_event_key", material["independence_key"]),
        }
    )
    episode_id = "EP-" + episode_semantic[:20].upper()
    dates = [str(row.get("date") or "") for row in fact_rows if row.get("date")]
    episode = HistoricalEpisodePacket(
        episode_id=episode_id,
        episode_type="ruler_person_governance_event",
        episode_status="accepted_with_uncertainty" if uncertainties else "accepted",
        evaluation_context=str(material["person_ref"]),
        semantic_fingerprint=episode_semantic,
        time_start="；".join(dates) or None,
        time_end=None,
        time_precision="source_expression" if dates else "unknown",
        locations=(),
        participants=(EpisodeParticipant(person_ref=str(material["person_ref"]), role_codes=("subject",), role_status="resolved"),),
        action=str(material["episode_action"]),
        responsibility=str(material["episode_responsibility"]),
        outcome=tuple(str(value) for value in material["episode_outcomes"]),
        consequence=tuple(str(value) for value in material["episode_outcomes"]),
        assertion_links=tuple(assertion_links),
        conflicts=(),
        uncertainties=uncertainties,
        completeness={
            "identity": "complete",
            "time": "complete" if dates else "partial",
            "action": "complete",
            "responsibility": "complete",
            "outcome": "complete",
            "consequence": "complete",
            "source_diversity": "complete" if len(source_refs) > 1 else "partial",
            "conflict_resolution": "not_applicable",
        },
        lineage={
            "fact_refs": ";".join(str(ref) for ref in material["fact_refs"]),
            "ruler_context_refs": ";".join(context_refs),
            "source_refs": ";".join(sorted(source_refs)),
        },
        provenance={"ruler": ruler, "mode": "current_shadow"},
    )
    unit_ref = "REU-" + reu_semantic[:20].upper()
    reu = RuleEvidenceUnitRecord(
        unit_ref=unit_ref,
        rule_code=str(material["rule_code"]),
        evaluation_context=str(material["person_ref"]),
        direction=str(material["direction"]),
        semantic_fingerprint=reu_semantic,
        status="accepted_shadow",
        payload={
            "independence_key": material["independence_key"],
            "settlement_event_key": material.get("settlement_event_key", material["independence_key"]),
            "judge_reason": material["judge_reason"],
            "remaining_gap": str(material.get("remaining_gap") or ""),
            "factor_option_codes": dict(material["factor_option_codes"]),
        },
        members=(RuleEvidenceMember(member_ref=episode_id, member_type="episode", member_role="core_evidence"),),
    )
    return episode, reu


def build_i5b_current_value(
    source_pack_path: Path,
    *,
    workspace_root: Path = ROOT,
) -> dict[str, Any]:
    source_pack_path = source_pack_path.resolve()
    pack = _load_json(source_pack_path)
    if pack.get("schema_version") != SOURCE_PACK_SCHEMA_VERSION:
        raise ValueError("current source pack schema_version 不匹配")
    declared_hash = str(pack.get("source_pack_sha256") or "")
    unsigned_pack = dict(pack)
    unsigned_pack.pop("source_pack_sha256", None)
    if declared_hash != _digest(unsigned_pack):
        raise ValueError("current source pack sha256 不匹配")
    three_channel = pack.get("three_channel_input") or {}
    channel_counts = three_channel.get("channel_counts") or {}
    if set(channel_counts) != {"ruler_chronicle", "person_biography", "dynasty_governance"} or any(int(value) <= 0 for value in channel_counts.values()):
        raise ValueError("current source pack 未闭合三路中性材料")
    dispositions = pack.get("three_channel_disposition") or {}
    if set(dispositions) != set(channel_counts):
        raise ValueError("current source pack 三路处置不闭合")
    if len(pack.get("ruler_context_materials") or ()) != int(dispositions["ruler_chronicle"]["ruler_window_context_count"]):
        raise ValueError("皇帝篇章 supporting context 数量不一致")
    outcome_registry = pack.get("outcome_registry") or {}
    outcome_clusters = list(outcome_registry.get("clusters") or ())
    dynasty_governance_count = sum(
        row["origin"] == "dynasty_governance" and row["outcome_kind"] == "governance"
        for row in outcome_clusters
    )
    if dynasty_governance_count != int(dispositions["dynasty_governance"]["ruler_window_achievement_count"]):
        raise ValueError("朝代文治成果处置数量不一致")
    if pack.get("declarations", {}).get("formal_write") is not False:
        raise ValueError("current source pack 不得授权正式写入")
    profile_gate = pack.get("profile_projection_gate") or {}
    if profile_gate.get("status") not in {
        "material_coverage_open",
        "ready_for_freeze_review",
        "frozen_after_complete_coverage",
    }:
        raise ValueError("人物画像投影缺少当前覆盖门禁")
    profile_coverage_complete = profile_gate.get("material_coverage_complete") is True
    profile_freeze_allowed = profile_gate.get("freeze_allowed") is True
    if profile_freeze_allowed and not profile_coverage_complete:
        raise ValueError("材料覆盖未闭合时不得冻结人才等级或政治风险")

    policy_path = ROOT / str(pack["factor_acceptance"]["policy_ref"])
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    facts = {str(row["record_ref"]): row for row in pack.get("facts") or ()}
    outcome_validation = validate_historical_outcome_registry(
        outcome_registry,
        schema_path=ROOT / "config/historical-outcome-cluster-registry.schema.json",
        facts=facts,
    )
    outcome_by_ref = {
        str(row["outcome_ref"]): row for row in outcome_clusters
    }
    ruler_outcome_clusters = _ruler_window_outcomes(outcome_clusters)
    ruler_outcome_by_ref = {
        str(row["outcome_ref"]): row for row in ruler_outcome_clusters
    }
    current_members = copy.deepcopy(list(pack.get("members") or ()))
    for member in current_members:
        person_ref = str(member["person_ref"])
        assessment = assess_person_talent_grade(
            person_ref=person_ref,
            clusters=outcome_clusters,
        )
        member["effective_talent_grade"] = assessment["grade"]
        member["talent_grade_basis"] = assessment["basis"]
        review = member["profile_review"]["talent_grade"]
        review["grade"] = assessment["grade"]
        review["basis"] = assessment["basis"]
        alignment = review["rule_alignment"]
        alignment["outcome_refs"] = assessment["outcome_refs"]
        alignment["rule_path"] = assessment["rule_path"]
        review["evidence_refs"] = sorted(
            {
                fact_ref
                for outcome_ref in assessment["outcome_refs"]
                for fact_ref in outcome_by_ref[outcome_ref]["fact_refs"]
            }
        )
    profile_by_ref = {
        str(row["person_ref"]): row for row in current_members
    }
    team_policy = policy["rules"]["team_building"]
    team_budget = policy["settlement_budget"]["team_building"]
    talent_values = team_policy["talent_quality_factor"]
    risk_values = team_policy["negative_talent_severity_value"]
    team = copy.deepcopy(pack["team"])
    team["positive_members"] = [
        str(row["person"])
        for row in sorted(
            current_members,
            key=lambda row: (
                -Decimal(str(talent_values[row["effective_talent_grade"]])),
                str(row["person"]),
            ),
        )[: int(team_budget["positive_member_budget"])]
    ]
    team["negative_members"] = [
        str(row["person"])
        for row in sorted(
            (
                row
                for row in current_members
                if row.get("negative_talent_severity") is not None
            ),
            key=lambda row: (
                -Decimal(str(risk_values[row["negative_talent_severity"]])),
                str(row["person"]),
            ),
        )[: int(team_budget["negative_member_budget"])]
    ]
    selected_names = set(team["positive_members"])
    selected_members = [row for row in current_members if row["person"] in selected_names]
    team["functional_complementarity"] = derive_functional_complementarity(selected_members)
    team["stability_required_functions"] = list(TEAM_FUNCTION_ROLES)
    for stage in team["stability_stages"]:
        stage_members = [
            profile_by_ref[str(person_ref)]
            for person_ref in stage["member_refs"]
            if str(person_ref) in profile_by_ref
        ]
        stage["covered_function_groups"] = sorted(
            {group for member in stage_members for group in _member_function_groups(member)}
        )
    team["long_term_stability"] = derive_long_term_stability(team)
    current_profiles = {
        person_ref: {
            "review_status": (
                "human_frozen" if profile_freeze_allowed else "provisional_current"
            ),
            "talent_grade": member["effective_talent_grade"],
            "talent_grade_basis": member["talent_grade_basis"],
            "profile_ref": member["profile_ref"],
            "negative_risk_status": (
                "established"
                if member.get("negative_talent_severity") is not None
                else "reviewed_no_finding"
            ),
            "negative_talent_class": member.get("negative_talent_class"),
            "negative_talent_severity": member.get("negative_talent_severity"),
        }
        for person_ref, member in profile_by_ref.items()
    }
    ruler_contexts = {
        str(row["material_ref"]): row
        for row in pack.get("ruler_context_materials") or ()
    }
    materials = list(pack.get("materials") or ())
    material_ids = [str(row["material_id"]) for row in materials]
    if len(material_ids) != len(set(material_ids)):
        raise ValueError("current source pack material_id 重复")
    context_refs_by_episode: dict[str, set[str]] = {}
    for material in materials:
        context_refs_by_episode.setdefault(_neutral_episode_key(material), set()).update(
            str(ref) for ref in material.get("ruler_context_refs") or ()
        )
    episode_by_id: dict[str, HistoricalEpisodePacket] = {}
    reus = []
    direct_by_rule: dict[str, list[dict[str, Any]]] = {rule: [] for rule in RULES}
    eligible_by_rule: dict[str, dict[str, list[dict[str, str]]]] = {
        rule: {"positive": [], "negative": []} for rule in RULES
    }
    settlement_keys: set[tuple[str, str, str]] = set()
    linked_ruler_context_refs: set[str] = set()
    for material in materials:
        material = dict(material)
        material["ruler_context_refs"] = sorted(
            context_refs_by_episode[_neutral_episode_key(material)]
        )
        rule = str(material["rule_code"])
        direction = str(material["direction"])
        if rule not in RULES or direction not in {"positive", "negative"}:
            raise ValueError(f"材料规则或方向非法: {material['material_id']}")
        if rule == "appointment_delegation" and direction == "positive":
            raise ValueError("正向任用授权必须由当前成果登记确定性派生")
        if rule == "anti_nepotism" and material.get("public_power_effect") is not True:
            raise ValueError(f"{material['material_id']} 未通过公共权力作用 Gate")
        unknown_facts = sorted(set(str(ref) for ref in material["fact_refs"]) - set(facts))
        if unknown_facts:
            raise ValueError(f"{material['material_id']} 引用未知当前事实: {unknown_facts}")
        material_context_refs = {
            str(ref) for ref in material.get("ruler_context_refs") or ()
        }
        unknown_contexts = sorted(material_context_refs - set(ruler_contexts))
        if unknown_contexts:
            raise ValueError(f"{material['material_id']} 引用未知皇帝篇章材料: {unknown_contexts}")
        unrelated_contexts = sorted(
            ref
            for ref in material_context_refs
            if material.get("subject_kind") != "ruler_institution"
            and str(material["person_ref"]) != str(pack["ruler_ref"])
            and str(material["person_ref"])
            not in {str(value) for value in ruler_contexts[ref].get("person_refs") or ()}
        )
        if unrelated_contexts:
            raise ValueError(f"{material['material_id']} 皇帝篇章人物不匹配: {unrelated_contexts}")
        linked_ruler_context_refs.update(material_context_refs)
        settlement_event_key = str(
            material.get("settlement_event_key") or material["independence_key"]
        )
        settlement_identity = (rule, direction, settlement_event_key)
        if settlement_identity in settlement_keys:
            raise ValueError(f"重复结算事件: {settlement_identity}")
        settlement_keys.add(settlement_identity)
        options = dict(material["factor_option_codes"])
        if rule == "talent_discovery":
            profile = profile_by_ref.get(str(material["person_ref"]))
            if profile is not None:
                options["talent_quality_factor"] = str(
                    profile["effective_talent_grade"]
                )
        required = set(_required_factor_names(rule, direction))
        if set(options) != required:
            raise ValueError(f"{material['material_id']} 因子集合不闭合")
        values = _policy_values(policy, rule, options)
        declared_values = {name: str(value) for name, value in (material.get("factor_values") or {}).items()}
        mapped_values = {name: str(value) for name, value in values.items()}
        compared_names = (
            set(mapped_values) - {"talent_quality_factor"}
            if rule == "talent_discovery"
            else set(mapped_values)
        )
        if any(declared_values.get(name) != mapped_values[name] for name in compared_names):
            raise ValueError(f"{material['material_id']} 数值不是政策确定性映射")
        current_fact = _current_fact_text(material, facts)
        material["fact_summary"] = current_fact
        material["episode_action"] = current_fact
        material["factor_option_codes"] = options
        episode, reu = _episode_and_reu(
            material=material,
            facts=facts,
            ruler_contexts=ruler_contexts,
            ruler=str(pack["ruler"]),
        )
        existing_episode = episode_by_id.setdefault(episode.episode_id, episode)
        if existing_episode != episode:
            previous = asdict(existing_episode)
            current = asdict(episode)
            differing = sorted(
                key for key in previous if previous[key] != current[key]
            )
            raise ValueError(
                f"Episode 语义指纹冲突: {episode.episode_id}; fields={differing}; "
                f"material={material['material_id']}"
            )
        reus.append(reu)
        source_refs = sorted({
            f"{facts[str(ref)]['source_page']}@{facts[str(ref)]['revision_ref']}"
            for ref in material["fact_refs"]
        })
        direct_by_rule[rule].append(
            {
                "material_id": material["material_id"],
                "subject": material["subject"],
                "object_ref": material["person_ref"],
                "side": direction,
                "factor_values": values,
                "factor_option_codes": options,
                "fact": current_fact,
                "rule_evidence_unit_ref": reu.unit_ref,
                "source_refs": source_refs,
            }
        )
        eligible_by_rule[rule][direction].append(
            {
                "material_id": str(material["material_id"]),
                "independence_key": settlement_event_key,
                "judge_reason": str(material["judge_reason"]),
            }
        )

    generated_materials, generated_decisions, generated_units = (
        _outcome_appointment_materials(
            clusters=ruler_outcome_clusters,
            profile_by_ref=profile_by_ref,
            policy=policy,
        )
    )
    for cluster in outcome_clusters:
        cluster_context_refs = {
            str(ref) for ref in cluster.get("ruler_context_refs") or ()
        }
        unknown_contexts = sorted(cluster_context_refs - set(ruler_contexts))
        if unknown_contexts:
            raise ValueError(
                f"{cluster['outcome_ref']} 引用未知皇帝篇章材料: {unknown_contexts}"
            )
        linked_ruler_context_refs.update(cluster_context_refs)
    direct_by_rule["appointment_delegation"].extend(generated_materials)
    eligible_by_rule["appointment_delegation"]["positive"].extend(
        generated_decisions
    )
    reus.extend(generated_units)

    manifest = {
        "schema_version": "i5b-material-budget-shadow-manifest-v1",
        "task_code": f"I5B-CURRENT-{_digest({'pack': declared_hash, 'policy': policy}, 16).upper()}",
        "ruler": pack["ruler"],
        "ruler_ref": pack["ruler_ref"],
        "window": pack["window"],
        "policy": pack["factor_acceptance"]["policy_ref"],
        "settlement_mode": "policy_budget",
        "rules": {},
    }
    for rule in RULES:
        manifest["rules"][rule] = {
            "source": str(source_pack_path),
            "direct_materials": direct_by_rule[rule],
            "eligible": eligible_by_rule[rule],
            "excluded": [],
        }
    governance_by_ref = {
        ref: row
        for ref, row in ruler_outcome_by_ref.items()
        if row["outcome_kind"] == "governance"
    }
    positive_member_refs = {
        str(row["person_ref"])
        for row in current_members
        if str(row["person"]) in set(team["positive_members"])
    }
    team_governance_refs = sorted(
        ref
        for ref, row in governance_by_ref.items()
        if row["result_direction"] == "positive"
        and row["result_status"] in {"implemented", "operated", "completed", "mixed"}
        and row["scale"]["level"] in {"national", "important", "era_shaping"}
        and any(
            member["actor_ref"] in positive_member_refs
            and member["role_code"] in {"exclusive", "lead"}
            for member in row["members"]
        )
    )
    governance_results = [
        {
            "result": governance_by_ref[ref]["observable_result"],
            "source_refs": governance_by_ref[ref]["source_refs"],
            "outcome_ref": ref,
        }
        for ref in team_governance_refs
    ]
    governance_dispositions = [
        {
            "outcome_ref": ref,
            "disposition": (
                "selected_team_result_support"
                if ref in team_governance_refs
                else "supporting_policy_context_not_i5b_team_score"
                if row["result_direction"] == "positive"
                else "excluded_no_preserved_positive_result"
            ),
        }
        for ref, row in sorted(governance_by_ref.items())
    ]
    dispositions["dynasty_governance"]["team_support_count"] = len(
        team_governance_refs
    )
    profile_projection_review = []
    for member in sorted(current_members, key=lambda row: str(row["person"])):
        person_ref = str(member["person_ref"])
        biography_fact_refs = sorted(
            str(row["record_ref"])
            for row in facts.values()
            if str(row["person_ref"]) == person_ref
        )
        member_context_refs = sorted(
            ref
            for ref, row in ruler_contexts.items()
            if person_ref in {str(value) for value in row.get("person_refs") or ()}
        )
        member_governance_refs = sorted(
            ref
            for ref, row in governance_by_ref.items()
            if person_ref in {str(value["actor_ref"]) for value in row["members"]}
        )
        supporting_unit_refs = sorted(
            str(value) for value in member.get("supporting_unit_refs") or ()
        )
        profile_review = member.get("profile_review") or {}
        biography_scan = profile_review.get("full_lifecycle_biography") or {}
        talent_review = profile_review.get("talent_grade") or {}
        grade_alignment = talent_review.get("rule_alignment") or {}
        authority_review = profile_review.get("authority_grade_calibration") or {}
        risk_review = profile_review.get("political_risk") or {}
        profile_evidence_refs = {
            "talent_grade": sorted(str(value) for value in talent_review.get("evidence_refs") or ()),
            "full_lifecycle_biography": sorted(
                str(value) for value in biography_scan.get("evidence_refs") or ()
            ),
            "authority_grade_calibration": sorted(
                str(value) for value in authority_review.get("evidence_refs") or ()
            ),
            "political_risk": sorted(
                str(value) for value in risk_review.get("evidence_refs") or ()
            ),
        }
        known_profile_refs = set(facts) | set(ruler_contexts) | set(outcome_by_ref)
        unknown_profile_refs = sorted(
            ref
            for refs in profile_evidence_refs.values()
            for ref in refs
            if ref not in known_profile_refs
        )
        if unknown_profile_refs:
            raise ValueError(f"{member['person']} 人物画像引用未知当前材料: {unknown_profile_refs}")
        gaps = []
        biography_sources = {
            (str(row["source_page"]), str(row["revision_ref"]))
            for row in facts.values()
            if str(row["person_ref"]) == person_ref
        }
        if not biography_fact_refs:
            gaps.append("missing_current_biography_fact")
        if (
            biography_scan.get("scan_status") != "complete_section"
            or not biography_scan.get("source_page")
            or not biography_scan.get("revision_ref")
            or int(biography_scan.get("section_chars") or 0) <= 0
            or (
                str(biography_scan.get("source_page")),
                str(biography_scan.get("revision_ref")),
            )
            not in biography_sources
            or not profile_evidence_refs.get("full_lifecycle_biography")
        ):
            gaps.append("missing_full_lifecycle_biography_lineage")
        if (
            talent_review.get("status") not in {
                "accepted_current",
                "provisional_registry_open",
            }
            or talent_review.get("grade") != member["effective_talent_grade"]
            or talent_review.get("policy_ref")
            != "config/talent-grade-v11-domain-equivalent-historic.yml"
            or not profile_evidence_refs.get("talent_grade")
        ):
            gaps.append("missing_talent_grade_lineage")
        grade_registry_refs = sorted(
            str(value) for value in grade_alignment.get("outcome_refs") or ()
        )
        computed_grade = assess_person_talent_grade(
            person_ref=person_ref, clusters=outcome_clusters
        )
        if (
            grade_alignment.get("status") != "accepted_current"
            or grade_alignment.get("policy_ref")
            != "config/talent-grade-v11-domain-equivalent-historic.yml"
            or not grade_alignment.get("rule_path")
            or not grade_registry_refs
            or computed_grade["grade"] != member["effective_talent_grade"]
            or computed_grade["basis"] != talent_review.get("basis")
            or computed_grade["rule_path"] != grade_alignment.get("rule_path")
            or computed_grade["outcome_refs"] != grade_registry_refs
        ):
            gaps.append("missing_talent_grade_rule_alignment")
        elif unknown_registry_refs := sorted(
            set(grade_registry_refs) - set(outcome_by_ref)
        ):
            raise ValueError(
                f"{member['person']} 人才等级引用未知成果登记: "
                f"{unknown_registry_refs}"
            )
        if (
            authority_review.get("status") != "accepted_current"
            or not profile_evidence_refs.get("authority_grade_calibration")
        ):
            gaps.append("missing_authoritative_grade_calibration")
        risk_status = risk_review.get("assessment_status")
        risk_scan = risk_review.get("scan_receipt") or {}
        if (
            risk_status not in {"established", "reviewed_no_material_risk"}
            or risk_review.get("policy_ref") != "config/political-risk.yml"
            or risk_scan.get("biography_full_scan") is not True
            or risk_scan.get("cross_record_search") is not True
            or risk_scan.get("domain_query_matrix") is not True
        ):
            gaps.append("missing_window_risk_source")
        elif risk_status == "established" and (
            risk_review.get("risk_class") != member.get("negative_talent_class")
            or risk_review.get("severity") != member.get("negative_talent_severity")
            or not profile_evidence_refs.get("political_risk")
        ):
            gaps.append("window_risk_value_mismatch")
        elif risk_status == "reviewed_no_material_risk" and (
            member.get("negative_talent_class") is not None
            or member.get("negative_talent_severity") is not None
            or risk_scan.get("counterevidence_review") is not True
        ):
            gaps.append("window_no_risk_review_mismatch")
        profile_projection_review.append(
            {
                "person": member["person"],
                "person_ref": person_ref,
                "candidate_talent_grade": member["effective_talent_grade"],
                "candidate_negative_talent_class": member.get("negative_talent_class"),
                "candidate_negative_talent_severity": member.get("negative_talent_severity"),
                "biography_fact_refs": biography_fact_refs,
                "ruler_context_refs": member_context_refs,
                "outcome_refs": sorted(
                    ref for ref, row in outcome_by_ref.items()
                    if any(value["actor_ref"] == person_ref for value in row["members"])
                ),
                "supporting_unit_refs": supporting_unit_refs,
                "profile_evidence_refs": profile_evidence_refs,
                "profile_review": profile_review,
                "talent_grade_rule_alignment": grade_alignment,
                "coverage_gaps": gaps,
                "value_status": (
                    "frozen_after_complete_coverage"
                    if profile_freeze_allowed
                    else "provisional_material_coverage_open"
                ),
            }
        )
    if profile_coverage_complete and any(
        row["coverage_gaps"] for row in profile_projection_review
    ):
        open_rows = {
            row["person"]: row["coverage_gaps"]
            for row in profile_projection_review
            if row["coverage_gaps"]
        }
        raise ValueError(f"人物画像声明覆盖闭合但仍存在 lineage 缺口: {open_rows}")
    manifest["rules"]["team_building"] = {
        "source": str(source_pack_path),
        "positive_members": team["positive_members"],
        "negative_members": team["negative_members"],
        "functional_complementarity": team["functional_complementarity"],
        "long_term_stability": team["long_term_stability"],
        "remaining_member_judge_reason": (
            "人物画像已在三路材料、成果登记和窗口政治风险覆盖闭合后冻结；未进入正8/负3的成员仅作支持。"
            if profile_freeze_allowed
            else "当前人物画像与窗口风险仍为暂定值；未进入正8/负3的成员仅作支持。"
        ),
        "governance_results": governance_results,
    }
    budget = build_i5b_material_budget_shadow(
        source_pack_path,
        manifest_payload=manifest,
        current_profiles=current_profiles,
    )
    team_semantic = _digest(
        {
            "ruler_ref": pack["ruler_ref"],
            "positive_members": team["positive_members"],
            "negative_members": team["negative_members"],
            "outcome_refs": team_governance_refs,
            "functional_complementarity": team["functional_complementarity"],
            "long_term_stability": team["long_term_stability"],
        }
    )
    team_reu = RuleEvidenceUnitRecord(
        unit_ref="REU-TEAM-" + team_semantic[:16].upper(),
        rule_code="team_building",
        evaluation_context=str(pack["ruler_ref"]),
        direction="net",
        semantic_fingerprint=team_semantic,
        status="accepted_shadow",
        payload={
            "positive_members": list(team["positive_members"]),
            "negative_members": list(team["negative_members"]),
            "functional_complementarity": team["functional_complementarity"],
            "long_term_stability": team["long_term_stability"],
            "ruler_context_inventory_fingerprint": _digest(pack["ruler_context_materials"]),
            "linked_ruler_context_refs": sorted(linked_ruler_context_refs),
            "governance_dispositions": governance_dispositions,
            "profile_value_status": (
                "frozen_after_complete_coverage"
                if profile_freeze_allowed
                else "provisional_material_coverage_open"
            ),
        },
        members=(
            RuleEvidenceMember(
                member_ref="TEAM-CONTEXT-" + team_semantic[:16].upper(),
                member_type="aggregate_context",
                member_role="team_window",
            ),
            *tuple(
                RuleEvidenceMember(
                    member_ref=ref,
                    member_type="outcome_cluster",
                    member_role="governance_result_support",
                )
                for ref in team_governance_refs
            ),
        ),
    )
    score_episodes = sorted(episode_by_id.values(), key=lambda value: value.episode_id)
    outcome_episodes = sorted(
        (build_outcome_episode(row, facts=facts) for row in outcome_clusters),
        key=lambda value: value.episode_id,
    )
    episodes = [*score_episodes, *outcome_episodes]
    profile_name_by_ref = {
        str(row["person_ref"]): str(row["person"])
        for row in current_members
    }
    fact_owner = {
        str(row["person_ref"]): str(row["canonical_name"])
        for row in facts.values()
        if str(row["person_ref"]) in profile_name_by_ref
    }
    score_by_person: dict[str, set[str]] = {}
    for episode in score_episodes:
        owner = fact_owner.get(episode.evaluation_context)
        if owner:
            score_by_person.setdefault(owner, set()).add(episode.episode_id)
    outcome_by_person: dict[str, set[str]] = {}
    for cluster in outcome_clusters:
        for member in cluster["members"]:
            person_name = profile_name_by_ref.get(str(member["actor_ref"]))
            if member["actor_kind"] == "person" and person_name:
                outcome_by_person.setdefault(person_name, set()).add(
                    str(cluster["episode_refs"][0])
                )
    combined_by_person = {
        name: sorted(
            score_by_person.get(name, set()) | outcome_by_person.get(name, set())
        )
        for name in sorted(set(score_by_person) | set(outcome_by_person))
    }
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "current_shadow_chain_complete"
            if profile_freeze_allowed
            else "current_shadow_chain_complete_profile_values_provisional"
        ),
        "ruler": pack["ruler"],
        "ruler_ref": pack["ruler_ref"],
        "window": pack["window"],
        "source_pack_ref": (
            str(source_pack_path.relative_to(workspace_root))
            if source_pack_path.is_relative_to(workspace_root)
            else str(source_pack_path)
        ),
        "source_pack_sha256": declared_hash,
        "three_channel_input": three_channel,
        "three_channel_disposition": dispositions,
        "judge_coverage": pack["judge_coverage"],
        "linked_ruler_context_refs": sorted(linked_ruler_context_refs),
        "governance_results": governance_results,
        "governance_dispositions": governance_dispositions,
        "outcome_registry_validation": outcome_validation,
        "historical_outcome_clusters": outcome_clusters,
        "ruler_historical_outcome_refs": sorted(ruler_outcome_by_ref),
        "profile_projection_gate": profile_gate,
        "profile_projection_review": profile_projection_review,
        "episodes": [asdict(value) for value in episodes],
        "episode_index_by_person": combined_by_person,
        "rule_evidence_units": [asdict(value) for value in (*reus, team_reu)],
        "excluded_units": pack["excluded_units"],
        "material_budget": budget,
        "net_signal": budget["summary"]["weighted_raw_signal"],
        "net_signal_status": (
            "stable_profile_inputs"
            if profile_freeze_allowed
            else "provisional_profile_inputs"
        ),
        "declarations": {
            "current_value_only": True,
            "three_channel_materials_consumed": True,
            "linked_ruler_context_count": len(linked_ruler_context_refs),
            "selected_governance_result_count": len(team_governance_refs),
            "profile_material_coverage_complete": profile_coverage_complete,
            "profile_values_frozen": profile_freeze_allowed,
            "profile_freeze_gate_passed": profile_coverage_complete
            and profile_freeze_allowed,
            "formal_scoring_ready": False,
            "profile_member_count": len(profile_projection_review),
            "profile_member_with_open_gap_count": sum(
                bool(row["coverage_gaps"]) for row in profile_projection_review
            ),
            "historical_outcome_cluster_count": len(outcome_by_ref),
            "ruler_historical_outcome_cluster_count": len(ruler_outcome_by_ref),
            "outside_ruler_window_outcome_count": (
                len(outcome_by_ref) - len(ruler_outcome_by_ref)
            ),
            "campaign_outcome_count": outcome_validation["kind_counts"]["campaign"],
            "governance_outcome_count": outcome_validation["kind_counts"]["governance"],
            "episode_count": len(episodes),
            "rule_evidence_unit_count": len(reus) + 1,
            "external_retrieval_count": 0,
            "runtime_model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "score_45": None,
            "tier": None,
            "ranking": None,
        },
    }
    report["database_dry_run"] = build_outcome_database_dry_run(report)
    report["report_sha256"] = _digest(report)
    return report


def _decimal_text(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001")))


def build_outcome_database_dry_run(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact current-row plan without opening a database connection."""

    clusters = list(report.get("historical_outcome_clusters") or ())
    migration = ROOT / "db/postgres/007_v4_historical_outcome_clusters.sql"
    return {
        "schema_version": "historical-outcome-database-dry-run-v1",
        "status": "ready_before_database_write",
        "ruler": report["ruler"],
        "source_pack_sha256": report["source_pack_sha256"],
        "planned_current_rows": {
            "historical_episodes": len(clusters),
            "historical_outcome_clusters": len(clusters),
            "outcome_cluster_members": sum(len(row["members"]) for row in clusters),
            "outcome_episode_links": sum(len(row["episode_refs"]) for row in clusters),
        },
        "migration_ref": "db/postgres/007_v4_historical_outcome_clusters.sql",
        "migration_sha256": hashlib.sha256(migration.read_bytes()).hexdigest(),
        "database_connection_opened": False,
        "database_write_count": 0,
        "formal_score_write_count": 0,
    }


def _person_material_budget(
    report: Mapping[str, Any], *, person: str, person_ref: str
) -> dict[str, Any]:
    budget = copy.deepcopy(report["material_budget"])
    owner_by_reu = {
        str(row["unit_ref"]): str(row["evaluation_context"])
        for row in report["rule_evidence_units"]
    }
    for rule in budget["rules"]:
        if rule["rule_code"] == "team_building":
            rule["positive_members"] = [
                row for row in rule["positive_members"] if row["person"] == person
            ]
            rule["negative_members"] = [
                row for row in rule["negative_members"] if row["person"] == person
            ]
            rule["supporting_only_members"] = [
                row
                for row in rule.get("supporting_only_members") or ()
                if row["person"] == person
            ]
            positive_pool = sum(
                (Decimal(str(row["talent_value"])) for row in rule["positive_members"]),
                Decimal("0"),
            )
            positive = (
                positive_pool
                * Decimal(str(rule["functional_complementarity_factor"]))
                * Decimal(str(rule["long_term_stability_factor"]))
            )
            negative = sum(
                (Decimal(str(row["negative_value"])) for row in rule["negative_members"]),
                Decimal("0"),
            )
        else:
            for key in ("settled_materials", "supporting_only_materials"):
                rule[key] = [
                    row
                    for row in rule[key]
                    if owner_by_reu.get(str(row["rule_evidence_unit_ref"])) == person_ref
                ]
            positive = sum(
                (
                    Decimal(str(row["actual_signal_contribution"]))
                    for row in rule["settled_materials"]
                    if row["side"] == "positive"
                ),
                Decimal("0"),
            )
            negative = sum(
                (
                    Decimal(str(row["actual_signal_contribution"]))
                    for row in rule["settled_materials"]
                    if row["side"] == "negative"
                ),
                Decimal("0"),
            )
        rule["positive_signal"] = _decimal_text(positive)
        rule["negative_signal"] = _decimal_text(negative)
        rule["rule_raw_net"] = _decimal_text(positive - negative)
    budget["ruler"] = f"{report['ruler']} / {person}"
    budget["summary"]["weighted_raw_signal"] = "人物过滤视图不单独汇总"
    return budget


def render_scoring_detail_markdown(
    report: Mapping[str, Any], *, person: str | None = None
) -> str:
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("计分详情只接受当前 I5B 结果")
    unsigned = dict(report)
    declared_hash = str(unsigned.pop("report_sha256", ""))
    if declared_hash != _digest(unsigned):
        raise ValueError("当前 I5B 结果 report_sha256 不匹配")
    material_budget = report.get("material_budget")
    if not isinstance(material_budget, Mapping):
        raise ValueError("当前 I5B 结果缺少 material_budget")
    if person is None:
        lines = render_i5b_material_budget_shadow_markdown(material_budget).rstrip().splitlines()
        role_catalogs = {
            "campaign": CAMPAIGN_ROLES,
            "governance": GOVERNANCE_ROLES,
        }
        section_labels = {
            "governance": "治理成果登记",
            "campaign": "战役登记",
        }
        for outcome_kind in ("governance", "campaign"):
            lines.extend(
                [
                    "",
                    f"## {section_labels[outcome_kind]}",
                    "",
                    "| 登记号 | 成果 | 责任对象 | 规模 | 状态 | 已实现结果 | 史源 |",
                    "| --- | --- | --- | --- | --- | --- | --- |",
                ]
            )
            ruler_outcome_refs = set(report["ruler_historical_outcome_refs"])
            for cluster in report["historical_outcome_clusters"]:
                if cluster["outcome_ref"] not in ruler_outcome_refs:
                    continue
                if cluster["outcome_kind"] != outcome_kind:
                    continue
                roles = role_catalogs[outcome_kind]
                members = "、".join(
                    f"{row['actor_name']}（{roles[row['role_code']]}）"
                    for row in cluster["members"]
                )
                lines.append(
                    f"| {cluster['outcome_ref']} | {cluster['canonical_label']} | "
                    f"{members} | {cluster['scale']['level']} | "
                    f"{cluster['result_direction']} / {cluster['result_status']} | "
                    f"{cluster['observable_result']} | "
                    f"{'、'.join(cluster['source_refs'])} |"
                )
        return "\n".join(lines) + "\n"
    profile = next(
        (row for row in report["profile_projection_review"] if row["person"] == person),
        None,
    )
    if profile is None:
        raise ValueError(f"当前 I5B 结果不存在臣子: {person}")
    lines = render_i5b_material_budget_shadow_markdown(
        _person_material_budget(
            report,
            person=person,
            person_ref=str(profile["person_ref"]),
        )
    ).rstrip().splitlines()
    risk = profile["profile_review"]["political_risk"]
    biography = profile["profile_review"]["full_lifecycle_biography"]
    talent = profile["profile_review"]["talent_grade"]
    alignment = profile.get("talent_grade_rule_alignment") or {}
    registry_refs = alignment.get("outcome_refs") or []
    rule_alignment = (
        f"{alignment['policy_ref']}#{alignment['rule_path']}"
        if alignment.get("policy_ref") and alignment.get("rule_path")
        else "未确立"
    )
    registry_support = "、".join(str(value) for value in registry_refs) or "缺失"
    lines.extend(
        [
            "",
            "## 当前人物画像",
            "",
            "| 人才档位 | 人才等级确立理由 | 规则对应 | 登记支撑 | 政治风险 | 画像状态 | 本传史源 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            f"| {profile['candidate_talent_grade']} | {talent['basis']} | "
            f"{rule_alignment} | {registry_support} | "
            f"{risk['assessment_status']} / {risk.get('severity') or '无'} | "
            f"{profile['value_status']} | "
            f"{biography['source_page']}@{biography['revision_ref']} |",
            "",
            f"政治风险判定：{risk['basis']}",
            "",
            "## 人才等级成果登记",
            "",
            "| 成果 | 类型 | 角色 | 规模 | 已实现结果 | 史源 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    outcome_by_ref = {
        row["outcome_ref"]: row for row in report["historical_outcome_clusters"]
    }
    for outcome_ref in registry_refs:
        outcome = outcome_by_ref[outcome_ref]
        role = next(
            row["role_code"]
            for row in outcome["members"]
            if row["actor_ref"] == profile["person_ref"]
        )
        lines.append(
            f"| {outcome['canonical_label']} | {outcome['outcome_kind']} | {role} | "
            f"{outcome['scale']['level']} | {outcome['observable_result']} | "
            f"{'、'.join(outcome['source_refs'])} |"
        )
    lines.extend(
        [
            "",
            "## HistoricalEpisode",
            "",
        ]
    )
    indexed_episode_refs = set(
        report["episode_index_by_person"].get(person) or ()
    )
    episodes = {
        row["episode_id"]: row
        for row in report["episodes"]
        if row["episode_id"] in indexed_episode_refs
    }
    if not episodes:
        lines.append("当前没有进入计分链的 Episode。")
    for episode_id, episode in sorted(episodes.items()):
        source_refs = episode["lineage"].get("source_refs") or ""
        lines.extend(
            [
                f"### `{episode_id}`",
                "",
                f"- 行为：{episode['action']}",
                f"- 责任：{episode['responsibility']}",
                f"- 结果：{'；'.join(episode['outcome'])}",
                f"- 史源：{source_refs}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the current-only I5B neutral-material shadow chain")
    parser.add_argument("--source-pack", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    report = build_i5b_current_value(args.source_pack)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_markdown.write_text(
        render_scoring_detail_markdown(report), encoding="utf-8", newline="\n"
    )
    print(json.dumps({"ruler": report["ruler"], "status": report["status"], "episode_count": report["declarations"]["episode_count"], "reu_count": report["declarations"]["rule_evidence_unit_count"], "net_signal": report["net_signal"], "report_sha256": report["report_sha256"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
