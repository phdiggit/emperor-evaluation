# 第五项 B：用人与授权计分规则（V4）

本文规定第五项 B 五个 `rule_code` 的 V4 统计单元、分类档位、V3 数值投影、材料聚合、项内权重和动态映射边界。

当前状态：V4 已冻结 24 个分类因子的语义；V3 的材料分、规则原始信号、团队人物池和五条 rule 权重已移植为 V4 shadow 计分骨架。最终 `0—45` 分仍须经过版本化批次动态映射；映射快照获批前，`score_rate`、`score` 和 `tier` 必须为空。

```text
talent_discovery
appointment_delegation
team_building
tolerate_talent
anti_nepotism
```

数值事实源为 `config/i5b-scoring-policy.yml`；分类语义事实源为 `config/i5b-factor-semantics.yml`。因子智能体只能输出分类 `option_code`、理由和 lineage，不得看到或输出数值。

## 机器消费摘要

```text
SourcePassage
→ Assertion
→ HistoricalEpisode / AggregateContext / PersonProfileSnapshot
→ RuleEvidenceUnit
→ categorical factor Judgment
→ deterministic V3 numeric projection
→ MaterialContribution / TeamObjectContribution
→ RuleSignalEnvelope
→ WeightedRawEnvelope
→ versioned BatchMappingSnapshot
→ I5B score (0—45)
```

| rule | V4 统计单元 | 数值投影 |
| --- | --- | --- |
| `talent_discovery` | 使用前的独立识才 Episode | 四个分类因子联合投影，并联人物画像与渠道观察。 |
| `appointment_delegation` | 上游冻结 canonical slot | 六个分类因子与 V3 数值表一一对应。 |
| `team_building` | 皇帝—时间窗口人物集合 | 逐人物能力正池与政治风险负池正交聚合。 |
| `tolerate_talent` | 同一对象的反馈—回应—安全—修复链 | 四因子联合投影，并联处置严重度与对象过错。 |
| `anti_nepotism` | Episode 三因子＋AggregateContext 网络因子 | 先区分污染、预防、纠偏，再联合投影。 |

硬边界：

- 每项贡献必须回到 Assertion、passage 和业务统计单元；
- 同一技术性 `claim + canonical person + side` 绑定不得重复入分；
- 同一决策弧、业务收益或损害不得跨 rule 重复结算；
- 不使用 Top-K，不用材料数量硬上限丢弃已接受材料；
- `not_applicable`、`insufficient_evidence`、`insufficient_projection` 都不是零分；
- 无材料的 rule 在 raw envelope 中显式记双零，但不得伪造 cluster；
- V3 主键、旧分数和旧数据库状态不得直接成为 V4 正式结果。

## 一、材料信号尺度

```text
material_score = clamp(raw_material_score, -4.0, +4.0)
```

| `abs(material_score)` | 解释 |
| ---: | --- |
| `0.3—0.8` | 弱证、边界证或辅助材料。 |
| `0.8—1.6` | 常规有效材料。 |
| `1.6—2.8` | 强材料。 |
| `2.8—4.0` | 极强材料。 |

同一 claim 被技术性拆成多个 role binding 时只保留语义最完整的一条；这是去除技术重复，不是删除独立成立的事件。所有通过门禁的独立材料必须进入聚合。

## 二、证据修正因子

除团队人物池外，V3 共用骨架保留为：

```text
evidence_factor = clamp(
  attribution_factor * source_factor * context_factor,
  0.45,
  1.25
)
```

| 因子 | 档位与数值 |
| --- | --- |
| `attribution_factor` | `indirect=.8`；`direct=1.0`；`direct_under_pressure=1.1`。 |
| `source_factor` | `weak_or_compressed=.75`；`standard=1.0`；`complete_direct_chain=1.1`。 |
| `context_factor` | `weak_but_applicable=.7`；`clear=1.0`；`core_mechanism_direct=1.1`。 |

`source_factor` 只由确定性 lineage 生成。其他 rule 没有同名分类因子时，由规则专用 deterministic adapter 从冻结结构观察投影；缺输入即 `insufficient_projection`，不得猜默认值。

## 三、`talent_discovery` 发现人才

适用：在首次实质使用前识别、验证、引入或突破障碍，使此前未进入核心视野的人才转化为实际使用。

V4 分类因子为 `recognition_novelty`、`recognition_basis`、`barrier_crossing`、`conversion_to_use`。

