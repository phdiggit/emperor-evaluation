# Manual Review Config Layer Design (2026-06-20)

## 1. 结论摘要

本设计文档讨论的是“人工裁判辅助配置层”，不是 view-config 的继续扩张。

`data/view_configs/` 第一阶段承载的是低风险导出视图数据，例如：

- 人物枚举；
- 候选池结构化行；
- 导出目标映射；
- 非规则型视图配置。

而下一层要支撑的是：

- 检索关键词组织；
- 回源核验触发；
- 原子证据定级辅助；
- 证据簇归并与定级辅助；
- 人物临时档位建议；
- 档位到正式分数的受保护映射。

这些内容已经明显触及人工复核流程、规则边界、正式结果保护，因此不能继续与 `data/view_configs/` 混放。

结论建议：

- 建立独立的 `review_configs/` 层，专门承载“人工裁判辅助配置”；
- 再向上单独建立 `protected_rule_configs/` 层，承载受保护规则与正式结果边界；
- `view_configs/` 保持“导出视图数据层”定位，不继续吸收 review / scoring / protected-rule 内容。

## 2. 为什么 review config 不能继续放在 `data/view_configs/`

`data/view_configs/` 的成功前提是：它装的是“渲染目标、人物枚举、结构化行数据”，而不是“判断逻辑”。

如果把人工裁判辅助配置继续放进 `data/view_configs/`，会有四个问题：

1. 语义层级混乱
   - `view_configs` 当前语义是“导出视图层”；
   - review config 语义是“人工裁判辅助层”；
   - 两者混放后，reviewer 很难一眼区分“只是改导出”还是“实质影响判断辅助”。

2. 风险边界模糊
   - 检索关键词、回源触发器、证据定级规则已经可能影响人工审查路径；
   - 如果仍放在 `view_configs`，容易被误当作普通可调展示配置。

3. 校验器职责会被污染
   - `validate_view_configs.py` 当前只做最小 parse/schema；
   - review config 未来需要更强的字段约束、去重约束、引用约束；
   - 把这两类校验混在一个 validator 里，会让第一阶段轻量护栏失焦。

4. 审计与审批路径不一致
   - view-config 的变更可以按“低风险结构化数据”审；
   - review config 的变更应按“影响人工裁判辅助”的更高敏感度审；
   - 同目录混放不利于后续建立差异化审批。

因此，review config 不应继续进入 `data/view_configs/`。

## 3. `review_configs` 与 `protected_rule_configs` 的边界

推荐分层如下：

### 3.1 `review_configs`

定位：

- 给人工审查提供辅助线索、候选规则、触发器、对象池；
- 可以影响“看什么、怎么归类、优先复核什么”；
- 不能直接产生正式结果。

允许承载的典型内容：

- search keyword profiles；
- source verification triggers；
- evidence anchor objects；
- atomic evidence grading rules；
- cluster merge rules；
- cluster grading rules；
- temporary band suggestion mappings。

不允许承载的内容：

- 正式分数；
- 正式排名；
- 自动发布开关；
- 无人工确认的正式档位结论。

### 3.2 `protected_rule_configs`

定位：

- 承载高保护层规则与正式结果边界；
- 即使配置化，也必须受人工确认和更严格审核流程保护；
- 不能被当作普通用户可调配置。

典型内容：

- 人物定档到正式档位的受保护映射；
- 档位到正式分数区间的受保护映射；
- 正式结果保护语句；
- 自动裁判的最高敏感规则边界。

判断标准：

- 如果某项配置变化会直接提高“自动写正式结论”的风险，它就不属于 `review_configs`；
- 如果某项配置只是在人工复核前提供候选参考，它可以留在 `review_configs`。

## 4. 检索关键词配置如何避免臃肿

设计原则：

- 以“项目 / 子项”为主；
- 以“时代 / person override”为辅；
- 不按人物全量复制关键词池。

### 4.1 推荐分层

先建立：

- `search_keyword_profiles`

按 `item` / `subitem` 维护主配置：

- `positive_terms`
- `negative_terms`
- `reversal_terms`
- `source_scopes`
- `query_modes`

然后只在必要时建立：

- `search_keyword_overrides`

用于处理：

- 特定时代的术语差异；
- 特定人物的异名、制度背景、文献别称；
- 个别人物独有的检索噪音过滤。

### 4.2 避免臃肿的压缩策略

1. 不按人物复制主 profile
   - 同一子项先共享一份主 profile；
   - 人物层只记录增量 override。

2. override 只允许表达差异
   - 例如 `append_terms`、`exclude_terms`、`replace_terms`；
   - 不允许整包重写主 profile。

3. query mode 独立于 person
   - 例如“正证回源”“负证回源”“制度背景扫描”应先按子项建模；
   - person 只修正术语，不改模式定义。

## 5. 原子证据定级配置如何避免臃肿

设计原则：

