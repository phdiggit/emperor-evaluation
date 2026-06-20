# 第五项B证据簇裁判配置层设计审计

## 1. 当前链路概览

当前第五项B证据链路大致分为四层：

1. 证据卡层：`data/evidence_cards.jsonl`
   - 记录原子证据，核心字段包括 `evidence_id`、`person`、`subitem`、`polarity`、`strength`、`human_level`、`source_id`、`trigger_family`、`trigger_terms`、`cross_item_split`、`scoring_effect`、`adjudication_status`。
   - `validate_evidence.py` 已校验极性、强度、人类档位、强负/极负必要切分、高风险负证补充字段和强证待人工裁判状态。

2. 证据簇层：`data/evidence_clusters.jsonl`
   - 聚合多个证据卡，核心字段包括 `cluster_id`、`cluster_type`、`polarity`、`linked_evidence_ids`、`five_axis_assessment`、`candidate_strength`、`upper_probe`、`cross_item_split`、`adjudication_status`。
   - 当前 validator 已校验 `linked_evidence_ids` 引用、单卡成簇强度下限、`candidate_strength` 范围、`candidate_strength=4` 必须待人工裁判。

3. 批次裁判草案层：`data/adjudication_batches/*.jsonl`
   - `i5b_expanded_pilot_batch1_cluster_adjudication_20260619.jsonl` 记录正负簇摘要、相邻项切分、负证拦截、规则压力和 `net_adjudication_draft`。
   - `i5b_expanded_pilot_batch1_post_supplement_adjudication_20260619.jsonl` 记录补证前后影响、role-class sweep 影响、补证后负证拦截、相邻项切分和净裁量草案。
   - 这些文件已经接近人工会审准备层，不应被普通配置直接覆盖。

4. 导出和自动草案层：`scripts/export_i5b_auto_adjudication.py`
   - 读取证据卡与证据簇，推导 `negative_boundary_tier`、`negative_boundary_blocking`、`cross_item_split_residual_level`、`auto_band_direction`、`confidence`、规则敏感点、正式档位草案和内部试算草案。
   - 脚本输出多份 markdown，包括自动结算草案、规则敏感点清单、正式定档落地表、评分标尺草案和内部闭环收尾。
   - 这条链路已有明确声明：不直接出正式分、不排名、不出总榜。

设计判断：

- 证据卡、证据簇、人物临时定档、分数是分层流程。
- 证据簇规则最多辅助人工复核和提示风险，不应直接生成正式分数、正式定档或排名。
- 配置层应该先抽出“提示和边界”，不应把 `export_i5b_auto_adjudication.py` 当前的自动草案逻辑原样固化为正式配置。

## 2. 当前裁判规则分布

当前规则散落在以下位置：

| 位置 | 当前承载内容 | 风险判断 |
| --- | --- | --- |
| `docs/manual_review_config_layer_design_20260620.md` | review config 与 protected rule config 分层、证据簇 merge/grading 配置方向 | 是本次设计的上位分层依据 |
| `docs/config_granularity_redesign_20260620.md` | 长期中文配置目录、人工复核配置、受保护规则配置目录方向 | 是目录命名依据 |
| `data/configs/人工复核配置/README.md` | 人工复核配置只作检索画像/辅助，不代表证据、评分、裁判、定档 | 可复用为安全声明模板 |
| `data/configs/视图配置/第五项B_人物池.json` | 人物风险画像、相邻项污染风险、负证扫描重点 | 可作为配置设计时的风险来源，不能反向支配史料 |
| `data/configs/视图配置/第五项B_视图分组.json` | 三人试点、扩展第一批、净证据导出目标 | 只定义对象集合，不定义裁判规则 |
| `data/evidence_cards.jsonl` | 原子证据强度、人类档位、cross item split、scoring effect、adjudication status | 是事实与候选定级数据，不应在本任务修改 |
| `data/evidence_clusters.jsonl` | 证据簇候选强度、upper probe、cross item split、adjudication status | 是簇级数据，不应在本任务修改 |
| `data/adjudication_batches/*.jsonl` | 批次级净裁量草案、相邻项切分、补证后结算、规则压力摘要 | 已接近人工会审准备，不应自动升级为正式配置 |
| `scripts/export_i5b_auto_adjudication.py` | 当前最集中的规则敏感逻辑和导出渲染混合体 | 后续应拆出提示/边界，不应直接配置化为自动裁判 |
| `scripts/validate_evidence.py` | 证据卡和证据簇的基础结构、引用、强度、人审状态护栏 | 后续新 validator 可复用其字段约束思想 |
| tests | 对强负、极负、人审状态、单卡成簇、自动草案不出分不排名的行为锁定 | 是安全边界的测试证据 |

