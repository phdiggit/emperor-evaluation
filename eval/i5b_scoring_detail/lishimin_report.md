# 李世民当前计分详情

> 本报告仅展示当前声明工作集的 shadow raw signal，不是45分、档位或排名。

## 汇总

| Rule | 正向 | 负向 | 净值 | 权重 | 加权贡献 | 历史覆盖 |
|---|---:|---:|---:|---:|---:|---|
| 人才发现 (`talent_discovery`) | 4.015 | 0.000 | 4.015 | 0.190 | 0.763 | `coverage_complete` |
| 任用授权 (`appointment_delegation`) | 10.474 | 1.084 | 9.390 | 0.360 | 3.380 | `coverage_complete` |
| 团队建设 (`team_building`) | 13.285 | 0.922 | 12.364 | 0.210 | 2.596 | `coverage_complete` |
| 容才 (`tolerate_talent`) | 12.126 | 0.653 | 11.473 | 0.180 | 2.065 | `coverage_complete` |
| 反任人唯亲 (`anti_nepotism`) | 2.332 | 0.000 | 2.332 | 0.060 | 0.140 | `coverage_complete` |

- 当前 declared-workset weighted raw signal：`8.945`
- 历史覆盖完成：`5/5`
- 正式45分、tier、排名：均未生成

### 通用证据因子

- 公式：`evidence_factor = clamp(attribution_factor * source_factor * context_factor, 0.45, 1.25)`
- 取值范围：`0.45` 至 `1.25`

## 人才发现 (`talent_discovery`)

