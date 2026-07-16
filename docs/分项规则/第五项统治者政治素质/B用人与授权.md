# 第五项 B：用人与授权计分规则（V4）

第五项 B 评价统治者发现人才、合理任用与授权、建立团队、容纳并保护人才、避免任人唯亲的能力。本项满分为 45 分。

本规则包含五个计分分项：

| 分项代码 | 中文名称 | 项内权重 |
| --- | --- | ---: |
| `talent_discovery` | 发现人才 | 19% |
| `appointment_delegation` | 任用授权质量 | 36% |
| `team_building` | 建立团队 | 21% |
| `tolerate_talent` | 容人保全 | 18% |
| `anti_nepotism` | 避免任人唯亲 | 6% |

## 一、通用计算规则

### 1. 材料分

每条有效材料先按所属分项公式计算原始材料分，再限制在 `-4.0—+4.0`：

```text
material_score = clamp(raw_material_score, -4.0, +4.0)
```

| 材料分绝对值 | 中文解释 |
| ---: | --- |
| `0.3—0.8` | 弱证、边界证或辅助材料 |
| `0.8—1.6` | 常规有效材料 |
| `1.6—2.8` | 强材料 |
| `2.8—4.0` | 极强材料 |

只有人工接受且具备 Assertion、HistoricalEpisode、RuleEvidenceUnit 和史源 lineage 的正式材料参加计分。同一事实被技术性拆成多条记录时只计一次。

### 2. 证据修正系数

除“建立团队”外，其余分项使用统一证据修正系数：

```text
evidence_factor = clamp(
  attribution_factor × source_factor × context_factor,
  0.45,
  1.25
)
```

#### 皇帝归责系数 `attribution_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `indirect` | 间接归责 | 0.80 |
| `direct` | 直接归责 | 1.00 |
| `direct_under_pressure` | 在明确反对或现实压力下仍由皇帝直接决策 | 1.10 |

#### 史源系数 `source_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `weak_or_compressed` | 史源较弱或记载过度压缩 | 0.75 |
| `standard` | 标准有效史源 | 1.00 |
| `complete_direct_chain` | 直接且完整的证据链 | 1.10 |

#### 语境系数 `context_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `weak_but_applicable` | 语境较弱但仍可适用 | 0.70 |
| `clear` | 事实链与规则边界清楚 | 1.00 |
| `core_mechanism_direct` | 直接呈现本分项核心机制 | 1.10 |

材料缺少必要输入时记为“无法投影”，不得用默认值补齐，也不得把证据不足当作零分。

### 3. 结算预算

结算预算限制正式入分单元数量，不要求建立历史材料全集。军事、行政、地方、制度、储位等只作检索与覆盖标签，不设固定分值、代表名额或必填槽位。

| 分项 | 正向结算预算 | 负向结算预算 | 计数单位 |
| --- | ---: | ---: | --- |
| 发现人才 | 3 | 3 | 独立识才链 |
| 任用授权质量 | 3 | 3 | 独立任用授权链 |
| 建立团队 | 8名成员 | 3名风险成员 | 一个皇帝—窗口团队单元 |
| 容人保全 | 3 | 3 | 独立反馈—回应—安全—修复链 |
| 避免任人唯亲 | 3 | 3 | 独立私人关系—公共任用影响链 |

人工冻结先判断适用性、皇帝归责、因果独立性和重复边界，形成合格候选集；数值投影完成后，事件型分项正负两侧分别结算最终材料分最高的预算内单元。Judge 只能因事实不成立、路由错误、归责不足、因果不独立或重复结算排除材料，不得以领域代表性或已有同领域高分材料为由排除。预算未用满不扣分，不改变分母，也不触发补齐领域的检索任务。

同一事件、同一履职结果或同一制度运行事实被拆成多条记录时只算一个结算单元。同一对象的连续材料优先聚合为主事实及持续性证据；重复性、持续性和制度化程度只由专属因子表达，不按材料篇数再次累加。

正向与负向预算独立。正向预算已满不得关闭负向、反证和路由纠错；已知的新材料只有可能改变适用性、因子档位、正负方向、重复边界或预算边界分数时才重新进入 Judge，否则只补充 lineage。