```text
raw_material_score =
  direction_sign
  * discovery_level
  * talent_quality_factor
  * channel_factor
  * evidence_factor
```

| `discovery_level` | 数值 | V4 联合判断口径 |
| --- | ---: | --- |
| `passive_reputation` | `.6` | 主要沿用既有名望，缺少独立验证或转化。 |
| `recommendation_entry` | `.8` | 经荐举进入视野，并形成有限验证或试用。 |
| `attributable_interview_trial_or_appointment` | `1.0` | 皇帝直接观察、面试、试用或实质使用链成立。 |
| `difficult_cross_boundary_discovery` | `1.2` | 低位、异质或跨阵营障碍被突破并完成实质转化。 |

四因子必须联合决定 `discovery_level`，不得各自乘一次。使用后战果不得反向充当使用前识才依据。

人物等级来自版本化 `PersonProfileSnapshot`：`ordinary=.6`、`usable=.9`、`important=1.15`、`top=1.45`、`historic=1.8`。

渠道：单次个案 `1.0`；明确跨身份或跨阵营 `1.1`；跨事件可重复机制 `1.2`。单 Episode 不能单独证明可重复机制。

## 四、`appointment_delegation` 任用授权质量

```text
raw_material_score =
  appointment_importance
  * appointment_effect
  * continuity_factor
  * evidence_factor
```

| 因子 | V4 档位与数值 |
| --- | --- |
| `appointment_importance` | `nominal_or_light=.6`；`real_bounded=1.0`；`major_affairs=1.25`；`critical_national_or_long_term=1.4`。 |
| `appointment_effect` | `weak_feedback=+.4`；`normal_success=+1.0`；`major_success=+1.5`；`poor_result=-.8`；`major_direct_damage=-1.8`；`structural_continuing_damage=-2.6`。 |
| `continuity_factor` | `short_or_one_off=.85`；`stable=1.0`；`long_term_multi_stage=1.15`。 |

重要性只按授权当时责任域判断，后续成果不得反向抬档。一次性档需要明确一次性事实或有界缺失复核；稳定档至少两个可区分观察；多阶段档至少两次可区分授权。

本 rule 使用 V3 已实际运行的 `v3-native-density-decay-20260711` 三层衰减策略，见第八章。

## 五、`team_building` 建立团队

统计单元是冻结的“皇帝—时间窗口—人物集合”，不是单个 claim 或单个人物即时评分。

```text
positive_pool = sum(talent_quality_factor_rank / rank ^ 0.5)

negative_team_contribution =
  negative_talent_severity_value
  * negative_talent_class_relevance

negative_pool = sum(negative_team_contribution_rank / rank ^ 0.5)

positive_signal = positive_pool * role_complementarity_factor * long_term_stability_factor
negative_signal = negative_pool * role_complementarity_factor * long_term_stability_factor
team_raw_net = positive_signal - negative_signal
```

每个 canonical person 在同一窗口只进入一次。人才能力与负面政治风险是正交双轴；风险不得降低人才等级。

跨朝、跨君主人物不拆分全生涯人才等级或持续性成果。人才等级继续复用同一版本化人物画像；是否进入某一皇帝窗口，只在“皇帝—窗口—人物关系”层判断。关系来源固定为 `self_selected`、`inherited_and_retained`、`recalled`、`passive_holdover`，不附加数值系数：前三类只有在窗口内实质履职得到证据确认后进入团队人物池，`passive_holdover` 排除；继承并明确留用者可以进入团队，但不得据此生成该皇帝的 `talent_discovery` 贡献。

全局画像无政治风险标签者不做逐窗风险复核；有风险标签者只有 `exposed_in_window` 才进入当前窗口负池，`not_exposed_after_bounded_review` 不进入，`insufficient_evidence` 失败关闭。后朝风险不得反向处罚前朝窗口。该适用性作为版本化 member assessment overlay 保存，不回改253份人物画像或12个冻结回归窗口。

`frozen_workset_member_set_complete=true` 只声明测试工作集中的成员齐全，不声明历史团队人物名录穷尽。历史团队覆盖必须先冻结实质团队角色纳入门槛，并对全部候选人物完成 `included`、`excluded_not_material_team_role` 或 `insufficient_membership_evidence` 处置。

