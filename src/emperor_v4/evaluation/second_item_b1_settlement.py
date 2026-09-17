from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json


B1_PATH = Path("docs/评分结算/净收益/第二项治国净收益/制度行政/02-B1官僚治理与行政执行方向卡.json")
METHOD_PATH = Path("docs/评分结算/净收益/第二项治国净收益/制度行政/04-治理手段165分正式结算.json")
TOTAL_PATH = Path("docs/评分结算/净收益/第二项治国净收益/01-第二项治国净收益正式结算.json")
FINANCE_PATHS = {
    "C1": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/01-C1正式结算.json"),
    "C2": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/02-C2正式结算.json"),
    "C3": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/03-C3正式结算.json"),
    "C4": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/04-C4正式结算.json"),
}
CONTRACT_PATH = Path("docs/分项规则/第二项治国净收益/制度行政/00-规则与计分合同.md")

POSITION_Q = {
    "lower": 0.1,
    "lower-middle": 0.3,
    "middle": 0.5,
    "middle-upper": 0.7,
    "upper": 0.9,
}
INTERVALS = {
    "G0": (0.0, 19.9),
    "G1": (20.0, 39.9),
    "G2": (40.0, 54.9),
    "G3": (55.0, 69.9),
    "G4": (70.0, 84.9),
    "G5": (85.0, 100.0),
}
THRESHOLDS = {"G0": 0.0, "G1": 0.5, "G2": 1.0, "G3": 2.0, "G4": 3.0, "G5": 4.0}
GATE_CODES = {
    "G0": "B1_G0_SYSTEMIC_ADMIN_BREAKDOWN",
    "G1": "B1_G1_DYSFUNCTION_DOMINANT",
    "G2": "B1_G2_LIMITED_OR_MIXED",
    "G3": "B1_G3_MAIN_STAGE_USABLE",
    "G4": "B1_G4_BROAD_STABLE_DELIVERY",
    "G5": "B1_G5_RARE_RELIABILITY",
}
ALLOWED_B1_ROLES = {"core", "central", "distributed", "support", "context"}
ALLOWED_SEVERITIES = {"N3-domain", "N3-cross", "N3-terminal"}
ALLOWED_SEVERITY_SCOPES = {"localized", "major-stage", "broad"}
PROFILE_KEYS = ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
ADJUDICATION_STATUSES = {
    "COUNTED_INDEPENDENT",
    "ABSORBED_SAME_LIFECYCLE",
    "BOUNDARY_CONTEXT",
    "ZERO_NET",
}
PUBLIC_STATUS_LABELS = {
    "COUNTED_INDEPENDENT": "独立计入",
    "ABSORBED_SAME_LIFECYCLE": "并入同一运行链",
    "BOUNDARY_CONTEXT": "不单独计入",
    "ZERO_NET": "不增加净值",
}
PUBLIC_DIRECTION_LABELS = {
    "positive": "正向",
    "positive_correction": "正向",
    "negative": "负向",
    "mixed_positive": "正向主导",
    "mixed_negative": "负向主导",
    "mixed": "正负并存",
    "balanced": "正负并存",
    "neutral": "正负并存",
    "context": "边界材料",
}
PUBLIC_ROLE_LABELS = {
    "core": "核心行政链",
    "central": "中枢行政链",
    "distributed": "多责任官行政链",
    "support": "支撑行政链",
    "context": "边界材料",
}
PUBLIC_CLOSURE_LABELS = {
    "sustained_or_systemic": "持续或系统运行",
    "observed_or_repeated": "已有实际运行",
    "observed": "已有实际运行",
    "not_restored": "未恢复",
    "reversed": "后续逆转",
    "not_closed": "运行证据尚未完整",
}
PUBLIC_FORBIDDEN_RE = re.compile(
    r"(?:本轮|重审|恢复原|旧裁决|\bv20\b|\bv50\b|按合同|门禁|主档|消费|闭合|净余量|"
    r"(?<![A-Za-z])position(?![A-Za-z])|(?<![A-Za-z])fallback(?![A-Za-z])|"
    r"\bB[12]\b|\bM[0-3]\b|N3-(?:domain|cross|terminal)|"
    r"(?<![A-Za-z])(?:core|support|central|distributed|context|mixed_positive|mixed_negative|"
    r"observed_or_repeated|sustained_or_systemic|lifecycle|profile|balanced|personnel)(?![A-Za-z])|"
    r"(?<![A-Za-z])(?:record_adjudication|profile_fallback)(?![A-Za-z]))",
    flags=re.I,
)

# These four profiles were the only records whose previous compatibility pass
# obtained prose from a ruler-level basis or from a generic profile fallback.
# Keep their facts attached to the profile itself before the compatibility
# module is removed from the repository.
LEGACY_PROFILE_BASIS = {
    "B1-PROFILE-CED7C6A0472A53CD": (
        "王公、妃主和豪强侵扰民众受到官僚问责约束，官吏在问责后保持清谨；"
        "由此形成特权干预受限、官僚能够独立执行的行政运行。"
    ),
    "B1-PROFILE-4E9F2CBCC8A6912B": (
        "官吏受赃问责并形成清谨结果；该材料与特权干预受限属于同一行政运行过程，"
        "故并入“特权势力干预约束与官僚独立执行”，不另行计入本项。"
    ),
    "B1-PROFILE-5B138E7D76DA61AC": (
        "郑弘开通零陵、桂阳道路，使交趾七郡贡运此后成为常路；"
        "该跨区域行政传导形成实际交付，作为独立行政运行链计入本项。"
    ),
    "B1-PROFILE-66B0DC7313747BA0": (
        "强臣退出后，正式责任中心重新配置，军政责任由中枢与地方责任官承接；"
        "相关任命、执行与后续岗位接续形成独立行政运行链。"
    ),
}


def _iter_profiles(row: dict[str, Any]):
    for key in PROFILE_KEYS:
        for profile in row.get(key) or []:
            if isinstance(profile, dict):
                yield profile


