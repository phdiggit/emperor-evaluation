# Batch Canonical Absorption Audit

本报告对应当前批次收束审计任务。它只做 `data/*_batches/` 到 canonical 主表的吸收核查，不移动、不删除任何文件。

## 1. 总体结论

这三份 batch 文件都还不适合直接归档。

1. `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl` 与 `data/query_profiles.jsonl` 存在明显 schema drift，canonical 目前只有一条通用模板记录，尚未看到 3 条迁移审计画像被真正吸收。
2. `data/search_log_batches/i5b_next_four_20260618.jsonl` 与 `data/search_logs.jsonl` 目标表同属检索线索层，但 canonical 目前覆盖的是三人试点人物，而 batch 覆盖的是另外四名人物，0 条精确吸收。
3. `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 的 12 条记录后续已在 PR #119 中 canonicalize 到多粒度 lane：`data/thematic_anchor_objects.jsonl`、`data/thematic_anchor_mechanisms.jsonl`、`data/thematic_anchor_events.jsonl`。原始 batch 继续作为历史输入保留，不再属于“待 schema 决策”的未收束状态。

结论上：

- `query_profile_batches` 和 `search_log_batches` 目前应视为 `needs canonical import first`。
- `thematic_anchor_batches` 已完成 canonical lane 吸收，可视为 `canonicalized_keep_source_batch`。
- 按 strict identity field 计算，三份 batch 与 canonical 主表都没有 exact-id overlap；thematic anchor 的“部分吸收”只存在于 person/theme 级聚合判断，不是 1:1 记录吸收。

## 2. 复核方法

本轮采用的方式如下：

1. 读取三个 batch 文件与对应 canonical 主表的 JSONL 内容。
2. 以稳定 identity 字段做严格比对：
   - `query_profile_id`
   - `search_id`
   - `anchor_id`
3. 再补充做 schema 级对照，比较 batch 记录和 canonical 记录的字段结构、粒度和人物覆盖范围。
4. 对 `thematic_anchor_batches` 额外做 person/theme 级语义归并，因为 canonical 主表是人物级总锚点，而 batch 是对象级/事件级锚点。

## 3. 吸收审计表

| batch file | likely canonical target(s) | batch count | canonical count | matching key / identity fields | absorption status | schema drift notes | duplicate / conflicting notes | archive risk later | recommended next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl` | `data/query_profiles.jsonl` | 3 | 1 | batch: `query_profile_id`, `inherits_from`, `person`, `item`, `subitem`; canonical: `query_profile_id`, `item`, `subitem`, `search_modes`, `positive_terms`, `negative_terms`, `reversal_terms`, `source_scopes` | 3/3 not absorbed | batch 是 `migration_audit_profile`，带 `profile_scope/profile_role/positive_dimensions/negative_dimensions/object_anchors/priority_search_ids/status=batch_pending_merge`；canonical 目前只有通用模板行，字段更偏通用检索词，不含 migration audit 语义。 | 没有发现与 canonical 的 exact `query_profile_id` 重叠；也没有 1:1 重复记录。主要冲突是粒度与字段模型不一致。 | high | needs canonical import first |
| `data/search_log_batches/i5b_next_four_20260618.jsonl` | `data/search_logs.jsonl` | 24 | 27 | batch: `search_id`, `query_profile_id`, `person`, `polarity`, `trigger_family`, `query_terms`; canonical: `search_id`, `person`, `polarity`, `trigger_family`, `query_terms`, `query`, `source_scope`, `searched_at`, `result_status`, `linked_evidence_id` | 24/24 not absorbed | batch 里有 `derived_from_dimension/expected_source_scope/linked_source_ids/linked_evidence_ids/next_action/status` 等审阅态字段；canonical 里是已定型的 search log 记录格式。两者同属检索线索层，但覆盖人物不同。 | 没有发现 `search_id` 重叠；batch 覆盖的人物是 `刘彻/刘邦/杨坚/朱元璋`，canonical 覆盖的是 `刘庄/刘秀/李世民`。无 exact duplicate，但有同层不同人群的并行记录。 | high | needs canonical import first |
| `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` | `data/thematic_anchor_objects.jsonl`; `data/thematic_anchor_mechanisms.jsonl`; `data/thematic_anchor_events.jsonl` | 12 | 12 | batch: `anchor_id`, `item`, `subitem`, `object_name`, `object_type`, `object_level`, `anchor_role`; lane rows: `anchor_id`, `anchor_kind`, `anchor_scope`, `object_type`, `object_name`, `object_level`, `anchor_role`, `review_status`, `source_batch` | 12/12 canonicalized into thematic anchor lanes | batch 的 `status` 已映射为 `review_status`，并按 `anchor_kind` 分流到 person / mechanism / event 三类 canonical lane；人物级总锚点 `data/thematic_anchors.jsonl` 保持为 aggregate 层。 | 没有发现 lane 内或 lane 间 `anchor_id` 重复；`ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 已落在事件 lane。 | low | keep source batch as historical input |

## 4. 文件级备注

### `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl`

这份 batch 明确写了 `inherits_from: QRY-I5B-001`，说明它是从 canonical 的通用画像模板向人物级迁移的中间层。问题在于 canonical `data/query_profiles.jsonl` 目前只有一条模板型记录，没有 3 条迁移审计画像的落地结果。

### `data/search_log_batches/i5b_next_four_20260618.jsonl`

这份 batch 的人物是 `刘彻`、`刘邦`、`杨坚`、`朱元璋`，而 canonical `data/search_logs.jsonl` 目前覆盖的是 `李世民`、`刘秀`、`刘庄`。两者同为检索线索层，但不是同一批对象，不能按 exact key 认为已吸收。

### `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`

这份 batch 的对象锚点更细，属于对象层、事件层、边界层混合输入。后续已通过多粒度 lane 方案完成吸收：人物对象进入 `data/thematic_anchor_objects.jsonl`，机制对象进入 `data/thematic_anchor_mechanisms.jsonl`，事件对象进入 `data/thematic_anchor_events.jsonl`。`data/thematic_anchors.jsonl` 继续保留人物/theme 聚合层职责。

## 5. 下一步可执行方案

建议下一步拆成两个最小 Issue / PR：

1. **继续处理 query profile / search log 两类 batch**
   - 只处理 `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl` 和 `data/search_log_batches/i5b_next_four_20260618.jsonl` 的 canonical import 方案。
   - 目标是把 batch 里的人物级画像和检索线索明确落到 canonical 主表，补齐字段映射和 identity 键。

2. **thematic anchor 侧转入 post-import consistency 维护**
   - `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 已有 canonical lane 落点。
   - 后续只需维护 discoverability、解析校验和 source-batch 历史保留，不再作为“未收束 schema 决策”处理。

在 query profile / search log 两个方向没有完成之前，对应 batch 文件仍应继续保留在 transitional batch layer。thematic anchor batch 则应视为“已 canonicalize、保留历史输入”的已收束状态。
