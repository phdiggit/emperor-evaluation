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

五个分项统一遵守领域等价原则：因子只评价识才难度、公共责任、实际运行、人才能力、反馈安全或公共权力损害，不评价材料是否以战役叙事呈现。相同责任范围、相同结果尺度和相同证据强度的军事、行政、法制、财政、地方治理、教育文化与专业技术事实必须进入同一档位；官名、兵力数字、史料篇幅和叙事戏剧性不得成为隐含加权项。

| 分项 | 正向上限 | 负向上限 | 计数单位 |
| --- | ---: | ---: | --- |
| 发现人才 | 12 | 12 | 独立识才链 |
| 任用授权质量 | 12 | 12 | 聚合后的独立任用对象或责任群体 |
| 建立团队 | 8名成员 | 3名风险成员 | 一个皇帝—窗口团队单元 |
| 容人保全 | 12 | 12 | 独立反馈—回应—安全—修复链 |
| 避免任人唯亲 | 12 | 12 | 独立私人关系—公共任用影响链 |

事件型分项正负两侧独立结算最强12个合格单元：第1—6名按`1.00`、第7—9名按`0.75`、第10—12名按`0.50`计入。未用满不扣分；Judge 只能因事实、路由、归责、独立性或重复边界排除，不得因领域或名额平衡排除。

同一事件、同一履职结果或同一制度运行事实被拆成多条记录时只算一个结算单元。同一对象的连续材料优先聚合为主事实及持续性证据；重复性、持续性和制度化程度只由专属因子表达，不按材料篇数再次累加。

正向与负向独立；一侧已满不关闭另一侧、反证或路由纠错。第12名以后只在可能改变方向、档位、去重或预算边界时重审，否则仅补 lineage。

单一皇帝的五个分项共享 15 分钟历史覆盖硬截止时间，自该皇帝首个宽搜任务被领取时开始，恢复运行不得重置。宽搜、按文献页回源和最小充分 Claim 抽取应解耦并允许阶段重叠；到点停止领取新任务，超时返回只形成待补缺口，不得进入本轮候选，也不得把未经回源线索转为正式材料。

单一皇帝每轮最多启动12个人物检索入口；皇帝政策和责任群体不占名额。人物稳定去重后截取，旧材料复用不耗名额，不得用别名或拆分焦点绕过上限。

### 4. 聚合与停止

各分项沿用本规则规定的材料聚合公式，不增加领域权重。预算内单元聚合后得到：

```text
rule_raw_net = positive_signal - negative_signal
```

该侧已有12个合格单元、候选和反证均已处置，且没有可能越过预算边界的未决线索时停止扩展检索。

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
| `difficult_cross_boundary_discovery` | 突破身份、门第、地域、阵营、低位接近或专业识别障碍并完成实质转化 | 1.20 |

发现程度由识别新颖度、识别依据、障碍突破和转化使用四项观察联合判断，四项观察不分别重复相乘。敌对阵营降人不因军事身份自动进入最高档；从基层文书、策论、技术作品、地方履职或非主流专业中识别人才，若存在同等可验证的接近与识别障碍，也适用最高档。

### 3. 人才等级 `talent_quality_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `ordinary` | 普通人才 | 0.60 |
| `usable` | 可用人才 | 0.90 |
| `important` | 重要人才 | 1.15 |
| `top` | 顶级人才 | 1.45 |
| `historic` | 历史级人才 | 1.80 |

人才等级取人物画像的当前有效档位，不得由官职、声望或单次战果临时反推。五档统一事实门槛见 `docs/证据规则/公共成果登记与人物画像规则.md`；本分项只使用该档位，不另行评定人物能力。

### 4. 发现人才聚合

同一对象同一方向最多保留3条独立识才链并先做密度控制；全局正负各按通用12条上限和尾部衰减结算。人物领域只作检索标签。

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

评价窗口从统治者取得独立用人或统军权限开始。登基前的幕府、储位或创业阶段，只要授权主体确为该统治者，并已形成“具体责任—实际运行—可归责结果”的完整任用授权链，即使该项具体职责在登基前已经结束，也可以作为独立材料进入本分项；不强制要求同一职责延续进入在位期。若同一责任链跨越登基前后，应合并为一个跨阶段单元，不得重复结算。

