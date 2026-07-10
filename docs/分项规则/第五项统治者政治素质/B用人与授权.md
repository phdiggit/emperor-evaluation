# 第五项B 用人与授权计分规则

本文规定第五项B“用人与授权”五个 `rule_code` 的材料计分公式、材料信号映射、因子档位和总分层权重。五个 `rule_code` 固定为：

```text
talent_discovery
appointment_delegation
team_building
tolerate_talent
anti_nepotism
```

## 机器消费摘要

抓包端只需要识别候选事实，不直接判定因子档位或正式入分。推荐把候选事实抽成以下稳定字段：

```json
{
  "personnel_profile": {
    "person": "人才或用人对象",
    "person_role": "岗位、任务、身份或团队角色",
    "talent_quality": "ordinary | usable | important | top | historic | negative",
    "action_type": "discover | appoint | delegate | reuse | build_team | tolerate | protect | select_openly | favor_private",
    "appointment_or_authorization": "任用、授权、复用或托付事实",
    "feedback_or_result": "履职结果、复用反馈、损害或治理后果",
    "team_function": "decision | administration | military | correction | resource | other",
    "selection_channel": "荐举、公开选任、破格拔擢、亲旧近幸、外戚宦官等渠道",
    "same_event_chain": true
  }
}
```

候选路由先按“用人行为重心”分流：

| `rule_code` | 快速路由口径 |
| --- | --- |
| `talent_discovery` | 识别、引入、召见、试用或拔擢此前未进入核心视野的人才。 |
| `appointment_delegation` | 把具体人才放到岗位、任务、权责链或长期托付关系中，并可见适配反馈。 |
| `team_building` | 皇帝对象池整体人才结构、功能互补、核心班底和长期团队质量。 |
| `tolerate_talent` | 容谏、保全能臣、维护表达安全、修复授权信用，或对应负向破坏。 |
| `anti_nepotism` | 抑制亲旧、近幸、外戚、宦官、宠臣、小圈子对任免的污染，或公开择才。 |

factorization prompt 只注入当前 rule 的因子表和短边界：

- `team_building` 使用对象池聚合，不以单条 claim 临场给团队成员定级。
- 其余 rule 使用单材料公式、材料层封顶和正负信号聚合。
- 任用、授权、复用、信任和结果反馈在 `appointment_delegation` 内一次判读；不得拆成多个旧口径重复入分。
- 相邻项边界只注入与当前候选最可能混淆的二至三条；不得把本文件全文作为常规 prompt 上下文。

数据链硬边界：

- 第五项B当前正式计分链只认已回源对象、史源、规则、结构化因子和计算明细；不得直接手写人物级分数或单人 override。
- `raw_objs` 保持原始对象粒度，不能合并加工；每个 `raw_objs` 至少有一条 `obj_srcs` 史料链，`talent_quality` 等对象属性必须来自 `obj_attrs`。
- 第五项B当前计算链为 `obj_srcs` / `obj_attrs` → `evd_cluster_calc_details.calc_detail`；规则承载对象另由 `rule_evidence_units` / `rule_evidence_unit_members` / `fact_relations` 表达。
- `calc_detail.covered_material_ids`、`scored_material_ids` 和 `supporting_material_ids` 必须能回到源材料；`query_profiles` / `data/query_profile_batches/**`、`search_logs`、`source_review_log` 只记录召回、抓包和复核过程。
- 正向、负向、相邻项 query lanes 的覆盖、对象化、入库、未决和排除理由必须可审计；本公式不设置严重负向硬上限。

## 一、材料信号尺度

单条材料先计算 `raw_material_score`，再进入材料层封顶：

```text
material_score = clamp(raw_material_score, -4.0, +4.0)
```

单条材料有效区间为 `[-4.0, +4.0]`。

材料强度解释：

| abs(material_score) | 解释 |
| ---: | --- |
| `0.3 - 0.8` | 弱证、边界证、辅助性材料。 |
| `0.8 - 1.6` | 常规有效材料。 |
| `1.6 - 2.8` | 强材料。 |
| `2.8 - 4.0` | 极强材料。 |

除 `team_building` 外，同一 `claim_id + object_id + side` 下拆出的多个 role binding，默认只保留一条最能代表本 rule 的 `score` 材料；其余材料若有上下文价值，记为 `supporting_only`。

## 二、证据修正因子

三项证据修正因子适用于除 `team_building` 聚合内置对象排序外的材料公式：

