# Thematic Anchor Schema Decision 20260620

## 结论

本次选择 **Outcome B**：当前不把 `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 吸收到 `data/thematic_anchors.jsonl`。

原因不是 JSONL 解析问题，而是 **schema 粒度不安全**：

- batch 记录是对象级、机制级、事件级混合输入；
- canonical 主表目前是人物/theme 级总锚点；
- 其中 1 条事件型锚点 `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 没有清晰且无歧义的 canonical 落点；
- 如果强行塞入现有 canonical 行，只能把关键语义压扁到 `anchor_summary` / `note`，会丢失 `object_type`、`anchor_role`、`cross_item_risks`、`status` 这些必要信息，也会逼迫事件锚点错误地附着到人物级总锚点上。

## 现有 schema 的不匹配点

### batch 侧字段

`data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 的记录带有这些语义：

- `object_type`
- `object_name`
- `anchor_role`
- `anchor_scope`
- `consensus_level`
- `cross_item_risks`
- `usable_for`
- `status`

这说明 batch 不只是“人物主题摘要”，而是把对象、机制、事件和风险边界一起显式编码了。

### canonical 侧字段

`data/thematic_anchors.jsonl` 目前只有这些字段：

- `anchor_id`
- `theme`
- `item`
- `subitem`
- `persons`
- `linked_evidence_ids`
- `linked_cluster_ids`
- `anchor_summary`
- `comparative_value`
- `note`

它能表达人物/theme 级的聚合结论，但 **没有原生位置** 保存对象类型、事件类型、机制角色、跨项风险与审核状态。

## 为什么现在不安全

1. **粒度不一致**
   - canonical 的 3 条记录是人物级总锚点。
   - batch 的 11 条人物/对象锚点可以概念性归并，但归并后仍然不是同一层级。
   - 事件锚点是机制/事件层，不是单纯人物对象。

2. **语义不能无损落地**
   - 事件锚点的核心不是“刘庄本人某个对象列表”，而是“楚王英案后续牵连”这一事件性负证。
   - 这类语义如果只写进 `anchor_summary`，会失去可检索、可审计、可复核的结构化边界。

3. **不能把相邻项风险当作当前项结论**
   - 该事件锚点明确带有 `cross_item_risks`，而且需要人工裁判剩余权重。
   - 现有 canonical 主表没有专门字段表示“待裁判事件残余权重”或“机制级负证待定状态”。

## 建议的目标 schema

如果后续要让这类 batch 安全吸收，建议把 canonical 锚点拆成显式的多粒度 schema，而不是继续把所有内容压进人物主题摘要。

建议新增或标准化这些字段：

- `anchor_kind`: `person` / `object` / `event` / `mechanism`
- `anchor_scope`
- `object_type`
- `object_name`
- `anchor_role`
- `consensus_level`
- `cross_item_risks`
- `usable_for`
- `review_status`
- `linked_persons`

如果短期内不改 canonical 结构，也至少需要一个独立的事件锚点承载层，而不是复用人物级总锚点行。

## 对 `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 的处理建议

不建议静默丢弃，也不建议直接并入现有人物级 canonical 行。

建议先把它保留为：

- 独立的事件/机制锚点候选；
- 仍标记为需要人工裁判剩余权重；
- 通过后续 schema 扩展决定它是否进入 canonical，或是否单独落在事件锚点表。

如果必须给出当前处理意见，只能是：

- **不吸收进 `data/thematic_anchors.jsonl`**
- **保留 batch 语义，不做 canonical 结论化**

## 下一步 PR 形态

建议拆成两个后续 PR：

1. **schema 迁移 PR**
   - 为 thematic anchor 引入 `anchor_kind` / `anchor_scope` / `review_status` 等结构化字段；
   - 明确人物锚点、对象锚点、事件锚点的承载方式。

2. **定向吸收 PR**
   - 在 schema 就位后，再把这批 batch 的 11 条人物/对象锚点和 1 条事件锚点分别落地；
   - 事件锚点单独处理，不与人物级总锚点混写。

## 本次核查摘要

- 已读取并解析 `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`
- 已读取并解析 `data/thematic_anchors.jsonl`
- 两边都没有 `anchor_id` 重复
- 未移动或删除任何 batch 文件
- 未触碰 `data/query_profiles.jsonl`
- 未触碰 `data/search_logs.jsonl`
- 未触碰任何导出文件

