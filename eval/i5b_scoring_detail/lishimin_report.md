# 李世民当前计分详情

> 本报告仅展示当前声明工作集的 shadow raw signal，不是45分、档位或排名。

## 汇总

| Rule | 正向 | 负向 | 净值 | 权重 | 加权贡献 | 历史覆盖 |
|---|---:|---:|---:|---:|---:|---|
| 人才发现 (`talent_discovery`) | 4.712 | 0.000 | 4.712 | 0.190 | 0.895 | `unassessed` |
| 任用授权 (`appointment_delegation`) | 10.722 | 0.000 | 10.722 | 0.360 | 3.860 | `unassessed` |
| 团队建设 (`team_building`) | 14.120 | 0.922 | 13.198 | 0.210 | 2.772 | `unassessed` |
| 容才 (`tolerate_talent`) | 11.006 | 0.653 | 10.353 | 0.180 | 1.864 | `unassessed` |
| 反任人唯亲 (`anti_nepotism`) | 0.000 | 0.000 | 0.000 | 0.060 | 0.000 | `unassessed` |

- 当前 declared-workset weighted raw signal：`9.390`
- 历史覆盖完成：`0/5`
- 正式45分、tier、排名：均未生成

### 通用证据因子

- 公式：`evidence_factor = clamp(attribution_factor * source_factor * context_factor, 0.45, 1.25)`
- 取值范围：`0.45` 至 `1.25`

## 人才发现 (`talent_discovery`)

- 当前净值：`4.712 - 0.000 = 4.712`
- 加权贡献：`4.712 × 0.190 = 0.895`
- 投影模式：`v4_joint_factor_projection`
- 聚合策略：`v3_legacy_object_density-v1`
- 公式：`direction_sign * discovery_level * talent_quality_factor * channel_factor * evidence_factor`
- 明细对账：`reconciled`（`joint_projection_report`）

### 因子档位

- **识才方向** (`direction_sign`)：区分成功识才与错失、压制人才。
  - **正向识才** (`positive`) = `1.0`：皇帝有效发现并转化人才。
  - **错失或压制识才** (`missed_or_suppressed_discovery`) = `-1.0`：可识别人才被忽视、阻断或压制。
- **发现强度** (`discovery_level`)：衡量从被动获知到跨障碍主动识别的强度。
  - **被动闻名** (`passive_reputation`) = `0.6`：主要依靠既有名望进入视野。
  - **荐举进入** (`recommendation_entry`) = `0.8`：经他人荐举进入候选池，皇帝验证有限。
  - **皇帝验证并试用** (`attributable_interview_trial_or_appointment`) = `1.0`：皇帝通过面试、试用或首次实质任命完成可归责验证。
  - **跨障碍识才** (`difficult_cross_boundary_discovery`) = `1.2`：皇帝主动跨越阵营、身份或接近障碍完成识别。
- **人才质量档** (`talent_quality_factor`)：使用版本化人物画像中的有效人才档。
  - **普通人才** (`ordinary`) = `0.6`：能力和贡献处于一般可用以下或边界水平。
  - **可用人才** (`usable`) = `0.9`：能稳定承担有限职责。
  - **重要人才** (`important`) = `1.15`：在重要职责或成果中有明确作用。
  - **顶级人才** (`top`) = `1.45`：属于同时代相关领域第一梯队。
  - **历史级人才** (`historic`) = `1.8`：在多个国家级成果或长期结构中具有时代塑造作用。
- **识才渠道** (`channel_factor`)：衡量识才是单一个案、跨身份渠道还是可重复机制。
  - **单一个案** (`single_case`) = `1.0`：只有一次可定位的识才事件。
  - **跨身份或阵营** (`cross_identity_or_camp`) = `1.1`：识才突破既有身份、门第或阵营边界。
  - **可重复识才机制** (`repeatable_discovery_mechanism`) = `1.2`：多个独立案例证明同一稳定渠道持续运行。

### 计入材料

