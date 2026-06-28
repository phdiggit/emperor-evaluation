# 第五项B_朱元璋机器审计净证据池

本文件为机器审计视图，用于代码审查、数据追踪和回源定位，不作为人工业务审核主入口。

## 证据组裁量结论

| 证据簇ID（cluster_id） | 人物（person） | 方向（polarity） | 簇类型（cluster_type） | 关联证据ID（linked_evidence_ids） | 候选强度（candidate_strength） | 上探标记（upper_probe） | 裁判状态（adjudication_status） | 摘要（summary） | 相邻项剥离说明（cross_item_split） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADJ-I5B-ZHUYUANZHANG-POS-TALENT-AUTHORIZATION-001 | 朱元璋 | 正向 | 人才选择与授权生态 | [见附录：关联证据ID（linked_evidence_ids）](../附录/朱元璋_机器审计净证据池长字段附录.md#adj-i5b-zhuyuanzhang-pos-talent-authorization-001-linked_evidence_ids) | 3 | [见附录：上探标记（upper_probe）](../附录/朱元璋_机器审计净证据池长字段附录.md#adj-i5b-zhuyuanzhang-pos-talent-authorization-001-upper_probe) | 已回源，待人工裁判 | [见附录：摘要（summary）](../附录/朱元璋_机器审计净证据池长字段附录.md#adj-i5b-zhuyuanzhang-pos-talent-authorization-001-summary) | [见附录：相邻项剥离说明（cross_item_split）](../附录/朱元璋_机器审计净证据池长字段附录.md#adj-i5b-zhuyuanzhang-pos-talent-authorization-001-cross_item_split) |
| ADJ-I5B-ZHUYUANZHANG-NEG-MERIT-PURGE-001 | 朱元璋 | 负向 | merit_subject_purge_and_security_case | EVD-I5B-ZHUYUANZHANG-NEG-HULAN-001；EVD-I5B-ZHUYUANZHANG-NEG-LANYU-001 | 3 | [见附录：上探标记（upper_probe）](../附录/朱元璋_机器审计净证据池长字段附录.md#adj-i5b-zhuyuanzhang-neg-merit-purge-001-upper_probe) | 已回源，待人工裁判 | [见附录：摘要（summary）](../附录/朱元璋_机器审计净证据池长字段附录.md#adj-i5b-zhuyuanzhang-neg-merit-purge-001-summary) | [见附录：相邻项剥离说明（cross_item_split）](../附录/朱元璋_机器审计净证据池长字段附录.md#adj-i5b-zhuyuanzhang-neg-merit-purge-001-cross_item_split) |

## 原子证据卡

| 证据ID（evidence_id） | 人物（person） | 方向（polarity） | 人工强度（human_level） | 触发类型（trigger_family） | 来源ID（source_id） | 短摘（quote_short） | 对象锚点（object_anchor） | 证据角色（evidence_role） | 减轻/剥离标记（mitigation_flag） | 上限封顶标记（upper_bound_flag） | 簇内角色（cluster_role） | 相邻项剥离说明（cross_item_split） | 评分影响（scoring_effect） | 裁判状态（adjudication_status） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EVD-I5B-ZHUYUANZHANG-POS-SHIREN-001 | 朱元璋 | 正向 | 强正 | 识人拔擢 | SRC-MTZL-J008-001 | [见附录：短摘（quote_short）](../附录/朱元璋_机器审计净证据池长字段附录.md#evd-i5b-zhuyuanzhang-pos-shiren-001-quote_short) | 开国识人 | 强正核心 | 不回填开国战果 | 不得因盛世上探 | 正向核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/朱元璋_机器审计净证据池长字段附录.md#evd-i5b-zhuyuanzhang-pos-shiren-001-cross_item_split) | 强正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-ZHUYUANZHANG-POS-SHOUQUAN-001 | 朱元璋 | 正向 | 强正 | 授权专任 | SRC-MTZL-J024-001 | [见附录：短摘（quote_short）](../附录/朱元璋_机器审计净证据池长字段附录.md#evd-i5b-zhuyuanzhang-pos-shouquan-001-quote_short) | 授权专任 | 强正核心 | 不回填后续制度效应 | 不得因战功上探 | 正向核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/朱元璋_机器审计净证据池长字段附录.md#evd-i5b-zhuyuanzhang-pos-shouquan-001-cross_item_split) | 强正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-ZHUYUANZHANG-NEG-HULAN-001 | 朱元璋 | 负向 | 强负 | 系统性清洗 | SRC-MS-J308-001 | [见附录：短摘（quote_short）](../附录/朱元璋_机器审计净证据池长字段附录.md#evd-i5b-zhuyuanzhang-neg-hulan-001-quote_short) | 人才生态清洗 | 强负核心 | 不回填政权安全 | 不得因党案上探 | 负向核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/朱元璋_机器审计净证据池长字段附录.md#evd-i5b-zhuyuanzhang-neg-hulan-001-cross_item_split) | 强负候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-ZHUYUANZHANG-NEG-LANYU-001 | 朱元璋 | 负向 | 中负 | 功臣安全 | SRC-MS-J132-001 | [见附录：短摘（quote_short）](../附录/朱元璋_机器审计净证据池长字段附录.md#evd-i5b-zhuyuanzhang-neg-lanyu-001-quote_short) | 功臣安全反复 | 中负核心 | 不回填党案安全 | 不得因后续制度上探 | 负向增厚 | [见附录：相邻项剥离说明（cross_item_split）](../附录/朱元璋_机器审计净证据池长字段附录.md#evd-i5b-zhuyuanzhang-neg-lanyu-001-cross_item_split) | 中负候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
