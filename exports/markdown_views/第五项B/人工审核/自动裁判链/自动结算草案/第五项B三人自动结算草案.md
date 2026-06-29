# 第五项B代表性皇帝自动结算草案

本文件由现有 `evidence_cards` / `evidence_clusters` / `thematic_anchors` 规则派生，只输出 band direction、confidence 与规则敏感点，不生成分数、排名或总榜。

- **活动人物组**：代表性皇帝
- **覆盖人物**：李世民、刘秀、刘庄、嬴政、刘邦、刘恒、刘彻、刘询、刘启、杨坚、杨广、李隆基、武则天、李治、李渊、李纯、赵匡胤、赵恒、赵光义、赵构、赵祯、朱元璋、朱棣、朱瞻基、朱由检、皇太极、玄烨、雍正、弘历

## 自动结算总览

| 人物（person） | 自动结算方向（auto_band_direction） | 置信度（confidence） | 负向边界档（negative_boundary_tier） | 规则敏感点（rule_sensitive_points） |
| --- | --- | --- | --- | --- |
| 李世民 | 高位强正，上探极正候选 | 高偏中 | 弱至中 | 弱负上调中负边界 |
| 刘秀 | 强正受压制，不上探极正 | 中偏高 | 中至强 | 中负上调强负边界；强负核心压制强正 |
| 刘庄 | 中正受中负压制 | 中 | 相邻项剥离后中度剩余 | 相邻项主导剥离；B项剩余默认中负 |
| 嬴政 | 强正封顶，不上探极正 | 中偏高 | 弱至中 | 弱负上调中负边界 |
| 刘邦 | 强正受压制，不上探极正 | 中偏高 | 中至强 | 中负上调强负边界；强负核心压制强正 |
| 刘恒 | 高位强正，上探极正候选 | 高偏中 | 弱至中 | 弱负上调中负边界 |
| 刘彻 | 强正封顶，不上探极正 | 中偏高 | 相邻项剥离后中度剩余 | 相邻项主导剥离；B项剩余默认中负 |
| 刘询 | 强正封顶，不上探极正 | 中偏高 | 无 | 无 |
| 刘启 | 中正受强负压制 | 中 | 中至强 | 中负上调强负边界；强负核心压制强正 |
| 杨坚 | 强正封顶，不上探极正 | 中偏高 | 相邻项剥离后中度剩余 | 相邻项主导剥离；B项剩余默认中负 |
| 杨广 | 中正受强负压制 | 中 | 中至强 | 中负上调强负边界；强负核心压制强正 |
| 李隆基 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 武则天 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 李治 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 李渊 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 李纯 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 赵匡胤 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 赵恒 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 赵光义 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 赵构 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 赵祯 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 朱元璋 | 强正受压制，不上探极正 | 中偏高 | 中至强 | 中负上调强负边界；强负核心压制强正 |
| 朱棣 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 朱瞻基 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 朱由检 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 皇太极 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 玄烨 | 自动草案待规则复核 | 中偏低 | 无 | 无 |
| 雍正 | 中正受中负压制 | 中 | 相邻项剥离后中度剩余 | 相邻项主导剥离；B项剩余默认中负 |
| 弘历 | 自动草案待规则复核 | 中偏低 | 无 | 无 |

## 逐人自动草案

## 李世民

### 证据簇自动结算

**ADJ-I5B-LISHIMIN-POS-TALENT-ECOSYSTEM-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：人才生态与授权
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 幕府聚才
  2. 旧敌转用
  3. 帝国级顶级将帅
  4. 顶级谏臣
  5. 寒门/后进人才
  6. 功臣安全秩序

* **证据角色（linked_evidence_roles）**：
  1. 强正核心
  2. 中正锚点

* **触发类型（linked_trigger_families）**：
  1. 识人拔擢
  2. 授权专任
  3. 容谏纳言
  4. 异质人才整合

* **证据强度（linked_strengths）**：
  1. 3
  2. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因盛世上探
  2. 不得因后效上探
  3. 不得因战功上探
  4. 不得因治绩上探
  5. 不得因文名上探
  6. 不得因边疆结果上探

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 不回填后续政务
  2. 不回填后续纳谏
  3. 不回填边疆战果
  4. 不回填政策纠错
  5. 不回填后续升迁
  6. 不回填后续战果

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心
  2. 正向增厚

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 战役胜负、边疆收益、房杜后续政务成绩、魏征政策纠错效果、贞观治绩和总体盛世光环均不得回填第五项B；本证据组只保留识人、授权、容谏、寒门/后进通道与功臣安全秩序。
  2. B项只计发现和吸纳人才；房杜后续政务成绩切第二项，军事战果切第一项或第三项。
  3. B项只计旧敌阵营人才的转化与任用；魏征后续纳谏效果切第二项B2或第五项E。
  4. B项只计授权与权责匹配；突厥战果与边疆收益切第一项或第三项，制度执行切第二项B3。
  5. B项只计谏臣表达安全与反馈入口；政策纠错效果切第二项B2，认知反省切第五项E。
  6. B项只计人才发现与入仕通道；后续升迁、政务成绩与文辞褒誉切第二项或评价项。
  7. B项只计功臣安全机制与授权秩序；后续军事战果、边疆经营切第一项/第三项。

---

**ADJ-I5B-LISHIMIN-NEG-TALENT-RISK-001｜负向｜候选强度（candidate_strength）=2｜中负边界**

* **簇类型（cluster_type）**：人才安全与信任风险
* **边界档（boundary_tier）**：弱至中
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 功臣处置争议
  2. 确认谋反功臣
  3. 顶级谏臣

