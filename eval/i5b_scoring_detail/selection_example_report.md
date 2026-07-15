# 指定皇帝、臣子与 Rule 的计分详情

- 皇帝：李世民
- 臣子：魏徵、房玄龄
- Rules：talent_discovery、appointment_delegation、team_building、tolerate_talent
- 臣子检索范围：`selected_rulers`

> Rule 子集只展示加权 raw signal 小计；臣子条目只表示参与，不构成臣子个人分数。

## 皇帝：李世民

| Rule | 正向 | 负向 | 净值 | 权重 | 加权贡献 |
|---|---:|---:|---:|---:|---:|
| 人才发现 (`talent_discovery`) | 4.015 | 0.000 | 4.015 | 0.190 | 0.763 |
| 任用授权 (`appointment_delegation`) | 10.474 | 1.084 | 9.390 | 0.360 | 3.380 |
| 团队建设 (`team_building`) | 13.285 | 0.922 | 12.364 | 0.210 | 2.596 |
| 容才 (`tolerate_talent`) | 12.126 | 0.653 | 11.473 | 0.180 | 2.065 |

所选 Rule 加权 raw signal 小计：`8.805`

### 人才发现明细

- 公式：`direction_sign * discovery_level * talent_quality_factor * channel_factor * evidence_factor`
- 对账：`reconciled`
- Primary：`eval/i5b_joint_projection_scored_shadow/talent_discovery_report.json`
- **识才方向** (`direction_sign`)：区分成功识才与错失、压制人才。
  - 正向识才 (`positive`) = `1.0`：皇帝有效发现并转化人才。
  - 错失或压制识才 (`missed_or_suppressed_discovery`) = `-1.0`：可识别人才被忽视、阻断或压制。
- **发现强度** (`discovery_level`)：衡量从被动获知到跨障碍主动识别的强度。
  - 被动闻名 (`passive_reputation`) = `0.6`：主要依靠既有名望进入视野。
  - 荐举进入 (`recommendation_entry`) = `0.8`：经他人荐举进入候选池，皇帝验证有限。
  - 皇帝验证并试用 (`attributable_interview_trial_or_appointment`) = `1.0`：皇帝通过面试、试用或首次实质任命完成可归责验证。
  - 跨障碍识才 (`difficult_cross_boundary_discovery`) = `1.2`：皇帝主动跨越阵营、身份或接近障碍完成识别。
- **人才质量档** (`talent_quality_factor`)：使用版本化人物画像中的有效人才档。
  - 普通人才 (`ordinary`) = `0.6`：能力和贡献处于一般可用以下或边界水平。
  - 可用人才 (`usable`) = `0.9`：能稳定承担有限职责。
  - 重要人才 (`important`) = `1.15`：在重要职责或成果中有明确作用。
  - 顶级人才 (`top`) = `1.45`：属于同时代相关领域第一梯队。
  - 历史级人才 (`historic`) = `1.8`：在多个国家级成果或长期结构中具有时代塑造作用。
- **识才渠道** (`channel_factor`)：衡量识才是单一个案、跨身份渠道还是可重复机制。
  - 单一个案 (`single_case`) = `1.0`：只有一次可定位的识才事件。
  - 跨身份或阵营 (`cross_identity_or_camp`) = `1.1`：识才突破既有身份、门第或阵营边界。
  - 可重复识才机制 (`repeatable_discovery_mechanism`) = `1.2`：多个独立案例证明同一稳定渠道持续运行。
