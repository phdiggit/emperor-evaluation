from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from export_md_scaffold import escape_cell, join_list_cell, read_jsonl
from i5b_markdown_display import display_field_label, display_value, human_review_table_fields, load_display_dictionary


ROOT = Path(__file__).resolve().parents[2]
I5B_HUMAN_AUTO_CHAIN_ROOT = ROOT / "exports" / "markdown_views" / "第五项B" / "人工审核" / "自动裁判链"

READINESS_AUDIT_BATCH_PATH = ROOT / "data" / "audit_batches" / "i5b_expanded_pilot_batch1_readiness_audit_20260619.jsonl"
READINESS_AUDIT_EXPORT_PATH = I5B_HUMAN_AUTO_CHAIN_ROOT / "试点闭环" / "第五项B扩展试点第一批人工裁判准备审计.md"
YONGZHENG_RULE_BOUNDARY_BATCH_PATH = ROOT / "data" / "rule_boundary_batches" / "i5b_yongzheng_rule_boundary_review_20260619.jsonl"
ZHUYUANZHANG_MICRO_SUPPLEMENT_SOURCE_BATCH_PATH = ROOT / "data" / "source_batches" / "i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl"
ZHUYUANZHANG_MICRO_SUPPLEMENT_EVIDENCE_BATCH_PATH = ROOT / "data" / "evidence_card_batches" / "i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl"
READINESS_FOLLOWUP_BATCH_PATH = ROOT / "data" / "audit_batches" / "i5b_expanded_pilot_batch1_readiness_followup_20260619.jsonl"
READINESS_FOLLOWUP_EXPORT_PATH = I5B_HUMAN_AUTO_CHAIN_ROOT / "试点闭环" / "第五项B扩展试点第一批readiness后续处理.md"
HUMAN_REVIEW_PACKAGE_BATCH_PATH = ROOT / "data" / "review_packages" / "i5b_expanded_pilot_batch1_human_review_package_20260619.jsonl"
HUMAN_REVIEW_PACKAGE_EXPORT_PATH = I5B_HUMAN_AUTO_CHAIN_ROOT / "试点闭环" / "第五项B扩展试点第一批人工会审准备包.md"
RELATIVE_BAND_PREPARATION_BATCH_PATH = ROOT / "data" / "relative_band_batches" / "i5b_expanded_pilot_batch1_relative_band_preparation_20260619.jsonl"
RELATIVE_BAND_PREPARATION_EXPORT_PATH = I5B_HUMAN_AUTO_CHAIN_ROOT / "正式定档草案" / "第五项B扩展试点第一批相对档位准备草案.md"


def _human_display_config() -> dict[str, object]:
    config = dict(load_display_dictionary())
    config["keep_machine_field_name"] = False
    labels = dict(config.get("field_labels") or {})
    labels.update(
        {
            "evidence_id": "证据编号",
            "source_id": "来源编号",
            "cluster_id": "证据簇编号",
            "linked_evidence_ids": "关联证据编号",
        }
    )
    config["field_labels"] = labels
    return config


def _label(field: str, config: dict[str, object]) -> str:
    return display_field_label(field, config)


def _value(value: object, config: dict[str, object]) -> str:
    return display_value(value, config)


def _list_value(value: object, config: dict[str, object]) -> str:
    if isinstance(value, list):
        return "；".join(_value(item, config) for item in value)
    return _value(value, config)


def _table(headers: list[str], rows: list[dict[str, object]], config: dict[str, object]) -> list[str]:
    lines = [
        "| " + " | ".join(_label(header, config) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(_value(row.get(header), config)) for header in headers) + " |")
    return lines


def _human_table_fields(table_key: str, config: dict[str, object]) -> list[str]:
    return human_review_table_fields(table_key, config)


