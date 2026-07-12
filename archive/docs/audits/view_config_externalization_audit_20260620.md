# View Config Externalization Audit (2026-06-20)

## 1. 结论摘要

本轮 view-config 第一阶段可以视为已完成收口。

当前已经完成的低风险配置化对象，集中在三类：

- 结构化行数据：`i5b_expanded_candidate_pool.jsonl`
- 人物/导出 target 映射：`i5b_net_evidence_targets.jsonl`
- 批次人物枚举：`i5b_expanded_batch1_targets.jsonl`

同时，`scripts/validate_view_configs.py` 已对现有 `data/view_configs/*.jsonl` 建立最小 parse/schema 护栏，足以支撑“第一阶段低风险配置化”这一层级。

结论建议：

- 不建议立刻继续外置路径常量、表头 arrays、模板正文。
- 如果下一阶段继续，优先做“剩余结构化枚举数据”的极小切片，而不是扩成通用配置框架。
- 评分、档位、自动裁判规则、正式结果保护语句，继续明确排除在普通用户可调配置层之外。

## 2. 当前 `data/view_configs` 文件清单

| file | 来源脚本 | 来源常量/数据块 | 当前用途 |
| --- | --- | --- | --- |
| `data/view_configs/i5b_expanded_candidate_pool.jsonl` | `scripts/export_project_doc_views.py` | `I5B_EXPANDED_CANDIDATE_POOL_ROWS` | 第五项B扩展候选池行数据 |
| `data/view_configs/i5b_net_evidence_targets.jsonl` | `scripts/export_i5b_net_evidence.py` | `I5B_NET_EVIDENCE_TARGETS` | 净证据导出目标人物与导出路径映射 |
| `data/view_configs/i5b_expanded_batch1_targets.jsonl` | `scripts/export_i5b_expanded_batch1.py` | `EXPANDED_BATCH1_PERSONS` | expanded batch1 人物枚举顺序 |

这些文件都属于“结构化枚举/视图数据”，而不是业务判断逻辑。

## 3. `validate_view_configs.py` 当前覆盖范围

当前 `scripts/validate_view_configs.py` 已覆盖以下最小 schema：

### 3.1 通用层

- `data/view_configs/*.jsonl` 的每个非空行都必须可解析；
- 每个非空行都必须是 JSON object；
- 报错包含文件名与行号。

### 3.2 `i5b_expanded_candidate_pool.jsonl`

必填字段：

- `person`
- `candidate_type`
- `why_selected`
- `expected_rule_pressure`
- `required_evidence_focus`
- `adjacent_item_risk`
- `negative_scan_focus`
- `recommended_priority`

附加约束：

- `recommended_priority` 必须匹配 `P<number>` 格式。

### 3.3 `i5b_net_evidence_targets.jsonl`

必填字段：

- `person`
- `export_path`

若存在以下字段，则必须为非空字符串：

- `person`
- `person_key`
- `path`
- `output_path`
- `doc_path`
- `export_path`

### 3.4 `i5b_expanded_batch1_targets.jsonl`

必填字段：

- `person`

若存在以下字段，则必须为非空字符串：

- `person`
- `person_key`
- `target`
- `doc_path`
- `export_path`
- `source_path`
- `output_path`

### 3.5 当前未覆盖的范围

当前 validator 仍然刻意不做以下检查：

- 不检查人物结论是否合理；
- 不检查净证据/补证/裁判结果；
- 不检查评分、档位、正式结果、排名；
- 不检查模板正文内容；
- 不检查路径是否存在或是否应双写。

这条边界是合理的，因为第一阶段目标是“最小 parse/schema 护栏”，不是把业务判断搬进配置校验器。

## 4. 现有 exporter 中是否还有明显适合继续外置的结构化枚举数据

有，但已经从“高收益低风险”进入“收益还行、但不急于立刻做”的阶段。

当前还能看到的明显剩余对象：

1. `scripts/export_md.py` 中的 `I5B_TRIAL_TARGETS`
   - 形态上仍是纯人物枚举；
   - 风险低于路径常量、表头 arrays、模板正文；
   - 若后续继续做第二阶段，优先级最高。

2. 个别导出入口里的“小规模 target/person list”
   - 前提是它们确实只承载人物顺序或目标集合；
   - 如果混入 workflow 含义、规则边界或文案语义，就不应继续按普通 view-config 推进。

除此之外，现有导出脚本里已经没有太多“显眼且独立”的纯结构化枚举数据了。剩余硬编码更多开始落到路径常量、表头 arrays、模板正文和规则边界文案上，这些都比第一阶段对象更敏感。

## 5. 哪些剩余硬编码应暂时留在代码里

以下内容建议继续留在代码中，不进入当前普通 view-config 层：

### 5.1 路径常量

例如：

- `docs/...`
- `exports/markdown_views/...`
- 各类 batch file 路径

原因：