def _publicize_text(value: object) -> str:
    """Remove legacy process markers from already-adjudicated profile prose.

    This is an upstream migration of stored profile text, not reader-side
    semantic selection. It never consults grade_basis or any other ruler-level
    explanation.
    """

    text = re.sub(r"\s+", " ", str(value or "")).replace("`", "").strip()
    if not text:
        return ""
    replacements = (
        (r"N3-terminal", "广域整体失效"),
        (r"N3-cross", "跨功能失灵"),
        (r"N3-domain", "单功能系统失灵"),
        (r"B1-central", "中枢行政链"),
        (r"B1-core", "核心行政链"),
        (r"B1-support", "支撑行政链"),
        (r"B1-(?:distributed|personnel)", "多责任官行政链"),
        (r"B1", "官僚治理"),
        (r"B2", "反馈与约束"),
        (r"M[0-3]", ""),
        (r"(?<![A-Za-z])N3(?![-A-Za-z])", "系统失灵"),
        (r"(?<![A-Za-z])M(?![A-Za-z])", ""),
        (r"G[0-5]", ""),
        (r"(?<![A-Za-z])core(?![A-Za-z])", "核心"),
        (r"(?<![A-Za-z])support(?![A-Za-z])", "支撑"),
        (r"(?<![A-Za-z])central(?![A-Za-z])", "中枢"),
        (r"(?<![A-Za-z])distributed(?![A-Za-z])", "多责任官"),
        (r"(?<![A-Za-z])context(?![A-Za-z])", "边界"),
        (r"(?<![A-Za-z])personnel(?![A-Za-z])", "人员"),
        (r"(?<![A-Za-z])accountability(?![A-Za-z])", "问责"),
        (r"(?<![A-Za-z])capture(?![A-Za-z])", "俘获"),
        (r"(?<![A-Za-z])mixed_positive(?![A-Za-z])", "正向主导"),
        (r"(?<![A-Za-z])mixed_negative(?![A-Za-z])", "负向主导"),
        (r"(?<![A-Za-z])mixed(?![A-Za-z])", "正负并存"),
        (r"(?<![A-Za-z])balanced(?![A-Za-z])", "正负并存"),
        (r"(?<![A-Za-z])observed_or_repeated(?![A-Za-z])", "已有实际运行"),
        (r"(?<![A-Za-z])sustained_or_systemic(?![A-Za-z])", "持续或系统运行"),
        (r"(?<![A-Za-z])not_restored(?![A-Za-z])", "未恢复"),
        (r"(?<![A-Za-z])not_closed(?![A-Za-z])", "运行证据尚未完整"),
        (r"(?<![A-Za-z])lifecycle(?![A-Za-z])", "运行过程"),
        (r"(?<![A-Za-z])profile(?![A-Za-z])", "材料"),
        (r"(?<![A-Za-z])v20(?![A-Za-z])", "既有材料"),
        (r"(?<![A-Za-z])v50(?![A-Za-z])", "既有材料"),
        (r"(?<![A-Za-z])position(?![A-Za-z])", "档内位置"),
        (r"(?<![A-Za-z])localized(?![A-Za-z])", "局部范围"),
        (r"(?<![A-Za-z])major-stage(?![A-Za-z])", "主要阶段"),
        (r"(?<![A-Za-z])broad(?![A-Za-z])", "广泛范围"),
        (r"(?<![A-Za-z])late-stage(?![A-Za-z])", "后期"),
        (r"(?<![A-Za-z])material_id(?![A-Za-z])", "材料编号"),
        (r"(?<![A-Za-z])JSON(?![A-Za-z])", "相关材料"),
        (r"(?<![A-Za-z])battle-adjudications(?![A-Za-z])", "战事材料"),
        (r"volume-\d+\.battle-adjudications\.json", "战事材料"),
        (r"volume-\d+\.战事材料\.(?:json|相关材料)", "相关战事材料"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    for old, new in (
        ("按v20/v50材料并集复核", "根据既有材料"),
        ("按既有材料/既有材料材料并集复核", "根据既有材料"),
        ("既有材料材料并集复核", "既有材料复核"),
        ("grade_basis", "正式裁决"),
        ("旧profile与正式裁决不同步", ""),
        ("旧材料与正式裁决不同步", ""),
        ("结算正式裁决自身亦明确", "该材料明确"),
        ("口径：只收非战役事实；", ""),
        ("分流说明：本文件只写非战役事实。", ""),
        ("本轮", ""),
        ("重审", "复核"),
        ("恢复原", "恢复"),
        ("旧裁决", "既有裁决"),
        ("按合同", "按本项规则"),
        ("门禁", "等级判断"),
        ("主档", "主要记录"),
        ("消费", "计入"),
        ("闭合", "形成"),
        ("净余量", "剩余依据"),
        ("同一同一", "同一"),
        ("官僚治理 官僚治理", "官僚治理"),
    ):
        text = text.replace(old, new)
    text = re.sub(
        r"按该负同一运行过程实际击中的官僚治理组织功能面与责任窗口裁为[^；]+；",
        "",
        text,
    )
    text = re.sub(
        r"\|\s*P\d+·L\d+·READY\s*\|.*?\|\s*（[^|]*）\s*\|",
        "；",
        text,
    )
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[；，]\s*[；，]+", "；", text)
    return text.strip(" ；，。")


def _public_label(profile: dict[str, Any]) -> str:
    label = _publicize_text(profile.get("mechanism"))
    label = re.sub(r"^[：:、，；\s]+|[：:、，；\s]+$", "", label)
    return label or "行政运行机制"


def _derived_status(profile: dict[str, Any]) -> str:
    mode = str(profile.get("position_count_mode") or "")
    if mode == "absorbed_same_lifecycle" or (
        profile.get("position_weight_override") == 0 and profile.get("absorbed_into_lifecycle_key")
    ):
        return "ABSORBED_SAME_LIFECYCLE"
    if mode in {"context_only", "context_only_no_effective_mechanism"} or profile.get("direction") == "context":
        return "BOUNDARY_CONTEXT"
    if mode == "balanced_mixed_lifecycle" or float(profile.get("signed_weight") or 0.0) == 0.0:
        return "ZERO_NET"
    return "COUNTED_INDEPENDENT"


def _public_tags(profile: dict[str, Any], status: str) -> list[str]:
    role = "补充材料" if status == "ABSORBED_SAME_LIFECYCLE" else (
        "边界材料" if status == "BOUNDARY_CONTEXT" else PUBLIC_ROLE_LABELS.get(
            str(profile.get("b1_role") or ""), "行政运行链"
        )
    )
    values = [
        PUBLIC_DIRECTION_LABELS.get(str(profile.get("direction") or ""), "正负并存"),
        role,
        PUBLIC_STATUS_LABELS[status],
    ]
    closure = PUBLIC_CLOSURE_LABELS.get(str(profile.get("result_closure") or "").lower())
    if closure:
        values.append(closure)
    return list(dict.fromkeys(value for value in values if value))


def _profile_key_options(profile: dict[str, Any]) -> set[str]:
    return {
        str(profile.get(field))
        for field in ("grade_independence_lifecycle_key", "lifecycle_group_key", "lifecycle_key")
        if profile.get(field)
    }


def _weight_text(value: object) -> str:
    number = float(value or 0.0)
    if number.is_integer():
        return f"{number:+.0f}"
    return f"{number:+.1f}"


def _status_clause(profile: dict[str, Any], status: str, target_label: str = "") -> str:
    if status == "ABSORBED_SAME_LIFECYCLE":
        target = f"“{target_label}”" if target_label else "目标运行链"
        return f"该材料与{target}属于同一行政运行过程，故并入该运行链，不另行计入本项"
    if status == "BOUNDARY_CONTEXT":
        return "该材料仅用于说明行政边界或责任范围，不单独计入本项"
    if status == "ZERO_NET":
        return "正负作用发生在同一行政运行过程中，故不增加本项净值"
    return "该材料形成独立行政运行链，计入本项"


def _public_summary(row: dict[str, Any]) -> str:
    independent = [
        profile for profile in _iter_profiles(row)
        if profile.get("adjudication_status") == "COUNTED_INDEPENDENT"
    ]
    positive = sum(1 for profile in independent if profile.get("direction") in {"positive", "positive_correction"})
    negative = sum(1 for profile in independent if profile.get("direction") == "negative")
    mixed = sum(
        1 for profile in independent
        if profile.get("direction") not in {"positive", "positive_correction", "negative"}
    )
    mixed += sum(1 for profile in _iter_profiles(row) if profile.get("adjudication_status") == "ZERO_NET")
    absorbed = sum(1 for profile in _iter_profiles(row) if profile.get("adjudication_status") == "ABSORBED_SAME_LIFECYCLE")
    context = sum(1 for profile in _iter_profiles(row) if profile.get("adjudication_status") == "BOUNDARY_CONTEXT")
    parts = [f"正式结算按独立行政运行链判断：正向 {positive} 条、负向 {negative} 条、正负并存 {mixed} 条"]
    if absorbed:
        parts.append(f"{absorbed} 条补充材料并入同一运行链")
    if context:
        parts.append(f"{context} 条边界材料不单独计入")
    parts.append("各条权重并不相同，不能按条数直接相减")
    return "；".join(parts) + "。"


def _group_key(profile: dict[str, Any]) -> str:
    return str(
        profile.get("grade_independence_lifecycle_key")
        or profile.get("lifecycle_group_key")
        or profile.get("lifecycle_key")
        or profile["material_id"]
    )


def _excluded(profile: dict[str, Any]) -> bool:
    return profile.get("position_weight_override") == 0 or profile.get("position_count_mode") in {
        "absorbed_same_lifecycle",
        "balanced_mixed_lifecycle",
        "context_only",
        "context_only_no_effective_mechanism",
    }


def profile_id(ruler_id: str, profile: dict[str, Any]) -> str:
    raw = "|".join(
        (
            ruler_id,
            str(profile["material_id"]),
            str(profile.get("evidence_slice") or "PRIMARY"),
            _group_key(profile),
        )
    )
    return "B1-PROFILE-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def active_groups(row: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
        for profile in row.get(key) or []:
            if _excluded(profile):
                continue
            groups.setdefault(_group_key(profile), []).append(profile)
    representatives = []
    for group_profiles in groups.values():
        nonzero = [profile for profile in group_profiles if float(profile.get("signed_weight") or 0.0) != 0]
        if not nonzero:
            continue
        representatives.append(max(nonzero, key=lambda profile: abs(float(profile["signed_weight"]))))
    return representatives


def position_residual(row: dict[str, Any]) -> float:
    profiles = active_groups(row)
    residual = sum(float(profile.get("signed_weight") or 0.0) for profile in profiles)
    for profile in profiles:
        if profile.get("M") != "M3" or float(profile.get("signed_weight") or 0.0) >= 0:
            continue
        if profile.get("direction") == "mixed_negative":
            continue
        severity = str(profile.get("severity") or "")
        if "terminal" in severity:
            residual -= 1.0
        elif "cross" in severity:
            residual -= 0.5
    return round(residual - THRESHOLDS[str(row["grade"])], 3)


def position_from_residual(residual: float) -> str:
    if residual < -1:
        return "lower"
    if residual < 0:
        return "lower-middle"
    if residual < 1:
        return "middle"
    if residual < 2:
        return "middle-upper"
    return "upper"


def index_from_grade_position(grade: str, position: str) -> float:
    low, high = INTERVALS[grade]
    return round(low + POSITION_Q[position] * (high - low), 1)


def _competition_ranks(records: list[dict[str, Any]], score_key: str) -> None:
    scores = sorted((float(row[score_key]) for row in records), reverse=True)
    for row in records:
        row["rank"] = scores.index(float(row[score_key])) + 1
    records.sort(key=lambda row: (int(row["rank"]), str(row["ruler_id"])))


def _reader_text(text: str) -> str:
    replacements = {
        "mixed_positive": "正向主导复合链",
        "mixed_negative": "负向主导复合链",
        "distributed→core": "多责任官样本转为核心行政机制",
        "B1-distributed": "多责任官样本",
        "B1-central": "中枢运行",
        "B1-support": "行政交付",
        "B1-core": "核心行政机制",
        "distributed": "多责任官样本",
        "central": "中枢运行",
        "support": "行政交付",
        "core": "核心行政机制",
        "personnel": "选任与考课",
        "capture": "控制",
        "major-stage": "主要阶段",
        "mixed": "复合",
        "N3-cross": "N3（跨功能失灵）",
        "N3-domain": "N3（单功能系统失灵）",
        "N3-terminal": "N3（广域整体失效）",
        "N3-domain": "N3（单功能系统失灵）",
        "position": "档内位置",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _public_position_basis(row: dict[str, Any]) -> str:
    position_cn = {
        "lower": "下位",
        "lower-middle": "中下位",
        "middle": "中位",
        "middle-upper": "中上位",
        "upper": "上位",
    }
    return (
        f"档位{row['grade']}内的公开位置按有效行政运行链的合计依据机械确定为"
        f"{position_cn[row['position']]}，公开指数为{float(row['direction_index']):.1f}/100；"
        "该位置只用于同档展示，不用于跨档比较。"
    )


def _structured_basis(row: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "公开总括",
            "text": str(row["public_adjudication_summary"]),
        },
        {
            "role": "档内位置",
            "text": _public_position_basis(row),
        },
    ]


def _scoring_signature(payload: dict[str, Any]) -> str:
    snapshot = []
    for row in sorted(payload.get("records") or [], key=lambda item: str(item.get("ruler_id"))):
        profiles = []
        for profile in _iter_profiles(row):
            profiles.append({
                key: profile.get(key)
                for key in (
                    "material_id", "evidence_slice", "M", "direction", "direction_factor",
                    "signed_weight", "lifecycle_key", "lifecycle_group_key",
                    "grade_independence_lifecycle_key", "position_count_mode",
                    "position_weight_override", "absorbed_into_lifecycle_key", "b1_role",
                    "severity", "severity_scope",
                )
            })
        snapshot.append({
            "ruler_id": row.get("ruler_id"),
            "grade": row.get("grade"),
            "position": row.get("position"),
            "position_residual": row.get("position_residual"),
            "grade_threshold_consumed": row.get("grade_threshold_consumed"),
            "position_q": row.get("position_q"),
            "direction_index": row.get("direction_index"),
            "rank": row.get("rank"),
            "profiles": profiles,
        })
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _prepare_profile_adjudication(payload: dict[str, Any]) -> tuple[int, Counter[str]]:
    profile_count = 0
    status_counts: Counter[str] = Counter()
    for row in payload["records"]:
        profiles = list(_iter_profiles(row))
        for profile in profiles:
            profile_count += 1
            derived_status = _derived_status(profile)
            stored_status = str(profile.get("adjudication_status") or "")
            if stored_status and stored_status != derived_status and not (
                stored_status == "BOUNDARY_CONTEXT"
                and derived_status == "ABSORBED_SAME_LIFECYCLE"
                and profile.get("absorbed_into_lifecycle_key") in _profile_key_options(profile)
            ):
                raise ValueError(f"B1 profile公开状态与计入字段不一致：{row['ruler_name']} / {profile.get('material_id')}")
            status = stored_status or derived_status
            if status not in ADJUDICATION_STATUSES:
                raise ValueError(f"B1 profile的公开裁决状态非法：{row['ruler_name']} / {profile.get('material_id')}")
            profile["adjudication_status"] = status
            profile["public_label"] = _publicize_text(profile.get("public_label")) or _public_label(profile)

            basis = LEGACY_PROFILE_BASIS.get(str(profile.get("profile_id"))) or profile.get("adjudication_basis")
            if not str(basis or "").strip():
                raise ValueError(f"B1 profile缺少逐材料正式裁决：{row['ruler_name']} / {profile.get('material_id')}")
            profile["adjudication_basis"] = _publicize_text(basis)
            if not profile["adjudication_basis"]:
                raise ValueError(f"B1 profile逐材料正式裁决为空：{row['ruler_name']} / {profile.get('material_id')}")
            boundary = _publicize_text(profile.get("adjudication_boundary"))
            if boundary:
                profile["adjudication_boundary"] = boundary
            else:
                profile.pop("adjudication_boundary", None)
            profile["adjudication_tags"] = _public_tags(profile, status)
            # The old compatibility source trail is deliberately not a formal
            # field: profile prose is now the source, and the settlement gate
            # rejects any fallback marker that survives the migration.
            profile.pop("adjudication_basis_source", None)

        by_id = {str(profile["profile_id"]): profile for profile in profiles}
        for profile in profiles:
            status = str(profile["adjudication_status"])
            target_label = ""
            if status == "ABSORBED_SAME_LIFECYCLE":
                target_key = str(profile.get("absorbed_into_lifecycle_key") or "")
                candidates = [
                    candidate
                    for candidate in profiles
                    if candidate is not profile
                    and target_key
                    and target_key in _profile_key_options(candidate)
                    and candidate.get("adjudication_status") in {"COUNTED_INDEPENDENT", "ZERO_NET"}
                ]
                if len(candidates) != 1:
                    # One legacy record points to itself despite being marked
                    # absorbed. It carries boundary evidence, not an
                    # independent score; make that public state explicit.
                    if not candidates and profile.get("absorbed_into_lifecycle_key") in _profile_key_options(profile):
                        status = "BOUNDARY_CONTEXT"
                        profile["adjudication_status"] = status
                        profile.pop("absorbed_into_profile_id", None)
                        profile["adjudication_tags"] = _public_tags(profile, status)
                    else:
                        raise ValueError(
                            f"B1 absorbed profile无法唯一定位目标：{row['ruler_name']} / {profile.get('material_id')}"
                        )
                else:
                    target = candidates[0]
                    target_id = str(target["profile_id"])
                    if target_id == str(profile["profile_id"]) or target_id not in by_id:
                        raise ValueError(f"B1 absorbed profile目标无效：{row['ruler_name']} / {profile.get('material_id')}")
                    profile["absorbed_into_profile_id"] = target_id
                    target_label = str(target.get("public_label") or "行政运行机制")
            elif profile.get("absorbed_into_profile_id"):
                raise ValueError(f"非并入profile不得保留absorbed_into_profile_id：{row['ruler_name']} / {profile.get('material_id')}")

            clause = _status_clause(profile, status, target_label)
            basis = str(profile["adjudication_basis"]).rstrip("。")
            if clause not in basis and not (
                status == "ABSORBED_SAME_LIFECYCLE" and "并入" in basis and "不另行计入" in basis
            ):
                profile["adjudication_basis"] = f"{basis}；{clause}。"
            status_counts[status] += 1

        row["public_adjudication_summary"] = _public_summary(row)
        row["profile_adjudication_style"] = "B1-PROFILE-ADJUDICATION-V2"

    payload["profile_adjudication_style"] = "B1-PROFILE-ADJUDICATION-V2"
    payload["profile_adjudication_record_count"] = len(payload.get("records") or [])
    payload["profile_adjudication_profile_count"] = profile_count
    payload["profile_adjudication_status_counts"] = dict(sorted(status_counts.items()))
    payload.pop("profile_adjudication_basis_source_counts", None)
    payload.pop("profile_adjudication_polish_count", None)
    return profile_count, status_counts


def refresh_b1_payload(payload: dict[str, Any]) -> dict[str, Any]:
    before = _scoring_signature(payload)
    records = payload["records"]
    for row in records:
        ruler_id = str(row["ruler_id"])
        for key in PROFILE_KEYS:
            for profile in row.get(key) or []:
                profile.pop("position_depth_bonus", None)
                if profile.get("position_count_mode") == "representative_delivery_depth":
                    profile.pop("position_count_mode", None)
                profile["profile_id"] = profile_id(ruler_id, profile)
    _prepare_profile_adjudication(payload)
    for row in records:
        residual = position_residual(row)
        active = active_groups(row)
        if row["grade"] == "G0" and not active:
            position = "middle"
        else:
            position = position_from_residual(residual)
        row["position_residual"] = residual
        row["grade_threshold_consumed"] = THRESHOLDS[row["grade"]]
        row["position"] = position
        row["position_q"] = POSITION_Q[position]
        row["direction_index"] = index_from_grade_position(row["grade"], position)
        row["index_interval"] = list(INTERVALS[row["grade"]])
        row["grade_gate_code"] = GATE_CODES[row["grade"]]
        row["position_basis"] = (
            f"有效生命周期签名M权重合计扣除{row['grade']}门槛占用"
            f"{THRESHOLDS[row['grade']]:g}后，净余量={residual:g}，按合同机械映射为{position}。"
        )
        row["structured_grade_basis"] = _structured_basis(row)
        row["profile_semantic_review_status"] = "B1_CONTRACT_V54_LOW_GATE_NEGATIVE_PURITY_REVIEWED"
        row.pop("v50_review_decision", None)
        row.pop("v50_review_status", None)
        row.pop("v50_review_basis", None)
        row.pop("structured_basis_source", None)
        row.pop("structured_basis_source_line", None)
    _competition_ranks(records, "direction_index")
    payload["grade_distribution"] = dict(sorted(Counter(row["grade"] for row in records).items()))
    payload["promotion_task_code"] = "B1-V54-LOW-GATE-NEGATIVE-PURITY-CONTRACT-READJUDICATION"
    payload["contract_recalculation_status"] = "FORMAL_COMPLETE"
    payload["contract_recalculation_count"] = len(records)
    payload["profile_semantic_review_count"] = len(records)
    payload["position_basis_refresh_count"] = len(records)
    payload["structured_basis_count"] = len(records)
    for key in (
        "profile_semantic_patch_count",
        "v50_review_covered_count",
        "v50_review_preserved_count",
        "v50_review_preserved_rulers",
        "v50_person_patch_count",
        "v50_explicit_value_patch_count",
        "structured_basis_source_counts",
        "structured_basis_conflict_policy",
        "structured_basis_review_covered_count",
    ):
        payload.pop(key, None)
    if _scoring_signature(payload) != before:
        raise ValueError("B1逐材料公开字段迁移意外改变了正式评分字段")
    contract = CONTRACT_PATH.read_bytes()
    for source in payload.get("source_documents") or []:
        if source.get("path") == CONTRACT_PATH.as_posix():
            source["byte_sha256"] = hashlib.sha256(contract).hexdigest()
    return payload


def validate_gate_references(payload: dict[str, Any]) -> None:
    validate_profile_contract(payload)
    validate_public_profile_contract(payload)
    for row in payload["records"]:
        active = {_group_key(profile): profile for profile in active_groups(row)}
        by_id = {str(profile["profile_id"]): profile for profile in active.values()}
        grade = str(row["grade"])
        active_negative_m3 = [
            profile
            for profile in active.values()
            if profile.get("M") == "M3" and float(profile.get("signed_weight") or 0.0) < 0
        ]
        if grade == "G0" and not any(
            profile.get("severity") == "N3-terminal"
            and profile.get("severity_scope") == "broad"
            and profile.get("b1_role") == "core"
            for profile in active_negative_m3
        ):
            raise ValueError(f"B1 G0缺少broad N3-terminal核心失效链：{row['ruler_name']}")
        if grade == "G1":
            has_terminal_residual = any(
                profile.get("severity") == "N3-terminal"
                for profile in active_negative_m3
            )
            has_dominant_cross = any(
                profile.get("severity") == "N3-cross"
                and profile.get("severity_scope") in {"major-stage", "broad"}
                for profile in active_negative_m3
            )
            dominant_domains = [
                profile
                for profile in active_negative_m3
                if profile.get("severity") == "N3-domain"
                and profile.get("severity_scope") in {"major-stage", "broad"}
            ]
            if not (has_terminal_residual or has_dominant_cross or len(dominant_domains) >= 2):
                raise ValueError(f"B1 G1缺少terminal残存、主要阶段cross或两条独立domain负链：{row['ruler_name']}")
        if grade == "G3":
            route = row.get("g3_gate_route")
            refs = row.get("g3_gate_profile_ids") or []
            profiles = [by_id.get(str(profile_ref)) for profile_ref in refs]
            if len(refs) != len(set(map(str, refs))) or any(profile is None for profile in profiles):
                raise ValueError(f"B1 G3门禁引用缺失或重复：{row['ruler_name']}")
            if route == "CORE_M3":
                if len(profiles) != 1 or profiles[0]["M"] != "M3" or profiles[0].get("b1_role") != "core" or float(profiles[0]["signed_weight"]) <= 0:
                    raise ValueError(f"B1 G3核心M3路线无效：{row['ruler_name']}")
            elif route == "CENTRAL_OR_DISTRIBUTED_M3":
                if len(profiles) != 1 or profiles[0]["M"] != "M3" or profiles[0].get("b1_role") not in {"central", "distributed"} or float(profiles[0]["signed_weight"]) <= 0:
                    raise ValueError(f"B1 G3中枢/分布式M3路线无效：{row['ruler_name']}")
            elif route == "MULTI_CHAIN":
                if len(profiles) < 2 or any(
                    profile["M"] not in {"M2", "M3"}
                    or profile.get("b1_role") == "context"
                    or float(profile["signed_weight"]) <= 0
                    for profile in profiles
                ):
                    raise ValueError(f"B1 G3多链路线不足两条独立正M2/M3：{row['ruler_name']}")
            else:
                raise ValueError(f"B1 G3缺少合法门禁路线：{row['ruler_name']}")
        if grade in {"G4", "G5"}:
            refs = [row.get("g4_core_profile_id"), row.get("g4_secondary_profile_id")]
            if any(not ref or str(ref) not in by_id for ref in refs):
                raise ValueError(f"B1 G4门禁引用缺失：{row['ruler_name']}")
            core, secondary = (by_id[str(ref)] for ref in refs)
            if core["M"] != "M3" or core.get("b1_role") != "core" or float(core["signed_weight"]) <= 0:
                raise ValueError(f"B1 G4核心链不是B1-core正M3：{row['ruler_name']}")
            if secondary["M"] not in {"M2", "M3"} or float(secondary["signed_weight"]) <= 0:
                raise ValueError(f"B1 G4第二验证无效：{row['ruler_name']}")
            if _group_key(core) == _group_key(secondary):
                raise ValueError(f"B1 G4两条链未去重：{row['ruler_name']}")
            if any(
                profile.get("M") == "M3"
                and float(profile.get("signed_weight") or 0.0) < 0
                and profile.get("severity") == "N3-cross"
                and profile.get("severity_scope") in {"major-stage", "broad"}
                for profile in active.values()
            ):
                raise ValueError(f"B1 G4/G5仍有独立major-stage/broad N3-cross：{row['ruler_name']}")
        if grade == "G5":
            extra_id = row.get("g5_extra_basis_id")
            route = row.get("g5_extra_route")
            if not extra_id or str(extra_id) not in by_id:
                raise ValueError(f"B1 G5额外链缺失：{row['ruler_name']}")
            extra = by_id[str(extra_id)]
            consumed = {row["g4_core_profile_id"], row["g4_secondary_profile_id"]}
            if (
                route not in {"THIRD_CORE_M3", "CROSS_STAGE_REPLACEMENT", "PRESSURE_RECOVERY"}
                or extra["M"] not in {"M2", "M3"}
                or (route == "THIRD_CORE_M3" and extra["M"] != "M3")
                or (route == "THIRD_CORE_M3" and extra.get("b1_role") != "core")
                or float(extra["signed_weight"]) <= 0
                or extra_id in consumed
            ):
                raise ValueError(f"B1 G5额外链无效或被G4重复消费：{row['ruler_name']}")
            if any(
                profile.get("M") == "M3"
                and float(profile.get("signed_weight") or 0.0) < 0
                and profile.get("severity") in {"N3-cross", "N3-terminal"}
                and profile.get("severity_scope") in {"major-stage", "broad"}
                for profile in active.values()
            ):
                raise ValueError(f"B1 G5仍有主要阶段跨功能失灵：{row['ruler_name']}")


def validate_profile_contract(payload: dict[str, Any]) -> None:
    for row in payload["records"]:
        for key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
            for profile in row.get(key) or []:
                role = profile.get("b1_role")
                if role not in ALLOWED_B1_ROLES:
                    raise ValueError(f"B1 profile缺少合法b1_role：{row['ruler_name']} / {profile.get('material_id')}")
                if _excluded(profile):
                    if role != "context":
                        raise ValueError(f"B1排除profile必须标为context：{row['ruler_name']} / {profile.get('material_id')}")
                    continue
                level = profile.get("M")
                weight = float(profile.get("signed_weight") or 0.0)
                if level in {"M2", "M3"}:
                    factors = {
                        "positive": 1.0, "positive_correction": 1.0,
                        "mixed_positive": 0.5, "mixed": 0.0, "neutral": 0.0,
                        "mixed_negative": -0.5, "negative": -1.0,
                    }
                    factor = factors.get(str(profile.get("direction")))
                    if factor is None or profile.get("direction_factor") != factor:
                        raise ValueError(f"B1方向与direction_factor不一致：{row['ruler_name']} / {profile.get('material_id')}")
                    expected = (1.0 if level == "M2" else 2.0) * factor
                    if abs(weight - expected) > 1e-9:
                        raise ValueError(
                            f"B1 M档与signed_weight不一致：{row['ruler_name']} / {profile.get('material_id')} / {level} / {weight:g}"
                        )
                elif level == "M0":
                    if weight != 0 or role != "context":
                        raise ValueError(f"B1 M0必须零权重且为context：{row['ruler_name']} / {profile.get('material_id')}")
                else:
                    raise ValueError(f"B1非法M档：{row['ruler_name']} / {profile.get('material_id')}")
                if level == "M3" and weight < 0:
                    if profile.get("direction") == "mixed_negative":
                        if any(profile.get(field) is not None for field in ("severity", "severity_scope", "severity_basis")):
                            raise ValueError(f"B1混合负M3不得保留独立Severity：{row['ruler_name']} / {profile.get('material_id')}")
                    else:
                        if profile.get("severity") not in ALLOWED_SEVERITIES:
                            raise ValueError(f"B1有效负M3缺少Severity：{row['ruler_name']} / {profile.get('material_id')}")
                        if profile.get("severity_scope") not in ALLOWED_SEVERITY_SCOPES:
                            raise ValueError(f"B1有效负M3缺少Severity scope：{row['ruler_name']} / {profile.get('material_id')}")
                        if profile.get("severity") in {"N3-cross", "N3-terminal"} and role != "core":
                            raise ValueError(f"B1 cross/terminal负M3必须标为core失灵：{row['ruler_name']} / {profile.get('material_id')}")
                elif any(profile.get(field) is not None for field in ("severity", "severity_scope", "severity_basis")):
                    raise ValueError(f"B1非负M3残留Severity字段：{row['ruler_name']} / {profile.get('material_id')}")


def validate_public_profile_contract(payload: dict[str, Any]) -> None:
    if payload.get("profile_adjudication_style") != "B1-PROFILE-ADJUDICATION-V2":
        raise ValueError("B1缺少正式逐材料公开裁决合同标记")
    expected_profile_count = 0
    status_counts: Counter[str] = Counter()
    for row in payload["records"]:
        profiles = list(_iter_profiles(row))
        by_id = {str(profile.get("profile_id")): profile for profile in profiles}
        for profile in profiles:
            expected_profile_count += 1
            status = str(profile.get("adjudication_status") or "")
            if status not in ADJUDICATION_STATUSES:
                raise ValueError(f"B1逐材料公开裁决状态缺失：{row['ruler_name']} / {profile.get('material_id')}")
            status_counts[status] += 1
            label = str(profile.get("public_label") or "").strip()
            basis = str(profile.get("adjudication_basis") or "").strip()
            if not label or not basis:
                raise ValueError(f"B1逐材料公开名称或裁决缺失：{row['ruler_name']} / {profile.get('material_id')}")
            if PUBLIC_FORBIDDEN_RE.search(" ".join((label, basis, str(profile.get("adjudication_boundary") or "")))):
                raise ValueError(f"B1逐材料公开裁决仍含内部术语：{row['ruler_name']} / {profile.get('material_id')}")
            if profile.get("adjudication_tags") != _public_tags(profile, status):
                raise ValueError(f"B1逐材料公开标签与正式状态不一致：{row['ruler_name']} / {profile.get('material_id')}")
            target_id = str(profile.get("absorbed_into_profile_id") or "")
            if status == "ABSORBED_SAME_LIFECYCLE":
                target = by_id.get(target_id)
                if target is None or target is profile or target.get("adjudication_status") not in {
                    "COUNTED_INDEPENDENT", "ZERO_NET"
                }:
                    raise ValueError(f"B1并入材料缺少唯一主profile：{row['ruler_name']} / {profile.get('material_id')}")
            elif target_id:
                raise ValueError(f"B1非并入材料错误保留主profile引用：{row['ruler_name']} / {profile.get('material_id')}")
        if row.get("public_adjudication_summary") != _public_summary(row):
            raise ValueError(f"B1人物级公开总括不是当前profile的机械汇总：{row['ruler_name']}")

    if payload.get("profile_adjudication_profile_count") != expected_profile_count:
        raise ValueError("B1逐材料公开裁决计数元数据不一致")
    if payload.get("profile_adjudication_status_counts") != dict(sorted(status_counts.items())):
        raise ValueError("B1逐材料公开裁决状态分布元数据不一致")


def _summary(row: dict[str, Any]) -> str:
    return str(row.get("public_adjudication_summary") or "未形成公开逐材料总括。")


def _profile_contribution(profile: dict[str, Any]) -> str:
    status = str(profile.get("adjudication_status") or "")
    if status == "ABSORBED_SAME_LIFECYCLE":
        return "并入同一运行链"
    if status == "BOUNDARY_CONTEXT":
        return "不单独计入"
    if status == "ZERO_NET":
        return "0（不增加净值）"
    return _weight_text(profile.get("signed_weight"))


def _source_label(source_title: str) -> str:
    title = source_title.replace("\\", "/").strip()
    if "/卷" in title and not title.startswith("docs/"):
        work, volume = title.rsplit("/", 1)
        return f"《{work.split('/')[-1]}·{volume}》"
    match = re.search(r"/([^/]+)/volume-(\d+)[^/]*$", title)
    if match:
        return f"《{match.group(1)}·卷{int(match.group(2)):03d}》"
    stem = Path(title).stem.replace(".source-summary", "")
    return f"《{stem}》"


def _material_basis(workspace_root: Path, payload: dict[str, Any]) -> dict[str, str]:
    materials = {}
    registry_root = workspace_root / "docs/公共成果/制度行政/01-制度行政计分材料登记"
    for registry_path in sorted(registry_root.glob("*.json")):
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        for material in registry.get("records") or []:
            materials[material["material_id"]] = material
    result = {}
    for row in payload["records"]:
        lines = []
        seen = set()
        profiles_by_material = {
            str(profile["material_id"]): profile
            for key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
            for profile in row.get(key) or []
        }
        for material_id in row.get("direct_material_ids") or []:
            material = materials.get(material_id)
            if material is None:
                profile = profiles_by_material.get(str(material_id), {})
                label = str(profile.get("public_label") or "行政运行机制")
                basis = str(profile.get("adjudication_basis") or "正式记录未另列史料摘录")
                source_line = f"《补充裁决材料》：{label}：{basis}"
                if source_line not in seen:
                    seen.add(source_line)
                    lines.append(f"  - {source_line}")
                continue
            material_line_count = len(lines)
            for evidence in material.get("evidence") or []:
                quote = _reader_text(str(evidence.get("exact_quote") or "").strip())
                if not quote or quote in seen:
                    continue
                source = str(evidence.get("source_title") or evidence.get("source_document_ref") or "史料")
                if (
                    "02-B1官僚治理与行政执行方向卡" in source
                    or re.search(
                        r"grade_basis|v20|v50|battle-adjudications|P\d+·L\d+·READY|分流说明：|口径：只收非战役事实",
                        quote,
                        flags=re.I,
                    )
                ):
                    continue
                seen.add(quote)
                lines.append(f"  - {_source_label(source)}：{quote}")
            if len(lines) == material_line_count:
                profile = profiles_by_material.get(str(material_id), {})
                label = str(profile.get("public_label") or "行政运行机制")
                basis = str(profile.get("adjudication_basis") or "正式记录未另列史料摘录")
                source_line = f"《补充裁决材料》：{label}：{basis}"
                if source_line not in seen:
                    seen.add(source_line)
                    lines.append(f"  - {source_line}")
        if not lines:
            raise ValueError(f"B1直接材料没有可展示原文：{row['ruler_name']}")
        result[row["ruler_name"]] = "- 材料依据：\n" + "\n".join(lines)
    return result


def render_b1_markdown(payload: dict[str, Any], workspace_root: Path) -> str:
    material_by_name = _material_basis(workspace_root, payload)
    position_cn = {
        "lower": "下位", "lower-middle": "中下位", "middle": "中位",
        "middle-upper": "中上位", "upper": "上位",
    }
    records = payload["records"]
    scores = sorted(float(row["direction_index"]) for row in records)
    lines = [
        "# B1官僚治理与行政执行方向卡", "", "## 一、方向卡结论", "",
        (
            f"B1已按新合同完成{len(records)}人全池门禁与档内位置重算，最高内部指数为"
            f"{records[0]['ruler_name']} {float(records[0]['direction_index']):.1f}，"
            f"平均{sum(scores) / len(scores):.1f}，中位数{scores[len(scores) // 2]:.1f}，"
            f"范围{scores[0]:.1f}—{scores[-1]:.1f}。"
        ),
        "", "> B1使用100刻度内部指数，不是第二项独立分值；正式结果按当前总则合成。", "",
        "## 二、评价边界", "",
        "评价官僚组织能否把政策与国家任务转化为可观察行政交付；官名、少数名臣、静态建制、宏观盛衰及邻项结果不得替代B1机制链。", "",
        "## 三、档位分布", "", "| 档位 | 人数 |", "|---|---:|",
    ]
    lines.extend(f"| {grade} | {payload['grade_distribution'].get(grade, 0)} |" for grade in INTERVALS)
    lines.extend([
        "", "## 四、185人方向卡排序", "",
        "| 排名 | 人物 | 政权 | 档位 | 运行摘要 | 内部指数/100 |",
        "|---:|---|---|---|---|---:|",
    ])
    for row in records:
        lines.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | "
            f"{row['grade']}（{position_cn[row['position']]}） | {_summary(row)} | "
            f"**{float(row['direction_index']):.1f}** |"
        )
    lines.extend(["", "## 五、逐人裁决与材料依据", ""])
    for row in records:
        lines.extend([
            f"### {row['ruler_name']}（{row['polity']}，分项第{row['rank']}名）", "",
            f"- 档位：{row['grade']}（{position_cn[row['position']]}）",
            f"- 内部指数：{float(row['direction_index']):.1f}/100",
            "- 结算依据：",
        ])
        lines.extend(
            f"  - **{point['role']}**：{str(point['text']).rstrip('。')}。"
            for point in _structured_basis(row)
        )
        lines.append("- 逐材料裁决：")
        target_labels = {
            str(profile.get("profile_id")): str(profile.get("public_label") or "行政运行机制")
            for profile in _iter_profiles(row)
        }
        for profile in _iter_profiles(row):
            tags = "、".join(str(tag) for tag in profile.get("adjudication_tags") or [])
            lines.append(
                f"  - **{profile['public_label']}**（{tags}；本项计入：{_profile_contribution(profile)}）"
            )
            lines.append(f"    - 裁决：{str(profile['adjudication_basis']).rstrip('。')}。")
            boundary = str(profile.get("adjudication_boundary") or "").strip()
            if boundary:
                lines.append(f"    - 边界：{boundary.rstrip('。')}。")
            target_id = str(profile.get("absorbed_into_profile_id") or "")
            if target_id:
                lines.append(f"    - 并入：{target_labels.get(target_id, '对应主运行链')}。")
        lines.extend([material_by_name[row["ruler_name"]], ""])
    return "\n".join(lines).rstrip() + "\n"


def render_method_markdown(method: dict[str, Any]) -> str:
    method_md = [
        "# 治理手段165分正式结算", "",
        "| 排名 | 人物 | 政权 | A/B1方向指数 | AB互补块/120 | B2方向指数→/45 | 正式得分/165 |",
        "|---:|---|---|---|---:|---|---:|",
    ]
    for row in method["records"]:
        method_md.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | A={float(row['A_direction_index']):.1f} / "
            f"B1={float(row['B1_direction_index']):.1f} | {float(row['AB_block_120']):.1f} | "
            f"{float(row['B2_direction_index']):.1f} → {float(row['B2_45']):.1f} | **{float(row['score']):.1f}** |"
        )
    return "\n".join(method_md) + "\n"


