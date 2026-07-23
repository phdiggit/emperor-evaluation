from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.historical_outcome_cluster import (
    assess_person_talent_grade,
)


SCHEMA_VERSION = "historical-person-profile-registry-v1"


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _assessment_clusters(
    outcome_registry: Mapping[str, Any],
    source_packs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    origin_clusters = {
        str(cluster["outcome_ref"]): cluster
        for source_pack in source_packs
        for cluster in (source_pack.get("outcome_registry") or {}).get("clusters") or ()
    }
    clusters = []
    for outcome in outcome_registry.get("outcomes") or ():
        cluster = dict(outcome)
        cluster["outcome_ref"] = str(outcome["registration_ref"])
        cluster["settlement_scope"] = {
            "war_terminal": "war_terminal_context",
            "person_command_result": "person_campaign_subresult",
        }.get(str(outcome["event_level"]), "independent_outcome")
        origin_rows = [
            origin_clusters[str(origin_ref)]
            for origin_ref in outcome.get("origin_outcome_refs") or ()
            if str(origin_ref) in origin_clusters
        ]
        members = []
        for member in outcome.get("members") or ():
            projected = dict(member)
            credits = {
                str(origin_member.get("talent_credit") or "")
                for origin in origin_rows
                for origin_member in origin.get("members") or ()
                if str(origin_member["actor_ref"]) == str(member["actor_ref"])
                and origin_member.get("talent_credit")
            }
            if len(credits) > 1:
                raise ValueError(
                    f"{outcome['registration_ref']} 的人物人才信用发生漂移: "
                    f"{member['actor_ref']}"
                )
            if credits:
                projected["talent_credit"] = next(iter(credits))
            members.append(projected)
        cluster["members"] = members
        clusters.append(cluster)
    return sorted(
        clusters,
        key=lambda row: (
            str(row["canonical_label"]),
            str(row["outcome_ref"]),
        ),
    )


def _single_shared_value(
    *,
    person: str,
    field: str,
    values: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    nonempty = [dict(value) for value in values if value]
    if not nonempty:
        return {}
    first = nonempty[0]
    if any(value != first for value in nonempty[1:]):
        raise ValueError(f"{person} 的共享人物画像字段发生漂移: {field}")
    return first


def build_historical_person_profile_registry(
    outcome_registry: Mapping[str, Any],
    source_packs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one full-lifecycle profile per person before ruler projection."""

    clusters = _assessment_clusters(outcome_registry, source_packs)
    names: dict[str, str] = {}
    member_candidates: dict[str, list[Mapping[str, Any]]] = {}
    for outcome in outcome_registry.get("outcomes") or ():
        for member in outcome.get("members") or ():
            person_ref = str(member["actor_ref"])
            person_name = str(member["actor_name"])
            existing_name = names.setdefault(person_ref, person_name)
            if existing_name != person_name:
                raise ValueError(f"人物引用对应多个姓名: {person_ref}")
    source_pack_refs = []
    for source_pack in source_packs:
        source_pack_ref = str(source_pack.get("source_pack_sha256") or "")
        if not source_pack_ref:
            raise ValueError("人物画像总登记输入缺少 source_pack_sha256")
        source_pack_refs.append(source_pack_ref)
        for member in source_pack.get("members") or ():
            person_ref = str(member["person_ref"])
            person_name = str(member["person"])
            existing_name = names.setdefault(person_ref, person_name)
            if existing_name != person_name:
                raise ValueError(f"人物引用对应多个姓名: {person_ref}")
            member_candidates.setdefault(person_ref, []).append(member)

    profiles = []
    for person_ref, person_name in sorted(names.items(), key=lambda row: row[1]):
        candidates = member_candidates.get(person_ref, [])
        profile_refs = {
            str(candidate.get("profile_ref") or "")
            for candidate in candidates
            if candidate.get("profile_ref")
        }
        if len(profile_refs) > 1:
            raise ValueError(f"{person_name} 对应多个共享 profile_ref")
        profile_ref = (
            next(iter(profile_refs))
            if profile_refs
            else "PROFILE-" + _digest({"person_ref": person_ref})[:16].upper()
        )
        reviews = [
            candidate.get("profile_review") or {} for candidate in candidates
        ]
        biography = _single_shared_value(
            person=person_name,
            field="full_lifecycle_biography",
            values=[
                review.get("full_lifecycle_biography") or {}
                for review in reviews
            ],
        )
        authority = _single_shared_value(
            person=person_name,
            field="authority_grade_calibration",
            values=[
                review.get("authority_grade_calibration") or {}
                for review in reviews
            ],
        )
        assessment = assess_person_talent_grade(
            person_ref=person_ref,
            clusters=clusters,
        )
        counted_outcomes = {
            str(outcome["registration_ref"]): outcome
            for outcome in outcome_registry.get("outcomes") or ()
            if str(outcome["registration_ref"]) in assessment["outcome_refs"]
        }
        talent_evidence_refs = sorted(
            {
                str(fact_ref)
                for outcome in counted_outcomes.values()
                for fact_ref in outcome.get("fact_refs") or ()
            }
        )
        coverage_gaps = []
        if (
            biography.get("scan_status") != "complete_section"
            or not biography.get("source_page")
            or not biography.get("revision_ref")
            or int(biography.get("section_chars") or 0) <= 0
            or not biography.get("evidence_refs")
        ):
            coverage_gaps.append("missing_full_lifecycle_biography_lineage")
        if (
            authority.get("status") != "accepted_current"
            or not authority.get("evidence_refs")
        ):
            coverage_gaps.append("missing_authoritative_grade_calibration")
        role_families = sorted(
            {
                str(role)
                for candidate in candidates
                for role in candidate.get("role_families") or ()
            }
        )
        profile = {
            "profile_ref": profile_ref,
            "person": person_name,
            "person_ref": person_ref,
            "overall_grade": assessment["grade"],
            "overall_rule_path": assessment["rule_path"],
            "overall_basis": assessment["basis"],
            "primary_domains": assessment["primary_domains"],
            "domain_grades": assessment["domain_grades"],
            "talent_grade_outcome_refs": assessment["outcome_refs"],
            "outcome_refs": sorted(
                str(outcome["registration_ref"])
                for outcome in outcome_registry.get("outcomes") or ()
                if any(
                    str(member["actor_ref"]) == person_ref
                    for member in outcome.get("members") or ()
                )
            ),
            "talent_grade_evidence_refs": talent_evidence_refs,
            "role_families": role_families,
            "full_lifecycle_biography": biography or None,
            "authority_grade_calibration": authority or None,
            "coverage_status": (
                "complete_shared_profile"
                if not coverage_gaps
                else "registered_outcomes_only"
            ),
            "coverage_gaps": coverage_gaps,
        }
        profile["profile_fingerprint"] = _digest(profile)
        profiles.append(profile)
    registry = {
        "schema_version": SCHEMA_VERSION,
        "status": "current_shadow_shared_profiles",
        "profiles": profiles,
        "declarations": {
            "profile_count": len(profiles),
            "complete_profile_count": sum(
                not profile["coverage_gaps"] for profile in profiles
            ),
            "open_profile_count": sum(
                bool(profile["coverage_gaps"]) for profile in profiles
            ),
            "source_pack_count": len(source_packs),
            "source_pack_refs": sorted(source_pack_refs),
            "outcome_registry_fingerprint": outcome_registry[
                "registry_fingerprint"
            ],
            "ruler_window_binding_count": 0,
            "team_projection_count": 0,
            "political_risk_projection_count": 0,
            "formal_write_count": 0,
        },
    }
    registry["registry_fingerprint"] = _digest(registry)
    return registry


def render_historical_person_profile_registry_markdown(
    registry: Mapping[str, Any],
) -> str:
    declarations = registry["declarations"]
    lines = [
        "# 人物全生涯画像总登记（未绑定皇帝窗口）",
        "",
        "> 人才档位与全生涯本传凭据在此共享；团队选择和政治风险按皇帝窗口另行投影。",
        "",
        f"- 总人物：{declarations['profile_count']}",
        f"- 画像闭合：{declarations['complete_profile_count']}",
        f"- 尚有缺口：{declarations['open_profile_count']}",
        f"- 皇帝窗口绑定：{declarations['ruler_window_binding_count']}",
        f"- 正式写入：{declarations['formal_write_count']}",
        "",
        "| 画像号 | 人物 | 总档 | 主领域 | 军事 | 治理 | 谋略 | 文化学术 | 定级依据 | 本传固定版本 | 覆盖状态 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    domain_labels = {
        "military": "军事",
        "civil_governance": "治理",
        "statecraft": "谋略",
        "culture_and_scholarship": "文化学术",
    }
    grade_labels = {
        "ordinary": "普通",
        "usable": "可用",
        "important": "重要",
        "top": "顶尖",
        "historic": "历史级",
    }
    coverage_labels = {
        "complete_shared_profile": "共享画像已闭合",
        "registered_outcomes_only": "仅成果登记，待补全生涯本传",
    }
    basis_labels = {
        "culture_and_scholarship：": "文化学术：",
        "civil_governance：": "治理：",
        "statecraft：": "谋略：",
        "military：": "军事：",
        "historic级": "历史级",
        "important级": "重要级",
        "national级": "全国级",
        "regional级": "区域级",
        "ordinary级": "普通级",
        "usable级": "可用级",
        "top级": "顶尖级",
    }
    for profile in registry["profiles"]:
        domains = profile["domain_grades"]
        biography = profile.get("full_lifecycle_biography") or {}
        source = (
            f"{biography['source_page']}@{biography['revision_ref']}"
            if biography
            else "未闭合"
        )
        primary = "、".join(
            domain_labels.get(str(value), str(value))
            for value in profile["primary_domains"]
        ) or "未确立"
        basis = str(profile["overall_basis"]).replace("|", "／").replace("\n", " ")
        for source_text, display_text in basis_labels.items():
            basis = basis.replace(source_text, display_text)
        lines.append(
            f"| {profile['profile_ref']} | {profile['person']} | "
            f"{grade_labels[profile['overall_grade']]} | {primary} | "
            f"{grade_labels[domains['military']['grade']]} | "
            f"{grade_labels[domains['civil_governance']['grade']]} | "
            f"{grade_labels[domains['statecraft']['grade']]} | "
            f"{grade_labels[domains['culture_and_scholarship']['grade']]} | "
            f"{basis} | {source} | "
            f"{coverage_labels[profile['coverage_status']]} |"
        )
    return "\n".join(lines) + "\n"