| 对象 | 单元/材料 | 方向 | 材料分 | 排名权重/加权值 | 因子选择 |
|---|---|---|---:|---|---|
| 马周 | `REU-LSM-MAZHOU-DISCOVERY-OPEN-v1` | positive | 1.837 | — / — | 直接归责[attribution_factor=direct](1.0)；跨身份或阵营[channel_factor=cross_identity_or_camp](1.1)；直击核心机制[context_factor=core_mechanism_direct](1.1)；正向识才[direction_sign=positive](1.0)；跨障碍识才[discovery_level=difficult_cross_boundary_discovery](1.2)；完整直接链[source_factor=complete_direct_chain](1.1)；重要人才[talent_quality_factor=important](1.15) |
| 房玄龄 | `REU-LSM-FANGXUANLING-DISCOVERY-OPEN-v1` | positive | 2.875 | — / — | 直接归责[attribution_factor=direct](1.0)；跨身份或阵营[channel_factor=cross_identity_or_camp](1.1)；直击核心机制[context_factor=core_mechanism_direct](1.1)；正向识才[direction_sign=positive](1.0)；跨障碍识才[discovery_level=difficult_cross_boundary_discovery](1.2)；完整直接链[source_factor=complete_direct_chain](1.1)；历史级人才[talent_quality_factor=historic](1.8) |

### 限制

- 当前统治期口径排除即位前的张亮荐举事件，其条件影子分不进入净值。
- 历史正反候选人口尚未穷尽，4.712是当前已投影工作集净值。

### Lineage

- `eval/i5b_joint_projection_scored_shadow/talent_discovery_report.json`
- `eval/v3_claim_migration/lishimin_first_cohort_pre_source_review_report.json`

## 任用授权 (`appointment_delegation`)

- 当前净值：`10.722 - 0.000 = 10.722`
- 加权贡献：`10.722 × 0.360 = 3.860`
- 投影模式：`exact_v4_option_mapping`
- 聚合策略：`v3-native-density-decay-20260711`
- 公式：`appointment_importance * appointment_effect * continuity_factor * evidence_factor`
- 明细对账：`reconciled`（`appointment_expanded_shadow`）

### 因子档位

- **任用责任重要度** (`appointment_importance`)：只按授权当时的责任域和权力范围判断。
  - **名义或轻量职责** (`nominal_or_light`) = `0.6`：权限有限，主要是名义、顾问或轻量任务。
  - **实质但有界职责** (`real_bounded`) = `1.0`：有真实权限，但责任域明确且有限。
  - **重要军政职责** (`major_affairs`) = `1.25`：承担重要军政、方面或中枢职责。
  - **国家关键或长期职责** (`critical_national_or_long_term`) = `1.4`：直接涉及国家全局、战略地域、制度形成或长期总责。
- **人岗配置结果** (`appointment_effect`)：衡量任用本身产生的直接履职反馈和损益。
  - **弱反馈** (`weak_feedback`) = `0.4`：只有有限履职或结果证据。
  - **正常成功** (`normal_success`) = `1.0`：人岗适配并产生稳定、可归责的正常结果。
  - **重大成功** (`major_success`) = `1.5`：产生异常显著且直接归属于人岗配置的结果。
  - **结果不佳** (`poor_result`) = `-0.8`：任用产生明确但有限的负面结果。
  - **重大直接损害** (`major_direct_damage`) = `-1.8`：产生重大、一次性的直接损害。
  - **持续结构损害** (`structural_continuing_damage`) = `-2.6`：损害跨期影响制度、组织能力或后续治理。
- **授权连续性** (`continuity_factor`)：衡量一次性任用、稳定履职或多阶段重复授权。
  - **短期或一次性** (`short_or_one_off`) = `0.85`：明确为一次任务或缺乏持续观察。
  - **稳定授权** (`stable`) = `1.0`：同一授权下有至少两个可区分的履职或反馈观察。
  - **长期多阶段授权** (`long_term_multi_stage`) = `1.15`：至少两次可区分的皇帝授权决定形成跨阶段复用。

### 计入材料

