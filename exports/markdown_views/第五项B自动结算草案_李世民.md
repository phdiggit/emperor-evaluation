# 第五项B自动结算草案_李世民

本文为纯 Markdown 人物详情页，保留该人物自动特征、证据簇、`linked_*`、`cross_item_split_signals` 与 warning `matched_fields` 的全量展示。

[返回索引](./第五项B三人自动结算草案.md)

## 李世民

### 证据簇自动结算

**ADJ-I5B-LISHIMIN-POS-TALENT-ECOSYSTEM-001｜正向｜候选强度=3｜强正候选**

* **簇类型**：人才生态与授权
* **边界档**：无
* **是否阻断极限档**：否
* **剩余强度**：强

* **对象锚点**：
  1. 幕府聚才
  2. 旧敌转用
  3. 帝国级顶级将帅
  4. 顶级谏臣
  5. 寒门/后进人才
  6. 功臣安全秩序

* **证据角色**：
  1. 强正核心
  2. 中正锚点

* **触发类型**：
  1. 识人拔擢
  2. 授权专任
  3. 容谏纳言
  4. 异质人才整合

* **证据强度**：
  1. 3
  2. 2

* **上限封顶标记**：
  1. 不得因盛世上探
  2. 不得因后效上探
  3. 不得因战功上探
  4. 不得因治绩上探
  5. 不得因文名上探
  6. 不得因边疆结果上探

* **减轻/剥离标记**：
  1. 不回填后续政务
  2. 不回填后续纳谏
  3. 不回填边疆战果
  4. 不回填政策纠错
  5. 不回填后续升迁
  6. 不回填后续战果

* **簇内角色**：
  1. 正向核心
  2. 正向增厚

* **相邻项剥离说明**：
  1. 战役胜负、边疆收益、房杜后续政务成绩、魏征政策纠错效果、贞观治绩和总体盛世光环均不得回填第五项B；本证据组只保留识人、授权、容谏、寒门/后进通道与功臣安全秩序。
  2. B项只计发现和吸纳人才；房杜后续政务成绩切第二项，军事战果切第一项或第三项。
  3. B项只计旧敌阵营人才的转化与任用；魏征后续纳谏效果切第二项B2或第五项E。
  4. B项只计授权与权责匹配；突厥战果与边疆收益切第一项或第三项，制度执行切第二项B3。
  5. B项只计谏臣表达安全与反馈入口；政策纠错效果切第二项B2，认知反省切第五项E。
  6. B项只计人才发现与入仕通道；后续升迁、政务成绩与文辞褒誉切第二项或评价项。
  7. B项只计功臣安全机制与授权秩序；后续军事战果、边疆经营切第一项/第三项。

---

**ADJ-I5B-LISHIMIN-NEG-TALENT-RISK-001｜负向｜候选强度=2｜中负边界**

* **簇类型**：人才安全与信任风险
* **边界档**：弱至中
* **是否阻断极限档**：否
* **剩余强度**：中

* **对象锚点**：
  1. 功臣处置争议
  2. 确认谋反功臣
  3. 顶级谏臣

* **证据角色**：
  1. 中负边界
  2. 弱负边界
  3. 减轻型中负

* **触发类型**：
  1. 功臣处置争议
  2. 确认谋反功臣
  3. 谏臣身后信用反转

* **证据强度**：
  1. 2
  2. 1

* **上限封顶标记**：
  1. 不得上探强负
  2. 不得上探中负

* **减轻/剥离标记**：
  1. 剥离政权安全风险
  2. 剥离谋反事实
  3. 复碑恢复

* **簇内角色**：
  1. 边界负证
  2. 边界负证，不作为强负核心

* **相邻项剥离说明**：
  1. 谋反与政权安全切第五项C；司法严酷和刑罚问题切第五项D；魏征生前容谏正证另入正向证据组；本证据组只保留用人生态中的功臣/谏臣安全感与信任风险。
  2. 谋反和政权安全风险切第五项C；司法严酷或刑罚过重切第五项D；B项只保留功臣处置争议与授权预期受损。
  3. 太子谋反和政权安全切第五项C；司法严酷切第五项D；战功本身不在B项加分；B项仅计功臣处置严厉对功臣预期的弱影响。
  4. B项只计顶级谏臣身后政治信用与表达安全预期的剩余损伤；魏征生前纳谏正证另入正向证据组，政策纠错效果切第二项B2，皇帝认知/反思能力切第五项E；复碑与恢复评价只作为减轻与封顶因素，不改写本项中负剩余。

### 自动特征

| field | value |
| --- | --- |
| positive_cluster_ids | ["ADJ-I5B-LISHIMIN-POS-TALENT-ECOSYSTEM-001"] |
| negative_cluster_ids | ["ADJ-I5B-LISHIMIN-NEG-TALENT-RISK-001"] |
| core_positive_count | 3 |
| strong_positive_count | 3 |
| extreme_positive_count | 0 |
| core_negative_count | 1 |
| strong_negative_count | 0 |
| extreme_negative_count | 0 |
| coverage_dimension_count | 5 |
| single_dimension_flag | False |
| startup_positive_share | 0.33 |
| has_high_value_object_anchor | True |
| has_boundary_evidence | True |
| has_mitigation_flag | True |
| has_upper_bound_flag | True |
| has_strong_negative_core | False |
| has_extreme_negative_core | False |
| negative_boundary_tier | weak_to_medium |
| negative_boundary_blocking | False |
| cross_item_split_required | True |
| cross_item_split_residual_level | medium |

### 触发的规则敏感点

- 弱负上调中负边界：不阻断极正或高位上探；只降低置信度，不进入强负核心。

## 人工复核提示（display-only）

> 仅展示=true；需要人工复核=true；不影响分数=true

**1. 回源核验提示（source_review_required｜I5B-CLUSTER-WARN-SOURCE-REVIEW-REQUIRED）**

* **提示语**：提示人工对强证、极端证和上探候选进行回源核验，避免仅凭标签或摘要定性。
* **命中词**：强正、上探
* **命中字段**：
  1. linked_cards[0].scoring_effect
  2. linked_cards[0].evidence_role
  3. linked_cards[3].scoring_effect
  4. linked_cards[3].evidence_role
  5. linked_cards[5].scoring_effect
  6. linked_cards[5].evidence_role
  7. linked_cards[0].upper_bound_flag
  8. linked_cards[1].upper_bound_flag
  9. linked_cards[2].upper_bound_flag
  10. linked_cards[3].upper_bound_flag
  11. linked_cards[4].upper_bound_flag
  12. linked_cards[5].upper_bound_flag

**2. 单证不足提示（single_evidence_limit｜I5B-CLUSTER-WARN-SINGLE-EVIDENCE-LIMIT）**

* **提示语**：提示人工检查单条证据是否不足以支撑高强度证据簇，不能机械升档。
* **命中词**：单证
* **命中字段**：
  1. linked_cards[2].scoring_effect

### 自动结算结论

- **band_direction**：高位强正，上探极正候选
- **confidence**：high_mid
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。