* **证据角色（linked_evidence_roles）**：
  1. 中负边界
  2. 弱负边界
  3. 减轻型中负

* **触发类型（linked_trigger_families）**：
  1. 功臣处置争议
  2. 确认谋反功臣
  3. 谏臣身后信用反转

* **证据强度（linked_strengths）**：
  1. 2
  2. 1

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探强负
  2. 不得上探中负

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离政权安全风险
  2. 剥离谋反事实
  3. 复碑恢复

* **簇内角色（linked_cluster_roles）**：
  1. 边界负证
  2. 边界负证，不作为强负核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 谋反与政权安全切第五项C；司法严酷和刑罚问题切第五项D；魏征生前容谏正证另入正向证据组；本证据组只保留用人生态中的功臣/谏臣安全感与信任风险。
  2. 谋反和政权安全风险切第五项C；司法严酷或刑罚过重切第五项D；B项只保留功臣处置争议与授权预期受损。
  3. 太子谋反和政权安全切第五项C；司法严酷切第五项D；战功本身不在B项加分；B项仅计功臣处置严厉对功臣预期的弱影响。
  4. B项只计顶级谏臣身后政治信用与表达安全预期的剩余损伤；魏征生前纳谏正证另入正向证据组，政策纠错效果切第二项B2，皇帝认知/反思能力切第五项E；复碑与恢复评价只作为减轻与封顶因素，不改写本项中负剩余。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-LISHIMIN-POS-TALENT-ECOSYSTEM-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-LISHIMIN-NEG-TALENT-RISK-001"
]
```
* **正向核心数量（core_positive_count）**：3
* **强正证据数量（strong_positive_count）**：3
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：1
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：5
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：识人任用、人才生态、授权专任
* **是否满足三核心覆盖（positive_three_core_coverage）**：是
* **创业期正证占比（startup_positive_share）**：0.33
* **是否有高价值对象锚点（has_high_value_object_anchor）**：是
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：弱至中
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：中

### 触发的规则敏感点

- **弱负上调中负边界**：不阻断极正或高位上探；只降低置信度，不进入强负核心。

### 自动结算结论

- **自动结算方向（band_direction）**：高位强正，上探极正候选
- **置信度（confidence）**：高偏中
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 刘秀

### 证据簇自动结算

**ADJ-I5B-LIUXIU-POS-TALENT-AUTHORIZATION-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：人才选择与授权生态
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 创业期军政支柱
  2. 反馈入口
  3. 跨区域军政协同
  4. 少年将才

* **证据角色（linked_evidence_roles）**：
  1. 中正锚点
  2. 强正核心

* **触发类型（linked_trigger_families）**：
  1. 识人拔擢
  2. 容谏纳言
  3. 授权专任

* **证据强度（linked_strengths）**：
  1. 2
  2. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因战功上探
  2. 不得因政绩上探
  3. 不得因后效上探
  4. 不得因战果上探

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 不回填西征战果
  2. 不回填后续治理
  3. 不回填北州战果
  4. 不回填拒朱鮪战果
  5. 不回填定河北战果

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心
  2. 正向增厚

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 战役胜负、河北/关中进展、边疆或区域收益、邓禹/吴汉/耿弇/冯异/寇恂的具体战功与后续政务成绩均不得回填第五项B；本证据组只保留识人、授权、纳言、文武协同与人才结构。
  2. B项只计早期任用、授权与选将；西征战果、关中平定和后续政务成绩切第一项、第二项或第三项。
  3. B项只计建议被采纳与反馈入口，不把后续治理效果直接回填。
  4. B项只计识别与授兵、授权秩序；后续北州战果切第一项或第三项。
  5. B项只计职位编组与授权秩序；拒朱鮪与战果切第一项或第三项。
  6. B项只计任用与授权；后续追击与定河北战果切第一项或第三项。

---

**ADJ-I5B-LIUXIU-NEG-REMONSTRANCE-SAFETY-001｜负向｜候选强度（candidate_strength）=3｜强负候选**

* **簇类型（cluster_type）**：谏诤安全与表达风险
* **边界档（boundary_tier）**：中至强
* **是否阻断极限档（blocking_extreme）**：是
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 表达安全边界
  2. 反谶表达安全
  3. 尚书近臣表达安全

* **证据角色（linked_evidence_roles）**：
  1. 强负核心

* **触发类型（linked_trigger_families）**：
  1. 容谏纳言
  2. 意识形态压制
  3. 廷杖刑辱

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探极负

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离灾异判断
  2. 剥离谶纬认知
  3. 剥离政治残酷性

* **簇内角色（linked_cluster_roles）**：
  1. 强负核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 韩歆灾异/饥凶判断切第五项E或第二项B2；桓谭谶纬认知争议切第五项E；申屠刚材料中的法理严察、行政威慑或政治残酷性切第二项B3或第五项D。本证据组只保留表达安全、谏臣保护与人才生态受损。
  2. B项只保留容谏与谏臣保护面；灾异/饥凶预测及政策判断切第五项E或第二项B2。
  3. B项只保留反谶人才受压与表达安全问题；谶纬信念切第五项E，政治残酷性另切第五项D。
  4. B项只计臣下表达安全与近臣受辱；若讨论法理严察或政治残酷性，分别切行政执行/第五项D。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUXIU-POS-TALENT-AUTHORIZATION-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUXIU-NEG-REMONSTRANCE-SAFETY-001"
]
```
* **正向核心数量（core_positive_count）**：4
* **强正证据数量（strong_positive_count）**：2
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：3
* **强负证据数量（strong_negative_count）**：3
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：3
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：授权专任、识人任用
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.8
* **是否有高价值对象锚点（has_high_value_object_anchor）**：是
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：是
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：中至强
* **负向边界是否阻断（negative_boundary_blocking）**：是
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：强

