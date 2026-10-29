"""Contract checks for authored B1/B2 quality judgments.

Evidence describes the observed mechanism. It does not calculate the grade or
the position: those remain explicit, source-backed adjudications.
"""
from __future__ import annotations

from typing import Any
from decimal import Decimal, ROUND_HALF_UP

ASSESSMENT_METHOD = "GOVERNANCE-QUALITY-V1"
PROFILE_KEYS = ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
EVIDENCE_USES = {"direct", "verification", "context", "absorbed"}
CONFIDENCES = {"LOW", "MEDIUM", "HIGH"}
POSITION_Q = {"lower":"0.1", "lower-middle":"0.3", "middle":"0.5", "middle-upper":"0.7", "upper":"0.9"}
INDEX_INTERVALS = {
    100: {"G0":("0","19.9"), "G1":("20","39.9"), "G2":("40","54.9"), "G3":("55","69.9"), "G4":("70","84.9"), "G5":("85","100")},
    80: {"G0":("0","15.9"), "G1":("16","31.9"), "G2":("32","43.9"), "G3":("44","55.9"), "G4":("56","67.9"), "G5":("68","80")},
}
B2_GRADE_CODES = {"G0":"B2_G0_SYSTEM_CLOSURE", "G1":"B2_G1_OBSERVED_SUPPRESSION", "G2":"B2_G2_LIMITED_MIXED_OR_DEFAULT", "G3":"B2_G3_MAIN_STAGE_FEEDBACK_SAFE", "G4":"B2_G4_MULTICHANNEL_CROSSLEVEL_SUPREME", "G5":"B2_G5_RARE_MULTICHANNEL_INSTITUTIONALIZED"}


def direction_index(grade: str, position: str, *, scale: int = 100) -> float:
    low, high = (Decimal(x) for x in INDEX_INTERVALS[scale][grade])
    value = low + Decimal(POSITION_Q[position]) * (high-low)
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
REQUIRED_ASSESSMENT_FIELDS = (
    "main_state_basis", "scope_and_attribution", "counterevidence_and_recovery",
    "position_basis", "material_review_basis",
)
RETIRED_ROW_FIELDS = {
    "position_residual", "grade_threshold_consumed", "g3_core_profile_id",
    "g3_m2_profile_ids", "g3_gate_route", "g3_gate_profile_ids",
    "g4_core_profile_id", "g4_secondary_profile_id", "g5_extra_route",
    "g5_extra_basis_id", "g5_reliability_validation", "g5_eligibility",
}
RETIRED_PROFILE_FIELDS = {
    "signed_weight", "position_weight_override", "position_depth_bonus",
    "mixed_weight_mode", "grade_weight_override",
}


def profiles(row: dict[str, Any]):
    for key in PROFILE_KEYS:
        yield from row.get(key) or []


def is_direct(profile: dict[str, Any]) -> bool:
    return profile.get("evidence_use") == "direct" and profile.get("M") in {"M2", "M3"}


def validate_quality_assessment(row: dict[str, Any], axis: str) -> None:
    name = str(row.get("ruler_name") or row.get("ruler_id") or "未命名对象")
    if axis not in {"B1", "B2"} or row.get("assessment_method") != ASSESSMENT_METHOD:
        raise ValueError(f"{axis}缺少当前质量裁决方式：{name}")
    if row.get("confidence") not in CONFIDENCES:
        raise ValueError(f"{axis}缺少有效置信度：{name}")
    assessment = row.get("semantic_assessment")
    if not isinstance(assessment, dict) or any(
        not isinstance(assessment.get(key), str) or not assessment[key].strip()
        for key in REQUIRED_ASSESSMENT_FIELDS
    ):
        raise ValueError(f"{axis}质量裁决缺少范围、归责、反证恢复或位置依据：{name}")
    if assessment["main_state_basis"] != row.get("grade_basis") or assessment["position_basis"] != row.get("position_basis"):
        raise ValueError(f"{axis}质量裁决与当前理由不同值：{name}")
    if RETIRED_ROW_FIELDS & row.keys():
        raise ValueError(f"{axis}仍保留已退役的权重或机械升档字段：{name}")
    items = list(profiles(row))
    ids = [p.get("profile_id") for p in items]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{axis}材料切片身份缺失或重复：{name}")
    for p in items:
        if p.get("M") not in {"M0", "M2", "M3"} or p.get("evidence_use") not in EVIDENCE_USES:
            raise ValueError(f"{axis}材料强度或用途非法：{name}")
        if RETIRED_PROFILE_FIELDS & p.keys():
            raise ValueError(f"{axis}材料仍以权重决定质量：{name}")
        if p["M"] == "M0" and p["evidence_use"] == "direct":
            raise ValueError(f"{axis}未闭合材料不能作为直接运行事实：{name}")
        if not isinstance(p.get("material_review_basis"), str) or not p["material_review_basis"].strip():
            raise ValueError(f"{axis}材料缺少采用范围与来源复核理由：{name}")
    default = row.get("grade_origin") == "MISSING_EVIDENCE_DEFAULT"
    if default:
        if axis != "B2" or (row.get("grade"), row.get("position"), row.get("confidence")) != ("G2", "lower", "LOW"):
            raise ValueError(f"{axis}缺证默认值不符合合同：{name}")
        if row.get("evidence_status") != "INSUFFICIENT_EVIDENCE_DEFAULT" or any(is_direct(p) for p in items):
            raise ValueError(f"{axis}缺证默认不能虚构直接正负材料：{name}")
    elif row.get("evidence_status") == "INSUFFICIENT_EVIDENCE_DEFAULT":
        raise ValueError(f"{axis}缺证状态与裁决性质不一致：{name}")
    if row.get("grade") in {"G4", "G5"} and not str(assessment.get("reliability_basis") or "").strip():
        raise ValueError(f"{axis}高档缺少广泛持续可靠性说明：{name}")
    if row.get("grade") == "G5" and not str(assessment.get("rare_quality_basis") or "").strip():
        raise ValueError(f"{axis}最高档缺少罕见质量说明：{name}")
