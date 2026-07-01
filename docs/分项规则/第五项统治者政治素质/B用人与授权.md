# B用人与授权

## 定位

本文是第五项B《用人与授权》的唯一分项规则文档，收束原第五项B边界说明、正式工作流模板、正式定分公式、对象史料上下文机制和负向材料分案中的第五项B专用内容。通用证据、数据和展示规则通过链接引用，不在本文重复长文。

## 本分项引用以下通用规则

- 最高层评分标准：[`../../皇帝综合评价体系评分标准.md`](../../皇帝综合评价体系评分标准.md)
- 项目总规则：[`../../项目总纲/总规则.md`](../../项目总纲/总规则.md)
- 史料检索与回源工作流：[`../../证据规则/史料检索与回源工作流.md`](../../证据规则/史料检索与回源工作流.md)
- 证据簇计算公式：[`../../证据规则/证据簇计算公式.md`](../../证据规则/证据簇计算公式.md)
- 数据主表字段规范：[`../../数据结构与生成库/数据主表字段规范.md`](../../数据结构与生成库/数据主表字段规范.md)
- query/search 字段规范：[`../../数据结构与生成库/query_profile与search_log字段规范.md`](../../数据结构与生成库/query_profile与search_log字段规范.md)
- 人工阅读型 Markdown 导出规范：[`../../展示与协作/人工阅读型Markdown导出规范.md`](../../展示与协作/人工阅读型Markdown导出规范.md)

## 评价对象

第五项B只评价统治者识人、择人、任人、授权、容纳谏诤、保护表达安全和维持人才生态的能力。评价对象可以是人物、人才群体、任用机制、授权链条或表达安全生态，但它们必须能回到“用人与授权”本项核心。

被任用对象层级只通过本规则中的 `talent_quality_factor`、`object_weight`、`office_weight` 等因子或团队级聚合过程影响材料分。顶级人物、制度关键岗位、跨地域或跨系统人才网络可以提高对应材料的因子值；普通个案、低层执行者或偶发任免只能按对应因子进入信号，不另设额外上限或档位判断。

## 对象、史料与检索覆盖口径

第五项B当前计分链只认对象、史源、规则和公式因子，不引入额外的中间分层算法。检索包、搜索日志、批次说明和 PR 风险说明都不是分值来源；只有已经回源、完成相邻项切分并写入 `obj_srcs` 的材料，才允许进入 `evd_clusters`。

对象和材料进入计算前必须满足：

- `raw_objs` 保持原始对象粒度，不能合并加工；
- 每个 `raw_objs` 至少有一条 `obj_srcs` 史料链；
- `obj_srcs` 必须绑定 `emp_obj_id`、`item_id`、`rule_id`、`doc_id` 和方向；
- `talent_quality` 等对象属性必须来自 `obj_attrs`，并保留 `doc_id`；
- 相邻项材料必须先切分，只把第五项B剩余部分落到对应 `rule_code`；
- 没有材料的 `rule_code` 不生成证据簇，结果层按 0 处理。

对象属性只回答对象质量、角色权重或规则因子取值，不是独立分数。

高风险线索应在 `search_logs`、`source_review_log`、批次 review log 或 PR body 中保留状态，例如 `pending_source_review`、`source_verified_objectized`、`adjacent_only`、`excluded_with_reason`。这些状态用于防漏检和复核，不直接改写公式输出。

### 关键词补齐与 query lane 报告

关键词补齐、补搜词、检索对象扩展和相邻项切分线不得写进 `project_config.yml`。这些研究输入必须通过以下持久化位置承载：

- `query_profiles` / `data/query_profile_batches/**`：人物或批次的正向、负向、反转 / 相邻项 query dimensions；
- `search_logs`：具体 query lane 的检索入口、结果状态、对象化关系、未决状态和排除理由；
- `source_review_log`：回源结果、未决 lead、排除理由、相邻项切分和 PR 复核说明；
- 对象导入 payload：已经人工回源判断、可写入 `raw_objs` / `emp_objs` / `obj_srcs` / `obj_attrs` 的材料。

每个 I5B source/object batch 必须报告正向、负向、相邻项 query lanes 的覆盖、对象化、入库、未决和排除理由。报告可以写在 PR body、批次 manifest / review log 或 `source_review_log`，但必须能追溯到相应 `query_profile_id`、`search_id`、史源、`raw_objs` / `obj_srcs` / `obj_attrs` 入库记录，或 exclusion / pending reason。

