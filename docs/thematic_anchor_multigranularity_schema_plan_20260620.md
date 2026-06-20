# Thematic Anchor Multigranularity Schema Plan 20260620

## 目标

本计划只定义 **多粒度 thematic anchor 的最小安全 schema lane**，不把
`data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`
吸收到 `data/thematic_anchors.jsonl`。

当前最重要的约束是：事件型锚点必须保留结构化语义，不能被静默压扁进人物级总锚点。

## 1. 当前 canonical schema summary

`data/thematic_anchors.jsonl` 当前是 3 行，字段集合固定为 10 个：

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

当前文件的三条记录都是人物/theme 级聚合锚点，语义重点是：

- 用 `theme` / `persons` / `anchor_summary` 描述总锚点；
- 用 `linked_evidence_ids` 和 `linked_cluster_ids` 连接证据与簇；
- 用 `comparative_value` 记录对评分/比较的辅助解释；
- 没有原生字段表达 `anchor_kind`、`anchor_scope`、`object_type`、`anchor_role` 或 `review_status`。

这意味着当前 canonical 文件更像“人物主题总索引”，而不是多粒度锚点的通用承载层。

## 2. Batch schema summary

`data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 当前是 12 行，字段集合固定为 13 个：

- `anchor_id`
- `item`
- `subitem`
- `anchor_scope`
- `object_type`
- `object_name`
- `object_level`
- `anchor_role`
- `usable_for`
- `cross_item_risks`
- `consensus_level`
- `status`
- `note`

这份 batch 不是单纯的人物摘要，而是把对象、机制、事件与跨项风险显式编码了。它至少包含以下粒度：

- 人物对象
- 机制对象
- 事件对象

其中 `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 明确是事件/机制交叉型负证候选，不能强行当成人物对象行处理。

## 3. Proposed minimal schema fields

为了支持多粒度锚点，建议先把核心语义字段显式化。下面这些字段是最小安全集合：

| 字段 | 建议类型 | 作用 |
|---|---|---|
| `anchor_kind` | enum: `person` / `object` / `event` / `mechanism` | 标记锚点所在粒度 |
| `anchor_scope` | string | 标记迁移/适用范围，例如 `three_pilot_migration` |
| `object_type` | string | 标记对象类别，例如人物对象、事件对象、机制对象 |
| `object_name` | string | 标记对象名或事件名 |
| `anchor_role` | string | 标记该锚点承担的语义角色 |
| `consensus_level` | string | 标记当前共识强度 |
| `cross_item_risks` | array[string] | 标记可能误回填到其他项的风险 |
| `usable_for` | array[string] | 标记可用于哪些分析/校准用途 |
| `review_status` | string | 标记是否已审阅、待审阅、待人工裁判等 |
| `linked_persons` | array[string] | 当锚点不是纯人物粒度时，保留相关人物归属 |

建议的最小补充约定：

- `anchor_kind` 是总分流字段，优先于 `object_type` 做上层路由；
- `object_type` 负责记录更细的对象类别；
- `review_status` 负责区分“结构化进入候选层”与“已完成人工裁判”；
- `linked_persons` 只做关联，不自动把事件锚点降格为人物锚点。

## 4. Recommended canonical storage shape

推荐方案不是直接扩写 `data/thematic_anchors.jsonl`，而是保留现有文件作为 **人物/theme 聚合层**，
并为未来新增独立 canonical 文件，至少分成：

- `data/thematic_anchor_objects.jsonl`
- `data/thematic_anchor_events.jsonl`

如果后续还要保留机制层，可再视需要增加：

- `data/thematic_anchor_mechanisms.jsonl`

这样做的原因是：

- 当前 canonical 文件的字段结构是 aggregate-first；
- 事件锚点和机制锚点需要独立的审核与风险表达；
- 分文件能避免把不同粒度强行塞进一张扁平表里，降低回填和误归类风险。

换句话说，当前最安全的做法是：

1. `data/thematic_anchors.jsonl` 继续只承载人物/theme 级总锚点；
2. 新的对象/事件/机制锚点进入独立 canonical 层；
3. 未来再做一个统一索引文件或视图去汇总它们。

## 5. Migration strategy

从当前聚合锚点迁移到未来 schema，建议分三步：

1. **先定路由，不先搬运**
   - 先按 `anchor_kind` 把锚点分到 person/object/event/mechanism 四类；
   - 人物级聚合锚点保持在现有 canonical 文件。

2. **再做结构化拆分**
   - 从现有人物/theme 级总锚点中抽出可复用的 `theme`、`persons`、`linked_evidence_ids`、`linked_cluster_ids`；
   - 把对象级、事件级、机制级语义放到新文件中；
   - 事件锚点保留 `cross_item_risks` 与 `review_status`，不提前结论化。

3. **最后再做汇总索引**
   - 允许一个上层视图把 person/object/event/mechanism 汇总到同一导航层；
   - 但汇总层只能做索引，不取代结构化源文件。

对于旧的 aggregate anchors，迁移原则是：

- 保持原有人物级总锚点不动；
- 只有在粒度一致、风险表达一致时才做引用复用；
- 不把事件或机制语义回填成人物综合判断。

## 6. Explicit handling for `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618`

这条锚点应被明确视为：

- `anchor_kind = event`
- `anchor_scope = three_pilot_migration`
- `object_type = 事件/机制对象`
- `review_status = pending_manual_risk_split` 或同等含义的待裁判状态

处理原则：

- 不能静默丢弃；
- 不能并入某个现有人物级 canonical 行；
- 不能因为它和第五项C / 第五项D 相邻，就直接把相邻项风险当成当前项结论；
- 不能把“宗室臣僚安全生态受损”简化成人物好坏判断。

推荐的临时落点是：

- 继续保留在 batch 语义里；
- 等未来 `data/thematic_anchor_events.jsonl` 就位后再进入事件层；
- 在人工裁判前，只把它当作“高风险、需拆分”的事件型负证候选。

## 7. Next PR shape for actual data migration/import

下一张 PR 不应该直接做全量导入，而应该只做 **schema 就位 + 小范围迁移**：

1. 增加或固定未来 canonical 文件结构；
2. 先迁移少量明确的人物对象锚点，验证字段路由；
3. 单独处理事件锚点，不与人物对象混写；
4. 如果要保留统一索引，再增加只读汇总视图。

对这次 batch 来说，下一 PR 最合理的切法是：

- 人物对象锚点先进入 `data/thematic_anchor_objects.jsonl`；
- `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 单独进入事件层候选；
- 现有 `data/thematic_anchors.jsonl` 保持不变，直到新 schema 已经被验证可用。

## 8. Validation checklist for future migration

未来真正迁移时，建议至少通过以下检查：

- JSONL 解析无误；
- `anchor_kind` 路由正确；
- `object_type`、`object_name`、`anchor_role` 不丢失；
- `cross_item_risks` 完整保留；
- `usable_for` 仍可用于下游分析；
- `review_status` 能区分候选、待审、已定稿；
- 事件锚点没有被回填成人物级综合结论；
- `linked_persons` 只做关联，不制造错误归属；
- `git diff --name-only` 只显示预期文件；
- 迁移前后 `data/thematic_anchors.jsonl` 的现有聚合锚点保持稳定，除非后续 PR 明确要求改动。

## 结论

本次最小安全方案是：

- 继续把 `data/thematic_anchors.jsonl` 作为人物/theme 聚合层；
- 为对象、事件、机制分别预留独立 canonical lane；
- `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 先保留为事件型待裁判候选，不进入人物级总锚点；
- 等 schema 验证完成后，再开下一张专门做数据迁移/import 的 PR。
