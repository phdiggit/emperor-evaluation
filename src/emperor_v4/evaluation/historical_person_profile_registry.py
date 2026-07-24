from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.historical_outcome_cluster import (
    assess_person_talent_grade,
)


SCHEMA_VERSION = "historical-person-profile-registry-v2"


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
    origin_rulers = {
        str(cluster["outcome_ref"]): str(source_pack.get("ruler_ref") or "")
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
            own_reign_governance = (
                str(outcome["outcome_kind"]) == "governance"
                and any(
                    origin_rulers.get(str(origin["outcome_ref"])) == str(member["actor_ref"])
                    and str(origin.get("ruler_window_status") or "") == "within_window"
                    and any(
                        str(origin_member["actor_ref"]) == str(member["actor_ref"])
                        and str(origin_member.get("actor_kind") or "") == "ruler"
                        for origin_member in origin.get("members") or ()
                    )
                    for origin in origin_rows
                )
            )
            projected["talent_grade_eligible"] = not own_reign_governance
            if own_reign_governance:
                projected[
                    "talent_grade_exclusion_reason"
                ] = "ruler_own_reign_governance"
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


def _complete_grade_basis_outcomes(
    *,
    person_ref: str,
    clusters: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return every registered outcome eligible to inform a person's grade.

    This inventory is intentionally broader than the outcomes matched by the
    current talent-grade rule. Outcome registration is upstream of grading, so
    reaching a grade threshold must never hide another qualified outcome.
    """

    rows = []
    for cluster in clusters:
        if cluster.get("settlement_scope") == "war_terminal_context":
            continue
        member = next(
            (
                candidate
                for candidate in cluster.get("members") or ()
                if str(candidate["actor_ref"]) == person_ref
            ),
            None,
        )
        if member is None:
            continue
        if member.get("talent_grade_eligible") is False:
            continue
        kind = str(cluster["outcome_kind"])
        role_code = str(member["role_code"])
        if role_code not in {
            "commander_in_chief",
            "principal_commander",
            "exclusive",
            "lead",
        }:
            continue
        if kind == "campaign" and member.get("talent_credit") != "independent":
            continue
        payload = dict(cluster.get("payload") or {})
        rows.append(
            {
                "outcome_ref": str(cluster["outcome_ref"]),
                "origin_outcome_refs": sorted(
                    str(value)
                    for value in cluster.get("origin_outcome_refs") or ()
                ),
                "outcome_kind": kind,
                "canonical_label": str(cluster["canonical_label"]),
                "role_code": role_code,
                "contribution_scope": str(
                    member.get("contribution_scope") or ""
                ),
                "result_direction": str(cluster["result_direction"]),
                "result_status": str(cluster["result_status"]),
                "observable_result": str(cluster["observable_result"]),
                "scale": dict(cluster["scale"]),
                "current_outcome_assessment": (
                    {
                        "campaign_tier": str(payload["campaign_tier"]),
                        "combat_difficulty": str(payload["combat_difficulty"]),
                        "battle_result": str(payload["battle_result"]),
                        "objective_completion": str(
                            payload["objective_completion"]
                        ),
                    }
                    if kind == "campaign"
                    else {
                        "level": str(cluster["scale"]["level"]),
                        "domain": str(payload.get("domain") or ""),
                    }
                ),
                "fact_refs": sorted(
                    str(value) for value in cluster.get("fact_refs") or ()
                ),
                "source_refs": sorted(
                    str(value) for value in cluster.get("source_refs") or ()
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["outcome_kind"]),
            str(row["canonical_label"]),
            str(row["outcome_ref"]),
        ),
    )


def _render_complete_grade_basis(
    rows: Sequence[Mapping[str, Any]],
) -> str:
    role_labels = {
        "commander_in_chief": "主帅",
        "principal_commander": "主将",
        "exclusive": "独占",
        "lead": "主导",
    }
    domain_labels = {
        "campaign": "军事",
        "governance": "治理",
        "statecraft": "谋略",
    }
    battle_result_labels = {
        "victory": "胜利",
        "mixed": "有胜有失",
        "defeat": "失败",
        "unclear": "不明",
    }
    completion_labels = {
        "complete": "完成",
        "partial": "部分完成",
        "failed": "未完成",
        "unclear": "不明",
    }
    scale_labels = {
        "local": "局部",
        "important": "重要",
        "regional": "区域",
        "national": "全国",
        "era_shaping": "时代级",
    }
    parts = []
    for row in rows:
        assessment = row["current_outcome_assessment"]
        if row["outcome_kind"] == "campaign":
            assessment_text = (
                f"战役等级{assessment['campaign_tier']}、"
                f"作战难度{assessment['combat_difficulty']}、"
                f"结果{battle_result_labels[assessment['battle_result']]}/"
                f"{completion_labels[assessment['objective_completion']]}"
            )
        else:
            assessment_text = f"成果规模{scale_labels[assessment['level']]}"
        parts.append(
            f"{domain_labels[str(row['outcome_kind'])]}：作为"
            f"{role_labels[str(row['role_code'])]}承担“"
            f"{row['canonical_label']}”，{assessment_text}；"
            f"已实现结果：{row['observable_result']}"
        )
    return "。".join(parts) + ("。" if parts else "")


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
        complete_basis_outcomes = _complete_grade_basis_outcomes(
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
        talent_grade_exclusions = sorted(
            (
                {
                    "outcome_ref": str(cluster["outcome_ref"]),
                    "canonical_label": str(cluster["canonical_label"]),
                    "reason": str(member["talent_grade_exclusion_reason"]),
                }
                for cluster in clusters
                for member in cluster.get("members") or ()
                if str(member["actor_ref"]) == person_ref
                and member.get("talent_grade_eligible") is False
            ),
            key=lambda row: (row["canonical_label"], row["outcome_ref"]),
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
            "complete_grade_basis": _render_complete_grade_basis(
                complete_basis_outcomes
            ),
            "grade_basis_outcomes": complete_basis_outcomes,
            "primary_domains": assessment["primary_domains"],
            "domain_grades": assessment["domain_grades"],
            "talent_grade_outcome_refs": assessment["outcome_refs"],
            "talent_grade_exclusions": talent_grade_exclusions,
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
            "overall_grade_status": (
                "frozen"
                if not coverage_gaps
                else "registered_outcomes_lower_bound"
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
        "> 人才档位与全生涯本传凭据在此共享；皇帝本人在位治理保留为生涯事实但不抬高其人才档位；团队选择和政治风险按皇帝窗口另行投影。",
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
    role_labels = {
        "commander_in_chief": "主帅",
        "principal_commander": "主将",
        "exclusive": "独占",
        "lead": "主导",
    }
    battle_result_labels = {
        "victory": "胜利",
        "mixed": "有胜有失",
        "defeat": "失败",
        "unclear": "不明",
    }
    completion_labels = {
        "complete": "完成",
        "partial": "部分完成",
        "failed": "未完成",
        "unclear": "不明",
    }
    scale_labels = {
        "local": "局部",
        "important": "重要",
        "regional": "区域",
        "national": "全国",
        "era_shaping": "时代级",
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
        overall_grade = grade_labels[profile["overall_grade"]]
        if profile.get("overall_grade_status") == "registered_outcomes_lower_bound":
            overall_grade = "至少" + overall_grade
        biography = profile.get("full_lifecycle_biography") or {}
        source_versions = {
            str(source_ref).split("#", 1)[0]
            for outcome in profile["grade_basis_outcomes"]
            for source_ref in outcome.get("source_refs") or ()
        }
        if biography:
            source_versions.add(
                f"{biography['source_page']}@{biography['revision_ref']}"
            )
        source = "、".join(sorted(source_versions)) or "未闭合"
        primary = "、".join(
            domain_labels.get(str(value), str(value))
            for value in profile["primary_domains"]
        ) or "未确立"
        basis_count = len(profile["grade_basis_outcomes"])
        basis = (
            f"[{basis_count} 项，查看明细]"
            f"(#profile-{str(profile['profile_ref']).lower()})"
            if basis_count
            else "无达到登记门槛的独立成果"
        )
        lines.append(
            f"| {profile['profile_ref']} | {profile['person']} | "
            f"{overall_grade} | {primary} | "
            f"{grade_labels[domains['military']['grade']]} | "
            f"{grade_labels[domains['civil_governance']['grade']]} | "
            f"{grade_labels[domains['statecraft']['grade']]} | "
            f"{grade_labels[domains['culture_and_scholarship']['grade']]} | "
            f"{basis} | {source} | "
            f"{coverage_labels[profile['coverage_status']]} |"
        )
    lines.extend(["", "## 完整定级依据", ""])
    for profile in registry["profiles"]:
        rows = profile["grade_basis_outcomes"]
        exclusions = profile.get("talent_grade_exclusions") or []
        if not rows and not exclusions:
            continue
        anchor = f"profile-{str(profile['profile_ref']).lower()}"
        current_basis = str(profile["overall_basis"]).replace("\n", " ")
        overall_grade = grade_labels[profile["overall_grade"]]
        if profile.get("overall_grade_status") == "registered_outcomes_lower_bound":
            overall_grade = "至少" + overall_grade
        for source_text, display_text in basis_labels.items():
            current_basis = current_basis.replace(source_text, display_text)
        lines.extend(
            [
                f'<a id="{anchor}"></a>',
                "",
                f"### {profile['person']}（{overall_grade}）",
                "",
                f"- 当前档位判定：{current_basis}",
                f"- 全部合格成果：{len(rows)} 项",
                f"- 定级排除：{len(exclusions)} 项",
                "",
            ]
        )
        if exclusions:
            lines.append(
                "- 排除明细："
                + "；".join(
                    f"{row['canonical_label']}（{row['reason']}）"
                    for row in exclusions
                )
            )
            lines.append("")
        for index, row in enumerate(rows, start=1):
            assessment = row["current_outcome_assessment"]
            if row["outcome_kind"] == "campaign":
                assessment_text = (
                    f"{assessment['campaign_tier']} / "
                    f"{assessment['combat_difficulty']}；"
                    f"{battle_result_labels[assessment['battle_result']]} / "
                    f"{completion_labels[assessment['objective_completion']]}"
                )
            else:
                assessment_text = (
                    f"成果规模 {scale_labels[assessment['level']]}"
                )
            sources = "；".join(row.get("source_refs") or ()) or "未登记"
            lines.extend(
                [
                    f"{index}. {row['canonical_label']}",
                    "",
                    f"   - 责任：{role_labels[row['role_code']]}；"
                    f"{row['contribution_scope'] or '见成果成员责任链'}",
                    f"   - 当前成果定级：{assessment_text}",
                    f"   - 实际结果：{row['observable_result']}",
                    f"   - 固定史源：{sources}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"