### 4. 聚合与停止

各分项沿用本规则规定的材料聚合公式，不增加领域权重。预算内单元聚合后得到：

```text
rule_raw_net = positive_signal - negative_signal
```

满足以下条件后，停止该侧常规扩展检索：合格候选数已达到结算预算，且继续检索不太可能产生高于当前预算边界的独立材料；候选清单已逐项处置；已知反证和负向线索已完成检查；没有仍可能改变裁决的未决线索。停止后新增同质材料不得增加数值；只有可能超过预算边界或改变既有 Gate 裁决的材料才重新进入版本化 Judge。

## 二、发现人才 `talent_discovery`

本分项评价统治者在首次实质使用前，识别、验证、引入人才并将其转化为实际使用的能力。使用后的政绩或战果不得反向充当识才依据。

评价窗口仍以在位期为主，但发现行为允许回溯到统治者取得独立用人或统军权限后的储位、藩府或创业阶段。只有统治者本人或其直接授权者完成招募、验证和转化，且对象进入其本人团队并延续到评价窗口，才进入候选；由前任君主、父祖朝廷或其他政治主体独立招募者不得仅因后来被沿用而归责给本统治者。登基前材料必须标记 `pre_accession_leadership_formation`，不得与登基后的同一识才链重复结算。

```text
raw_material_score =
  direction_sign
  × discovery_level
  × talent_quality_factor
  × evidence_factor
```

### 1. 方向 `direction_sign`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `positive` | 成功发现并转化人才 | +1.00 |
| `missed_or_suppressed_discovery` | 错失或压制人才发现 | -1.00 |

### 2. 发现程度 `discovery_level`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `passive_reputation` | 主要沿用既有名望，缺少独立验证或转化 | 0.60 |
| `recommendation_entry` | 经荐举进入视野，并形成有限验证或试用 | 0.80 |
| `attributable_interview_trial_or_appointment` | 皇帝直接观察、面试、试用或实质任用 | 1.00 |
| `difficult_cross_boundary_discovery` | 突破身份、门第、地域或阵营障碍并完成实质转化 | 1.20 |

发现程度由识别新颖度、识别依据、障碍突破和转化使用四项观察联合判断，四项观察不分别重复相乘。

### 3. 人才等级 `talent_quality_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `ordinary` | 普通人才 | 0.60 |
| `usable` | 可用人才 | 0.90 |
| `important` | 重要人才 | 1.15 |
| `top` | 顶级人才 | 1.45 |
| `historic` | 历史级人才 | 1.80 |

人才等级取人物画像的当前有效档位，不得由官职、声望或单次战果临时反推。

### 4. 发现人才聚合

同一对象同一方向的多条材料先执行密度控制；正负各最多结算3条独立识才链。人物所属领域只作检索标签，不参与加权。

```text
object_side_score = min(
  strongest_material + 0.35 × sum(secondary_materials),
  strongest_material × 1.5,
  4.0
)

side_signal = sum(settled_object_side_score)
talent_discovery.rule_raw_net = positive_signal - negative_signal
```

## 三、任用授权质量 `appointment_delegation`

本分项评价统治者是否把合适的人放在合适的职责上，并给予与职责匹配、边界清楚且可持续的授权。

任用授权既允许“具体人物—具体职责—履职反馈”链，也允许“责任机构或责任群体—制度化权限—持续运行反馈”链。文官治理不得因成果由集体完成、分散在多个时点或表现为制度运行而被排除；史料数量和职责领域不附加权重。

```text
raw_material_score =
  appointment_importance
  × appointment_effect
  × continuity_factor
  × evidence_factor
```

### 1. 任用重要性 `appointment_importance`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `nominal_or_light` | 名义性、礼仪性或轻量职责 | 0.60 |
| `real_bounded` | 有实权但职责范围有限 | 1.00 |
| `major_affairs` | 承担重要军政或方面事务 | 1.25 |
| `critical_national_or_long_term` | 国家全局、战略地域、长期责任或制度形成关键职责 | 1.40 |

重要性只按授权当时的责任域判断，不得用后续成果反向抬档。