### 触发的规则敏感点

- **中负上调强负边界**：阻断极正/高位上探；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。
- **强负核心压制强正**：保留强正基础，但自动标记为强正受压制，不上探极正。

### 自动结算结论

- **自动结算方向（band_direction）**：强正受压制，不上探极正
- **置信度（confidence）**：中偏高
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 刘庄

### 证据簇自动结算

**ADJ-I5B-LIUZHUANG-POS-TALENT-AUTHORIZATION-001｜正向｜候选强度（candidate_strength）=2｜中正增厚**

* **簇类型（cluster_type）**：人才选择与授权生态
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 旧臣与宗室辅政
  2. 日食求言
  3. 边疆授权

* **证据角色（linked_evidence_roles）**：
  1. 中正锚点

* **触发类型（linked_trigger_families）**：
  1. 识人拔擢
  2. 容谏纳言
  3. 授权专任

* **证据强度（linked_strengths）**：
  1. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因稳定上探
  2. 不得因后续改制上探
  3. 不得因边疆收益上探

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 不回填辅政后效
  2. 不回填纠错效果
  3. 不回填西域战功

* **簇内角色（linked_cluster_roles）**：
  1. 正向增厚

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 西域战果、军事胜负、边疆收益、辅政后的政务成效、政治稳定与政策纠错效果均不得回填第五项B；本证据组只保留识人、任用、授权、求言与反馈入口。
  2. B项只计识人、任用与人才结构；辅政后的政务成效、政治稳定与制度收益切第二项或第五项C。
  3. B项只计反馈入口与表达安全；后续纠错、行政调整和政策效果切第二项B2、第二项B3或第五项E。
  4. B项只计任用、遣使与授权秩序；伊吾、西域战果与边疆收益切第一项/第三项，行政后效切第二项。

---

**ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001｜负向｜候选强度（candidate_strength）=3｜中负边界**

* **簇类型（cluster_type）**：人才安全与政治牵连风险
* **边界档（boundary_tier）**：相邻项剥离后中度剩余
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 楚狱边界负证

* **证据角色（linked_evidence_roles）**：
  1. 强负核心

* **触发类型（linked_trigger_families）**：
  1. 疑忌杀害

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探极负

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离政权安全与司法严酷

* **簇内角色（linked_cluster_roles）**：
  1. 强负核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 楚王英案中的宗室控制、谋反与政权安全切第五项C；坐死徙者以千数、司法严酷与政治残酷性切第五项D；行政威慑或吏治效果切第二项B3。本证据组只保留人才安全感、牵连扩大与表达生态受损。
  2. B项只计高压问责、牵连扩大与人才安全感；权力集中和宗室控制切第五项C，行政威慑/吏治效果切第二项B3，政治残酷性切第五项D。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUZHUANG-POS-TALENT-AUTHORIZATION-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001"
]
```
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：1
* **强负证据数量（strong_negative_count）**：1
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：3
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.33
* **是否有高价值对象锚点（has_high_value_object_anchor）**：是
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：相邻项剥离后中度剩余
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：中

### 触发的规则敏感点

- **相邻项主导剥离**：大案本身严重不等于第五项B强负；剥离后只保留 B 项剩余影响。
- **B项剩余默认中负**：默认中负剩余；只有直接寒蝉、群臣莫敢正言、人才退缩或授权可信度破坏等硬证时，才保留强负核心。

### 自动结算结论

- **自动结算方向（band_direction）**：中正受中负压制
- **置信度（confidence）**：中
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 嬴政

### 证据簇自动结算

**ADJ-I5B-YINGZHENG-POS-TALENT-AUTHORIZATION-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：talent_channel_and_military_authorization
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 李斯客卿通道
  2. 王翦伐楚授权

* **证据角色（linked_evidence_roles）**：
  1. 强正核心

* **触发类型（linked_trigger_families）**：
  1. 容谏纳言
  2. 授权专任

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因秦统一结果上探极正
  2. 不得因统一结果上探极正

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离统一战略收益
  2. 剥离灭楚战果

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 统一战争收益切第一项/第三项；制度建设切第二项；本簇只保留容谏、复用客卿和授权专任。
  2. 客卿政策对统一战略的收益切第一项/第六项；制度化客卿通道效果切第二项；B项只保留容谏、复官和人才通道剩余影响。
  3. 灭楚胜负、统一结果和军事收益切第一项/第三项；B项只保留重新选择将帅、接受专业判断和授权专任。

---

**ADJ-I5B-YINGZHENG-NEG-EXPRESSION-SAFETY-001｜负向｜候选强度（candidate_strength）=3｜中负边界**

* **簇类型（cluster_type）**：expression_safety_and_talent_ecology_risk
* **边界档（boundary_tier）**：相邻项剥离后中度剩余
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 焚书表达安全

* **证据角色（linked_evidence_roles）**：
  1. 中负候选

* **触发类型（linked_trigger_families）**：
  1. 表达安全

* **证据强度（linked_strengths）**：
  1. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探极负

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离思想控制和刑罚残酷性

* **簇内角色（linked_cluster_roles）**：
  1. 负向核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 思想控制切第五项E；刑罚残酷性切第五项D；政权安全切第五项C；本簇只保留表达安全和人才生态剩余影响。
  2. 思想控制和认知路线切第五项E；弃市、族等刑罚残酷性切第五项D；政权安全控制切第五项C；B项只保留表达安全和人才生态剩余影响。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-YINGZHENG-POS-TALENT-AUTHORIZATION-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-YINGZHENG-NEG-EXPRESSION-SAFETY-001"
]
```
* **正向核心数量（core_positive_count）**：2
* **强正证据数量（strong_positive_count）**：2
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：1
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：2
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：人才生态、授权专任
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.5
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：弱至中
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：中

