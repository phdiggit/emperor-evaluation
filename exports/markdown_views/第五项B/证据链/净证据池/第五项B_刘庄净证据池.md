# 第五项B_刘庄净证据池

本文件为定档前净证据池视图；只汇总已回源原子证据与证据组裁量候选，不代表最终档位、得分或排名。

## 证据组裁量结论

| 证据簇ID（cluster_id） | 人物（person） | 方向（polarity） | 簇类型（cluster_type） | 关联证据ID（linked_evidence_ids） | 候选强度（candidate_strength） | 上探标记（upper_probe） | 裁判状态（adjudication_status） | 摘要（summary） | 相邻项剥离说明（cross_item_split） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADJ-I5B-LIUZHUANG-POS-TALENT-AUTHORIZATION-001 | 刘庄 | 正向 | 人才选择与授权生态 | [见附录：关联证据ID（linked_evidence_ids）](../附录/刘庄_净证据池长字段附录.md#adj-i5b-liuzhuang-pos-talent-authorization-001-linked_evidence_ids) | 2 | [见附录：上探标记（upper_probe）](../附录/刘庄_净证据池长字段附录.md#adj-i5b-liuzhuang-pos-talent-authorization-001-upper_probe) | 已回源，待人工裁判 | [见附录：摘要（summary）](../附录/刘庄_净证据池长字段附录.md#adj-i5b-liuzhuang-pos-talent-authorization-001-summary) | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘庄_净证据池长字段附录.md#adj-i5b-liuzhuang-pos-talent-authorization-001-cross_item_split) |
| ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001 | 刘庄 | 负向 | 人才安全与政治牵连风险 | EVD-I5B-LIUZHUANG-NEG-YIJI-001 | 3 | [见附录：上探标记（upper_probe）](../附录/刘庄_净证据池长字段附录.md#adj-i5b-liuzhuang-neg-talent-safety-001-upper_probe) | 已回源，待人工裁判 | [见附录：摘要（summary）](../附录/刘庄_净证据池长字段附录.md#adj-i5b-liuzhuang-neg-talent-safety-001-summary) | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘庄_净证据池长字段附录.md#adj-i5b-liuzhuang-neg-talent-safety-001-cross_item_split) |

## 原子证据卡

| 证据ID（evidence_id） | 人物（person） | 方向（polarity） | 人工强度（human_level） | 触发类型（trigger_family） | 来源ID（source_id） | 短摘（quote_short） | 对象锚点（object_anchor） | 证据角色（evidence_role） | 减轻/剥离标记（mitigation_flag） | 上限封顶标记（upper_bound_flag） | 簇内角色（cluster_role） | 相邻项剥离说明（cross_item_split） | 评分影响（scoring_effect） | 裁判状态（adjudication_status） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EVD-I5B-LIUZHUANG-POS-RONGJIAN-QIUYAN-001 | 刘庄 | 正向 | 中正 | 容谏纳言 | SRC-HHS-J2-XIANZONG-001 | [见附录：短摘（quote_short）](../附录/刘庄_净证据池长字段附录.md#evd-i5b-liuzhuang-pos-rongjian-qiuyan-001-quote_short) | 日食求言 | 中正锚点 | 不回填纠错效果 | 不得因后续改制上探 | 正向增厚 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘庄_净证据池长字段附录.md#evd-i5b-liuzhuang-pos-rongjian-qiuyan-001-cross_item_split) | 中正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUZHUANG-POS-SHIREN-CANGYU-001 | 刘庄 | 正向 | 中正 | 识人拔擢 | SRC-HHS-J2-XIANZONG-001 | [见附录：短摘（quote_short）](../附录/刘庄_净证据池长字段附录.md#evd-i5b-liuzhuang-pos-shiren-cangyu-001-quote_short) | 旧臣与宗室辅政 | 中正锚点 | 不回填辅政后效 | 不得因稳定上探 | 正向增厚 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘庄_净证据池长字段附录.md#evd-i5b-liuzhuang-pos-shiren-cangyu-001-cross_item_split) | 中正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUZHUANG-POS-SHOUQUAN-BANCHAO-001 | 刘庄 | 正向 | 中正 | 授权专任 | SRC-HHS-J47-BANCHAO-001 | [见附录：短摘（quote_short）](../附录/刘庄_净证据池长字段附录.md#evd-i5b-liuzhuang-pos-shouquan-banchao-001-quote_short) | 边疆授权 | 中正锚点 | 不回填西域战功 | 不得因边疆收益上探 | 正向增厚 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘庄_净证据池长字段附录.md#evd-i5b-liuzhuang-pos-shouquan-banchao-001-cross_item_split) | 中正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUZHUANG-NEG-YIJI-001 | 刘庄 | 负向 | 强负 | 疑忌杀害 | SRC-HHS-GW10WANG-LIUZHUANG-YIJI-001 | [见附录：短摘（quote_short）](../附录/刘庄_净证据池长字段附录.md#evd-i5b-liuzhuang-neg-yiji-001-quote_short) | 楚狱边界负证 | 强负核心 | 剥离政权安全与司法严酷 | 不得上探极负 | 强负核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘庄_净证据池长字段附录.md#evd-i5b-liuzhuang-neg-yiji-001-cross_item_split) | 强负候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