| 对象 | 单元/材料 | 方向 | 材料分 | 排名权重/加权值 | 因子选择 |
|---|---|---|---:|---|---|
| 房玄龄 | `REU-LSM-FANGXUANLING-CENTRAL-AUTHORITY-v1` | — | 3.01875 | 1.0 / 4.528125 |  |
| 李靖 | `REU-LSM-LIJING-MILITARY-AUTHORITY-v1` | — | 3.01875 | 0.707106781187 / 3.20186789356 |  |
| 马周 | `REU-LSM-MAZHOU-AUTHORIZATION-v1` | — | 1.9481 | 0.57735026919 / 1.687104089112 |  |
| 魏徵 | `REU-LSM-WEIZHENG-APPOINTMENT-v1` | — | 1.7394 | 0.5 / 1.30455 |  |

### 排除或净增为零

- claim=CLMK-16700995A10383DDB30D；conditional_material_score=0.393；current_net_addition=0；person=高士廉；reason=与马周既有集体留辅授权弧碰撞
- claim=CLMK-83BDFCBE319619857BEB；conditional_material_score=0.531；current_net_addition=0；person=萧瑀；reason=多Claim任用弧和V4史源重绑未闭合

### 限制

- 四个既有人工作集按人物层平方根衰减和1.5正向lane计算；历史任用正负事件尚未穷尽。
- 高士廉留辅与马周既有授权弧碰撞，净增为0；萧瑀弧未完成回源和多Claim合并，净增为0。

### Lineage

- `eval/appointment_delegation_v3_parity_demo/report.json`
- `eval/appointment_delegation_factor_open_development_v2/factor_gold.yml`
- `eval/appointment_delegation_factor_sealed_holdout_v2/factor_gold.yml`
- `eval/i5b_ruler_rule_net/lishimin_appointment_shadow.yml`
- `eval/v3_claim_migration/lishimin_first_cohort_pre_source_review_report.json`

补充明细源：
- `appointment_parity_report`：`eval/appointment_delegation_v3_parity_demo/report.json`

## 团队建设 (`team_building`)

- 当前净值：`14.120 - 0.922 = 13.198`
- 加权贡献：`13.198 × 0.210 = 2.772`
- 投影模式：`v4_person_profile_and_team_window`
- 聚合策略：`v3-team-object-pool-v1`
- 公式：`negative_pool=sum(negative_team_contribution_rank / rank ^ 0.5)；negative_signal=negative_pool * role_complementarity_factor * long_term_stability_factor；negative_team_contribution=negative_talent_severity_value * negative_talent_class_relevance；positive_pool=sum(talent_quality_factor_rank / rank ^ 0.5)；positive_signal=positive_pool * role_complementarity_factor * long_term_stability_factor；rule_raw_net=positive_signal - negative_signal`
- 明细对账：`reconciled`（`team_roster_shadow`）

### 因子档位

- **团队成员人才档** (`talent_quality_factor`)：每名成员进入正向人才池的基础值。
  - **普通** (`ordinary`) = `0.35`：普通人才基础值。
  - **可用** (`usable`) = `0.55`：可用人才基础值。
  - **重要** (`important`) = `0.9`：重要人才基础值。
  - **顶级** (`top`) = `1.2`：顶级人才基础值。
  - **历史级** (`historic`) = `1.6`：历史级人才基础值。
- **负向人才严重度** (`negative_talent_severity_value`)：衡量窗口内已实现负向行为的严重程度。
  - **轻微** (`minor`) = `0.2`：有限且可控的负向影响。
  - **实质** (`material`) = `0.45`：已产生明确实质损害。
  - **重大** (`major`) = `0.8`：对团队或政权造成重大损害。
  - **历史级损害** (`historic`) = `1.2`：产生长期或时代级结构损害。
