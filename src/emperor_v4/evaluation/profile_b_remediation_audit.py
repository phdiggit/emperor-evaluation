"""Current-state audit for the checklist's person-level remediation entries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.formal_json_store import load_json, write_json


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
AUDIT = PROFILE_ROOT / "交叉轴复核" / "11-B人物级整改现状审计.json"

B_ENTRIES: dict[str, tuple[str, ...]] = {
    "弘历": ("C1", "M2", "M4", "C2"),
    "李隆基": ("C1",),
    "李治": ("C1",),
    "刘义隆": ("C1",),
    "萧衍": ("C1",),
    "刘彧": ("C1",),
    "拓跋珪": ("C1",),
    "李渊": ("C1",),
    "武则天": ("M2",),
    "刘邦": ("M2",),
    "刘启": ("M2",),
    "姚苌": ("C1",),
    "李昪": ("C1",),
    "赵匡胤": ("C1",),
}

PENDING_EVIDENCE_DETAILS: dict[str, dict[str, Any]] = {
    "刘邦": {
        "disposition": "LOCAL_CANDIDATES_NOT_YET_FORMALIZED",
        "candidate_refs": [
            "docs/史料通读产物/唐以前编年/汉/卷010-通读总结.md#L21",
            "docs/史料通读产物/唐以前编年/汉/卷010-通读总结.md#L27",
            "docs/史料通读产物/唐以前编年/汉/卷010-通读总结.md#L32",
        ],
        "reason": "鸿沟和约后追击可形成外部承诺破坏候选；反间与说齐仍需拆分战争战略、臣使执行和本人外交条件设计，当前不足以直接新增正式M2父链。",
        "reopen_condition": "逐条完成外部对象条件、本人授权、对方反馈、执行终局与跨轴去重后，再决定是否局部复裁。",
    },
    "刘启": {
        "disposition": "NO_CLOSED_EXTERNAL_M2_LIFECYCLE_FOUND",
        "candidate_refs": [
            "docs/史料通读产物/唐以前编年/汉/卷016-通读总结.md#L26",
            "docs/史料通读产物/唐以前编年/汉/卷016-通读总结.md#L96",
        ],
        "reason": "和亲后连续入侵未闭合结果/因果门；七国之乱是本朝宗室与诸侯危机，已转M4，不能代替景帝本人外部外交周期。",
        "reopen_condition": "补齐景帝朝匈奴方向使节、边市、停战、交换或反馈重谈的直接过程链。",
    },
}


def _config() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))["profile_assessment"]


def _payloads() -> dict[str, dict[str, Any]]:
    config = _config()
    return {
        axis: load_json(ROOT / config["settled_axes"][axis]["json"])
        for axis in config["axis_order"]
    }


def _parent_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    return list(record.get("parent_chains") or record.get("parents") or [])


def _counterpattern_errors(record: dict[str, Any]) -> list[str]:
    counterpattern = record.get("counterpattern")
    if not isinstance(counterpattern, dict):
        return []
    parents = {str(parent.get("parent_id")): parent for parent in _parent_rows(record)}
    positive_refs = {str(value) for value in counterpattern.get("positive_parent_refs") or []}
    negative_refs = {
        str(value)
        for value in (counterpattern.get("counter_parent_refs") or counterpattern.get("negative_parent_refs") or [])
    }
    errors: list[str] = []
    if not positive_refs <= parents.keys():
        errors.append("positive_parent_ref_missing")
    if not negative_refs <= parents.keys():
        errors.append("counter_parent_ref_missing")
    for ref in positive_refs:
        if not str(parents[ref].get("direction") or "").startswith(("POSITIVE", "MIXED_POSITIVE")):
            errors.append("positive_parent_ref_direction_mismatch")
    for ref in negative_refs:
        direction = str(parents[ref].get("direction") or "")
        if not direction.startswith(("NEGATIVE", "MIXED_NEGATIVE")) and direction not in {"MIXED", "MIXED_BALANCED"}:
            errors.append("counter_parent_ref_direction_mismatch")
    scoring = [parent for parent in parents.values() if parent.get("consumption_status") == "SCORING_PARENT"]
    if any(str(parent.get("direction") or "").startswith(("POSITIVE", "MIXED_POSITIVE")) for parent in scoring) and not positive_refs:
        errors.append("scoring_positive_parent_without_counterpattern_ref")
    if any(str(parent.get("direction") or "").startswith(("NEGATIVE", "MIXED_NEGATIVE")) for parent in scoring) and not negative_refs:
        errors.append("scoring_negative_parent_without_counterpattern_ref")
    return sorted(set(errors))


def build_audit() -> dict[str, Any]:
    payloads = _payloads()
    rows: list[dict[str, Any]] = []
    structural_errors: list[dict[str, Any]] = []
    for ruler_name, axes in B_ENTRIES.items():
        for axis in axes:
            record = next(row for row in payloads[axis]["records"] if row["ruler_name"] == ruler_name)
            pending_display = bool(record.get("display_point_only")) or record.get("adjudication_state") in {
                "UNRESOLVED_EVIDENCE_GAP",
                "REASSESSMENT_REQUIRED",
            }
            errors = _counterpattern_errors(record)
            if errors:
                structural_errors.append(
                    {"axis": axis, "ruler_id": record["ruler_id"], "ruler_name": ruler_name, "errors": errors}
                )
            rows.append(
                {
                    "axis": axis,
                    "ruler_id": record["ruler_id"],
                    "ruler_name": ruler_name,
                    "formal_value": {
                        "axis_grade": record["axis_grade"],
                        "position": record["position"],
                        "score_100": record["score_100"],
                        "radar_value": record["radar_value"],
                    },
                    "formal_status": record.get("formal_status"),
                    "adjudication_state": record.get("adjudication_state", "FORMAL_CURRENT"),
                    "display_point_only": bool(record.get("display_point_only")),
                    "parent_count": len(_parent_rows(record)),
                    "scoring_parent_count": sum(parent.get("consumption_status") == "SCORING_PARENT" for parent in _parent_rows(record)),
                    "structural_status": "STRUCTURE_CLOSED" if not errors else "STRUCTURAL_REVIEW_REQUIRED",
                    "evidence_status": "DISPLAY_POINT_PENDING_REOPEN" if pending_display else "CURRENT_FORMAL_VALUE",
                    **(
                        {"pending_evidence_detail": PENDING_EVIDENCE_DETAILS[ruler_name]}
                        if pending_display and ruler_name in PENDING_EVIDENCE_DETAILS
                        else {}
                    ),
                }
            )
    pending = [row for row in rows if row["evidence_status"] != "CURRENT_FORMAL_VALUE"]
    return {
        "schema_version": "profile-b-person-remediation-current-state-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "CHECKLIST_B_PERSON_LEVEL_REMEDIATION_CURRENT_STATE",
        "source_checklist": "X:/下载/人物画像全池整改清单.md",
        "entry_count": len(rows),
        "person_count": len(B_ENTRIES),
        "structure_closed_count": sum(row["structural_status"] == "STRUCTURE_CLOSED" for row in rows),
        "pending_evidence_count": len(pending),
        "structural_error_count": len(structural_errors),
        "rows": rows,
        "structural_errors": structural_errors,
        "pending_evidence": pending,
        "grade_write": False,
        "position_write": False,
        "radar_write": False,
        "formal_score_write": False,
    }


def write() -> dict[str, Any]:
    audit = build_audit()
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    write_json(AUDIT, audit)
    return {
        "audit_json": AUDIT.relative_to(ROOT).as_posix(),
        "entry_count": audit["entry_count"],
        "structure_closed_count": audit["structure_closed_count"],
        "pending_evidence_count": audit["pending_evidence_count"],
        "structural_error_count": audit["structural_error_count"],
        "formal_score_write": False,
    }


def verify() -> dict[str, Any]:
    expected = build_audit()
    if not AUDIT.is_file():
        raise ValueError(f"B人物级审计不存在: {AUDIT}")
    if load_json(AUDIT) != expected:
        raise ValueError("B人物级审计与当前正式画像不一致")
    if expected["structural_error_count"]:
        raise ValueError(f"B人物级结构缺口: {expected['structural_error_count']}")
    return {
        "status": "PASS",
        "entry_count": expected["entry_count"],
        "structure_closed_count": expected["structure_closed_count"],
        "pending_evidence_count": expected["pending_evidence_count"],
        "formal_score_write": False,
    }


if __name__ == "__main__":
    import sys

    result = write() if len(sys.argv) > 1 and sys.argv[1] == "write" else verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
