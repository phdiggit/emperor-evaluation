# JSONL batch 收束执行报告

- 执行日期：2026-06-24
- 任务范围：PR #232 active/review batch 引用收束与目录规范化。
- 基准报告：`exports/governance/jsonl数据文件盘点报告.md`
- 开工扫描：`git status --short` 干净；`git ls-files "*.jsonl"` 为 33 个；旧 batch/review JSONL 为 22 个；`data/batches/**` 与 `archive/data/jsonl_batches/**` 无 tracked 文件。
- 执行原则：不修改 canonical JSONL，不合并 batch 数据到 canonical，不改评分、证据卡、证据簇、人物结论、分项规则或排名。

## 1. 本轮动作总览

| action | files | non_empty_lines | 说明 |
| --- | ---: | ---: | --- |
| deleted | 4 | 44 | fully absorbed 且无 batch-only 字段的 active batch 已删除。 |
| moved_to_data_batches | 16 | 95 | 当前试点输入与仍被 exporter/tests 使用的 review-only 材料迁入 `data/batches/<batch_id>/`。 |
| moved_to_archive | 2 | 19 | 不再作为当前默认输入的 unresolved / absorbed 历史材料迁入 `archive/data/jsonl_batches/`。 |
| kept | 0 | 0 | 本轮没有旧 `_batches` 文件继续保留原位。 |
| deferred | 0 | 0 | #231 遗留的 22 个 active/review/archive_candidate 文件本轮均已处理。 |

提交后 tracked JSONL 预计从 33 个降为 29 个；减少来自 4 个 fully absorbed active batch 删除。`data/batches/` 新增 3 个 manifest。

## 2. 已处理文件