def export_expanded_i5b_batch1_readiness_audit() -> Path:
    READINESS_AUDIT_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    display_config = _human_display_config()

    rows = read_jsonl(READINESS_AUDIT_BATCH_PATH)
    person_rows = [row for row in rows if row.get("row_type") != "batch_rule_pressure_summary"]
    summary_rows = [row for row in rows if row.get("row_type") == "batch_rule_pressure_summary"]

    lines = [
        "# 第五项B扩展试点第一批人工裁判准备审计",
        "",
        "本文仅用于人工裁判准备审计，不定档，不出分，不排名，不出总榜。",
        "",
        "## 人员准备度总览",
        "",
        *_table(
            _human_table_fields("expanded_batch_readiness", display_config),
            person_rows,
            display_config,
        ),
    ]

    lines.extend(["", "## 逐人审计", ""])
    for row in person_rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- {_label('current_draft_status', display_config)}：{_value(row.get('current_draft_status'), display_config)}",
                f"- {_label('stabilized_findings', display_config)}：{_list_value(row.get('stabilized_findings'), display_config)}",
                f"- {_label('unstable_findings', display_config)}：{_list_value(row.get('unstable_findings'), display_config)}",
                f"- {_label('must_human_review_points', display_config)}：{_list_value(row.get('must_human_review_points'), display_config)}",
                f"- {_label('rule_pressure_points', display_config)}：{_list_value(row.get('rule_pressure_points'), display_config)}",
                f"- {_label('cross_item_split_risks', display_config)}：{_list_value(row.get('cross_item_split_risks'), display_config)}",
                f"- {_label('negative_intercept_review_needed', display_config)}：{_value(row.get('negative_intercept_review_needed'), display_config)}",
                f"- {_label('remaining_evidence_gaps', display_config)}：{_list_value(row.get('remaining_evidence_gaps'), display_config)}",
                f"- {_label('recommended_next_step', display_config)}：{_value(row.get('recommended_next_step'), display_config)}",
                f"- {_label('status', display_config)}：{_value(row.get('status'), display_config)}",
                "",
            ]
        )

    if summary_rows:
        summary = summary_rows[0]
        lines.extend(
            [
                "## 批次级规则压力总结",
                "",
                f"- {_label('batch_rule_pressure_id', display_config)}：{_value(summary.get('batch_rule_pressure_id'), display_config)}",
                f"- {_label('stable_rule_lessons', display_config)}：{_list_value(summary.get('stable_rule_lessons'), display_config)}",
                f"- {_label('open_rule_questions', display_config)}：{_list_value(summary.get('open_rule_questions'), display_config)}",
                f"- {_label('recommended_workflow_patches', display_config)}：{_list_value(summary.get('recommended_workflow_patches'), display_config)}",
                f"- {_label('not_for_scoring_statement', display_config)}：{_value(summary.get('not_for_scoring_statement'), display_config)}",
                f"- {_label('status', display_config)}：{_value(summary.get('status'), display_config)}",
                "",
            ]
        )

    lines.extend(["## 审计结语", "", "本审计只给出人工裁判准备建议，不转为正式档位或分数。"])

    READINESS_AUDIT_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return READINESS_AUDIT_EXPORT_PATH


def export_expanded_i5b_batch1_readiness_followup() -> Path:
    READINESS_FOLLOWUP_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    display_config = _human_display_config()

    boundary_rows = read_jsonl(YONGZHENG_RULE_BOUNDARY_BATCH_PATH)
    source_rows = read_jsonl(ZHUYUANZHANG_MICRO_SUPPLEMENT_SOURCE_BATCH_PATH)
    evidence_rows = read_jsonl(ZHUYUANZHANG_MICRO_SUPPLEMENT_EVIDENCE_BATCH_PATH)
    followup_rows = read_jsonl(READINESS_FOLLOWUP_BATCH_PATH)
    person_followup_rows = [row for row in followup_rows if row.get("row_type") != "batch_followup_summary"]

    lines = [
        "# 第五项B扩展试点第一批readiness后续处理",
        "",
        "本文仅用于 readiness 后续处理，不定档，不出分，不排名，不出总榜。",
    ]

    if boundary_rows:
        row = boundary_rows[0]
        lines.extend(
            [
                "",
                "## 雍正规则边界复核",
                "",
                f"- {_label('review_id', display_config)}：{_value(row.get('review_id'), display_config)}",
                f"- {_label('input_readiness_id', display_config)}：{_value(row.get('input_readiness_id'), display_config)}",
                f"- {_label('boundary_questions', display_config)}：{_list_value(row.get('boundary_questions'), display_config)}",
                f"- {_label('resolved_boundary_points', display_config)}：{_list_value(row.get('resolved_boundary_points'), display_config)}",
                f"- {_label('open_boundary_points', display_config)}：{_list_value(row.get('open_boundary_points'), display_config)}",
                f"- {_label('not_carded_people_review', display_config)}：{_list_value(row.get('not_carded_people_review'), display_config)}",
                f"- {_label('cross_item_split_guardrails', display_config)}：{_list_value(row.get('cross_item_split_guardrails'), display_config)}",
                f"- {_label('recommended_next_step', display_config)}：{_value(row.get('recommended_next_step'), display_config)}",
                f"- {_label('not_for_scoring_statement', display_config)}：{_value(row.get('not_for_scoring_statement'), display_config)}",
                f"- {_label('status', display_config)}：{_value(row.get('status'), display_config)}",
            ]
        )

    lines.extend(
        [
            "",
            "## 朱元璋 micro supplement 来源",
            "",
            *_table(_human_table_fields("targeted_supplement_sources", display_config), source_rows, display_config),
        ]
    )

    lines.extend(
        [
            "",
            "## 朱元璋 micro supplement 证据卡",
            "",
            *_table(_human_table_fields("micro_supplement_evidence_cards", display_config), evidence_rows, display_config),
        ]
    )

    lines.extend(
        [
            "",
            "## readiness follow-up 人物总览",
            "",
            *_table(_human_table_fields("expanded_batch_followup", display_config), person_followup_rows, display_config),
            "",
            "## readiness follow-up summary",
            "",
        ]
    )
    for row in followup_rows:
        if row.get("row_type") == "batch_followup_summary":
            lines.extend(
                [
                    f"- {_label('batch_followup_id', display_config)}：{_value(row.get('batch_followup_id'), display_config)}",
                    f"- {_label('batch_next_step_summary', display_config)}：{_value(row.get('batch_next_step_summary'), display_config)}",
                    f"- {_label('not_for_scoring_statement', display_config)}：{_value(row.get('not_for_scoring_statement'), display_config)}",
                    f"- {_label('status', display_config)}：{_value(row.get('status'), display_config)}",
                    "",
                ]
            )
            continue
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- {_label('prior_readiness_id', display_config)}：{_value(row.get('prior_readiness_id'), display_config)}",
                f"- {_label('prior_next_step', display_config)}：{_value(row.get('prior_next_step'), display_config)}",
                f"- {_label('followup_action', display_config)}：{_value(row.get('followup_action'), display_config)}",
                f"- {_label('followup_outcome_summary', display_config)}：{_value(row.get('followup_outcome_summary'), display_config)}",
                f"- {_label('current_readiness_recommendation', display_config)}：{_value(row.get('current_readiness_recommendation'), display_config)}",
                f"- {_label('remaining_notes', display_config)}：{_list_value(row.get('remaining_notes'), display_config)}",
                f"- {_label('status', display_config)}：{_value(row.get('status'), display_config)}",
                "",
            ]
        )

    lines.extend(["## 结语", "", "本轮只生成后续处理建议，不转为正式档位或分数。"])

    READINESS_FOLLOWUP_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return READINESS_FOLLOWUP_EXPORT_PATH


