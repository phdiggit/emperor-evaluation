from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIG_PATH = ROOT / "configs" / "i5b_trial_targets.json"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人自动结算草案.md"
RULES_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B自动结算规则敏感点清单.md"
FORMAL_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人正式定档落地表.md"

HIGH_VALUE_ANCHOR_KEYWORDS = (
    "幕府聚才",
    "顶级谏臣",
    "帝国级顶级将帅",
    "创业期军政支柱",
    "寒门/后进人才",
    "功臣安全秩序",
    "旧敌转用",
    "跨区域军政协同",
    "少年将才",
    "旧臣与宗室辅政",
    "日食求言",
    "边疆授权",
)

STARTUP_ANCHOR_KEYWORDS = (
    "创业期",
    "军政支柱",
    "军政授权",
    "大将军",
    "将帅",
    "持节",
    "专任",
    "分兵",
    "偏裨",
    "幽州",
    "兵",
)

BOUNDARY_ANCHOR_KEYWORDS = (
    "边界",
    "争议",
    "封顶",
    "中负",
    "弱负",
    "中正锚点",
)

DIRECT_SAFETY_KEYWORDS = (
    "群臣莫敢正言",
    "莫敢正言",
    "明显寒蝉",
    "寒蝉",
    "人才退缩",
    "谏臣安全受损",
    "能臣安全受损",
    "表达入口被破坏",
    "表达入口",
    "授权可信度破坏",
    "授权可信度",
    "表达安全受损",
    "安全受损",
    "不能容",
    "将下斩之",
    "捶扑",
    "牵曳",
    "直言",
)


RULE_SENSITIVE_POINTS = [
    {
        "rule_id": "RULE-I5B-BOUNDARY-WEAK-TO-MEDIUM",
        "rule_question": "弱负上调为中负的边界负证是否阻断极正或高位上探？",
        "default_rule": "不阻断；只降低置信度，不进入强负核心。",
        "why_it_matters": "避免把带 mitigation_flag / upper_bound_flag 的轻边界直接抬成拦截项。",
    },
    {
        "rule_id": "RULE-I5B-BOUNDARY-MEDIUM-TO-STRONG",
        "rule_question": "中负上调为强负的边界负证是否阻断极正或高位上探？",
        "default_rule": "阻断；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。",
        "why_it_matters": "把真正破坏表达安全、人才安全或授权可信度的负证与普通边界负证分开。",
    },
    {
        "rule_id": "RULE-I5B-SINGLE-DIMENSION-STRONG-POS-THREE-CORE",
        "rule_question": "单一维度强正是否可以上探极正？",
        "default_rule": "默认强正封顶；但同一维度内若至少存在三个强正核心且均为第五项B直接证据，则允许上探极正候选。",
        "why_it_matters": "把“单维强正封顶”与“单维但足够厚的三核心极正候选”区分开。",
    },
    {
        "rule_id": "RULE-I5B-ADJACENT-STRONG-NEG-RESIDUAL-DETAIL",
        "rule_question": "相邻项强负剥离后，第五项B剩余如何执行？",
        "default_rule": "大案本身严重不等于第五项B强负；若剥离后仅剩人才安全/表达安全的轻微外溢，则默认中负剩余；若出现群臣莫敢正言、明显寒蝉、人才退缩或授权可信度破坏等硬证，才保留强负核心。",
        "why_it_matters": "把政权安全、司法残酷、行政威慑与B项剩余影响分开。",
    },
    {
        "rule_id": "RULE-I5B-STRONG-NEG-CORE-SUPPRESSES-STRONG-POS",
        "rule_question": "强正底盘已经成立时，强负核心如何影响上探？",
        "default_rule": "保留强正基础，但自动标记为强正受压制，不上探极正；若强负核心呈结构性寒蝉，可进一步压低到中正受强负压制。",
        "why_it_matters": "防止强正掩盖对表达安全和人才安全的硬伤。",
    },
]