## 计入第五项B

可计入第五项B的材料包括：

- 识别、拔擢、信任和长期任用关键人才；
- 对能臣、谏臣、异质人才、旧敌或边缘人才的整合与保护；
- 授权专任、权责清晰、避免反复猜忌或任意掣肘；
- 建立或维持表达安全、反馈入口和纠错环境；
- 人才生态的结构性改善或结构性破坏；
- 处置核心人才时是否存在明确事实链条、程序边界、外溢影响和后续补救。

## 不直接计入第五项B

以下内容不得直接计入第五项B：

- 政策最终收益，主要归第二项或第四项；
- 军事战果，主要归第一项或第三项；
- 权力集中、制度控制本身，主要归第五项其他子项；
- 统治者道德残酷性本身，主要归第五项相邻子项或第七项；
- 认知、学习、纠错能力本身，主要归第五项相邻子项或治国能力项；
- 行政执行成效本身，主要归第二项相关子项；
- 后宫、男宠、宦官等身份因素本身，除非其实际干预核心任免、授权、表达安全或人才生态。

## 相邻项切分

材料明显涉及安全、司法、行政、政策或战果时，必须同时记录应切往的相邻项，不得强行纳入第五项B。

- 政权安全案：先判断谋反、叛乱、司法程序和政权安全归属；剥离后只保留对人才安全、表达寒蝉或授权信用的剩余影响。
- 军事失败或战功：战果归军事项；只有错用将帅、任将机制或长期授权失衡才可保留第五项B剩余。
- 政策成败：政策收益或损害归治国、文明或负债项；第五项B只记录用人链条本身。
- 私德与残酷性：道德评价不得直接转写为用人负证；只有实际破坏人才生态或表达安全才进入第五项B。

相邻项主导的大案，剥离后第五项B只保留可对应具体对象和规则因子的剩余影响；若只有轻微外溢或象征性影响，只作备注，不进入信号计算。

## 专用触发点

第五项B负向材料重点包括：

- 无明确谋反嫌疑而处置核心人才、能臣或谏臣；
- 嫌疑明显但未坐实，且证据争议、追悔、恢复评价或反形未具；
- 大规模株连、系统清洗或人才生态污染；
- 身后追责造成现实外溢、信用撤销或群臣表达安全下降；
- 宠信佞臣、近幸用事、后宫/男宠/宦官实际干预核心任免；
- 错用将相导致长期授权失衡，或压制谏臣造成表达寒蝉；
- 同一规则下正负材料并存，不能机械抵消。

确有谋反链条的功臣处置，不得机械计为第五项B负向分；未坐实但嫌疑明显的疑案必须按具体对象、史料和剩余第五项B影响拆分。死后信任逆转若出现公开信用撤销并直接命中谏臣或表达安全预期，应落到具体对象和规则因子；只有系统牵连扩大、群体外溢、表达寒蝉或授权可信度破裂等材料，才提高对应负向因子。

## 规则计算复核点

第五项B当前计算链为 `obj_srcs` / `obj_attrs` → `evd_clusters` / `evd_cluster_calc_details` → `emp_item_results` / `emp_item_result_calc_details`。人工复核只检查对象覆盖、史料回源、相邻项剥离、规则归属、因子赋值、明细表可重放和结果公式版本，不维护额外中间等级。

当前复核点包括：

1. 检索包对象是否都经过回源、排除或待处理记录；
2. 已入库 `obj_srcs` 是否全部覆盖到对应证据簇的 `material_ids`；
3. 实际计分材料是否进入 `calc_detail.materials`，属性或身份补源是否进入 `supporting_material_ids`；
4. `calc_detail.covered_material_ids`、`scored_material_ids` 和 `supporting_material_ids` 是否能分别解释覆盖、计分和补源关系；
5. 每条计分材料是否有稳定 `obj_key`，并按同一对象完成同向去重；
6. 因子标签是否能从本规则文档或证据簇公式文档解析到当前数值；
7. 相邻项材料是否已经剥离，剩余第五项B影响是否对应到具体对象；
8. 修改规则内部乘数后，是否能从 `evd_cluster_calc_details.calc_detail.factor_refs` 重放并更新证据簇、定分结果和明细表。