V3 人物画像只能通过 `eval/v3_person_profile_migration/source_snapshot.json` 的冻结来源包进入迁移。用户已授权其中 typed 人才等级与政治风险为本轮画像事实源；242份合格画像全部保留 v2/v4/v5 原始版本和正交风险轴，另有11名缺失者按同一守门员标准补充定级，V4 共持有253份版本化画像。旧 `P-* / PER-*` 只作 lineage，正式身份统一使用新 `PER-V4-*`。人物能力域不得从人才等级、官职或关键词反推：已有独立人工结论的55份保存明确能力域，其余198份保存空数组表示未评审，并在团队窗口 Gate 中 fail closed。

V3 的 `talent-grade-v2/v4/v5` 分别高度集中于 important、historic、top，不能继续视为统一标尺。V4 以 `talent-grade-v6-calibration-v1` 保存校准层：原档位和版本不可覆盖，消费方从 `person_profile_current.effective_talent_grade` 读取当前有效档位。top 必须至少有两个独立且结果明确的重大成果簇，其中至少一个达到国家级、基础制度级或独立决定性战区级，并通过高个人归属和同时代第一梯队对照；同一职责链、共同参与、同类个案、官位与声望不得拆簇。首轮94人复核将31个原top降为important，并将张苍 historic 调为 top、汤思退 important 调为 usable；分布只作漂移告警，不作配额。

`talent-grade-v7-important-calibration-v1` 对V6后的157个important做双向复核。important 的主路径要求至少一个已实施、结果明确、个人归属中高，且达到中央关键政策、区域治理、重大军事行动、重要制度或领域代表性尺度的成果簇；替代路径要求至少两个相互独立且结果明确的中型成果簇。只证明稳定胜任、局部或辅助成果者归usable；连稳定正向能力证据也不足才归ordinary。满足既有V6 top硬门者允许由important升top。该轮周勃、曹仁升top，36人降usable，119人保留important；政治风险轴不参与人才扣档，分布不作为配额。

`talent-grade-v8-final-calibration-v1` 收口historic、usable与ordinary。军事成果在计簇前必须先过含金量门：对外战争结合对手当时国力、动员能力、战略威胁与战争难度，弱小、崩解或残余政权不得仅凭“灭国”计重大或时代级；对内战争结合兵力与地域规模、持续时间、对国家存续或统一的威胁及战后战略后果，小规模叛乱不得自动计重大。多个低含金量战果不能拼成historic。historic仍以三个独立时代塑造成果簇为主路径；另设极窄文明基础单簇路径，仅适用于由个人高度独占地完成、跨数百年持续成为基础范式的制度或作品体系，不适用于一般名著、声望或集体官修。该轮13个historic保留6、降top6、降important1；低档复核使3人升important、2人由ordinary升usable，top上升historic候选为0。最终分布为historic6、top66、important123、usable55、ordinary3。

`talent-grade-v9-high-tier-calibration-v1` 以不再细分微因子的冻结标准，重新复核V8后全部6名historic和66名top，并对72人逐项做独立对抗复核。军事看战功含金量、按任务重要性加权的胜率与败仗成本、军事思想或组织遗产；文治看已兑现的治世成果或制度建设、持续兑现和思想流传；文化看当朝领域地位、后世影响及原创范式价值；全能型只计算相互独立领域达到的实际高度。historic须先有时代或文明塑造高度，再满足重复高风险兑现、基础性长期遗产或多个独立top领域之一；top须有国家级或领域第一梯队成果，并有稳定兑现、第二重大成果或重要方法遗产之一。单一文明级作品不自动晋级，必须与其他文化类别横向比较原创性、作者归属和跨时代范式影响。最终6名historic全部保留，卫青、张良、曹参、李斯、李靖、班超、陈群由top升historic，其余59名top保留；有效分布为historic13、top59、important123、usable55、ordinary3。司马迁保留historic的依据是《史记》由个人完成的纪传体通史原创范式及其跨史学、文学的长期基础影响，而不是正史名位或单部名作本身。李靖与徐达按同一军事标尺均为historic：徐达的岭北重败计入成本，李靖的平萧铣、灭东突厥与平吐谷浑按对手强度和战略结果计入重复兑现。

`talent-grade-v10-targeted-correction-v1` 不改写V9，只追加两人纠偏层。陈群由historic调回top：九品官人法的个人归属和长期影响足以制度领域top，但单一制度的寿命不能替代净治理效果；制度型historic须达到国家底层结构重构，并具有跨模块兑现或长期净正向塑形，陈群不足以越过商鞅、李斯式守门员。苏定方由top升historic：灭西突厥和灭百济分别属于时代级与国家级跨战区完整兑现，已满足V9的时代塑造加重复高风险兑现，不要求第三项同高度成果或独立军事思想遗产。征高句丽先破敌、夺营并围平壤，最终未克只降低任务完成率，不得记为战场败仗。当前有效historic名单相应以苏定方替换陈群，总分布仍为historic13、top59、important123、usable55、ordinary3。

