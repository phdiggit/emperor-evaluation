from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from uuid import uuid4

import yaml

from emperor_v4.evaluation.historical_outcome_cluster import (
    SCHEMA_VERSION as CLUSTER_SCHEMA_VERSION,
    cluster_semantic_fingerprint,
)
from emperor_v4.evaluation.historical_person_profile_registry import (
    build_historical_person_profile_registry,
    render_historical_person_profile_registry_markdown,
)


SCHEMA_VERSION = "historical-outcome-unbound-registry-v3"

_DISPLAY_LABELS = {
    "war_terminal": "战争终局根节点",
    "campaign_group": "战役群",
    "person_command_result": "人物指挥子成果",
    "governance_result": "治理成果",
    "macro_public_result": "宏观公共结果",
    "person_statecraft_result": "人物谋略成果",
    "commander_in_chief": "主帅",
    "principal_commander": "主将",
    "participant": "从攻",
    "not_in_command_chain": "不在军事指挥链",
    "exclusive": "独占",
    "lead": "主导",
    "governance_participant": "实质参与",
    "authorized": "正式授权",
    "reign_holder": "在位承接",
    "authorization_only": "仅授权",
    "operational_direction": "战役筹划与统筹",
    "frontline_command": "前线最高指挥",
    "local": "局部",
    "important": "重要",
    "regional": "区域",
    "national": "全国",
    "era_shaping": "时代塑造",
    "local_tactical": "局部战术",
    "important_objective": "重要目标",
    "regional_theater_control": "区域战区控制",
    "national_war_outcome": "全国战争结果",
    "state_survival": "国家存亡",
    "unification": "统一",
    "state_conquest": "灭国",
    "local_public_result": "局部公共结果",
    "important_public_result": "重要公共结果",
    "regional_governance_result": "区域治理结果",
    "national_core_subsystem": "全国核心子系统",
    "national_public_result": "全国公共结果",
    "national_cultural_corpus": "全国文化典籍",
    "era_order_reconstruction": "时代秩序重构",
    "civilization_foundational_corpus": "文明奠基典籍",
    "major_stage_or_crisis": "重大阶段或危机",
    "independent_direction": "独立战略方向",
    "single_pole_or_state_terminal": "单一竞争极或国家终局",
    "composite_poles_terminal": "复合竞争极终局",
    "unification_terminal": "统一终局",
    "external_hegemony_terminal": "外部霸权终局",
    "local_point": "局部节点",
    "important_region": "重要区域",
    "strategic_gateway": "战略门户",
    "core_heartland": "核心腹地",
    "capital_or_state_survival": "都城或国家存亡",
    "bounded": "局部可承受",
    "major": "重大",
    "critical": "关键",
    "existential": "存亡级",
    "minor": "弱小力量",
    "regional_major": "区域主要对手",
    "first_tier_pole": "第一梯队竞争极",
    "dominant_pole": "主导竞争极",
    "external_state": "外部国家",
    "external_hegemony": "外部霸权",
    "unclear": "不明",
    "strong": "强盛",
    "viable": "可战",
    "weakened": "削弱",
    "residual": "残余",
    "victory": "胜利",
    "mixed": "混合",
    "defeat": "失败",
    "complete": "完成",
    "partial": "部分完成",
    "failed": "失败",
    "none": "无",
    "limited": "有限",
    "material": "实质",
    "severe_repaired": "严重但已修复",
    "near_collapse_repaired": "近乎崩溃但已修复",
    "terminal_failure": "终局失败",
    "primary": "主要责任",
    "shared": "共同责任",
    "subordinate_execution": "部属执行",
    "disobedience": "违令",
    "mitigated": "已减责",
    "not_responsible": "无责任",
    "external_unattributed": "外部不可归责",
    "established": "因果已建立",
    "source_attributed": "史源支持结果归因",
    "members": "成员列表",
    "revision": "固定版本",
    "positive": "正面",
    "negative": "负面",
    "mixed": "利弊并存",
    "unclear": "证据不足",
    "not_established": "未建立",
    "incremental": "有限影响",
    "significant": "显著影响",
    "structural": "结构性影响",
    "era_shaping": "时代塑造",
    "productivity_livelihood": "生产力与民生",
    "civilization_institution": "文明与制度进步",
    "civilization_institutions": "文明与制度进步",
    "state_people_security": "国家与民众安全",
    "culture_intellectual": "文化教育与思想活力",
    "culture_education_thought": "文化教育与思想活力",
    "policy_design": "政策设计",
    "institutional_design": "制度设计",
    "implementation_lead": "实施主导",
    "operational_delivery": "运行交付",
    "corrective_oversight": "纠偏监督",
    "scholarly_authorship": "学术创作",
    "implemented": "已实施",
    "operated": "已运行",
    "completed": "已完成",
    "failed": "失败",
}


def _display_label(value: object) -> str:
    text = str(value)
    return _DISPLAY_LABELS.get(text, text)


def _display_text(value: object) -> str:
    text = str(value)
    for token in sorted(_DISPLAY_LABELS, key=len, reverse=True):
        text = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])",
            _DISPLAY_LABELS[token],
            text,
        )
    return text.replace("固定 固定版本", "固定版本")


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _registration_ref(outcome_kind: str, independent_key: str) -> str:
    return "HOUT-" + _digest(
        {"outcome_kind": outcome_kind, "independent_key": independent_key}
    )[:20].upper()


