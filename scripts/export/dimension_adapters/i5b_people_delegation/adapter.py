from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from shared import config_loaders
from shared.config_loaders import load_i5b_cluster_warning_rules
from shared.i5b_cluster_warning_display import (
    match_display_only_cluster_warnings,
    render_display_only_cluster_warning_section,
)
from shared.i5b_markdown_display import human_review_table_fields as configured_human_review_table_fields
from validate import validate_human_readable_markdown_exports as human_readable_markdown_validator
from export.dimension_adapters.i5b_people_delegation.output_specs import *  # noqa: F401,F403
from export.dimension_adapters.i5b_people_delegation.formal_algorithm import (
    FORMAL_ALGORITHM_VERSION,
    compute_formal_algorithm_result,
    formal_algorithm_mapping_rows,
)
from export.dimension_adapters.i5b_people_delegation.rules import *  # noqa: F401,F403
from export.dimension_export.data_loading import (
    DEFAULT_DISPLAY_CONFIG,
    load_markdown_view_config as _load_markdown_view_config,
    read_jsonl,
)
from export.dimension_export.evidence_index import (
    collect_cluster_warnings,
    person_clusters_for_report,
    render_cluster_warning_section,
    unique_values,
)
from export.dimension_export.markdown_rendering import (
    add_table_appendix_item,
    cluster_card_value,
    display_field_label,
    display_value,
    escape_cell,
    field_render_policy,
    make_appendix_anchor,
    markdown_code_block,
    markdown_display_table,
    markdown_field_item,
    markdown_inline_value,
    markdown_list_items,
    markdown_table,
    markdown_value_text,
    render_cluster_cards,
    render_numbered_list,
    render_table_appendix_page,
    render_table_appendix_section,
    render_table_cell,
    table_appendix_href,
    value_label_key,
)
from export.dimension_export.output_layout import ensure_directories, remove_existing_paths, write_markdown_outputs
from export.dimension_export.pipeline import build_dimension_context
from export.dimension_export.validation import HumanReadableMarkdownValidationError

def load_i5b_markdown_view_config(path: Path | None = None) -> dict[str, Any]:
    if path is not None:
        raise ValueError("第五项B Markdown 展示默认值已迁回代码，不再读取外部 markdown_view 配置")
    return _load_markdown_view_config()


def person_detail_export_path(person: str) -> Path:
    return AUTO_DRAFT_DETAIL_DIR / f"{person}.md"


def person_appendix_export_path(person: str) -> Path:
    return AUTO_DRAFT_APPENDIX_DIR / f"{person}_长字段附录.md"


def person_detail_relative_link(person: str) -> str:
    return f"./人物详情/{person_detail_export_path(person).name}"


def person_detail_backlink() -> str:
    return f"../{EXPORT_PATH.name}"


def human_table_fields(table_key: str, display_config: dict[str, Any] | None = None) -> list[str]:
    config = display_config if display_config is not None else load_i5b_markdown_view_config()
    return configured_human_review_table_fields(table_key, config)


def add_appendix_item(
    appendix_items: list[dict[str, Any]],
    *,
    person: str,
    field: str,
    label: str,
    value: object,
) -> str:
    anchor = make_appendix_anchor(field, appendix_items)
    appendix_items.append({"anchor": anchor, "field": field, "label": label, "value": value})
    return f"[见附录：{label}](../附录/{person_appendix_export_path(person).name}#{anchor})"


def render_display_field(
    field: str,
    value: object,
    *,
    person: str | None = None,
    display_config: dict[str, Any] | None = None,
    appendix_items: list[dict[str, Any]] | None = None,
    bullet: str = "*",
) -> list[str]:
    config = display_config if display_config is not None else load_i5b_markdown_view_config()
    label = display_field_label(field, config)
    value_text = markdown_value_text(value)
    policy = field_render_policy(field, config)
    max_inline_chars = int(policy.get("max_inline_value_chars") or config.get("max_inline_value_chars") or 96)
    strategy = str(policy.get("long_field_strategy") or config.get("long_field_strategy") or "inline")
    is_long = len(value_text) > max_inline_chars

    if is_long and strategy == "appendix_link":
        if appendix_items is not None and person is not None:
            return [f"{bullet} **{label}**：{add_appendix_item(appendix_items, person=person, field=field, label=label, value=value)}"]
        strategy = str(policy.get("fallback_long_field_strategy") or config.get("fallback_long_field_strategy") or "fenced_code_block")

    if is_long and strategy == "fenced_code_block":
        return [f"{bullet} **{label}**：", markdown_code_block(value, config)]

    return [f"{bullet} **{label}**：{markdown_inline_value(value, config)}"]