- **负向类型相关度** (`negative_talent_class_relevance`)：衡量负向人物类型与团队建设规则的相关程度。
  - **谄媚者** (`sycophant`) = `0.8`：以迎合削弱真实反馈。
  - **私宠** (`favorite`) = `0.7`：主要依靠私人偏爱进入核心。
  - **滥权者** (`power_abuser`) = `1.0`：利用职位破坏组织与公共权力。
  - **构陷者** (`framer`) = `1.0`：通过构陷破坏人才安全和团队协作。
  - **榨取型官员** (`extractive_official`) = `0.9`：以职位榨取资源并损害治理。
  - **酷吏** (`cruel_official`) = `0.9`：以残酷执法破坏治理与人才安全。
  - **无能致害** (`incompetent_harmful`) = `1.0`：因能力不足造成明确损害。
  - **叛乱行为者** (`traitorous_actor`) = `0.8`：在当前皇帝窗口内实施叛乱或严重背叛。
  - **混合或争议** (`mixed_or_disputed`) = `0.5`：负向类型存在但归类或责任有争议。
- **角色互补度** (`role_complementarity_factor`)：衡量决策、行政、军事、纠错四类核心角色覆盖。
  - **同质化** (`homogeneous`) = `0.9`：核心角色高度集中。
  - **普通双角色** (`ordinary_two`) = `1.0`：稳定覆盖两个核心角色。
  - **强三角色** (`strong_three`) = `1.1`：稳定覆盖三个核心角色。
  - **四角色均衡** (`balanced_four`) = `1.2`：四类核心角色均有有效成员。
- **团队长期稳定性** (`long_term_stability_factor`)：衡量团队结构在窗口内是否持续、可管理并跨阶段运行。
  - **碎片化** (`fragmented`) = `0.85`：团队结构短促或彼此割裂。
  - **强制更替崩塌** (`forced_turnover_collapse`) = `0.85`：频繁清洗或强制更替导致结构失效。
  - **稳定但狭窄** (`stable_but_narrow`) = `0.85`：团队稳定但角色或人才层次过窄。
  - **窗口内稳定** (`stable_window`) = `1.0`：在当前观察窗口内保持稳定。
  - **可管理更替** (`managed_turnover`) = `1.1`：人员更替存在但核心功能持续。
  - **跨阶段持久** (`durable_multi_stage`) = `1.2`：多阶段保持角色互补和核心功能。

### 团队成员池

| 人物 | 人才档 | 来源 | 角色 | 窗口负向 |
|---|---|---|---|---|
| 房玄龄 | `historic` | `self_selected` | decision、administration | — |
| 李靖 | `historic` | `inherited_and_retained` | military、decision | — |
| 李绩 | `historic` | `inherited_and_retained` | military、decision | — |
| 苏定方 | `historic` | `self_selected` | military | — |
| 杜如晦 | `top` | `self_selected` | decision、administration | — |
| 魏徵 | `top` | `self_selected` | correction、decision | — |
| 长孙无忌 | `top` | `self_selected` | decision、administration | — |
| 马周 | `important` | `self_selected` | administration、correction | — |
| 褚遂良 | `important` | `self_selected` | correction、administration | — |
| 戴胄 | `important` | `self_selected` | administration、correction | — |
| 虞世南 | `important` | `self_selected` | correction、administration | — |
| 高士廉 | `important` | `self_selected` | administration、decision | — |
| 温彦博 | `important` | `recalled` | administration、decision | — |
| 萧瑀 | `important` | `inherited_and_retained` | decision、administration | — |
| 侯君集 | `important` | `self_selected` | military、decision | traitorous_actor/major |
| 尉迟敬德 | `important` | `self_selected` | military | — |
| 秦琼 | `important` | `self_selected` | military | — |
| 段志玄 | `important` | `self_selected` | military | — |
| 唐俭 | `important` | `self_selected` | administration、decision | — |
| 王玄策 | `important` | `self_selected` | military、administration | — |
| 屈突通 | `important` | `inherited_and_retained` | military、administration | — |
| 王珪 | `usable` | `self_selected` | correction、decision | — |
| 岑文本 | `usable` | `self_selected` | administration、correction | — |
| 张亮 | `usable` | `self_selected` | administration、military | — |
| 李君羡 | `usable` | `self_selected` | military | — |