def normalize_outcome_registry_for_public_view(
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    """Expose legacy governance outcomes through the current public contract.

    Source packs remain immutable scoring inputs.  This compatibility boundary
    fixes only two retired public-view encodings: ``mixed`` as an operation
    status, and a direction asserted without an explicit comparison category.
    """

    normalized = json.loads(json.dumps(registry, ensure_ascii=False))
    axis_labels = {
        "productivity_livelihood": "生产力与民生",
        "civilization_institutions": "文明与制度进步",
        "state_people_security": "国家与民众安全",
        "culture_education_thought": "文化教育与思想活力",
    }
    direction_labels = {
        "positive": "正向",
        "negative": "负向",
        "mixed": "利弊并存",
        "not_established": "未建立",
    }
    for cluster in normalized.get("clusters") or ():
        if cluster.get("outcome_kind") != "governance":
            continue
        if cluster.get("result_status") == "mixed":
            cluster["result_status"] = "operated"
        judgment = (cluster.get("payload") or {}).get("value_judgment") or {}
        comparison_basis = str(judgment.get("comparison_basis") or "")
        if comparison_basis == "public_effect_without_explicit_baseline":
            comparison_basis = (
                "not_established"
                if judgment.get("overall_direction") == "unclear"
                else "inferred_prior_state"
            )
            judgment["comparison_basis"] = comparison_basis
            if comparison_basis == "not_established":
                judgment["overall_direction"] = "unclear"
                judgment["overall_magnitude"] = "not_established"
                cluster["result_direction"] = "unclear"
        label = str(cluster.get("canonical_label") or "本项治理")
        result = str(cluster.get("observable_result") or "逐字材料所载公共结果")
        basis = str(judgment.get("basis") or "")
        if comparison_basis != "not_established" and not all(
            marker in basis for marker in ("基线：", "变化：", "结果：")
        ):
            baseline_refs = "、".join(
                str(value) for value in judgment.get("baseline_fact_refs") or ()
            )
            baseline = (
                f"逐字证据链中的历史基线事实（{baseline_refs}）"
                if baseline_refs
                else "逐字材料未直陈前态，按该项公共制度或结果尚未形成的最低前态推定"
            )
            judgment["basis"] = (
                f"基线：{baseline}；变化：{label}；结果：{result}"
            )
        elif comparison_basis == "not_established":
            judgment["basis"] = "现有逐字材料无法建立举措前后比较，价值方向保持不明。"
        for axis_name, axis in (judgment.get("axes") or {}).items():
            direction = str(axis.get("direction") or "not_established")
            axis_basis = str(axis.get("basis") or "")
            if direction == "not_established":
                if not axis_basis:
                    axis["basis"] = "现有逐字材料未建立该轴的公共效果。"
                continue
            if (
                not axis_basis
                or "逐字材料显示" in axis_basis
                or axis_name in axis_basis
                or (direction == "negative" and "改善" in axis_basis)
            ):
                axis["basis"] = (
                    f"{axis_labels.get(axis_name, axis_name)}轴按逐字材料所载结果"
                    f"“{result}”判断为{direction_labels.get(direction, direction)}。"
                )
        cluster["semantic_fingerprint"] = cluster_semantic_fingerprint(cluster)
    return normalized


def public_registry_matches_source_pack(
    materialized: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    *,
    ruler_ref: str | None = None,
) -> bool:
    """Accept a pack projection even when shared ruler duties add public outcomes."""

    if ruler_ref is not None:
        source_registry = {
            **source_registry,
            "clusters": [
                cluster
                for cluster in source_registry.get("clusters") or ()
                if cluster.get("outcome_kind") != "governance"
                or any(
                    member.get("actor_kind") == "ruler"
                    and str(member.get("actor_ref") or "") == ruler_ref
                    for member in cluster.get("members") or ()
                )
            ],
        }
    normalized_source = normalize_outcome_registry_for_public_view(source_registry)
    for expected in (source_registry, normalized_source):
        if materialized == expected:
            return True
        source_keys = {
            (str(row["outcome_kind"]), str(row["independent_key"]))
            for row in expected.get("clusters") or ()
        }
        projected = {
            **materialized,
            "clusters": [
                row
                for row in materialized.get("clusters") or ()
                if (str(row["outcome_kind"]), str(row["independent_key"]))
                in source_keys
            ],
        }
        if projected == expected:
            return True

    def comparable_cluster(cluster: Mapping[str, Any]) -> dict[str, Any]:
        comparable = {
            key: value
            for key, value in cluster.items()
            if key
            not in {
                "fact_refs",
                "source_refs",
                "episode_refs",
                "evidence_lineage",
                "members",
                "limitations",
                "semantic_fingerprint",
            }
        }
        payload = dict(comparable.get("payload") or {})
        judgment = payload.get("value_judgment")
        if isinstance(judgment, Mapping):
            payload["value_judgment"] = {
                "comparison_basis": judgment.get("comparison_basis"),
                "effect_horizon": judgment.get("effect_horizon"),
                "overall_direction": judgment.get("overall_direction"),
                "overall_magnitude": judgment.get("overall_magnitude"),
                "axes": {
                    axis_name: {
                        "direction": axis.get("direction"),
                        "magnitude": axis.get("magnitude"),
                    }
                    for axis_name, axis in (judgment.get("axes") or {}).items()
                },
            }
            comparable["payload"] = payload
        return comparable

    def member_core(member: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in member.items()
            if key
            not in {
                "contribution_basis_fact_refs",
                "contribution_types",
            }
        }

    def merged_cluster_contains_source(
        actual: Mapping[str, Any],
        expected: Mapping[str, Any],
    ) -> bool:
        if comparable_cluster(actual) != comparable_cluster(expected):
            return False
        for field in ("fact_refs", "source_refs", "episode_refs", "limitations"):
            if not set(expected.get(field) or ()).issubset(
                set(actual.get(field) or ())
            ):
                return False
        actual_lineage = {
            str(row["fact_ref"]): set(row.get("evidence_roles") or ())
            for row in actual.get("evidence_lineage") or ()
        }
        for row in expected.get("evidence_lineage") or ():
            if not set(row.get("evidence_roles") or ()).issubset(
                actual_lineage.get(str(row["fact_ref"]), set())
            ):
                return False
        actual_members = {
            str(row["actor_ref"]): row for row in actual.get("members") or ()
        }
        for expected_member in expected.get("members") or ():
            actual_member = actual_members.get(str(expected_member["actor_ref"]))
            if actual_member is None:
                return False
            if member_core(actual_member) != member_core(expected_member):
                return False
            for field in (
                "contribution_basis_fact_refs",
                "contribution_types",
            ):
                if not set(expected_member.get(field) or ()).issubset(
                    set(actual_member.get(field) or ())
                ):
                    return False
        return True

    if (
        materialized.get("schema_version") == normalized_source.get("schema_version")
        and materialized.get("status") == normalized_source.get("status")
    ):
        actual_by_key = {
            (str(row["outcome_kind"]), str(row["independent_key"])): row
            for row in materialized.get("clusters") or ()
        }
        expected_by_key = {
            (str(row["outcome_kind"]), str(row["independent_key"])): row
            for row in normalized_source.get("clusters") or ()
        }
        if all(
            key in actual_by_key
            and merged_cluster_contains_source(actual_by_key[key], expected)
            for key, expected in expected_by_key.items()
        ):
            return True
    return False


def _event_level(cluster: Mapping[str, Any]) -> str:
    scope = str(cluster.get("settlement_scope") or "")
    if cluster["outcome_kind"] == "campaign":
        if scope == "war_terminal_context":
            return "war_terminal"
        return (
            "person_command_result"
            if scope == "person_campaign_subresult"
            else "campaign_group"
        )
    if cluster["outcome_kind"] == "statecraft":
        return "person_statecraft_result"
    return "macro_public_result" if scope == "reign_macro_outcome" else "governance_result"


def _unbound_member(member: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        key: value
        for key, value in member.items()
        if key not in {"actor_kind", "talent_credit", "ruler_campaign_relation"}
    }
    if member.get("ruler_campaign_relation") is not None:
        result["sovereign_relation"] = member["ruler_campaign_relation"]
    return result


def _unbound_outcome(cluster: Mapping[str, Any]) -> dict[str, Any]:
    cluster = (
        normalize_outcome_registry_for_public_view(
            {"clusters": [cluster]}
        )["clusters"][0]
    )
    result = {
        key: value
        for key, value in cluster.items()
        if key
        not in {
            "outcome_ref",
            "semantic_fingerprint",
            "settlement_scope",
            "ruler_window_status",
            "ruler_context_refs",
            "parent_outcome_ref",
        }
    }
    result["registration_ref"] = _registration_ref(
        str(cluster["outcome_kind"]), str(cluster["independent_key"])
    )
    result["event_level"] = _event_level(cluster)
    result["members"] = [_unbound_member(row) for row in cluster["members"]]
    result["origin_outcome_refs"] = [str(cluster["outcome_ref"])]
    if cluster.get("parent_outcome_ref"):
        result["origin_parent_outcome_ref"] = str(cluster["parent_outcome_ref"])
    return result


def build_unbound_historical_outcome_registry(
    source_packs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the auditable outcome layer before any ruler-window projection."""

    def comparable_outcome(
        outcome: Mapping[str, Any], mergeable_fields: set[str]
    ) -> dict[str, Any]:
        comparable = {
            name: value
            for name, value in outcome.items()
            if name not in mergeable_fields
        }
        payload = dict(comparable.get("payload") or {})
        judgment = payload.get("value_judgment")
        if isinstance(judgment, Mapping):
            payload["value_judgment"] = {
                "comparison_basis": judgment.get("comparison_basis"),
                "effect_horizon": judgment.get("effect_horizon"),
                "overall_direction": judgment.get("overall_direction"),
                "overall_magnitude": judgment.get("overall_magnitude"),
                "axes": {
                    axis_name: {
                        "direction": axis.get("direction"),
                        "magnitude": axis.get("magnitude"),
                    }
                    for axis_name, axis in (judgment.get("axes") or {}).items()
                },
            }
            comparable["payload"] = payload
        return comparable

    def merge_value_judgment_evidence(
        existing: dict[str, Any], candidate: Mapping[str, Any]
    ) -> None:
        existing_judgment = (existing.get("payload") or {}).get("value_judgment")
        candidate_judgment = (candidate.get("payload") or {}).get("value_judgment")
        if not isinstance(existing_judgment, dict) or not isinstance(
            candidate_judgment, Mapping
        ):
            return
        existing_judgment["baseline_fact_refs"] = list(
            dict.fromkeys(
                [
                    *existing_judgment.get("baseline_fact_refs", ()),
                    *candidate_judgment.get("baseline_fact_refs", ()),
                ]
            )
        )
        for axis_name, candidate_axis in (
            candidate_judgment.get("axes") or {}
        ).items():
            existing_axis = (existing_judgment.get("axes") or {}).get(axis_name)
            if not isinstance(existing_axis, dict):
                continue
            existing_axis["basis_fact_refs"] = list(
                dict.fromkeys(
                    [
                        *existing_axis.get("basis_fact_refs", ()),
                        *candidate_axis.get("basis_fact_refs", ()),
                    ]
                )
            )

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    origin_to_registration: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    source_pack_refs = []
    duplicate_count = 0
    for source_pack in source_packs:
        source_pack_ref = str(source_pack.get("source_pack_sha256") or "")
        if not source_pack_ref:
            raise ValueError("成果总登记输入缺少 source_pack_sha256")
        source_pack_refs.append(source_pack_ref)
        registry = source_pack.get("outcome_registry") or {}
        for cluster in registry.get("clusters") or ():
            key = (str(cluster["outcome_kind"]), str(cluster["independent_key"]))
            candidate = _unbound_outcome(cluster)
            origin_ref = str(cluster["outcome_ref"])
            origin_to_registration[origin_ref] = candidate["registration_ref"]
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = candidate
                continue
            duplicate_count += 1
            mergeable_fields = {
                "fact_refs",
                "source_refs",
                "episode_refs",
                "origin_outcome_refs",
                "evidence_lineage",
                "members",
                "limitations",
            }
            comparable_existing = comparable_outcome(existing, mergeable_fields)
            comparable_candidate = comparable_outcome(candidate, mergeable_fields)
            if comparable_existing != comparable_candidate:
                conflicts.append(
                    {
                        "outcome_kind": key[0],
                        "independent_key": key[1],
                        "origin_outcome_refs": sorted(
                            {
                                *existing["origin_outcome_refs"],
                                *candidate["origin_outcome_refs"],
                            }
                        ),
                        "reason": "同一全局成果键的成果本体不一致，必须先人工归并。",
                    }
                )
                continue
            merge_value_judgment_evidence(existing, candidate)
            for field in (
                "fact_refs",
                "source_refs",
                "episode_refs",
                "origin_outcome_refs",
                "limitations",
            ):
                current_values = list(existing.get(field) or ())
                current_set = set(current_values)
                existing[field] = current_values + sorted(
                    value
                    for value in (candidate.get(field) or ())
                    if value not in current_set
                )
            existing_lineage = [
                dict(row) for row in existing.get("evidence_lineage") or ()
            ]
            lineage_by_ref = {
                str(row["fact_ref"]): row for row in existing_lineage
            }
            for row in candidate.get("evidence_lineage") or ():
                fact_ref = str(row["fact_ref"])
                previous = lineage_by_ref.get(fact_ref)
                if previous is None:
                    appended = dict(row)
                    lineage_by_ref[fact_ref] = appended
                    existing_lineage.append(appended)
                    continue
                previous["evidence_roles"] = list(
                    dict.fromkeys(
                        [
                            *previous.get("evidence_roles", ()),
                            *row.get("evidence_roles", ()),
                        ]
                    )
                )
            existing["evidence_lineage"] = existing_lineage
            existing_members = [
                dict(row) for row in existing.get("members") or ()
            ]
            members_by_ref = {
                str(row["actor_ref"]): row for row in existing_members
            }
            for row in candidate.get("members") or ():
                actor_ref = str(row["actor_ref"])
                previous = members_by_ref.get(actor_ref)
                if previous is None:
                    appended = dict(row)
                    members_by_ref[actor_ref] = appended
                    existing_members.append(appended)
                    continue
                comparable_previous = {
                    key: value
                    for key, value in previous.items()
                    if key
                    not in {
                        "contribution_basis_fact_refs",
                        "contribution_types",
                    }
                }
                comparable_member = {
                    key: value
                    for key, value in row.items()
                    if key
                    not in {
                        "contribution_basis_fact_refs",
                        "contribution_types",
                    }
                }
                if comparable_previous != comparable_member:
                    conflicts.append(
                        {
                            "outcome_kind": key[0],
                            "independent_key": key[1],
                            "origin_outcome_refs": sorted(
                                {
                                    *existing["origin_outcome_refs"],
                                    *candidate["origin_outcome_refs"],
                                }
                            ),
                            "reason": (
                                "同一全局成果键的人物责任不一致，必须先人工归并。"
                            ),
                        }
                    )
                    continue
                for field in (
                    "contribution_basis_fact_refs",
                    "contribution_types",
                ):
                    if field in previous or field in row:
                        previous[field] = list(
                            dict.fromkeys(
                                [
                                    *previous.get(field, ()),
                                    *row.get(field, ()),
                                ]
                            )
                        )
            existing["members"] = existing_members

    outcomes = list(by_key.values())
    for outcome in outcomes:
        origin_parent = outcome.pop("origin_parent_outcome_ref", None)
        if origin_parent:
            parent_ref = origin_to_registration.get(str(origin_parent))
            if parent_ref is None:
                conflicts.append(
                    {
                        "outcome_kind": outcome["outcome_kind"],
                        "independent_key": outcome["independent_key"],
                        "origin_outcome_refs": outcome["origin_outcome_refs"],
                        "reason": "人物子战役的父级成果不在总登记输入中。",
                    }
                )
            else:
                outcome["parent_registration_ref"] = parent_ref
        outcome["registration_fingerprint"] = _digest(
            {
                key: value
                for key, value in outcome.items()
                if key not in {"origin_outcome_refs", "registration_fingerprint"}
            }
        )
    outcomes.sort(
        key=lambda row: (
            {"campaign": 0, "governance": 1, "statecraft": 2}[row["outcome_kind"]],
            str((row.get("period") or {}).get("start") or ""),
            str(row["canonical_label"]),
        )
    )
    campaign_count = sum(row["outcome_kind"] == "campaign" for row in outcomes)
    governance_count = sum(row["outcome_kind"] == "governance" for row in outcomes)
    statecraft_count = sum(row["outcome_kind"] == "statecraft" for row in outcomes)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "needs_review" if conflicts else "current_shadow_unbound",
        "declarations": {
            "source_pack_count": len(source_packs),
            "source_pack_refs": sorted(source_pack_refs),
            "outcome_count": len(outcomes),
            "campaign_count": campaign_count,
            "governance_count": governance_count,
            "statecraft_count": statecraft_count,
            "duplicate_registration_count": duplicate_count,
            "window_binding_count": 0,
            "rule_evidence_unit_count": 0,
            "score_contribution_count": 0,
            "formal_write_count": 0,
        },
        "conflicts": conflicts,
        "outcomes": outcomes,
    }
    report["registry_fingerprint"] = _digest(report)
    return report


def build_ruler_outcome_bindings(
    source_pack: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract only post-registration ruler-window and talent projections."""

    registration_by_key = {
        (str(row["outcome_kind"]), str(row["independent_key"])): row
        for row in registry["outcomes"]
    }
    bindings = []
    current_ruler_ref = str(source_pack["ruler_ref"])
    for cluster in (source_pack.get("outcome_registry") or {}).get("clusters") or ():
        registration = registration_by_key.get(
            (str(cluster["outcome_kind"]), str(cluster["independent_key"]))
        )
        if registration is None:
            raise ValueError(f"成果未进入总登记: {cluster['outcome_ref']}")
        if cluster["outcome_kind"] == "governance" and not any(
            member.get("actor_kind") == "ruler"
            and str(member.get("actor_ref") or "") == current_ruler_ref
            for member in cluster.get("members") or ()
        ):
            continue
        binding = {
            "registration_ref": registration["registration_ref"],
            "outcome_ref": cluster["outcome_ref"],
            "ruler_window_status": cluster["ruler_window_status"],
            "ruler_actor_refs": sorted(
                str(member["actor_ref"])
                for member in cluster["members"]
                if member["actor_kind"] == "ruler"
            ),
            "campaign_talent_credits": {
                str(member["actor_ref"]): member["talent_credit"]
                for member in cluster["members"]
                if cluster["outcome_kind"] == "campaign"
            },
        }
        if "ruler_context_refs" in cluster:
            binding["ruler_context_refs"] = list(
                cluster.get("ruler_context_refs") or ()
            )
        bindings.append(binding)
    existing_registration_refs = {
        str(binding["registration_ref"]) for binding in bindings
    }
    for registration in registry["outcomes"]:
        registration_ref = str(registration["registration_ref"])
        if registration_ref in existing_registration_refs:
            continue
        if registration["outcome_kind"] != "governance":
            continue
        if not any(
            str(member["actor_ref"]) == current_ruler_ref
            for member in registration.get("members") or ()
        ):
            continue
        origin_refs = sorted(registration.get("origin_outcome_refs") or ())
        if not origin_refs:
            raise ValueError(f"共享治理成果缺少来源 outcome_ref: {registration_ref}")
        bindings.append(
            {
                "registration_ref": registration_ref,
                "outcome_ref": origin_refs[0],
                "ruler_window_status": "within_window",
                "ruler_actor_refs": [current_ruler_ref],
                "campaign_talent_credits": {},
            }
        )
    bindings_by_ref = {
        str(binding["registration_ref"]): binding for binding in bindings
    }
    pending = list(bindings)
    window_status_priority = {
        "unresolved": 0,
        "outside_window": 1,
        "leadership_formation": 2,
        "within_window": 3,
    }
    outcomes_by_ref = {
        str(row["registration_ref"]): row for row in registry["outcomes"]
    }
    while pending:
        child_binding = pending.pop()
        child_registration = outcomes_by_ref[str(child_binding["registration_ref"])]
        parent_ref = child_registration.get("parent_registration_ref")
        if not parent_ref:
            continue
        parent_ref = str(parent_ref)
        existing_parent = bindings_by_ref.get(parent_ref)
        if existing_parent is not None:
            if existing_parent.get("context_only_ancestor") and (
                window_status_priority[str(child_binding["ruler_window_status"])]
                > window_status_priority[str(existing_parent["ruler_window_status"])]
            ):
                existing_parent["ruler_window_status"] = child_binding[
                    "ruler_window_status"
                ]
            continue
        parent_registration = outcomes_by_ref.get(parent_ref)
        if parent_registration is None:
            raise ValueError(
                f"成果总登记缺少窗口绑定所需祖先: {child_binding['registration_ref']}"
            )
        origin_refs = sorted(parent_registration.get("origin_outcome_refs") or ())
        if not origin_refs:
            raise ValueError(f"成果祖先缺少来源 outcome_ref: {parent_ref}")
        parent_binding = {
            "registration_ref": parent_ref,
            "outcome_ref": origin_refs[0],
            "ruler_window_status": child_binding["ruler_window_status"],
            "ruler_actor_refs": [],
            "campaign_talent_credits": {},
            "context_only_ancestor": True,
        }
        bindings_by_ref[parent_ref] = parent_binding
        pending.append(parent_binding)
    bindings = sorted(
        bindings_by_ref.values(), key=lambda row: str(row["registration_ref"])
    )
    report = {
        "schema_version": "ruler-outcome-binding-v2",
        "status": "current_shadow_binding",
        "ruler_ref": source_pack["ruler_ref"],
        "projected_registry_status": source_pack["outcome_registry"]["status"],
        "source_pack_sha256": source_pack["source_pack_sha256"],
        "registry_fingerprint": registry["registry_fingerprint"],
        "binding_count": len(bindings),
        "formal_write_count": 0,
        "bindings": bindings,
    }
    report["binding_fingerprint"] = _digest(report)
    return report


def materialize_ruler_outcome_registry(
    registry: Mapping[str, Any],
    binding_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Join the accepted outcome layer with one ruler projection for consumers."""

    if binding_report.get("registry_fingerprint") != registry.get(
        "registry_fingerprint"
    ):
        raise ValueError("皇帝窗口绑定与成果总登记版本不一致")
    outcomes_by_ref = {
        str(row["registration_ref"]): row for row in registry["outcomes"]
    }
    bindings_by_registration = {
        str(row["registration_ref"]): row for row in binding_report["bindings"]
    }
    outcome_ref_by_registration = {
        registration_ref: str(binding["outcome_ref"])
        for registration_ref, binding in bindings_by_registration.items()
    }
    clusters = []
    for registration_ref, binding in bindings_by_registration.items():
        registered = outcomes_by_ref.get(registration_ref)
        if registered is None:
            raise ValueError(f"窗口绑定引用未知成果: {registration_ref}")
        cluster = {
            key: json.loads(json.dumps(value, ensure_ascii=False))
            for key, value in registered.items()
            if key
            not in {
                "registration_ref",
                "registration_fingerprint",
                "event_level",
                "origin_outcome_refs",
                "parent_registration_ref",
            }
        }
        cluster["outcome_ref"] = binding["outcome_ref"]
        cluster["ruler_window_status"] = binding["ruler_window_status"]
        if "ruler_context_refs" in binding:
            cluster["ruler_context_refs"] = list(
                binding.get("ruler_context_refs") or ()
            )
        event_level = str(registered["event_level"])
        if event_level == "war_terminal":
            cluster["settlement_scope"] = "war_terminal_context"
        elif event_level == "campaign_group":
            cluster["settlement_scope"] = "ruler_campaign_parent"
            if registered.get("parent_registration_ref"):
                parent_registration_ref = str(
                    registered["parent_registration_ref"]
                )
                parent_outcome_ref = outcome_ref_by_registration.get(
                    parent_registration_ref
                )
                if parent_outcome_ref is None:
                    raise ValueError(
                        f"窗口绑定缺少战役群战争终局父级: {registration_ref}"
                    )
                cluster["parent_outcome_ref"] = parent_outcome_ref
        elif event_level == "person_command_result":
            cluster["settlement_scope"] = "person_campaign_subresult"
            parent_registration_ref = str(registered["parent_registration_ref"])
            parent_outcome_ref = outcome_ref_by_registration.get(parent_registration_ref)
            if parent_outcome_ref is None:
                raise ValueError(f"窗口绑定缺少人物子战役父级: {registration_ref}")
            cluster["parent_outcome_ref"] = parent_outcome_ref
        elif event_level == "macro_public_result":
            cluster["settlement_scope"] = "reign_macro_outcome"
        elif event_level == "person_statecraft_result":
            cluster["settlement_scope"] = "person_statecraft_result"
        else:
            cluster["settlement_scope"] = (
                "person_governance_result"
                if binding["ruler_window_status"] == "outside_window"
                else "governance_result"
            )
        talent_credits = binding.get("campaign_talent_credits") or {}
        ruler_actor_refs = {
            str(value) for value in binding.get("ruler_actor_refs") or ()
        }
        members = []
        for registered_member in registered["members"]:
            member = dict(registered_member)
            sovereign_relation = member.pop("sovereign_relation", None)
            actor_ref = str(member["actor_ref"])
            member["actor_kind"] = (
                "ruler" if actor_ref in ruler_actor_refs else "person"
            )
            if registered["outcome_kind"] == "campaign":
                if actor_ref not in talent_credits:
                    raise ValueError(
                        f"战役窗口绑定缺少人物信用: {registration_ref}/{actor_ref}"
                    )
                member["talent_credit"] = talent_credits[actor_ref]
                if sovereign_relation is not None:
                    member["ruler_campaign_relation"] = sovereign_relation
            members.append(member)
        cluster["members"] = members
        cluster["semantic_fingerprint"] = cluster_semantic_fingerprint(cluster)
        clusters.append(cluster)
    clusters.sort(key=lambda row: str(row["outcome_ref"]))
    return {
        "schema_version": CLUSTER_SCHEMA_VERSION,
        "status": binding_report["projected_registry_status"],
        "clusters": clusters,
    }


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    replacement = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    replacement.write_text(content, encoding="utf-8", newline="\n")
    os.replace(replacement, path)


def _partition_outcome_registry(
    registry: Mapping[str, Any],
    *,
    partition_token: str,
    outcome_partitions: Mapping[str, str],
    source_pack_refs: Sequence[str],
) -> dict[str, Any]:
    outcomes = [
        json.loads(json.dumps(row, ensure_ascii=False))
        for row in registry["outcomes"]
        if outcome_partitions[str(row["registration_ref"])] == partition_token
    ]
    declarations = dict(registry["declarations"])
    declarations.update(
        {
            "source_pack_count": len(source_pack_refs),
            "source_pack_refs": sorted(source_pack_refs),
            "outcome_count": len(outcomes),
            "campaign_count": sum(
                row["outcome_kind"] == "campaign" for row in outcomes
            ),
            "governance_count": sum(
                row["outcome_kind"] == "governance" for row in outcomes
            ),
            "statecraft_count": sum(
                row["outcome_kind"] == "statecraft" for row in outcomes
            ),
            "duplicate_registration_count": sum(
                max(0, len(row.get("origin_outcome_refs") or ()) - 1)
                for row in outcomes
            ),
        }
    )
    report = {
        "schema_version": registry["schema_version"],
        "status": registry["status"],
        "registry_partition": partition_token,
        "declarations": declarations,
        "conflicts": [
            dict(row)
            for row in registry.get("conflicts") or ()
            if outcome_partitions.get(
                _registration_ref(
                    str(row["outcome_kind"]), str(row["independent_key"])
                )
            )
            == partition_token
        ],
        "outcomes": outcomes,
    }
    report["registry_fingerprint"] = _digest(report)
    return report


def write_dynasty_outcome_partition(
    *,
    outcome_pack: Mapping[str, Any],
    dynasty_token: str,
    output_root: Path,
) -> dict[str, Any]:
    """Write one dynasty governance partition without a ruler source pack."""

    token = str(dynasty_token).strip()
    if not token or any(value in token for value in ("/", "\\", "..")):
        raise ValueError("朝代治理 token 含非法路径字符")
    registry = build_unbound_historical_outcome_registry([outcome_pack])
    outcome_partitions = {
        str(row["registration_ref"]): token for row in registry["outcomes"]
    }
    partition = _partition_outcome_registry(
        registry,
        partition_token=token,
        outcome_partitions=outcome_partitions,
        source_pack_refs=[str(outcome_pack["source_pack_sha256"])],
    )
    partition_root = output_root.resolve() / token
    json_path = partition_root / "current.json"
    markdown_path = partition_root / "current.md"
    _atomic_text(
        json_path,
        json.dumps(partition, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_text(
        markdown_path,
        render_unbound_historical_outcome_registry_markdown(partition),
    )
    return {
        "registry": partition,
        "current_json": str(json_path),
        "current_markdown": str(markdown_path),
    }


def _partition_profile_registry(
    registry: Mapping[str, Any],
    *,
    partition_token: str,
    profile_partitions: Mapping[str, str],
    outcome_registry_fingerprint: str,
    source_pack_refs: Sequence[str],
) -> dict[str, Any]:
    profiles = [
        json.loads(json.dumps(row, ensure_ascii=False))
        for row in registry["profiles"]
        if profile_partitions[str(row["person_ref"])] == partition_token
    ]
    declarations = dict(registry["declarations"])
    declarations.update(
        {
            "profile_count": len(profiles),
            "complete_profile_count": sum(
                not profile["coverage_gaps"] for profile in profiles
            ),
            "open_profile_count": sum(
                bool(profile["coverage_gaps"]) for profile in profiles
            ),
            "outcome_registry_fingerprint": outcome_registry_fingerprint,
            "source_pack_count": len(source_pack_refs),
            "source_pack_refs": sorted(source_pack_refs),
        }
    )
    report = {
        "schema_version": registry["schema_version"],
        "status": registry["status"],
        "registry_partition": partition_token,
        "profiles": profiles,
        "declarations": declarations,
    }
    report["registry_fingerprint"] = _digest(report)
    return report


def _dynasty_token_lookup(project: Mapping[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    dynasties = (project.get("dynasty_governance_catalog") or {}).get(
        "dynasties"
    ) or {}
    for dynasty_name, dynasty in dynasties.items():
        token = str(dynasty["dynasty_token"])
        for label in (str(dynasty_name), *(dynasty.get("aliases") or ())):
            existing = lookup.setdefault(str(label), token)
            if existing != token:
                raise ValueError(f"朝代别名映射冲突: {label}")
    return lookup


def _profile_partition_map(
    *,
    workspace_root: Path,
    project: Mapping[str, Any],
    profile_registry: Mapping[str, Any],
    partitioned_packs: Sequence[tuple[str, Mapping[str, Any]]],
) -> dict[str, str]:
    identity_path = workspace_root / "config/historical-entity-identities.yml"
    identity_registry = yaml.safe_load(identity_path.read_text(encoding="utf-8"))
    dynasty_tokens = _dynasty_token_lookup(project)
    identity_partitions = {}
    for entity in identity_registry.get("entities") or ():
        dynasty = str(entity.get("dynasty") or "")
        token = dynasty_tokens.get(dynasty)
        if token:
            identity_partitions[str(entity["person_ref"])] = token
    observed: dict[str, set[str]] = {}
    for token, source_pack in partitioned_packs:
        for member in source_pack.get("members") or ():
            observed.setdefault(str(member["person_ref"]), set()).add(token)
        for cluster in (source_pack.get("outcome_registry") or {}).get(
            "clusters"
        ) or ():
            for member in cluster.get("members") or ():
                observed.setdefault(str(member["actor_ref"]), set()).add(token)
    result = {}
    for profile in profile_registry["profiles"]:
        person_ref = str(profile["person_ref"])
        token = identity_partitions.get(person_ref)
        if token is None:
            candidates = observed.get(person_ref) or set()
            if len(candidates) != 1:
                raise ValueError(
                    f"人物画像缺少唯一朝代分区: {profile['person']} / "
                    f"{sorted(candidates)}"
                )
            token = next(iter(candidates))
        result[person_ref] = token
    return result


def write_current_outcome_layers(
    workspace_root: Path,
    *,
    include_rulers: Sequence[str] = (),
    dynasty_outcome_packs: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Publish shared outcomes and profiles first, then ruler bindings."""

    workspace_root = workspace_root.resolve()
    explicitly_included = {str(value) for value in include_rulers}
    project = yaml.safe_load(
        (workspace_root / "config/project.yml").read_text(encoding="utf-8")
    )
    configured = (project.get("i5b_current_value") or {}).get("rulers") or {}
    configured_packs = []
    for ruler_name, ruler_config in configured.items():
        if not isinstance(ruler_config, Mapping):
            continue
        source_path = workspace_root / str(ruler_config["source_pack"])
        source_pack = json.loads(source_path.read_text(encoding="utf-8"))
        projection_gate = source_pack.get("profile_projection_gate") or {}
        if (
            projection_gate.get("freeze_allowed") is not True
            and str(ruler_name) not in explicitly_included
        ):
            continue
        configured_packs.append((str(ruler_name), ruler_config, source_pack))
    partitioned_packs = [
        (
            str(ruler_config["dynasty_governance_material_token"]),
            source_pack,
        )
        for _ruler_name, ruler_config, source_pack in configured_packs
    ]
    for token, source_pack in (dynasty_outcome_packs or {}).items():
        if source_pack.get("pack_scope") != "dynasty_governance":
            raise ValueError(f"{token} 朝代治理成果包 scope 不匹配")
        if str(source_pack.get("dynasty_token") or "") != str(token):
            raise ValueError(f"{token} 朝代治理成果包 token 不匹配")
        partitioned_packs.append((str(token), source_pack))
    if not partitioned_packs:
        raise ValueError("当前配置没有可汇总的成果 source pack")
    registry = build_unbound_historical_outcome_registry(
        [row[1] for row in partitioned_packs]
    )
    registry_config = project.get("historical_outcome_registry") or {}
    output_json = workspace_root / str(
        registry_config.get("current_json")
        or "eval/historical_outcome_registry/current.json"
    )
    output_markdown = workspace_root / str(
        registry_config.get("current_markdown")
        or "eval/historical_outcome_registry/current.md"
    )
    profile_registry = build_historical_person_profile_registry(
        registry, [row[1] for row in partitioned_packs]
    )
    profile_config = project.get("historical_person_profile_registry") or {}
    profile_json = workspace_root / str(
        profile_config.get("current_json")
        or "eval/historical_person_profiles/current.json"
    )
    profile_markdown = workspace_root / str(
        profile_config.get("current_markdown")
        or "eval/historical_person_profiles/current.md"
    )
    origin_partitions: dict[str, set[str]] = {}
    source_refs_by_partition: dict[str, list[str]] = {}
    for token, source_pack in partitioned_packs:
        source_ref = str(source_pack["source_pack_sha256"])
        source_refs_by_partition.setdefault(token, []).append(source_ref)
        for cluster in (source_pack.get("outcome_registry") or {}).get(
            "clusters"
        ) or ():
            origin_partitions.setdefault(str(cluster["outcome_ref"]), set()).add(
                token
            )
    owner_overrides = registry_config.get(
        "cross_dynasty_outcome_partition_owners"
    ) or {}
    outcome_partitions = {}
    for outcome in registry["outcomes"]:
        candidates = {
            token
            for origin_ref in outcome.get("origin_outcome_refs") or ()
            for token in origin_partitions.get(str(origin_ref), set())
        }
        override = owner_overrides.get(str(outcome["independent_key"]))
        if override:
            candidates = {str(override)}
        if len(candidates) != 1:
            raise ValueError(
                f"公共成果缺少唯一朝代分区: {outcome['canonical_label']} / "
                f"{sorted(candidates)}"
            )
        outcome_partitions[str(outcome["registration_ref"])] = next(
            iter(candidates)
        )
    profile_partitions = _profile_partition_map(
        workspace_root=workspace_root,
        project=project,
        profile_registry=profile_registry,
        partitioned_packs=partitioned_packs,
    )
    partition_tokens = sorted(
        {
            *outcome_partitions.values(),
            *profile_partitions.values(),
        }
    )
    outcome_partition_root = workspace_root / str(
        registry_config.get("partition_root")
        or "eval/historical_outcome_registry"
    )
    profile_partition_root = workspace_root / str(
        profile_config.get("partition_root")
        or "eval/historical_person_profiles"
    )
    outcome_partitions_payload = {
        token: _partition_outcome_registry(
            registry,
            partition_token=token,
            outcome_partitions=outcome_partitions,
            source_pack_refs=source_refs_by_partition.get(token, ()),
        )
        for token in partition_tokens
    }
    merged_outcomes = sorted(
        (
            outcome
            for partition in outcome_partitions_payload.values()
            for outcome in partition["outcomes"]
        ),
        key=lambda row: (
            {"campaign": 0, "governance": 1, "statecraft": 2}[
                row["outcome_kind"]
            ],
            str((row.get("period") or {}).get("start") or ""),
            str(row["canonical_label"]),
        ),
    )
    if merged_outcomes != registry["outcomes"]:
        raise ValueError("朝代成果分区无法确定性无损合并为全局 current")
    profile_partitions_payload = {
        token: _partition_profile_registry(
            profile_registry,
            partition_token=token,
            profile_partitions=profile_partitions,
            outcome_registry_fingerprint=outcome_partitions_payload[token][
                "registry_fingerprint"
            ],
            source_pack_refs=source_refs_by_partition.get(token, ()),
        )
        for token in partition_tokens
    }
    merged_profiles = sorted(
        (
            profile
            for partition in profile_partitions_payload.values()
            for profile in partition["profiles"]
        ),
        key=lambda row: str(row["person"]),
    )
    if merged_profiles != profile_registry["profiles"]:
        raise ValueError("朝代人物画像分区无法确定性无损合并为全局 current")
    prepared_bindings = []
    for ruler_name, ruler_config, source_pack in configured_packs:
        binding = build_ruler_outcome_bindings(source_pack, registry)
        materialized = materialize_ruler_outcome_registry(registry, binding)
        direct_outcome_refs = {
            str(row["outcome_ref"])
            for row in binding["bindings"]
            if not row.get("context_only_ancestor")
        }
        direct_materialized = {
            **materialized,
            "clusters": [
                cluster
                for cluster in materialized["clusters"]
                if str(cluster["outcome_ref"]) in direct_outcome_refs
            ],
        }
        if not public_registry_matches_source_pack(
            direct_materialized,
            source_pack["outcome_registry"],
            ruler_ref=str(source_pack["ruler_ref"]),
        ):
            raise ValueError(f"{ruler_name} 窗口绑定无法无损还原当前成果投影")
        binding_path = ruler_config.get("outcome_binding")
        if not binding_path:
            raise ValueError(f"{ruler_name} 缺少 outcome_binding 配置")
        binding_output = workspace_root / str(binding_path)
        prepared_bindings.append((ruler_name, binding_output, binding))

    _atomic_text(
        output_json,
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_text(
        output_markdown,
        render_unbound_historical_outcome_registry_markdown(registry),
    )
    _atomic_text(
        profile_json,
        json.dumps(
            profile_registry, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n",
    )
    _atomic_text(
        profile_markdown,
        render_historical_person_profile_registry_markdown(profile_registry),
    )
    partition_paths = {}
    for token in partition_tokens:
        outcome_partition = outcome_partitions_payload[token]
        outcome_json = outcome_partition_root / token / "current.json"
        outcome_markdown = outcome_partition_root / token / "current.md"
        profile_partition = profile_partitions_payload[token]
        person_json = profile_partition_root / token / "current.json"
        person_markdown = profile_partition_root / token / "current.md"
        _atomic_text(
            outcome_json,
            json.dumps(
                outcome_partition, ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
        )
        _atomic_text(
            outcome_markdown,
            render_unbound_historical_outcome_registry_markdown(
                outcome_partition
            ),
        )
        _atomic_text(
            person_json,
            json.dumps(
                profile_partition, ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
        )
        _atomic_text(
            person_markdown,
            render_historical_person_profile_registry_markdown(
                profile_partition
            ),
        )
        partition_paths[token] = {
            "outcome_json": str(outcome_json),
            "outcome_markdown": str(outcome_markdown),
            "profile_json": str(person_json),
            "profile_markdown": str(person_markdown),
        }
    binding_paths = {}
    for ruler_name, binding_output, binding in prepared_bindings:
        _atomic_text(
            binding_output,
            json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        binding_paths[ruler_name] = str(binding_output)
    return {
        "registry": registry,
        "registry_json": str(output_json),
        "registry_markdown": str(output_markdown),
        "profile_registry": profile_registry,
        "profile_registry_json": str(profile_json),
        "profile_registry_markdown": str(profile_markdown),
        "partition_paths": partition_paths,
        "binding_paths": binding_paths,
        "included_rulers": sorted(row[0] for row in configured_packs),
    }


def _members_text(members: Sequence[Mapping[str, Any]]) -> str:
    values = []
    for member in members:
        relation = member.get("sovereign_relation")
        relation_parts = []
        if relation:
            relation_parts.append(f"统治者控制={_display_label(relation)}")
        if member.get("authorization_mode"):
            relation_parts.append(
                "授权方式="
                + {
                    "explicit": "正式",
                    "tacit": "默许",
                }[str(member["authorization_mode"])]
            )
        if member.get("control_extent"):
            relation_parts.append(
                "控制范围="
                + {
                    "partial": "局部",
                    "sustained": "持续",
                }[str(member["control_extent"])]
            )
        if member.get("obstruction_status") == "confirmed":
            relation_parts.append("存在明确阻挠")
        suffix = "；" + "；".join(relation_parts) if relation_parts else ""
        values.append(
            f"{member['actor_name']}（{_display_label(member['role_code'])}{suffix}；"
            f"{_display_text(member['contribution_scope'])}）"
        )
    return "、".join(values)


def _period_text(period: Mapping[str, Any]) -> str:
    start = str(period.get("start") or "")
    end = str(period.get("end") or "")
    return start if not end or end == start else f"{start}—{end}"


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_unbound_historical_outcome_registry_markdown(
    registry: Mapping[str, Any],
) -> str:
    declarations = registry["declarations"]
    lines = [
        "# 战役、治理与谋略成果总登记（未绑定皇帝窗口）",
        "",
        "> 本表只审成果本体。皇帝窗口、规则材料、人才信用和计分均未投影。",
        "",
        f"- 总成果：{declarations['outcome_count']}",
        f"- 战役：{declarations['campaign_count']}",
        f"- 治理：{declarations['governance_count']}",
        f"- 谋略：{declarations['statecraft_count']}",
        f"- 窗口绑定：{declarations['window_binding_count']}",
        f"- 规则材料：{declarations['rule_evidence_unit_count']}",
        f"- 计分贡献：{declarations['score_contribution_count']}",
        "",
    ]
    if registry.get("conflicts"):
        lines.extend(["## 待归并冲突", ""])
        for conflict in registry["conflicts"]:
            lines.append(
                f"- `{conflict['independent_key']}`：{conflict['reason']}"
            )
        lines.append("")

    campaigns = [
        row for row in registry["outcomes"] if row["outcome_kind"] == "campaign"
    ]
    lines.extend(
        [
            "## 战役登记",
            "",
            "| 登记号 | 战役成果 | 层级 | 时段 | 战前背景 | 失败利害 | 战略结果等级 | 作战难度 | 土地轴 | 对手轴 | 结果轴 | 战争成本 | 目标未完成 | 可归责失败 | 参与者责任 | 已实现结果 | 史源 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in campaigns:
        payload = row["payload"]
        failures = "、".join(
            f"{item.get('actor_name') or '外部因素'}:"
            f"{_display_label(item['responsibility'])}"
            f"(严重度={item['severity_index']}；{_display_text(item['basis'])})"
            for item in payload.get("attributable_failures") or ()
        ) or "无"
        operational_costs = "、".join(
            _display_text(item["basis"])
            for item in payload.get("operational_costs") or ()
        ) or "无"
        shortfalls = "、".join(
            _display_text(item["basis"])
            for item in payload.get("objective_shortfalls") or ()
        ) or "无"
        result = (
            f"{_display_label(payload['battle_result'])} / "
            f"{_display_label(payload['objective_completion'])}"
        )
        opponent = (
            f"{_display_label(payload['opponent_strategic_weight'])} / "
            f"{_display_label(payload['opponent_condition'])}"
        )
        lines.append(
            "| "
            + " | ".join(
                _escape(value)
                for value in (
                    row["registration_ref"],
                    row["canonical_label"],
                    _display_label(row["event_level"]),
                    _period_text(row["period"]),
                    _display_text(payload["prewar_context"]),
                    f"{_display_label(payload['strategic_stakes'])}；"
                    f"{_display_text(payload['failure_stakes'])}",
                    f"{payload['campaign_tier']} / "
                    f"{_display_label(payload['strategic_result_class'])}；"
                    f"{_display_text(payload['campaign_tier_basis'])}",
                    f"{payload['combat_difficulty']}；"
                    f"{_display_text(payload['combat_difficulty_basis'])}",
                    _display_label(payload["land_strategic_value"]),
                    opponent,
                    result,
                    operational_costs,
                    shortfalls,
                    failures,
                    _members_text(row["members"]),
                    _display_text(row["observable_result"]),
                    "、".join(row["source_refs"]),
                )
            )
            + " |"
        )

    governance = [
        row for row in registry["outcomes"] if row["outcome_kind"] == "governance"
    ]
    lines.extend(
        [
            "",
            "## 治理登记",
            "",
            "| 登记号 | 治理成果 | 类型 | 时段 | 运行状态 | 价值方向 | 相对历史基线与四轴进步 | 规模 | 因果归责 | 参与者责任 | 已实现结果 | 限制 | 史源 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in governance:
        payload = row["payload"]
        scale = row["scale"]
        value_judgment = payload["value_judgment"]
        lines.append(
            "| "
            + " | ".join(
                _escape(value)
                for value in (
                    row["registration_ref"],
                    row["canonical_label"],
                    _display_label(row["event_level"]),
                    _period_text(row["period"]),
                    _display_label(row["result_status"]),
                    _display_label(value_judgment["overall_direction"]),
                    (
                        f"总体强度={_display_label(value_judgment['overall_magnitude'])}；"
                        + "；".join(
                            f"{_display_label(axis_name)}="
                            f"{_display_label(axis['direction'])}/"
                            f"{_display_label(axis['magnitude'])}"
                            for axis_name, axis in value_judgment["axes"].items()
                        )
                        + f"；{_display_text(value_judgment['basis'])}"
                    ),
                    f"{_display_label(scale['level'])} / "
                    f"{_display_label(scale['consequence_basis'])}；"
                    f"{_display_text(scale['reason'])}",
                    _display_label(payload["causal_attribution_status"]),
                    _members_text(row["members"]),
                    _display_text(row["observable_result"]),
                    "；".join(_display_text(value) for value in row["limitations"])
                    or "无",
                    "、".join(row["source_refs"]),
                )
            )
            + " |"
        )
    statecraft = [
        row for row in registry["outcomes"] if row["outcome_kind"] == "statecraft"
    ]
    lines.extend(
        [
            "",
            "## 人物谋略登记",
            "",
            "> 只供人物画像消费，不进入皇帝治理投影；未实施建议、纯夺权和只有手段成功而无独立战略结果者不登记。",
            "",
            "| 登记号 | 谋略成果 | 时段 | 规模 | 参与者责任 | 已实现结果 | 限制 | 史源 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in statecraft:
        scale = row["scale"]
        lines.append(
            "| "
            + " | ".join(
                _escape(value)
                for value in (
                    row["registration_ref"],
                    row["canonical_label"],
                    _period_text(row["period"]),
                    f"{_display_label(scale['level'])} / "
                    f"{_display_label(scale['consequence_basis'])}；"
                    f"{_display_text(scale['reason'])}",
                    _members_text(row["members"]),
                    _display_text(row["observable_result"]),
                    "；".join(_display_text(value) for value in row["limitations"])
                    or "无",
                    "、".join(row["source_refs"]),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
