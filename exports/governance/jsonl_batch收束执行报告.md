# JSONL batch 收束执行报告

- 执行日期：2026-06-24
- 任务范围：PR #231 第一轮安全执行。
- 基准报告：`exports/governance/jsonl数据文件盘点报告.md`
- 开工扫描：`git status --short` 干净；`git ls-files "*.jsonl"` 为 40 个；batch/review JSONL 为 29 个。
- 执行原则：只处理 #230 标为 `merged_batch` 且本轮复核满足删除条件的 Liu Bang batch；不迁移 active/review batch，不创建 `data/batches/`，不修改 canonical JSONL。

## 1. 执行动作总览

| action | files | non_empty_lines | 说明 |
| --- | --- | --- | --- |
| deleted | 7 | 23 | 7 个 Liu Bang merged batch 已完全吸收，且无 scripts/tests 执行引用。 |
| moved_to_archive | 0 | 0 | 本轮未创建 `archive/data/`。 |
| moved_to_data_batches | 0 | 0 | 本轮未创建 `data/batches/`。 |
| kept | 0 | 0 | 本轮没有对 merged batch 选择保留原位。 |
| deferred | 23 | 119 | active_batch、review_only_batch、archive_candidate 暂不处理，留给后续 PR。 |

提交后 tracked JSONL 预计从 40 个降为 33 个；当前工作树中仍存在的 tracked JSONL 非空行数为 409。

## 2. 已处理文件

| old_path | new_path 或 deleted | 原 status_label | 行数 | 主 ID 覆盖情况 | 下游引用处理情况 | 是否有唯一内容 | 处理理由 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `data/source_batches/i5b_liubang_negative_20260618.jsonl` | deleted | merged_batch | 3 | `source_id` 3/3 已在 `data/sources.jsonl` | `git grep` 未发现 scripts/tests 执行引用；仅旧审计/治理报告引用。 | 否；同 ID 行与 canonical 完全一致。 | 已完全吸收，删除不会丢失事实字段。 |
| `data/source_batches/i5b_liubang_positive_20260618.jsonl` | deleted | merged_batch | 4 | `source_id` 4/4 已在 `data/sources.jsonl` | `git grep` 未发现 scripts/tests 执行引用；仅旧审计/治理报告引用。 | 否；同 ID 行与 canonical 完全一致。 | 已完全吸收，删除不会丢失事实字段。 |
| `data/source_batches/i5b_liubang_supplemental_safety_20260618.jsonl` | deleted | merged_batch | 4 | `source_id` 4/4 已在 `data/sources.jsonl` | `git grep` 未发现 scripts/tests 执行引用；仅旧审计/治理报告引用。 | 否；同 ID 行与 canonical 完全一致。 | 已完全吸收，删除不会丢失事实字段。 |
| `data/evidence_card_batches/i5b_liubang_negative_20260618.jsonl` | deleted | merged_batch | 3 | `evidence_id` 3/3 已在 `data/evidence_cards.jsonl` | `git grep` 未发现 scripts/tests 执行引用；仅旧审计/治理报告引用。 | 否；无 batch-only 字段。`case_classification` / `risk_status` 为旧枚举值，canonical 已改为当前受控枚举。 | 已完全吸收；保留旧枚举 batch 会制造双轨口径。 |
| `data/evidence_card_batches/i5b_liubang_positive_20260618.jsonl` | deleted | merged_batch | 4 | `evidence_id` 4/4 已在 `data/evidence_cards.jsonl` | `git grep` 未发现 scripts/tests 执行引用；仅旧审计/治理报告引用。 | 否；同 ID 行与 canonical 完全一致。 | 已完全吸收，删除不会丢失事实字段。 |
| `data/evidence_card_batches/i5b_liubang_supplemental_safety_20260618.jsonl` | deleted | merged_batch | 3 | `evidence_id` 3/3 已在 `data/evidence_cards.jsonl` | `git grep` 未发现 scripts/tests 执行引用；仅旧审计/治理报告引用。 | 否；无 batch-only 字段。2 条 `case_classification` / `risk_status` 为旧枚举值，canonical 已改为当前受控枚举。 | 已完全吸收；保留旧枚举 batch 会制造双轨口径。 |
| `data/evidence_cluster_batches/i5b_liubang_clusters_20260618.jsonl` | deleted | merged_batch | 2 | `cluster_id` 2/2 已在 `data/evidence_clusters.jsonl` | `git grep` 未发现 scripts/tests 执行引用；仅旧审计/治理报告引用。 | 否；同 ID 行与 canonical 完全一致。 | 已完全吸收，删除不会丢失事实字段。 |

