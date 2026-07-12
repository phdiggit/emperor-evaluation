# Batch Canonical Absorption Audit

本报告对应当前批次收束审计任务。它只做 `data/*_batches/` 到 canonical 主表的吸收核查，不移动、不删除任何文件。

## 1. 总体结论

这三份 batch 文件都已完成 canonical 吸收，但 source batch 仍应作为历史输入保留。

1. `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl` 的 3 条迁移审计画像已通过同 `query_profile_id` 原位 merge 方式补回 `data/query_profiles.jsonl`，保留项目级通用模板并补齐人物级迁移字段。
2. `data/search_log_batches/i5b_next_four_20260618.jsonl` 的 24 条检索线索已通过同 `search_id` 原位 merge 方式补回 `data/search_logs.jsonl`，保留 canonical 检索字段并补齐批次审阅语义与 source/evidence 链接字段。
3. `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 的 12 条记录后续已在 PR #119 中 canonicalize 到多粒度 lane：`data/thematic_anchor_objects.jsonl`、`data/thematic_anchor_mechanisms.jsonl`、`data/thematic_anchor_events.jsonl`。原始 batch 继续作为历史输入保留，不再属于“待 schema 决策”的未收束状态。

结论上：

- `query_profile_batches` 和 `search_log_batches` 已完成 canonical merge，可视为 `canonicalized_keep_source_batch`。
- `thematic_anchor_batches` 已完成 canonical lane 吸收，可视为 `canonicalized_keep_source_batch`。
- 当前三份 batch 都已有 canonical 落点；保留 batch 的原因是审计追溯，而不是继续承担活跃主表职责。

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
| `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl` | `data/query_profiles.jsonl` | 3 | 4 | batch: `query_profile_id`, `inherits_from`, `person`, `item`, `subitem`; canonical: `query_profile_id`, `item`, `subitem`, `search_modes`, `positive_terms`, `negative_terms`, `reversal_terms`, `source_scopes`, plus migration-audit extension fields | 3/3 canonical-merged by exact `query_profile_id` | batch 的 `schema_version/profile_scope/profile_role/positive_dimensions/negative_dimensions/object_anchors/priority_search_ids/status` 已补回 canonical 行；项目级通用模板 `QRY-I5B-001` 保持不动。 | 没有发现 `query_profile_id` 缺失或重复；merge 规则是“同 ID 同语义记录原位补字段，不追加重复行”。 | low | keep source batch as historical input |
| `data/search_log_batches/i5b_next_four_20260618.jsonl` | `data/search_logs.jsonl` | 24 | 49 | batch: `search_id`, `query_profile_id`, `person`, `polarity`, `trigger_family`, `query_terms`; canonical: `search_id`, `person`, `polarity`, `trigger_family`, `query_terms`, `query`, `source_scope`, `searched_at`, `result_status`, `linked_evidence_id`, plus review/source linkage extension fields | 24/24 canonical-merged by exact `search_id` | batch 的 `query_profile_id/derived_from_dimension/expected_source_scope/cross_item_watch/next_action/linked_source_ids/linked_evidence_ids/rejection_reason/status/polarity` 已补回 canonical 行；其中 `status` 需映射到 canonical `result_status`，原始 batch 状态与极性另保存在 `source_status/source_polarity`。 | 没有发现 `search_id` 缺失或重复；merge 规则是“同 ID 同语义记录原位补字段，不追加重复行”。 | low | keep source batch as historical input |
| `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` | `data/thematic_anchor_objects.jsonl`; `data/thematic_anchor_mechanisms.jsonl`; `data/thematic_anchor_events.jsonl` | 12 | 12 | batch: `anchor_id`, `item`, `subitem`, `object_name`, `object_type`, `object_level`, `anchor_role`; lane rows: `anchor_id`, `anchor_kind`, `anchor_scope`, `object_type`, `object_name`, `object_level`, `anchor_role`, `review_status`, `source_batch` | 12/12 canonicalized into thematic anchor lanes | batch 的 `status` 已映射为 `review_status`，并按 `anchor_kind` 分流到 person / mechanism / event 三类 canonical lane；人物级总锚点 `data/thematic_anchors.jsonl` 保持为 aggregate 层。 | 没有发现 lane 内或 lane 间 `anchor_id` 重复；`ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 已落在事件 lane。 | low | keep source batch as historical input |

## 4. 文件级备注

### `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl`

这份 batch 明确写了 `inherits_from: QRY-I5B-001`，说明它是从 canonical 的通用画像模板向人物级迁移的中间层。后续已通过同 `query_profile_id` 原位 merge 方式补回 canonical：既保留通用模板型字段，又补入 `person/profile_scope/profile_role/object_anchors/priority_search_ids` 等迁移审计语义。

### `data/search_log_batches/i5b_next_four_20260618.jsonl`

这份 batch 的人物是 `刘彻`、`刘邦`、`杨坚`、`朱元璋`。后续已通过同 `search_id` 原位 merge 方式补回 canonical：保留 `query/source_scope/result_status` 等 canonical 字段，同时补入 `query_profile_id/derived_from_dimension/expected_source_scope/cross_item_watch/next_action/linked_source_ids/linked_evidence_ids` 等批次审阅语义。

### `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`

这份 batch 的对象锚点更细，属于对象层、事件层、边界层混合输入。后续已通过多粒度 lane 方案完成吸收：人物对象进入 `data/thematic_anchor_objects.jsonl`，机制对象进入 `data/thematic_anchor_mechanisms.jsonl`，事件对象进入 `data/thematic_anchor_events.jsonl`。`data/thematic_anchors.jsonl` 继续保留人物/theme 聚合层职责。

## 5. 下一步可执行方案

当前这三类 batch 都已完成 canonical 吸收。后续若还要继续推进，只剩两个轻量方向：

1. **把 query/search merge 规则固化到 validator 或测试**
   - 只在需要重复执行同类 import 时再做。

2. **继续保留 source batch 作为历史输入**
   - 不移动、不删除，直到用户明确要求做历史归档动作。