### 触发的规则敏感点

- **弱负上调中负边界**：不阻断极正或高位上探；只降低置信度，不进入强负核心。

### 自动结算结论

- **自动结算方向（band_direction）**：强正封顶，不上探极正
- **置信度（confidence）**：中偏高
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 刘邦

### 证据簇自动结算

**ADJ-I5B-LIUBANG-POS-TALENT-AUTHORIZATION-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：talent_selection_authorization_feedback_and_integration
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 三杰分工与吾能用之
  2. 张良容谏与采纳
  3. 异质人才整合与授权
  4. 高自主权授权

* **证据角色（linked_evidence_roles）**：
  1. 强正核心
  2. 中正锚点

* **触发类型（linked_trigger_families）**：
  1. 识人拔擢
  2. 容谏反馈
  3. 异质人才整合
  4. 授权专任

* **证据强度（linked_strengths）**：
  1. 3
  2. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因结果论上探
  2. 不得因入关结果上探
  3. 不得因军事计策上探
  4. 不得因战果上探

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 不回填楚汉胜负
  2. 不回填入秦成果
  3. 不回填反间计成效
  4. 不回填韩信破齐

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心
  2. 正向增厚

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 楚汉胜负、具体战役成败、韩信破齐等军事成果切第一项/第三项；萧何治理与后勤效果切第二项或治理项；齐地政权安全和异姓王控制切第五项C；高祖得天下光环不得回填第五项B。本证据组只保留识人、分工、授权、反馈入口、异质人才整合。
  2. 战役胜负切第一/第三项；萧何治理效果切第二项；高祖自我总结可能带有结果论，B项只保留识人、任用与分工意识。
  3. 具体军事胜负切第一/第三项；霸上政治策略后效切第五项C或第二项；B项只计反馈入口、纳言与采纳谋臣意见。
  4. 反间计具体成效切第一/第三项或第五项C；陈平个人品行争议只作任用风险背景；B项只计识别异质人才、压住群议并授予护军职责。
  5. 韩信破齐及后续军事战果切第一/第三项；齐地政权安全和异姓王控制切第五项C；B项只计高自主权授权与听取张良意见后的托付。

---

**ADJ-I5B-LIUBANG-NEG-MERIT-SUBJECT-SAFETY-001｜负向｜候选强度（candidate_strength）=3｜强负候选**

* **簇类型（cluster_type）**：merit_subject_safety_trust_reversal_and_chilling_effect
* **边界档（boundary_tier）**：中至强
* **是否阻断极限档（blocking_extreme）**：是
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 功臣安全与授权预期
  2. 功臣处置反复
  3. 同功群体寒蝉

* **证据角色（linked_evidence_roles）**：
  1. 中负核心
  2. 强负核心

* **触发类型（linked_trigger_families）**：
  1. 功臣安全

* **证据强度（linked_strengths）**：
  1. 2
  2. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因陈豨案上探
  2. 不得因族灭上探
  3. 不得因军事威胁上探

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 不回填谋反定性
  2. 不回填谋反安全
  3. 不回填英布叛乱

* **簇内角色（linked_cluster_roles）**：
  1. 负向核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 韩信陈豨案、彭越谋反嫌疑、英布叛乱、异姓王控制与军事威胁切第五项C；夷三族、醢刑、刑罚残酷和政治残酷性切第五项D；本证据组只保留功臣安全感、授权预期、同功群体恐惧和人才生态寒蝉效应。
  2. 谋反事实、陈豨案与政权安全切第五项C；刑罚严酷和夷三族切第五项D；B项只保留功臣安全感、授权预期与人才生态信号。
  3. 征兵不至、谋反风险和异姓王控制切第五项C；族灭与刑罚严酷切第五项D；B项只保留高功臣处置反复对功臣安全感和授权预期的剩余影响。
  4. 英布叛乱、军事威胁和异姓王控制切第五项C；醢刑残酷切第五项D；B项只计功臣群体安全感、人才生态寒蝉效应和授权秩序外溢受损。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUBANG-POS-TALENT-AUTHORIZATION-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUBANG-NEG-MERIT-SUBJECT-SAFETY-001"
]
```
* **正向核心数量（core_positive_count）**：3
* **强正证据数量（strong_positive_count）**：3
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：3
* **强负证据数量（strong_negative_count）**：1
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：4
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：识人任用、人才生态
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.14
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：是
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：中至强
* **负向边界是否阻断（negative_boundary_blocking）**：是
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：强

### 触发的规则敏感点

- **中负上调强负边界**：阻断极正/高位上探；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。
- **强负核心压制强正**：保留强正基础，但自动标记为强正受压制，不上探极正。

### 自动结算结论

- **自动结算方向（band_direction）**：强正受压制，不上探极正
- **置信度（confidence）**：中偏高
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 刘恒

### 证据簇自动结算

**ADJ-I5B-LIUHENG-POS-FEEDBACK-TALENT-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：remonstrance_feedback_and_talent_recognition
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 张释之执法进谏
  2. 冯唐魏尚复用链
  3. 贾谊早期拔擢

* **证据角色（linked_evidence_roles）**：
  1. 强正核心
  2. 中正核心

* **触发类型（linked_trigger_families）**：
  1. 容谏纳言
  2. 容人复用
  3. 识人拔擢

* **证据强度（linked_strengths）**：
  1. 3
  2. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因文景之治上探极正
  2. 不得因文景之治或边防收益上探极正
  3. 不得单凭贾谊早期超迁上探强正

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离刑法宽平成效
  2. 剥离边郡军事得失
  3. 剥离贾谊政策成败

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心
  2. 正向补强

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 刑法宽平切第二项；边郡军事切第三项；文景之治总成效不得回填B项；本簇只保留容谏、反馈入口、复用和识才。
  2. 刑法宽平和司法制度成效切第二项；个案处罚轻重不回填B项；B项只保留专业反馈入口和容谏空间。
  3. 边郡军事得失切第三项；赏罚制度效果切第二项；B项只保留听取反馈和人才复用。
  4. 贾谊政策主张成败切第六项或第二项；后续疏远另入负证；B项只保留早期识才拔擢。

---

**ADJ-I5B-LIUHENG-NEG-JIAYI-TALENT-CHANNEL-001｜负向｜候选强度（candidate_strength）=3｜中负边界**

* **簇类型（cluster_type）**：new_talent_channel_blocked
* **边界档（boundary_tier）**：相邻项剥离后中度剩余
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 贾谊疏远外放

* **证据角色（linked_evidence_roles）**：
  1. 中负候选

* **触发类型（linked_trigger_families）**：
  1. 人才保护不足

* **证据强度（linked_strengths）**：
  1. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探强负

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离老臣政治平衡和政策成败

* **簇内角色（linked_cluster_roles）**：
  1. 负向核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 老臣政治平衡切第五项C或第一项B；贾谊政策主张成败切第二项/第六项；本簇只保留人才保护不足和建言通道受阻。
  2. 老臣政治平衡切第五项C或第一项B；贾谊政策主张成败切第六项/第二项；B项只保留新进人才保护和建言通道受阻。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUHENG-POS-FEEDBACK-TALENT-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUHENG-NEG-JIAYI-TALENT-CHANNEL-001"
]
```
* **正向核心数量（core_positive_count）**：3
* **强正证据数量（strong_positive_count）**：2
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：1
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：3
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：人才生态
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：弱至中
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：中