- 按 `subitem + dimension + polarity + evidence_type` 组织；
- 不按人物复制规则；
- 锚点对象单独建池，通过 `anchor_id` 引用。

### 5.1 为什么不能按人物复制

如果把原子证据定级规则按人物复制，会立即产生：

- 同类规则大量重复；
- 人物之间不一致但难以追踪；
- review 时无法分辨“规则不同”还是“只是人物名字不同”。

原子证据定级应优先表达“什么类型的证据，在什么维度/极性下，通常如何处理”，而不是“某人默认怎么判”。

### 5.2 推荐结构

- `atomic_evidence_grading_rules`

关键组织键：

- `subitem`
- `dimension`
- `polarity`
- `evidence_type`

可选辅助字段：

- `grade_hint`
- `needs_source_verification`
- `single_source_limit`
- `adjacent_item_guardrail`
- `anchor_ids`
- `notes`

### 5.3 锚点对象独立建池

另建：

- `evidence_anchor_objects`

由 `anchor_id` 管理高复用对象，例如：

- 典型事件锚点；
- 典型制度锚点；
- 特定争议类型锚点；
- 可重复引用的 object anchor 组合。

原子定级规则只引用 `anchor_id`，不内嵌整段对象定义，避免重复膨胀。

## 6. 证据簇归并与证据簇定级配置如何避免臃肿

设计原则：

- merge rules 和 grading rules 分离；
- 按 `rule_type` 组织；
- 支持 negative override / single evidence limit / same source dedup / adjacent item guardrail。

### 6.1 为什么 merge 和 grading 必须分离

“是否归并到同一证据簇”和“归并后证据簇如何定级”是两个不同问题：

- merge 处理的是聚合边界；
- grading 处理的是强弱判断。

如果混在一起：

- 很难定位某次变更到底改变了“聚类逻辑”还是“强度逻辑”；
- 也不利于后续对相邻项守卫和负证 override 做局部审查。

### 6.2 推荐配置类型

- `cluster_merge_rules`
- `cluster_grading_rules`

二者都按 `rule_type` 分类，例如：

- `same_event_merge`
- `same_institution_merge`
- `same_source_dedup`
- `negative_override`
- `single_evidence_limit`
- `adjacent_item_guardrail`
- `cross_source_reinforcement`

### 6.3 压缩策略

1. 规则类型优先于人物
   - 先按 rule type 组织；
   - 不按人物复制一套 merge/grading 规则。

2. 例外条件独立表达
   - `negative_override`
   - `single_evidence_limit`
   - `same_source_dedup`
   - `adjacent_item_guardrail`
   应作为显式字段或显式 rule type，而不是散落在备注中。

3. 共享 guardrail，不重复抄写
   - 相邻项守卫、同源去重等高复用规则应统一引用；
   - 避免在每条 grading rule 里重复写一遍。

## 7. 回源核验触发器如何设计

设计原则：

- 按触发条件组织，而不是按人物；
- 目标是告诉 reviewer “什么时候必须回源 / 复核”，不是“某人固定触发什么”。

### 7.1 推荐配置类型

- `source_verification_triggers`

### 7.2 典型触发场景

- 强证候选出现；
- 关键簇候选出现；
- 仅有二手材料；
- 缺原文；
- 高争议反转材料；
- 单一来源支撑高等级判断；
- 相邻项污染风险升高。

### 7.3 关键字段建议

- `trigger_id`
- `trigger_type`
- `applies_to_subitem`
- `applies_to_dimension`
- `applies_to_polarity`
- `condition_summary`
- `required_action`
- `priority`
- `notes`

### 7.4 避免臃肿的策略

- 不按人物建触发器；
- 用统一的条件类型复用触发逻辑；
- 人物差异若确有必要，只作为极少数 override。

## 8. 人物定档映射为什么属于 `protected_rule_configs`

人物定档映射已经接近正式结果面，因此不能作为普通 review config。

原因：

1. 只能给临时档位建议
   - review config 可以给 `temporary_band_suggestion`；
   - 不能直接写 `formal_band`。

2. 需要人工确认
   - 人物定档本身具有汇总性和裁判性；
   - 一旦配置化后被误用为自动落档，风险远高于检索关键词或回源触发器。

3. 不得自动写正式档位
   - 即使系统内部有建议映射，也只能输出“建议复核”；
   - 不能无人工确认地落入正式结果文件或正式导出面。

因此，人物定档映射如果未来配置化，应归入 `protected_rule_configs`，并默认带有人审门槛。

## 9. 档位到正式分数映射为什么属于最高保护层

档位到正式分数映射比人物定档映射更敏感，属于最高保护层。

原因：

1. 只能框定分数区间
   - 配置最多表达某档位对应的“候选区间”；
   - 不应直接等同为最终正式分。

2. 不得自动发布正式分
   - 即使存在区间映射，也不能自动写入正式分数字段；
   - 更不能借此生成正式排名或总榜。