| old_path | new_path/deleted | 原标签 | 行数 | 主 ID 覆盖 | 引用处理 | 是否唯一内容 | 处理理由 |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| `data/source_batches/i5b_expanded_pilot_batch1_20260619.jsonl` | deleted | active_batch | 17 | 17/17 已在 `data/sources.jsonl` | exporter/tests 改读 canonical 或 ID 过滤。 | 否；同 ID 行与 canonical 完全一致。 | fully absorbed，删除不丢字段。 |
| `data/evidence_card_batches/i5b_expanded_pilot_batch1_20260619.jsonl` | deleted | active_batch | 18 | 18/18 已在 `data/evidence_cards.jsonl` | exporter fallback 和 tests 改读 canonical。 | 否；同 ID 行与 canonical 完全一致。 | fully absorbed，删除不丢字段。 |
| `data/evidence_cluster_batches/i5b_expanded_pilot_batch1_20260619.jsonl` | deleted | active_batch | 6 | 6/6 已在 `data/evidence_clusters.jsonl` | exporter fallback 和 tests 改读 canonical。 | 否；同 ID 行与 canonical 完全一致。 | fully absorbed，删除不丢字段。 |
| `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl` | deleted | active_batch | 3 | 3/3 已在 `data/query_profiles.jsonl` | validator 改为校验 canonical `source_batch` 历史字段。 | 否；同 ID 行与 canonical 完全一致。 | fully absorbed，旧文件不再作为执行输入。 |
| `data/query_profile_batches/i5b_expanded_pilot_batch1_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/query_profiles.jsonl` | active_batch | 3 | 0/3 | exporter/tests 同步到新路径。 | 是；仍为当前 intake profile。 | non-absorbed 当前输入，迁入 batch 聚合目录。 |
| `data/search_log_batches/i5b_expanded_pilot_batch1_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/search_logs.jsonl` | active_batch | 12 | 8/12 | tests 同步到新路径。 | 是；仍含未吸收 lead。 | partial absorbed，保留为当前输入。 |
| `data/source_batches/i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/sources_targeted_supplement.jsonl` | active_batch | 6 | 0/6 | exporter/tests 同步到新路径。 | 是。 | targeted supplement 未并入 canonical。 |
| `data/evidence_card_batches/i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/evidence_cards_targeted_supplement.jsonl` | active_batch | 11 | 0/11 | exporter/tests 同步到新路径。 | 是。 | targeted supplement 未并入 canonical。 |
| `data/adjudication_batches/i5b_expanded_pilot_batch1_cluster_adjudication_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/review/adjudication_cluster.jsonl` | review_only_batch | 3 | n/a | exporter/tests 同步到新路径。 | 是；review-only。 | 当前导出仍使用，迁入 batch review 区。 |
| `data/adjudication_batches/i5b_expanded_pilot_batch1_post_supplement_adjudication_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/review/adjudication_post_supplement.jsonl` | review_only_batch | 3 | n/a | exporter/tests 同步到新路径。 | 是；review-only。 | 当前导出仍使用，迁入 batch review 区。 |
| `data/audit_batches/i5b_expanded_pilot_batch1_readiness_audit_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/review/readiness_audit.jsonl` | review_only_batch | 4 | n/a | exporter/tests 同步到新路径。 | 是；review-only。 | 当前导出仍使用，迁入 batch review 区。 |
| `data/audit_batches/i5b_expanded_pilot_batch1_readiness_followup_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/review/readiness_followup.jsonl` | review_only_batch | 4 | n/a | exporter/tests 同步到新路径。 | 是；review-only。 | 当前导出仍使用，迁入 batch review 区。 |
| `data/relative_band_batches/i5b_expanded_pilot_batch1_relative_band_preparation_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/review/relative_band_preparation.jsonl` | review_only_batch | 4 | n/a | exporter/tests 同步到新路径。 | 是；review-only。 | 当前导出仍使用，迁入 batch review 区。 |
| `data/review_packages/i5b_expanded_pilot_batch1_human_review_package_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/review/human_review_package.jsonl` | review_only_batch | 4 | n/a | exporter/tests 同步到新路径。 | 是；review-only。 | 当前导出仍使用，迁入 batch review 区。 |
| `data/rule_boundary_batches/i5b_yongzheng_rule_boundary_review_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/review/yongzheng_rule_boundary_review.jsonl` | review_only_batch | 1 | n/a | exporter/tests 同步到新路径。 | 是；review-only。 | 雍正边界材料仍被 current exporter/tests 使用，先收束到 review 区，后续可单独归档。 |
| `data/sweep_batches/i5b_yongzheng_role_class_sweep_20260619.jsonl` | `data/batches/i5b_expanded_pilot_batch1/review/yongzheng_role_class_sweep.jsonl` | review_only_batch | 5 | n/a | exporter/tests 同步到新路径。 | 是；review-only。 | 雍正 sweep 仍被 current exporter/tests 使用，先收束到 review 区，后续可单独归档。 |
| `data/source_batches/i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl` | `data/batches/i5b_zhu_yuanzhang_micro_supplement/sources.jsonl` | active_batch | 2 | 0/2 | exporter/tests 同步到新路径。 | 是。 | non-absorbed micro supplement，迁入独立 batch。 |
| `data/evidence_card_batches/i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl` | `data/batches/i5b_zhu_yuanzhang_micro_supplement/evidence_cards.jsonl` | active_batch | 5 | 0/5 | exporter/tests 同步到新路径。 | 是。 | non-absorbed micro supplement，迁入独立 batch。 |
| `data/query_profile_batches/i5b_next_four_profiles_20260618.jsonl` | `data/batches/i5b_next_four/query_profiles.jsonl` | archive_candidate | 4 | 0/4 | manifest 登记为当前输入。 | 是。 | 与 next_four search logs 配套，迁入当前 batch。 |
| `data/search_log_batches/i5b_next_four_20260618.jsonl` | `data/batches/i5b_next_four/search_logs.jsonl` | active_batch | 24 | 24/24 主 ID 已在 canonical | validator 改为校验 canonical `source_batch`；batch-only metadata 留在 manifest batch。 | 是；保留 `status` 与 batch 版 `query_terms` 表达。 | 主 ID absorbed 但有 batch-only 审计信息，迁入 current batch 而非删除。 |
| `data/search_log_batches/i5b_liubang_supplemental_safety_20260618.jsonl` | `archive/data/jsonl_batches/unresolved/data/search_log_batches/i5b_liubang_supplemental_safety_20260618.jsonl` | archive_candidate | 7 | 0/7 | 无默认执行引用。 | 是；未吸收线索。 | 不作为当前输入，归档为 unresolved，禁止直接删除。 |
| `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` | `archive/data/jsonl_batches/absorbed/data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` | active_batch | 12 | 12/12 已在 canonical lanes | validator 改为校验 canonical lane `source_batch`。 | 有 batch-only `status` 字段。 | 主 ID absorbed，但保留历史批次版本用于追溯。 |