### 2. 任用效果 `appointment_effect`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `weak_feedback` | 有正向反馈，但效果较弱 | +0.40 |
| `normal_success` | 正常成功履职 | +1.00 |
| `major_success` | 人岗配置带来重大且直接的成功 | +1.50 |
| `exceptional_success` | 人岗配置直接改变国家战略格局或形成基础制度成果，且受任者贡献高度直接 | +1.80 |
| `bounded_control_failure` | 授权或监督失误成立，但未证明超出个案的公共损害 | -0.30 |
| `limited_direct_damage` | 已形成明确、直接但范围有限的公共损害 | -0.80 |
| `major_direct_damage` | 造成重大但相对一次性的直接损害 | -1.80 |
| `structural_continuing_damage` | 造成跨期、制度性或组织能力持续损害 | -2.60 |

### 3. 持续性 `continuity_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `short_or_one_off` | 短期或一次性授权 | 0.85 |
| `stable` | 稳定授权，并有至少两个可区分的履职或反馈观察 | 1.00 |
| `long_term_multi_stage` | 长期多阶段授权，至少有两次可区分的授权决定 | 1.15 |

### 4. 任用责任链证据合同

| 合同字段 | 计分要求 |
| --- | --- |
| 皇帝归责 | 必须有皇帝设立、任命、授权、采纳或维持该责任机制的 Assertion。 |
| 责任主体 | 可以是具体人物、正式机构或边界明确的责任群体；不得强制要求唯一受任者。 |
| 权限或程序边界 | 必须说明该主体负责什么、可以决定什么或必须履行什么程序。 |
| 实际运行观察 | 必须至少有一次区别于制度设立动作的执行、履职、复核或反馈观察；只有诏令、原则或政策入口不得投影。 |
| 运行结果 | 用于判断 `appointment_effect`；政策本身的社会净收益不在本分项重复结算。 |
| 负向损害与纠正 | 分别记录受任者行为、实际公共损害、皇帝事前可预见性、知情后的收权/停职/惩处/补救及是否恢复任用；不得仅按任务级别放大个人违法。 |
| Lineage | 上述字段必须分别绑定已接受 Assertion，并归入同一 HistoricalEpisode / RuleEvidenceUnit 责任链。 |

### 5. 任用授权聚合

制度运行材料必须至少证明皇帝归责、责任主体或责任机构、权限或程序边界、实际运行观察四项；若另有可归责结果，可提高 `appointment_effect`，但不得因缺少唯一受任者而直接判为无法投影。`appointment_effect` 只评价选任、授权或责任机制是否有效运转；政策本身的社会净收益仍回到前四项结算。

负向档位只按实际损害分档：只证明授权或监督失误、未证明超出个案的公共损害，使用 `bounded_control_failure`；已形成明确、直接但范围有限的公共损害，使用 `limited_direct_damage`；屠城、系统性劫掠、大规模强制劳役等重大一次性损害，使用 `major_direct_damage`；损害继续破坏人口、财政、制度或组织能力时，使用 `structural_continuing_damage`。皇帝知情前后的收权、停职、惩处、补救和恢复任用单独记录，用于归责和净损害判断，不进入档位名称。若严重行为是受任者违令所为且皇帝及时制止、惩处并补救，主要归责于受任者，不得自动按皇帝直接重大损害结算。

正负各最多结算3条独立任用授权链。全部通过证据合同、路由、归责、独立性和去重 Gate 的候选完成材料投影后，正负两侧分别结算最终材料分最高的3条；沿用对象内、事件内和对象间衰减。任用领域只作检索标签，不设领域配额或代表名额。

```text
material_weight(rank) = 1 / rank
event_weight(rank) = 1 / rank
object_weight(rank) = 1 / rank ^ 0.5

positive_signal = 1.5 × sum(settled_object_value × object_weight)
negative_signal = 1.0 × sum(settled_object_value × object_weight)
appointment_delegation.rule_raw_net = positive_signal - negative_signal
```

## 四、建立团队 `team_building`

本分项以“皇帝—时间窗口”为唯一计分单元。人物能力与政治风险分别计算，不得因政治风险降低人才等级；成员所属决策、行政、军事、纠错等角色只用于判断团队互补性，不形成必填槽位。