DIMENSION_RULES = [
    ("幕府聚才", "人才组织"),
    ("旧敌转用", "旧敌转用"),
    ("容谏", "容谏反馈"),
    ("反馈入口", "容谏反馈"),
    ("谏臣", "容谏反馈"),
    ("授权", "授权专任"),
    ("专任", "授权专任"),
    ("持节", "创业期军政授权"),
    ("分兵", "创业期军政授权"),
    ("将军", "创业期军政授权"),
    ("大将军", "创业期军政授权"),
    ("寒门/后进", "寒门后进"),
    ("寒门", "寒门后进"),
    ("后进", "寒门后进"),
    ("功臣安全", "功臣安全"),
    ("功臣", "功臣安全"),
    ("旧臣与宗室辅政", "辅政"),
    ("辅政", "辅政"),
    ("边疆授权", "边疆授权"),
    ("西域", "边疆授权"),
    ("楚狱", "楚狱牵连"),
    ("表达安全", "表达安全"),
    ("谏臣保护", "表达安全"),
    ("反谶", "思想/谏诤受压"),
    ("直言", "直言型人才"),
    ("身后信用反转", "同一对象反转"),
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def escape_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_table(headers: list[str], rows: list[dict[str, Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(row.get(header)) for header in headers) + " |")
    return "\n".join(lines)


def unique_values(values: list[object]) -> list[str]:
    results: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            cleaned = value.strip()
        else:
            cleaned = str(value).strip()
        if cleaned and cleaned not in results:
            results.append(cleaned)
    return results


def contains_any(value: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in value for keyword in keywords)


def card_text(card: dict[str, Any]) -> str:
    parts = [
        card.get("object_anchor"),
        card.get("evidence_role"),
        card.get("mitigation_flag"),
        card.get("upper_bound_flag"),
        card.get("cluster_role"),
        card.get("trigger_family"),
        card.get("cross_item_split"),
        card.get("quote_short"),
    ]
    return " ".join(str(part) for part in parts if part)


def infer_dimension(card: dict[str, Any]) -> str:
    anchor = str(card.get("object_anchor") or "")
    trigger_family = str(card.get("trigger_family") or "")
    text = f"{anchor} {trigger_family}"

    for keyword, dimension in DIMENSION_RULES:
        if keyword in text:
            return dimension

    if contains_any(text, ("军政", "将才", "分兵", "持节", "大将军", "将军", "总管")):
        return "创业期军政授权"
    if contains_any(text, ("纳言", "纳谏", "反馈入口", "求言")):
        return "容谏反馈"
    if contains_any(text, ("人才", "用人", "任用", "拔擢", "识人")):
        return "识人任用"
    return trigger_family or anchor or "未分类"


def is_startup_card(card: dict[str, Any]) -> bool:
    text = f"{card.get('object_anchor') or ''} {card.get('trigger_family') or ''}"
    return contains_any(text, STARTUP_ANCHOR_KEYWORDS)


def is_high_value_anchor(card: dict[str, Any]) -> bool:
    text = f"{card.get('object_anchor') or ''} {card.get('trigger_family') or ''} {card.get('evidence_role') or ''}"
    return contains_any(text, HIGH_VALUE_ANCHOR_KEYWORDS)


def is_boundary_card(card: dict[str, Any]) -> bool:
    text = f"{card.get('object_anchor') or ''} {card.get('evidence_role') or ''} {card.get('cluster_role') or ''} {card.get('trigger_family') or ''}"
    return contains_any(text, BOUNDARY_ANCHOR_KEYWORDS) or bool(card.get("mitigation_flag")) or bool(card.get("upper_bound_flag"))


def has_direct_safety_hard_evidence(cards: list[dict[str, Any]]) -> bool:
    for card in cards:
        text = card_text(card)
        if contains_any(text, DIRECT_SAFETY_KEYWORDS):
            return True
    return False


def safe_join(values: list[object]) -> str:
    return "；".join(unique_values([value for value in values if value not in (None, "")]))


def classify_negative_boundary(
    linked_cards: list[dict[str, Any]],
    cluster_candidate_strength: int | None = None,
) -> dict[str, Any]:
    max_strength = max((int(card.get("strength") or 0) for card in linked_cards), default=0)
    direct_safety_hard = has_direct_safety_hard_evidence(linked_cards)
    has_boundary = any(is_boundary_card(card) for card in linked_cards)
    cluster_strength = int(cluster_candidate_strength or 0)

    if direct_safety_hard:
        return {
            "boundary_tier": "medium_to_strong",
            "residual_level": "strong",
            "blocking_extreme": True,
            "auto_cluster_result": "强负候选",
            "negative_core": True,
            "hard_evidence": True,
        }

    if max_strength >= 3 or cluster_strength >= 3:
        return {
            "boundary_tier": "adjacent_item_medium_residual",
            "residual_level": "medium",
            "blocking_extreme": False,
            "auto_cluster_result": "中负边界",
            "negative_core": False,
            "hard_evidence": False,
        }

    if max_strength == 2:
        return {
            "boundary_tier": "weak_to_medium",
            "residual_level": "medium",
            "blocking_extreme": False,
            "auto_cluster_result": "中负边界",
            "negative_core": False,
            "hard_evidence": False,
        }

    if max_strength == 1:
        return {
            "boundary_tier": "weak_to_medium",
            "residual_level": "weak",
            "blocking_extreme": False,
            "auto_cluster_result": "弱负边界",
            "negative_core": False,
            "hard_evidence": False,
        }

    if has_boundary:
        return {
            "boundary_tier": "weak_to_medium",
            "residual_level": "none",
            "blocking_extreme": False,
            "auto_cluster_result": "未定",
            "negative_core": False,
            "hard_evidence": False,
        }

    return {
        "boundary_tier": "none",
        "residual_level": "none",
        "blocking_extreme": False,
        "auto_cluster_result": "未定",
        "negative_core": False,
        "hard_evidence": False,
    }


def build_rule_sensitive_points(report: dict[str, Any]) -> list[dict[str, str]]:
    points: list[dict[str, str]] = []
    negative_boundary_tier = str(report.get("negative_boundary_tier") or "none")

    if negative_boundary_tier == "weak_to_medium":
        points.append(
            {
                "rule": "弱负上调中负边界",
                "decision": "不阻断极正或高位上探；只降低置信度，不进入强负核心。",
            }
        )
    elif negative_boundary_tier == "medium_to_strong":
        points.append(
            {
                "rule": "中负上调强负边界",
                "decision": "阻断极正/高位上探；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。",
            }
        )
    elif negative_boundary_tier == "adjacent_item_medium_residual":
        points.append(
            {
                "rule": "相邻项主导剥离",
                "decision": "大案本身严重不等于第五项B强负；剥离后只保留 B 项剩余影响。",
            }
        )

    if bool(report.get("single_dimension_flag")) and int(report.get("strong_positive_count") or 0) >= 3:
        points.append(
            {
                "rule": "单维强正三核心",
                "decision": "同一维度内至少三个强正核心且均为第五项B直接证据时，才允许上探极正候选。",
            }
        )

    if bool(report.get("has_strong_negative_core")):
        points.append(
            {
                "rule": "强负核心压制强正",
                "decision": "保留强正基础，但自动标记为强正受压制，不上探极正。",
            }
        )

    if negative_boundary_tier == "adjacent_item_medium_residual":
        points.append(
            {
                "rule": "B项剩余默认中负",
                "decision": "默认中负剩余；只有直接寒蝉、群臣莫敢正言、人才退缩或授权可信度破坏等硬证时，才保留强负核心。",
            }
        )

    return points


def build_formal_band_draft(report: dict[str, Any]) -> str:
    auto_band_direction = str(report.get("auto_band_direction") or "")
    formal_band_map = {
        "高位强正，上探极正候选": "极正候选 / 高位强正上探极正",
        "强正受压制，不上探极正": "强正受压制",
        "强正封顶，不上探极正": "强正封顶",
        "中正受中负压制": "中正受中负压制",
        "中正受强负压制": "中正受强负压制",
    }
    return formal_band_map.get(auto_band_direction, auto_band_direction or "待定")


def format_rule_resolutions(report: dict[str, Any]) -> str:
    points = report.get("rule_sensitive_points") or []
    if not points:
        return "无"
    resolutions = []
    for point in points:
        rule = str(point.get("rule") or "未命名规则")
        decision = str(point.get("decision") or "").rstrip("。")
        if decision:
            resolutions.append(f"{rule}：已按规则解决（{decision}）")
        else:
            resolutions.append(f"{rule}：已按规则解决")
    return "；".join(resolutions)


def format_remaining_questions(report: dict[str, Any]) -> str:
    questions: list[str] = []
    if str(report.get("negative_boundary_tier") or "") == "none":
        questions.append("暂无新增规则问题")
    if bool(report.get("has_extreme_negative_core")) and not bool(report.get("negative_boundary_blocking")):
        questions.append("极负核心是否需要单列更强阻断规则")
    return "；".join(questions) if questions else "无"


def format_score_stage_prerequisites(report: dict[str, Any]) -> str:
    if str(report.get("auto_band_direction") or "") == "自动草案待规则复核":
        return "需另建第五项B档位到分值映射，并经规则级确认；本表不得直接推分。"
    return "需另建第五项B档位到分值映射，并经规则级确认；本表不得直接推分。"


def summarize_positive_basis(report: dict[str, Any]) -> str:
    anchors = safe_join(report.get("positive_anchor_names") or [])
    dimensions = safe_join(report.get("positive_dimensions") or [])
    strength = int(report.get("strong_positive_count") or 0)
    coverage = int(report.get("coverage_dimension_count") or 0)
    parts = [
        f"{strength}个强正核心",
        f"{coverage}个正向维度" if coverage else "正向维度未单列",
    ]
    if anchors:
        parts.append(f"对象锚点：{anchors}")
    if dimensions:
        parts.append(f"维度摘要：{dimensions}")
    return "；".join(parts)


def summarize_negative_pressure(report: dict[str, Any]) -> str:
    tier = str(report.get("negative_boundary_tier") or "none")
    blocking = bool(report.get("negative_boundary_blocking"))
    residual = str(report.get("cross_item_split_residual_level") or "none")
    pressure_map = {
        "weak_to_medium": "弱负升中负边界",
        "medium_to_strong": "中负升强负边界",
        "adjacent_item_medium_residual": "相邻项剥离后的中负剩余",
        "none": "无明确负压",
    }
    parts = [pressure_map.get(tier, tier)]
    parts.append("阻断极正" if blocking else "不阻断极正")
    parts.append(f"残余层级：{residual}")
    return "；".join(parts)


def evaluate_cluster(
    cluster: dict[str, Any],
    evidence_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    linked_evidence_ids = list(cluster.get("linked_evidence_ids") or [])
    linked_cards = [evidence_lookup[evidence_id] for evidence_id in linked_evidence_ids if evidence_id in evidence_lookup]

    linked_object_anchors = unique_values([card.get("object_anchor") for card in linked_cards])
    linked_evidence_roles = unique_values([card.get("evidence_role") for card in linked_cards])
    linked_trigger_families = unique_values([card.get("trigger_family") for card in linked_cards])
    linked_strengths = unique_values([card.get("strength") for card in linked_cards])
    linked_upper_bound_flags = unique_values([card.get("upper_bound_flag") for card in linked_cards])
    linked_mitigation_flags = unique_values([card.get("mitigation_flag") for card in linked_cards])
    linked_cluster_roles = unique_values([card.get("cluster_role") for card in linked_cards])
    linked_cross_item_splits = unique_values(
        [cluster.get("cross_item_split", "")] + [card.get("cross_item_split") for card in linked_cards]
    )

    negative_profile = classify_negative_boundary(linked_cards, cluster.get("candidate_strength"))
    residual_level = "none"
    if cluster.get("polarity") == "negative":
        residual_level = negative_profile["residual_level"]
    elif cluster.get("polarity") == "positive":
        residual_level = "strong" if int(cluster.get("candidate_strength") or 0) >= 3 else "medium"

    if cluster.get("polarity") == "positive":
        auto_cluster_result = "强正候选" if int(cluster.get("candidate_strength") or 0) >= 3 else "中正增厚"
    else:
        auto_cluster_result = negative_profile["auto_cluster_result"]

    return {
        "cluster_id": cluster.get("cluster_id"),
        "person": cluster.get("person"),
        "polarity": cluster.get("polarity"),
        "cluster_type": cluster.get("cluster_type"),
        "candidate_strength": cluster.get("candidate_strength"),
        "linked_evidence_ids": linked_evidence_ids,
        "linked_object_anchors": linked_object_anchors,
        "linked_evidence_roles": linked_evidence_roles,
        "linked_trigger_families": linked_trigger_families,
        "linked_strengths": linked_strengths,
        "linked_upper_bound_flags": linked_upper_bound_flags,
        "linked_mitigation_flags": linked_mitigation_flags,
        "linked_cluster_roles": linked_cluster_roles,
        "cross_item_split_signals": linked_cross_item_splits,
        "residual_level": residual_level,
        "boundary_tier": negative_profile["boundary_tier"] if cluster.get("polarity") == "negative" else "none",
        "blocking_extreme": negative_profile["blocking_extreme"] if cluster.get("polarity") == "negative" else False,
        "negative_core": negative_profile["negative_core"] if cluster.get("polarity") == "negative" else False,
        "has_high_value_object_anchor": any(is_high_value_anchor(card) for card in linked_cards),
        "has_boundary_evidence": any(is_boundary_card(card) for card in linked_cards),
        "has_mitigation_flag": bool(linked_mitigation_flags),
        "has_upper_bound_flag": bool(linked_upper_bound_flags),
        "auto_cluster_result": auto_cluster_result,
        "summary": cluster.get("summary"),
    }


def evaluate_person(
    person: str,
    cluster_rows: list[dict[str, Any]],
    evidence_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    person_cards = [card for card in evidence_lookup.values() if card.get("person") == person and card.get("subitem") == "第五项B"]
    positive_cards = [card for card in person_cards if card.get("polarity") == "positive"]
    negative_cards = [card for card in person_cards if card.get("polarity") == "negative"]

    positive_dimensions = unique_values([infer_dimension(card) for card in positive_cards])
    positive_anchor_names = unique_values([card.get("object_anchor") for card in positive_cards])
    negative_anchor_names = unique_values([card.get("object_anchor") for card in negative_cards])
    positive_cluster_ids = unique_values([row.get("cluster_id") for row in cluster_rows if row.get("person") == person and row.get("polarity") == "positive"])
    negative_cluster_ids = unique_values([row.get("cluster_id") for row in cluster_rows if row.get("person") == person and row.get("polarity") == "negative"])

    strong_positive_count = sum(int(card.get("strength") or 0) >= 3 for card in positive_cards)
    extreme_positive_count = sum(int(card.get("strength") or 0) == 4 for card in positive_cards)
    strong_negative_count = sum(int(card.get("strength") or 0) >= 3 for card in negative_cards)
    extreme_negative_count = sum(int(card.get("strength") or 0) == 4 for card in negative_cards)
    core_positive_count = sum("核心" in str(card.get("evidence_role") or "") or "核心" in str(card.get("cluster_role") or "") for card in positive_cards)
    core_negative_count = sum("核心" in str(card.get("evidence_role") or "") or "核心" in str(card.get("cluster_role") or "") for card in negative_cards)

    startup_positive_cards = [card for card in positive_cards if is_startup_card(card)]
    startup_share = round(len(startup_positive_cards) / len(positive_cards), 2) if positive_cards else 0.0
    positive_dimension_count = len(positive_dimensions)
    single_dimension_flag = startup_share >= 0.8 and positive_dimension_count <= 2
    has_high_value_object_anchor = any(is_high_value_anchor(card) for card in person_cards)
    has_boundary_evidence = any(is_boundary_card(card) for card in negative_cards)
    has_mitigation_flag = any(bool(card.get("mitigation_flag")) for card in person_cards)
    has_upper_bound_flag = any(bool(card.get("upper_bound_flag")) for card in person_cards)
    negative_profile = classify_negative_boundary(negative_cards)
    negative_residual_level = negative_profile["residual_level"]
    negative_boundary_tier = negative_profile["boundary_tier"]
    negative_boundary_blocking = negative_profile["blocking_extreme"]
    has_strong_negative_core = bool(negative_profile["negative_core"]) or (
        strong_negative_count > 0 and negative_boundary_tier == "medium_to_strong"
    )
    has_extreme_negative_core = extreme_negative_count > 0
    cross_item_split_required = any(bool(card.get("cross_item_split")) for card in person_cards)
    positive_extreme_allowed = strong_positive_count >= 3 or (positive_dimension_count >= 3 and not single_dimension_flag)
    rule_sensitive_points = build_rule_sensitive_points(
        {
            "negative_boundary_tier": negative_boundary_tier,
            "single_dimension_flag": single_dimension_flag,
            "strong_positive_count": strong_positive_count,
            "has_strong_negative_core": has_strong_negative_core,
        }
    )

    max_positive_strength = max((int(card.get("strength") or 0) for card in positive_cards), default=0)
    positive_cluster_rows = [evaluate_cluster(row, evidence_lookup) for row in cluster_rows if row.get("person") == person and row.get("polarity") == "positive"]
    negative_cluster_rows = [evaluate_cluster(row, evidence_lookup) for row in cluster_rows if row.get("person") == person and row.get("polarity") == "negative"]
    positive_cluster_rows.sort(key=lambda row: (-int(row["candidate_strength"] or 0), str(row["cluster_id"])))
    negative_cluster_rows.sort(key=lambda row: (-int(row["candidate_strength"] or 0), str(row["cluster_id"])))

    if max_positive_strength >= 3 and negative_boundary_blocking:
        auto_band_direction = "强正受压制，不上探极正"
    elif max_positive_strength >= 3 and positive_extreme_allowed and negative_boundary_tier in {"none", "weak_to_medium", "adjacent_item_medium_residual"}:
        auto_band_direction = "高位强正，上探极正候选"
    elif max_positive_strength >= 3:
        auto_band_direction = "强正封顶，不上探极正"
    elif max_positive_strength <= 2 and negative_residual_level == "medium":
        auto_band_direction = "中正受中负压制"
    elif max_positive_strength <= 2 and negative_residual_level in {"strong", "extreme"}:
        auto_band_direction = "中正受强负压制"
    else:
        auto_band_direction = "自动草案待规则复核"

    if auto_band_direction == "高位强正，上探极正候选":
        confidence = "high" if negative_boundary_tier == "none" else "high_mid"
    elif auto_band_direction == "强正封顶，不上探极正":
        confidence = "medium_high" if max_positive_strength >= 3 else "medium"
    elif auto_band_direction == "强正受压制，不上探极正":
        confidence = "medium_high"
    elif auto_band_direction == "中正受中负压制":
        confidence = "medium"
    elif auto_band_direction == "中正受强负压制":
        confidence = "medium"
    else:
        confidence = "medium_low"

    return {
        "person": person,
        "positive_cluster_ids": positive_cluster_ids,
        "negative_cluster_ids": negative_cluster_ids,
        "positive_dimensions": positive_dimensions,
        "positive_anchor_names": positive_anchor_names,
        "negative_anchor_names": negative_anchor_names,
        "core_positive_count": core_positive_count,
        "strong_positive_count": strong_positive_count,
        "extreme_positive_count": extreme_positive_count,
        "core_negative_count": core_negative_count,
        "strong_negative_count": strong_negative_count,
        "extreme_negative_count": extreme_negative_count,
        "coverage_dimension_count": positive_dimension_count,
        "single_dimension_flag": single_dimension_flag,
        "startup_positive_share": startup_share,
        "has_high_value_object_anchor": has_high_value_object_anchor,
        "has_boundary_evidence": has_boundary_evidence,
        "has_mitigation_flag": has_mitigation_flag,
        "has_upper_bound_flag": has_upper_bound_flag,
        "has_strong_negative_core": has_strong_negative_core,
        "has_extreme_negative_core": has_extreme_negative_core,
        "negative_boundary_tier": negative_boundary_tier,
        "negative_boundary_blocking": negative_boundary_blocking,
        "cross_item_split_required": cross_item_split_required,
        "cross_item_split_residual_level": negative_residual_level,
        "auto_band_direction": auto_band_direction,
        "confidence": confidence,
        "rule_sensitive_points": rule_sensitive_points,
        "positive_cluster_rows": positive_cluster_rows,
        "negative_cluster_rows": negative_cluster_rows,
        "person_cards": person_cards,
    }


def render_rule_sensitive_points() -> str:
    rows = []
    for rule in RULE_SENSITIVE_POINTS:
        rows.append(
            {
                "rule_id": rule["rule_id"],
                "rule_question": rule["rule_question"],
                "default_rule": rule["default_rule"],
                "why_it_matters": rule["why_it_matters"],
            }
        )

    lines = [
        "# 第五项B自动结算规则敏感点清单",
        "",
        "本文件只列抽象规则问题和默认处理方式，不审人物个案、不计分、不排名。",
        "",
        markdown_table(["rule_id", "rule_question", "default_rule", "why_it_matters"], rows),
        "",
        "## 规则使用方式",
        "",
        "1. 先看规则问题是否被当前 cluster 命中。",
        "2. 弱负升中负的边界只降置信度，不阻断极正/高位上探，也不进入强负核心。",
        "3. 中负升强负的边界阻断极正/高位上探，只在有明确突破中负封顶的硬证时进入强负核心。",
        "4. 若规则仍无法抽象化，才把问题后移到规则层审核。",
    ]
    return "\n".join(lines) + "\n"


def render_person_section(report: dict[str, Any]) -> str:
    person = report["person"]
    positive_rows = report["positive_cluster_rows"]
    negative_rows = report["negative_cluster_rows"]
    cluster_rows = positive_rows + negative_rows

    sections = [
        f"## {person}",
        "",
        "### 证据簇自动结算",
        "",
        markdown_table(
            [
                "cluster_id",
                "polarity",
                "cluster_type",
                "candidate_strength",
                "linked_object_anchors",
                "linked_evidence_roles",
                "linked_trigger_families",
                "linked_strengths",
                "linked_upper_bound_flags",
                "linked_mitigation_flags",
                "linked_cluster_roles",
                "cross_item_split_signals",
                "boundary_tier",
                "blocking_extreme",
                "residual_level",
                "auto_cluster_result",
            ],
            cluster_rows,
        ),
        "",
        "### 自动特征",
        "",
        markdown_table(
            [
                "field",
                "value",
            ],
            [
                {"field": "positive_cluster_ids", "value": report["positive_cluster_ids"]},
                {"field": "negative_cluster_ids", "value": report["negative_cluster_ids"]},
                {"field": "core_positive_count", "value": report["core_positive_count"]},
                {"field": "strong_positive_count", "value": report["strong_positive_count"]},
                {"field": "extreme_positive_count", "value": report["extreme_positive_count"]},
                {"field": "core_negative_count", "value": report["core_negative_count"]},
                {"field": "strong_negative_count", "value": report["strong_negative_count"]},
                {"field": "extreme_negative_count", "value": report["extreme_negative_count"]},
                {"field": "coverage_dimension_count", "value": report["coverage_dimension_count"]},
                {"field": "single_dimension_flag", "value": report["single_dimension_flag"]},
                {"field": "startup_positive_share", "value": report["startup_positive_share"]},
                {"field": "has_high_value_object_anchor", "value": report["has_high_value_object_anchor"]},
                {"field": "has_boundary_evidence", "value": report["has_boundary_evidence"]},
                {"field": "has_mitigation_flag", "value": report["has_mitigation_flag"]},
                {"field": "has_upper_bound_flag", "value": report["has_upper_bound_flag"]},
                {"field": "has_strong_negative_core", "value": report["has_strong_negative_core"]},
                {"field": "has_extreme_negative_core", "value": report["has_extreme_negative_core"]},
                {"field": "negative_boundary_tier", "value": report["negative_boundary_tier"]},
                {"field": "negative_boundary_blocking", "value": report["negative_boundary_blocking"]},
                {"field": "cross_item_split_required", "value": report["cross_item_split_required"]},
                {"field": "cross_item_split_residual_level", "value": report["cross_item_split_residual_level"]},
            ],
        ),
        "",
        "### 触发的规则敏感点",
        "",
    ]

    for point in report["rule_sensitive_points"]:
        sections.append(f"- {point['rule']}：{point['decision']}")

    sections.extend(
        [
            "",
            "### 自动结算结论",
            "",
            f"- band_direction：{report['auto_band_direction']}",
            f"- confidence：{report['confidence']}",
            "- 不回填相邻项说明：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。",
        ]
    )

    return "\n".join(sections) + "\n"


def render_formal_person_section(report: dict[str, Any]) -> str:
    person = report["person"]
    sections = [
        f"## {person}",
        "",
        "### 正式档位落地",
        "",
        f"- 自动结算来源：{report['auto_band_direction']} / {report['confidence']}",
        f"- 正式档位草案：{build_formal_band_draft(report)}",
        f"- 不出分说明：本阶段只落档位方向，不生成分数。",
        f"- 不排名说明：本阶段不生成排名或名次。",
        "",
        "### 正向证据组摘要",
        "",
        f"- {summarize_positive_basis(report)}",
        "",
        "### 负向证据组摘要",
        "",
        f"- {summarize_negative_pressure(report)}",
        "",
        "### 已按规则解决的敏感点",
        "",
        f"- {format_rule_resolutions(report)}",
        "",
        "### 相邻项剥离说明",
        "",
        "- 战功、政绩、边疆收益、治世光环、政权安全与司法残酷均不回填第五项B。",
        "",
        "### 规则状态",
        "",
        f"- remaining_rule_questions：{format_remaining_questions(report)}",
        f"- score_stage_prerequisites：{format_score_stage_prerequisites(report)}",
        f"- not_scored_flag：是",
        f"- ranking_suppressed_flag：是",
    ]
    return "\n".join(sections) + "\n"


def render_auto_adjudication() -> str:
    config = read_json(CONFIG_PATH)
    targets = list(config.get("targets") or [])
    evidence_cards = read_jsonl(DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = read_jsonl(DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    cluster_lookup = {row["cluster_id"]: row for row in evidence_clusters if row.get("cluster_id")}
    person_reports = [evaluate_person(person, evidence_clusters, evidence_lookup) for person in targets]

    overview_rows = []
    for report in person_reports:
        rule_points = report["rule_sensitive_points"]
        overview_rows.append(
            {
                "person": report["person"],
                "positive_cluster_ids": safe_join(report["positive_cluster_ids"]),
                "negative_cluster_ids": safe_join(report["negative_cluster_ids"]),
                "auto_band_direction": report["auto_band_direction"],
                "confidence": report["confidence"],
                "negative_boundary_tier": report["negative_boundary_tier"],
                "negative_boundary_blocking": report["negative_boundary_blocking"],
                "rule_sensitive_points": "；".join(point["rule"] for point in rule_points),
            }
        )

    lines = [
        "# 第五项B三人自动结算草案",
        "",
        "本文件由现有 `evidence_cards` / `evidence_clusters` / `thematic_anchors` 规则派生，只输出 band direction、confidence 与规则敏感点，不生成分数、排名或总榜。",
        "",
            "## 自动结算总览",
            "",
            markdown_table(
                [
                    "person",
                    "positive_cluster_ids",
                    "negative_cluster_ids",
                    "auto_band_direction",
                    "confidence",
                    "negative_boundary_tier",
                    "negative_boundary_blocking",
                    "rule_sensitive_points",
                ],
                overview_rows,
            ),
        "",
        "## 逐人自动草案",
        "",
    ]

    for report in person_reports:
        lines.append(render_person_section(report))

    return "\n".join(lines).rstrip() + "\n"


def render_formal_landing_table() -> str:
    config = read_json(CONFIG_PATH)
    targets = list(config.get("targets") or [])
    evidence_cards = read_jsonl(DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = read_jsonl(DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    person_reports = [evaluate_person(person, evidence_clusters, evidence_lookup) for person in targets]

    overview_rows = []
    for report in person_reports:
        rule_points = report["rule_sensitive_points"]
        overview_rows.append(
            {
                "person": report["person"],
                "auto_band_direction": report["auto_band_direction"],
                "formal_band_draft": build_formal_band_draft(report),
                "confidence": report["confidence"],
                "positive_basis": summarize_positive_basis(report),
                "negative_pressure": summarize_negative_pressure(report),
                "negative_boundary_tier": report["negative_boundary_tier"],
                "negative_boundary_blocking": report["negative_boundary_blocking"],
                "rule_sensitive_points_resolved": format_rule_resolutions({"rule_sensitive_points": rule_points}),
                "remaining_rule_questions": format_remaining_questions(report),
                "score_stage_prerequisites": format_score_stage_prerequisites(report),
                "not_scored_flag": "是",
                "ranking_suppressed_flag": "是",
            }
        )

    lines = [
        "# 第五项B三人正式定档落地表",
        "",
        "本文件由自动结算草案与规则级复核结果派生，只输出正式档位草案，不生成分数、排名或总榜。",
        "",
        "## 一、正式落地总览",
        "",
        markdown_table(
            [
                "person",
                "auto_band_direction",
                "formal_band_draft",
                "confidence",
                "positive_basis",
                "negative_pressure",
                "negative_boundary_tier",
                "negative_boundary_blocking",
                "rule_sensitive_points_resolved",
                "remaining_rule_questions",
                "score_stage_prerequisites",
                "not_scored_flag",
                "ranking_suppressed_flag",
            ],
            overview_rows,
        ),
        "",
        "## 二、逐人落地说明",
        "",
    ]

    for report in person_reports:
        lines.append(render_formal_person_section(report))

    return "\n".join(lines).rstrip() + "\n"


def export_auto_adjudication() -> tuple[Path, Path]:
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FORMAL_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    EXPORT_PATH.write_text(render_auto_adjudication(), encoding="utf-8")
    RULES_EXPORT_PATH.write_text(render_rule_sensitive_points(), encoding="utf-8")
    FORMAL_EXPORT_PATH.write_text(render_formal_landing_table(), encoding="utf-8")
    return EXPORT_PATH, RULES_EXPORT_PATH


def main() -> int:
    export_path, rules_path = export_auto_adjudication()
    print(f"exported {export_path}")
    print(f"exported {rules_path}")
    print(f"exported {FORMAL_EXPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