重要观察：

- 文档层强调分层和禁止自动正式结果。
- 脚本层已经有可抽象的规则敏感点，但也混入了 `auto_band_direction`、正式档位草案和内部试算草案。
- 数据层保留了大量“草案”“待人工裁判”“不得直接入分”的字段。
- 测试层明确要求强证待人工裁判，并多次断言导出不应包含正式评分、排名和总榜。

## 3. 适合配置化的规则

适合配置化的内容应满足三个条件：

- 只描述“发现什么风险或触发什么提示”；
- 不直接改变证据卡、证据簇或人物最终结论；
- 输出结果仍然需要人工复核或人工确认。

建议优先配置化：

1. 证据簇极性与强度提示
   - `polarity_scope`: positive / negative / both
   - `evidence_strength_scope`: weak / medium / strong / extreme / candidate_strength 范围
   - 用途：提醒 reviewer 该证据簇可能需要额外核验。

2. 正负证并存提示
   - 例如强正底盘和强负核心同时存在时，提示“保留并存关系，不做简单抵消”。
   - 只能提示，不得自动给出人物最终档位。

3. 相邻项污染提示
   - 例如统一功业、军功、行政成效、财政整饬、政权安全、司法严酷、治世光环不应直接回填第五项B。
   - 可作为 `warning_type = adjacent_item_contamination`。

4. 单证不足提示
   - 当前 validator 已有单卡成簇强度下限。配置层可进一步提示“单一中负不能自动形成强负核心”。
   - 只用于提示，不应推翻 validator。

5. 需要回源核验提示
   - 例如强负核心候选、极正上探候选、同一来源支撑高等级判断、争议反转材料。
   - 可输出 required action：回源核验、复核原文、检查同源重复。

6. 需要人工复核提示
   - 例如 `candidate_strength >= 3`、`upper_probe` 非空、`negative_boundary_tier` 命中、`cross_item_split` 有相邻项风险。
   - 字段应是 `required_human_review: true`，而不是自动结论。

7. 关键词触发后的裁判注意事项
   - 连接前一层人工复核关键词配置。
   - 例如酷吏、告密、寒蝉、功臣处置、纳谏、授权等词命中后，提示 reviewer 检查相邻项切分和证据强度，不直接判断人物。

8. 同源去重和覆盖厚度提示
   - 可提示同一来源、同一事件、同一对象是否只是重复覆盖。
   - 不能自动把多条同源证据加总为更高强度。

9. role-class sweep 防漏提示
   - 当前批次里已有 role-class sweep 经验。
   - 可提示“边疆授权对象、督抚、近臣、功臣、谏臣等角色类是否漏扫”，但不直接生成证据或档位。

## 4. 不适合配置化的规则

以下内容不应进入普通可编辑配置，也不应在本阶段配置化：

1. 某人物最终档位
   - 例如“刘邦最终强正受压制”“朱元璋最终强负候选”。
   - 这类结论必须来自完整证据链和人工裁判。

2. 某人物正式分数或内部试算分
   - `final_score`、`trial_score`、`score_range` 等均不适合进入普通裁判提示配置。
   - 档位到分数映射若未来存在，也应属于最高保护层。

3. 证据簇自动压制或自动升档
   - “强负核心压制强正”可以作为提示边界。
   - 但不能配置成无需人工确认的自动压制结果。

4. 复杂史料解释
   - 争议文本、原文语境、后世评价取舍、同一事件的多义解释不能配置化替代。

5. 争议史料取舍
   - 某来源可信度、某段史料是否足以定性，必须人工裁判。

6. 跨项最终归属判断
   - 第五项B 与第五项C/D/E、第二项B2 等相邻项最终归属不能由普通配置一次性决定。

7. 人物标签反向主导史料
   - 人物池中的 `candidate_type`、`expected_rule_pressure` 只能提示审计风险，不能作为证据解释的前提。

8. 正式定档、排名、总榜
   - 所有 formal score / ranking / leaderboard 相关内容都应禁止进入本层配置。

## 5. 建议目录结构

建议沿用当前中文配置分层：