规则无法抽象化、schema/回源出现错误或计算明细无法解释时，应回到对象链和证据簇修正，不得直接手写人物级分数或单人 override。

## 证据簇公式

第五项B对应 `eval_items.item_code = I5B`。以下公式按 `eval_rules.rule_code` 维护。

当前证据簇公式版本：

```text
evidence_cluster_signal_v3
```

### `talent_discovery` 发现人才

适用：识别、引入、召见、拔擢此前未进入核心视野的人才。

```text
material_score =
  direction_sign
  * discovery_level
  * talent_quality_factor
  * channel_factor
  * attribution_factor
  * source_factor
  * context_factor
```

本规则中，人才质量是最重要的单项参数。`discovery_level` 只判断发现链条是否成立、发现难度有多高；`talent_quality_factor` 判断被发现对象本身的历史能力层级。顶级人才被识别，比普通人才被识别更能说明皇帝的发现能力；但人才质量不能替代发现链条，只有已证明被识别、引入、召见或拔擢进核心视野的对象，才可进入本规则。

`talent_quality_factor` 必须由 `obj_attrs.attr_code = talent_quality` 的属性事实映射而来。该属性应在相关 `obj_srcs` 入库时补齐；计算前若缺失，不得临时决定因子。

`discovery_level`：

| 值 | 口径 |
| --- | --- |
| `0.6` | 只是被动听闻或沿用已有名望。 |
| `0.8` | 接受荐举并纳入视野。 |
| `1.0` | 召见、试用、拔擢链条清楚。 |
| `1.2` | 发现低位、异质、旧敌阵营或被遮蔽的关键人才。 |

`obj_attrs.value_text -> talent_quality_factor`：

| `obj_attrs.value_text` | 因子 | 口径 |
| --- | --- | --- |
| `一般人才` | `0.5` | 只有普通任职或局部能力线索。 |
| `可用人才` | `0.9` | 有明确职能能力或局部贡献。 |
| `重要人才` | `1.3` | 能支撑一条稳定政务、军事、谏议或技术线。 |
| `顶级人才` | `1.8` | 属于一代名臣、名将、核心谏臣或关键制度人才。 |
| `历史级人才` | `2.5` | 对时代格局、国家核心能力或后世评价有显著权重。 |

`channel_factor`：

| 值 | 口径 |
| --- | --- |
| `1.0` | 普通单线发现。 |
| `1.2` | 跨阵营、跨身份、寒门或异质人才通道成立。 |
| `1.5` | 形成可重复的人才发现机制或稳定荐才网络。 |

### `appointment_trust` 任人信任

适用：任用、信任、复用关键人才，并赋予可见职责。任人信任必须判断“信任是否合理”；信任佞臣、错信不适任者或把核心权力交给破坏人才生态的对象，应作为负向材料。

```text
material_score =
  trust_depth
  * object_weight
  * trust_validity
  * continuity_factor
  * attribution_factor
  * source_factor
  * context_factor
```

本规则不先套 `direction_sign`。`trust_validity` 可以为负；若对象明显不适任、佞幸化、破坏公共任用秩序或造成核心人才生态损害，深度信任会放大负向分，而不是生成正向分。

`trust_depth`：

| 值 | 口径 |
| --- | --- |
| `0.7` | 普通任命或名义性信任。 |
| `1.0` | 有实际职责的任用。 |
| `1.2` | 中枢、军政关键岗位或核心职掌。 |
| `1.5` | 托孤、危局、旧敌转用、重大机密或国家级信任。 |

`trust_validity`：

| 值 | 口径 |
| --- | --- |
| `+1.2` | 旧敌、新进、异质人才或高风险岗位仍能任用，且后续证明其公共能力和岗位适格性清楚。 |
| `+1.0` | 常规合理信任。 |
| `+0.3` | 信任事实清楚，但对象适格性、公共能力或结果反馈不足。 |
| `-0.6` | 错信、偏信或亲旧近幸色彩明显，已削弱任用质量。 |
| `-1.5` | 深度信任明显不适任、佞幸化或破坏人才生态的对象。 |
| `-2.0` | 长期信任核心负向对象，并造成系统性任用污染、表达压制或关键人才损害。 |
| `-3.0` | 把核心权力交给直接制造人才安全灾难、授权信用崩坏或大规模排斥称职人才的对象。 |