```text
evidence_factor =
  attribution_factor
  * source_factor
  * context_factor
```

计算时对合乘结果封顶：

```text
evidence_factor = clamp(evidence_factor, 0.45, 1.25)
```

### `attribution_factor`

| 值 | 口径 |
| ---: | --- |
| `0.8` | 间接归因；通过臣僚荐举、既有制度链、群体决策或后见整理才能归因于皇帝。 |
| `1.0` | 皇帝决策链清楚；材料可见皇帝任用、授权、采纳、处置或保全动作。 |
| `1.1` | 皇帝亲自判断清楚，且存在逆阻力、反常规取舍或关键取舍压力。 |

### `source_factor`

| 值 | 口径 |
| ---: | --- |
| `0.75` | 史源链较弱、事实链压缩、片段性强，或需要较多旁证才能支撑。 |
| `1.0` | 标准史源，事实链清楚。 |
| `1.1` | 标准史源且关键事实链完整、对象和动作均明确。 |

### `context_factor`

| 值 | 口径 |
| ---: | --- |
| `0.7` | 已满足本 rule 的适用条件，但事实链较弱或上下文不完整。 |
| `1.0` | 本 rule 语境成立，事实和对象关系清楚。 |
| `1.1` | 本 rule 语境强，材料直接展示该 rule 的核心机制。 |

## 三、`talent_discovery` 发现人才

适用：识别、引入、召见、试用或拔擢此前未进入核心视野的人才。

计分承载对象：被发现、被推荐、被识别、被引入核心视野或被破格拔擢的人才本人。

```text
raw_material_score =
  direction_sign
  * discovery_level
  * talent_quality_factor
  * channel_factor
  * evidence_factor
```

`direction_sign` 默认为 `+1`；负向材料只在错失、压制或拒绝关键人才发现机会时使用 `-1`。

“提拔、拔擢、擢用”可作为发现人才的代理信号，但必须同时显示对象此前低位、被埋没、未充分显名、异质来源、旧阵营，或存在破格识别、试用、荐举链条。普通升迁、已知重臣任命或单纯授权办事，不得仅凭任官事实计入发现人才。

TODO：待更多皇帝样本跑完后复核“仅有提拔、擢用、任命事实，缺少显性发现信号”的材料是否需要放宽；若多数样本 `talent_discovery` 原始信号系统性偏低，再讨论是否调整本段口径。

### `discovery_level`

| 值 | 口径 |
| ---: | --- |
| `0.6` | 仅沿用已有名望或被动听闻，发现动作弱。 |
| `0.8` | 接受荐举、引入视野，但主要发现动作来自他人推荐。 |
| `1.0` | 皇帝形成召见、试用、任用或拔擢链条，发现动作可归因。 |
| `1.2` | 对低位、被遮蔽、旧阵营、异质身份等高识别难度对象，完成破格发现并进入核心任用链。 |

### `talent_quality_factor`

`talent_quality_factor` 必须来自对象属性 `talent_quality`，不得在材料计分时临场定级。

| 人才层级 | 因子 |
| --- | ---: |
| 普通人才 | `0.6` |
| 可用人才 | `0.9` |
| 重要人才 | `1.15` |
| 顶级人才 | `1.45` |
| 历史级人才 | `1.8` |

### `channel_factor`

| 值 | 口径 |
| ---: | --- |
| `1.0` | 普通单线发现、单次荐举或个案拔擢。 |
| `1.1` | 跨阵营、跨身份、寒门或异质人才通道成立。 |
| `1.2` | 形成可重复的人才发现机制或稳定荐才网络。 |

## 四、`appointment_delegation` 任用授权质量

适用：任用、信任、复用关键人才，或授予其岗位、任务、军政权责、机要职责。任用授权质量评价的是“皇帝是否把合适的人放到合适的位置、任务或权责链上，并产生合理后果”。

计分承载对象：被任用、被信任、被复用、被授权或被长期托付的具体人物及其岗位、任务或权责链。

```text
raw_material_score =
  appointment_importance
  * appointment_effect
  * continuity_factor
  * evidence_factor
```

同一条事实链中，“任命某人”“授予某项职责”“该职责结果如何”只在本规则内形成一条入分判断，不拆入多个 rule 重复计分。若同一 claim/object 拆出多个 role binding，默认只保留最能代表任用授权质量的一条 `score`。