```text
data/configs/
  人工复核配置/
    第五项B_证据簇裁判提示.json
  受保护规则配置/
    第五项B_证据簇裁判边界.json
```

命名理由：

- `人工复核配置/第五项B_证据簇裁判提示.json`
  - 定位是提示 reviewer “这类证据簇需要注意什么”。
  - 它只影响复核路径，不生成结论。
  - 与现有 `第五项B_检索关键词基础.json`、`第五项B_检索关键词补丁.json` 同属人工复核辅助层。

- `受保护规则配置/第五项B_证据簇裁判边界.json`
  - 定位是保存不应轻易改动的规则边界。
  - 它比人工复核提示更敏感，必须带 required human confirmation。
  - 不能由普通用户把它当成“调参文件”随手修改。

本任务不新增上述配置文件，只建议后续路径。

## 6. schema 草案

### A. 人工复核提示配置

用途：

- 提示某类证据簇需要什么复核动作。
- 不产出人物结论，不产出簇结论，不修改强度。

建议文件：

```text
data/configs/人工复核配置/第五项B_证据簇裁判提示.json
```

建议顶层：

- formatted JSON
- 顶层 array
- 每个元素 object
- UTF-8 中文直写

建议字段：

| 字段 | 类型 | 要求 | 说明 |
| --- | --- | --- | --- |
| `rule_id` | string | 必填，唯一 | 例如 `I5B-CLUSTER-WARN-ADJACENT-CONTAMINATION` |
| `subitem` | string | 必填，固定 `第五项B` | 防止跨子项误用 |
| `trigger_type` | string | 必填 | 例如 `trigger_terms`、`cluster_field`、`strength_scope`、`cross_item_split` |
| `trigger_terms` | string array | 条件需要时必填 | 例如 `["统一", "军功", "行政成效"]` |
| `polarity_scope` | string array | 必填 | 允许 `positive`、`negative`、`both` 等受控值 |
| `evidence_strength_scope` | string array | 必填 | 例如 `["candidate_strength_3", "candidate_strength_4"]` |
| `warning_type` | string | 必填 | 例如 `adjacent_item_contamination`、`single_evidence_limit`、`source_review_required` |
| `warning_message` | string | 必填 | 给人工 reviewer 的提示文本 |
| `adjacent_item_risk` | string array | 可选 | 例如 `["第五项C", "第五项D", "第二项B2"]` |
| `required_human_review` | bool | 必填 | 本层应大量使用 `true` |
| `note` | string | 必填 | 说明配置用途和边界 |

示例草案：

```json
[
    {
        "rule_id": "I5B-CLUSTER-WARN-ADJACENT-CONTAMINATION",
        "subitem": "第五项B",
        "trigger_type": "trigger_terms",
        "trigger_terms": [
            "统一",
            "军功",
            "行政成效"
        ],
        "polarity_scope": [
            "positive",
            "negative"
        ],
        "evidence_strength_scope": [
            "candidate_strength_2",
            "candidate_strength_3",
            "candidate_strength_4"
        ],
        "warning_type": "adjacent_item_contamination",
        "warning_message": "检查是否把统一功业、军功或行政成效回填到第五项B。",
        "adjacent_item_risk": [
            "第一项",
            "第二项B2",
            "第五项C"
        ],
        "required_human_review": true,
        "note": "只提示相邻项污染风险，不产生证据簇强度或人物档位结论。"
    }
]
```

### B. 受保护边界配置

用途：

- 保存不可轻易改动的裁判边界。
- 防止脚本、批次或人工复核提示层把敏感规则变成自动定档。
- 仍然不直接生成正式分数或排名。

建议文件：

```text
data/configs/受保护规则配置/第五项B_证据簇裁判边界.json
```

建议字段：

| 字段 | 类型 | 要求 | 说明 |
| --- | --- | --- | --- |
| `boundary_id` | string | 必填，唯一 | 例如 `I5B-BOUNDARY-NO-AUTO-FINAL-BAND` |
| `subitem` | string | 必填，固定 `第五项B` | 防止跨子项误用 |
| `boundary_name` | string | 必填 | 人类可读边界名 |
| `applies_to` | string array | 必填 | 例如 `["evidence_cluster", "adjudication_batch", "auto_adjudication_export"]` |
| `rule_statement` | string | 必填 | 边界声明 |
| `forbidden_auto_action` | string array | 必填，非空 | 明确禁止自动行为 |
| `required_human_confirmation` | bool | 必填 | 应为 `true` |
| `examples` | object array | 可选 | 只作示例，不绑定人物最终结论 |
| `note` | string | 必填 | 说明保护原因 |

