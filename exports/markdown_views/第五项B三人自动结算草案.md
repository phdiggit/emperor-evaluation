# 第五项B三人自动结算草案

本文件由现有 `evidence_cards` / `evidence_clusters` / `thematic_anchors` 规则派生，只输出 band direction、confidence 与规则敏感点，不生成分数、排名或总榜。

## 自动结算总览

| person | positive_cluster_ids | negative_cluster_ids | auto_band_direction | confidence | negative_boundary_tier | negative_boundary_blocking | rule_sensitive_points |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 李世民 | ADJ-I5B-LISHIMIN-POS-TALENT-ECOSYSTEM-001 | ADJ-I5B-LISHIMIN-NEG-TALENT-RISK-001 | 高位强正，上探极正候选 | high_mid | weak_to_medium | False | 弱负上调中负边界 |
| 刘秀 | ADJ-I5B-LIUXIU-POS-TALENT-AUTHORIZATION-001 | ADJ-I5B-LIUXIU-NEG-REMONSTRANCE-SAFETY-001 | 强正受压制，不上探极正 | medium_high | medium_to_strong | True | 中负上调强负边界；强负核心压制强正 |
| 刘庄 | ADJ-I5B-LIUZHUANG-POS-TALENT-AUTHORIZATION-001 | ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001 | 中正受中负压制 | medium | adjacent_item_medium_residual | False | 相邻项主导剥离；B项剩余默认中负 |

## 逐人自动草案

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

## 刘秀

### 证据簇自动结算

**ADJ-I5B-LIUXIU-POS-TALENT-AUTHORIZATION-001｜正向｜候选强度=3｜强正候选**

* **簇类型**：人才选择与授权生态
* **边界档**：无
* **是否阻断极限档**：否
* **剩余强度**：强

* **对象锚点**：
  1. 创业期军政支柱
  2. 反馈入口
  3. 跨区域军政协同
  4. 少年将才

* **证据角色**：
  1. 中正锚点
  2. 强正核心

* **触发类型**：
  1. 识人拔擢
  2. 容谏纳言
  3. 授权专任

* **证据强度**：
  1. 2
  2. 3

* **上限封顶标记**：
  1. 不得因战功上探
  2. 不得因政绩上探
  3. 不得因后效上探
  4. 不得因战果上探

* **减轻/剥离标记**：
  1. 不回填西征战果
  2. 不回填后续治理
  3. 不回填北州战果
  4. 不回填拒朱鮪战果
  5. 不回填定河北战果

* **簇内角色**：
  1. 正向核心
  2. 正向增厚

* **相邻项剥离说明**：
  1. 战役胜负、河北/关中进展、边疆或区域收益、邓禹/吴汉/耿弇/冯异/寇恂的具体战功与后续政务成绩均不得回填第五项B；本证据组只保留识人、授权、纳言、文武协同与人才结构。
  2. B项只计早期任用、授权与选将；西征战果、关中平定和后续政务成绩切第一项、第二项或第三项。
  3. B项只计建议被采纳与反馈入口，不把后续治理效果直接回填。
  4. B项只计识别与授兵、授权秩序；后续北州战果切第一项或第三项。
  5. B项只计职位编组与授权秩序；拒朱鮪与战果切第一项或第三项。
  6. B项只计任用与授权；后续追击与定河北战果切第一项或第三项。

---

**ADJ-I5B-LIUXIU-NEG-REMONSTRANCE-SAFETY-001｜负向｜候选强度=3｜强负候选**

* **簇类型**：谏诤安全与表达风险
* **边界档**：中至强
* **是否阻断极限档**：是
* **剩余强度**：强

* **对象锚点**：
  1. 表达安全边界
  2. 反谶表达安全
  3. 尚书近臣表达安全

* **证据角色**：
  1. 强负核心

* **触发类型**：
  1. 容谏纳言
  2. 意识形态压制
  3. 廷杖刑辱

* **证据强度**：
  1. 3

* **上限封顶标记**：
  1. 不得上探极负