`appointment_effect` 可以为负；对象明显不适任、佞幸化、破坏公共任用秩序，或授权安排直接造成军政治理损害时，任用授权重要性会放大负向分。

撤权、诛废、猜忌、清洗、功臣不保等处置性材料，本身不作为本规则的结果反馈；只有材料证明其是某次任用授权安排的直接履职后果时，才计入 `appointment_effect`。

### `appointment_importance`

| 值 | 口径 |
| ---: | --- |
| `0.6` | 名义任命、名义授权、职责不清或职责较轻。 |
| `1.0` | 有实际职责的任用、信任或单一领域真实授权。 |
| `1.25` | 中枢、军政关键岗位、核心职掌或重大军政事务授权。 |
| `1.4` | 托孤、危局、旧敌转用、重大机密、国家级或长期关键任用授权。 |

### `appointment_effect`

| 值 | 口径 |
| ---: | --- |
| `+1.5` | 高风险、关键岗位或高强度授权高度适配，并产生重大成功或强烈体现任用授权合理。 |
| `+1.0` | 人岗匹配成立，有明确任后表现、职责履行、政策、军事、行政成果或持续复用反馈。 |
| `+0.4` | 任用、信任、授权关系存在，但只见任官、亲近、名望、任务交付或弱反馈，缺少充分结果或岗位适配证明。 |
| `-0.8` | 错任、错信、偏信、弱匹配或授权后结果较差，显示任用授权判断有问题。 |
| `-1.8` | 深度任用授权明显不适任对象，并直接造成重大军政失败、治理损害、关键职责失守或人才生态损害。 |
| `-2.6` | 长期或国家级错误任用授权造成连续性、结构性、大规模后续损害，或系统性任用污染、表达压制、关键人才损害。 |

### `continuity_factor`

| 值 | 口径 |
| ---: | --- |
| `0.85` | 短期、单次、临时任用授权，或未形成持续复用。 |
| `1.0` | 稳定任用授权。 |
| `1.15` | 长期复用、多阶段持续信任，或同一对象跨阶段承担关键职责。 |

## 五、`team_building` 建立团队

适用：形成互补团队、核心幕府、中枢班底、荐才网络或长期人才结构。

计分承载对象：该皇帝对象池中的全部具体人才对象；团队质量由对象池聚合，不由单条材料临场定级。不得因对象不是核心官职、核心将相或长期班底成员而在候选阶段排除；是否弱贡献、负贡献或仅作上下文，由对象属性、团队聚合排序和 `target_action` 决定。

```text
object_score_i =
  talent_quality_factor_i
  * role_complementarity_factor
  * long_term_stability_factor

positive_signal =
  sum(object_score_i for positive team objects)

negative_signal =
  sum(abs(object_score_i) for negative team objects)

team_raw_net =
  positive_signal - negative_signal
```

`team_raw_net` 直接作为本 rule 的原始净信号输出，不在 rule 层做响应函数、二次封顶或最终得分映射。

`team_building` 以对象池中的人才对象为计分单元。每个对象在同一目标皇帝下只贡献一次团队信号；多条史料只用于支撑该对象画像、身份和人才层级，不因多条 claim 形成重复入分。若数据链意外产生同一对象多条 `score`，只保留最能代表该对象团队贡献的一条，其余不得叠分。

### `talent_quality_factor`

| 人才层级 | 因子 |
| --- | ---: |
| 历史级人才 | `1.6` |
| 顶级人才 | `1.2` |
| 重要人才 | `0.9` |
| 可用人才 | `0.55` |
| 普通人才 | `0.35` |
| 佞臣 | `-0.6` |
| 大佞臣 | `-1.1` |
| 历史级佞臣 | `-1.7` |

### `role_complementarity_factor`

| 值 | 口径 |
| ---: | --- |
| `0.9` | 功能同质化明显，主要集中在单一文官、军功、近幸或地方执行序列。 |
| `1.0` | 常规互补，至少两个功能面有称职对象。 |
| `1.1` | 较强互补，至少三个功能面有重要及以上对象承担。 |
| `1.2` | 高度互补，决策、行政资源、军事安全、纠偏整合四个功能面均有重要及以上对象支撑。 |

### `long_term_stability_factor`

| 值 | 口径 |
| ---: | --- |
| `0.85` | 零散、短期、临时组合。 |
| `1.0` | 稳定团队。 |
| `1.1` | 长期稳定核心班底。 |
| `1.2` | 长期可持续人才结构或成熟中枢团队。 |