`continuity_factor`：

| 值 | 口径 |
| --- | --- |
| `0.8` | 短期或后续不明。 |
| `1.0` | 稳定任用。 |
| `1.15` | 长期复用或多阶段持续信任。 |

使用限制：

- 不能把“信任很深”本身算成正向材料；深度只提供乘数规模，正负由 `trust_validity` 决定。
- 亲属、私旧、近幸、宠臣或权相不是自动负证；只有公共能力链条不足、岗位不适格、排挤称职人才或污染任用秩序时，才转为负向。
- 重大事件进入本项时必须绑定具体被信任对象和具体史料事实，不得只用事件名直接给总扣分。

### `delegation` 合理授权

适用：授权专任、权责配置、任将任相、机要托付。合理授权必须看人岗匹配和结果反馈。

```text
material_score =
  authorization_intensity
  * person_post_fit
  * result_feedback
  * attribution_factor
  * source_factor
  * context_factor
```

本规则不先套 `direction_sign`。`result_feedback` 可以为负，若授权给明显不适任对象并造成损害，材料应进入负向授权簇。

`authorization_intensity`：

| 值 | 口径 |
| --- | --- |
| `0.6` | 名义授权或职责不清。 |
| `1.0` | 单一领域的真实授权。 |
| `1.3` | 重大军政事务授权。 |
| `1.6` | 国家级、危局或长期关键授权。 |

`person_post_fit`：

| 值 | 口径 |
| --- | --- |
| `0.5` | 人岗明显不匹配。 |
| `0.8` | 匹配度不明或只是普通称职。 |
| `1.0` | 人岗匹配清楚。 |
| `1.2` | 顶级专长与岗位高度匹配。 |

`result_feedback`：

| 值 | 口径 |
| --- | --- |
| `+1.5` | 重大成功强烈验证授权合理。 |
| `+1.0` | 正常成功或职责履行良好。 |
| `+0.3` | 结果不明，或结果主要属于相邻项，不能充分验证授权。 |
| `-0.7` | 效果较差，显示匹配或授权判断有问题。 |
| `-1.5` | 重大错授、长期错用或对人才结构造成明显损害。 |
| `-2.0` | 关键战机撤权、撤授权或权责反转，直接破坏授权信用或核心人才发挥。 |
| `-3.0` | 错授或撤权造成连续性人才安全灾难、关键团队崩坏或大规模后续损害。 |

使用限制：

- 不能把战功、政绩或盛世光环本身计为第五项B收益。
- 结果只能作为 `result_feedback` 的具体履职反馈，且必须同时说明人岗匹配和皇帝归因。
- 只有“授予高位”而匹配和结果都很差时，不得按授权存在记正分。
- 战果、败绩或冤案不能作为抽象总分直接进入本项；必须拆到具体授权、撤权、权责配置及其对象。

### `team_building` 建立团队

适用：形成互补团队、核心幕府、中枢班底、荐才网络或长期人才结构。

```text
positive_signal =
  team_quality_signal
  * role_complementarity_factor
  * long_term_stability_factor

team_quality_signal =
  sqrt(sum(positive_weighted_i^2))
  - sqrt(sum(abs(negative_weighted_i)^2))

weighted_i = talent_quality_factor_i * rank_decay_i
```

`team_quality_signal` 从该皇帝 I5B 对象池的具体人才对象计算。候选来自 `emp_objs` 中的皇帝关联人物对象，并要求已有 `obj_attrs.talent_quality`；不再要求对象另有 `team_building` 专属 `obj_srcs`。群体、机制或事件对象不作为单个人才进入排序。人才层级必须来自 `obj_attrs.talent_quality`，不得在证据簇计算时临场补写。

`talent_quality_factor`：

| 值 | 口径 |
| --- | --- |
| `2.00` | 历史级人才。 |
| `1.35` | 顶级人才。 |
| `1.00` | 重要人才。 |
| `0.55` | 可用人才。 |
| `0.55` | 一般人才。 |
| `-0.55` | 佞臣。 |
| `-1.35` | 大佞臣。 |
| `-2.00` | 历史级佞臣。 |

`rank_decay` 按 `abs(talent_quality_factor)` 从高到低排序后自动应用：