### 触发的规则敏感点

- **弱负上调中负边界**：不阻断极正或高位上探；只降低置信度，不进入强负核心。

### 自动结算结论

- **自动结算方向（band_direction）**：高位强正，上探极正候选
- **置信度（confidence）**：高偏中
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 刘彻

### 证据簇自动结算

**ADJ-I5B-LIUCHE-POS-TALENT-AUTHORIZATION-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：military_talent_selection_and_authorization
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 卫青军事授权

* **证据角色（linked_evidence_roles）**：
  1. 强正核心

* **触发类型（linked_trigger_families）**：
  1. 授权专任

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因战果上探极正

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离战果与开边收益

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 战役胜负、俘获数量、开边收益和军事结果切第一项/第三项；本簇只保留拜将、授权和人才结构。
  2. 战役胜负、俘获数量、开边收益和军事结果切第一项/第三项；B项只保留识人、拜将和授权结构。

---

**ADJ-I5B-LIUCHE-NEG-KULI-TALENT-SAFETY-001｜负向｜候选强度（candidate_strength）=3｜中负边界**

* **簇类型（cluster_type）**：cruel_official_authorization_and_talent_safety
* **边界档（boundary_tier）**：相邻项剥离后中度剩余
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 酷吏授权风险

* **证据角色（linked_evidence_roles）**：
  1. 强负核心

* **触发类型（linked_trigger_families）**：
  1. 权奸酷吏授权

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探极负

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离司法残酷性

* **簇内角色（linked_cluster_roles）**：
  1. 强负核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 刑狱严酷、政治残酷性和具体冤滥切第五项D；政权安全案件切第五项C；本簇只计酷吏授权对人才安全感和表达生态的剩余影响。
  2. 刑狱严酷、个案冤滥和政治残酷性切第五项D；政权安全案件切第五项C；B项只保留酷吏被授权后对人才安全与表达生态的剩余影响。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUCHE-POS-TALENT-AUTHORIZATION-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUCHE-NEG-KULI-TALENT-SAFETY-001"
]
```
* **正向核心数量（core_positive_count）**：1
* **强正证据数量（strong_positive_count）**：1
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：1
* **强负证据数量（strong_negative_count）**：1
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：1
* **是否单维集中（single_dimension_flag）**：是
* **正向规则核心覆盖（positive_rule_cores）**：识人任用
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：1.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：相邻项剥离后中度剩余
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：中

### 触发的规则敏感点

- **相邻项主导剥离**：大案本身严重不等于第五项B强负；剥离后只保留 B 项剩余影响。
- **B项剩余默认中负**：默认中负剩余；只有直接寒蝉、群臣莫敢正言、人才退缩或授权可信度破坏等硬证时，才保留强负核心。

### 自动结算结论

- **自动结算方向（band_direction）**：强正封顶，不上探极正
- **置信度（confidence）**：中偏高
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 刘询

### 证据簇自动结算

**ADJ-I5B-LIUXUN-POS-FEEDBACK-TALENT-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：talent_recognition_and_administrative_authorization
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 丙吉荐才知人
  2. 黄霸循吏任用

* **证据角色（linked_evidence_roles）**：
  1. 强正核心
  2. 中正补强

* **触发类型（linked_trigger_families）**：
  1. 识人拔擢
  2. 授权专任

* **证据强度（linked_strengths）**：
  1. 3
  2. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因中兴光环上探极正
  2. 不得因循吏政绩上探极正

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离宣帝朝总成效
  2. 剥离地方治理成效

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心
  2. 正向补强

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 宣帝中兴、地方治理效果和吏治总成效不得回填第五项B；本簇只保留识才、荐才、授权和任职反馈。
  2. 宣帝朝吏治总成效和麒麟阁政治评价切第二项或总评项；B项只保留荐才、识才和任职反馈。
  3. 颍川治理成效和民生结果切第二项；B项只保留识别、拔擢和授权链。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUXUN-POS-FEEDBACK-TALENT-001"
]
```
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：1
* **强正证据数量（strong_positive_count）**：1
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：2
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：识人任用
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.5
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：强正封顶，不上探极正
- **置信度（confidence）**：中偏高
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 刘启

