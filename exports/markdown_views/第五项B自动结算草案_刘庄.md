# 第五项B自动结算草案_刘庄

本文为纯 Markdown 人物详情页，保留该人物自动特征、证据簇、`linked_*`、`cross_item_split_signals` 与 warning `matched_fields` 的全量展示。

[返回索引](./第五项B三人自动结算草案.md)

## 刘庄

### 证据簇自动结算

**ADJ-I5B-LIUZHUANG-POS-TALENT-AUTHORIZATION-001｜正向｜候选强度=2｜中正增厚**

* **簇类型**：人才选择与授权生态
* **边界档**：无
* **是否阻断极限档**：否
* **剩余强度**：中

* **对象锚点**：
  1. 旧臣与宗室辅政
  2. 日食求言
  3. 边疆授权

* **证据角色**：
  1. 中正锚点

* **触发类型**：
  1. 识人拔擢
  2. 容谏纳言
  3. 授权专任

* **证据强度**：
  1. 2

* **上限封顶标记**：
  1. 不得因稳定上探
  2. 不得因后续改制上探
  3. 不得因边疆收益上探

* **减轻/剥离标记**：
  1. 不回填辅政后效
  2. 不回填纠错效果
  3. 不回填西域战功

* **簇内角色**：
  1. 正向增厚

* **相邻项剥离说明**：
  1. 西域战果、军事胜负、边疆收益、辅政后的政务成效、政治稳定与政策纠错效果均不得回填第五项B；本证据组只保留识人、任用、授权、求言与反馈入口。
  2. B项只计识人、任用与人才结构；辅政后的政务成效、政治稳定与制度收益切第二项或第五项C。
  3. B项只计反馈入口与表达安全；后续纠错、行政调整和政策效果切第二项B2、第二项B3或第五项E。
  4. B项只计任用、遣使与授权秩序；伊吾、西域战果与边疆收益切第一项/第三项，行政后效切第二项。

---

**ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001｜负向｜候选强度=3｜中负边界**

* **簇类型**：人才安全与政治牵连风险
* **边界档**：相邻项剥离后中度剩余
* **是否阻断极限档**：否
* **剩余强度**：中

* **对象锚点**：
  1. 楚狱边界负证

* **证据角色**：
  1. 强负核心

* **触发类型**：
  1. 疑忌杀害

* **证据强度**：
  1. 3

* **上限封顶标记**：
  1. 不得上探极负

* **减轻/剥离标记**：
  1. 剥离政权安全与司法严酷

* **簇内角色**：
  1. 强负核心

* **相邻项剥离说明**：
  1. 楚王英案中的宗室控制、谋反与政权安全切第五项C；坐死徙者以千数、司法严酷与政治残酷性切第五项D；行政威慑或吏治效果切第二项B3。本证据组只保留人才安全感、牵连扩大与表达生态受损。
  2. B项只计高压问责、牵连扩大与人才安全感；权力集中和宗室控制切第五项C，行政威慑/吏治效果切第二项B3，政治残酷性切第五项D。

### 自动特征

| field | value |
| --- | --- |
| positive_cluster_ids | ["ADJ-I5B-LIUZHUANG-POS-TALENT-AUTHORIZATION-001"] |
| negative_cluster_ids | ["ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001"] |
| core_positive_count | 0 |
| strong_positive_count | 0 |
| extreme_positive_count | 0 |
| core_negative_count | 1 |
| strong_negative_count | 1 |
| extreme_negative_count | 0 |
| coverage_dimension_count | 3 |
| single_dimension_flag | False |
| startup_positive_share | 0.33 |
| has_high_value_object_anchor | True |
| has_boundary_evidence | True |
| has_mitigation_flag | True |
| has_upper_bound_flag | True |
| has_strong_negative_core | False |
| has_extreme_negative_core | False |
| negative_boundary_tier | adjacent_item_medium_residual |
| negative_boundary_blocking | False |
| cross_item_split_required | True |
| cross_item_split_residual_level | medium |

### 触发的规则敏感点

- 相邻项主导剥离：大案本身严重不等于第五项B强负；剥离后只保留 B 项剩余影响。
- B项剩余默认中负：默认中负剩余；只有直接寒蝉、群臣莫敢正言、人才退缩或授权可信度破坏等硬证时，才保留强负核心。

## 人工复核提示（display-only）

> 仅展示=true；需要人工复核=true；不影响分数=true

**1. 回源核验提示（source_review_required｜I5B-CLUSTER-WARN-SOURCE-REVIEW-REQUIRED）**

* **提示语**：提示人工对强证、极端证和上探候选进行回源核验，避免仅凭标签或摘要定性。
* **命中词**：强负、极负、上探
* **命中字段**：
  1. cluster.note
  2. cluster.summary
  3. linked_cards[0].scoring_effect
  4. linked_cards[0].evidence_role
  5. linked_cards[0].cluster_role
  6. linked_cards[0].upper_bound_flag

### 自动结算结论

- **band_direction**：中正受中负压制
- **confidence**：medium
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。