| 排序 | 衰减 |
| --- | --- |
| 第 1 位 | `1.00` |
| 第 2 位 | `0.90` |
| 第 3 位 | `0.80` |
| 第 4-6 位 | `0.45` |
| 第 7 位以后 | `0.25` |

`role_complementarity_factor`：

| 值 | 口径 |
| --- | --- |
| `0.85` | 同质化明显。 |
| `1.00` | 常规互补。 |
| `1.15` | 文武、谋政、执行、反馈等互补清楚。 |
| `1.30` | 多类型高质量人才高度互补。 |

`long_term_stability_factor`：

| 值 | 口径 |
| --- | --- |
| `0.80` | 零散、短期、临时组合。 |
| `1.00` | 稳定团队。 |
| `1.15` | 长期稳定核心班底。 |
| `1.30` | 长期可持续人才结构或成熟中枢团队。 |

同一合传、同一荐才链或同一事件中的对象必须先拆成原始对象，再由团队公式聚合团队质量。负向团队破坏材料不进入 `team_quality_signal`，仍必须绑定具体对象和具体史料。

### `tolerate_talent` 容人保全

适用：容谏、保全能臣、维护表达安全、避免滥杀能臣，以及相关负向反转。

正向材料：

```text
positive_material_score =
  feedback_entry
  * expression_safety
  * protection_repair
  * object_weight
  * attribution_factor
  * source_factor
  * context_factor
```

开国/创业皇帝的功臣安全压力可以形成场景基线项，但不得只凭皇帝画像字段直接给分。基线必须同时满足：

```text
founder_retention_baseline =
  founder_pressure
  * retention_signal
```

`founder_retention_baseline` 不算对象，不增加 `independent_object_count`，也不增加 `dimension_count`；只作为正向平方和中的一个公式项：

```text
positive_raw =
  sqrt(founder_retention_baseline^2 + sum(positive_material_score_i ^ 2))
```

若没有功臣整体保全、局部保全或退场安排等对象池材料，`retention_signal = 0`，即使 `emps.is_founder = true` 也不产生基线分。

`feedback_entry`：

| 值 | 口径 |
| --- | --- |
| `0.7` | 单次采纳或个案容忍。 |
| `1.5` | 多次谏诤、犯颜、纠错仍能保留。 |
| `2.0` | 反馈入口制度化，或谏臣能进入中枢议政链条。 |

`expression_safety`：

| 值 | 口径 |
| --- | --- |
| `0.8` | 能容忍但气氛紧张或依赖个案恩免。 |
| `1.0` | 表达安全基本稳定。 |
| `1.2` | 明确保护、保全或鼓励高质量反馈。 |

`protection_repair`：

| 值 | 口径 |
| --- | --- |
| `1.0` | 无特殊补救。 |
| `1.1` | 有恢复、平反、复碑、复官等补救。 |
| `1.2` | 主动保护人才安全或修复授权信用。 |

`founder_pressure`：

| 值 | 口径 |
| --- | --- |
| `0.0` | 非开国/非创业皇帝。 |
| `0.6` | 开国/创业皇帝，但权力来源不主要来自军功、起兵或创业军政集团。 |
| `1.2` | 开国/中兴/创业皇帝，且 `power_origin` 含军功、开国核心，或 `succession_mode` 含起兵、中兴。 |

`retention_signal`：

| 值 | 口径 |
| --- | --- |
| `0.0` | 对象池没有功臣保全、功臣安置、退场安排或授权信用修复材料。 |
| `1.0` | 有个体或局部高风险功臣保全、退场安排、授权信用修复材料。 |
| `1.25` | 有功臣集团整体保全、封功臣、罢兵就国、择任职事等群体性安置材料。 |

负向材料：

```text
negative_material_score =
  - disposition_severity
  * object_weight
  * spillover_factor
  * certainty_factor
  * attribution_factor
  * source_factor
  * context_factor
```

`disposition_severity`：

| 值 | 口径 |
| --- | --- |
| `0.6` | 象征性信用撤销或轻处分。 |
| `1.0` | 贬黜、压制、表达入口受损。 |
| `1.5` | 处死、重罚或严重人才安全事件。 |
| `3.0` | 大规模牵连、系统清洗或长期人才生态破坏。 |
| `4.0` | 针对核心能臣、储备或继承人才、功臣集团、表达对象造成灾难级安全破坏，并有具体连坐或处置对象。 |