def render_score_mapping_draft() -> str:
    display_config = load_i5b_markdown_view_config()
    score_rows = formal_algorithm_mapping_rows()
    lines = [
        "# 第五项B正式算法标尺与档位映射",
        "",
        f"状态：G8 已批准 / `{FORMAL_ALGORITHM_VERSION}` 已释放 / G9 前不发布人物正式分值",
        "",
        "## 一、定位",
        "",
        "本文件定义第五项B《用人与授权》的 V3.2 九档与 45 分档内自动定分算法版本，但不发布任何人物正式分数。",
        "",
        "它只读取已经完成裁量的净证据和正式定档落地表，不回到人物级个案，不生成排名，不生成总榜。",
        "",
        "若与第五项B自动结算规则、正式定档落地表、证据裁量总则存在冲突，以已合并的规则结论和“不直接推分”约束为先。",
        "",
        "## 二、与现有文档的关系",
        "",
        "1. `docs/分项规则/第五项统治者政治素质/B用人与授权.md` 决定 band direction 与规则敏感点。",
        "2. `exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B三人正式定档落地表.md` 只展示正式档位和 G9 压制状态。",
        "3. 本文件回答自动结算方向如何进入 V3.2 九档和 45 分档内区间。",
        "4. 本文件不替代 `docs/分项规则/第五项统治者政治素质/B用人与授权.md`。",
        "5. 本文件不替代 `docs/证据规则/证据裁量总则.md` 中的评分标尺关系。",
        "",
        "## 三、通用映射原则",
        "",
        "1. 先看档位，再看压制、封顶、相邻项剥离和负证拦截。",
        "2. 极正候选 / 极正、高位强正、强正三段，优先作为正向高区间候选。",
        "3. 强正受压制、强正封顶，仍属正向段，但必须受上限或压制规则控制。",
        "4. 中正、中正受中负压制、中正受强负压制，属于中位段与压制段。",
        "5. 中负、强负属于负向段，先完成相邻项切分，再进入区间判断。",
        "6. 任何档位都不能绕过 `score_stage_prerequisites` 直接给人物正式分。",
        "7. 本文给出的区间是算法版本的 45 分区间；人物级正式分值字段在 G9 前必须压制。",
        "",
        "## 四、V3.2 对齐边界",
        "",
        "1. V3.2 已定义正收益总盘 1500 分、历史负债 0—300 扣分和七大项权重。",
        "2. 第五项B《用人与授权》正式上限为 45 分。",
        "3. 本表 `relative_score_range_draft` 栏位沿用展示配置名称，内容已改为 45 分正式算法区间。",
        "4. 算法可以确定区间和候选值，但 G9 前不得发布人物级正式分值。",
        "5. 本 PR 不生成正式人物分数、排名或榜单。",
        "6. 本 PR 不改变任何人物现有 trial index、band、evidence 或 adjudication。",
        f"7. 正式 45 分映射由 `{FORMAL_ALGORITHM_VERSION}` 承接；人物值发布仍需 G9。",
        "",
        "## 五、档位到分值映射草案",
        "",
        "说明：以下区间为算法版本的 45 分区间；当前不直接发布人物出分。",
        "",
        markdown_display_table(
            human_table_fields("score_mapping_draft", display_config),
            score_rows,
            display_config=display_config,
        ),
        "",
        "## 六、正式出分前置条件",
        "",
        "1. 先有同一版本规则和算法产生的正式九档。",
        "2. 再由算法在档内确定候选值。",
        "3. 人物级分值发布需另过 G9。",
        "4. 当前三人不得据此获得正式分数。",
        "5. 当前三人不得因此改变现有正式档位草案。",
        "",
        "## 七、禁止事项",
        "",
        "1. G9 前不给李世民、刘秀、刘庄三人正式分。",
        "2. G9 前不得给任何人物发布正式分。",
        "3. 不排名。",
        "4. 不生成阶段总榜或总榜。",
        "5. 不把战功、政绩、边疆收益、统一贡献、治世光环回填第五项B。",
        "6. 不把本草案当作正式评分标准。",
        "",
        "## 八、待确认事项",
        "",
        "1. 总评分标准是否存在全局满分上限。",
        "2. 第五项B是否需要单独的正负向惩罚系数。",
        "3. `强正受压制` 与 `强正封顶` 在正式出分时是否同列处理。",
        "4. `中正受中负压制` 与 `中正受强负压制` 是否需要进一步细分。",
        "5. 正式出分任务是否要额外引入子项内归一化系数。",
        "",
        "## 九、结论",
        "",
        "本文件是 G8 已批准的正式算法版本说明，不是人物正式出分表。",
        "",
        "若未来进入正式分值阶段，应先取得 G9，再按同一算法版本发布人物级正式分值和必要回归报告。",
    ]
    return "\n".join(lines) + "\n"


def summarize_positive_basis(report: dict[str, Any]) -> str:
    anchors = safe_join(report.get("positive_anchor_names") or [])
    dimensions = safe_join(report.get("positive_dimensions") or [])
    rule_cores = safe_join(report.get("positive_rule_cores") or [])
    strength = int(report.get("strong_positive_count") or 0)
    coverage = int(report.get("coverage_dimension_count") or 0)
    parts = [
        f"{strength}个强正核心",
        f"{coverage}个正向维度" if coverage else "正向维度未单列",
        "三核心覆盖已满足" if bool(report.get("positive_three_core_coverage")) else "三核心覆盖不足",
    ]
    if anchors:
        parts.append(f"对象锚点：{anchors}")
    if dimensions:
        parts.append(f"维度摘要：{dimensions}")
    if rule_cores:
        parts.append(f"规则核心：{rule_cores}")
    return "；".join(parts)


