from __future__ import annotations

from pathlib import Path

from export_md_scaffold import escape_cell, join_list_cell, read_jsonl


ROOT = Path(__file__).resolve().parents[1]
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


def export_expanded_i5b_batch1_readiness_audit() -> Path:
    READINESS_AUDIT_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

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
        "| readiness_id | person | current_draft_status | recommended_next_step | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in person_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(row.get("readiness_id")),
                    escape_cell(row.get("person")),
                    escape_cell(row.get("current_draft_status")),
                    escape_cell(row.get("recommended_next_step")),
                    escape_cell(row.get("status")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## 逐人审计", ""])
    for row in person_rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- current draft status：{row.get('current_draft_status') or ''}",
                f"- stabilized findings：{join_list_cell(row.get('stabilized_findings'))}",
                f"- unstable findings：{join_list_cell(row.get('unstable_findings'))}",
                f"- must human review points：{join_list_cell(row.get('must_human_review_points'))}",
                f"- rule pressure points：{join_list_cell(row.get('rule_pressure_points'))}",
                f"- cross item split risks：{join_list_cell(row.get('cross_item_split_risks'))}",
                f"- negative intercept review needed：{row.get('negative_intercept_review_needed') or ''}",
                f"- remaining evidence gaps：{join_list_cell(row.get('remaining_evidence_gaps'))}",
                f"- recommended next step：{row.get('recommended_next_step') or ''}",
                f"- status：{row.get('status') or ''}",
                "",
            ]
        )

    if summary_rows:
        summary = summary_rows[0]
        lines.extend(
            [
                "## 批次级规则压力总结",
                "",
                f"- batch_rule_pressure_id：{summary.get('batch_rule_pressure_id') or ''}",
                f"- stable_rule_lessons：{join_list_cell(summary.get('stable_rule_lessons'))}",
                f"- open_rule_questions：{join_list_cell(summary.get('open_rule_questions'))}",
                f"- recommended_workflow_patches：{join_list_cell(summary.get('recommended_workflow_patches'))}",
                f"- not_for_scoring_statement：{summary.get('not_for_scoring_statement') or ''}",
                f"- status：{summary.get('status') or ''}",
                "",
            ]
        )

    lines.extend(["## 审计结语", "", "本审计只给出人工裁判准备建议，不转为正式档位或分数。"])

    READINESS_AUDIT_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return READINESS_AUDIT_EXPORT_PATH