持久化事实源为 PostgreSQL `v4_person_profile.person_profile_snapshots` 与 `v4_person_profile.ruler_team_window_snapshots`；成员通过 `ruler_team_window_members` 绑定具体画像版本。JSON 迁移包只是可重建视图，不替代数据库状态。

人才正池：`ordinary=.35`、`usable=.55`、`important=.9`、`top=1.2`、`historic=1.6`。

负面严重度：`minor=.20`、`material=.45`、`major=.80`、`historic=1.20`。

负面类型系数：`sycophant=.80`、`favorite=.70`、`power_abuser=1.00`、`framer=1.00`、`extractive_official=.90`、`cruel_official=.90`、`incompetent_harmful=1.00`、`traitorous_actor=.80`、`mixed_or_disputed=.50`。映射版本为 `negative-profile-team-v1`。

结构映射：

| V4 因子 | 档位与数值/职责 |
| --- | --- |
| `functional_complementarity` | `homogeneous=.9`；`ordinary_two=1.0`；`strong_three=1.1`；`balanced_four=1.2`。 |
| `continuity_structure` | `fragmented/forced_turnover_collapse/stable_but_narrow=.85`；`stable_window=1.0`；`managed_turnover=1.1`；`durable_multi_stage=1.2`。 |
| `core_role_coverage` | 验证互补档，不另乘一次。 |
| `talent_depth` | 正池审计摘要，不另乘一次。 |
| `negative_profile_exposure` | 负池审计摘要，不另乘一次。 |
| `confidant_dependency` | 当前只作诊断，不进入 V3 原始公式。 |

## 六、`tolerate_talent` 容人保全

V4 分类因子为 `feedback_reception`、`talent_safety`、`professional_autonomy`、`conflict_repair_continuity`。

```text
positive_raw_material_score =
  feedback_entry * expression_safety * protection_repair * evidence_factor

negative_raw_material_score =
  - handling_severity * target_fault_factor * evidence_factor
```

正向数值：

- `feedback_entry`：单次采纳或容忍 `.7`；多次反馈且仍被保留 `1.0`；跨阶段持续反馈 `1.3`；高密度跨领域长期犯颜 `1.7`；反馈入口制度化 `2.0`；
- `expression_safety`：紧张或依赖个案恩免 `.8`；基本安全 `1.0`；主动保护或鼓励 `1.15`；
- `protection_repair`：无特殊补救 `1.0`；恢复、平反或复官 `1.1`；主动保护或完整修复信用 `1.15`。

负向数值：

- `handling_severity`：轻处分 `.6`；贬黜或压制 `1.2`；严重非永久伤害 `1.8`；处死或逼令自尽 `2.6`；集团或系统清洗 `3.2`；
- `target_fault_factor`：因反馈受害或构陷 `1.5`；轻过重罚 `1.2`；过错未知 `1.0`；争议嫌疑 `.9`；重大过错但处置过重 `.5`；谋反坐实后的极弱残余 `.2`。

`feedback_entry`不按谏诤次数线性累加。`durable_multi_stage_feedback=1.3`允许几个按时间可区分的反馈事件跨阶段闭合；`exceptional_dense_cross_domain_remonstrance=1.7`则必须同时有长时段、高密度独立谏诤、多个重大政务领域、逆耳或犯颜情形，以及皇帝持续容纳并保留反馈职责。只有次数概数或史料篇幅不足以进入1.7档。魏徵`TT-O01`有《旧唐书》所载“前后二百余事”、多领域具体谏诤和贞观八年至十六年的独立履职后续，因此映射该1.7档。

`institutionalized_feedback_entry=2.0`不是“同一臣子反复进谏”的更高档。它要求皇帝预先建立正式反馈通道，并有多个独立事件证明该通道持续运行，通常还应面向多名表达者或正式职能主体；单次求言诏令、某一臣子长期进谏或事后多次采纳均不足。李世民的`TT-LSM-INSTITUTIONAL-REM-01`已达到该档：贞观元年建立谏官随宰相议政的正式入口，三、五、六、八、十五、十六、十七年又有持续复核、奖励和重新动员的独立观察。该制度单元只结算通道建立与运行，魏徵等个人单元只结算个人反馈留任与安全；`TT-O04`与`TT-S04`仍是其他统治者的合同可达候选。