```text
positive_pool = sum(talent_value_rank / rank ^ 0.5)
negative_member_value =
  negative_talent_severity_value × negative_talent_class_relevance

negative_pool = sum(negative_member_value_rank / rank ^ 0.5)

team_building.positive_signal =
  positive_pool × functional_complementarity_factor × long_term_stability_factor

team_building.negative_signal =
  negative_pool × functional_complementarity_factor × long_term_stability_factor

team_building.rule_raw_net = team_building.positive_signal - team_building.negative_signal
```

正池最多冻结8名能够代表窗口团队结构的成员，负池最多冻结3名在窗口内实际暴露风险的成员。成员冻结由人工在数值投影前完成，不按人才档位或计算后数值自动取前N名。正池预算已满后，新增同质成员只补充团队 lineage；只有可能改变互补性、稳定性或现有成员代表性的材料才重新进入 Judge。

### 1. 人才能力档位 `talent_quality_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `ordinary` | 普通人才 | 0.35 |
| `usable` | 可用人才 | 0.55 |
| `important` | 重要人才 | 0.90 |
| `top` | 顶级人才 | 1.20 |
| `historic` | 历史级人才 | 1.60 |

### 2. 负面严重度 `negative_talent_severity_value`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `minor` | 轻微政治风险 | 0.20 |
| `material` | 实质政治风险 | 0.45 |
| `major` | 重大政治风险 | 0.80 |
| `historic` | 历史性或系统性重大风险 | 1.20 |

只有风险在当前皇帝窗口内实际暴露，才进入负池；后朝风险不得倒灌前朝窗口。

### 3. 负面类型相关度 `negative_talent_class_relevance`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `sycophant` | 谄媚迎合 | 0.80 |
| `favorite` | 私宠亲信 | 0.70 |
| `power_abuser` | 滥权者 | 1.00 |
| `framer` | 构陷者 | 1.00 |
| `extractive_official` | 掊克聚敛者 | 0.90 |
| `cruel_official` | 酷烈执法者 | 0.90 |
| `incompetent_harmful` | 无能且造成实害者 | 1.00 |
| `traitorous_actor` | 谋逆或严重背叛者 | 0.80 |
| `mixed_or_disputed` | 类型混合或存在争议 | 0.50 |

负面严重度评价风险造成的实际强度，负面类型相关度评价该风险与“建立团队”规则的贴合程度；二者不得合并为同一个档位。

### 4. 功能互补系数 `functional_complementarity_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `homogeneous` | 团队功能明显单一 | 0.90 |
| `ordinary_two` | 具备两个主要功能面 | 1.00 |
| `strong_three` | 三个主要功能面形成有效互补 | 1.10 |
| `balanced_four` | 多个主要功能面均衡协同 | 1.20 |

### 5. 长期稳定系数 `long_term_stability_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `unstable_or_narrow` | 功能碎片化、强制更替断裂或长期覆盖过窄 | 0.85 |
| `stable_window` | 窗口内稳定运行 | 1.00 |
| `managed_turnover` | 成员有序更替且核心功能不断裂 | 1.10 |
| `durable_multi_stage` | 跨多个阶段持续稳定运行 | 1.20 |

亲信依赖只在形成反馈失真、滥权或任人唯亲事实时进入负池，不另设重复系数。

## 五、容人保全 `tolerate_talent`

本分项评价统治者是否允许人才提出不同意见、保持专业自主、免受不当报复，并在冲突后完成修复。正向事件和负向处置分别计算。

```text
positive_raw_material_score =
  feedback_entry
  × expression_safety
  × protection_repair
  × evidence_factor

negative_raw_material_score =
  - handling_severity
  × target_fault_factor
  × evidence_factor
```

### 1. 反馈入口 `feedback_entry`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `single_acceptance_or_tolerance` | 单次采纳或容忍不同意见 | 0.70 |
| `repeated_feedback_retained` | 多次反馈后仍保留其职责和地位 | 1.00 |
| `durable_multi_stage_feedback` | 跨阶段持续允许反馈 | 1.30 |
| `exceptional_dense_cross_domain_remonstrance` | 长期、高密度、跨领域容纳犯颜直谏 | 1.70 |
| `institutionalized_feedback_entry` | 建立并持续运行制度化反馈入口 | 2.00 |