### 阻断或排除候选

- disposition=blocked_missing_v4_profile；person=长孙顺德
- disposition=blocked_missing_v4_profile；person=张公谨
- disposition=blocked_missing_v4_profile_and_window_rebind；person=程知节
- disposition=excluded_no_substantive_window_evidence；person=刘弘基
- disposition=blocked_indirect_only_and_missing_v4_profile；person=刘洎
- disposition=blocked_no_direct_window_claim；person=于志宁

### 尚未逐项处置人物

- 封德彝
- 宇文士及
- 杨师道
- 刘洎
- 孔颖达
- 令狐德棻
- 韦挺
- 李道宗
- 薛万彻
- 李大亮
- 阿史那社尔
- 契苾何力
- 张士贵
- 薛万均
- 孙伏伽
- 张行成
- 崔仁师
- 许敬宗

### 当前结构因子

- `talent_depth`：`multi_historic`
- `functional_complementarity`：`balanced_four`
- `continuity_structure`：`durable_multi_stage`
- `role_complementarity_factor`：`1.2`
- `long_term_stability_factor`：`1.2`

### 计算展开

- `grade_counts`：`historic=4；important=14；ordinary=0；top=3；usable=4`
- `positive_pool`：`9.805485068533`
- `positive_signal`：`14.119898498688`
- `negative_pool`：`0.64`
- `negative_signal`：`0.9216`
- `rule_raw_net`：`13.198298498688`
- `conservative_rule_raw_net`：`9.552521215929`

### 限制

- 25人建议计算池已按贞观窗口实质履职与有效画像过滤，但完整历史团队候选处置尚未人工冻结。
- 正向池使用互补性1.2、稳定性1.2；负向池仅计李世民窗口内暴露的侯君集，不回灌后朝政治风险。

### Lineage

- `eval/team_building_v8_scored_shadow/report.json`
- `eval/i5b_ruler_rule_net/lishimin_team_roster_shadow.yml`
- `eval/v3_claim_migration/lishimin_source_snapshot.json`
- `eval/v3_person_profile_migration/authorized_profile_promotion.json`
- `eval/v3_person_profile_migration/supplemental_profile_promotion.json`

补充明细源：
- `team_scored_shadow_report`：`eval/team_building_v8_scored_shadow/report.json`

## 容才 (`tolerate_talent`)

- 当前净值：`11.006 - 0.653 = 10.353`
- 加权贡献：`10.353 × 0.180 = 1.864`
- 投影模式：`v4_joint_factor_projection`
- 聚合策略：`v3_legacy_object_density-v1`
- 公式：`negative=-handling_severity * target_fault_factor * evidence_factor；positive=feedback_entry * expression_safety * protection_repair * evidence_factor`
- 明细对账：`reconciled`（`joint_projection_report`）

### 因子档位

- **反馈入口强度** (`feedback_entry`)：衡量从单次采纳、重复反馈、跨阶段持续、高密度跨领域谏诤到正式反馈通道持续运行的层级。次数不线性累加，高档必须同时有时间、领域和独立事件覆盖。
  - **单次采纳或容忍** (`single_acceptance_or_tolerance`) = `0.7`：只证明一次建议被采纳，或一次表达未受压制。
  - **多次反馈且仍被保留** (`repeated_feedback_retained`) = `1.0`：同一臣子有两个以上独立反馈事件，皇帝未因此排斥其履职；尚不证明长期跨阶段。
  - **跨阶段持续反馈** (`durable_multi_stage_feedback`) = `1.3`：反馈和容纳跨越统治期的多个明显阶段，且有独立后续证明表达者持续履职。仅几次跨阶段采纳最高落在此档。
  - **高密度跨领域长期犯颜** (`exceptional_dense_cross_domain_remonstrance`) = `1.7`：在长时段内存在大量可分辨谏诤，覆盖多个重大政务领域，包含逆耳或犯颜情形，且皇帝仍持续容纳、采用并保留其反馈职责。不得只凭一个模糊次数或史料篇幅推出。
  - **制度化反馈入口** (`institutionalized_feedback_entry`) = `2.0`：皇帝预先建立正式反馈通道，且该通道跨多个独立事件持续运行；通常应面向多名表达者或正式职能主体。不能由某一臣子反复进谏、单次求言诏令或事后采纳推出。（当前投影状态=已有已接受的shadow投影材料；合同可达性=已在李世民求谏机制shadow材料中达到）
