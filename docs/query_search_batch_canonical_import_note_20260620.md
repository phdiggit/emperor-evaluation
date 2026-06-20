# Query Search Batch Canonical Import Note 20260620

本说明对应以下两份 source batch 的 canonical import：

- `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl`
- `data/search_log_batches/i5b_next_four_20260618.jsonl`

目标 canonical 文件：

- `data/query_profiles.jsonl`
- `data/search_logs.jsonl`

## Merge rule

本次采用的规则不是追加重复行，而是：

- `query_profile_batches`：按 `query_profile_id` 做 exact-id 原位 merge；
- `search_log_batches`：按 `search_id` 做 exact-id 原位 merge。

判定理由：

- canonical 中已存在同 ID、同语义记录；
- 现有 canonical 行已经承接主字段，但部分迁移审计语义被压扁进 `note` 或未结构化保留；
- 继续追加新行会制造重复主键与双轨语义。

## Query profile field mapping

保留/补回的稳定与迁移字段：

- `query_profile_id`
- `item`
- `subitem`
- `person`
- `schema_version`
- `profile_scope`
- `profile_role`
- `inherits_from`
- `status`
- `positive_dimensions`
- `negative_dimensions`
- `reversal_or_balance_dimensions`
- `object_anchors`
- `cross_item_risks`
- `priority_search_ids`
- `coverage_policy`
- `evidence_policy`
- `retention_policy`
- `source_batch`
- `note`

保留不动的 canonical 通用字段：

- `search_modes`
- `positive_terms`
- `negative_terms`
- `reversal_terms`
- `source_scopes`
- `reverse_search_required_when`
- `thematic_anchor_targets`
- `cross_item_split_notes`

## Search log field mapping

保留/补回的字段：

- `search_id`
- `query_profile_id`
- `person`
- `item`
- `subitem`
- `polarity`
- `trigger_family`
- `query_terms`
- `derived_from_dimension`
- `expected_source_scope`
- `cross_item_watch`
- `next_action`
- `linked_source_ids`
- `linked_evidence_ids`
- `rejection_reason`
- `source_status`
- `source_polarity`
- `source_batch`
- `note`

保留不动的 canonical 检索字段：

- `query`
- `source_scope`
- `searched_at`
- `result_status`
- `result_summary`
- `linked_evidence_id`

其中状态映射规则为：

- batch `status=needs_human_review` 映射为 canonical `result_status=evidence_found_card_created`
- batch `status=lead_needs_source_review` 映射为 canonical `result_status=lead_needs_source_review`
- batch `polarity=neutral` 因 canonical 仅接受 `positive/negative`，落表时映射为 `negative`
- 原始 batch `status/polarity` 另保存在 `source_status/source_polarity`

## Import summary

- query profile source rows: `3`
- query profile imported via exact-id merge: `3`
- query profile skipped: `0`
- search log source rows: `24`
- search log imported via exact-id merge: `24`
- search log skipped: `0`

## Scope guardrails

- source batch 文件未移动、未删除、未修改
- thematic anchor 文件未修改
- 未修改评分、档位、排名或裁判结论
