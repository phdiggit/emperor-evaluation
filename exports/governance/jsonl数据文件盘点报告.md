# JSONL 数据文件盘点报告

- 扫描日期：2026-06-24
- 扫描范围：`git ls-files "*.jsonl"` 返回的 tracked JSONL。
- 扫描方法：实时统计非空行、抽取每个文件首批 JSON object 的主 ID 字段、用 `git grep` 对 `scripts/`、`tests/`、`docs/`、`data/` 做静态引用扫描，并对 batch 主 ID 与 canonical 主表做吸收检查。
- 重要边界：本报告只盘点和分类，不删除、不迁移、不归档、不合并任何 JSONL。

## 1. 执行摘要

- tracked JSONL 总数：40
- 总非空行数：432
- 按主标签数量：canonical=8；canonical_lane=3；active_batch=12；merged_batch=7；review_only_batch=8；archive_candidate=2；delete_candidate=0
- 关键风险摘要：`data/query_profile_batches/i5b_next_four_profiles_20260618.jsonl` 与 `data/search_log_batches/i5b_liubang_supplemental_safety_20260618.jsonl` 未发现执行引用且未完全进入 canonical；多组已吸收 Liu Bang batch 仍留在 active data 目录；若 #231 收束前直接删除 active_batch，会影响 exporter、validator 或 tests。

## 2. 按目录统计
| directory | files | non_empty_lines | 初步判断 |
| --- | --- | --- | --- |
| data | 11 | 251 | 顶层 canonical / canonical_lane 主数据 |
| data/adjudication_batches | 2 | 6 | 批次或复核材料，#231 需按标签收束 |
| data/audit_batches | 2 | 8 | 批次或复核材料，#231 需按标签收束 |
| data/evidence_card_batches | 6 | 44 | 批次或复核材料，#231 需按标签收束 |
| data/evidence_cluster_batches | 2 | 8 | 批次或复核材料，#231 需按标签收束 |
| data/query_profile_batches | 3 | 10 | 批次或复核材料，#231 需按标签收束 |
| data/relative_band_batches | 1 | 4 | 批次或复核材料，#231 需按标签收束 |
| data/review_packages | 1 | 4 | 批次或复核材料，#231 需按标签收束 |
| data/rule_boundary_batches | 1 | 1 | 批次或复核材料，#231 需按标签收束 |
| data/search_log_batches | 3 | 43 | 批次或复核材料，#231 需按标签收束 |
| data/source_batches | 6 | 36 | 批次或复核材料，#231 需按标签收束 |
| data/sweep_batches | 1 | 5 | 批次或复核材料，#231 需按标签收束 |
| data/thematic_anchor_batches | 1 | 12 | 批次或复核材料，#231 需按标签收束 |

## 3. 按标签统计
| status_label | files | non_empty_lines | 说明 |
| --- | --- | --- | --- |
| canonical | 8 | 239 | 当前主事实源或顶层主表，长期保留。 |
| canonical_lane | 3 | 12 | 稳定 lane；当前并非全部进入 build_db，但已进入 canonical integrity 校验。 |
| active_batch | 12 | 119 | 仍被 validator、exporter 或 tests 引用，#231 不应直接删。 |
| merged_batch | 7 | 23 | 内容疑似已合入 canonical，但需 #231 复核后再处置。 |
| review_only_batch | 8 | 28 | 审计、readiness、human review、relative band、rule boundary、sweep 或裁量复核材料。 |
| archive_candidate | 2 | 11 | 无执行引用或未完全吸收，需人工确认唯一性后归档。 |
| delete_candidate | 0 | 0 | 本轮保守使用；当前未直接给出删除候选。 |

## 4. 全量文件清单