### 证据簇自动结算

**ADJ-I5B-LIUQI-POS-MILITARY-AUTH-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：crisis_military_authorization
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 周亚夫太尉授权

* **证据角色（linked_evidence_roles）**：
  1. 中正核心

* **触发类型（linked_trigger_families）**：
  1. 授权专任

* **证据强度（linked_strengths）**：
  1. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因平乱战果上探强正

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离七国乱战果

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 七国之乱平定和军事胜负切第一项/第三项/第五项C；本簇只保留周亚夫授权。
  2. 七国之乱平定、军事胜负和政权安全切第一项/第三项/第五项C；B项只保留授权结构。

---

**ADJ-I5B-LIUQI-NEG-TALENT-SAFETY-001｜负向｜候选强度（candidate_strength）=3｜强负候选**

* **簇类型（cluster_type）**：minister_safety_and_authorization_reversal
* **边界档（boundary_tier）**：中至强
* **是否阻断极限档（blocking_extreme）**：是
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 晁错人才安全
  2. 周亚夫授权反转

* **证据角色（linked_evidence_roles）**：
  1. 强负核心

* **触发类型（linked_trigger_families）**：
  1. 功臣旧臣处置

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探极负

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离七国乱政权安全
  2. 剥离甲楯案和储位政治

* **簇内角色（linked_cluster_roles）**：
  1. 强负核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 削藩政策、七国之乱、储位政治、政权安全和司法残酷性切相邻项；本簇只保留人才安全和授权可信度反转。
  2. 削藩政策正确性、七国之乱和政权安全切第二项/第五项C；刑罚残酷性切第五项D；B项只保留人才安全和授权可信度剩余影响。
  3. 甲楯案事实、储位政治、政权安全和司法残酷性切第五项C/D；B项只保留功臣安全与授权反转。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUQI-POS-MILITARY-AUTH-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-LIUQI-NEG-TALENT-SAFETY-001"
]
```
* **正向核心数量（core_positive_count）**：1
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：2
* **强负证据数量（strong_negative_count）**：2
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：1
* **是否单维集中（single_dimension_flag）**：是
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：1.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：是
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：中至强
* **负向边界是否阻断（negative_boundary_blocking）**：是
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：强

### 触发的规则敏感点

- **中负上调强负边界**：阻断极正/高位上探；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。
- **强负核心压制强正**：保留强正基础，但自动标记为强正受压制，不上探极正。

### 自动结算结论

- **自动结算方向（band_direction）**：中正受强负压制
- **置信度（confidence）**：中
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 杨坚

### 证据簇自动结算

**ADJ-I5B-YANGJIAN-POS-TALENT-FEEDBACK-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：central_talent_authorization_and_feedback
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 高颎中枢授权
  2. 苏威容谏反馈

* **证据角色（linked_evidence_roles）**：
  1. 强正核心

* **触发类型（linked_trigger_families）**：
  1. 识人拔擢
  2. 容谏反馈

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因开皇治绩上探极正

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离平乱战果
  2. 剥离具体案件法理

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 开皇制度成效、平乱战果、军事征伐结果和政策效果不得回填第五项B；本簇只保留识人、授权和容谏反馈。
  2. 尉迥平定、军事胜负和开皇制度成效切第一项/第三项或第二项；B项只保留识人、拔擢和授权结构。
  3. 具体案件刑罚、行政法理和政策成效切第五项D或第二项；B项只保留容谏反馈和表达入口。

---

**ADJ-I5B-YANGJIAN-NEG-MERIT-SUBJECT-SAFETY-001｜负向｜候选强度（candidate_strength）=3｜中负边界**

* **簇类型（cluster_type）**：merit_subject_safety_and_trust_reversal
* **边界档（boundary_tier）**：相邻项剥离后中度剩余
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 史万岁功臣安全

* **证据角色（linked_evidence_roles）**：
  1. 强负核心

* **触发类型（linked_trigger_families）**：
  1. 功臣安全

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探极负

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离军功争议和刑罚残酷性

* **簇内角色（linked_cluster_roles）**：
  1. 强负核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 军功争议、军事行政责任和政权安全切第五项C或第一/第三项；杀戮和刑罚残酷性切第五项D；本簇只保留功臣/能臣安全、授权可信度和表达生态剩余影响。
  2. 南宁处置、军功争议、政权安全和军事行政背景切第五项C或第一/第三项；杀戮和刑罚残酷性切第五项D；B项只保留功臣/能臣安全与表达生态剩余影响。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-YANGJIAN-POS-TALENT-FEEDBACK-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-YANGJIAN-NEG-MERIT-SUBJECT-SAFETY-001"
]
```
* **正向核心数量（core_positive_count）**：2
* **强正证据数量（strong_positive_count）**：2
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：1
* **强负证据数量（strong_negative_count）**：1
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：2
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：识人任用、人才生态
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：相邻项剥离后中度剩余
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：中

### 触发的规则敏感点

