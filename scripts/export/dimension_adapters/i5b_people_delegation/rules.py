from __future__ import annotations

from typing import Any

from export.dimension_export.evidence_index import unique_values


TRIAL_SCORE_MAP = {
    "极正候选 / 高位强正上探极正": {"score_range": "94-100", "trial_score": 97},
    "强正受压制": {"score_range": "72-80", "trial_score": 76},
    "中正受中负压制": {"score_range": "48-57", "trial_score": 53},
    "强正封顶": {"score_range": "68-75", "trial_score": 72},
    "中正受强负压制": {"score_range": "38-47", "trial_score": 43},
    "强正": {"score_range": "78-85", "trial_score": 82},
    "中正": {"score_range": "58-67", "trial_score": 63},
    "中负": {"score_range": "20-37", "trial_score": 29},
    "强负": {"score_range": "0-19", "trial_score": 10},
}


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


POSITIVE_CORE_KEYWORDS = {
    "识人任用": (
        "识人",
        "择人",
        "拔擢",
        "任用",
        "用人",
        "人才组织",
        "幕府聚才",
        "寒门",
        "后进",
        "旧敌转用",
    ),
    "授权专任": (
        "授权",
        "专任",
        "持节",
        "分兵",
        "边疆授权",
        "军政授权",
        "权责清晰",
    ),
    "人才生态": (
        "人才生态",
        "表达安全",
        "反馈入口",
        "容谏",
        "谏臣",
        "功臣安全",
        "异质人才",
        "保护",
        "纠错环境",
    ),
}
REQUIRED_POSITIVE_RULE_CORES = tuple(POSITIVE_CORE_KEYWORDS)


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
        "default_rule": "默认强正封顶；但同一维度内若至少存在三个强正核心、均为第五项B直接证据，且覆盖识人任用、授权专任、人才生态三类核心，才允许上探极正候选。",
        "why_it_matters": "把“单维同类证据堆叠封顶”与“单维但覆盖三核心的极正候选”区分开。",
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


def infer_positive_rule_core(card: dict[str, Any]) -> str | None:
    primary_text = " ".join(
        str(part)
        for part in (
            card.get("evidence_role"),
            card.get("cluster_role"),
            card.get("quote_short"),
            card.get("scoring_effect"),
        )
        if part
    )
    for core, keywords in POSITIVE_CORE_KEYWORDS.items():
        if contains_any(primary_text, keywords):
            return core

    text = card_text(card)
    for core, keywords in POSITIVE_CORE_KEYWORDS.items():
        if contains_any(text, keywords):
            return core
    return None


def infer_positive_rule_cores(cards: list[dict[str, Any]]) -> list[str]:
    strong_core_cards = [
        card
        for card in cards
        if int(card.get("strength") or 0) >= 3
        and ("核心" in str(card.get("evidence_role") or "") or "核心" in str(card.get("cluster_role") or ""))
    ]
    return unique_values([infer_positive_rule_core(card) for card in strong_core_cards])


def has_required_positive_rule_cores(cards: list[dict[str, Any]]) -> bool:
    cores = set(infer_positive_rule_cores(cards))
    return set(REQUIRED_POSITIVE_RULE_CORES).issubset(cores)


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
        if bool(report.get("positive_three_core_coverage")):
            decision = "同一维度内至少三个强正核心，且覆盖识人任用、授权专任、人才生态三类核心，允许上探极正候选。"
        else:
            decision = "虽有同一维度三条强正，但三核心覆盖不足；默认强正封顶，不上探极正。"
        points.append(
            {
                "rule": "单维强正三核心",
                "decision": decision,
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


def build_trial_score_draft(report: dict[str, Any]) -> dict[str, Any]:
    formal_band_draft = build_formal_band_draft(report)
    return TRIAL_SCORE_MAP.get(formal_band_draft, {"score_range": "待定", "trial_score": "待定"})


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
        return "需先解决规则复核问题；G9 前不得发布人物正式分值。"
    return "已具备 G8 正式算法映射；G9 前不得发布人物正式分值、排名或榜单。"


def build_negative_intercept_status(report: dict[str, Any]) -> str:
    if bool(report.get("negative_boundary_blocking")):
        return "已阻断极正"
    return "未阻断极正"


def build_adjacent_item_stripping_status(report: dict[str, Any]) -> str:
    tier = str(report.get("negative_boundary_tier") or "")
    if tier == "weak_to_medium":
        return "已剥离战果、政绩、边疆收益与治世光环，B项仅保留人才安全轻边界"
    if tier == "medium_to_strong":
        return "已剥离战果、政绩、后效与相邻项外溢，B项保留强负核心"
    if tier == "adjacent_item_medium_residual":
        return "已剥离楚狱、政权安全、司法严酷等相邻项，B项仅留中负剩余"
    return "已完成相邻项剥离"