def export_expanded_i5b_batch1_human_review_package() -> Path:
    HUMAN_REVIEW_PACKAGE_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    display_config = _human_display_config()

    rows = read_jsonl(HUMAN_REVIEW_PACKAGE_BATCH_PATH)
    person_rows = [row for row in rows if row.get("row_type") != "batch_review_agenda"]
    agenda_rows = [row for row in rows if row.get("row_type") == "batch_review_agenda"]

    lines = [
        "# 第五项B扩展试点第一批人工会审准备包",
        "",
        "本文仅用于人工会审准备，不定档，不出分，不排名，不出总榜。",
        "",
        "## 会审总览",
        "",
        *_table(
            _human_table_fields("human_review_package_overview", display_config),
            person_rows,
            display_config,
        ),
    ]

    lines.extend(["", "## 逐人会审焦点", ""])
    for row in person_rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- {_label('input_followup_id', display_config)}：{_value(row.get('input_followup_id'), display_config)}",
                f"- {_label('current_readiness_recommendation', display_config)}：{_value(row.get('current_readiness_recommendation'), display_config)}",
                f"- {_label('core_rule_question', display_config)}：{_value(row.get('core_rule_question'), display_config)}",
                f"- {_label('evidence_pressure_summary', display_config)}：{_value(row.get('evidence_pressure_summary'), display_config)}",
                f"- {_label('negative_intercept_gate', display_config)}：{_value(row.get('negative_intercept_gate'), display_config)}",
                f"- {_label('cross_item_split_gate', display_config)}：{_value(row.get('cross_item_split_gate'), display_config)}",
                f"- {_label('possible_human_review_paths', display_config)}：{_list_value(row.get('possible_human_review_paths'), display_config)}",
                f"- {_label('recommended_human_review_focus', display_config)}：{_value(row.get('recommended_human_review_focus'), display_config)}",
                f"- {_label('forbidden_shortcuts', display_config)}：{_list_value(row.get('forbidden_shortcuts'), display_config)}",
                f"- {_label('not_for_scoring_statement', display_config)}：{_value(row.get('not_for_scoring_statement'), display_config)}",
                f"- {_label('status', display_config)}：{_value(row.get('status'), display_config)}",
                "",
            ]
        )

    if agenda_rows:
        row = agenda_rows[0]
        lines.extend(
            [
                "## 批次级会审议程",
                "",
                f"- {_label('batch_review_agenda_id', display_config)}：{_value(row.get('batch_review_agenda_id'), display_config)}",
                f"- {_label('shared_rule_questions', display_config)}：{_list_value(row.get('shared_rule_questions'), display_config)}",
                f"- {_label('shared_negative_intercept_gate', display_config)}：{_value(row.get('shared_negative_intercept_gate'), display_config)}",
                f"- {_label('shared_cross_item_split_gate', display_config)}：{_value(row.get('shared_cross_item_split_gate'), display_config)}",
                f"- {_label('workflow_lessons', display_config)}：{_list_value(row.get('workflow_lessons'), display_config)}",
                f"- {_label('decision_points_for_user', display_config)}：{_list_value(row.get('decision_points_for_user'), display_config)}",
                f"- {_label('not_for_scoring_statement', display_config)}：{_value(row.get('not_for_scoring_statement'), display_config)}",
                f"- {_label('status', display_config)}：{_value(row.get('status'), display_config)}",
                "",
            ]
        )

    lines.extend(["## 下一步建议", "", "本准备包只进入规则、边界与裁判路径会审，不形成正式档位或分数。"])

    HUMAN_REVIEW_PACKAGE_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return HUMAN_REVIEW_PACKAGE_EXPORT_PATH