* **减轻/剥离标记**：
  1. 剥离灾异判断
  2. 剥离谶纬认知
  3. 剥离政治残酷性

* **簇内角色**：
  1. 强负核心

* **相邻项剥离说明**：
  1. 韩歆灾异/饥凶判断切第五项E或第二项B2；桓谭谶纬认知争议切第五项E；申屠刚材料中的法理严察、行政威慑或政治残酷性切第二项B3或第五项D。本证据组只保留表达安全、谏臣保护与人才生态受损。
  2. B项只保留容谏与谏臣保护面；灾异/饥凶预测及政策判断切第五项E或第二项B2。
  3. B项只保留反谶人才受压与表达安全问题；谶纬信念切第五项E，政治残酷性另切第五项D。
  4. B项只计臣下表达安全与近臣受辱；若讨论法理严察或政治残酷性，分别切行政执行/第五项D。

### 自动特征

| field | value |
| --- | --- |
| positive_cluster_ids | ["ADJ-I5B-LIUXIU-POS-TALENT-AUTHORIZATION-001"] |
| negative_cluster_ids | ["ADJ-I5B-LIUXIU-NEG-REMONSTRANCE-SAFETY-001"] |
| core_positive_count | 4 |
| strong_positive_count | 2 |
| extreme_positive_count | 0 |
| core_negative_count | 3 |
| strong_negative_count | 3 |
| extreme_negative_count | 0 |
| coverage_dimension_count | 3 |
| single_dimension_flag | False |
| startup_positive_share | 0.8 |
| has_high_value_object_anchor | True |
| has_boundary_evidence | True |
| has_mitigation_flag | True |
| has_upper_bound_flag | True |
| has_strong_negative_core | True |
| has_extreme_negative_core | False |
| negative_boundary_tier | medium_to_strong |
| negative_boundary_blocking | True |
| cross_item_split_required | True |
| cross_item_split_residual_level | strong |

### 触发的规则敏感点

- 中负上调强负边界：阻断极正/高位上探；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。
- 强负核心压制强正：保留强正基础，但自动标记为强正受压制，不上探极正。

## 人工复核提示（display-only）

> 仅展示=true；需要人工复核=true；不影响分数=true

**1. 回源核验提示（source_review_required｜I5B-CLUSTER-WARN-SOURCE-REVIEW-REQUIRED）**

* **提示语**：提示人工对强证、极端证和上探候选进行回源核验，避免仅凭标签或摘要定性。
* **命中词**：强正、极正、上探
* **命中字段**：
  1. cluster.note
  2. cluster.summary
  3. linked_cards[3].scoring_effect
  4. linked_cards[3].evidence_role
  5. linked_cards[4].scoring_effect
  6. linked_cards[4].evidence_role
  7. linked_cards[0].upper_bound_flag
  8. linked_cards[1].upper_bound_flag
  9. linked_cards[2].upper_bound_flag
  10. linked_cards[3].upper_bound_flag
  11. linked_cards[4].upper_bound_flag

**2. 回源核验提示（source_review_required｜I5B-CLUSTER-WARN-SOURCE-REVIEW-REQUIRED）**

* **提示语**：提示人工对强证、极端证和上探候选进行回源核验，避免仅凭标签或摘要定性。
* **命中词**：强负、极负、上探
* **命中字段**：
  1. cluster.summary
  2. linked_cards[0].scoring_effect
  3. linked_cards[0].evidence_role
  4. linked_cards[0].cluster_role
  5. linked_cards[1].scoring_effect
  6. linked_cards[1].evidence_role
  7. linked_cards[1].cluster_role
  8. linked_cards[2].scoring_effect
  9. linked_cards[2].evidence_role
  10. linked_cards[2].cluster_role
  11. linked_cards[0].upper_bound_flag
  12. linked_cards[1].upper_bound_flag
  13. linked_cards[2].upper_bound_flag

### 自动结算结论

- **band_direction**：强正受压制，不上探极正
- **confidence**：medium_high
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

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
