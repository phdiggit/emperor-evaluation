# Config Granularity Redesign Audit (2026-06-20)

## 1. 结论摘要

当前配置化第一阶段在“低风险切片”目标上是成功的，但在“长期用户可读性”上已经出现明显碎片化。

最典型的问题是：

- `data/view_configs/` 里多份文件都在表达“第五项B人物集合”的不同切面；
- 三人试点、扩展第一批、净证据导出目标，本质上不是三套独立人物配置，而是同一人物池上的不同视图分组；
- 对用户开放的配置文件命名仍偏技术化，且至少有一份用户可编辑 JSONL 仍使用了 `\uXXXX` 转义，不利于直接阅读和编辑。

本次审计建议：

1. 不继续沿着“一个小视图一个小文件”的方向扩张。
2. 长期应把用户可编辑配置统一收敛到：
   - `data/configs/视图配置/`
   - `data/configs/人工复核配置/`
   - `data/configs/受保护规则配置/`
3. 第五项B人物相关配置应逐步合并为两层：
   - `第五项B_人物池.jsonl`
   - `第五项B_视图分组.jsonl`
4. 用户可编辑 JSONL 应统一要求：
   - UTF-8 编码；
   - 中文直写；
   - 不使用 `\uXXXX` 转义；
   - 中文、短名、语义直观的文件名。

本 PR 只做设计审计，不迁移、不重命名、不改任何现有配置内容。

## 2. 当前配置目录清单

当前已存在且与本次审计直接相关的配置目录/位置如下：

### 2.1 `configs/`

当前文件：

- `configs/i5b_trial_targets.json`

### 2.2 `data/view_configs/`

当前文件：

- `data/view_configs/i5b_expanded_candidate_pool.jsonl`
- `data/view_configs/i5b_trial_targets.jsonl`
- `data/view_configs/i5b_expanded_batch1_targets.jsonl`
- `data/view_configs/i5b_net_evidence_targets.jsonl`

### 2.3 `data/review_configs/`

当前文件：

- `data/review_configs/search_keyword_profiles.jsonl`
- `data/review_configs/search_keyword_overrides.jsonl`

## 3. 当前每个配置文件的用途

| 路径 | 当前用途 | 备注 |
| --- | --- | --- |
| `configs/i5b_trial_targets.json` | 第五项B三人试点目标的旧式 JSON 配置 | 当前更像过渡性配置，不在最新 view-config / review-config 分层里 |
| `data/view_configs/i5b_expanded_candidate_pool.jsonl` | 第五项B扩展候选池行数据 | 包含人物、候选理由、风险、证据关注点、优先级 |
| `data/view_configs/i5b_trial_targets.jsonl` | 第五项B三人试点人物枚举 | 仅表达三人试点人物集合 |
| `data/view_configs/i5b_expanded_batch1_targets.jsonl` | 第五项B扩展第一批人物枚举 | 仅表达扩展第一批人物集合 |
| `data/view_configs/i5b_net_evidence_targets.jsonl` | 第五项B净证据导出人物与导出路径映射 | 本质上也是人物集合，只是附带逐人导出路径 |
| `data/review_configs/search_keyword_profiles.jsonl` | 第五项B检索关键词主 profile | 按子项/维度/极性/关键词族组织 |
| `data/review_configs/search_keyword_overrides.jsonl` | 第五项B检索关键词增量补丁 | 按时代/person 做 override，不复制整包关键词池 |

## 4. 哪些配置文件过碎

当前“过碎”的重点不在 review-config，而在 view-config 第一阶段的人物相关文件。

判定为过碎的配置：

1. `data/view_configs/i5b_trial_targets.jsonl`
   - 只表达“三人试点人物集合”；
   - 与人物池本体分离后，用户要跨文件才能理解“三人试点到底是哪些人”。

2. `data/view_configs/i5b_expanded_batch1_targets.jsonl`
   - 只表达“扩展第一批人物集合”；
   - 与候选池数据断裂，用户无法一处同时看到“人物是谁、为什么进池、属于哪个分组”。