`spillover_factor`：

| 值 | 口径 |
| --- | --- |
| `0.7` | 个案事实清楚且主要属于政权安全、司法或相邻项。 |
| `1.0` | 有争议、反转、追悔或表达安全剩余影响。 |
| `1.5` | 形成寒蝉、授权信用破裂或人才安全预期下降。 |
| `4.0` | 系统性外溢到人才生态，或造成跨群体连坐、表达压制预期。 |

`certainty_factor` 只表示事实链确定度，不表示处置是否有争议。事实越确定，负向绝对值越高；事实链不完整则降权。处置正当性争议、追悔、反转或表达安全剩余影响，放在 `spillover_factor` 或 `context_factor` 中处理。

`certainty_factor`：

| 值 | 口径 |
| --- | --- |
| `0.7` | 事实链不完整、来源不足或关键事实存疑。 |
| `1.0` | 标准史源事件链清楚。 |
| `1.15` | 多源互证或反复出现。 |

确有谋反或政权安全链条的处置，不得机械计为第五项B负向分；只有剥离相邻项后仍存在表达寒蝉、能臣安全或授权信用损害，才保留本规则负向分。

重大事件可以跨多个 `rule` 扣分，但每个 `rule` 必须绑定本规则维度下的具体对象、具体史料和具体后果。不得用“巫蛊之祸”“岳飞案”等抽象事件名直接给总扣分；例如巫蛊链条应分别拆成刘据、卫氏等人才安全，江充等错信和近幸污染，司马迁等表达安全损害。

### `anti_nepotism` 避免任人唯亲

适用：抑制亲旧、近幸、外戚、宦官、宠臣或小圈子对核心任免的污染；也适用于公开择才、制度化选任、跨身份用人等正向材料。

正向材料：

```text
positive_material_score =
  selection_openness
  * institutionalization
  * office_weight
  * attribution_factor
  * source_factor
  * context_factor
```

`selection_openness`：

| 值 | 口径 |
| --- | --- |
| `0.7` | 个案中能避免明显私旧干扰。 |
| `1.0` | 以能力、职掌或公议为主要任用依据。 |
| `1.2` | 跨宗族、跨身份、跨阵营或破格公开择才。 |
| `1.4` | 制度化、长期化地压制任人唯亲。 |

`institutionalization`：

| 值 | 口径 |
| --- | --- |
| `0.8` | 单次事件。 |
| `1.0` | 多次稳定做法。 |
| `1.2` | 形成制度、规则或可持续选任机制。 |

`office_weight`：

| 值 | 口径 |
| --- | --- |
| `0.8` | 普通岗位。 |
| `1.0` | 重要岗位。 |
| `1.2` | 中枢、军政或继承相关关键岗位。 |

负向材料：

```text
negative_material_score =
  - favoritism_intensity
  * office_weight
  * displacement_harm
  * attribution_factor
  * source_factor
  * context_factor
```

`favoritism_intensity`：

| 值 | 口径 |
| --- | --- |
| `0.7` | 亲旧、私人关系或近幸色彩明显。 |
| `1.0` | 明显以私关系任用不称职对象。 |
| `1.4` | 近幸、外戚、宦官或宠臣持续干预核心任免。 |
| `1.8` | 小圈子、裙带或私人集团系统性污染用人秩序。 |

`displacement_harm`：

| 值 | 口径 |
| --- | --- |
| `0.7` | 损害不明或主要是道德观感。 |
| `1.0` | 排挤称职人才或扰乱关键岗位。 |
| `1.35` | 损害团队结构、政策执行或表达安全。 |
| `1.70` | 形成长期制度性任用污染。 |

## 证据簇到正式定分公式

本节规定 `I5B` 从 `evd_clusters` 生成 `emp_item_results` 的当前公式。证据簇计算本身见 [`../../证据规则/证据簇计算公式.md`](../../证据规则/证据簇计算公式.md)；本节只处理子项正式分值和 V3.2 档位。

当前公式版本：

```text
item_result_formula_i5b_v6
```

当前执行流程：