## 3. 未处理文件清单

### active_batch：延后到 #232 或专门迁移 PR

这些文件仍被 exporter、validator、tests 或 data refs 使用。本 PR 不直接删除，也不强行迁移到 `data/batches/`。

- `data/evidence_card_batches/i5b_expanded_pilot_batch1_20260619.jsonl`
- `data/evidence_card_batches/i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl`
- `data/evidence_card_batches/i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl`
- `data/evidence_cluster_batches/i5b_expanded_pilot_batch1_20260619.jsonl`
- `data/query_profile_batches/i5b_expanded_pilot_batch1_20260619.jsonl`
- `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl`
- `data/search_log_batches/i5b_expanded_pilot_batch1_20260619.jsonl`
- `data/search_log_batches/i5b_next_four_20260618.jsonl`
- `data/source_batches/i5b_expanded_pilot_batch1_20260619.jsonl`
- `data/source_batches/i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl`
- `data/source_batches/i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl`
- `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`

推荐后续 PR：先解除脚本和测试对旧 batch 路径的直接引用，再决定是否迁入 `data/batches/<batch_id>/` 或归档。

### review_only_batch：延后到审计材料归档 PR

这些文件承载 readiness、adjudication、human review、relative band、rule boundary 或 sweep 复核材料；本 PR 不合并进 canonical。

- `data/adjudication_batches/i5b_expanded_pilot_batch1_cluster_adjudication_20260619.jsonl`
- `data/adjudication_batches/i5b_expanded_pilot_batch1_post_supplement_adjudication_20260619.jsonl`
- `data/audit_batches/i5b_expanded_pilot_batch1_readiness_audit_20260619.jsonl`
- `data/audit_batches/i5b_expanded_pilot_batch1_readiness_followup_20260619.jsonl`
- `data/relative_band_batches/i5b_expanded_pilot_batch1_relative_band_preparation_20260619.jsonl`
- `data/review_packages/i5b_expanded_pilot_batch1_human_review_package_20260619.jsonl`
- `data/rule_boundary_batches/i5b_yongzheng_rule_boundary_review_20260619.jsonl`
- `data/sweep_batches/i5b_yongzheng_role_class_sweep_20260619.jsonl`

推荐后续 PR：若仍被 exporter/tests 需要，先迁移引用；若仅保留审计价值，再移动到 `archive/data/jsonl_batches/review_only/`。

### archive_candidate：延后到唯一性确认 PR

- `data/query_profile_batches/i5b_next_four_profiles_20260618.jsonl`
- `data/search_log_batches/i5b_liubang_supplemental_safety_20260618.jsonl`

这两个文件包含 canonical 未吸收内容。本 PR 不删除；后续应确认是否归档到 `archive/data/jsonl_batches/unresolved/`，或继续作为当前数据输入保留。

## 4. 本 PR 非目标

- 未修改 canonical JSONL 内容。
- 未合并 batch 数据到 canonical。
- 未改证据卡、证据簇、人物评分或排名。
- 未新增数据库 schema。
- 未新增 worker / parser / crawler。
- 未修改分项规则或评分标准。
- 未处理 canonical_lane 是否进入 build_db 的问题。