def render_result_markdown(result: dict[str, Any]) -> str:
    result_md = ["# C1—C4财政民生治理结果正式结算", ""]
    if result.get("governance_activation"):
        result_md.extend(["> C1—C4当前规范池已统一启用 GOVERNANCE-STATE-RECOVERY-V4；池外记录不进入当前综合榜。", ""])
    result_md.extend(["| 排名 | 人物 | 政权 | C1 | C2 | C3 | C4 | 治理结果分 |", "|---:|---|---|---|---|---|---|---:|"])
    for row in sorted(result["scores"], key=lambda r: (r["rank"], r["ruler_id"])):
        cells = " | ".join(f"{row[f'{axis}_band']}/{row[f'{axis}_score']:.1f}" for axis in FINANCE_PATHS)
        result_md.append(f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {cells} | **{row['score']:.1f}** |")
    return "\n".join(result_md) + "\n"


def render_handoff_markdown(handoff: dict[str, Any]) -> str:
    handoff_md = ["# 交接质量正式结算", "", "> D1行政连续性与D3权力交接等权合成；低侧封顶只在实际触发时附注在档位组合中。", "", "| 排名 | 人物 | 政权 | D1↔D3档位组合 | 合计/20 |", "|---:|---|---|---|---:|"]
    for row in handoff["records"]:
        combination = f"H{row['D1_level']}↔D3-{row['D3_level']}"
        if row["score"] < 2.0 * (row["D1_level"] + row["D3_level"]):
            combination += f"（低侧封顶{row['low_side_cap']:.1f}）"
        handoff_md.append(f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {combination} | **{row['score']:.1f}** |")
    return "\n".join(handoff_md) + "\n"


def render_total_markdown(total: dict[str, Any]) -> str:
    total_md = ["# 第二项治国净收益正式结算", ""]
    if total.get("governance_activation"):
        total_md.extend(["> 治理结果 C1—C4 当前规范池已统一启用 GOVERNANCE-STATE-RECOVERY-V4；第二项总表保留池外历史记录，综合榜仅读取 `COMPOSITE_READY` 对象。", ""])
    total_md.extend([
        "| 排名 | 人物 | 政权 | 治理手段/165 | C1/80 | C2/35 | C3/60 | C4 | 治理结果/202 | 交接/20 | 总分/387 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in total["records"]:
        total_md.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {float(row['governance_method_score']):.1f} | "
            f"{float(row['C1_score']):.1f} | {float(row['C2_score']):.1f} | {float(row['C3_score']):.1f} | "
            f"{float(row['C4_score']):.1f} | {float(row['governance_result_score']):.1f} | "
            f"{float(row['handoff_score']):.1f} | **{float(row['second_item_score']):.1f}** |"
        )
    return "\n".join(total_md) + "\n"


def verify_derived_views(workspace_root: Path) -> dict[str, Any]:
    specs = {
        METHOD_PATH: (render_method_markdown, "score"),
        TOTAL_PATH: (render_total_markdown, "second_item_score"),
        FINANCE_PATHS["C1"].with_name("05-治理结果正式结算.json"): (render_result_markdown, "score"),
        TOTAL_PATH.parent / "政权交接稳定/03-交接质量20分正式结算.json": (render_handoff_markdown, "score"),
    }
    for relative, (renderer, score_key) in specs.items():
        path = workspace_root / relative
        payload = load_json(path)
        rows = payload.get("records", payload.get("scores", []))
        scores = sorted((float(row[score_key]) for row in rows), reverse=True)
        for row in rows:
            if row["rank"] != scores.index(float(row[score_key])) + 1:
                raise ValueError(f"第二项汇总竞争排名错误：{relative.name} {row['ruler_name']}")
        if path.with_suffix(".md").read_text(encoding="utf-8") != renderer(payload):
            raise ValueError(f"第二项汇总Markdown与正式JSON不一致：{relative.name}")
    return {"reading_view_count": len(specs)}


def rebuild_derived(workspace_root: Path, *, write: bool = False, refresh_source: bool = True) -> dict[str, Any]:
    b1_path = workspace_root / B1_PATH
    b1 = load_json(b1_path)
    if refresh_source:
        b1 = refresh_b1_payload(b1)
    validate_gate_references(b1)
    b1_md = render_b1_markdown(b1, workspace_root)

    method_path = workspace_root / METHOD_PATH
    method = json.loads(method_path.read_text(encoding="utf-8"))
    a_by_id = {
        row["ruler_id"]: row
        for row in load_json(b1_path.with_name("01-A制度建设与实际运行方向卡.json"))["records"]
    }
    b1_by_id = {row["ruler_id"]: row for row in b1["records"]}
    b2_by_id = {
        row["ruler_id"]: row
        for row in load_json(b1_path.with_name("03-B2反馈纠错与权力约束方向卡.json"))["records"]
    }
    for row in method["records"]:
        row["A_direction_index"] = a_by_id[row["ruler_id"]]["direction_index"]
        row["B1_direction_index"] = b1_by_id[row["ruler_id"]]["direction_index"]
        row["B2_direction_index"] = b2_by_id[row["ruler_id"]]["direction_index"]
        row["B2_45"] = round(float(row["B2_direction_index"]) * 45 / 80 + 1e-9, 1)
        a, b = float(row["A_direction_index"]), float(row["B1_direction_index"])
        row["AB_block_120"] = round(0.8 * (max(a, b) + 0.5 * min(a, b)) + 1e-9, 1)
        row["score"] = round(float(row["AB_block_120"]) + float(row["B2_45"]), 1)
    _competition_ranks(method["records"], "score")
    method_md_text = render_method_markdown(method)

    total_path = workspace_root / TOTAL_PATH
    total = json.loads(total_path.read_text(encoding="utf-8"))
    finance_by_axis = {
        axis: {
            row["ruler_id"]: row
            for row in load_json(workspace_root / path)["scores"]
        }
        for axis, path in FINANCE_PATHS.items()
    }
    result_path = workspace_root / FINANCE_PATHS["C1"].with_name("05-治理结果正式结算.json")
    result = load_json(result_path)
    for row in result["scores"]:
        for axis, finance_rows in finance_by_axis.items():
            source = finance_rows[row["ruler_id"]]
            row[f"{axis}_score"] = float(source["score"])
            row[f"{axis}_band"] = source["main_band"]
        row["score"] = round(sum(row[f"{axis}_score"] for axis in FINANCE_PATHS), 1)
    scores = sorted((row["score"] for row in result["scores"]), reverse=True)
    for row in result["scores"]:
        row["rank"] = scores.index(row["score"]) + 1
    result.pop("v2_activation", None)
    result["governance_activation"] = load_json(workspace_root / FINANCE_PATHS["C1"]).get("governance_activation")
    result_md_text = render_result_markdown(result)

    handoff_root = total_path.parent / "政权交接稳定"
    handoff_path = handoff_root / "03-交接质量20分正式结算.json"
    handoff = load_json(handoff_path)
    d1 = {r["ruler_id"]: r for r in load_json(handoff_root / "01-D1继任行政连续性方向卡.json")["records"]}
    d3 = {r["ruler_id"]: r for r in load_json(handoff_root / "02-D3政权交接稳定方向卡.json")["records"]}
    caps = {0: 4.0, 1: 8.0, 2: 12.0, 3: 16.0, 4: 20.0, 5: 20.0}
    for row in handoff["records"]:
        row["D1_level"] = int(d1[row["ruler_id"]]["grade"][-1])
        row["D3_level"] = int(d3[row["ruler_id"]]["D3_grade"][-1])
        row["low_side_cap"] = caps[min(row["D1_level"], row["D3_level"])]
        row["score"] = min(2.0 * (row["D1_level"] + row["D3_level"]), row["low_side_cap"])
    _competition_ranks(handoff["records"], "score")
    handoff_by_id = {r["ruler_id"]: r for r in handoff["records"]}
    handoff_md_text = render_handoff_markdown(handoff)
    method_by_id = {row["ruler_id"]: row for row in method["records"]}
    for row in total["records"]:
        row["handoff_score"] = handoff_by_id[row["ruler_id"]]["score"]
        row["governance_method_score"] = method_by_id[row["ruler_id"]]["score"]
        for axis, finance_rows in finance_by_axis.items():
            row[f"{axis}_score"] = float(finance_rows[row["ruler_id"]]["score"])
            row[f"{axis}_band"] = finance_rows[row["ruler_id"]]["main_band"]
        row["governance_result_score"] = round(
            sum(float(row[f"{axis}_score"]) for axis in FINANCE_PATHS), 1
        )
        row["second_item_score"] = round(
            float(row["governance_method_score"])
            + float(row["governance_result_score"])
            + float(row["handoff_score"]),
            1,
        )
    _competition_ranks(total["records"], "second_item_score")
    total.pop("v2_activation", None)
    total["governance_activation"] = result.get("governance_activation")
    total_md_text = render_total_markdown(total)
    if write:
        if refresh_source:
            write_json(b1_path, b1, ruler_polities=load_ruler_polities(workspace_root))
            b1_path.with_suffix(".md").write_text(b1_md, encoding="utf-8", newline="\n")
        write_json(result_path, result)
        result_path.with_suffix(".md").write_text(result_md_text, encoding="utf-8", newline="\n")
        write_json(handoff_path, handoff)
        handoff_path.with_suffix(".md").write_text(handoff_md_text, encoding="utf-8", newline="\n")
        method_path.write_text(json.dumps(method, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        method_path.with_suffix(".md").write_text(method_md_text, encoding="utf-8", newline="\n")
        total_path.write_text(json.dumps(total, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        total_path.with_suffix(".md").write_text(total_md_text, encoding="utf-8", newline="\n")
    return {
        "record_count": len(b1["records"]),
        "grade_distribution": b1["grade_distribution"],
        "changed_method_records": len(method["records"]),
        "changed_total_records": len(total["records"]),
    }