`downstream_refs` 为静态扫描结果；`absorbed_by_canonical` 仅对可映射到 canonical 主表或 canonical lane 的 batch 计算。
| path | lines | directory | primary_id_field | status_label | confidence | rationale | downstream_refs | absorbed_by_canonical | proposed_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| data/adjudication_batches/i5b_expanded_pilot_batch1_cluster_adjudication_20260619.jsonl | 3 | data/adjudication_batches | adjudication_id | review_only_batch | high | 文件位于审计、裁量、readiness、human review、relative band、rule boundary 或 sweep 复核批次目录。 | i5b_exporter, tests | n/a | #231 只做归档/保留审查，不把它当作数据主源。 |
| data/adjudication_batches/i5b_expanded_pilot_batch1_post_supplement_adjudication_20260619.jsonl | 3 | data/adjudication_batches | adjudication_id | review_only_batch | high | 文件位于审计、裁量、readiness、human review、relative band、rule boundary 或 sweep 复核批次目录。 | i5b_exporter, tests | n/a | #231 只做归档/保留审查，不把它当作数据主源。 |
| data/audit_batches/i5b_expanded_pilot_batch1_readiness_audit_20260619.jsonl | 4 | data/audit_batches | readiness_id | review_only_batch | high | 文件位于审计、裁量、readiness、human review、relative band、rule boundary 或 sweep 复核批次目录。 | i5b_exporter, tests | n/a | #231 只做归档/保留审查，不把它当作数据主源。 |
| data/audit_batches/i5b_expanded_pilot_batch1_readiness_followup_20260619.jsonl | 4 | data/audit_batches | followup_id | review_only_batch | high | 文件位于审计、裁量、readiness、human review、relative band、rule boundary 或 sweep 复核批次目录。 | i5b_exporter, tests | n/a | #231 只做归档/保留审查，不把它当作数据主源。 |
| data/events.jsonl | 0 | data | unknown | canonical | high | 顶层主表；build/validate/export/tests 静态扫描用于确认当前对齐情况。 | build_db, validate_all, tests, docs_only | n/a | 长期保留；后续只通过正式数据流程更新。 |
| data/evidence_card_batches/i5b_expanded_pilot_batch1_20260619.jsonl | 18 | data/evidence_card_batches | evidence_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | i5b_exporter, tests | 18/18 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/evidence_card_batches/i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl | 11 | data/evidence_card_batches | evidence_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | i5b_exporter, tests | 0/11 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/evidence_card_batches/i5b_liubang_negative_20260618.jsonl | 3 | data/evidence_card_batches | evidence_id | merged_batch | medium | 主 ID 已全部出现在对应 canonical 主表或 canonical lane，且静态扫描未发现执行引用。 | none_found | 3/3 | #231 复核后可进入 archive_candidate 或 delete_candidate 审查。 |
| data/evidence_card_batches/i5b_liubang_positive_20260618.jsonl | 4 | data/evidence_card_batches | evidence_id | merged_batch | medium | 主 ID 已全部出现在对应 canonical 主表或 canonical lane，且静态扫描未发现执行引用。 | none_found | 4/4 | #231 复核后可进入 archive_candidate 或 delete_candidate 审查。 |
| data/evidence_card_batches/i5b_liubang_supplemental_safety_20260618.jsonl | 3 | data/evidence_card_batches | evidence_id | merged_batch | medium | 主 ID 已全部出现在对应 canonical 主表或 canonical lane，且静态扫描未发现执行引用。 | none_found | 3/3 | #231 复核后可进入 archive_candidate 或 delete_candidate 审查。 |
| data/evidence_card_batches/i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl | 5 | data/evidence_card_batches | evidence_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | export_md, i5b_exporter, tests | 0/5 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/evidence_cards.jsonl | 39 | data | evidence_id | canonical | high | 顶层主表；build/validate/export/tests 静态扫描用于确认当前对齐情况。 | build_db, validate_all, i5b_exporter, tests, docs_only | n/a | 长期保留；后续只通过正式数据流程更新。 |
| data/evidence_cluster_batches/i5b_expanded_pilot_batch1_20260619.jsonl | 6 | data/evidence_cluster_batches | cluster_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | i5b_exporter, tests | 6/6 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/evidence_cluster_batches/i5b_liubang_clusters_20260618.jsonl | 2 | data/evidence_cluster_batches | cluster_id | merged_batch | medium | 主 ID 已全部出现在对应 canonical 主表或 canonical lane，且静态扫描未发现执行引用。 | none_found | 2/2 | #231 复核后可进入 archive_candidate 或 delete_candidate 审查。 |
| data/evidence_clusters.jsonl | 12 | data | cluster_id | canonical | high | 顶层主表；build/validate/export/tests 静态扫描用于确认当前对齐情况。 | build_db, validate_all, i5b_exporter, tests, docs_only | n/a | 长期保留；后续只通过正式数据流程更新。 |
| data/query_profile_batches/i5b_expanded_pilot_batch1_20260619.jsonl | 3 | data/query_profile_batches | query_profile_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | i5b_exporter, tests | 0/3 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/query_profile_batches/i5b_next_four_profiles_20260618.jsonl | 4 | data/query_profile_batches | query_profile_id | archive_candidate | medium | 未发现执行引用，但主 ID 尚未全部进入 canonical；保守列为归档候选而非删除候选。 | none_found | 0/4 | #231 人工确认是否仍是唯一数据源；确认前不删除。 |
| data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl | 3 | data/query_profile_batches | query_profile_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | validate_all, tests, data_refs | 3/3 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/query_profiles.jsonl | 4 | data | query_profile_id | canonical | high | 顶层主表；build/validate/export/tests 静态扫描用于确认当前对齐情况。 | build_db, validate_all, tests, docs_only | n/a | 长期保留；后续只通过正式数据流程更新。 |
| data/relative_band_batches/i5b_expanded_pilot_batch1_relative_band_preparation_20260619.jsonl | 4 | data/relative_band_batches | relative_band_draft_id | review_only_batch | high | 文件位于审计、裁量、readiness、human review、relative band、rule boundary 或 sweep 复核批次目录。 | i5b_exporter, tests | n/a | #231 只做归档/保留审查，不把它当作数据主源。 |
| data/review_packages/i5b_expanded_pilot_batch1_human_review_package_20260619.jsonl | 4 | data/review_packages | review_package_id | review_only_batch | high | 文件位于审计、裁量、readiness、human review、relative band、rule boundary 或 sweep 复核批次目录。 | i5b_exporter, tests | n/a | #231 只做归档/保留审查，不把它当作数据主源。 |
| data/rule_boundary_batches/i5b_yongzheng_rule_boundary_review_20260619.jsonl | 1 | data/rule_boundary_batches | review_id | review_only_batch | high | 文件位于审计、裁量、readiness、human review、relative band、rule boundary 或 sweep 复核批次目录。 | export_md, i5b_exporter, tests | n/a | #231 只做归档/保留审查，不把它当作数据主源。 |
| data/search_log_batches/i5b_expanded_pilot_batch1_20260619.jsonl | 12 | data/search_log_batches | search_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | i5b_exporter, tests | 8/12 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/search_log_batches/i5b_liubang_supplemental_safety_20260618.jsonl | 7 | data/search_log_batches | search_id | archive_candidate | medium | 未发现执行引用，但主 ID 尚未全部进入 canonical；保守列为归档候选而非删除候选。 | none_found | 0/7 | #231 人工确认是否仍是唯一数据源；确认前不删除。 |
| data/search_log_batches/i5b_next_four_20260618.jsonl | 24 | data/search_log_batches | search_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | validate_all, tests, data_refs | 24/24 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/search_logs.jsonl | 49 | data | search_id | canonical | high | 顶层主表；build/validate/export/tests 静态扫描用于确认当前对齐情况。 | build_db, validate_all, tests, docs_only | n/a | 长期保留；后续只通过正式数据流程更新。 |
| data/source_batches/i5b_expanded_pilot_batch1_20260619.jsonl | 17 | data/source_batches | source_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | i5b_exporter, tests | 17/17 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/source_batches/i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl | 6 | data/source_batches | source_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | i5b_exporter, tests | 0/6 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/source_batches/i5b_liubang_negative_20260618.jsonl | 3 | data/source_batches | source_id | merged_batch | medium | 主 ID 已全部出现在对应 canonical 主表或 canonical lane，且静态扫描未发现执行引用。 | none_found | 3/3 | #231 复核后可进入 archive_candidate 或 delete_candidate 审查。 |
| data/source_batches/i5b_liubang_positive_20260618.jsonl | 4 | data/source_batches | source_id | merged_batch | medium | 主 ID 已全部出现在对应 canonical 主表或 canonical lane，且静态扫描未发现执行引用。 | none_found | 4/4 | #231 复核后可进入 archive_candidate 或 delete_candidate 审查。 |
| data/source_batches/i5b_liubang_supplemental_safety_20260618.jsonl | 4 | data/source_batches | source_id | merged_batch | medium | 主 ID 已全部出现在对应 canonical 主表或 canonical lane，且静态扫描未发现执行引用。 | none_found | 4/4 | #231 复核后可进入 archive_candidate 或 delete_candidate 审查。 |
| data/source_batches/i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl | 2 | data/source_batches | source_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | export_md, i5b_exporter, tests | 0/2 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/sources.jsonl | 36 | data | source_id | canonical | high | 顶层主表；build/validate/export/tests 静态扫描用于确认当前对齐情况。 | build_db, validate_all, tests, docs_only | n/a | 长期保留；后续只通过正式数据流程更新。 |
| data/sweep_batches/i5b_yongzheng_role_class_sweep_20260619.jsonl | 5 | data/sweep_batches | sweep_id | review_only_batch | high | 文件位于审计、裁量、readiness、human review、relative band、rule boundary 或 sweep 复核批次目录。 | i5b_exporter, tests | n/a | #231 只做归档/保留审查，不把它当作数据主源。 |
| data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl | 12 | data/thematic_anchor_batches | anchor_id | active_batch | high | 仍被 validator、exporter 或测试静态引用，当前不能直接归档或删除。 | validate_all, tests, data_refs | 12/12 | #231 先解除或替换下游引用，再决定是否归档或删除。 |
| data/thematic_anchor_events.jsonl | 1 | data | anchor_id | canonical_lane | high | thematic anchor 细粒度稳定 lane；validate_canonical_data_integrity 已纳入 lane 校验。 | validate_all, tests, docs_only | n/a | 长期保留，并在后续与 build_db/validator 口径继续对齐。 |
| data/thematic_anchor_mechanisms.jsonl | 1 | data | anchor_id | canonical_lane | high | thematic anchor 细粒度稳定 lane；validate_canonical_data_integrity 已纳入 lane 校验。 | validate_all, tests, docs_only | n/a | 长期保留，并在后续与 build_db/validator 口径继续对齐。 |
| data/thematic_anchor_objects.jsonl | 10 | data | anchor_id | canonical_lane | high | thematic anchor 细粒度稳定 lane；validate_canonical_data_integrity 已纳入 lane 校验。 | validate_all, tests, docs_only | n/a | 长期保留，并在后续与 build_db/validator 口径继续对齐。 |
| data/thematic_anchors.jsonl | 3 | data | anchor_id | canonical | high | 顶层主表；build/validate/export/tests 静态扫描用于确认当前对齐情况。 | build_db, validate_all, tests, docs_only | n/a | 长期保留；后续只通过正式数据流程更新。 |
| data/trigger_terms.jsonl | 96 | data | term_id | canonical | high | 顶层主表；build/validate/export/tests 静态扫描用于确认当前对齐情况。 | build_db, validate_all, i5b_exporter, tests, docs_only | n/a | 长期保留；后续只通过正式数据流程更新。 |