def export_expanded_i5b_batch1_readiness_followup() -> Path:
    READINESS_FOLLOWUP_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    boundary_rows = read_jsonl(YONGZHENG_RULE_BOUNDARY_BATCH_PATH)
    source_rows = read_jsonl(ZHUYUANZHANG_MICRO_SUPPLEMENT_SOURCE_BATCH_PATH)
    evidence_rows = read_jsonl(ZHUYUANZHANG_MICRO_SUPPLEMENT_EVIDENCE_BATCH_PATH)
    followup_rows = read_jsonl(READINESS_FOLLOWUP_BATCH_PATH)

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
                f"- review_id：{row.get('review_id') or ''}",
                f"- input_readiness_id：{row.get('input_readiness_id') or ''}",
                f"- boundary_questions：{join_list_cell(row.get('boundary_questions'))}",
                f"- resolved_boundary_points：{join_list_cell(row.get('resolved_boundary_points'))}",
                f"- open_boundary_points：{join_list_cell(row.get('open_boundary_points'))}",
                f"- not_carded_people_review：{join_list_cell(row.get('not_carded_people_review'))}",
                f"- cross_item_split_guardrails：{join_list_cell(row.get('cross_item_split_guardrails'))}",
                f"- recommended_next_step：{row.get('recommended_next_step') or ''}",
                f"- not_for_scoring_statement：{row.get('not_for_scoring_statement') or ''}",
                f"- status：{row.get('status') or ''}",
            ]
        )

    lines.extend(
        [
            "",
            "## 朱元璋 micro supplement 来源",
            "",
            "| source_id | title | volume | location | url |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in source_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(row.get("source_id")),
                    escape_cell(row.get("title")),
                    escape_cell(row.get("volume")),
                    escape_cell(row.get("location")),
                    escape_cell(row.get("url")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 朱元璋 micro supplement 证据卡",
            "",
            "| evidence_id | polarity | source_id | object_anchor | micro_gap_addressed |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in evidence_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(row.get("evidence_id")),
                    escape_cell(row.get("polarity")),
                    escape_cell(row.get("source_id")),
                    escape_cell(row.get("object_anchor")),
                    escape_cell(row.get("micro_gap_addressed")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## readiness follow-up summary", ""])
    for row in followup_rows:
        if row.get("row_type") == "batch_followup_summary":
            lines.extend(
                [
                    f"- batch_followup_id：{row.get('batch_followup_id') or ''}",
                    f"- batch_next_step_summary：{row.get('batch_next_step_summary') or ''}",
                    f"- not_for_scoring_statement：{row.get('not_for_scoring_statement') or ''}",
                    f"- status：{row.get('status') or ''}",
                    "",
                ]
            )
            continue
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- prior_readiness_id：{row.get('prior_readiness_id') or ''}",
                f"- prior_next_step：{row.get('prior_next_step') or ''}",
                f"- followup_action：{row.get('followup_action') or ''}",
                f"- followup_outcome_summary：{row.get('followup_outcome_summary') or ''}",
                f"- current_readiness_recommendation：{row.get('current_readiness_recommendation') or ''}",
                f"- remaining_notes：{join_list_cell(row.get('remaining_notes'))}",
                f"- status：{row.get('status') or ''}",
                "",
            ]
        )

    lines.extend(["## 结语", "", "本轮只生成后续处理建议，不转为正式档位或分数。"])

    READINESS_FOLLOWUP_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return READINESS_FOLLOWUP_EXPORT_PATH


def export_expanded_i5b_batch1_human_review_package() -> Path:
    HUMAN_REVIEW_PACKAGE_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

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
        "| review_package_id | person | current_readiness_recommendation | core_rule_question | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in person_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(row.get("review_package_id")),
                    escape_cell(row.get("person")),
                    escape_cell(row.get("current_readiness_recommendation")),
                    escape_cell(row.get("core_rule_question")),
                    escape_cell(row.get("status")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## 逐人会审焦点", ""])
    for row in person_rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- input_followup_id：{row.get('input_followup_id') or ''}",
                f"- current_readiness_recommendation：{row.get('current_readiness_recommendation') or ''}",
                f"- core_rule_question：{row.get('core_rule_question') or ''}",
                f"- evidence_pressure_summary：{row.get('evidence_pressure_summary') or ''}",
                f"- negative_intercept_gate：{row.get('negative_intercept_gate') or ''}",
                f"- cross_item_split_gate：{row.get('cross_item_split_gate') or ''}",
                f"- possible_human_review_paths：{join_list_cell(row.get('possible_human_review_paths'))}",
                f"- recommended_human_review_focus：{row.get('recommended_human_review_focus') or ''}",
                f"- forbidden_shortcuts：{join_list_cell(row.get('forbidden_shortcuts'))}",
                f"- not_for_scoring_statement：{row.get('not_for_scoring_statement') or ''}",
                f"- status：{row.get('status') or ''}",
                "",
            ]
        )

    if agenda_rows:
        row = agenda_rows[0]
        lines.extend(
            [
                "## 批次级会审议程",
                "",
                f"- batch_review_agenda_id：{row.get('batch_review_agenda_id') or ''}",
                f"- shared_rule_questions：{join_list_cell(row.get('shared_rule_questions'))}",
                f"- shared_negative_intercept_gate：{row.get('shared_negative_intercept_gate') or ''}",
                f"- shared_cross_item_split_gate：{row.get('shared_cross_item_split_gate') or ''}",
                f"- workflow_lessons：{join_list_cell(row.get('workflow_lessons'))}",
                f"- decision_points_for_user：{join_list_cell(row.get('decision_points_for_user'))}",
                f"- not_for_scoring_statement：{row.get('not_for_scoring_statement') or ''}",
                f"- status：{row.get('status') or ''}",
                "",
            ]
        )

    lines.extend(["## 下一步建议", "", "本准备包只进入规则、边界与裁判路径会审，不形成正式档位或分数。"])

    HUMAN_REVIEW_PACKAGE_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return HUMAN_REVIEW_PACKAGE_EXPORT_PATH


def export_expanded_i5b_batch1_relative_band_preparation() -> Path:
    RELATIVE_BAND_PREPARATION_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

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
        "| relative_band_draft_id | person | input_review_package_id | current_review_stage | positive_base_status | negative_gate_status | cross_item_split_status | next_step_recommendation | status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in person_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(row.get("relative_band_draft_id")),
                    escape_cell(row.get("person")),
                    escape_cell(row.get("input_review_package_id")),
                    escape_cell(row.get("current_review_stage")),
                    escape_cell(row.get("positive_base_status")),
                    escape_cell(row.get("negative_gate_status")),
                    escape_cell(row.get("cross_item_split_status")),
                    escape_cell(row.get("next_step_recommendation")),
                    escape_cell(row.get("status")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## 逐人准备细节", ""])
    for row in person_rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- relative_band_draft_id：{row.get('relative_band_draft_id') or ''}",
                f"- input_review_package_id：{row.get('input_review_package_id') or ''}",
                f"- current_review_stage：{row.get('current_review_stage') or ''}",
                f"- rule_based_positioning_summary：{row.get('rule_based_positioning_summary') or ''}",
                f"- positive_base_status：{row.get('positive_base_status') or ''}",
                f"- negative_gate_status：{row.get('negative_gate_status') or ''}",
                f"- cross_item_split_status：{row.get('cross_item_split_status') or ''}",
                f"- relative_band_path_options：{join_list_cell(row.get('relative_band_path_options'))}",
                f"- human_confirmation_questions：{join_list_cell(row.get('human_confirmation_questions'))}",
                f"- blocked_shortcuts：{join_list_cell(row.get('blocked_shortcuts'))}",
                f"- next_step_recommendation：{row.get('next_step_recommendation') or ''}",
                f"- not_for_scoring_statement：{row.get('not_for_scoring_statement') or ''}",
                f"- status：{row.get('status') or ''}",
                "",
            ]
        )

    if summary_rows:
        row = summary_rows[0]
        lines.extend(
            [
                "## 批次级规则准备摘要",
                "",
                f"- batch_relative_band_draft_id：{row.get('batch_relative_band_draft_id') or ''}",
                f"- shared_positioning_rules：{join_list_cell(row.get('shared_positioning_rules'))}",
                f"- shared_negative_gate_rules：{join_list_cell(row.get('shared_negative_gate_rules'))}",
                f"- shared_cross_item_split_rules：{join_list_cell(row.get('shared_cross_item_split_rules'))}",
                f"- user_decision_questions：{join_list_cell(row.get('user_decision_questions'))}",
                f"- next_workflow_options：{join_list_cell(row.get('next_workflow_options'))}",
                f"- not_for_scoring_statement：{row.get('not_for_scoring_statement') or ''}",
                f"- status：{row.get('status') or ''}",
                "",
            ]
        )

    lines.extend(["## 下一步建议", "", "本草案只供相对档位讨论前的规则确认，不定档，不出分，不排名，不出总榜。"])

    RELATIVE_BAND_PREPARATION_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return RELATIVE_BAND_PREPARATION_EXPORT_PATH