## 3. 旧 `_batches` 目录剩余文件清单

提交后无 tracked JSONL 继续位于以下旧输入目录：

- `data/adjudication_batches/`
- `data/audit_batches/`
- `data/evidence_card_batches/`
- `data/evidence_cluster_batches/`
- `data/query_profile_batches/`
- `data/relative_band_batches/`
- `data/review_packages/`
- `data/rule_boundary_batches/`
- `data/search_log_batches/`
- `data/source_batches/`
- `data/sweep_batches/`
- `data/thematic_anchor_batches/`

说明：canonical JSONL 中仍保留旧 `source_batch` 字符串作为历史来源字段；validator/tests 只校验这些历史字段，不再读取旧 batch 文件作为默认输入。

## 4. 新 `data/batches/` manifest 清单

- `data/batches/i5b_expanded_pilot_batch1/manifest.yml`
- `data/batches/i5b_next_four/manifest.yml`
- `data/batches/i5b_zhu_yuanzhang_micro_supplement/manifest.yml`

当前 `data/batches/**` JSONL 清单：

- `data/batches/i5b_expanded_pilot_batch1/query_profiles.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/search_logs.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/sources_targeted_supplement.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/evidence_cards_targeted_supplement.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/review/adjudication_cluster.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/review/adjudication_post_supplement.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/review/readiness_audit.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/review/readiness_followup.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/review/human_review_package.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/review/relative_band_preparation.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/review/yongzheng_rule_boundary_review.jsonl`
- `data/batches/i5b_expanded_pilot_batch1/review/yongzheng_role_class_sweep.jsonl`
- `data/batches/i5b_next_four/query_profiles.jsonl`
- `data/batches/i5b_next_four/search_logs.jsonl`
- `data/batches/i5b_zhu_yuanzhang_micro_supplement/sources.jsonl`
- `data/batches/i5b_zhu_yuanzhang_micro_supplement/evidence_cards.jsonl`

## 5. archive/data/jsonl_batches 清单

- `archive/data/jsonl_batches/README.md`
- `archive/data/jsonl_batches/absorbed/data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`
- `archive/data/jsonl_batches/unresolved/data/search_log_batches/i5b_liubang_supplemental_safety_20260618.jsonl`

`archive/data/jsonl_batches/` 只保留历史追溯材料，不作为当前事实源；不得被 `build_db`、validator 或 exporter 当作默认输入。

## 6. 引用处理与剩余引用

- scripts/export：旧 `_batches` 默认读取路径已改为 `data/batches/**` 或 canonical 主表读取。
- scripts/validate：不再读取 `data/query_profile_batches/`、`data/search_log_batches/`、`data/thematic_anchor_batches/` 文件；改为校验 canonical / canonical lane 中的历史 `source_batch` 字段。
- tests：当前输入测试改读 `data/batches/**`；已删除 absorbed batch 的测试改读 canonical 主表。
- docs/data：旧路径仍可能作为历史治理报告、生命周期规则示例或 canonical `source_batch` 溯源字段出现；这些不是默认执行输入。

## 7. 本轮未处理项与下一 PR 建议

- 雍正 rule boundary 与 role-class sweep 本轮迁入 `data/batches/i5b_expanded_pilot_batch1/review/`，因为 exporter/tests 仍使用；后续若导出不再需要，可单独迁入 archive review_only。
- canonical lane 与 build_db 是否对齐仍未处理；本 PR 只解除旧 batch 文件执行引用。
- canonical JSONL、评分标准、分项规则、正式分数和排名均未修改。