def export_expanded_i5b_batch1_relative_band_preparation() -> Path:
    RELATIVE_BAND_PREPARATION_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    display_config = _human_display_config()

    rows = read_jsonl(RELATIVE_BAND_PREPARATION_BATCH_PATH)
    person_rows = [row for row in rows if row.get("row_type") != "batch_relative_band_summary"]
    summary_rows = [row for row in rows if row.get("row_type") == "batch_relative_band_summary"]

    lines = [
        "# 第五项B扩展试点第一批相对档位准备草案",
        "",
        "本文仅用于相对档位准备，不定档，不出分，不排名，不出总榜。",
        "",
        "## 逐人准备表",
        "",
        *_table(
            _human_table_fields("relative_band_preparation", display_config),
            person_rows,
            display_config,
        ),
    ]

    lines.extend(["", "## 逐人准备细节", ""])
    for row in person_rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- {_label('relative_band_draft_id', display_config)}：{_value(row.get('relative_band_draft_id'), display_config)}",
                f"- {_label('input_review_package_id', display_config)}：{_value(row.get('input_review_package_id'), display_config)}",
                f"- {_label('current_review_stage', display_config)}：{_value(row.get('current_review_stage'), display_config)}",
                f"- {_label('rule_based_positioning_summary', display_config)}：{_value(row.get('rule_based_positioning_summary'), display_config)}",
                f"- {_label('positive_base_status', display_config)}：{_value(row.get('positive_base_status'), display_config)}",
                f"- {_label('negative_gate_status', display_config)}：{_value(row.get('negative_gate_status'), display_config)}",
                f"- {_label('cross_item_split_status', display_config)}：{_value(row.get('cross_item_split_status'), display_config)}",
                f"- {_label('relative_band_path_options', display_config)}：{_list_value(row.get('relative_band_path_options'), display_config)}",
                f"- {_label('human_confirmation_questions', display_config)}：{_list_value(row.get('human_confirmation_questions'), display_config)}",
                f"- {_label('blocked_shortcuts', display_config)}：{_list_value(row.get('blocked_shortcuts'), display_config)}",
                f"- {_label('next_step_recommendation', display_config)}：{_value(row.get('next_step_recommendation'), display_config)}",
                f"- {_label('not_for_scoring_statement', display_config)}：{_value(row.get('not_for_scoring_statement'), display_config)}",
                f"- {_label('status', display_config)}：{_value(row.get('status'), display_config)}",
                "",
            ]
        )

    if summary_rows:
        row = summary_rows[0]
        lines.extend(
            [
                "## 批次级规则准备摘要",
                "",
                f"- {_label('batch_relative_band_draft_id', display_config)}：{_value(row.get('batch_relative_band_draft_id'), display_config)}",
                f"- {_label('shared_positioning_rules', display_config)}：{_list_value(row.get('shared_positioning_rules'), display_config)}",
                f"- {_label('shared_negative_gate_rules', display_config)}：{_list_value(row.get('shared_negative_gate_rules'), display_config)}",
                f"- {_label('shared_cross_item_split_rules', display_config)}：{_list_value(row.get('shared_cross_item_split_rules'), display_config)}",
                f"- {_label('user_decision_questions', display_config)}：{_list_value(row.get('user_decision_questions'), display_config)}",
                f"- {_label('next_workflow_options', display_config)}：{_list_value(row.get('next_workflow_options'), display_config)}",
                f"- {_label('not_for_scoring_statement', display_config)}：{_value(row.get('not_for_scoring_statement'), display_config)}",
                f"- {_label('status', display_config)}：{_value(row.get('status'), display_config)}",
                "",
            ]
        )

    lines.extend(["## 下一步建议", "", "本草案只供相对档位讨论前的规则确认，不定档，不出分，不排名，不出总榜。"])

    RELATIVE_BAND_PREPARATION_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return RELATIVE_BAND_PREPARATION_EXPORT_PATH