3. `data/view_configs/i5b_net_evidence_targets.jsonl`
   - 既表达人物集合，又重复显式存逐人导出路径；
   - 长期看更像“视图分组 + 命名规则”，不是单独的数据实体。

4. `configs/i5b_trial_targets.json`
   - 继续保留会让“旧 JSON 入口”和“新 JSONL 入口”并存；
   - 目录层级和命名语义都不统一。

相对不算“过碎”的配置：

- `data/view_configs/i5b_expanded_candidate_pool.jsonl`
  - 这是人物池本体，信息密度高，长期仍有保留价值；
  - 但文件名和编码形式仍建议重构。

- `data/review_configs/search_keyword_profiles.jsonl`
- `data/review_configs/search_keyword_overrides.jsonl`
  - 这两份配置是“基础 profile / 增量补丁”的合理分层；
  - 当前尚未出现明显碎片化问题。

## 5. 哪些配置应合并

推荐合并对象如下：

### 5.1 人物相关 view-config 合并

应逐步合并为：

- `第五项B_人物池.jsonl`
- `第五项B_视图分组.jsonl`

对应关系：

- `i5b_expanded_candidate_pool.jsonl` 的人物主信息，进入 `第五项B_人物池.jsonl`
- `i5b_trial_targets.jsonl` 的“三人试点”集合，进入 `第五项B_视图分组.jsonl`
- `i5b_expanded_batch1_targets.jsonl` 的“扩展第一批”集合，进入 `第五项B_视图分组.jsonl`
- `i5b_net_evidence_targets.jsonl` 的“净证据导出目标”集合，进入 `第五项B_视图分组.jsonl`

### 5.2 关键词配置命名合并

逻辑上不要求把两份 review-config 合成一份，但命名应转向中文直观结构：

- `检索关键词_基础.jsonl`
- `检索关键词_补丁.jsonl`

也就是说：

- 保留“主 profile / 增量 override”的分层；
- 但把当前偏工程化的英文名改成中文短名。

## 6. 推荐的长期配置结构

长期建议采用统一中文目录：

```text
data/configs/
  视图配置/
  人工复核配置/
  受保护规则配置/
```

原因：

1. 比 `view_configs` / `review_configs` / `protected_rule_configs` 更直观
   - 对非开发用户更友好；
   - 目录语义一眼可懂。

2. 有利于后续做权限与说明分层
   - `视图配置`：低风险、偏展示与分组；
   - `人工复核配置`：影响人工复核路径，但不直接生成正式结果；
   - `受保护规则配置`：高敏感，需要人工确认。

3. 避免“普通配置”和“保护层规则”混在同一种英文技术目录里
   - 降低误改风险；
   - 提高审计可读性。

## 7. 是否建议采用 `data/configs/视图配置/`、`data/configs/人工复核配置/`、`data/configs/受保护规则配置/`

建议采用。

推荐结论如下：

- `data/configs/视图配置/`：建议
- `data/configs/人工复核配置/`：建议
- `data/configs/受保护规则配置/`：建议

不建议长期继续使用：

- `data/view_configs/`
- `data/review_configs/`

原因不是技术上不可用，而是：

- 命名偏工程化；
- 不够面向最终用户；
- 在配置数量增加后，英文技术名对审计和培训都不友好。

## 8. 是否建议把人物相关配置合并为 `第五项B_人物池.jsonl` 与 `第五项B_视图分组.jsonl`

建议。

这是本次审计最核心的长期结构建议。

### 8.1 `第五项B_人物池.jsonl`

建议承载：

- `person`
- `candidate_type`
- `why_selected`
- `expected_rule_pressure`
- `required_evidence_focus`
- `adjacent_item_risk`
- `negative_scan_focus`
- `recommended_priority`

也就是把“人物是什么、为什么在池里、风险点和证据关注点是什么”放到一处。

### 8.2 `第五项B_视图分组.jsonl`

建议承载：

- `group_id`
- `group_name`
- `group_type`
- `persons`
- `note`

其中 `persons` 可引用人物池中的 `person`。

示例分组：

- 三人试点
- 扩展第一批
- 净证据导出目标