1. 选定一个皇帝与 `I5B` 子项，定位 `emps.id` 与 `eval_items.item_code = I5B`。
2. 读取 I5B 六个固定 `rule_code` 的证据簇：`talent_discovery`、`appointment_trust`、`delegation`、`team_building`、`tolerate_talent`、`anti_nepotism`。
3. 对每个 `rule_code` 读取 `evd_clusters.positive_signal` 与 `evd_clusters.negative_signal`。
4. 若某个 `rule_code` 没有证据簇，说明该规则当前没有已回源可计入材料；计算时按 `positive_signal = 0`、`negative_signal = 0` 处理，并在 `emp_item_result_calc_details` 或缺口报告记录 `no_material`。
5. 对每个规则分别计算正向响应、负向响应和净效果；正负两侧必须先分别响应，再相减。
6. 按六个规则权重聚合为 `base_core`。
7. 用整体校准公式生成 `base_rate`，再直接裁剪为正式 `score_rate`。
8. 生成 `score_rate`、`score`、`tier` 和 `tier_band`，写入 `emp_item_results`。
9. 将本次规则输入、响应结果、`base_core`、最终分值和公式版本写入 `emp_item_result_calc_details`，用于当前复算、筛选和审查。

落表边界：

- `evd_clusters` 保存原始信号，不保存正式分值，也不保存档位结论。
- `emp_item_results` 保存当前正式子项结果；它是公式输出，不是原始事实源。
- 若修改本节公式，应提升 `item_result_formula_i5b_*` 版本并重算 `emp_item_results`；不应因此改写对象池或史料表。
- 若发现公式输入材料缺漏，应先回到 `obj_srcs`、`obj_attrs` 和 `evd_clusters` 补齐，再重算本表。

输入：

```text
positive_signal(rule)    = evd_clusters.positive_signal
negative_signal(rule)    = evd_clusters.negative_signal
max_score                = 45
```

规则响应函数：

```text
positive_response(signal) =
  5.5 * (1 - exp(-signal / 3.5))

negative_response(signal) =
  9.0 * (1 - exp(-signal / 5.0))

rule_net_effect(rule) =
  positive_response(positive_signal(rule))
  - negative_response(negative_signal(rule))
```

`evd_clusters` 保存的是未封顶原始信号，不再把规则材料提前框死在 `[-4, +4]` 的旧强度层级。定分层只处理边际递减：原始信号越厚，增量越小；正负两侧必须先分别响应后再相减。

v8 使用非对称响应，并调整规则权重。正向响应较 v5 放宽，避免高密度正证过早抹平顶级优势；负向响应上限更高、收敛更慢，使巫蛊、岳飞案等由具体对象拆出的严重负证能在本规则内部形成足够扣分，不再另设规则表严重权重或严重负向补丁。任人信任、合理授权与具体任用结果存在一定交叉，v7 从二者各匀出部分权重给建立团队，提高团队质量聚合对总分的解释力；v8 进一步降低负向响应的收敛程度，将 `negative_response` 调整为 `9.0 * (1 - exp(-signal / 5.0))`。

基础画像：

```text
base_core =
  0.19 * talent_discovery.rule_net_effect
+ 0.19 * appointment_trust.rule_net_effect
+ 0.17 * delegation.rule_net_effect
+ 0.21 * team_building.rule_net_effect
+ 0.18 * tolerate_talent.rule_net_effect
+ 0.06 * anti_nepotism.rule_net_effect
```

基础得分率：

```text
base_rate = 0.50
          + base_core / 7.5
```

这里使用整体线性校准，而不是给高端单独设置折点。`base_core = 2.25` 约进入优秀线，`base_core = 3.00` 约进入历史顶级线，`base_core = 3.45` 约进入历史极限线。这个映射承认各 `rule` 已经在响应函数中完成一次边际递减，定分层不再额外把高材料密度人物压回普通优秀档。

最终得分率：

```text
score_rate = clamp(
  base_rate,
  0.00,
  0.98
)
```

本公式不设置严重负向硬上限，也不在定分层追加事件补丁。负证已经进入各 `rule` 的 `negative_signal`、规则内部材料乘数和 `negative_response`；是否构成更强压档，应回到对应对象、史料、证据簇和规则内部因子调整。

规则表自 v6 起不保存严重性权重字段；严重性由分项规则内部材料因子和 `evd_clusters` 信号表达。

正式分值：