四个 V4 因子决定 lane 和语义边界，但不能凭一个安全档猜处置严重度，也不能凭 `mixed_responsibility` 猜对象过错。缺 `feedback_pattern`、实际处置或 `target_fault_assessment` 即 `insufficient_projection`。

## 七、`anti_nepotism` 避免任人唯亲

必须先确认私人关系锚点和公共任用影响，再区分污染、预防或纠偏；普通公开择才没有私人任用对照时不自动适用。

Episode 拥有 `capability_basis`、`process_integrity`、`public_power_exposure`；AggregateContext 独占 `network_effect`。

```text
positive_raw_material_score =
  selection_openness * institutionalization * office_weight * evidence_factor

negative_raw_material_score =
  - favoritism_intensity * office_weight * displacement_harm * evidence_factor
```

正向数值：`selection_openness=.7/1.0/1.25/1.4`；`institutionalization=.8/1.0/1.15`；`office_weight=.8/1.0/1.15`，分别对应个案到制度化、普通到关键岗位。

负向数值：`favoritism_intensity=.7/1.1/1.5/2.0`，对应私人色彩到系统捕获；`displacement_harm=.7/1.0/1.4/2.0`，对应任用观感到长期制度污染。

`public_power_exposure` 可投影岗位权重，其余数值必须由四因子联合判断。网络广度不等于实际排挤损害；缺 `displacement_harm_observation` 即 `insufficient_projection`。

## 八、规则原始信号聚合

```text
rule_raw_net = positive_signal - negative_signal
```

`talent_discovery`、`tolerate_talent`、`anti_nepotism` 继承 V3 实际运行的对象内密度控制：

```text
object_side_score = min(
  strongest_material + 0.35 * sum(secondary_materials),
  strongest_material * 1.5,
  4.0
)

side_signal = sum(object_side_score)
```

`appointment_delegation` 使用：

```text
material_weight(rank) = 1 / rank ^ 1.0
event_weight(rank)    = 1 / rank ^ 1.0
object_weight(rank)   = 1 / rank ^ 0.5

positive_signal = 1.5 * sum(object_value * object_weight)
negative_signal = 1.0 * sum(object_value * object_weight)
```

每条材料必须记录 event key、rank、weight、weighted value、Judgment 和 Assertion lineage。`team_building` 始终使用第五章的时间窗口人物池。

## 九、动态计分输入与五条 rule 权重

```text
weighted_raw_signal =
  0.19 * talent_discovery.rule_raw_net
+ 0.36 * appointment_delegation.rule_raw_net
+ 0.21 * team_building.rule_raw_net
+ 0.18 * tolerate_talent.rule_raw_net
+ 0.06 * anti_nepotism.rule_raw_net
```

权重和为 `1.0`。`weighted_raw_signal` 只是动态映射输入，不是得分率或 45 分。

V3 没有完成最终动态映射算法；真实 calculator 也把 `score_rate`、`score`、`tier` 留空。V4 继承以下原则：

- 必须在多皇帝批次中映射，禁止单皇帝即时定标；
- 同时使用标杆人物、原始信号分布、合理区分度和总则档位；
- 映射必须单调；
- 每次冻结 calibration version、cohort、输入 fingerprint、标杆、分布摘要、映射定义、间距诊断和人工批准；
- 重映射产生新版本，不覆盖旧分数；
- 映射快照批准前，最终分数字段保持 `null`。

单皇帝可以独立得到稳定的五条 `rule_raw_net` 和 `weighted_raw_signal`，最终 `0—45` 分则依赖冻结批次标尺。

## 十、跨规则与跨项复用边界

- `talent_discovery` 结算首次进入有效视野；后续岗位适配归 `appointment_delegation`；
- `team_building` 结算窗口整体结构，不重复累加成员的单次发现或任用材料分；
- `tolerate_talent` 结算人才反馈、安全与修复，不重复第五项 E 的一般纳谏；
- `anti_nepotism` 结算私人关系对公共任用的污染、预防和纠偏；一般权力主体失控归第五项 C；
- 军事、治理和文明成果可证明任用反馈，但实际领域净收益归相应大项。

每个 ScoreContribution 必须声明 primary owner、supporting-only rules、去重键、排除原因和完整 lineage。

## 十一、当前实现与发布边界