这样用户看到“人物池”和“分组”两份文件，就能理解：

- 有哪些人物；
- 这些人物为什么存在；
- 每个视图/导出面具体使用哪个分组。

## 9. 三人试点、扩展第一批、净证据导出目标应如何表达为分组

不建议继续各自独立成一个配置文件。

建议作为 `第五项B_视图分组.jsonl` 的三类记录：

### 9.1 三人试点

示例语义：

- `group_id`: `第五项B_三人试点`
- `group_type`: `试点人物组`
- `persons`: `["李世民", "刘秀", "刘庄"]`

### 9.2 扩展第一批

示例语义：

- `group_id`: `第五项B_扩展第一批`
- `group_type`: `扩展人物组`
- `persons`: `["刘邦", "雍正", "朱元璋"]`

### 9.3 净证据导出目标

示例语义：

- `group_id`: `第五项B_净证据导出目标`
- `group_type`: `导出人物组`
- `persons`: `["李世民", "刘秀", "刘庄"]`

关键点：

- 同一个人物可以出现在多个分组中；
- 分组表达的是“用途和覆盖范围”，不是新的“人物主数据”；
- 人物主数据仍应只维护在 `第五项B_人物池.jsonl`。

## 10. 净证据导出路径是否应由命名规则生成，而不是逐人配置

建议长期改为“命名规则生成”，而不是继续逐人配置。

原因：

1. 当前逐人 `export_path` 重复度太高
   - `第五项B_李世民净证据池.md`
   - `第五项B_刘秀净证据池.md`
   - `第五项B_刘庄净证据池.md`
   本质上只是同一命名模板套不同人物名。

2. 逐人路径配置会放大碎片化
   - 人物一多，文件既像分组，又像路径映射；
   - 用户很难区分“哪个是人物集合，哪个是命名规则”。

3. 命名规则更符合长期治理
   - 分组配置只说“哪些人要导出净证据池”；
   - 路径由稳定规则生成，例如：
     - `exports/markdown_views/第五项B_{person}净证据池.md`

保留例外机制即可：

- 默认由命名规则生成；
- 只有极少数特殊路径才允许 override。

## 11. 开放给用户的配置文件命名规范

建议统一采用：

- 中文
- 短名
- 语义直观

### 11.1 命名原则

1. 直接表达用途
   - 例如 `第五项B_人物池.jsonl`
   - 而不是 `i5b_expanded_candidate_pool.jsonl`

2. 优先让用户看懂，而不是优先体现内部脚本名
   - 文件名应为业务语义名，不应是 Python 常量翻译件。

3. 控制长度
   - 不追求把全部上下文都塞进文件名；
   - 目录分层负责大类，文件名负责对象本身。

### 11.2 推荐示例

- `第五项B_人物池.jsonl`
- `第五项B_视图分组.jsonl`
- `检索关键词_基础.jsonl`
- `检索关键词_补丁.jsonl`

## 12. `\uXXXX` Unicode 转义审计结果

本次扫描范围：

- `configs/`
- `data/view_configs/`
- `data/review_configs/`

扫描结果：

- 发现 `\uXXXX` 转义：`data/view_configs/i5b_expanded_candidate_pool.jsonl`
- 未发现 `\uXXXX` 转义：
  - `configs/i5b_trial_targets.json`
  - `data/view_configs/i5b_trial_targets.jsonl`
  - `data/view_configs/i5b_expanded_batch1_targets.jsonl`
  - `data/view_configs/i5b_net_evidence_targets.jsonl`
  - `data/review_configs/search_keyword_profiles.jsonl`
  - `data/review_configs/search_keyword_overrides.jsonl`

问题判断：

- `i5b_expanded_candidate_pool.jsonl` 属于用户可编辑配置；
- 当前用 `\uXXXX` 转义会显著削弱可读性；
- 这与“开放给用户的配置文件应可直接阅读和修改”的目标不一致。

本 PR 不直接修复该文件，只记录为迁移时的优先整改对象。

## 13. 用户可编辑 JSONL 的编码要求