- **表达安全** (`expression_safety`)：衡量表达者在反馈之后的人身、职业和持续表达安全。
  - **紧张或依赖个案** (`tense_or_case_dependent`) = `0.8`：表达受到威胁、冲突或个案恩免影响。
  - **基本安全** (`basically_safe`) = `1.0`：有晚于回应的独立观察证明未遭报复并继续履职。
  - **主动保护或鼓励** (`actively_protected_or_encouraged`) = `1.15`：皇帝明确保护表达者或持续鼓励其反馈。
- **保护与修复** (`protection_repair`)：衡量冲突后是否恢复职位、信用或反馈关系。
  - **无特殊保护修复** (`none`) = `1.0`：未发生需要计分的保护或修复动作。
  - **恢复或平反** (`restoration_or_rehabilitation`) = `1.1`：皇帝恢复职位、名誉或撤销部分损害。
  - **主动保护或完整修复** (`active_protection_or_trust_repair`) = `1.15`：皇帝主动保护表达者或实质恢复完整信任。
- **处置严重度** (`handling_severity`)：衡量因反馈或专业独立遭受的已实现处置。
  - **象征性或轻处分** (`symbolic_or_light`) = `0.6`：信用撤销、轻微惩戒或有限公开压制。
  - **贬黜或压制** (`demotion_or_suppression`) = `1.2`：已实现职业贬黜、排除或表达压制。
  - **监禁或严重非永久伤害** (`imprisonment_or_severe_nonpermanent_harm`) = `1.8`：已实现监禁、酷刑以外的严重伤害或长期职业损害。
  - **处死或逼令自尽** (`execution_or_forced_suicide`) = `2.6`：已导致本人被处死或被迫自尽。
  - **集团或系统清洗** (`clan_or_systemic_purge`) = `3.2`：伤害扩展到家族、群体或制度性清洗。
- **对象过错校准** (`target_fault_factor`)：根据表达者自身过错校准负向归责，避免把坐实重大过错全部算成容才失败。
  - **因反馈受害或被构陷** (`framed_or_harmed_for_feedback`) = `1.5`：没有重大过错，伤害直接由反馈触发。
  - **轻过重罚** (`minor_fault_disproportionate_harm`) = `1.2`：有轻微过错但处置明显失衡。
  - **过错未知** (`fault_unknown`) = `1.0`：现有证据无法确定对象过错。
  - **争议嫌疑** (`disputed_suspicion`) = `0.9`：存在嫌疑但未形成可靠坐实链。
  - **重大过错但处置过重** (`major_fault_but_excessive_harm`) = `0.5`：重大过错成立，但伤害仍超过必要范围。
  - **谋反坐实后的极弱残余** (`proven_rebellion_residual_talent_harm`) = `0.2`：谋反坐实，仅保留极弱的过度伤害残余。

### 计入材料

