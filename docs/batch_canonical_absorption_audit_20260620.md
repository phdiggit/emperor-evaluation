# Batch Canonical Absorption Audit

本报告对应当前批次收束审计任务。它只做 `data/*_batches/` 到 canonical 主表的吸收核查，不移动、不删除任何文件。

## 1. 总体结论

这三份 batch 文件都还不适合直接归档。

1. `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl` 与 `data/query_profiles.jsonl` 存在明显 schema drift，canonical 目前只有一条通用模板记录，尚未看到 3 条迁移审计画像被真正吸收。
2. `data/search_log_batches/i5b_next_four_20260618.jsonl` 与 `data/search_logs.jsonl` 目标表同属检索线索层，但 canonical 目前覆盖的是三人试点人物，而 batch 覆盖的是另外四名人物，0 条精确吸收。
3. `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 与 `data/thematic_anchors.jsonl` 存在概念级部分吸收：11 条人物/对象锚点可在 canonical 的 3 条人物级总锚点中找到归并位置，但 1 条事件型锚点没有清晰 canonical 落点，仍需更深层 schema 判断。

结论上：

- `query_profile_batches` 和 `search_log_batches` 目前应视为 `needs canonical import first`。
- `thematic_anchor_batches` 目前应视为 `needs deeper schema investigation`。
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
| `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` | `data/thematic_anchors.jsonl` | 12 | 3 | batch: `anchor_id`, `item`, `subitem`, `object_name`, `object_type`, `object_level`, `anchor_role`; canonical: `anchor_id`, `theme`, `persons`, `linked_evidence_ids`, `linked_cluster_ids`, `comparative_value`, `anchor_summary` | 11/12 partially absorbed; 1/12 not absorbed | batch 是对象级/事件级显式锚点，canonical 是人物级总锚点聚合。字段从 `usable_for/cross_item_risks/consensus_level/status` 转为 `linked_evidence_ids/linked_cluster_ids/comparative_value/anchor_summary`，属于明显的粒度收敛。 | 没有发现 `anchor_id` 重叠；11 条人物/对象锚点可被人物级 canonical 总锚点概念性吸收，但 `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 没有清晰 canonical 落点。 | high | needs deeper schema investigation |

## 4. 文件级备注

### `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl`

这份 batch 明确写了 `inherits_from: QRY-I5B-001`，说明它是从 canonical 的通用画像模板向人物级迁移的中间层。问题在于 canonical `data/query_profiles.jsonl` 目前只有一条模板型记录，没有 3 条迁移审计画像的落地结果。

### `data/search_log_batches/i5b_next_four_20260618.jsonl`

这份 batch 的人物是 `刘彻`、`刘邦`、`杨坚`、`朱元璋`，而 canonical `data/search_logs.jsonl` 目前覆盖的是 `李世民`、`刘秀`、`刘庄`。两者同为检索线索层，但不是同一批对象，不能按 exact key 认为已吸收。

### `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`

这份 batch 的对象锚点更细，属于对象层、事件层、边界层混合输入。canonical `data/thematic_anchors.jsonl` 已收敛成三条人物级总锚点，所以这份 batch 不是纯未吸收，也不是可直接归档，而是需要先决定是否继续保留这种粒度，还是把对象级锚点进一步合并为 canonical 的人物级总锚点。

## 5. 下一步可执行方案

建议下一步拆成两个最小 Issue / PR：

1. **先做 canonical 吸收落地 PR**
   - 只处理 `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl` 和 `data/search_log_batches/i5b_next_four_20260618.jsonl` 的 canonical import 方案。
   - 目标是先把 batch 里的人物级画像和检索线索明确落到 canonical 主表，补齐字段映射和 identity 键。
   - 在这一步完成前，不考虑归档 batch。

2. **再做 thematic anchor schema 决策 PR**
   - 只处理 `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 与 `data/thematic_anchors.jsonl` 的粒度收敛问题。
   - 先决定对象级锚点是否要继续保留为 batch 层，还是把事件型与对象型锚点拆分后再吸收到人物级 canonical。
   - 明确 `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 这类事件锚点的去向后，再讨论归档。

在上述两个方向都没有完成之前，三个 batch 文件都应继续保留在 transitional batch layer，不能移动、不能删除、也不应按“已吸收”处理。
