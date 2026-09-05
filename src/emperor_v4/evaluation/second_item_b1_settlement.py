from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json


B1_PATH = Path("docs/评分结算/第二项治国净收益/制度行政/02-B1官僚治理与行政执行方向卡.json")
METHOD_PATH = Path("docs/评分结算/第二项治国净收益/制度行政/04-治理手段165分正式结算.json")
TOTAL_PATH = Path("docs/评分结算/第二项治国净收益/01-第二项治国净收益正式结算.json")
FINANCE_PATHS = {
    "C1": Path("docs/评分结算/第二项治国净收益/财政民生/01-C1正式结算.json"),
    "C2": Path("docs/评分结算/第二项治国净收益/财政民生/02-C2正式结算.json"),
    "C3": Path("docs/评分结算/第二项治国净收益/财政民生/03-C3正式结算.json"),
    "C4": Path("docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json"),
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


def _structured_basis(row: dict[str, Any]) -> list[dict[str, str]]:
    position_cn = {
        "lower": "下位",
        "lower-middle": "中下位",
        "middle": "中位",
        "middle-upper": "中上位",
        "upper": "上位",
    }
    result = [{
        "role": "主档依据",
        "text": _reader_text(str(row["grade_basis"])),
    }, {
        "role": "档内位置依据",
        "text": (
            f"主档已定为{row['grade']}；有效生命周期权重合计扣除该档门槛占用"
            f"{THRESHOLDS[str(row['grade'])]:g}后，净余量为{float(row['position_residual']):g}，"
            f"仅据此确定档内{position_cn[row['position']]}（{float(row['direction_index']):.1f}）。"
            "净余量不用于跨档比较"
        ),
    }]
    directions: dict[str, list[dict[str, Any]]] = {"正向": [], "负向": []}
    for profile in active_groups(row):
        weight = float(profile.get("signed_weight") or 0.0)
        directions["正向" if weight > 0 else "负向"].append(profile)
    for label in ("正向", "负向"):
        if not directions[label]:
            result.append({"role": f"{label}依据（无可计M档）", "text": f"未闭合可计的{label}运行链"})
            continue
        for profile in directions[label]:
            suffix = ""
            severity = str(profile.get("severity") or "")
            if profile.get("M") == "M3" and "terminal" in severity:
                suffix = "，terminal"
            elif profile.get("M") == "M3" and "cross" in severity:
                suffix = "，cross"
            result.append({
                "role": f"{label}依据（{profile['M']}{suffix}）",
                "text": _reader_text(str(profile.get("mechanism") or profile["material_id"])),
            })
    return result


def refresh_b1_payload(payload: dict[str, Any]) -> dict[str, Any]:
    records = payload["records"]
    for row in records:
        ruler_id = str(row["ruler_id"])
        for key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile"):
            for profile in row.get(key) or []:
                profile.pop("position_depth_bonus", None)
                if profile.get("position_count_mode") == "representative_delivery_depth":
                    profile.pop("position_count_mode", None)
                profile["profile_id"] = profile_id(ruler_id, profile)
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
    contract = CONTRACT_PATH.read_bytes()
    for source in payload.get("source_documents") or []:
        if source.get("path") == CONTRACT_PATH.as_posix():
            source["byte_sha256"] = hashlib.sha256(contract).hexdigest()
    return payload


def validate_gate_references(payload: dict[str, Any]) -> None:
    validate_profile_contract(payload)
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


def _summary(row: dict[str, Any]) -> str:
    parts = []
    for label, predicate in (
        ("正", lambda weight: weight > 0),
        ("负", lambda weight: weight < 0),
    ):
        items = [
            f"{_reader_text(str(profile.get('mechanism') or profile['material_id']))}〔{label}M{profile['M'][1:]}〕"
            for profile in active_groups(row)
            if predicate(float(profile.get("signed_weight") or 0.0))
        ]
        if items:
            parts.append(f"{label}：" + "；".join(items))
    return "<br>".join(parts) or "无可计M档运行链"


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
                source_basis = profile.get("source_basis") or profile.get("source_refs")
                source_lines = source_basis if isinstance(source_basis, list) else [source_basis]
                for source_line in source_lines:
                    source_line = str(source_line or "").strip()
                    if not source_line or source_line in seen:
                        continue
                    seen.add(source_line)
                    lines.append(f"  - {source_line if source_line.startswith('《') else '《补充裁决材料》：' + source_line}")
                if not source_lines or not any(str(line or "").strip() for line in source_lines):
                    mechanism = str(profile.get("mechanism") or "补充裁决材料待登记")
                    if mechanism not in seen:
                        seen.add(mechanism)
                        lines.append(f"  - 《补充裁决材料》：{mechanism}")
                continue
            for evidence in material.get("evidence") or []:
                quote = _reader_text(str(evidence.get("exact_quote") or "").strip())
                if not quote or quote in seen:
                    continue
                seen.add(quote)
                source = str(evidence.get("source_title") or evidence.get("source_document_ref") or "史料")
                lines.append(f"  - {_source_label(source)}：{quote}")
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
        lines.extend([material_by_name[row["ruler_name"]], ""])
    return "\n".join(lines).rstrip() + "\n"


def rebuild_derived(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    b1_path = workspace_root / B1_PATH
    b1 = refresh_b1_payload(load_json(b1_path))
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
    method_md_text = "\n".join(method_md) + "\n"

    total_path = workspace_root / TOTAL_PATH
    total = json.loads(total_path.read_text(encoding="utf-8"))
    finance_by_axis = {
        axis: {
            row["ruler_id"]: row
            for row in load_json(workspace_root / path)["scores"]
        }
        for axis, path in FINANCE_PATHS.items()
    }
    method_by_id = {row["ruler_id"]: row for row in method["records"]}
    for row in total["records"]:
        row["governance_method_score"] = method_by_id[row["ruler_id"]]["score"]
        for axis, finance_rows in finance_by_axis.items():
            row[f"{axis}_score"] = float(finance_rows[row["ruler_id"]]["score"])
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
    total_md = [
        "# 第二项治国净收益387分正式结算", "",
        "| 排名 | 人物 | 政权 | 治理手段/165 | C1/80 | C2/35 | C3/60 | C4/-31—27 | 治理结果/202 | 交接/20 | 总分/387 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in total["records"]:
        total_md.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {float(row['governance_method_score']):.1f} | "
            f"{float(row['C1_score']):.1f} | {float(row['C2_score']):.1f} | {float(row['C3_score']):.1f} | "
            f"{float(row['C4_score']):.1f} | {float(row['governance_result_score']):.1f} | "
            f"{float(row['handoff_score']):.1f} | **{float(row['second_item_score']):.1f}** |"
        )
    total_md_text = "\n".join(total_md) + "\n"
    if write:
        write_json(b1_path, b1, ruler_polities=load_ruler_polities(workspace_root))
        b1_path.with_suffix(".md").write_text(b1_md, encoding="utf-8", newline="\n")
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