def summarize_negative_pressure(report: dict[str, Any]) -> str:
    display_config = load_i5b_markdown_view_config()
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
    parts.append(f"残余层级：{display_value(residual, display_config)}")
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
    positive_rule_cores = infer_positive_rule_cores(positive_cards)
    positive_three_core_coverage = has_required_positive_rule_cores(positive_cards)

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
    positive_extreme_allowed = (
        (single_dimension_flag and strong_positive_count >= 3 and positive_three_core_coverage)
        or (positive_dimension_count >= 3 and not single_dimension_flag)
    )
    rule_sensitive_points = build_rule_sensitive_points(
        {
            "negative_boundary_tier": negative_boundary_tier,
            "single_dimension_flag": single_dimension_flag,
            "strong_positive_count": strong_positive_count,
            "positive_three_core_coverage": positive_three_core_coverage,
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
        "positive_rule_cores": positive_rule_cores,
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
        "positive_three_core_coverage": positive_three_core_coverage,
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
    lines = [
        "# 第五项B自动结算规则敏感点清单",
        "",
        "本文件只列抽象规则问题和默认处理方式，不审人物个案、不计分、不排名。",
        "",
        "## 规则敏感点",
        "",
    ]
    for rule in RULE_SENSITIVE_POINTS:
        lines.extend(
            [
                f"### {rule['rule_id']}",
                "",
                f"- **规则问题**：{rule['rule_question']}",
                f"- **默认处理**：{rule['default_rule']}",
                f"- **治理意义**：{rule['why_it_matters']}",
                "",
            ]
        )
    lines.extend(
        [
        "## 规则使用方式",
        "",
        "1. 先看规则问题是否被当前 cluster 命中。",
        "2. 弱负升中负的边界只降置信度，不阻断极正/高位上探，也不进入强负核心。",
        "3. 中负升强负的边界阻断极正/高位上探，只在有明确突破中负封顶的硬证时进入强负核心。",
        "4. 若规则仍无法抽象化，才把问题后移到规则层审核。",
        ]
    )
    return "\n".join(lines) + "\n"


AUTO_FEATURE_FIELDS = [
    "positive_cluster_ids",
    "negative_cluster_ids",
    "core_positive_count",
    "strong_positive_count",
    "extreme_positive_count",
    "core_negative_count",
    "strong_negative_count",
    "extreme_negative_count",
    "coverage_dimension_count",
    "single_dimension_flag",
    "positive_rule_cores",
    "positive_three_core_coverage",
    "startup_positive_share",
    "has_high_value_object_anchor",
    "has_boundary_evidence",
    "has_mitigation_flag",
    "has_upper_bound_flag",
    "has_strong_negative_core",
    "has_extreme_negative_core",
    "negative_boundary_tier",
    "negative_boundary_blocking",
    "cross_item_split_required",
    "cross_item_split_residual_level",
]


def render_person_section(
    report: dict[str, Any],
    display_warning_section: str = "",
    *,
    display_config: dict[str, Any] | None = None,
    appendix_items: list[dict[str, Any]] | None = None,
) -> str:
    person = report["person"]
    positive_rows = report["positive_cluster_rows"]
    negative_rows = report["negative_cluster_rows"]
    cluster_rows = positive_rows + negative_rows
    config = display_config if display_config is not None else load_i5b_markdown_view_config()

    sections = [
        f"## {person}",
        "",
        "### 证据簇自动结算",
        "",
        render_cluster_cards(cluster_rows, config),
        "",
        "### 自动特征",
        "",
    ]
    for field in AUTO_FEATURE_FIELDS:
        sections.extend(
            render_display_field(
                field,
                report[field],
                person=person,
                display_config=config,
                appendix_items=appendix_items,
            )
        )
    sections.extend(["", "### 触发的规则敏感点", ""])

    for point in report["rule_sensitive_points"]:
        sections.append(f"- **{point['rule']}**：{point['decision']}")

    if display_warning_section:
        sections.extend(["", display_warning_section])

    sections.extend(
        [
            "",
            "### 自动结算结论",
            "",
            *render_display_field("band_direction", report["auto_band_direction"], display_config=config, bullet="-"),
            *render_display_field("confidence", report["confidence"], display_config=config, bullet="-"),
            "- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。",
        ]
    )

    return "\n".join(sections) + "\n"


def render_formal_person_section(report: dict[str, Any]) -> str:
    display_config = load_i5b_markdown_view_config()
    person = report["person"]
    formal_result = compute_formal_algorithm_result(report)
    sections = [
        f"## {person}",
        "",
        "### 正式档位落地",
        "",
        f"- **自动结算来源**：{report['auto_band_direction']} / {display_value(report['confidence'], display_config)}",
        f"- **正式档位草案**：{build_formal_band_draft(report)}",
        f"- **V3.2 正式九档**：{formal_result['formal_grade']}",
        f"- **45 分算法区间**：{formal_result['score_range_45']}",
        f"- **算法版本**：{formal_result['algorithm_version']}",
        f"- **不出分说明**：G9 前压制人物级正式分值，候选值不进入发布视图。",
        f"- **不排名说明**：本阶段不生成排名或名次。",
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
        *render_display_field("remaining_rule_questions", format_remaining_questions(report), bullet="-"),
        *render_display_field("score_stage_prerequisites", format_score_stage_prerequisites(report), bullet="-"),
        *render_display_field("not_scored_flag", "是", bullet="-"),
        *render_display_field("ranking_suppressed_flag", "是", bullet="-"),
        *render_display_field("formal_score_value_suppressed_until_g9", "是", bullet="-"),
    ]
    return "\n".join(sections) + "\n"


def build_auto_adjudication_context() -> dict[str, Any]:
    config = config_loaders.get_i5b_trial_config()
    targets = list(config.get("targets") or [])
    return build_dimension_context(targets=targets, data_dir=DATA_DIR, evaluate_person=evaluate_person)


def summarize_auto_feature_digest(report: dict[str, Any], display_config: dict[str, Any] | None = None) -> str:
    config = display_config if display_config is not None else load_i5b_markdown_view_config()
    return "；".join(
        [
            f"强正核心 {report['strong_positive_count']} 个",
            f"正向维度 {report['coverage_dimension_count']} 个",
            f"负向边界 {cluster_card_value(report['negative_boundary_tier'], config)}",
            f"置信 {display_value(report['confidence'], config)}",
        ]
    )


def summarize_cluster_count(report: dict[str, Any]) -> str:
    positive_count = len(report["positive_cluster_rows"])
    negative_count = len(report["negative_cluster_rows"])
    total_count = positive_count + negative_count
    return f"正 {positive_count} / 负 {negative_count} / 合计 {total_count}"


def render_split_index_page(
    person_reports: list[dict[str, Any]],
    evidence_lookup: dict[str, dict[str, Any]],
    cluster_lookup: dict[str, dict[str, Any]],
    warning_rules: list[dict[str, Any]],
    display_config: dict[str, Any] | None = None,
) -> str:
    config = display_config if display_config is not None else load_i5b_markdown_view_config()
    table_appendix_items: list[dict[str, Any]] = []
    overview_rows = []
    for report in person_reports:
        person_clusters = person_clusters_for_report(report, cluster_lookup)
        warnings = collect_cluster_warnings(
            person_clusters,
            evidence_lookup,
            warning_rules,
            match_warning=match_display_only_cluster_warnings,
        )
        overview_rows.append(
            {
                "person": report["person"],
                "auto_band_direction": report["auto_band_direction"],
                "auto_feature_digest": summarize_auto_feature_digest(report, config),
                "cluster_count_digest": summarize_cluster_count(report),
                "display_warning_count": len(warnings),
                "detail_page": f"[{report['person']}详情]({person_detail_relative_link(report['person'])})",
            }
        )

    lines = [
        "# 第五项B三人自动结算草案",
        "",
        "本文为 Typora 友好的纯 Markdown 索引页。详情页继续保留字段全量展示，不折叠、不截断、不隐藏 `linked_*` 与 `cross_item_split_signals`。",
        "",
        "## 阅读说明",
        "",
        "1. 先在本页查看三位试点人物总览。",
        "2. 再通过相对链接进入单个人物详情页。",
        "3. 人工复核提示数量按 display-only 规则统计，只改善阅读组织结构，不改变数据、裁判逻辑或评分结论。",
        "",
        "## 试点人物列表",
        "",
    ]
    for report in person_reports:
        lines.append(f"- [{report['person']}详情]({person_detail_relative_link(report['person'])})")

    lines.extend(
        [
            "",
            "## 总览索引",
            "",
            markdown_display_table(
                human_table_fields("auto_adjudication_overview", config),
                overview_rows,
                display_config=config,
                table_appendix_items=table_appendix_items,
            ),
        ]
    )
    if table_appendix_items:
        lines.extend(
            [
                "",
                "## 表格长字段附录",
                "",
                render_table_appendix_section(table_appendix_items, config).rstrip(),
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_person_detail_page(
    report: dict[str, Any],
    *,
    display_warning_section: str = "",
    display_config: dict[str, Any] | None = None,
    appendix_items: list[dict[str, Any]] | None = None,
) -> str:
    config = display_config if display_config is not None else load_i5b_markdown_view_config()
    resolved_appendix_items = appendix_items if appendix_items is not None else []
    lines = [
        f"# {report['person']}：第五项B自动结算草案",
        "",
        "本文为纯 Markdown 人物详情页，保留该人物自动特征、证据簇、`linked_*`、`cross_item_split_signals` 与 warning `matched_fields` 的全量展示。",
        "",
        f"[返回索引]({person_detail_backlink()})",
        "",
        render_person_section(
            report,
            display_warning_section=display_warning_section,
            display_config=config,
            appendix_items=resolved_appendix_items,
        ).rstrip(),
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_person_appendix_page(
    person: str,
    appendix_items: list[dict[str, Any]],
    display_config: dict[str, Any] | None = None,
) -> str:
    config = display_config if display_config is not None else load_i5b_markdown_view_config()
    lines = [
        f"# {person}：第五项B自动结算草案长字段附录",
        "",
        f"[返回人物详情](../人物详情/{person_detail_export_path(person).name})",
        "",
        "本附录只承接正文中过长字段的全量展示，不改变数据、裁判逻辑、评分或 warning 语义。",
        "",
    ]
    if not appendix_items:
        lines.append("无附录字段。")
        return "\n".join(lines).rstrip() + "\n"

    for item in appendix_items:
        lines.extend(
            [
                f"## {item['anchor']}",
                "",
                f"### {item['label']}",
                "",
                markdown_code_block(item["value"], config),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_review_entry_landing() -> str:
    targets = list(config_loaders.get_i5b_trial_config().get("targets") or [])
    lines = [
        "# 第五项B三人专人审核入口",
        "",
        "本文由 `scripts/export/export_i5b_auto_adjudication.py` 生成，是第五项B三人试点人工审核的当前状态入口；旧 `docs/` 同名文件已退役，不再作为当前入口。",
        "",
        "## 使用边界",
        "",
        "- 本入口不是正式评分表。",
        "- 本入口不生成正式分数、最终排名、总榜或人物级人工覆盖结论。",
        "- 本入口不生成最终排名。",
        "- 人工只核验数据质量、史料回源状态、上下文充分性、相邻项剥离、规则命中和算法版本，不逐人改写自动结算方向。",
        "- 自动结算草案、证据链和 warning 都只是复核材料；异常结果应回到数据、规则或算法层修复。",
        "- 人工审核主表隐藏 `evidence_id/source_id/cluster_id` 等机器字段；需要追踪时查看附录或机器审计视图。",
        "- `exports/markdown_views/第五项B/机器审计/` 只用于代码审查、数据追踪和回源定位，不作为业务审核主入口。",
        "",
        "## Canonical 入口层级",
        "",
        "- 审核入口视图：`exports/markdown_views/第五项B/人工审核/入口/`",
        "- 自动裁判链：`exports/markdown_views/第五项B/人工审核/自动裁判链/`",
        "- 自动结算索引：`exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/第五项B三人自动结算草案.md`",
        "- 规则敏感点：`exports/markdown_views/第五项B/人工审核/自动裁判链/规则敏感点/第五项B自动结算规则敏感点清单.md`",
        "- 正式定档草案：`exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B三人正式定档落地表.md`",
        "- 评分映射草案：`exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B评分标尺与档位映射草案.md`",
        "- 证据卡索引：`exports/markdown_views/第五项B/人工审核/证据链/证据卡/第五项B人工审核证据卡索引.md`",
        "- 证据簇索引：`exports/markdown_views/第五项B/人工审核/证据链/证据簇/第五项B人工审核证据簇索引.md`",
        "- 机器审计视图：`exports/markdown_views/第五项B/机器审计/证据链/`",
        "",
        "## 审核总流程",
        "",
        "1. 先读三人自动结算索引。",
        "2. 再读对应人物详情页。",
        "3. 再读该人物人工审核净证据池。",
        "4. 必要时查看人工审核证据卡索引和人工审核证据簇索引。",
        "5. 需要代码追踪、数据追踪或回源定位时，再进入机器审计视图。",
        "6. 最后回到人工复核工作台，只填写数据质量、回源、上下文、剥离和规则级复核状态。",
        "",
        "## 试点人物入口",
        "",
    ]
    for person in targets:
        lines.extend(
            [
                f"### {person}",
                "",
                "- 自动结算人物详情：",
                f"  - `exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/人物详情/{person}.md`",
                "- 自动结算长字段附录：",
                f"  - `exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/附录/{person}_长字段附录.md`",
                "- 净证据池：",
                f"  - `exports/markdown_views/第五项B/人工审核/证据链/净证据池/第五项B_{person}人工审核净证据池.md`",
                "- 人工审核史料详情附录：",
                f"  - `exports/markdown_views/第五项B/人工审核/证据链/附录/{person}_人工审核史料详情附录.md`",
                "- 数据质量核验栏位：回源状态、上下文充分性、相邻项剥离、证据方向一致性、规则命中异常。",
                "",
            ]
        )
    lines.extend(
        [
            "## 旧路径禁用",
            "",
            "以下旧路径若在历史分支或本地残留中出现，只能视为兼容层或待清理文件，不作为当前审核入口：",
            "",
            "- `exports/markdown_views/第五项B_李世民净证据池.md`",
            "- `exports/markdown_views/第五项B_刘秀净证据池.md`",
            "- `exports/markdown_views/第五项B_刘庄净证据池.md`",
            "- `exports/markdown_views/第五项B三人自动结算草案.md`",
            "- `exports/markdown_views/第五项B自动结算草案_李世民.md`",
            "- `exports/markdown_views/第五项B自动结算草案_刘秀.md`",
            "- `exports/markdown_views/第五项B自动结算草案_刘庄.md`",
            "- `exports/markdown_views/第五项B/自动结算草案/`",
            "- `exports/markdown_views/第五项B/证据链/`",
            "",
            "## 审核出口",
            "",
            "审核出口只记录规则级复核、数据质量核验和发布门槛状态；不得把本文档、自动结算草案、证据链视图或 warning 直接转写成正式分数、最终排名、正式档位或裁判结论。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_review_workbench() -> str:
    context = build_auto_adjudication_context()
    person_reports = context["person_reports"]
    rows = []
    for report in person_reports:
        rows.append(
            {
                "人物": report["person"],
                "自动结算方向（非正式）": report["auto_band_direction"],
                "正向簇数量": str(len(report["positive_cluster_ids"])),
                "负向簇数量": str(len(report["negative_cluster_ids"])),
                "规则敏感点": "；".join(point["rule"] for point in report["rule_sensitive_points"]) or "无",
                "数据质量核验状态": "待核验",
            }
        )

    lines = [
        "# 第五项B三人试点人工复核工作台",
        "",
        "本文由当前 canonical data 与配置生成，是人工复核当前状态视图；旧 `docs/` 同名文件已退役，不再手工维护。",
        "",
        "## 使用边界",
        "",
        "- 本工作台不是正式评分表。",
        "- 本工作台不生成正式分数，不生成最终排名。",
        "- 本工作台只组织数据质量、回源、上下文、相邻项剥离、规则命中和算法版本核验。",
        "- 自动结算方向只作为复核入口，不是正式档位、正式分数、排名或总榜。",
        "- warning 保持 display-only，只提示阅读风险，不自动压制、不自动升档、不构成正式结论。",
        "- 若发现异常，应修正数据、规则或算法，不做单人人工 override。",
        "",
        "## 人工复核总览",
        "",
        markdown_table(
            ["人物", "自动结算方向（非正式）", "正向簇数量", "负向簇数量", "规则敏感点", "数据质量核验状态"],
            rows,
        ),
        "",
    ]
    for report in person_reports:
        lines.extend(
            [
                f"## {report['person']}",
                "",
                f"- **自动结算方向（非正式）**：{report['auto_band_direction']}",
                f"- **正向簇数量**：{len(report['positive_cluster_ids'])}",
                f"- **负向簇数量**：{len(report['negative_cluster_ids'])}",
                f"- **负证拦截状态**：{build_negative_intercept_status(report)}",
                f"- **相邻项剥离状态**：{build_adjacent_item_stripping_status(report)}",
                f"- **剩余规则问题**：{format_remaining_questions(report)}",
                "- **数据质量核验栏位**：回源状态、上下文充分性、相邻项剥离、证据方向一致性、规则命中异常。",
                "- **发布门槛**：仅当规则级复核和数据质量核验完成后，才可进入后续发布流程；本视图不直接推出正式结论。",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_review_matrix_note() -> str:
    targets = list(config_loaders.get_i5b_trial_config().get("targets") or [])
    lines = [
        "# 第五项B三人试点矩阵说明",
        "",
        "本文由配置生成当前三人试点矩阵说明。矩阵骨架只规划检索与复核方向，不代表完成检索，不写入 `search_logs`，也不参与定档定分。",
        "",
        "## 试点人物",
        "",
    ]
    lines.extend(f"- {person}" for person in targets)
    lines.extend(
        [
            "",
            "## 矩阵用途",
            "",
            "- 为每个人物列出第五项B正向、负向和相邻项风险的检索方向。",
            "- 实际检索后，矩阵格只能落为 `checked_no_hard_evidence`、`evidence_found_card_created`、`lead_needs_source_review` 或 `routed_to_adjacent_item`。",
            "- 矩阵不写评分结果，不写正式档位，不把人物名望、战功、治绩、盛世光环或边疆收益回填第五项B。",
            "",
            "## 三人选择原因",
            "",
            "- 李世民：高位正证样本，用于检验极正与中负拦截并存。",
            "- 刘秀：旧体系高位被强负证重新打开的样本，用于检验负证召回。",
            "- 刘庄：旧体系正证漏检与负证强拦截并存的样本，用于检验正负双向检索。",
            "",
            "## 数据质量核验边界",
            "",
            "人工只核验回源、上下文、相邻项剥离、规则命中和算法版本；不得把矩阵骨架转写为人物级最终分档、正式分数、排名或单人特判。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_review_pilot_plan() -> str:
    targets = list(config_loaders.get_i5b_trial_config().get("targets") or [])
    lines = [
        "# 第五项B试点计划",
        "",
        "本文由配置生成第五项B三人试点当前计划视图。它只描述试点流程与状态入口，不写评分结果。",
        "",
        "## 试点对象",
        "",
    ]
    lines.extend(f"- {person}" for person in targets)
    lines.extend(
        [
            "",
            "## 试点原因",
            "",
            "- 第五项B已暴露正证漏检与负证漏检问题。",
            "- 可验证正负证矩阵、触发词、证据卡、相邻项切分、负证拦截和规则级复核全流程。",
            "- 三人试跑用于校验规则，不用于生成正式分数、排名或总榜。",
            "",
            "## 试点流程",
            "",
            "1. 定第五项B边界。",
            "2. 建第五项B正证触发词。",
            "3. 建第五项B负证触发词。",
            "4. 跑三人正负证矩阵。",
            "5. 命中材料回源。",
            "6. 生成证据卡。",
            "7. 做相邻项切分。",
            "8. 生成净证据池和自动结算草案。",
            "9. 进行规则级复核、数据质量核验和发布门槛检查。",
            "10. 后续是否扩展到全池，另按规则和任务范围确认。",
            "",
            "## 禁止事项",
            "",
            "- 不在本计划中写入旧分数或新分数。",
            "- 不把自动方向转写成正式档位。",
            "- 不新增人物级人工覆盖、单人特判或排名。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_review_entry_outputs() -> dict[Path, str]:
    return {
        REVIEW_ENTRY_EXPORT_PATH: render_review_entry_landing(),
        REVIEW_WORKBENCH_EXPORT_PATH: render_review_workbench(),
        REVIEW_MATRIX_EXPORT_PATH: render_review_matrix_note(),
        REVIEW_PLAN_EXPORT_PATH: render_review_pilot_plan(),
    }


def render_split_auto_adjudication_outputs(
    *,
    include_display_warnings: bool = False,
    warning_rules: list[dict[str, Any]] | None = None,
) -> dict[Path, str]:
    context = build_auto_adjudication_context()
    evidence_lookup = context["evidence_lookup"]
    cluster_lookup = context["cluster_lookup"]
    person_reports = context["person_reports"]
    resolved_warning_rules = warning_rules if warning_rules is not None else load_i5b_cluster_warning_rules()
    display_config = load_i5b_markdown_view_config()

    outputs: dict[Path, str] = {
        EXPORT_PATH: render_split_index_page(
            person_reports,
            evidence_lookup,
            cluster_lookup,
            resolved_warning_rules,
            display_config,
        )
    }
    for report in person_reports:
        display_warning_section = ""
        if include_display_warnings:
            person_clusters = person_clusters_for_report(report, cluster_lookup)
            display_warning_section = render_cluster_warning_section(
                person_clusters,
                evidence_lookup,
                resolved_warning_rules,
                match_warning=match_display_only_cluster_warnings,
                render_warning_section=render_display_only_cluster_warning_section,
            )
        appendix_items: list[dict[str, Any]] = []
        outputs[person_detail_export_path(report["person"])] = render_person_detail_page(
            report,
            display_warning_section=display_warning_section,
            display_config=display_config,
            appendix_items=appendix_items,
        )
        if appendix_items:
            outputs[person_appendix_export_path(report["person"])] = render_person_appendix_page(
                report["person"],
                appendix_items,
                display_config,
            )
    return outputs


def render_auto_adjudication(
    *,
    include_display_warnings: bool = False,
    warning_rules: list[dict[str, Any]] | None = None,
) -> str:
    display_config = load_i5b_markdown_view_config()
    config = config_loaders.get_i5b_trial_config()
    targets = list(config.get("targets") or [])
    evidence_cards = read_jsonl(DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = read_jsonl(DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    cluster_lookup = {row["cluster_id"]: row for row in evidence_clusters if row.get("cluster_id")}
    person_reports = [evaluate_person(person, evidence_clusters, evidence_lookup) for person in targets]
    resolved_warning_rules: list[dict[str, Any]] = []
    if include_display_warnings:
        resolved_warning_rules = warning_rules if warning_rules is not None else load_i5b_cluster_warning_rules()

    overview_rows = []
    for report in person_reports:
        rule_points = report["rule_sensitive_points"]
        overview_rows.append(
            {
                "person": report["person"],
                "auto_band_direction": report["auto_band_direction"],
                "confidence": report["confidence"],
                "negative_boundary_tier": report["negative_boundary_tier"],
                "negative_boundary_blocking_digest": report["negative_boundary_blocking"],
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
            markdown_display_table(
                human_table_fields("auto_adjudication_matrix", display_config),
                overview_rows,
                display_config=display_config,
            ),
        "",
        "## 逐人自动草案",
        "",
    ]

    for report in person_reports:
        display_warning_section = ""
        if include_display_warnings:
            person_cluster_ids = report["positive_cluster_ids"] + report["negative_cluster_ids"]
            person_clusters = [cluster_lookup[cluster_id] for cluster_id in person_cluster_ids if cluster_id in cluster_lookup]
            display_warning_section = render_cluster_warning_section(
                person_clusters,
                evidence_lookup,
                resolved_warning_rules,
                match_warning=match_display_only_cluster_warnings,
                render_warning_section=render_display_only_cluster_warning_section,
            )
        lines.append(render_person_section(report, display_warning_section=display_warning_section, display_config=display_config))

    return "\n".join(lines).rstrip() + "\n"

def render_formal_landing_table() -> str:
    display_config = load_i5b_markdown_view_config()
    config = config_loaders.get_i5b_trial_config()
    targets = list(config.get("targets") or [])
    evidence_cards = read_jsonl(DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = read_jsonl(DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    person_reports = [evaluate_person(person, evidence_clusters, evidence_lookup) for person in targets]

    table_appendix_items: list[dict[str, Any]] = []
    overview_rows = []
    for report in person_reports:
        rule_points = report["rule_sensitive_points"]
        formal_result = compute_formal_algorithm_result(report)
        overview_rows.append(
            {
                "person": report["person"],
                "auto_band_direction": report["auto_band_direction"],
                "formal_band_draft": build_formal_band_draft(report),
                "formal_v3_2_grade": formal_result["formal_grade"],
                "confidence": report["confidence"],
                "negative_boundary_tier": report["negative_boundary_tier"],
                "not_scored_flag": True,
                "ranking_suppressed_flag": True,
            }
        )

    lines = [
        "# 第五项B三人正式定档落地表",
        "",
        "本文件由自动结算草案与规则级复核结果派生，只输出正式档位草案，不生成分数、排名或总榜。",
        "",
        "## 一、正式落地总览",
        "",
        markdown_display_table(
            human_table_fields("formal_landing_overview", display_config),
            overview_rows,
            display_config=display_config,
            table_appendix_items=table_appendix_items,
        ),
        "",
    ]
    if table_appendix_items:
        lines.extend(
            [
                "## 表格长字段附录",
                "",
                render_table_appendix_section(table_appendix_items, display_config).rstrip(),
                "",
            ]
        )

    lines.extend(
        [
            "## 二、逐人落地说明",
            "",
        ]
    )

    for report in person_reports:
        lines.append(render_formal_person_section(report))

    return "\n".join(lines).rstrip() + "\n"


def render_three_pilot_closure() -> str:
    display_config = load_i5b_markdown_view_config()
    config = config_loaders.get_i5b_trial_config()
    targets = list(config.get("targets") or [])
    evidence_cards = read_jsonl(DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = read_jsonl(DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    person_reports = [evaluate_person(person, evidence_clusters, evidence_lookup) for person in targets]

    table_appendix_items: list[dict[str, Any]] = []
    overview_rows = []
    for report in person_reports:
        trial_score_draft = build_trial_score_draft(report)
        overview_rows.append(
            {
                "person": report["person"],
                "final_band": build_formal_band_draft(report),
                "internal_trial_score_range": trial_score_draft["score_range"],
                "internal_trial_score": trial_score_draft["trial_score"],
                "extend_pilot_ready": "可",
            }
        )

    lines = [
        "# 第五项B三人试点内部闭环收尾",
        "",
        "本文件只做第五项B三人试点的内部闭环收尾，不输出正式分，不排名，不生成阶段总榜或总榜；V3.2 已定义 1500 正收益总盘和第五项B 45分上限，G8 正式算法已释放，但 G9 前人物级正式分值、排名或总榜仍不得发布。",
        "",
        "## 一、内部闭环总览",
        "",
        markdown_display_table(
            human_table_fields("trial_closure_overview", display_config),
            overview_rows,
            display_config=display_config,
            table_appendix_items=table_appendix_items,
        ),
        "",
    ]
    if table_appendix_items:
        lines.extend(
            [
                "## 表格长字段附录",
                "",
                render_table_appendix_section(table_appendix_items, display_config).rstrip(),
                "",
            ]
        )

    lines.extend(
        [
            "## 二、逐人收尾说明",
            "",
        ]
    )

    for report in person_reports:
        trial_score_draft = build_trial_score_draft(report)
        lines.extend(
            [
                f"### {report['person']}",
                "",
                f"- **最终定档**：{build_formal_band_draft(report)}",
                f"- **内部试算区间**：{trial_score_draft['score_range']}",
                f"- **内部试算分**：{trial_score_draft['trial_score']}",
                f"- **定档依据摘要**：{summarize_positive_basis(report)}",
                f"- **负证拦截状态**：{build_negative_intercept_status(report)}；{summarize_negative_pressure(report)}",
                f"- **相邻项剥离状态**：{build_adjacent_item_stripping_status(report)}",
                f"- **规则敏感点是否已解决**：{format_rule_resolutions(report)}",
                "- **是否可进入扩展试点**：可",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def legacy_flat_export_paths() -> list[Path]:
    paths = list(LEGACY_FLAT_EXPORT_PATHS)
    for person in config_loaders.get_i5b_trial_targets():
        paths.append(MARKDOWN_VIEW_ROOT / f"第五项B自动结算草案_{person}.md")
    return paths


def remove_legacy_flat_exports() -> None:
    remove_existing_paths(legacy_flat_export_paths())


def export_auto_adjudication(
    *,
    include_display_warnings: bool = False,
    warning_rules: list[dict[str, Any]] | None = None,
    output_layout: str = OUTPUT_LAYOUT_CANONICAL,
    validate_output: bool = True,
) -> tuple[Path, Path, Path, Path]:
    ensure_directories(
        [
            EXPORT_PATH.parent,
            AUTO_DRAFT_DETAIL_DIR,
            AUTO_DRAFT_APPENDIX_DIR,
            RULES_EXPORT_PATH.parent,
            FORMAL_EXPORT_PATH.parent,
            SCORE_MAP_DRAFT_EXPORT_PATH.parent,
            CLOSURE_EXPORT_PATH.parent,
            REVIEW_ENTRY_DIR,
        ]
    )

    if output_layout == OUTPUT_LAYOUT_SPLIT:
        split_outputs = render_split_auto_adjudication_outputs(
            include_display_warnings=include_display_warnings,
            warning_rules=warning_rules,
        )
        write_markdown_outputs(split_outputs)
        remove_legacy_flat_exports()
        if validate_output:
            validation_root = MARKDOWN_VIEW_ROOT.parent.parent
            targets = list(config_loaders.get_i5b_trial_config().get("targets") or [])
            errors = human_readable_markdown_validator.validate_exports(validation_root, targets)
            if errors:
                raise HumanReadableMarkdownValidationError(errors)
    else:
        write_markdown_outputs(
            {
                EXPORT_PATH: render_auto_adjudication(
                    include_display_warnings=include_display_warnings,
                    warning_rules=warning_rules,
                )
            }
        )
    write_markdown_outputs(
        {
            RULES_EXPORT_PATH: render_rule_sensitive_points(),
            FORMAL_EXPORT_PATH: render_formal_landing_table(),
            SCORE_MAP_DRAFT_EXPORT_PATH: render_score_mapping_draft(),
        }
    )
    closure_content = render_three_pilot_closure()
    write_markdown_outputs({CLOSURE_EXPORT_PATH: closure_content})
    write_markdown_outputs(render_review_entry_outputs())
    remove_legacy_flat_exports()
    return EXPORT_PATH, RULES_EXPORT_PATH, FORMAL_EXPORT_PATH, CLOSURE_EXPORT_PATH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-display-warnings",
        action="store_true",
        default=False,
        help="include display-only human review warning section in the auto adjudication draft",
    )
    parser.add_argument(
        "--output-layout",
        choices=[OUTPUT_LAYOUT_CANONICAL, OUTPUT_LAYOUT_SPLIT],
        default=OUTPUT_LAYOUT_CANONICAL,
        help="choose canonical full-view export or Typora-friendly split export",
    )
    parser.add_argument(
        "--split-by-person",
        action="store_true",
        default=False,
        help="shortcut for --output-layout split",
    )
    parser.add_argument(
        "--skip-output-validation",
        action="store_true",
        default=False,
        help="debug-only escape hatch: skip post-export validation for split markdown output; not recommended for normal use",
    )
    args = parser.parse_args(argv)
    output_layout = OUTPUT_LAYOUT_SPLIT if args.split_by_person else args.output_layout

    try:
        export_path, rules_path, formal_path, closure_path = export_auto_adjudication(
            include_display_warnings=args.include_display_warnings,
            output_layout=output_layout,
            validate_output=not args.skip_output_validation,
        )
    except HumanReadableMarkdownValidationError as exc:
        print("Human-readable Markdown export validation failed:")
        for error in exc.errors:
            print(f"- {error}")
        return 1
    print(f"exported {export_path}")
    if output_layout == OUTPUT_LAYOUT_SPLIT:
        context = build_auto_adjudication_context()
        for report in context["person_reports"]:
            print(f"exported {person_detail_export_path(report['person'])}")
        if not args.skip_output_validation:
            print("validated human-readable split markdown exports")
    print(f"exported {rules_path}")
    print(f"exported {formal_path}")
    print(f"exported {SCORE_MAP_DRAFT_EXPORT_PATH}")
    print(f"exported {closure_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