- 岑文本 / `REU-LSM-CENWENBEN-DISCOVERY-HC-v1` / 材料分 `1.089` / 因子：直接归责[attribution_factor=direct](1.0)；单一个案[channel_factor=single_case](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；正向识才[direction_sign=positive](1.0)；皇帝验证并试用[discovery_level=attributable_interview_trial_or_appointment](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)；可用人才[talent_quality_factor=usable](0.9)
- 马周 / `REU-LSM-MAZHOU-DISCOVERY-HC-v1` / 材料分 `1.837` / 因子：直接归责[attribution_factor=direct](1.0)；跨身份或阵营[channel_factor=cross_identity_or_camp](1.1)；直击核心机制[context_factor=core_mechanism_direct](1.1)；正向识才[direction_sign=positive](1.0)；跨障碍识才[discovery_level=difficult_cross_boundary_discovery](1.2)；完整直接链[source_factor=complete_direct_chain](1.1)；重要人才[talent_quality_factor=important](1.15)
- 张玄素 / `REU-LSM-ZHANGXUANSU-DISCOVERY-HC-v1` / 材料分 `1.089` / 因子：直接归责[attribution_factor=direct](1.0)；单一个案[channel_factor=single_case](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；正向识才[direction_sign=positive](1.0)；皇帝验证并试用[discovery_level=attributable_interview_trial_or_appointment](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)；可用人才[talent_quality_factor=usable](0.9)

### 任用授权明细

- 公式：`appointment_importance * appointment_effect * continuity_factor * evidence_factor`
- 对账：`reconciled`
- Primary：`eval/i5b_appointment_delegation_historical_coverage/lishimin_scored_shadow_report_v1.json`
- **任用责任重要度** (`appointment_importance`)：只按授权当时的责任域和权力范围判断。
  - 名义或轻量职责 (`nominal_or_light`) = `0.6`：权限有限，主要是名义、顾问或轻量任务。
  - 实质但有界职责 (`real_bounded`) = `1.0`：有真实权限，但责任域明确且有限。
  - 重要军政职责 (`major_affairs`) = `1.25`：承担重要军政、方面或中枢职责。
  - 国家关键或长期职责 (`critical_national_or_long_term`) = `1.4`：直接涉及国家全局、战略地域、制度形成或长期总责。
- **人岗配置结果** (`appointment_effect`)：衡量任用本身产生的直接履职反馈和损益。
  - 弱反馈 (`weak_feedback`) = `0.4`：只有有限履职或结果证据。
  - 正常成功 (`normal_success`) = `1.0`：人岗适配并产生稳定、可归责的正常结果。
  - 重大成功 (`major_success`) = `1.5`：产生异常显著且直接归属于人岗配置的结果。
  - 结果不佳 (`poor_result`) = `-0.8`：任用产生明确但有限的负面结果。
  - 重大直接损害 (`major_direct_damage`) = `-1.8`：产生重大、一次性的直接损害。
  - 持续结构损害 (`structural_continuing_damage`) = `-2.6`：损害跨期影响制度、组织能力或后续治理。
- **授权连续性** (`continuity_factor`)：衡量一次性任用、稳定履职或多阶段重复授权。
  - 短期或一次性 (`short_or_one_off`) = `0.85`：明确为一次任务或缺乏持续观察。
  - 稳定授权 (`stable`) = `1.0`：同一授权下有至少两个可区分的履职或反馈观察。
  - 长期多阶段授权 (`long_term_multi_stage`) = `1.15`：至少两次可区分的皇帝授权决定形成跨阶段复用。

### 团队建设明细

- 公式：`negative_pool=sum(negative_team_contribution_rank / rank ^ 0.5)；negative_signal=negative_pool * role_complementarity_factor * long_term_stability_factor；negative_team_contribution=negative_talent_severity_value * negative_talent_class_relevance；positive_pool=sum(talent_quality_factor_rank / rank ^ 0.5)；positive_signal=positive_pool * role_complementarity_factor * long_term_stability_factor；rule_raw_net=positive_signal - negative_signal`
- 对账：`reconciled`
- Primary：`eval/i5b_team_building_historical_coverage/lishimin_scored_shadow_report_v2.json`
- **团队成员人才档** (`talent_quality_factor`)：每名成员进入正向人才池的基础值。
  - 普通 (`ordinary`) = `0.35`：普通人才基础值。
  - 可用 (`usable`) = `0.55`：可用人才基础值。
  - 重要 (`important`) = `0.9`：重要人才基础值。
  - 顶级 (`top`) = `1.2`：顶级人才基础值。
  - 历史级 (`historic`) = `1.6`：历史级人才基础值。
- **负向人才严重度** (`negative_talent_severity_value`)：衡量窗口内已实现负向行为的严重程度。
  - 轻微 (`minor`) = `0.2`：有限且可控的负向影响。
  - 实质 (`material`) = `0.45`：已产生明确实质损害。
  - 重大 (`major`) = `0.8`：对团队或政权造成重大损害。
  - 历史级损害 (`historic`) = `1.2`：产生长期或时代级结构损害。
- **负向类型相关度** (`negative_talent_class_relevance`)：衡量负向人物类型与团队建设规则的相关程度。
  - 谄媚者 (`sycophant`) = `0.8`：以迎合削弱真实反馈。
  - 私宠 (`favorite`) = `0.7`：主要依靠私人偏爱进入核心。
  - 滥权者 (`power_abuser`) = `1.0`：利用职位破坏组织与公共权力。
  - 构陷者 (`framer`) = `1.0`：通过构陷破坏人才安全和团队协作。
  - 榨取型官员 (`extractive_official`) = `0.9`：以职位榨取资源并损害治理。
  - 酷吏 (`cruel_official`) = `0.9`：以残酷执法破坏治理与人才安全。
  - 无能致害 (`incompetent_harmful`) = `1.0`：因能力不足造成明确损害。
  - 叛乱行为者 (`traitorous_actor`) = `0.8`：在当前皇帝窗口内实施叛乱或严重背叛。
  - 混合或争议 (`mixed_or_disputed`) = `0.5`：负向类型存在但归类或责任有争议。
- **角色互补度** (`role_complementarity_factor`)：衡量决策、行政、军事、纠错四类核心角色覆盖。
  - 同质化 (`homogeneous`) = `0.9`：核心角色高度集中。
  - 普通双角色 (`ordinary_two`) = `1.0`：稳定覆盖两个核心角色。
  - 强三角色 (`strong_three`) = `1.1`：稳定覆盖三个核心角色。
  - 四角色均衡 (`balanced_four`) = `1.2`：四类核心角色均有有效成员。
- **团队长期稳定性** (`long_term_stability_factor`)：衡量团队结构在窗口内是否持续、可管理并跨阶段运行。
  - 碎片化 (`fragmented`) = `0.85`：团队结构短促或彼此割裂。
  - 强制更替崩塌 (`forced_turnover_collapse`) = `0.85`：频繁清洗或强制更替导致结构失效。
  - 稳定但狭窄 (`stable_but_narrow`) = `0.85`：团队稳定但角色或人才层次过窄。
  - 窗口内稳定 (`stable_window`) = `1.0`：在当前观察窗口内保持稳定。
  - 可管理更替 (`managed_turnover`) = `1.1`：人员更替存在但核心功能持续。
  - 跨阶段持久 (`durable_multi_stage`) = `1.2`：多阶段保持角色互补和核心功能。
- 团队成员池：张亮、王玄策、马周、尉迟敬德、唐俭、戴胄、李君羡、李绩、王珪、秦琼、长孙无忌、李靖、杜如晦、魏徵、褚遂良、萧瑀、侯君集、屈突通、房玄龄、段志玄、岑文本、虞世南、高士廉、温彦博

### 容才明细

- 公式：`negative=-handling_severity * target_fault_factor * evidence_factor；positive=feedback_entry * expression_safety * protection_repair * evidence_factor`
- 对账：`reconciled`
- Primary：`eval/i5b_joint_projection_scored_shadow/tolerate_talent_report.json`
- **反馈入口强度** (`feedback_entry`)：衡量从单次采纳、重复反馈、跨阶段持续、高密度跨领域谏诤到正式反馈通道持续运行的层级。次数不线性累加，高档必须同时有时间、领域和独立事件覆盖。
  - 单次采纳或容忍 (`single_acceptance_or_tolerance`) = `0.7`：只证明一次建议被采纳，或一次表达未受压制。
  - 多次反馈且仍被保留 (`repeated_feedback_retained`) = `1.0`：同一臣子有两个以上独立反馈事件，皇帝未因此排斥其履职；尚不证明长期跨阶段。
  - 跨阶段持续反馈 (`durable_multi_stage_feedback`) = `1.3`：反馈和容纳跨越统治期的多个明显阶段，且有独立后续证明表达者持续履职。仅几次跨阶段采纳最高落在此档。
  - 高密度跨领域长期犯颜 (`exceptional_dense_cross_domain_remonstrance`) = `1.7`：在长时段内存在大量可分辨谏诤，覆盖多个重大政务领域，包含逆耳或犯颜情形，且皇帝仍持续容纳、采用并保留其反馈职责。不得只凭一个模糊次数或史料篇幅推出。
  - 制度化反馈入口 (`institutionalized_feedback_entry`) = `2.0`：皇帝预先建立正式反馈通道，且该通道跨多个独立事件持续运行；通常应面向多名表达者或正式职能主体。不能由某一臣子反复进谏、单次求言诏令或事后采纳推出。（当前投影状态=已有已接受的shadow投影材料；合同可达性=已在李世民求谏机制shadow材料中达到）
- **表达安全** (`expression_safety`)：衡量表达者在反馈之后的人身、职业和持续表达安全。
  - 紧张或依赖个案 (`tense_or_case_dependent`) = `0.8`：表达受到威胁、冲突或个案恩免影响。
  - 基本安全 (`basically_safe`) = `1.0`：有晚于回应的独立观察证明未遭报复并继续履职。
  - 主动保护或鼓励 (`actively_protected_or_encouraged`) = `1.15`：皇帝明确保护表达者或持续鼓励其反馈。
- **保护与修复** (`protection_repair`)：衡量冲突后是否恢复职位、信用或反馈关系。
  - 无特殊保护修复 (`none`) = `1.0`：未发生需要计分的保护或修复动作。
  - 恢复或平反 (`restoration_or_rehabilitation`) = `1.1`：皇帝恢复职位、名誉或撤销部分损害。
  - 主动保护或完整修复 (`active_protection_or_trust_repair`) = `1.15`：皇帝主动保护表达者或实质恢复完整信任。
- **处置严重度** (`handling_severity`)：衡量因反馈或专业独立遭受的已实现处置。
  - 象征性或轻处分 (`symbolic_or_light`) = `0.6`：信用撤销、轻微惩戒或有限公开压制。
  - 贬黜或压制 (`demotion_or_suppression`) = `1.2`：已实现职业贬黜、排除或表达压制。
  - 监禁或严重非永久伤害 (`imprisonment_or_severe_nonpermanent_harm`) = `1.8`：已实现监禁、酷刑以外的严重伤害或长期职业损害。
  - 处死或逼令自尽 (`execution_or_forced_suicide`) = `2.6`：已导致本人被处死或被迫自尽。
  - 集团或系统清洗 (`clan_or_systemic_purge`) = `3.2`：伤害扩展到家族、群体或制度性清洗。
- **对象过错校准** (`target_fault_factor`)：根据表达者自身过错校准负向归责，避免把坐实重大过错全部算成容才失败。
  - 因反馈受害或被构陷 (`framed_or_harmed_for_feedback`) = `1.5`：没有重大过错，伤害直接由反馈触发。
  - 轻过重罚 (`minor_fault_disproportionate_harm`) = `1.2`：有轻微过错但处置明显失衡。
  - 过错未知 (`fault_unknown`) = `1.0`：现有证据无法确定对象过错。
  - 争议嫌疑 (`disputed_suspicion`) = `0.9`：存在嫌疑但未形成可靠坐实链。
  - 重大过错但处置过重 (`major_fault_but_excessive_harm`) = `0.5`：重大过错成立，但伤害仍超过必要范围。
  - 谋反坐实后的极弱残余 (`proven_rebellion_residual_talent_harm`) = `0.2`：谋反坐实，仅保留极弱的过度伤害残余。
- 贞观求谏机制 / `TT-LSM-INSTITUTIONAL-REM-01` / 材料分 `2.783` / 因子：直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；制度化反馈入口[feedback_entry=institutionalized_feedback_entry](2.0)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)
- 魏徵 / `TT-O01` / 材料分 `2.057` / 因子：直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；基本安全[expression_safety=basically_safe](1.0)；高密度跨领域长期犯颜[feedback_entry=exceptional_dense_cross_domain_remonstrance](1.7)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)
- 虞世南 / `TT-LSM-YSN-01` / 材料分 `1.392` / 因子：直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；多次反馈且仍被保留[feedback_entry=repeated_feedback_retained](1.0)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)
- 褚遂良 / `TT-LSM-CSL-01` / 材料分 `1.573` / 因子：直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；基本安全[expression_safety=basically_safe](1.0)；跨阶段持续反馈[feedback_entry=durable_multi_stage_feedback](1.3)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)
- 马周 / `TT-LSM-MZ-01` / 材料分 `1.392` / 因子：直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；多次反馈且仍被保留[feedback_entry=repeated_feedback_retained](1.0)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)
- 戴胄 / `TT-LSM-DZ-01` / 材料分 `1.809` / 因子：直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；跨阶段持续反馈[feedback_entry=durable_multi_stage_feedback](1.3)；无特殊保护修复[protection_repair=none](1.0)；完整直接链[source_factor=complete_direct_chain](1.1)
- 王珪 / `TT-LSM-WG-WYB-ZXS-01` / 材料分 `1.120` / 因子：直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；主动保护或鼓励[expression_safety=actively_protected_or_encouraged](1.15)；单次采纳或容忍[feedback_entry=single_acceptance_or_tolerance](0.7)；主动保护或完整修复[protection_repair=active_protection_or_trust_repair](1.15)；完整直接链[source_factor=complete_direct_chain](1.1)
- 魏徵身后信用 / `TT-O05` / 材料分 `0.653` / 因子：直接归责[attribution_factor=direct](1.0)；直击核心机制[context_factor=core_mechanism_direct](1.1)；象征性或轻处分[handling_severity=symbolic_or_light](0.6)；完整直接链[source_factor=complete_direct_chain](1.1)；争议嫌疑[target_fault_factor=disputed_suspicion](0.9)

## 臣子：魏徵

参与项数量：`7`；个人分数：未生成。
- 李世民 / 任用授权 / `supporting_judgment` / `魏徵`
- 李世民 / 任用授权 / `supporting_material` / `REU-LSM-WEIZHENG-APPOINTMENT-v1` / 材料分 `1.7394`
- 李世民 / 团队建设 / `team_member` / `魏徵`
- 李世民 / 团队建设 / `team_member` / `魏徵`
- 李世民 / 容才 / `counted_material` / `TT-O01` / 材料分 `2.057`
- 李世民 / 容才 / `counted_material` / `TT-O05` / 材料分 `0.653`
- 李世民 / 容才 / `source_rebind_record` / `—`

## 臣子：房玄龄

参与项数量：`3`；个人分数：未生成。
- 李世民 / 任用授权 / `supporting_material` / `REU-LSM-FANGXUANLING-CENTRAL-AUTHORITY-v1` / 材料分 `3.01875`
- 李世民 / 团队建设 / `team_member` / `房玄龄`
- 李世民 / 团队建设 / `team_member` / `房玄龄`

## 安全声明

- 未把 Rule 子集声明为完整第五项分数
- 未把臣子参与项合成为臣子个人分数
- 模型调用和数据库写入均为0