建议明确写成仓库长期规范：

1. 用户可编辑 JSONL 必须使用 UTF-8。
2. 中文内容必须直写。
3. 不允许把中文内容保存成 `\uXXXX` 转义形式。
4. 若脚本写回用户可编辑 JSONL，必须保持中文直写。

理由很简单：

- 用户要能直接看；
- reviewer 要能直接审；
- diff 要能直接读；
- 配置不能因为编码表现形式而变成“技术人员专属文本”。

## 14. 分阶段迁移计划

推荐迁移顺序如下：

### 第一步：修 Unicode 编码

目标：

- 把用户可编辑 JSONL 里的 `\uXXXX` 转义改成 UTF-8 中文直写。

范围建议优先：

- `data/view_configs/i5b_expanded_candidate_pool.jsonl`

### 第二步：新增中文命名目标结构，但保留旧路径兼容

新增目标结构：

- `data/configs/视图配置/第五项B_人物池.jsonl`
- `data/configs/视图配置/第五项B_视图分组.jsonl`
- `data/configs/人工复核配置/检索关键词_基础.jsonl`
- `data/configs/人工复核配置/检索关键词_补丁.jsonl`

同时：

- 暂时保留旧路径；
- 允许脚本双读新旧结构；
- 先不立即删旧碎配置。

### 第三步：脚本读取新结构，旧文件废弃

目标：

- 逐步把脚本切到读取新结构；
- 旧文件进入废弃状态，但仍可短期保留只读兼容。

重点动作：

- 三人试点、扩展第一批、净证据导出目标改读 `第五项B_视图分组.jsonl`
- 候选池改读 `第五项B_人物池.jsonl`
- 净证据导出路径优先改为命名规则生成

### 第四步：删除旧碎配置

当新结构稳定后，删除：

- `configs/i5b_trial_targets.json`
- `data/view_configs/i5b_trial_targets.jsonl`
- `data/view_configs/i5b_expanded_batch1_targets.jsonl`
- `data/view_configs/i5b_net_evidence_targets.jsonl`
- 以及被新结构完全替代的旧命名文件

## 15. 推荐的长期目标结构

建议长期落点如下：

```text
data/configs/
  视图配置/
    第五项B_人物池.jsonl
    第五项B_视图分组.jsonl
  人工复核配置/
    检索关键词_基础.jsonl
    检索关键词_补丁.jsonl
  受保护规则配置/
    人物定档建议.jsonl
    档位分数区间.jsonl
```

这里的关键不是一次把所有东西都迁过去，而是先把：

- 人物池
- 视图分组
- 检索关键词主配置
- 检索关键词增量补丁

这四类最容易让用户理解的对象收拢起来。

## 16. 本次判定为“过碎”的配置与推荐合并目标

判定为过碎的配置：

- `configs/i5b_trial_targets.json`
- `data/view_configs/i5b_trial_targets.jsonl`
- `data/view_configs/i5b_expanded_batch1_targets.jsonl`
- `data/view_configs/i5b_net_evidence_targets.jsonl`

推荐合并后的目标结构：

- `data/configs/视图配置/第五项B_人物池.jsonl`
- `data/configs/视图配置/第五项B_视图分组.jsonl`
- `data/configs/人工复核配置/检索关键词_基础.jsonl`
- `data/configs/人工复核配置/检索关键词_补丁.jsonl`

## 17. 边界声明

本 PR 只做设计审计，不做以下操作：

- 不迁移现有配置；
- 不重命名现有配置；
- 不修改任何 `data/*` 内容；
- 不修改任何 `scripts/*`；
- 不修改任何 `tests/*`；
- 不修改任何 `configs/*`；
- 不修改任何 `exports/*`；
- 不修改 generated docs；
- 不修改 scoring / adjudication / formal score / ranking / leaderboard。

## 18. 2026-06-21 implementation note

后续迁移审计已完成：第五项B旧碎配置文件与读取 fallback 已删除，当前唯一主维护入口为：

- `data/configs/视图配置/第五项B_人物池.json`
- `data/configs/视图配置/第五项B_视图分组.json`