## 5. canonical 与 build/validate 对齐情况

- `build_db.py` 静态读取：`data/events.jsonl`, `data/evidence_cards.jsonl`, `data/evidence_clusters.jsonl`, `data/query_profiles.jsonl`, `data/search_logs.jsonl`, `data/sources.jsonl`, `data/thematic_anchors.jsonl`, `data/trigger_terms.jsonl`。
- validators / `validate_all.py` 链条静态覆盖：`data/events.jsonl`, `data/evidence_cards.jsonl`, `data/evidence_clusters.jsonl`, `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl`, `data/query_profiles.jsonl`, `data/search_log_batches/i5b_next_four_20260618.jsonl`, `data/search_logs.jsonl`, `data/sources.jsonl`, `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`, `data/thematic_anchor_events.jsonl`, `data/thematic_anchor_mechanisms.jsonl`, `data/thematic_anchor_objects.jsonl`, `data/thematic_anchors.jsonl`, `data/trigger_terms.jsonl`。
- exporters / i5b exporter 静态覆盖：`data/adjudication_batches/i5b_expanded_pilot_batch1_cluster_adjudication_20260619.jsonl`, `data/adjudication_batches/i5b_expanded_pilot_batch1_post_supplement_adjudication_20260619.jsonl`, `data/audit_batches/i5b_expanded_pilot_batch1_readiness_audit_20260619.jsonl`, `data/audit_batches/i5b_expanded_pilot_batch1_readiness_followup_20260619.jsonl`, `data/evidence_card_batches/i5b_expanded_pilot_batch1_20260619.jsonl`, `data/evidence_card_batches/i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl`, `data/evidence_card_batches/i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl`, `data/evidence_cards.jsonl`, `data/evidence_cluster_batches/i5b_expanded_pilot_batch1_20260619.jsonl`, `data/evidence_clusters.jsonl`, `data/query_profile_batches/i5b_expanded_pilot_batch1_20260619.jsonl`, `data/relative_band_batches/i5b_expanded_pilot_batch1_relative_band_preparation_20260619.jsonl`, `data/review_packages/i5b_expanded_pilot_batch1_human_review_package_20260619.jsonl`, `data/rule_boundary_batches/i5b_yongzheng_rule_boundary_review_20260619.jsonl`, `data/search_log_batches/i5b_expanded_pilot_batch1_20260619.jsonl`, `data/source_batches/i5b_expanded_pilot_batch1_20260619.jsonl`, `data/source_batches/i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl`, `data/source_batches/i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl`, `data/sweep_batches/i5b_yongzheng_role_class_sweep_20260619.jsonl`, `data/trigger_terms.jsonl`。
- canonical lane 观察：`data/thematic_anchor_objects.jsonl`、`data/thematic_anchor_events.jsonl`、`data/thematic_anchor_mechanisms.jsonl` 已进入 `validate_canonical_data_integrity.py` 的 lane 校验，但未进入 `build_db.py`；这是当前 JSONL 过渡期的主要 build/validate 不一致。
- 顶层 canonical 观察：`data/evidence_cards.jsonl`、`data/sources.jsonl`、`data/events.jsonl`、`data/trigger_terms.jsonl`、`data/search_logs.jsonl`、`data/evidence_clusters.jsonl`、`data/thematic_anchors.jsonl`、`data/query_profiles.jsonl` 属于长期主表；其中 `data/events.jsonl` 当前为 0 行，但仍被 build_db / validate_evidence 口径承认。
- 未发现执行引用的文件：`data/evidence_card_batches/i5b_liubang_negative_20260618.jsonl`, `data/evidence_card_batches/i5b_liubang_positive_20260618.jsonl`, `data/evidence_card_batches/i5b_liubang_supplemental_safety_20260618.jsonl`, `data/evidence_cluster_batches/i5b_liubang_clusters_20260618.jsonl`, `data/query_profile_batches/i5b_next_four_profiles_20260618.jsonl`, `data/search_log_batches/i5b_liubang_supplemental_safety_20260618.jsonl`, `data/source_batches/i5b_liubang_negative_20260618.jsonl`, `data/source_batches/i5b_liubang_positive_20260618.jsonl`, `data/source_batches/i5b_liubang_supplemental_safety_20260618.jsonl`。其中顶层 canonical / canonical_lane 不因静态引用少而降级；batch 文件则进入 merged 或 archive 审查。