```text
score = max_score * score_rate
```

档位映射沿用评分标准 V3.2：

| 档位 | 得分率 |
| --- | ---: |
| 历史极限 | 96%—98% |
| 历史顶级 | 90%—95% |
| 优秀 | 80%—89% |
| 良好 | 70%—79% |
| 合格 | 60%—69% |
| 一般 | 50%—59% |
| 较差 | 40%—49% |
| 很差 | 30%—39% |
| 极差 | 30%以下 |

公式实现按连续区间判断档位：`0.8956` 仍属“优秀”，`0.5927` 仍属“一般”，不得因百分制整数表述留下小数空档。

`tier_band` 只记录档内位置：`高段`、`正常`、`低段`；不得把“优秀上段”“历史顶级上段”写成正式档位。

## 对象史料上下文使用场景

第五项B对象链遇到以下情况，应在 `src_docs.locator`、`raw_objs.note`、`obj_srcs.note`、`obj_attrs.note` 或证据簇 `calc_detail` 中补充上下文：

- 单句无法判断任用、授权或处置的前因后果；
- 涉及谋反、清洗、追责、恢复评价、表达安全或相邻项剥离；
- 史源只提供身份或属性补源，不应进入正负信号计算；
- 需要解释 `obj_srcs.direction`、规则归属或相邻项剩余影响；
- 需要说明某条史料为何只进入 `supporting_material_ids`，而不进入 `calc_detail.materials`。

上下文说明不得直接用于手写分数或档位。计分只读取对象链、证据簇信号和已登记公式；上下文服务人工审核、回源复核、相邻项切分和计算明细追溯。长上下文字段展示规则引用 `展示与协作/人工阅读型Markdown导出规范.md`，不得在分项规则中另开展示规范。

## 工作流边界

第五项B执行时应先建立或更新人物级 `query_profile`，同步覆盖授权专任、反馈入口、表达安全、人才生态、异质人才整合和相邻项切分。人工审核只做数据质量、史料回源、上下文充分性、相邻项剥离、规则命中和算法版本审查；不得逐人改写公式输入、公式输出、人物级最终档位、人物级最终分数或单人 override。

对象史料必须能直接归入第五项B，或剥离相邻项后仍有第五项B剩余。`evd_clusters` 必须从当前对象链读取材料并完成相邻项切分；同类材料必须按来源、对象和规则归属记录处理方式。重复史源、属性补源和同对象补强材料按对象聚合、`supporting_material_ids` 或对应因子处理；新对象、新维度、反证、反转材料或相邻项切分价值应更新对象链和对应证据簇。

## 分层检索包与对象池构建入口

第五项B对象池构建采用“分层检索包”方法，但检索包本体不长期内嵌在规则文档中。规则文档只保留方法和入口；人物级检索画像进入结构化批次文件，后续扩展到更多人物时按“一人一行 query_profile”追加。

当前首批 29 人基线保存在：

```text
data/query_profile_batches/i5b_layered_retrieval_profiles_20260630.jsonl
```

每条人物级检索画像应至少包含：

- `source_targets`：本纪、列传、实录、通鉴等回源入口；
- `object_layers`：核心正向对象、补强对象、负向/反转对象、相邻项剥离对象；
- `query_bundles`：可执行检索入口，不是证据结论；
- `expected_lane_outcomes`：预期归 lane 和切分方向，不替代回源后的对象处理状态。

执行时先按对象层级回源，逐个对象写明 `source_verified_objectized`、`source_verified_pending_object_import`、`lead_needs_source_review`、`adjacent_only`、`excluded_with_reason` 或 `no_stable_object` 等处理结论；只有已回源且完成相邻项切分的对象，才允许进入后续证据簇或结果重算流程。

后续追加人物、其他批次或同方法生成的补充检索报告时，不新增第五项B专用规则文档；优先追加结构化 query_profile 批次文件，必要时再由脚本导出人工阅读型 Markdown。

## 禁止事项

- 不得用第五项B规则覆盖其他项。
- 不得把政策收益、军事战果、私德评价或制度控制直接算作用人与授权。
- 不得绕过已登记公式和回源数据直接写入最终档位、最终分数或排名。
- 不得为第五项B再新增专用分项规则文档或子目录。
- 不得复制通用证据、数据或展示规则长文；应通过链接引用。
