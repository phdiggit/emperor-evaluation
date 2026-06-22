本文件为机器审计视图，用于代码审查、数据追踪和回源定位，不作为人工业务审核主入口。

# 第五项B_刘秀净证据池

本文件为定档前净证据池视图；只汇总已回源原子证据与证据组裁量候选，不代表最终档位、得分或排名。

## 证据组裁量结论

| 证据簇ID（cluster_id） | 人物（person） | 方向（polarity） | 簇类型（cluster_type） | 关联证据ID（linked_evidence_ids） | 候选强度（candidate_strength） | 上探标记（upper_probe） | 裁判状态（adjudication_status） | 摘要（summary） | 相邻项剥离说明（cross_item_split） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADJ-I5B-LIUXIU-POS-TALENT-AUTHORIZATION-001 | 刘秀 | 正向 | 人才选择与授权生态 | [见附录：关联证据ID（linked_evidence_ids）](../附录/刘秀_净证据池长字段附录.md#adj-i5b-liuxiu-pos-talent-authorization-001-linked_evidence_ids) | 3 | [见附录：上探标记（upper_probe）](../附录/刘秀_净证据池长字段附录.md#adj-i5b-liuxiu-pos-talent-authorization-001-upper_probe) | 已回源，待人工裁判 | [见附录：摘要（summary）](../附录/刘秀_净证据池长字段附录.md#adj-i5b-liuxiu-pos-talent-authorization-001-summary) | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#adj-i5b-liuxiu-pos-talent-authorization-001-cross_item_split) |
| ADJ-I5B-LIUXIU-NEG-REMONSTRANCE-SAFETY-001 | 刘秀 | 负向 | 谏诤安全与表达风险 | [见附录：关联证据ID（linked_evidence_ids）](../附录/刘秀_净证据池长字段附录.md#adj-i5b-liuxiu-neg-remonstrance-safety-001-linked_evidence_ids) | 3 | [见附录：上探标记（upper_probe）](../附录/刘秀_净证据池长字段附录.md#adj-i5b-liuxiu-neg-remonstrance-safety-001-upper_probe) | 已回源，待人工裁判 | [见附录：摘要（summary）](../附录/刘秀_净证据池长字段附录.md#adj-i5b-liuxiu-neg-remonstrance-safety-001-summary) | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#adj-i5b-liuxiu-neg-remonstrance-safety-001-cross_item_split) |

## 原子证据卡

| 证据ID（evidence_id） | 人物（person） | 方向（polarity） | 人工强度（human_level） | 触发类型（trigger_family） | 来源ID（source_id） | 短摘（quote_short） | 对象锚点（object_anchor） | 证据角色（evidence_role） | 减轻/剥离标记（mitigation_flag） | 上限封顶标记（upper_bound_flag） | 簇内角色（cluster_role） | 相邻项剥离说明（cross_item_split） | 评分影响（scoring_effect） | 裁判状态（adjudication_status） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EVD-I5B-LIUXIU-POS-SHIREN-GENGYAN-001 | 刘秀 | 正向 | 强正 | 授权专任 | SRC-HHS-J19-GENGYAN-001 | [见附录：短摘（quote_short）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-shiren-gengyan-001-quote_short) | 少年将才 | 强正核心 | 不回填定河北战果 | 不得因战果上探 | 正向核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-shiren-gengyan-001-cross_item_split) | 强正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUXIU-POS-SHOUQUAN-KOUXUN-001 | 刘秀 | 正向 | 强正 | 授权专任 | SRC-HHS-J17-FENGYI-KOUXUN-001 | [见附录：短摘（quote_short）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-shouquan-kouxun-001-quote_short) | 跨区域军政协同 | 强正核心 | 不回填拒朱鮪战果 | 不得因后效上探 | 正向核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-shouquan-kouxun-001-cross_item_split) | 强正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUXIU-POS-RONGJIAN-FENGYI-001 | 刘秀 | 正向 | 中正 | 容谏纳言 | SRC-HHS-J17-FENGYI-KOUXUN-001 | [见附录：短摘（quote_short）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-rongjian-fengyi-001-quote_short) | 反馈入口 | 中正锚点 | 不回填后续治理 | 不得因政绩上探 | 正向增厚 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-rongjian-fengyi-001-cross_item_split) | 中正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUXIU-POS-SHIREN-DENGYU-001 | 刘秀 | 正向 | 中正 | 识人拔擢 | SRC-HHS-J16-DENGYU-001 | [见附录：短摘（quote_short）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-shiren-dengyu-001-quote_short) | 创业期军政支柱 | 中正锚点 | 不回填西征战果 | 不得因战功上探 | 正向核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-shiren-dengyu-001-cross_item_split) | 中正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUXIU-POS-SHOUQUAN-WUHAN-001 | 刘秀 | 正向 | 中正 | 授权专任 | SRC-HHS-J18-WUHAN-001 | [见附录：短摘（quote_short）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-shouquan-wuhan-001-quote_short) | 创业期军政支柱 | 中正锚点 | 不回填北州战果 | 不得因战功上探 | 正向核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-pos-shouquan-wuhan-001-cross_item_split) | 中正候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUXIU-NEG-HANXIN-001 | 刘秀 | 负向 | 强负 | 容谏纳言 | SRC-ZZTJ-J43-HANXIN-001 | [见附录：短摘（quote_short）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-neg-hanxin-001-quote_short) | 表达安全边界 | 强负核心 | 剥离灾异判断 | 不得上探极负 | 强负核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-neg-hanxin-001-cross_item_split) | 强负候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUXIU-NEG-HUANTAN-001 | 刘秀 | 负向 | 强负 | 意识形态压制 | SRC-HHS-HUANTAN-001 | [见附录：短摘（quote_short）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-neg-huantan-001-quote_short) | 反谶表达安全 | 强负核心 | 剥离谶纬认知 | 不得上探极负 | 强负核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-neg-huantan-001-cross_item_split) | 强负候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
| EVD-I5B-LIUXIU-NEG-TINGZHANG-001 | 刘秀 | 负向 | 强负 | 廷杖刑辱 | SRC-HHS-SHENTUGANG-001 | [见附录：短摘（quote_short）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-neg-tingzhang-001-quote_short) | 尚书近臣表达安全 | 强负核心 | 剥离政治残酷性 | 不得上探极负 | 强负核心 | [见附录：相邻项剥离说明（cross_item_split）](../附录/刘秀_净证据池长字段附录.md#evd-i5b-liuxiu-neg-tingzhang-001-cross_item_split) | 强负候选证据；不得直接入分，待人工裁判。 | 已回源，待人工裁判 |
