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
from emperor_v4.persistence.core_registry import RuleEvidenceUnitRecord


SCHEMA_VERSION = "i5b-current-value-report-v3"
SOURCE_PACK_SCHEMA_VERSION = "i5b-current-value-source-pack-v3"
RULES = ("talent_discovery", "appointment_delegation", "tolerate_talent", "anti_nepotism")


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
    uncertainties = tuple([str(material["remaining_gap"])]) if material.get("remaining_gap") else ()
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
        provenance={"ruler": ruler, "source_unit_code": str(material["source_unit_code"]), "mode": "current_shadow"},
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
    if len(pack.get("governance_achievements") or ()) != int(dispositions["dynasty_governance"]["ruler_window_achievement_count"]):
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
            if str(material["person_ref"])
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
        required = set(_required_factor_names(rule, direction))
        if set(options) != required:
            raise ValueError(f"{material['material_id']} 因子集合不闭合")
        values = _policy_values(policy, rule, options)
        declared_values = {name: str(value) for name, value in (material.get("factor_values") or {}).items()}
        mapped_values = {name: str(value) for name, value in values.items()}
        if declared_values != mapped_values:
            raise ValueError(f"{material['material_id']} 数值不是政策确定性映射")
        episode, reu = _episode_and_reu(
            material=material,
            facts=facts,
            ruler_contexts=ruler_contexts,
            ruler=str(pack["ruler"]),
        )
        existing_episode = episode_by_id.setdefault(episode.episode_id, episode)
        if existing_episode != episode:
            raise ValueError(f"Episode 语义指纹冲突: {episode.episode_id}")
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
                "fact": material["fact_summary"],
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
    team = pack["team"]
    governance_by_ref = {
        str(row["achievement_ref"]): row
        for row in pack.get("governance_achievements") or ()
    }
    positive_member_refs = {
        str(row["person_ref"])
        for row in facts.values()
        if str(row["canonical_name"]) in set(team["positive_members"])
    }
    team_governance_refs = sorted(
        ref
        for ref, row in governance_by_ref.items()
        if row["payload"].get("result_direction") == "positive"
        and row["payload"].get("positive_result_preserved") is True
        and row["payload"].get("implementation_status") in {"operated", "completed"}
        and row["payload"].get("scale", {}).get("level") in {"national", "important"}
        and positive_member_refs.intersection(str(value) for value in row.get("person_refs") or ())
    )
    governance_results = [
        {
            "result": governance_by_ref[ref]["payload"]["observable_result"],
            "source_refs": governance_by_ref[ref]["payload"]["source_refs"],
            "governance_achievement_ref": ref,
        }
        for ref in team_governance_refs
    ]
    governance_dispositions = [
        {
            "governance_achievement_ref": ref,
            "disposition": (
                "selected_team_result_support"
                if ref in team_governance_refs
                else "supporting_policy_context_not_i5b_team_score"
                if row["payload"].get("result_direction") == "positive"
                and row["payload"].get("positive_result_preserved") is True
                else "excluded_no_preserved_positive_result"
            ),
        }
        for ref, row in sorted(governance_by_ref.items())
    ]
    declared_team_support_count = int(
        dispositions["dynasty_governance"].get("team_support_count") or 0
    )
    if declared_team_support_count != len(team_governance_refs):
        raise ValueError("朝代文治团队支持数量与确定性选择不一致")
    profile_projection_review = []
    for member in sorted(pack.get("members") or (), key=lambda row: str(row["person"])):
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
            if person_ref in {str(value) for value in row.get("person_refs") or ()}
        )
        supporting_unit_refs = sorted(
            str(value) for value in member.get("supporting_unit_refs") or ()
        )
        profile_review = member.get("profile_review") or {}
        biography_scan = profile_review.get("full_lifecycle_biography") or {}
        talent_review = profile_review.get("talent_grade") or {}
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
        known_profile_refs = (
            set(facts) | set(ruler_contexts) | set(governance_by_ref)
        )
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
            talent_review.get("status") != "accepted_current"
            or talent_review.get("grade") != member["effective_talent_grade"]
            or talent_review.get("policy_ref")
            != "config/talent-grade-v11-domain-equivalent-historic.yml"
            or not profile_evidence_refs.get("talent_grade")
        ):
            gaps.append("missing_talent_grade_lineage")
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
                "governance_achievement_refs": member_governance_refs,
                "supporting_unit_refs": supporting_unit_refs,
                "profile_evidence_refs": profile_evidence_refs,
                "profile_review": profile_review,
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
        raise ValueError("人物画像声明覆盖闭合但仍存在 lineage 缺口")
    manifest["rules"]["team_building"] = {
        "source": str(source_pack_path),
        "positive_members": team["positive_members"],
        "negative_members": team["negative_members"],
        "functional_complementarity": team["functional_complementarity"],
        "long_term_stability": team["long_term_stability"],
        "remaining_member_judge_reason": "当前人物画像与窗口风险仍为暂定值；未进入正8/负3的成员仅作支持。",
        "governance_results": governance_results,
    }
    budget = build_i5b_material_budget_shadow(source_pack_path, manifest_payload=manifest)
    team_semantic = _digest(
        {
            "ruler_ref": pack["ruler_ref"],
            "positive_members": team["positive_members"],
            "negative_members": team["negative_members"],
            "governance_achievement_refs": team_governance_refs,
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
                    member_type="governance_achievement",
                    member_role="governance_result_support",
                )
                for ref in team_governance_refs
            ),
        ),
    )
    episodes = sorted(episode_by_id.values(), key=lambda value: value.episode_id)
    by_person: dict[str, list[str]] = {}
    fact_owner = {str(row["person_ref"]): str(row["canonical_name"]) for row in facts.values()}
    for episode in episodes:
        by_person.setdefault(fact_owner[episode.evaluation_context], []).append(episode.episode_id)
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
        "source_pack_ref": str(source_pack_path.relative_to(workspace_root)),
        "source_pack_sha256": declared_hash,
        "three_channel_input": three_channel,
        "three_channel_disposition": dispositions,
        "judge_coverage": pack["judge_coverage"],
        "linked_ruler_context_refs": sorted(linked_ruler_context_refs),
        "governance_results": governance_results,
        "governance_dispositions": governance_dispositions,
        "profile_projection_gate": profile_gate,
        "profile_projection_review": profile_projection_review,
        "episodes": [asdict(value) for value in episodes],
        "episode_index_by_person": {name: sorted(ids) for name, ids in sorted(by_person.items())},
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
    report["report_sha256"] = _digest(report)
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        f"# {report['ruler']} I5B 当前值影子结果",
        "",
        f"- 三路输入指纹：`{report['three_channel_input']['fingerprint']}`",
        f"- Episode：`{report['declarations']['episode_count']}`；REU：`{report['declarations']['rule_evidence_unit_count']}`",
        f"- 本纪补证链接：`{report['declarations']['linked_ruler_context_count']}`；文治结果支持：`{report['declarations']['selected_governance_result_count']}`",
        f"- 加权净信号：`{report['net_signal']}`",
        "- 人才等级与政治风险：材料覆盖仍开放，当前值仅为暂定输入，未冻结。",
        "- 45 分、档位和排名：未生成。",
        "",
        "## 五条规则",
        "",
        "| 规则 | 正向 | 负向 | 净信号 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for rule in report["material_budget"]["rules"]:
        lines.append(f"| {rule['rule_label']} | {rule['positive_signal']} | {rule['negative_signal']} | {rule['rule_raw_net']} |")
    lines.extend(["", "## 各臣子 Episode", ""])
    episode_by_id = {row["episode_id"]: row for row in report["episodes"]}
    rules_by_episode: dict[str, set[str]] = {}
    for reu in report["rule_evidence_units"]:
        for member in reu["members"]:
            if member["member_type"] == "episode":
                rules_by_episode.setdefault(member["member_ref"], set()).add(
                    reu["rule_code"]
                )
    for person, ids in report["episode_index_by_person"].items():
        lines.append(f"### {person}")
        lines.append("")
        for episode_id in ids:
            episode = episode_by_id[episode_id]
            rule_labels = "、".join(sorted(rules_by_episode[episode_id]))
            lines.append(f"- `{episode_id}`（{rule_labels}）：{episode['action']}")
        lines.append("")
    return "\n".join(lines)


def _decimal_text(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001")))


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
        return render_i5b_material_budget_shadow_markdown(material_budget)
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
    lines.extend(
        [
            "",
            "## 当前人物画像",
            "",
            "| 人才档位 | 政治风险状态 | 风险严重度 | 画像状态 | 本传史源 |",
            "| --- | --- | --- | --- | --- |",
            f"| {profile['candidate_talent_grade']} | {risk['assessment_status']} | "
            f"{risk.get('severity') or '无'} | {profile['value_status']} | "
            f"{biography['source_page']}@{biography['revision_ref']} |",
            "",
            f"政治风险判定：{risk['basis']}",
            "",
            "## HistoricalEpisode",
            "",
        ]
    )
    episodes = {
        row["episode_id"]: row
        for row in report["episodes"]
        if row["evaluation_context"] == profile["person_ref"]
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
    args.output_markdown.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"ruler": report["ruler"], "status": report["status"], "episode_count": report["declarations"]["episode_count"], "reu_count": report["declarations"]["rule_evidence_unit_count"], "net_signal": report["net_signal"], "report_sha256": report["report_sha256"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