## 六、`tolerate_talent` 容人保全

适用：容谏、保全能臣、维护表达安全、避免滥杀能臣，以及相关负向反转。

正向承载对象：被容纳、被保全、表达安全被保护或授权信用被修复的具体人才。

负向承载对象：被处置、受损、表达安全受压或人才安全受损的具体人才。

### 正向公式

```text
raw_material_score =
  feedback_entry
  * expression_safety
  * protection_repair
  * evidence_factor
```

### 负向公式

```text
raw_material_score =
  - handling_severity
  * target_fault_factor
  * evidence_factor
```

### `feedback_entry`

| 值 | 口径 |
| ---: | --- |
| `0.7` | 单次采纳或个案容忍。 |
| `1.3` | 多次谏诤、犯颜、纠错仍能保留。 |
| `1.7` | 反馈入口制度化，或谏臣能进入中枢议政链条。 |

### `expression_safety`

| 值 | 口径 |
| ---: | --- |
| `0.8` | 能容忍但气氛紧张或依赖个案恩免。 |
| `1.0` | 表达安全基本稳定。 |
| `1.15` | 明确保护、保全或鼓励高质量反馈。 |

### `protection_repair`

| 值 | 口径 |
| ---: | --- |
| `1.0` | 无特殊补救。 |
| `1.1` | 有恢复、平反、复碑、复官等补救。 |
| `1.15` | 主动保护人才安全或修复授权信用。 |

### `handling_severity`

| 值 | 口径 |
| ---: | --- |
| `0.6` | 象征性信用撤销或轻处分。 |
| `1.2` | 贬黜、压制、表达入口受损。 |
| `1.8` | 下狱、重罚、处死或严重人才安全事件。 |
| `2.6` | 大规模牵连、系统清洗或长期人才生态破坏。 |
| `3.2` | 针对核心能臣、储备或继承人才、功臣集团、表达对象造成灾难级安全破坏。 |

### `target_fault_factor`

| 值 | 口径 |
| ---: | --- |
| `1.5` | 无故构陷、冤杀，或因谏言、表达、纠错而受害。 |
| `1.2` | 过错轻微，处置明显不相称。 |
| `0.9` | 过错边界争议大，或嫌疑明显但未坐实。 |
| `0.5` | 违法乱纪、重大过错或危险行为基本成立，但处置仍显过重。 |
| `0.2` | 谋反、叛乱或严重危害基本坐实，但仍保留极弱的人才安全、表达安全或授权信用残余。 |

## 七、`anti_nepotism` 避免任人唯亲

适用：抑制亲旧、近幸、外戚、宦官、宠臣或小圈子对核心任免的污染；也适用于公开择才、制度化选任、跨身份用人等正向材料。

正向承载对象：被公开、公议、制度化或跨身份任用的具体对象或岗位任用链。

负向承载对象：造成任用污染、排挤称职人才或扰乱关键岗位的小圈子、近幸、亲旧、外戚、宦官、宠臣或被其占据的岗位链。

### 正向公式

```text
raw_material_score =
  selection_openness
  * institutionalization
  * office_weight
  * evidence_factor
```

### 负向公式

```text
raw_material_score =
  - favoritism_intensity
  * office_weight
  * displacement_harm
  * evidence_factor
```

### `selection_openness`

| 值 | 口径 |
| ---: | --- |
| `0.7` | 个案中能避免明显私旧干扰。 |
| `1.0` | 以能力、职掌或公议为主要任用依据。 |
| `1.25` | 跨宗族、跨身份、跨阵营或破格公开择才。 |
| `1.4` | 制度化、长期化地压制任人唯亲。 |

### `institutionalization`

| 值 | 口径 |
| ---: | --- |
| `0.8` | 单次事件。 |
| `1.0` | 多次稳定做法。 |
| `1.15` | 形成制度、规则或可持续选任机制。 |

### `office_weight`

| 值 | 口径 |
| ---: | --- |
| `0.8` | 普通岗位。 |
| `1.0` | 重要岗位。 |
| `1.15` | 中枢、军政或继承相关关键岗位。 |

### `favoritism_intensity`

| 值 | 口径 |
| ---: | --- |
| `0.7` | 亲旧、私人关系或近幸色彩明显。 |
| `1.1` | 明显以私关系任用不称职对象。 |
| `1.5` | 近幸、外戚、宦官或宠臣持续干预核心任免。 |
| `2.0` | 小圈子、裙带或私人集团系统性污染用人秩序。 |