- 当前路径仍与导出函数、双写策略、命名约定紧耦合；
- 一旦开放成普通配置，很容易把“导出目标治理”误降级成“任意改路径”；
- 当前阶段收益不如继续清理结构化枚举数据。

### 5.2 表头 arrays

例如：

- `HEADERS`
- `SEARCH_LOG_HEADERS`
- `NET_EVIDENCE_CARD_HEADERS`
- `EXPANDED_BATCH1_*_HEADERS`

原因：

- 它们看似像配置，实则与渲染顺序、测试断言、字段存在性假设耦合；
- 一旦外置，review 面会从“数据位置变化”扩大成“视图结构治理”。

### 5.3 模板正文与规则说明文案

例如：

- “不定档、不出分、不排名、不出总榜”
- readiness/review package/relative band 准备文案
- 全局总标尺简报说明段落

原因：

- 这些文本里已经混有治理边界与保护语句；
- 表面是文案，实际承载规则风险。

## 6. 风险分级：路径常量、表头 arrays、模板正文、规则说明文案

| 类型 | 风险等级 | 说明 |
| --- | --- | --- |
| 路径常量 | 中 | 技术上易外置，但会把导出目标治理暴露成普通配置；现阶段没必要立刻做。 |
| 表头 arrays | 中到中高 | 看似枚举，实则影响渲染结构、测试断言与字段假设；比人物列表更敏感。 |
| 模板正文 | 中高 | 一部分只是说明文案，一部分已包含“不得正式出分”等保护边界；不宜整包外置。 |
| 规则说明文案 | 高 | 经常混有规则状态、人工确认边界、结果保护语义；普通用户可调风险高。 |

补充说明：

- “风险高”不代表永远不能外置；
- 它表示若未来真的外置，必须先拆出受保护规则层，而不能直接放进普通 `data/view_configs/*.jsonl`。

## 7. 是否建议立刻继续外置路径/表头

不建议。

原因有三点：

1. 第一阶段的收益点已经基本拿到。
   当前最明显、最低风险的结构化枚举数据已经完成三刀外置。

2. 再往下走，风险会明显上升。
   剩余对象大多不是“纯枚举”，而是开始和渲染结构、文案语义、保护边界耦合。

3. 当前仓库更需要的是边界稳定，而不是继续追求“把所有硬编码都搬出去”。
   如果为了配置化而配置化，反而容易削弱审计可读性和规则保护层。

## 8. 下一阶段如果继续，优先做哪一类

如果确实继续，建议优先级如下：

1. 剩余纯人物/target 枚举数据
   - 首选 `scripts/export_md.py` 里的 `I5B_TRIAL_TARGETS`
   - 条件：保持“只外置枚举，不外置逻辑、不外置路径治理”

2. 极小范围的视图型结构化数据
   - 前提是该数据不承载评分、裁判、保护语句；
   - 仍然应以“一行一个 JSON object”的窄 schema 为主。

3. 不建议作为下一阶段优先项的内容
   - 路径常量
   - 表头 arrays
   - 模板正文
   - 规则说明文案

## 9. 明确不得进入普通用户可调配置层的内容

以下内容不应进入普通用户可调配置层，即便未来建立更复杂的配置体系，也必须继续保留人工确认或受保护层：

### 9.1 评分与档位

- 试算分值映射
- 档位到分值的映射
- 相对档位到正式结果的转换

### 9.2 自动裁判规则

- 自动裁判触发条件
- 规则敏感点清单
- 负证拦截门槛
- 相邻项切分守卫
- 维度判断启发式

### 9.3 正式结果保护语句

- “不正式出分”
- “不排名”
- “不生成总榜”
- “不得直接推分”

这些语句虽然是文本形式，但本质上属于结果保护边界，不应当被视为普通模板装饰。

### 9.4 正式结果面

- formal score
- ranking
- leaderboard
- 正式结论状态

这些内容即使未来做更强的配置治理，也不应进入普通用户可直接调整的 view-config 层。

## 10. 审计判断：第一阶段是否完成

判断：已完成。

完成依据：

- 已有 3 份 view-config JSONL 落地；
- 已有统一的最小 validator；
- 已把 validator 纳入 `validate_all.py`；
- 已建立 focused tests，覆盖：
  - JSONL schema 错误识别；
  - exporter 确实从 JSONL 读取；
  - 原有 smoke 行为不变。

因此，当前最合适的动作不是继续扩张外置范围，而是先把这一阶段视为收口完成，并把“什么不该外置”写清楚。

## 11. 下一阶段建议

建议：

- 当前不立刻开“路径常量/表头 arrays 外置”实现任务；
- 如果要继续，只开一个很小的 issue，专门评估 `scripts/export_md.py` 的 `I5B_TRIAL_TARGETS` 是否值得按同样模式外置；
- 若没有明确收益或新增复用需求，可以先暂停 view-config 扩张，转入其他更高价值工作。