| 对象 | 单元/材料 | 方向 | 材料分 | 排名权重/加权值 | 因子选择 |
|---|---|---|---:|---|---|
| 贞观求谏机制 | `TT-LSM-INSTITUTIONAL-REM-01` | positive | 2.783 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；制度化反馈入口[feedback_entry=institutionalized_feedback_entry](2.0)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1) |
| 魏徵 | `TT-O01` | positive | 2.057 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；基本安全[expression_safety=basically_safe](1.0)；高密度跨领域长期犯颜[feedback_entry=exceptional_dense_cross_domain_remonstrance](1.7)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1) |
| 虞世南 | `TT-LSM-YSN-01` | positive | 1.392 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；多次反馈且仍被保留[feedback_entry=repeated_feedback_retained](1.0)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1) |
| 褚遂良 | `TT-LSM-CSL-01` | positive | 1.573 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；基本安全[expression_safety=basically_safe](1.0)；跨阶段持续反馈[feedback_entry=durable_multi_stage_feedback](1.3)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1) |
| 马周 | `TT-LSM-MZ-01` | positive | 1.392 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；多次反馈且仍被保留[feedback_entry=repeated_feedback_retained](1.0)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1) |
| 戴胄 | `TT-LSM-DZ-01` | positive | 1.809 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；跨阶段持续反馈[feedback_entry=durable_multi_stage_feedback](1.3)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1) |
| 魏徵身后信用 | `TT-O05` | negative | 0.653 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；象征性或轻处分[handling_severity=symbolic_or_light](0.6)；完整直接链[source_factor=complete_direct_chain](1.1)；争议嫌疑[target_fault_factor=disputed_suspicion](0.9) |

### 限制

- 当前正向池包含贞观求谏机制2.783、魏徵2.057、虞世南1.392、褚遂良1.573、马周1.392、戴胄1.809；TT-O05身后信用撤销仍独立结算负向0.653。
- 制度单元只结算正式求谏通道的建立与持续运行；个人单元只结算个人反馈留任和表达安全，不重复结算同一收益。
- 103条V3 route线索已完成27人物组级盘点，但尚未完成102个事件组逐项处置，萧瑀、王珪、刘弘基、长孙无忌、房玄龄、温彦博仍待回源；历史覆盖处于in_progress而非完整。

### Lineage

- `eval/i5b_joint_projection_scored_shadow/tolerate_talent_report.json`
- `eval/v3_claim_migration/lishimin_source_snapshot.json`
- `eval/v3_claim_migration/lishimin_first_cohort_pre_source_review_report.json`
- `eval/i5b_ruler_rule_net/lishimin_tolerate_anti_shadow.yml`
- `eval/i5b_ruler_rule_net/lishimin_tt_o01_source_rebind.json`
- `eval/i5b_ruler_rule_net/lishimin_tolerate_talent_expansion_v1.json`
- `eval/i5b_ruler_rule_net/lishimin_tolerate_talent_institutional_channel_v1.json`

补充明细源：
- `rule_lane_shadow`：`eval/i5b_ruler_rule_net/lishimin_tolerate_anti_shadow.yml`
- `source_rebind_record`：`eval/i5b_ruler_rule_net/lishimin_tt_o01_source_rebind.json`
- `source_rebind_batch`：`eval/i5b_ruler_rule_net/lishimin_tolerate_talent_expansion_v1.json`
- `source_rebind_record`：`eval/i5b_ruler_rule_net/lishimin_tolerate_talent_institutional_channel_v1.json`

补充回源观察：
- `贞观八年`：李世民以魏徵负责箴规君失、不可一日离左右为由，不遣其出任诸道黜陟大使。
- `贞观十年`：魏徵因目疾请求散官后，李世民仍任其为特进、知门下事，使其继续参议得失。
- `贞观十六年`：李世民任魏徵为太子太师，并令其知门下省事如故，证明其晚期仍保有中枢职责。
- `贞观十六年至魏徵卒后初期`：魏徵病重时，李世民为其营宅并两次临视；魏徵去世后初期，李世民废朝并追赠。
- `None`：None
- `None`：None
- `None`：None
- `None`：None

## 反任人唯亲 (`anti_nepotism`)

- 当前净值：`0.000 - 0.000 = 0.000`
- 加权贡献：`0.000 × 0.060 = 0.000`
- 投影模式：`v4_episode_and_aggregate_joint_projection`
- 聚合策略：`v3_legacy_object_density-v1`
- 公式：`negative=-favoritism_intensity * office_weight * displacement_harm * evidence_factor；positive=selection_openness * institutionalization * office_weight * evidence_factor`
- 明细对账：`reconciled`（`rule_lane_shadow`）