- **相邻项主导剥离**：大案本身严重不等于第五项B强负；剥离后只保留 B 项剩余影响。
- **B项剩余默认中负**：默认中负剩余；只有直接寒蝉、群臣莫敢正言、人才退缩或授权可信度破坏等硬证时，才保留强负核心。

### 自动结算结论

- **自动结算方向（band_direction）**：强正封顶，不上探极正
- **置信度（confidence）**：中偏高
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 杨广

### 证据簇自动结算

**ADJ-I5B-YANGGUANG-POS-ADMIN-AUTH-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：administrative_confidential_authorization
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 虞世基机密授权

* **证据角色（linked_evidence_roles）**：
  1. 中正候选

* **触发类型（linked_trigger_families）**：
  1. 授权专任

* **证据强度（linked_strengths）**：
  1. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探强正

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 受同对象壅蔽负证限制

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 行政成败、隋末政局和政策后果不得回填第五项B；本簇只保留授权事实。
  2. 隋末政局、行政成败和政策后果切第一项/第二项/第五项C；B项只保留用才授权。

---

**ADJ-I5B-YANGGUANG-NEG-TALENT-FEEDBACK-SAFETY-001｜负向｜候选强度（candidate_strength）=3｜强负候选**

* **簇类型（cluster_type）**：old_minister_safety_and_feedback_blockage
* **边界档（boundary_tier）**：中至强
* **是否阻断极限档（blocking_extreme）**：是
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 高颎贺若弼旧臣安全
  2. 虞世基反馈壅蔽

* **证据角色（linked_evidence_roles）**：
  1. 强负核心

* **触发类型（linked_trigger_families）**：
  1. 功臣旧臣处置
  2. 容谏纳言

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得上探极负

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 剥离政权安全和刑罚残酷性
  2. 剥离隋末全局失败

* **簇内角色（linked_cluster_roles）**：
  1. 强负核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 政权安全、刑罚残酷、隋末军事政治失败和王朝崩溃切相邻项；本簇只保留人才安全、容谏反馈和近臣壅蔽。
  2. 政权安全、前朝旧臣政治站位和刑罚残酷性切第五项C/D；B项只保留旧臣安全、人才生态和授权可信度剩余影响。
  3. 隋末政局、军事失败和政策后果切第一项/第二项/第五项C；B项只保留反馈入口壅蔽和近臣任用风险。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-YANGGUANG-POS-ADMIN-AUTH-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-YANGGUANG-NEG-TALENT-FEEDBACK-SAFETY-001"
]
```
* **正向核心数量（core_positive_count）**：1
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：2
* **强负证据数量（strong_negative_count）**：2
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：1
* **是否单维集中（single_dimension_flag）**：是
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：1.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：是
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：中至强
* **负向边界是否阻断（negative_boundary_blocking）**：是
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：强

### 触发的规则敏感点

- **中负上调强负边界**：阻断极正/高位上探；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。
- **强负核心压制强正**：保留强正基础，但自动标记为强正受压制，不上探极正。

### 自动结算结论

- **自动结算方向（band_direction）**：中正受强负压制
- **置信度（confidence）**：中
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 李隆基

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 武则天

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 李治

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 李渊

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 李纯

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 赵匡胤

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 赵恒

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 赵光义

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 赵构

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 赵祯

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 朱元璋

### 证据簇自动结算

**ADJ-I5B-ZHUYUANZHANG-POS-TALENT-AUTHORIZATION-001｜正向｜候选强度（candidate_strength）=3｜强正候选**

* **簇类型（cluster_type）**：人才选择与授权生态
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：强

* **对象锚点（linked_object_anchors）**：
  1. 开国识人
  2. 授权专任

* **证据角色（linked_evidence_roles）**：
  1. 强正核心

* **触发类型（linked_trigger_families）**：
  1. 识人拔擢
  2. 授权专任

* **证据强度（linked_strengths）**：
  1. 3

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因盛世上探
  2. 不得因战功上探

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 不回填开国战果
  2. 不回填后续制度效应

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 战功、统一成果与制度后效切第一项/第二项/第三项。
  2. 战功和统一成果切第一项/第三项；制度成效切第二项。
  3. 战功、制度成效和后续治理切第一项/第二项/第三项。

---

**ADJ-I5B-ZHUYUANZHANG-NEG-MERIT-PURGE-001｜负向｜候选强度（candidate_strength）=3｜中负边界**

* **簇类型（cluster_type）**：merit_subject_purge_and_security_case
* **边界档（boundary_tier）**：相邻项剥离后中度剩余
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 人才生态清洗
  2. 功臣安全反复

* **证据角色（linked_evidence_roles）**：
  1. 强负核心
  2. 中负核心

* **触发类型（linked_trigger_families）**：
  1. 系统性清洗
  2. 功臣安全

* **证据强度（linked_strengths）**：
  1. 3
  2. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因党案上探
  2. 不得因后续制度上探

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 不回填政权安全
  2. 不回填党案安全

* **簇内角色（linked_cluster_roles）**：
  1. 负向核心
  2. 负向增厚

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 政权安全、党案与刑罚严酷切第五项C/D。
  2. 政权安全与真实谋反链条切第五项C；刑罚严酷切第五项D。
  3. 党案和政权安全切第五项C；刑罚严酷切第五项D。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-ZHUYUANZHANG-POS-TALENT-AUTHORIZATION-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-ZHUYUANZHANG-NEG-MERIT-PURGE-001"
]
```
* **正向核心数量（core_positive_count）**：2
* **强正证据数量（strong_positive_count）**：4
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：2
* **强负证据数量（strong_negative_count）**：5
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：3
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：识人任用、授权专任
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.17
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：是
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：中至强
* **负向边界是否阻断（negative_boundary_blocking）**：是
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：强