示例草案：

```json
[
    {
        "boundary_id": "I5B-BOUNDARY-NO-AUTO-FINAL-BAND",
        "subitem": "第五项B",
        "boundary_name": "证据簇不得直接生成正式档位",
        "applies_to": [
            "evidence_cluster",
            "adjudication_batch",
            "auto_adjudication_export"
        ],
        "rule_statement": "证据簇裁判配置只能输出复核提示、候选边界或待确认草案，不得自动生成某人物正式档位。",
        "forbidden_auto_action": [
            "write_final_band",
            "write_final_score",
            "write_ranking",
            "publish_leaderboard"
        ],
        "required_human_confirmation": true,
        "examples": [
            {
                "case_type": "strong_positive_with_strong_negative_core",
                "allowed_output": "提示强正底盘与强负核心并存，需要人工复核上探边界",
                "forbidden_output": "直接写入人物最终档位"
            }
        ],
        "note": "保护证据簇裁判配置不被误用为自动定档器。"
    }
]
```

## 7. validator 草案

未来建议新增独立 validator，例如：

```text
scripts/validate_i5b_cluster_adjudication_configs.py
```

也可以先整合进 `scripts/validate_review_configs.py`，但当受保护规则配置加入后，应拆出独立 validator，避免普通人工复核配置和高保护规则配置职责混杂。

基础校验：

1. JSON 顶层必须是 array。
2. 每项必须是 object。
3. 中文用户可编辑配置必须 UTF-8 直写，不允许 CJK Unicode escape。
4. `rule_id` / `boundary_id` 必须唯一。
5. `subitem` 必须等于 `第五项B`。
6. `trigger_terms`、`polarity_scope`、`evidence_strength_scope`、`adjacent_item_risk`、`applies_to`、`forbidden_auto_action` 等数组字段如果存在，必须是非空字符串数组。
7. `required_human_review` / `required_human_confirmation` 必须为 bool。
8. `forbidden_auto_action` 必须显式列出，且不能为空。
9. 不允许出现空 `warning_message`、空 `rule_statement`、空 `note`。

安全校验：

1. 禁止以下字段出现在任一配置中：
   - `formal_score`
   - `ranking`
   - `final_score`
   - `definitive_band`
   - `final_band`
   - `leaderboard`
   - `auto_publish`
   - `formal_result`

2. 禁止配置直接指定某人物最终档位或分数：
   - 若出现 `person` 字段，应先失败，除非未来有明确白名单。
   - 若出现 `score`、`rank`、`band` 等字段，应失败或要求更高保护层白名单。

3. 禁止 `required_human_review = false` 搭配高风险 `warning_type`：
   - `strong_negative_core`
   - `extreme_positive_probe`
   - `adjacent_item_contamination`
   - `source_review_required`

4. 禁止受保护边界配置缺少 `required_human_confirmation = true`。

5. 禁止普通人工复核提示配置写入 `forbidden_auto_action` 之外的自动动作。

引用校验可以后置：

- 第一阶段不强制引用真实 `cluster_id` 或 `evidence_id`。
- 后续若加入示例引用，应只允许引用示例 id 或测试 fixture，避免配置绑定当前人物结论。

## 8. 分阶段落地建议

### 第一刀：只加人工复核提示配置 skeleton + validator

范围：

- 新增空数组或极少量 skeleton：
  - `data/configs/人工复核配置/第五项B_证据簇裁判提示.json`
- 新增 validator：
  - 顶层 array
  - object item
  - `rule_id` 唯一
  - `subitem = 第五项B`
  - 禁止正式分、排名、最终档位字段

边界：

- 不填争议规则。
- 不改 `export_i5b_auto_adjudication.py`。
- 不改 evidence cards / clusters / adjudication batches。

### 第二刀：填入少量低风险提示规则

可填内容：

- 相邻项污染提示。
- 单证不足提示。
- 需要回源核验提示。
- 强证待人工复核提示。

仍然不做：

- 不写人物最终档位。
- 不写自动压制/自动升档。
- 不写正式分数或排名。

### 第三刀：考虑受保护边界配置

前置条件：

- 第二刀规则已被人工验证。
- validator 已能区分人工复核提示和受保护规则配置。
- PR 模板或审查流程明确要求人工确认。