- 当前净值：`4.015 - 0.000 = 4.015`
- 加权贡献：`4.015 × 0.190 = 0.763`
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
| 岑文本 | `REU-LSM-CENWENBEN-DISCOVERY-HC-v1` | positive | 1.089 | — / — | 直接归责[attribution_factor=direct](1.0)；单一个案[channel_factor=single_case](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；正向识才[direction_sign=positive](1.0)；皇帝验证并试用[discovery_level=attributable_interview_trial_or_appointment](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)；可用人才[talent_quality_factor=usable](0.9) |
| 马周 | `REU-LSM-MAZHOU-DISCOVERY-HC-v1` | positive | 1.837 | — / — | 直接归责[attribution_factor=direct](1.0)；跨身份或阵营[channel_factor=cross_identity_or_camp](1.1)；直击核心机制[context_factor=core_mechanism_direct](1.1)；正向识才[direction_sign=positive](1.0)；跨障碍识才[discovery_level=difficult_cross_boundary_discovery](1.2)；完整直接链[source_factor=complete_direct_chain](1.1)；重要人才[talent_quality_factor=important](1.15) |
| 张玄素 | `REU-LSM-ZHANGXUANSU-DISCOVERY-HC-v1` | positive | 1.089 | — / — | 直接归责[attribution_factor=direct](1.0)；单一个案[channel_factor=single_case](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；正向识才[direction_sign=positive](1.0)；皇帝验证并试用[discovery_level=attributable_interview_trial_or_appointment](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)；可用人才[talent_quality_factor=usable](0.9) |

### 限制

- 张玄素版本化PersonProfile已补齐，李世民3个正式识才单元全部完成数值投影。
- 即位前识才链不计入626—649窗口。

### Lineage

- `eval/i5b_joint_projection_scored_shadow/talent_discovery_report.json`
- `eval/i5b_talent_discovery_zhangxuansu_profile_closeout/zhangxuansu_profile_closeout_audit_v1.json`

## 任用授权 (`appointment_delegation`)

- 当前净值：`10.474 - 1.084 = 9.390`
- 加权贡献：`9.390 × 0.360 = 3.380`
- 投影模式：`exact_v4_option_mapping`
- 聚合策略：`v3-native-density-decay-20260711`
- 公式：`appointment_importance * appointment_effect * continuity_factor * evidence_factor`
- 明细对账：`reconciled`（`appointment_parity_report`）

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

### 限制

- 173个V3路线提示已逐项处置；正式数值链只消费四个在位期最小充分单元。
- 侯君集的吐谷浑、高昌成功与高昌后控制失败合并在同一受任者单元，避免功劳和失控重复结算。

### Lineage

- `eval/i5b_appointment_delegation_historical_coverage/lishimin_scored_shadow_report_v1.json`
- `eval/i5b_appointment_delegation_historical_coverage/lishimin_formal_acceptance_v1.json`
- `eval/i5b_appointment_delegation_historical_coverage/lishimin_candidate_inventory_v1.json`

补充明细源：
- `appointment_expanded_shadow`：`eval/i5b_ruler_rule_net/lishimin_appointment_shadow.yml`

## 团队建设 (`team_building`)

- 当前净值：`13.285 - 0.922 = 12.364`
- 加权贡献：`12.364 × 0.210 = 2.596`
- 投影模式：`v4_person_profile_and_team_window`
- 聚合策略：`v3-team-object-pool-v1`
- 公式：`negative_pool=sum(negative_team_contribution_rank / rank ^ 0.5)；negative_signal=negative_pool * role_complementarity_factor * long_term_stability_factor；negative_team_contribution=negative_talent_severity_value * negative_talent_class_relevance；positive_pool=sum(talent_quality_factor_rank / rank ^ 0.5)；positive_signal=positive_pool * role_complementarity_factor * long_term_stability_factor；rule_raw_net=positive_signal - negative_signal`
- 明细对账：`reconciled`（`team_historical_scored_shadow`）

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
| 张亮 | `usable` | `formally_accepted_historical` | administration、military | — |
| 王玄策 | `important` | `formally_accepted_historical` | military、administration | — |
| 马周 | `important` | `formally_accepted_historical` | administration、correction | — |
| 尉迟敬德 | `important` | `formally_accepted_historical` | military | — |
| 唐俭 | `important` | `formally_accepted_historical` | administration、decision | — |
| 戴胄 | `important` | `formally_accepted_historical` | administration、correction | — |
| 李君羡 | `usable` | `formally_accepted_historical` | military | — |
| 李绩 | `important` | `formally_accepted_historical` | military、decision | — |
| 王珪 | `important` | `formally_accepted_historical` | correction、decision | — |
| 秦琼 | `important` | `formally_accepted_historical` | military | — |
| 长孙无忌 | `top` | `formally_accepted_historical` | decision、administration | — |
| 李靖 | `historic` | `formally_accepted_historical` | military、decision | — |
| 杜如晦 | `top` | `formally_accepted_historical` | decision、administration | — |
| 魏徵 | `top` | `formally_accepted_historical` | correction、decision | — |
| 褚遂良 | `important` | `formally_accepted_historical` | correction、administration | — |
| 萧瑀 | `important` | `formally_accepted_historical` | decision、administration | — |
| 侯君集 | `important` | `formally_accepted_historical` | military、decision | traitorous_actor/major |
| 屈突通 | `important` | `formally_accepted_historical` | military、administration | — |
| 房玄龄 | `historic` | `formally_accepted_historical` | administration、decision | — |
| 段志玄 | `important` | `formally_accepted_historical` | military | — |
| 岑文本 | `important` | `formally_accepted_historical` | administration、correction | — |
| 虞世南 | `top` | `formally_accepted_historical` | correction、administration | — |
| 高士廉 | `important` | `formally_accepted_historical` | administration、decision | — |
| 温彦博 | `important` | `formally_accepted_historical` | administration、decision | — |

### 当前结构因子

- `confidant_dependency`：`distributed`
- `continuity_structure`：`durable_multi_stage`
- `core_role_coverage`：`four_core`
- `functional_complementarity`：`balanced_four`
- `negative_profile_exposure`：`material_exposure`
- `talent_depth`：`multi_historic`

### 限制

- 24人核心名单均经独立V4 SourcePassage与版本化人物画像复核；其余候选保留supporting-only，不作零材料或负面成员。
- 本rule只结算人物池质量、角色互补与窗口风险，不重复结算成员任命、战果或规谏事件收益。

### Lineage

- `eval/i5b_team_building_historical_coverage/lishimin_scored_shadow_report_v2.json`
- `eval/i5b_team_building_historical_coverage/lishimin_frozen_roster_acceptance_v2.json`

补充明细源：
- `team_roster_shadow`：`eval/i5b_ruler_rule_net/lishimin_team_roster_shadow.yml`

## 容才 (`tolerate_talent`)

- 当前净值：`12.126 - 0.653 = 11.473`
- 加权贡献：`11.473 × 0.180 = 2.065`
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
| 王珪 | `TT-LSM-WG-WYB-ZXS-01` | positive | 1.120 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；单次采纳或容忍[feedback_entry=single_acceptance_or_tolerance](0.7)；主动保护或完整修复[protection_repair=active_protection_or_trust_repair](1.15)；完整直接链[source_factor=complete_direct_chain](1.1) |
| 魏徵身后信用 | `TT-O05` | negative | 0.653 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；象征性或轻处分[handling_severity=symbolic_or_light](0.6)；完整直接链[source_factor=complete_direct_chain](1.1)；争议嫌疑[target_fault_factor=disputed_suspicion](0.9) |

### 证据不足投影

- assertion_draft_refs=ASTA-636ED5C01C6EEC9FDB26、ASTA-DD8C06887DD43AEF1A3B；canonical_event_group=TT-LISHIMIN-WANGGUI-LUJIANG-REMONSTRANCE；missing_inputs=independent_repair_followup、positive_safety_followup；object_ref=PER-NAME-CANDIDATE-WANG-GUI；projection_basis=原文直接支持王珪提出异议，以及太宗虽未执行建议却重其言；同段态度不能同时替代独立的后续安全或修复观察，因此保留正式证据链但不作数值投影。；rule_evidence_unit_ref=REU-5CED06C9C02D66E8E2E0；ruler=李世民；semantic_fingerprint=63459497fcdff16c51fc1e356e1ab2ee2d02c2a6402b82d344aaa4f08d422f82；side=positive；source_refs=eval/i5b_tolerate_talent_historical_coverage/lishimin_formal_acceptance_v1.json#TT-LSM-WG-LUJIANG-01、SP-A1003A0417042BEBC5E5；subject=王珪；unit_ref=TT-LSM-WG-LUJIANG-01
- assertion_draft_refs=ASTA-46C5F1C35C01C32EBF11、ASTA-AE3B1916D0A29AF567EF；canonical_event_group=TT-LISHIMIN-FANGXUANLING-RECALL-REPAIR；missing_inputs=feedback_causal_link、positive_safety_followup；object_ref=PER-FANG-XUANLING；projection_basis=材料直接支持遣还后皇帝醒悟并召回，足以冻结修复事实；但最初遣还未被证明由房玄龄进谏触发，也没有独立后续安全观察，不能完成容才联合数值投影。；rule_evidence_unit_ref=REU-46B1976D29648908E796；ruler=李世民；semantic_fingerprint=e3421efc23cb77076b1010383bdb50cafea1fe39a0019a28655593348ef98436；side=positive；source_refs=eval/i5b_tolerate_talent_historical_coverage/lishimin_formal_acceptance_v1.json#TT-LSM-FXL-RECALL-01、SP-A7C6622A9E5F51AFAA26；subject=房玄齡；unit_ref=TT-LSM-FXL-RECALL-01
- assertion_draft_refs=ASTA-34462F7D3D1E17258C7A、ASTA-CEB454A9C6C28D88A126；canonical_event_group=TT-LISHIMIN-FANGXUANLING-GOGURYEO-FEEDBACK；missing_inputs=independent_repair_followup、positive_safety_followup；object_ref=PER-FANG-XUANLING；projection_basis=材料直接支持房玄龄在群臣莫敢谏的压力语境下反复劝止讨高丽，以及皇帝肯认其病中忧国；未直接支持政策采纳、制度性保护或不同观察的后续安全，故正式留链但不数值投影。；rule_evidence_unit_ref=REU-0AFEF154A53A9112765F；ruler=李世民；semantic_fingerprint=0403d0c0ed2268389664e6adfd9529391a8340a9ce5476a9d182950bea8cfffd；side=positive；source_refs=eval/i5b_tolerate_talent_historical_coverage/lishimin_formal_acceptance_v1.json#TT-LSM-FXL-GOGURYEO-01、SP-E0CFB170CC2196868092；subject=房玄齡；unit_ref=TT-LSM-FXL-GOGURYEO-01

### 限制

- 当前正向池在既有六个单元上新增王珪受压直言—次日修复1.120；TT-O05身后信用撤销仍独立结算负向0.653。
- 制度单元只结算正式求谏通道的建立与持续运行；个人单元只结算个人反馈留任和表达安全，不重复结算同一收益。
- 107条正式接受Assertion已按显式事件节点形成107个Episode和11个RuleEvidenceUnit；其中3个新增单元因缺少独立安全或因果后续仅保留证据链，不进入数值投影。

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

- 当前净值：`2.332 - 0.000 = 2.332`
- 加权贡献：`2.332 × 0.060 = 0.140`
- 投影模式：`v4_episode_and_aggregate_joint_projection`
- 聚合策略：`v3_legacy_object_density-v1`
- 公式：`negative=-favoritism_intensity * office_weight * displacement_harm * evidence_factor；positive=selection_openness * institutionalization * office_weight * evidence_factor`
- 明细对账：`reconciled`（`joint_projection_report`）

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

### 计入材料

| 对象 | 单元/材料 | 方向 | 材料分 | 排名权重/加权值 | 因子选择 |
|---|---|---|---:|---|---|
| 唐宗室封爵制度 | `REU-LSM-ANTI-NEPOTISM-ROYAL-TITLE-CORRECTION-v1` | positive | 1.232 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；单次事件[institutionalization=single_event](0.8)；重要职位[office_weight=important](1.0)；制度化防亲[selection_openness=institutionalized_anti_nepotism](1.4)；标准直接材料[source_factor=standard](1.0) |
| 秦府旧人任官优先诉求 | `REU-LSM-ANTI-NEPOTISM-QINFU-PREFERENCE-REFUSAL-v1` | positive | 1.100 | — / — | 直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；单次事件[institutionalization=single_event](0.8)；重要职位[office_weight=important](1.0)；跨身份开放选任[selection_openness=cross_identity_open_selection](1.25)；标准直接材料[source_factor=standard](1.0) |

### 限制

- 4个未通过公共权力、私人因果或排挤损害Gate的事实单元已显式排除为not_applicable，不按零材料处理。

### Lineage

- `eval/i5b_anti_nepotism_historical_coverage/lishimin_scored_shadow_report_v2.json`
- `eval/i5b_anti_nepotism_historical_coverage/lishimin_projection_inputs_v2.json`

补充明细源：
- `joint_projection_report`：`eval/i5b_joint_projection_scored_shadow/anti_nepotism_report.json`

## 安全声明

- 本次导出模型调用：0
- 本次导出数据库写入：0
- 未执行动态映射，未生成正式评分或排名
