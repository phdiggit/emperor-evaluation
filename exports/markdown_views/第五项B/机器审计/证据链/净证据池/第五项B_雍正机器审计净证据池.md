# 第五项B_雍正机器审计净证据池

本文件为机器审计视图，用于代码审查、数据追踪和回源定位，不作为人工业务审核主入口。

## 证据组裁量结论

| 证据簇ID（cluster_id） | 人物（person） | 方向（polarity） | 簇类型（cluster_type） | 关联证据ID（linked_evidence_ids） | 候选强度（candidate_strength） | 上探标记（upper_probe） | 裁判状态（adjudication_status） | 摘要（summary） | 相邻项剥离说明（cross_item_split） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADJ-I5B-YONGZHENG-POS-TALENT-FEEDBACK-001 | 雍正 | 正向 | talent_recruitment_and_feedback_channel | EVD-I5B-YONGZHENG-POS-SHIREN-001；EVD-I5B-YONGZHENG-POS-RONGJIAN-001 | 2 | [见附录：上探标记（upper_probe）](../附录/雍正_机器审计净证据池长字段附录.md#adj-i5b-yongzheng-pos-talent-feedback-001-upper_probe) | 已回源，待人工裁判 | [见附录：摘要（summary）](../附录/雍正_机器审计净证据池长字段附录.md#adj-i5b-yongzheng-pos-talent-feedback-001-summary) | [见附录：相邻项剥离说明（cross_item_split）](../附录/雍正_机器审计净证据池长字段附录.md#adj-i5b-yongzheng-pos-talent-feedback-001-cross_item_split) |
| ADJ-I5B-YONGZHENG-NEG-TRUST-ECOSYSTEM-001 | 雍正 | 负向 | trust_ecology_and_expression_suppression | EVD-I5B-YONGZHENG-NEG-YIJI-001；EVD-I5B-YONGZHENG-NEG-YISHIXINGTAI-001 | 2 | [见附录：上探标记（upper_probe）](../附录/雍正_机器审计净证据池长字段附录.md#adj-i5b-yongzheng-neg-trust-ecosystem-001-upper_probe) | 已回源，待人工裁判 | [见附录：摘要（summary）](../附录/雍正_机器审计净证据池长字段附录.md#adj-i5b-yongzheng-neg-trust-ecosystem-001-summary) | [见附录：相邻项剥离说明（cross_item_split）](../附录/雍正_机器审计净证据池长字段附录.md#adj-i5b-yongzheng-neg-trust-ecosystem-001-cross_item_split) |

## 原子证据卡

| 证据ID（evidence_id） | 人物（person） | 方向（polarity） | 人工强度（human_level） | 触发类型（trigger_family） | 来源ID（source_id） | 短摘（quote_short） | 对象锚点（object_anchor） | 证据角色（evidence_role） | 减轻/剥离标记（mitigation_flag） | 上限封顶标记（upper_bound_flag） | 簇内角色（cluster_role） | 相邻项剥离说明（cross_item_split） | 评分影响（scoring_effect） | 裁判状态（adjudication_status） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EVD-I5B-YONGZHENG-POS-RONGJIAN-001 | 雍正 | 正向 | 中正 | 制度执行 | SRC-QSL-YZ-J1-001 | [见附录：短摘（quote_short）](../附录/雍正_机器审计净证据池长字段附录.md#evd-i5b-yongzheng-pos-rongjian-001-quote_short) | 制度执行入口 | 中正增厚 | 不回填治理结果 | 不得因整饬上探 | 正向增厚 | [见附录：相邻项剥离说明（cross_item_split）](../附录/雍正_机器审计净证据池长字段附录.md#evd-i5b-yongzheng-pos-rongjian-001-cross_item_split) | 中正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-YONGZHENG-POS-SHIREN-001 | 雍正 | 正向 | 中正 | 识人拔擢 | SRC-QSL-YZ-J1-001 | [见附录：短摘（quote_short）](../附录/雍正_机器审计净证据池长字段附录.md#evd-i5b-yongzheng-pos-shiren-001-quote_short) | 识人与反馈入口 | 中正核心 | 不回填后续政务 | 不得因后效上探 | 正向核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/雍正_机器审计净证据池长字段附录.md#evd-i5b-yongzheng-pos-shiren-001-cross_item_split) | 中正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-YONGZHENG-NEG-YIJI-001 | 雍正 | 负向 | 中负 | 近臣高压 | SRC-SYNL-YZ-J30-001 | [见附录：短摘（quote_short）](../附录/雍正_机器审计净证据池长字段附录.md#evd-i5b-yongzheng-neg-yiji-001-quote_short) | 近臣表达安全 | 中负核心 | 不回填政务问责 | 不得因整饬上探 | 负向核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/雍正_机器审计净证据池长字段附录.md#evd-i5b-yongzheng-neg-yiji-001-cross_item_split) | 中负候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-YONGZHENG-NEG-YISHIXINGTAI-001 | 雍正 | 负向 | 中负 | 表达安全 | SRC-SYNL-YZ-J89-001 | [见附录：短摘（quote_short）](../附录/雍正_机器审计净证据池长字段附录.md#evd-i5b-yongzheng-neg-yishixingtai-001-quote_short) | 异议表达边界 | 中负核心 | 不回填整饬成效 | 不得因高压上探 | 负向增厚 | [见附录：相邻项剥离说明（cross_item_split）](../附录/雍正_机器审计净证据池长字段附录.md#evd-i5b-yongzheng-neg-yishixingtai-001-cross_item_split) | 中负候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
