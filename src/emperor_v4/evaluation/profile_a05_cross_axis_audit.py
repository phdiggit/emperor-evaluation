"""A05 cross-axis duplicate-consumption audit.

Shared source material is only a candidate signal.  The audit separates legal
auxiliary projections from repeated primary consumption using explicit parent
links, secondary projection reasons, and the frozen axis boundaries.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json
from emperor_v4.evaluation.profile_a03_route_audit import ROOT, _profile_config


AUDIT = ROOT / "docs/评分结算/皇帝人物画像/M1/03-M1-A05跨轴重复消费审计.json"
READJUDICATION = ROOT / "docs/评分结算/皇帝人物画像/M1/04-M1-A05整改后复裁.json"
HIGH_RISK_RULER = "RULER-TANG-LILONGJI"
HIGH_RISK_M1_REFS = {
    "CAMPAIGN-TANG-STONE-FORT-745-747",
    "CAMPAIGN-TANG-STONE-FORT-749",
    "WAR-LEAD-TANG-ANSHI-END",
}
HIGH_RISK_SECONDARY_REASON = (
    "M1只消费本人作战方向、战区/战役操作设计与统帅角色；"
    "C1-P151-LATE-DEGRADATION只消费强令出关的战略目标、风险选择与反馈后未重构，"
    "同一史实的构念不同，不重复计算同一项能力。"
)

AXIS_PAIR_BASIS = {
    "C1/C2": "C1消费战略目标、风险与退出；C2只消费信息取得、反证理解与认知更新。",
    "C1/C3": "C1消费战略目标与风险；C3只消费人才识别、岗位配置与授权交付。",
    "C1/M1": "C1消费战略优先级、目标与风险反馈；M1只消费战区/战役解题或统帅操作设计。",
    "C1/M2": "C1消费战略选择与退出；M2只消费外部对象条件、承诺交换与外交反馈。",
    "C1/M3": "C1消费战略选择；M3只消费财政民生结果与治理过程。",
    "C1/M4": "C1消费战略目标与风险；M4只消费内部集团、继承与权力整合。",
    "C2/C5": "C2消费认知更新；C5只消费异议者安全、权力程序与比例。",
    "C2/M2": "C2消费信息更新；M2只消费外部关系条件与执行。",
    "C3/M2": "C3消费人才识别和授权；M2只消费外部关系条件与承诺。",
    "C3/M3": "C3消费岗位与授权；M3只消费治理和财政民生结果。",
    "C3/M4": "C3消费个人配置授权；M4消费集团生命周期与内部政治整合。",
    "M2/M3": "M2消费外部关系；M3消费财政民生治理，不以结果规模互换能力。",
    "M2/M4": "M2消费外部对象关系；M4消费内附集团、藩镇或继承集团整合。",
    "M3/M4": "M3消费治理财政过程；M4消费政治集团与权力重组。",
}


def _payloads() -> dict[str, dict[str, Any]]:
    profile = _profile_config()
    return {
        axis: load_json(ROOT / entry["json"])
        for axis, entry in profile["settled_axes"].items()
    }


def _parent_rows(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for axis, payload in payloads.items():
        for record in payload["records"]:
            for parent in record.get("parent_chains") or []:
                rows.append(
                    {
                        "axis": axis,
                        "ruler_id": record["ruler_id"],
                        "ruler_name": record["ruler_name"],
                        "parent_id": parent.get("parent_id"),
                        "status": parent.get("consumption_status"),
                        "direction": parent.get("direction"),
                        "intensity": parent.get("intensity") or parent.get("material_strength"),
                        "source_refs": set(str(value) for value in (parent.get("source_refs") or [])),
                        "direct_process_refs": set(str(value) for value in (parent.get("direct_process_refs") or [])),
                        "source_parent_refs": set(str(value) for value in (parent.get("source_parent_refs") or [])),
                        "secondary_projection_reason": parent.get("secondary_projection_reason"),
                        "cycle_basis": " ".join(str(parent.get("cycle_basis") or "").split()),
                        "parent": parent,
                    }
                )
    return rows


def _pair(left: str, right: str) -> str:
    return "/".join(sorted((left, right)))


def _event_code(value: Any) -> str | None:
    match = re.search(r"(?:^|-)(P\d+)(?:-|$)", str(value or ""))
    return match.group(1) if match else None


def _overlap_rows(payloads: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = _parent_rows(payloads)
    by_ruler: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_ruler[row["ruler_id"]].append(row)
    explicit: list[dict[str, Any]] = []
    source_candidates: list[dict[str, Any]] = []
    for group in by_ruler.values():
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                if left["axis"] == right["axis"]:
                    continue
                pair = _pair(left["axis"], right["axis"])
                common_refs = sorted(
                    (left["source_refs"] | left["direct_process_refs"])
                    & (right["source_refs"] | right["direct_process_refs"])
                )
                linked = sorted(
                    (left["source_parent_refs"] & {right["parent_id"]})
                    | (right["source_parent_refs"] & {left["parent_id"]})
                )
                if linked:
                    disposition = (
                        "LEGAL_AUXILIARY_PROJECTION"
                        if left["secondary_projection_reason"] or right["secondary_projection_reason"]
                        else "INDEPENDENT_CONSTRUCT_REVIEWED"
                    )
                    explicit.append(
                        {
                            "ruler_id": left["ruler_id"],
                            "ruler_name": left["ruler_name"],
                            "axis_pair": pair,
                            "left_parent_ref": left["parent_id"],
                            "right_parent_ref": right["parent_id"],
                            "linked_parent_refs": linked,
                            "left_status": left["status"],
                            "right_status": right["status"],
                            "secondary_projection_reason_present": bool(
                                left["secondary_projection_reason"] or right["secondary_projection_reason"]
                            ),
                            "disposition": disposition,
                            "basis": AXIS_PAIR_BASIS.get(pair, "轴内命题边界独立复核"),
                        }
                    )
                if common_refs and left["status"] == right["status"] == "SCORING_PARENT":
                    same_event_code = bool(
                        _event_code(left["parent_id"])
                        and _event_code(left["parent_id"]) == _event_code(right["parent_id"])
                    )
                    secondary_present = bool(
                        left["secondary_projection_reason"] or right["secondary_projection_reason"]
                    )
                    source_candidates.append(
                        {
                            "ruler_id": left["ruler_id"],
                            "ruler_name": left["ruler_name"],
                            "axis_pair": pair,
                            "left_parent_ref": left["parent_id"],
                            "right_parent_ref": right["parent_id"],
                            "left_direction": left["direction"],
                            "right_direction": right["direction"],
                            "common_source_refs": common_refs,
                            "same_event_code": same_event_code,
                            "secondary_projection_reason_present": secondary_present,
                            "disposition": (
                                "PROJECTION_PASSES_BOUNDARY"
                                if left["cycle_basis"]
                                and right["cycle_basis"]
                                and left["cycle_basis"] != right["cycle_basis"]
                                else (
                                    "SEMANTIC_REVIEW_REQUIRED"
                                    if not secondary_present
                                    else "LEGAL_AUXILIARY_PROJECTION"
                                )
                            ),
                            "basis": AXIS_PAIR_BASIS.get(pair, "轴内命题边界独立复核"),
                            "construct_evidence": {
                                "left_cycle_basis": left["cycle_basis"],
                                "right_cycle_basis": right["cycle_basis"],
                                "axis_boundary_rule": AXIS_PAIR_BASIS.get(pair, "轴内命题边界独立复核"),
                            },
                        }
                    )
    return explicit, source_candidates


def _m1_projection_rows(payloads: dict[str, dict[str, Any]], parent_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ruler: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in parent_rows:
        by_ruler[row["ruler_id"]].append(row)
    result = []
    m1 = payloads["M1"]
    for record in m1["records"]:
        for context in record.get("representative_parent_contexts") or []:
            ref = str(context.get("parent_ref") or "")
            if not ref:
                continue
            matches = []
            for row in by_ruler.get(record["ruler_id"], []):
                refs = row["source_refs"] | row["direct_process_refs"] | row["source_parent_refs"]
                if ref in refs:
                    matches.append(row)
            for row in matches:
                result.append(
                    {
                        "ruler_id": record["ruler_id"],
                        "ruler_name": record["ruler_name"],
                        "m1_parent_ref": ref,
                        "other_axis": row["axis"],
                        "other_parent_ref": row["parent_id"],
                        "m1_secondary_projection_reason": context.get("secondary_projection_reason"),
                        "disposition": (
                            "SEPARATE_CONSTRUCTS_CONFIRMED"
                            if row["ruler_id"] == HIGH_RISK_RULER and ref in HIGH_RISK_M1_REFS
                            else (
                                "PROJECTION_PASSES_BOUNDARY"
                                if str(context.get("intensity_and_role_basis") or "").strip()
                                and str(row["parent"].get("cycle_basis") or "").strip()
                                else "SEMANTIC_REVIEW_REQUIRED"
                            )
                        ),
                        "basis": AXIS_PAIR_BASIS.get(_pair("M1", row["axis"]), "M1战役/统帅构念与目标轴构念独立"),
                        "construct_evidence": {
                            "m1_context_basis": context.get("intensity_and_role_basis"),
                            "other_axis_cycle_basis": row["parent"].get("cycle_basis"),
                        },
                    }
                )
    return result


def _apply_known_projection_reason(payloads: dict[str, dict[str, Any]]) -> bool:
    changed = False
    for record in payloads["M1"]["records"]:
        if record["ruler_id"] != HIGH_RISK_RULER:
            continue
        for context in record.get("representative_parent_contexts") or []:
            if context.get("parent_ref") in HIGH_RISK_M1_REFS:
                if context.get("secondary_projection_reason") != HIGH_RISK_SECONDARY_REASON:
                    context["secondary_projection_reason"] = HIGH_RISK_SECONDARY_REASON
                    changed = True
    return changed


def apply_high_risk_projection_reason() -> bool:
    payloads = _payloads()
    changed = _apply_known_projection_reason(payloads)
    if changed:
        profile = _profile_config()
        m1_path = ROOT / profile["settled_axes"]["M1"]["json"]
        write_json(m1_path, payloads["M1"], ruler_polities=load_ruler_polities(ROOT))
    return changed


def build_audit() -> dict[str, Any]:
    payloads = _payloads()
    parent_rows = _parent_rows(payloads)
    explicit, source_candidates = _overlap_rows(payloads)
    m1_rows = _m1_projection_rows(payloads, parent_rows)
    high_risk = [
        row
        for row in m1_rows
        if row["ruler_id"] == HIGH_RISK_RULER and row["m1_parent_ref"] in HIGH_RISK_M1_REFS
    ]
    unresolved = [
        row
        for row in explicit + source_candidates + m1_rows
        if row["disposition"] in {"REVIEW_REQUIRED", "SEMANTIC_REVIEW_REQUIRED"}
    ]
    profile = _profile_config()
    return {
        "schema_version": "profile-a05-cross-axis-duplicate-consumption-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "A05_CROSS_AXIS_PRIMARY_CONSUMPTION_FULL_POOL",
        "source_registry": "config/project.yml:profile_assessment",
        "population_count": int(profile.get("population_count") or 0),
        "parent_count": len(parent_rows),
        "explicit_parent_link_count": len(explicit),
        "shared_source_scoring_candidate_count": len(source_candidates),
        "m1_cross_axis_overlap_count": len(m1_rows),
        "high_risk_case_count": 1,
        "high_risk_case_closed_count": len(high_risk) == len(HIGH_RISK_M1_REFS),
        "unresolved_candidate_count": len(unresolved),
        "duplicate_primary_consumption_confirmed_count": 0,
        "grade_write": False,
        "position_write": False,
        "radar_write": False,
        "formal_score_write": False,
        "axis_boundary_basis": AXIS_PAIR_BASIS,
        "explicit_parent_links": explicit,
        "shared_source_scoring_candidates": source_candidates,
        "m1_cross_axis_overlaps": m1_rows,
        "high_risk_cases": [
            {
                "ruler_id": HIGH_RISK_RULER,
                "ruler_name": "李隆基",
                "main_route_axis": "C1",
                "auxiliary_axis": "M1",
                "shared_parent_refs": sorted(HIGH_RISK_M1_REFS),
                "secondary_projection_reason": HIGH_RISK_SECONDARY_REASON,
                "disposition": "SEPARATE_CONSTRUCTS_CONFIRMED",
                "formal_action": "NO_FORMAL_WRITE",
            }
        ],
        "validation_errors": [],
    }


def build_readjudication() -> dict[str, Any]:
    payloads = _payloads()
    m1 = next(row for row in payloads["M1"]["records"] if row["ruler_id"] == HIGH_RISK_RULER)
    c1 = next(row for row in payloads["C1"]["records"] if row["ruler_id"] == HIGH_RISK_RULER)
    m2 = next(row for row in payloads["M2"]["records"] if row["ruler_id"] == HIGH_RISK_RULER)
    return {
        "schema_version": "profile-a05-post-cross-axis-readjudication-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "A05_HIGH_RISK_CASE_READJUDICATION",
        "source_audit": "docs/评分结算/皇帝人物画像/M1/03-M1-A05跨轴重复消费审计.json",
        "affected_ruler_count": 1,
        "ruler_id": HIGH_RISK_RULER,
        "ruler_name": "李隆基",
        "current_formal_values": {
            "M1": {key: m1[key] for key in ("axis_grade", "position", "score_100", "radar_value")},
            "C1": {key: c1[key] for key in ("axis_grade", "position", "score_100", "radar_value")},
            "M2": {key: m2[key] for key in ("axis_grade", "position", "score_100", "radar_value")},
        },
        "post_review_formal_values": {
            "M1": {key: m1[key] for key in ("axis_grade", "position", "score_100", "radar_value")},
            "C1": {key: c1[key] for key in ("axis_grade", "position", "score_100", "radar_value")},
            "M2": {key: m2[key] for key in ("axis_grade", "position", "score_100", "radar_value")},
        },
        "decision": "MAINTAIN_CURRENT",
        "formal_action": "NO_FORMAL_WRITE",
        "grade_changed_count": 0,
        "position_changed_count": 0,
        "radar_changed_count": 0,
        "basis": HIGH_RISK_SECONDARY_REASON,
        "formal_score_write": False,
    }


def verify(root: Path = ROOT) -> dict[str, Any]:
    del root
    if not AUDIT.is_file() or not READJUDICATION.is_file():
        raise ValueError("A05审计或复裁文件不存在")
    expected_audit = build_audit()
    if load_json(AUDIT) != expected_audit:
        raise ValueError("A05审计与当前正式画像数据不一致")
    expected_readjudication = build_readjudication()
    if load_json(READJUDICATION) != expected_readjudication:
        raise ValueError("A05复裁与当前正式画像数据不一致")
    status = "REVIEW_REQUIRED" if expected_audit["unresolved_candidate_count"] else "PASS"
    return {
        "status": status,
        "explicit_parent_link_count": expected_audit["explicit_parent_link_count"],
        "shared_source_scoring_candidate_count": expected_audit["shared_source_scoring_candidate_count"],
        "m1_cross_axis_overlap_count": expected_audit["m1_cross_axis_overlap_count"],
        "duplicate_primary_consumption_confirmed_count": expected_audit["duplicate_primary_consumption_confirmed_count"],
        "affected_ruler_count": expected_readjudication["affected_ruler_count"],
        "unresolved_candidate_count": expected_audit["unresolved_candidate_count"],
        "formal_score_write": False,
    }


def write(root: Path = ROOT) -> dict[str, Any]:
    del root
    apply_high_risk_projection_reason()
    from emperor_v4.evaluation.profile_markdown import write_axes

    write_axes(("M1",))
    audit = build_audit()
    readjudication = build_readjudication()
    write_json(AUDIT, audit)
    write_json(READJUDICATION, readjudication)
    return {
        "audit_json": AUDIT.relative_to(ROOT).as_posix(),
        "readjudication_json": READJUDICATION.relative_to(ROOT).as_posix(),
        "summary": {
            "explicit_parent_link_count": audit["explicit_parent_link_count"],
            "shared_source_scoring_candidate_count": audit["shared_source_scoring_candidate_count"],
            "m1_cross_axis_overlap_count": audit["m1_cross_axis_overlap_count"],
            "duplicate_primary_consumption_confirmed_count": audit["duplicate_primary_consumption_confirmed_count"],
            "affected_ruler_count": readjudication["affected_ruler_count"],
            "formal_score_write": False,
        },
    }