### 触发的规则敏感点

- **中负上调强负边界**：阻断极正/高位上探；进入强负核心或强负拦截候选，但仍不得机械扩大到极负。
- **强负核心压制强正**：保留强正基础，但自动标记为强正受压制，不上探极正。

### 自动结算结论

- **自动结算方向（band_direction）**：强正受压制，不上探极正
- **置信度（confidence）**：中偏高
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 朱棣

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 朱瞻基

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 朱由检

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 皇太极

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 玄烨

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 雍正

### 证据簇自动结算

**ADJ-I5B-YONGZHENG-POS-TALENT-FEEDBACK-001｜正向｜候选强度（candidate_strength）=2｜中正增厚**

* **簇类型（cluster_type）**：talent_recruitment_and_feedback_channel
* **边界档（boundary_tier）**：无
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 识人与反馈入口
  2. 制度执行入口

* **证据角色（linked_evidence_roles）**：
  1. 中正核心
  2. 中正增厚

* **触发类型（linked_trigger_families）**：
  1. 识人拔擢
  2. 制度执行

* **证据强度（linked_strengths）**：
  1. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因后效上探
  2. 不得因整饬上探

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 不回填后续政务
  2. 不回填治理结果

* **簇内角色（linked_cluster_roles）**：
  1. 正向核心
  2. 正向增厚

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 政务整饬、财政整理和最终治理成效切第二项；政治残酷性切第五项D。
  2. 政务整饬切第二项；政治残酷性切第五项D。
  3. 政务执行切第二项；表达安全切第五项C/D。

---

**ADJ-I5B-YONGZHENG-NEG-TRUST-ECOSYSTEM-001｜负向｜候选强度（candidate_strength）=2｜中负边界**

* **簇类型（cluster_type）**：trust_ecology_and_expression_suppression
* **边界档（boundary_tier）**：弱至中
* **是否阻断极限档（blocking_extreme）**：否
* **剩余强度（residual_level）**：中

* **对象锚点（linked_object_anchors）**：
  1. 近臣表达安全
  2. 异议表达边界

* **证据角色（linked_evidence_roles）**：
  1. 中负核心

* **触发类型（linked_trigger_families）**：
  1. 近臣高压
  2. 表达安全

* **证据强度（linked_strengths）**：
  1. 2

* **上限封顶标记（linked_upper_bound_flags）**：
  1. 不得因整饬上探
  2. 不得因高压上探

* **减轻/剥离标记（linked_mitigation_flags）**：
  1. 不回填政务问责
  2. 不回填整饬成效

* **簇内角色（linked_cluster_roles）**：
  1. 负向核心
  2. 负向增厚

* **相邻项剥离说明（cross_item_split_signals）**：
  1. 政权安全、刑罚严酷和明确谋反链条切第五项C/D。
  2. 政务整饬切第二项；政权安全与司法严酷切第五项C/D。
  3. 政务整饬切第二项；集权与表达安全切第五项C/D。

### 自动特征

* **正向证据簇（positive_cluster_ids）**：
```json
[
  "ADJ-I5B-YONGZHENG-POS-TALENT-FEEDBACK-001"
]
```
* **负向证据簇（negative_cluster_ids）**：
```json
[
  "ADJ-I5B-YONGZHENG-NEG-TRUST-ECOSYSTEM-001"
]
```
* **正向核心数量（core_positive_count）**：1
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：2
* **强负证据数量（strong_negative_count）**：1
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：4
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：是
* **是否有减轻/剥离标记（has_mitigation_flag）**：是
* **是否有上限封顶标记（has_upper_bound_flag）**：是
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：相邻项剥离后中度剩余
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：中

### 触发的规则敏感点

- **相邻项主导剥离**：大案本身严重不等于第五项B强负；剥离后只保留 B 项剩余影响。
- **B项剩余默认中负**：默认中负剩余；只有直接寒蝉、群臣莫敢正言、人才退缩或授权可信度破坏等硬证时，才保留强负核心。

### 自动结算结论

- **自动结算方向（band_direction）**：中正受中负压制
- **置信度（confidence）**：中
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。

## 弘历

### 证据簇自动结算

无证据簇：当前人物暂无 I5B 证据卡/证据簇，本页仅为 full-pool stress 占位审查页，不代表已完成自动结算或正式评分。

- **证据状态**：missing_evidence
- **评分状态**：unscored / blocked_before_formal_score

* **对象锚点（linked_object_anchors）**：无

* **相邻项剥离说明（cross_item_split_signals）**：无

### 自动特征

* **正向证据簇（positive_cluster_ids）**：无
* **负向证据簇（negative_cluster_ids）**：无
* **正向核心数量（core_positive_count）**：0
* **强正证据数量（strong_positive_count）**：0
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：0
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：0
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：无
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.0
* **是否有高价值对象锚点（has_high_value_object_anchor）**：否
* **是否有边界证据（has_boundary_evidence）**：否
* **是否有减轻/剥离标记（has_mitigation_flag）**：否
* **是否有上限封顶标记（has_upper_bound_flag）**：否
* **是否有强负核心（has_strong_negative_core）**：否
* **是否有极强负核心（has_extreme_negative_core）**：否
* **负向边界档（negative_boundary_tier）**：无
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：否
* **剥离后剩余强度（cross_item_split_residual_level）**：无

### 触发的规则敏感点


### 自动结算结论

- **自动结算方向（band_direction）**：自动草案待规则复核
- **置信度（confidence）**：中偏低
- **不回填相邻项说明**：战果、政务成效、边疆收益、政权安全、司法残酷和治世光环均切出第五项B。