### `displacement_harm`

| 值 | 口径 |
| ---: | --- |
| `0.7` | 未见实际排挤称职人才，主要停留在道德观感或任用观感。 |
| `1.0` | 排挤称职人才或扰乱关键岗位。 |
| `1.4` | 损害团队结构、政策执行或表达安全。 |
| `2.0` | 形成长期制度性任用污染。 |

## 八、规则原始信号聚合

各 rule 的材料按正负两侧分别聚合，再直接相减，得到规则原始净信号。规则层不做区间映射、响应函数、二次封顶或人物档位重映射。

除 `team_building` 为对象池单元、每个对象只贡献一次外，普通 claim-driven rule 先在同一对象内做重复材料衰减：

```text
object_side_signal =
  strongest_material_score
  + 0.35 * sum(other_material_scores)
```

同一对象内的聚合值不超过单材料最强值的 `1.5` 倍，也不超过单对象上限。随后 rule 侧不再做压缩，只做对象间线性求和：

```text
positive_signal(rule) =
  sum(object_side_signal_j for positive objects)

negative_signal(rule) =
  sum(object_side_signal_j for negative objects)

rule_raw_net(rule) =
  positive_signal(rule) - negative_signal(rule)
```

`rule_raw_net` 是动态计分前的原始数据。它只表达本 rule 下已回源材料的正负净信号，不直接等同于最终得分率、最终档位或历史极限。

某个 `rule_code` 没有证据簇时，按：

```text
positive_signal = 0
negative_signal = 0
rule_raw_net = 0
```

## 九、动态计分输入权重

输入：

```text
rule_raw_net(rule) = positive_signal(rule) - negative_signal(rule)
max_score          = 45
```

批量动态计分前，先保留各 rule 的 `positive_signal`、`negative_signal` 和 `rule_raw_net`。若需要形成单项综合原始信号，可使用以下权重：

```text
weighted_raw_signal =
  0.19 * talent_discovery.rule_raw_net
+ 0.36 * appointment_delegation.rule_raw_net
+ 0.21 * team_building.rule_raw_net
+ 0.18 * tolerate_talent.rule_raw_net
+ 0.06 * anti_nepotism.rule_raw_net
```

最终 `score_rate` 和 `score` 不在单个皇帝完成时按固定公式即时生成。应在一批目标的原始信号全部算完后，以标杆人物、分布形态、合理区分度和评分总则档位为约束，进行动态区间映射。评分总则中的历史极限、历史顶级、优秀等最终得分率档位仍保留在最终解释层，不在 rule 原始信号层重复定档。

## 十、跨项复用边界

本章只用于人工审核和跨项候选复用，不得作为 candidate 或 factorization prompt 的排他性门禁。每个 rule 必须按自己的“适用”说明独立判断：材料满足当前 rule 时必须保留当前候选并正常计分；即使同一事实也能支持其他 rule 或 item，也不得因此降低 `context_factor`、改成 `supporting_only` 或 `exclude`。

- 与 I5C：I5B 评价用人、授权、团队、容才和反亲私；I5C 评价权力结构是否可控、可约束、可纠偏。任用某人及其授权结果按 I5B rule 独立判断；同一事实涉及权力结构平衡或失控时，可同时保留 I5C 候选。
- 与 I5D：I5D 评价政治品格、待功臣、猜忌滥杀、仁暴取向等价值面；I5B 只在这些行为影响人才识别、任用授权、团队质量、容人保全或任用公正时入分。
- 与 I5E：I5E 评价认知、纳谏、学习、纠错能力；I5B 只评价反馈对象是否作为人才被容纳、保全、任用或进入稳定团队链条。
- 与 I6：I6 评价关键决策质量；I5B 评价关键决策中的用人和授权质量。同一事实满足两边 rule 时分别保留候选，不以“更像决策”排除任用授权结果。
- 与 I3：I3 评价军事边疆结果；I5B 评价将帅发现、任用授权、团队配置和人才保全。军事成果若是同一任用授权链的职责结果，必须计入 `appointment_delegation` 的结果反馈，也可同时作为 I3 候选。

同一材料可以服务多个 rule 或 item，分别按各自规则独立窄验。单个 rule 内仍执行同一 `claim_id + object_id + side` 的 role 去重；跨 rule 或跨 item 不以“语义重叠”为由预先排除符合规则的材料。