单纯由前任朝廷、父祖或其他政治主体授官，没有该统治者本人的任命、授权、采纳或维持行为，仍不适用；仅因相关人物后来继续受任，也不得倒推为该统治者登基前的任用成绩。登基前任用的实际结果只用于判断人岗配置和授权机制是否有效，夺权、战争、制度或治理结果本身仍回到对应项目结算。与发现人才使用同一事实链时，只能分别提取“识别并转化使用”和“具体授权后的履职效果”，不得重复使用同一观察抬高两条材料。

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
| `real_bounded` | 有实权但仅负责局部据点、普通地方、单项专业事务或其他失败影响可局部吸收的职责 | 1.00 |
| `major_affairs` | 承担重要战区、中央部门、重要地方或跨机构任务；失败会造成重大损失，但国家核心仍可承受 | 1.25 |
| `critical_national_or_long_term` | 直接控制国家存亡、首都或核心根据地、国家主力、统一战争关键方向，或全国核心制度的形成与长期运行 | 1.40 |

重要性只按授权当时的责任域和可预见失败后果判断，不得用后来恰好取得的大成果反向抬档。成果登记向本分项投影时，必须由参与者的结构化 `delegated_responsibility` 分别提供 `scope`、`importance_basis`、个人责任范围、授权者和授权证据。虎牢承担同时应对王世充、窦建德并关系唐朝统一成败，柏壁发生在晋阳失守、刘武周宋金刚进逼关中安全之后，均可进入 `critical_national_or_long_term`；普通方面远征、区域平叛或全国性但非核心的文化工程不得因此跟随抬档。

战役父项中的国家军队方面主帅不得因史书省略重复任命文字而记成“无皇帝授权”。有逐字任命、遣将或专任引文时登记 `explicit`；没有逐字任命引文，但固定史源明确该人在对应皇帝窗口内实际统领国家军队、独立承担方面或战役群主帅职责，且没有自立、越权或抗命证据时，可登记 `tacit`。默示授权只能由主帅或可证明独立方面责任的将领取得，普通参战者和现场副将不得自动取得。显式或默示只决定归责证据是否成立，不限制责任重要度；重要度仍按授权时可证的任务边界和失败后果判断。`authorizer_ref` 必须指向实际授权者，防止同一人物在受任皇帝窗口和本人后来称帝窗口之间发生归责倒置。

### 2. 任用效果 `appointment_effect`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `weak_feedback` | 有正向反馈，但效果较弱 | +0.40 |
| `normal_success` | 完成局部、常规或边界明确的职责，没有改变主要战略方向 | +1.00 |
| `major_success` | 完成重要战区、重要区域、中央子系统或重大阶段任务，形成重大且直接的正向反馈 | +1.50 |
| `exceptional_success` | 实际解除国家存亡危机、终结第一梯队竞争极、完成决定统一成败的独立战略方向，或建成国家运行所依赖的核心制度 | +1.80 |
| `bounded_control_failure` | 授权或监督失误成立，但未证明超出个案的公共损害 | -0.30 |
| `limited_direct_damage` | 已形成明确、直接但范围有限的公共损害 | -0.80 |
| `major_direct_damage` | 造成重大但相对一次性的直接损害 | -1.80 |
| `structural_continuing_damage` | 造成跨期、制度性或组织能力持续损害 | -2.60 |

效果档按已经实现且可归责的人岗配置反馈判断。战役依次读取完成度和 `strategic_result_class`：局部战术、普通重要目标为正常成功，重大阶段或危机为重大成功，独立战略方向及各类战争终局为卓越成功；`mixed / partial` 默认只记有限反馈。治理和谋略不得再按 `scale.level` 机械映射：全国性文化工程通常仍是重大成功，只有全国核心治理子系统、时代秩序重建或文明奠基成果才进入卓越成功。个人只承担成果一段工作时，继续以 `delegated_responsibility.appointment_effect` 收窄，不得继承整个成果的终局。