## 6. batch 与 review-only 观察

- `data/adjudication_batches`：2 个文件，标签 review_only_batch=2；吸收检查 n/a；下游引用 i5b_exporter, tests。
- `data/audit_batches`：2 个文件，标签 review_only_batch=2；吸收检查 n/a；下游引用 i5b_exporter, tests。
- `data/evidence_card_batches`：6 个文件，标签 active_batch=3, merged_batch=3；吸收检查 0/11, 0/5, 18/18, 3/3, 4/4；下游引用 export_md, i5b_exporter, tests；i5b_exporter, tests；none_found。
- `data/evidence_cluster_batches`：2 个文件，标签 active_batch=1, merged_batch=1；吸收检查 2/2, 6/6；下游引用 i5b_exporter, tests；none_found。
- `data/query_profile_batches`：3 个文件，标签 active_batch=2, archive_candidate=1；吸收检查 0/3, 0/4, 3/3；下游引用 i5b_exporter, tests；none_found；validate_all, tests, data_refs。
- `data/relative_band_batches`：1 个文件，标签 review_only_batch=1；吸收检查 n/a；下游引用 i5b_exporter, tests。
- `data/review_packages`：1 个文件，标签 review_only_batch=1；吸收检查 n/a；下游引用 i5b_exporter, tests。
- `data/rule_boundary_batches`：1 个文件，标签 review_only_batch=1；吸收检查 n/a；下游引用 export_md, i5b_exporter, tests。
- `data/search_log_batches`：3 个文件，标签 active_batch=2, archive_candidate=1；吸收检查 0/7, 24/24, 8/12；下游引用 i5b_exporter, tests；none_found；validate_all, tests, data_refs。
- `data/source_batches`：6 个文件，标签 active_batch=3, merged_batch=3；吸收检查 0/2, 0/6, 17/17, 3/3, 4/4；下游引用 export_md, i5b_exporter, tests；i5b_exporter, tests；none_found。
- `data/sweep_batches`：1 个文件，标签 review_only_batch=1；吸收检查 n/a；下游引用 i5b_exporter, tests。
- `data/thematic_anchor_batches`：1 个文件，标签 active_batch=1；吸收检查 12/12；下游引用 validate_all, tests, data_refs。