已完成：V3 计分格式和五权重移植；任用授权精确映射；团队双轴人物池；三条联合投影 rule 的缺失输入失败关闭合同与确定性 ScoreContribution；`WeightedRawEnvelope` 离线计算；多皇帝 `BatchMappingInput` 版本和 fingerprint。`team-building-v8-person-profile-raw-signal-v3` 已按V10最新有效人才校准链完成全部12个冻结测试窗口的工作集计算：正负池分别排序衰减，补充画像的政治风险人工评估按版本化结构兼容读取，结构观察显式冻结，成员发现与任用事件不重复计分；这不声明历史团队名录穷尽。三条联合投影当前为人才发现5/6、容才9/18、反任人唯亲8/11成功投影，其余单元保留 `insufficient_projection` 和缺失输入，不以零材料替代。统一 readiness runner v2 强制接收版本化历史覆盖报告；现有报告只能声明 `workset_projection_status`，只有候选清单、正反检索、逐项处置、投影消费对账和人工冻结全部关闭后才允许 `coverage_complete`。当前24名皇帝的五规则历史覆盖完整数均为0，没有生成候选映射批次。V3让同一结构乘数同时放大正负池的做法暂仅保留在shadow，仍须专门复核。

李世民V3 Claim只读试迁另冻结304条active Claim和629条直接证据。V3 route hint为识才17、任用授权174、容才103、反任人唯亲15、团队建设0；这些数字表示待复核候选，不是材料数、适用单元数或覆盖完成度。275条代表Claim仍处于V3 material review pending，且身份、史源元数据和事件去重尚需V4 Gate，因此当前接受为正式V4 Assertion的数量为0，五条`historical_coverage_status`保持`unassessed`。

首批回源队列固定为四条有V3 route的rule各8条，共32个不同Claim；反任人唯亲与识才先选，避免大体量任用候选吞掉稀缺rule。未入首批的179条容量延后、53条门禁阻断、40条无I5B路由候选均保留，`dropped_claim_count=0`。人工语义碰撞审计识别23条Claim对既有工作集形成42个`aggregate_component` rule-slot：任用授权魏徵19条、容才魏徵21条、识才马周2条，其中任用与容才共享19条。它们只说明可能是既有聚合单元的组成部件，不能自动合并、自动排除或继承旧Gold；精确lineage碰撞和完整事件等价当前均为0。

首批规则级预审只留下4条新事件回源候选：神通争功时以功次压过宗亲私情、房玄龄与李勣荐张亮、高士廉摄太子太傅同掌机务、萧瑀任太子太保并知政事。另2条属于既有聚合部件，6条需跨rule确定主结算，14条为错误路由，5条适用性不足，1条切片错位导致史源不足。预审不创建Assertion，也不证明这4条最终适用；它只把有限回源成本集中到仍可能闭合规则前提、皇帝归责、权责与结果链的材料。

李世民当前统一shadow净值以`eval/i5b_ruler_rule_net/lishimin_report.json`为机器视图：人才发现`4.712`、任用授权`10.722`、团队建设`13.198`、容才`10.353`、反任人唯亲`0.000`。这五个数均表示各自声明工作集或建议人物池的严格当前净值，不表示历史覆盖完整。团队建设以626—649窗口25人池计算，正池14.120、侯君集窗口负池0.922，并保留9.553的20人保守下界；许敬宗等后朝风险不倒灌。容才正向池现含贞观求谏机制2.783、魏徵2.057、虞世南1.392、褚遂良1.573、马周1.392、戴胄1.809；TT-O05身后信用撤销仍独立结算负向0.653，当前净值10.353。制度单元与个人单元按通道收益和个人收益严格去重。103条V3 route线索已完成27人物组级盘点，但102个事件组逐项处置、独立于V3 route的正反向检索以及萧瑀等六个优先人物回源仍未关闭，故覆盖状态只是`in_progress`。反任人唯亲的神通功次候选仍只列条件区间，不在通过公共权力适用性Gate前计入严格值。五权重合成raw signal为`9.390`，但单皇帝不得执行动态映射，正式45分、tier和排名仍为空。

尚未批准：旧 open/sealed Gold 作为新数值资格证明；未经验证的联合投影结果；动态映射的标杆和区间快照；正式 45 分、排名、生产 scorer 和数据库写入。

旧测试集继续只作已开封回归与诊断。政策校验入口：

```text
python -m emperor_v4.eval i5b-scoring-policy \
  --policy config/i5b-scoring-policy.yml \
  --output eval/i5b_test_set_portfolio/scoring_policy_report.json
```