3. 必须人工确认
   - 正式分数是结果发布面；
   - 一旦错误配置，损害范围大于关键词、回源触发器或证据簇规则。

因此，这类映射只能属于 `protected_rule_configs` 的最高保护层。

## 10. 每类配置建议的文件名、用途、关键字段、膨胀风险、压缩策略

| config file | 用途 | 关键字段 | 膨胀风险 | 压缩策略 |
| --- | --- | --- | --- | --- |
| `review_configs/search_keyword_profiles.jsonl` | 子项级检索关键词主配置 | `item`, `subitem`, `query_mode`, `positive_terms`, `negative_terms`, `reversal_terms`, `source_scopes` | 人物复制整包 profile | 只保留子项主配置 |
| `review_configs/search_keyword_overrides.jsonl` | 时代/person 差异 override | `scope_type`, `scope_key`, `subitem`, `append_terms`, `exclude_terms`, `replace_terms` | override 反客为主 | override 仅表达增量差异 |
| `review_configs/source_verification_triggers.jsonl` | 回源核验触发器 | `trigger_id`, `trigger_type`, `applies_to_subitem`, `condition_summary`, `required_action`, `priority` | 按人物复制触发器 | 统一按触发条件建模 |
| `review_configs/evidence_anchor_objects.jsonl` | 高复用锚点对象池 | `anchor_id`, `anchor_type`, `subitem`, `dimension`, `object_summary`, `notes` | 同类锚点反复内嵌 | 独立对象池，其他规则只引用 `anchor_id` |
| `review_configs/atomic_evidence_grading_rules.jsonl` | 原子证据定级辅助 | `rule_id`, `subitem`, `dimension`, `polarity`, `evidence_type`, `grade_hint`, `anchor_ids` | 按人物复制规则 | 按 evidence type 组织，不按人物复制 |
| `review_configs/cluster_merge_rules.jsonl` | 证据簇归并规则 | `rule_id`, `rule_type`, `subitem`, `dimension`, `merge_condition`, `same_source_dedup`, `adjacent_item_guardrail` | merge 与 grading 混写 | merge 独立成层 |
| `review_configs/cluster_grading_rules.jsonl` | 证据簇定级规则 | `rule_id`, `rule_type`, `subitem`, `dimension`, `polarity`, `grade_hint`, `negative_override`, `single_evidence_limit` | 例外条件散落在备注 | 把 override / limit 做成显式字段 |
| `protected_rule_configs/temporary_band_suggestions.jsonl` | 临时档位建议映射 | `mapping_id`, `subitem`, `preconditions`, `suggested_band`, `requires_human_confirmation` | 被误用为正式档位 | 只允许 suggestion，不允许 formal band |
| `protected_rule_configs/formal_band_score_ranges.jsonl` | 档位到正式分数区间的受保护映射 | `band`, `score_range_min`, `score_range_max`, `requires_human_confirmation`, `publish_blocked` | 被误用为自动正式出分 | 只表达区间，默认阻止自动发布 |

## 11. 明确禁止字段

以下字段不应出现在普通 `review_configs` 中，也不应在缺少人工确认的情况下进入任何可调配置层：

- `final_score`
- `final_rank`
- `leaderboard_position`
- `auto_decision`
- `auto_publish`
- `formal_band_without_human_confirmation`

这些字段的共同问题是：它们直接指向正式结果自动化，超出了“人工裁判辅助配置”的安全边界。

## 12. 推荐实施顺序

建议顺序如下：

1. `search_keyword_profiles` / `search_keyword_overrides`
   - 风险相对最低；
   - 最容易做出“主 profile + 增量 override”的压缩结构。

2. `source_verification_triggers`
   - 能提升回源一致性；
   - 但仍停留在“提醒与触发”层。

3. `evidence_anchor_objects`
   - 先把高复用锚点对象抽离；
   - 为后续原子规则和簇规则压缩做准备。

4. `atomic_evidence_grading_rules`
   - 在锚点对象池存在后更容易避免重复。

5. `cluster_merge_rules` / `cluster_grading_rules`
   - 这是更敏感的一层；
   - 必须等 merge / grading 分层边界明确后再做。

6. 最后才考虑 `protected_rule_configs`
   - 包括临时档位建议与正式分数区间映射；
   - 严禁在前几层未稳定前抢先实现。

## 13. 边界声明

本 PR 只提供设计文档，不实现任何配置层。

明确不做：

- 不新增 `review_configs/` 文件；
- 不新增 `protected_rule_configs/` 文件；
- 不修改 `scripts/*`；
- 不修改 `tests/*`；
- 不修改 `data/*`；
- 不修改 `data/view_configs/*`；
- 不修改 `exports/*`；
- 不修改 generated docs；
- 不修改 scoring / adjudication / formal score / ranking / leaderboard。