## 7. #231 建议动作清单

1. 先处理 `active_batch`：逐一确认 exporter、validator、tests 是否仍需要直接读 batch；只有解除下游引用后才进入归档或删除审查。
2. 对 `merged_batch` 做人工复核：重点确认 Liu Bang source/evidence/cluster batch 是否已完全由 canonical 承担，并决定归档还是删除。
3. 对 `archive_candidate` 做唯一性确认：`i5b_next_four_profiles_20260618` 与 `i5b_liubang_supplemental_safety_20260618` 当前未完全吸收，不应直接删除。
4. 对 `review_only_batch` 明确保留位置：若仍需审计价值，可移动到 archive 或改由导出报告承载；不要继续伪装成 active data 主源。
5. 对 canonical lane 与 build_db 的差异单独开口径任务：决定是否让 thematic object/event/mechanism lane 进入数据库生成，或继续作为 validate-only lane。

## 8. 本 PR 非目标

- 未删除任何 JSONL。
- 未迁移任何 JSONL。
- 未归档任何 JSONL。
- 未合并任何 batch 到 canonical。
- 未新增数据库 schema、worker、parser、抓取器或迁移脚本。
- 未修改 `data/`、`db/`、`scripts/`、`exports/markdown_views/`、评分标准或分项规则。