同一人的进谏次数不线性累加。制度化反馈入口必须有正式通道和多个独立运行事件，不能由单次求言或一人长期进谏代替。

### 2. 表达安全 `expression_safety`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `tense_or_case_dependent` | 表达环境紧张，或依赖个案恩免 | 0.80 |
| `basically_safe` | 基本安全，无实质报复 | 1.00 |
| `actively_protected_or_encouraged` | 皇帝主动保护或鼓励表达 | 1.15 |

### 3. 保护与修复 `protection_repair`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `none` | 无特殊保护或补救 | 1.00 |
| `restoration_or_rehabilitation` | 恢复、平反或复官 | 1.10 |
| `active_protection_or_trust_repair` | 主动保护或完整修复信用与信任 | 1.15 |

### 4. 处置严重度 `handling_severity`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `symbolic_or_light` | 象征性或轻微处分 | 0.60 |
| `demotion_or_suppression` | 贬黜、压制或排斥 | 1.20 |
| `imprisonment_or_severe_nonpermanent_harm` | 监禁或严重但非永久性伤害 | 1.80 |
| `execution_or_forced_suicide` | 处死或逼令自尽 | 2.60 |
| `clan_or_systemic_purge` | 集团、家族或系统性清洗 | 3.20 |

### 5. 对象过错系数 `target_fault_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `framed_or_harmed_for_feedback` | 因反馈受害或遭构陷 | 1.50 |
| `minor_fault_disproportionate_harm` | 轻过重罚 | 1.20 |
| `fault_unknown` | 对象过错不明 | 1.00 |
| `disputed_suspicion` | 存在争议性嫌疑 | 0.90 |
| `major_fault_but_excessive_harm` | 有重大过错，但处置仍明显过重 | 0.50 |
| `proven_rebellion_residual_talent_harm` | 谋反坐实后仅剩极弱的人才生态损害 | 0.20 |

缺少实际处置、反馈模式或对象过错判断时，不得计算负向材料分。

### 6. 容人保全聚合

政策、行政、军事、专业、人事等只作场景标签。没有发生某类分歧不扣分，也不要求补齐该类材料。正负各最多结算3条独立反馈—回应—安全—修复链，并沿用对象内密度控制：

```text
object_side_score = min(
  strongest_material + 0.35 × sum(secondary_materials),
  strongest_material × 1.5,
  4.0
)

side_signal = sum(settled_object_side_score)
tolerate_talent.rule_raw_net = positive_signal - negative_signal
```

## 六、避免任人唯亲 `anti_nepotism`

本分项处理公共任用对私人关系的抵抗、预防和纠偏，以及私人网络造成的任用污染。普通公开择才不自动计分；跨身份人才进入关键岗位或形成稳定开放机制时，可以计入正向槽位，无须存在同案私人关系对照。

```text
positive_raw_material_score =
  selection_openness
  × institutionalization
  × office_weight
  × evidence_factor

negative_raw_material_score =
  - favoritism_intensity
  × office_weight
  × displacement_harm
  × evidence_factor
```

### 1. 选拔开放度 `selection_openness`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `avoids_private_interference_case` | 在个案中回避私人干预 | 0.70 |
| `merit_or_formal_basis` | 依据能力或正式程序选拔 | 1.00 |
| `cross_identity_open_selection` | 跨身份开放选拔 | 1.25 |
| `broad_cross_identity_open_selection` | 在多个身份边界和关键岗位保持广泛开放 | 1.40 |

### 2. 制度化程度 `institutionalization`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `single_event` | 单次事件 | 0.80 |
| `repeated_stable_practice` | 重复且稳定的实践 | 1.00 |
| `durable_institution` | 持久运行的制度 | 1.15 |

### 3. 岗位权重 `office_weight`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `ordinary` | 普通岗位 | 0.80 |
| `important` | 重要岗位 | 1.00 |
| `central_military_or_succession` | 中枢、军事或继承关键岗位 | 1.15 |

