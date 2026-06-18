from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIG_PATH = ROOT / "configs" / "i5b_trial_targets.json"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人自动结算草案.md"
RULES_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B自动结算规则敏感点清单.md"

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
    "不能容",
    "将下斩之",
    "捶扑",
    "牵曳",
    "直言",
)


RULE_SENSITIVE_POINTS = [
    {
        "rule_id": "RULE-I5B-BOUNDARY-MIDNEG-NO-BLOCK",
        "rule_question": "多维强正证据簇存在中负边界负证，且该中负带 mitigation/upper_bound 时，是否阻断极正上探？",
        "default_rule": "不阻断；只降低置信度或保留极正候选标记。",
        "why_it_matters": "避免把魏征类边界负证机械放大成高档位拦截。",
    },
    {
        "rule_id": "RULE-I5B-SINGLE-DIMENSION-STRONG-POS-NO-EXTREME",
        "rule_question": "强正证据高度集中于创业期军政授权或单一人才类型时，能否上探极正？",
        "default_rule": "不能；强正封顶，除非补出长期中枢治理、文臣生态、反馈入口或异质人才整合等新维度。",
        "why_it_matters": "防止把创业期军政授权直接等同于极正。",
    },
    {
        "rule_id": "RULE-I5B-ADJACENT-STRONG-NEG-RESIDUAL",
        "rule_question": "大规模牵连、政权安全、司法残酷类材料剥离相邻项后，第五项B剩余强度如何默认处理？",
        "default_rule": "默认中负剩余；只有存在直接表达寒蝉、人才流失、群臣莫敢正言、谏臣安全破坏等硬证时，才保留强负剩余。",
        "why_it_matters": "避免把楚狱类材料未剥离相邻项就直接压成强负核心。",
    },
    {
        "rule_id": "RULE-I5B-STRONG-NEG-CORE-VS-STRONG-POS",
        "rule_question": "强正证据成立，但强负核心直接命中表达安全/人才安全时，是否允许高位上探？",
        "default_rule": "可保留强正基础，但自动标记为强正受压制，不得上探极正。",
        "why_it_matters": "用于刘秀这类强正与强负并存的高档位拦截场景。",
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

    residual_level = "none"
    if cluster.get("polarity") == "negative":
        max_strength = max((int(card.get("strength") or 0) for card in linked_cards), default=0)
        direct_safety_hard = has_direct_safety_hard_evidence(linked_cards)
        has_boundary = any(is_boundary_card(card) for card in linked_cards)
        if max_strength >= 4:
            residual_level = "extreme"
        elif max_strength >= 3:
            residual_level = "strong" if direct_safety_hard else "medium" if has_boundary else "strong"
        elif max_strength == 2:
            residual_level = "medium"
        elif max_strength == 1:
            residual_level = "weak"
        if direct_safety_hard:
            residual_level = "strong"
    elif cluster.get("polarity") == "positive":
        residual_level = "strong" if int(cluster.get("candidate_strength") or 0) >= 3 else "medium"

    if cluster.get("polarity") == "positive":
        auto_cluster_result = "强正候选" if int(cluster.get("candidate_strength") or 0) >= 3 else "中正增厚"
    else:
        auto_cluster_result = {
            "extreme": "极负候选",
            "strong": "强负候选",
            "medium": "中负边界",
            "weak": "弱负边界",
            "none": "未定",
        }[residual_level]

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
    has_strong_negative_core = strong_negative_count > 0
    has_extreme_negative_core = extreme_negative_count > 0
    cross_item_split_required = any(bool(card.get("cross_item_split")) for card in person_cards)

    negative_residual_level = "none"
    if negative_cards:
        max_negative_strength = max(int(card.get("strength") or 0) for card in negative_cards)
        direct_safety_hard = has_direct_safety_hard_evidence(negative_cards)
        if max_negative_strength >= 4:
            negative_residual_level = "extreme"
        elif max_negative_strength >= 3:
            negative_residual_level = "strong" if direct_safety_hard else "medium" if has_boundary_evidence else "strong"
        elif max_negative_strength == 2:
            negative_residual_level = "medium"
        else:
            negative_residual_level = "weak"
        if direct_safety_hard:
            negative_residual_level = "strong"

    max_positive_strength = max((int(card.get("strength") or 0) for card in positive_cards), default=0)
    positive_cluster_rows = [evaluate_cluster(row, evidence_lookup) for row in cluster_rows if row.get("person") == person and row.get("polarity") == "positive"]
    negative_cluster_rows = [evaluate_cluster(row, evidence_lookup) for row in cluster_rows if row.get("person") == person and row.get("polarity") == "negative"]
    positive_cluster_rows.sort(key=lambda row: (-int(row["candidate_strength"] or 0), str(row["cluster_id"])))
    negative_cluster_rows.sort(key=lambda row: (-int(row["candidate_strength"] or 0), str(row["cluster_id"])))

    if max_positive_strength >= 3 and negative_residual_level in {"none", "weak", "medium"}:
        if positive_dimension_count >= 3 and not single_dimension_flag:
            auto_band_direction = "高位强正，上探极正候选"
        else:
            auto_band_direction = "强正成立，但极正需看规则敏感点"
    elif max_positive_strength >= 3 and negative_residual_level in {"strong", "extreme"}:
        auto_band_direction = "强正受压制，不上探极正"
    elif max_positive_strength <= 2 and negative_residual_level == "medium":
        auto_band_direction = "中正受中负压制"
    elif max_positive_strength <= 2 and negative_residual_level in {"strong", "extreme"}:
        auto_band_direction = "中正受强负压制"
    else:
        auto_band_direction = "自动草案待规则复核"

    if auto_band_direction == "高位强正，上探极正候选":
        confidence = "high"
    elif auto_band_direction == "强正受压制，不上探极正":
        confidence = "medium_high"
    elif auto_band_direction == "中正受中负压制":
        confidence = "medium"
    elif auto_band_direction == "中正受强负压制":
        confidence = "medium"
    else:
        confidence = "medium_low"

    if person == "李世民":
        rule_sensitive_points = [
            {
                "rule": "中负边界是否阻断极正",
                "decision": "否；魏征线带 mitigation_flag / upper_bound_flag，默认不阻断。",
            },
            {
                "rule": "同一对象正负反转是否单列",
                "decision": "是；只在证据组层与定档层备注，不把单证继续抬成强负核心。",
            },
        ]
    elif person == "刘秀":
        rule_sensitive_points = [
            {
                "rule": "单一维度强正能否极正",
                "decision": "否；正向仍偏创业期军政授权，默认强正封顶。",
            },
            {
                "rule": "强负核心是否压制强正",
                "decision": "是；表达安全硬证默认触发高档位上探拦截。",
            },
        ]
    else:
        rule_sensitive_points = [
            {
                "rule": "相邻项强负剥离后的 B 项剩余",
                "decision": "默认中负剩余；若出现直接寒蝉硬证再升级为强负核心。",
            },
            {
                "rule": "中正正证能否机械抵消强负",
                "decision": "否；中正正证只保留底盘，不机械抵消相邻项强负。",
            },
        ]

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
        "2. 若规则已经足够抽象地解释边界，只回填到自动规则表，不做逐案裁判。",
        "3. 若规则仍无法抽象化，才把问题后移到规则层审核。",
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
        overview_rows.append(
            {
                "person": report["person"],
                "positive_cluster_ids": safe_join(report["positive_cluster_ids"]),
                "negative_cluster_ids": safe_join(report["negative_cluster_ids"]),
                "auto_band_direction": report["auto_band_direction"],
                "confidence": report["confidence"],
                "rule_sensitive_points": "；".join(point["rule"] for point in report["rule_sensitive_points"]),
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


def export_auto_adjudication() -> tuple[Path, Path]:
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    EXPORT_PATH.write_text(render_auto_adjudication(), encoding="utf-8")
    RULES_EXPORT_PATH.write_text(render_rule_sensitive_points(), encoding="utf-8")
    return EXPORT_PATH, RULES_EXPORT_PATH


def main() -> int:
    export_path, rules_path = export_auto_adjudication()
    print(f"exported {export_path}")
    print(f"exported {rules_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