### 3. 持续性 `continuity_factor`

| 档位代码 | 中文档位 | 系数 |
| --- | --- | ---: |
| `short_or_one_off` | 短期或一次性授权 | 0.85 |
| `stable` | 稳定授权，并有至少两个可区分的履职或反馈观察 | 1.00 |
| `long_term_multi_stage` | 长期多阶段授权；可以是至少两次可区分的授权决定，也可以是同一持续授权下跨阶段运行且至少有两个独立履职反馈 | 1.15 |

### 4. 任用责任链证据合同

| 合同字段 | 计分要求 |
| --- | --- |
| 皇帝归责 | 必须有皇帝设立、任命、授权、采纳或维持该责任机制的 Assertion。 |
| 责任主体 | 可以是具体人物、正式机构或边界明确的责任群体；不得强制要求唯一受任者。 |
| 权限或程序边界 | 必须说明该主体负责什么、可以决定什么或必须履行什么程序。 |
| 实际运行观察 | 必须至少有一次区别于制度设立动作的执行、履职、复核或反馈观察；只有诏令、原则或政策入口不得投影。 |
| 运行结果 | 用于判断 `appointment_effect`；政策本身的社会净收益不在本分项重复结算。 |
| 个人贡献边界 | 若受任者只承担公共成果的一段工作，必须在 `delegated_responsibility` 中单列其实际效果与持续性；不得继承整个成果的规模、终局或跨期持续性。 |
| 事后奖惩或明确评价 | 统治者在责任运行后作出的奖惩、留任、升降或明确功过归因，可以补强受任者角色、运行反馈和皇帝归责；它只能并入已有责任链，不得在缺少具体责任与实际运行观察时单独建立材料，也不得另行加分。 |
| 并行授权冲突 | 统治者同时维持彼此冲突、足以互相破坏的命令或授权时，必须合并观察整体协调责任和净运行结果；不得把其中一个子任务的阶段成功拆出单独正向结算。受任者依仍然有效的命令行动，不得误判为违令而切断统治者归责。 |
| 负向损害与纠正 | 分别记录受任者行为、实际公共损害、皇帝事前可预见性、知情后的收权/停职/惩处/补救及是否恢复任用；不得仅按任务级别放大个人违法。 |
| Lineage | 上述字段必须分别绑定已接受 Assertion，并归入同一 HistoricalEpisode / RuleEvidenceUnit 责任链。 |

### 5. 任用授权聚合

制度运行材料必须至少证明皇帝归责、责任主体或责任机构、权限或程序边界、实际运行观察四项；若另有可归责结果，可提高 `appointment_effect`，但不得因缺少唯一受任者而直接判为无法投影。`appointment_effect` 只评价选任、授权或责任机制是否有效运转；政策本身的社会净收益仍回到前四项结算。

负向档位只按实际损害分档：只证明授权或监督失误、未证明超出个案的公共损害，使用 `bounded_control_failure`；已形成明确、直接但范围有限的公共损害，使用 `limited_direct_damage`；屠城、系统性劫掠、大规模强制劳役等重大一次性损害，使用 `major_direct_damage`；损害继续破坏人口、财政、制度或组织能力时，使用 `structural_continuing_damage`。皇帝知情前后的收权、停职、惩处、补救和恢复任用单独记录，用于归责和净损害判断，不进入档位名称。若严重行为是受任者违令所为且皇帝及时制止、惩处并补救，主要归责于受任者，不得自动按皇帝直接重大损害结算。

同一对象的独立责任链先按强度排序，以 `1 / rank` 调和衰减聚合，再以对象或责任群体作为全局结算单元；不另设对象硬上限。正负各按通用12个对象上限和对象尾部衰减结算。任用领域只作检索标签。相同责任链跨期或换名仍须合并，只有目标、权限边界或独立结果不同的责任链才能进入下一顺位；不得用重复史料制造额外顺位。