### 4. 徇私强度 `favoritism_intensity`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `visible_private_relation` | 私人关系明显，但尚未替代能力判断 | 0.70 |
| `private_relation_over_merit` | 私人关系压过能力或正式程序 | 1.10 |
| `continuing_core_appointment_interference` | 持续干预核心任用 | 1.50 |
| `systemic_private_network_capture` | 私人网络系统性控制公共任用 | 2.00 |

### 5. 排挤损害 `displacement_harm`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `optics_only` | 主要损害任用公信与观感 | 0.70 |
| `qualified_people_or_key_office_harmed` | 合格人才或关键岗位受到损害 | 1.00 |
| `team_policy_or_expression_structure_harmed` | 团队、政策或表达结构受到损害 | 1.40 |
| `durable_institutional_pollution` | 形成长期制度污染 | 2.00 |

网络范围不能直接代替实际排挤损害；缺少损害观察时，不得计算负向材料分。

### 6. 避免任人唯亲聚合

中枢、军事、地方、宫廷、宗室、储位和选任制度只作公共权力场景标签。正负各最多结算3条独立私人关系—公共任用影响链，并沿用对象内密度控制：

```text
object_side_score = min(
  strongest_material + 0.35 × sum(secondary_materials),
  strongest_material × 1.5,
  4.0
)

side_signal = sum(settled_object_side_score)
anti_nepotism.rule_raw_net = positive_signal - negative_signal
```

## 七、第五项 B 原始信号

五个分项先各自得到净原始信号，再按固定权重合成：

```text
weighted_raw_signal =
  0.19 × talent_discovery.rule_raw_net
+ 0.36 × appointment_delegation.rule_raw_net
+ 0.21 × team_building.rule_raw_net
+ 0.18 × tolerate_talent.rule_raw_net
+ 0.06 × anti_nepotism.rule_raw_net
```

`weighted_raw_signal` 是批次动态映射的输入，不是得分率，也不是 45 分制得分。经适用性判断确认无可计分材料的侧信号记为零；证据不足或无法投影时结果为空，不得以零分代替。

## 八、45 分动态映射

最终得分必须在包含多名皇帝的冻结批次中，根据原始信号分布和标杆进行单调映射。单名皇帝只能计算稳定的五项净原始信号与加权原始信号，不能单独完成 45 分定标。

动态映射快照必须固定以下内容：

| 固定项 | 中文解释 |
| --- | --- |
| 校准版本 | 本次映射规则的唯一版本 |
| 皇帝批次 | 共同参与定标的皇帝集合 |
| 输入指纹 | 各分项原始信号及批次输入的内容指纹 |
| 标杆 | 用于校准高、中、低位置的参照对象 |
| 分布摘要 | 批次原始信号的范围与分布 |
| 单调映射定义 | 原始信号越高，映射结果不得反向降低 |
| 间距诊断 | 检查结果是否具有合理区分度 |
| 人工批准 | 对本次映射快照的正式接受决定 |

映射快照未批准时，45 分得分、得分率和档位均保持为空；重新映射必须生成新版本，不得覆盖旧结果。

## 九、重复结算边界

| 事实类型 | 主要计入分项 | 不重复计入 |
| --- | --- | --- |
| 首次进入有效视野 | 发现人才 | 后续岗位适配不再计发现人才 |
| 跨身份人才的识别与晋升 | 首次识别归发现人才；后续进入关键岗位或开放机制归避免任人唯亲 | 同一次识别或任用决定不得同时计入两条 rule |
| 人岗配置与授权反馈 | 任用授权质量 | 实际军事、治理或文明净收益仍归对应大项 |
| 时间窗口内的团队整体结构 | 建立团队 | 不重复累加成员的单次发现或任用材料分 |
| 人才反馈、安全与冲突修复 | 容人保全 | 一般纳谏能力不在本分项重复结算 |
| 私人关系对公共任用的影响 | 避免任人唯亲 | 一般权力失控不在本分项重复结算 |

同一决策弧、同一业务收益或同一损害只能有一个主要结算归属。其他分项可以引用同一事实作辅助证据，但不得再次计分。
