# 第五项B扩展第一批自动结算草案

本文件由现有 `evidence_cards` / `evidence_clusters` / `thematic_anchors` 规则派生，只输出 band direction、confidence 与规则敏感点，不生成分数、排名或总榜。

- **活动人物组**：扩展第一批
- **覆盖人物**：刘邦、雍正、朱元璋

## 自动结算总览

| 人物（person） | 自动结算方向（auto_band_direction） | 置信度（confidence） | 负向边界档（negative_boundary_tier） | 规则敏感点（rule_sensitive_points） |
| --- | --- | --- | --- | --- |
| 刘邦 | 强正受压制，不上探极正 | 中偏高 | 中至强 | 中负上调强负边界；强负核心压制强正 |
| 雍正 | 中正受中负压制 | 中 | 弱至中 | 弱负上调中负边界 |
| 朱元璋 | 强正封顶，不上探极正 | 中偏高 | 相邻项剥离后中度剩余 | 相邻项主导剥离；B项剩余默认中负 |

## 逐人自动草案

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
* **覆盖维度数量（coverage_dimension_count）**：3
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：识人任用、人才生态
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.2
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
* **强负证据数量（strong_negative_count）**：0
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：2
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
* **负向边界档（negative_boundary_tier）**：弱至中
* **负向边界是否阻断（negative_boundary_blocking）**：否
* **是否需要相邻项剥离（cross_item_split_required）**：是
* **剥离后剩余强度（cross_item_split_residual_level）**：中

### 触发的规则敏感点

- **弱负上调中负边界**：不阻断极正或高位上探；只降低置信度，不进入强负核心。

### 自动结算结论

- **自动结算方向（band_direction）**：中正受中负压制
- **置信度（confidence）**：中
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
* **强正证据数量（strong_positive_count）**：2
* **极强正证据数量（extreme_positive_count）**：0
* **负向核心数量（core_negative_count）**：2
* **强负证据数量（strong_negative_count）**：1
* **极强负证据数量（extreme_negative_count）**：0
* **覆盖维度数量（coverage_dimension_count）**：2
* **是否单维集中（single_dimension_flag）**：否
* **正向规则核心覆盖（positive_rule_cores）**：识人任用、授权专任
* **是否满足三核心覆盖（positive_three_core_coverage）**：否
* **创业期正证占比（startup_positive_share）**：0.5
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