```text
material_weight(rank) = 1 / rank
event_weight(rank) = 1 / rank
object_weight(rank) = 1 / rank ^ 0.5

positive_signal = 1.5 × sum(settled_object_value × object_weight)
negative_signal = 1.0 × sum(settled_object_value × object_weight)
appointment_delegation.rule_raw_net = positive_signal - negative_signal
```

## 四、建立团队 `team_building`

本分项以“皇帝—时间窗口”为唯一计分单元。人物能力与政治风险分别计算，不得因政治风险降低人才等级；成员功能统一归为战略决策、公共治理、专业执行、纠错反馈四类。军事只是专业执行的一种，法制、财政、工程、外交、教育文化等可按实际责任提供同等专业功能；四类只用于判断团队互补性，不形成职业配额或必填槽位。

```text
positive_pool = sum(talent_value)
negative_member_value = political_risk_severity_value

negative_pool = sum(negative_member_value)

team_building.positive_signal =
  positive_pool × functional_complementarity_factor × long_term_stability_factor

team_building.negative_signal = negative_pool

team_building.rule_raw_net = team_building.positive_signal - team_building.negative_signal
```

正池最多冻结8名能够代表窗口团队结构的成员，负池最多冻结3名在窗口内实际暴露风险的成员。成员冻结由人工在数值投影前完成，不按人才档位或计算后数值自动取前N名。正池预算已满后，新增同质成员只补充团队 lineage；只有可能改变互补性、稳定性或现有成员代表性的材料才重新进入 Judge。

正池成员还必须通过非递归归责门：统治者本人须有直接选拔、任命、调入、维持，或授予独立国家责任的行为。下属、皇子、藩王和方面统帅自行建立的幕府或班底，默认只归其直接组织者；上级的例行官名批准、同朝任职或授权该组织者，不得使上级递归继承整套下属团队。只有统治者后来以独立行为将该人纳入本人责任体系时，才从该节点起计入。

团队成员已经受正负池人数预算约束，不再叠加名次衰减。冻结成员在各自池内按其人才值或负面成员值全额进入求和，成员顺序仅用于可读展示，不影响数值。

### 1. 人才能力档位 `talent_quality_factor`

人才等级的事实门槛、成果归并和跨领域等价路径统一见 `docs/证据规则/公共成果登记与人物画像规则.md`，执行合同为 `config/talent-grade-v11-domain-equivalent-historic.yml`。本分项只把已经成立的公共档位映射为团队正池值，不在这里重新定档。

| 公共档位 | 团队正池值 |
| --- | ---: |
| `ordinary` | 0.35 |
| `usable` | 0.55 |
| `important` | 0.90 |
| `top` | 1.20 |
| `historic` | 1.60 |

### 2. 政治风险严重度 `political_risk_severity`

政治风险的事实门槛、排除项、严重度与影响范围统一见 `docs/证据规则/公共成果登记与人物画像规则.md`，执行合同为 `config/political-risk.yml`。本分项只消费当前皇帝窗口内已经成立的公共风险档位。

| 公共严重度 | 团队负池值 |
| --- | ---: |
| `limited` | 0.25 |
| `material` | 0.55 |
| `serious` | 0.75 |
| `major` | 1.00 |
| `systemic` | 1.35 |

### 3. 负面类型

公共风险类型只用于归责与去重，不附加本分项数值。

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

功能互补和长期稳定是正向团队结构系数，只作用于正池。负池按实际暴露风险的严重度直接求和，不因正向团队越互补、越稳定而被放大或缩小。

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
| `exceptional_dense_sustained_feedback` | 长期、高密度容纳重大或犯颜反馈；可以集中于一个关键专业领域，也可以跨领域 | 1.70 |
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

政策、行政、军事、专业、人事等只作场景标签，不设必填项。独立反馈—回应—安全—修复链先做对象内密度控制，再按通用12条上限和尾部衰减结算：

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
| `key_public_power_or_succession` | 国家中枢、关键地方、重大军政、全国核心专业系统或继承关键岗位 | 1.15 |

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

中枢、军事、地方、宫廷、宗室、储位和选任制度只作场景标签。独立私人关系—公共任用影响链先做对象内密度控制，再按通用12条上限和尾部衰减结算：

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