### 因子档位

- **选任开放度** (`selection_openness`)：衡量选任是否抵抗私人关系并保持能力或正式程序基础。
  - **个案抵抗私人干预** (`avoids_private_interference_case`) = `0.7`：在单一个案中拒绝私人关系干预。
  - **能力或正式程序选任** (`merit_or_formal_basis`) = `1.0`：选任明确基于能力、功绩或正式程序。
  - **跨身份开放选任** (`cross_identity_open_selection`) = `1.25`：稳定突破亲缘、门第、地域或阵营边界。
  - **制度化防亲** (`institutionalized_anti_nepotism`) = `1.4`：形成可重复、可审计的制度性防亲机制。
- **防亲制度化程度** (`institutionalization`)：衡量防亲行为是单次、重复惯例还是持久制度。
  - **单次事件** (`single_event`) = `0.8`：只有一次可定位的防亲或纠偏。
  - **重复稳定实践** (`repeated_stable_practice`) = `1.0`：多次独立事件证明稳定惯例。
  - **持久制度** (`durable_institution`) = `1.15`：形成正式、持续且可审计的制度。
- **公共职位权重** (`office_weight`)：衡量私人关系污染或防亲作用涉及的公共权力重要度。
  - **普通职位** (`ordinary`) = `0.8`：一般公共职位或有限权力。
  - **重要职位** (`important`) = `1.0`：重要中枢、方面或专业权力。
  - **中枢军权或继承关键** (`central_military_or_succession`) = `1.15`：涉及中枢核心、军权或继承秩序。
- **私人偏任强度** (`favoritism_intensity`)：衡量私人关系替代能力和程序的程度。
  - **可见私人关系** (`visible_private_relation`) = `0.7`：私人关系可见，但未证明替代能力。
  - **私情压过能力** (`private_relation_over_merit`) = `1.1`：私人关系明确压过能力或程序。
  - **持续干预核心任用** (`continuing_core_appointment_interference`) = `1.5`：私人关系跨期干预核心职位。
  - **私人网络系统俘获** (`systemic_private_network_capture`) = `2.0`：私人网络系统性控制关键任用和公共权力。
- **排挤与结构损害** (`displacement_harm`)：衡量私人偏任对合格人才、关键职位和组织结构的损害。
  - **仅观感损害** (`optics_only`) = `0.7`：主要损害公信力，未证明实质排挤。
  - **合格人才或关键职位受损** (`qualified_people_or_key_office_harmed`) = `1.0`：已排挤合格人才或污染关键职位。
  - **团队政策或表达结构受损** (`team_policy_or_expression_structure_harmed`) = `1.4`：破坏团队互补、政策质量或反馈结构。
  - **持久制度污染** (`durable_institutional_pollution`) = `2.0`：私人网络造成跨期制度性污染。

- 当前拒绝原因：功臣赏次尚未通过公共任用或职务影响适用性Gate

- 条件敏感性（不计入当前净值）：`factor_choice=institutionalization=single_event；office_weight=ordinary；selection_openness=avoids_private_interference_case；included_in_current_net=False；positive_material_range=0.493、0.542`

### 限制

- 神通争功虽呈现按功压过宗亲私情，但当前未证明功臣赏次构成公共任用或职务影响，严格净值为0。
- 不能把党项、乡党、亲礼、无朋党或未证实朋党指控当作本rule材料。

### Lineage

- `eval/v3_claim_migration/lishimin_source_snapshot.json#CLMK-7E2D72302A9C88F2CE3C`
- `eval/v3_claim_migration/lishimin_first_cohort_pre_source_review_report.json`
- `eval/i5b_ruler_rule_net/lishimin_tolerate_anti_shadow.yml`

补充明细源：
- `joint_projection_report`：`eval/i5b_joint_projection_scored_shadow/anti_nepotism_report.json`

## 安全声明

- 本次导出模型调用：0
- 本次导出数据库写入：0
- 未执行动态映射，未生成正式评分或排名