可填内容：

- 证据簇不得直接生成正式档位。
- 强负核心必须回源核验。
- 相邻项剥离后不得机械回填。
- 正负证并存不得简单相加。

仍然不做：

- 不把人物临时定档映射成正式定档。
- 不把档位映射成正式分数。

### 第四刀：再考虑脚本读取配置

只有当前三刀稳定后，才允许脚本读取提示配置。

读取方式建议：

- 先在导出中展示“命中的人工复核提示”。
- 不改变 `auto_band_direction`。
- 不改变 `candidate_strength`。
- 不改变 `net_adjudication_draft`。
- 不写正式分数、排名或总榜。

## 9. 风险点

1. 配置被误用为自动裁判
   - 风险：提示配置被脚本当成决定规则。
   - 护栏：字段名用 `warning_*`、`required_human_review`，禁止 `decision`、`final_*`。

2. 人物结论被提前固化
   - 风险：把刘邦、雍正、朱元璋等当前批次草案写进配置。
   - 护栏：第一阶段禁止 `person` 字段，后续如需人物示例也只能作为说明性 examples。

3. 证据强度被机械相加
   - 风险：多条弱/中证被自动合并成强证，或强负自动抵消强正。
   - 护栏：配置只提示同源去重、正负并存和人工复核，不执行加总。

4. 相邻项污染
   - 风险：统一功业、军功、行政成效、财政整饬、政权安全、司法严酷回填第五项B。
   - 护栏：建立相邻项污染提示，并在受保护边界里禁止自动回填。

5. 配置与证据数据不同步
   - 风险：配置引用过时 trigger、cluster type 或旧字段。
   - 护栏：validator 校验字段名、受控值和禁止字段；后续可加入引用检查。

6. validator 过宽导致伪规则进入
   - 风险：空数组、空 note、泛泛 rule statement 或自动结果字段混入。
   - 护栏：非空字符串数组、bool 字段、唯一 id、禁止字段、保护层确认字段全部必填。

7. 自动草案与正式结果边界被混淆
   - 风险：`formal_band_draft`、内部试算分或导出标题被误读为正式结果。
   - 护栏：设计中明确本配置层不承载 formal score / ranking / definitive band。

## 10. 本 PR 不做事项

本 PR 只新增设计审计文档。

明确不做：

- 不新增正式裁判配置。
- 不新增 `data/configs/人工复核配置/第五项B_证据簇裁判提示.json`。
- 不新增 `data/configs/受保护规则配置/第五项B_证据簇裁判边界.json`。
- 不修改 `data/evidence_cards.jsonl`。
- 不修改 `data/evidence_clusters.jsonl`。
- 不修改 `data/adjudication_batches/*.jsonl`。
- 不修改 `data/search_logs.jsonl`。
- 不修改 `data/sources.jsonl`。
- 不修改 `data/configs/**/*.json`。
- 不修改 `scripts/`。
- 不修改 `tests/`。
- 不修改 `exports/`。
- 不修改 generated docs。
- 不修改 scoring、adjudication、formal score、ranking、leaderboard。

## 11. 后续执行清单

后续如果要真正落地，应新开 PR，至少满足：

1. 明确白名单只包含目标配置、validator 和测试。
2. 先新增空 skeleton 和 validator，不填敏感规则。
3. validator 接入 `validate_all.py` 前必须有测试覆盖。
4. 配置只输出提示，不改变当前证据数据和自动草案。
5. PR body 必须重复声明“不出分、不定档、不排名、不出总榜”。

## 12. 2026-06-21 implementation note

第一阶段已新增 `data/configs/人工复核配置/第五项B_证据簇裁判提示.json` skeleton，并接入 `scripts/validate_i5b_cluster_adjudication_configs.py` 与 `scripts/validate_all.py`。

当前 skeleton 为空数组，不填正式规则，不启用任何提示规则，不被业务脚本读取；本阶段仍不修改证据卡、证据簇、adjudication batch、导出、评分、定档、排名或总榜。

## 13. 2026-06-21 low-risk warning rules note

第二阶段已将 `第五项B_证据簇裁判提示.json` 从空数组推进到少量低风险 disabled 提示规则，覆盖相邻项污染、单证不足、回源核验、正负证并存四类人工复核提醒。

所有规则仍为 `enabled=false`，未接入业务脚本读取，未改变证据数据、自动草案、评分、定档或排名。
