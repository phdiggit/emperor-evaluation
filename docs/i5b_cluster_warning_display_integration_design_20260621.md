# 第五项B证据簇提示规则展示集成设计审计

## 1. 当前导出链路

本次审计只查看现有链路，不改代码、不接入脚本读取、不改变任何导出结果。

现有 `scripts/export_i5b_auto_adjudication.py` 读取 `data/evidence_cards.jsonl`、`data/evidence_clusters.jsonl` 和第五项B三人试点配置，生成五类输出：

1. 自动结算草案：`exports/markdown_views/第五项B三人自动结算草案.md`
   - 逐人输出 `auto_band_direction`、`confidence`、正负证据簇、自动特征和触发的规则敏感点。
   - 当前最适合未来放置 display-only warning section，因为它本来就是草案和人工复核入口。

2. 规则敏感点清单：`exports/markdown_views/第五项B自动结算规则敏感点清单.md`
   - 列出抽象规则问题、默认处理方式和为什么重要。
   - 适合未来展示 warning rule 的说明性索引，但不应把 warning 命中写成规则结论。

3. 正式定档落地表：`exports/markdown_views/第五项B三人正式定档落地表.md`
   - 输出 `formal_band_draft`、`not_scored_flag`、`ranking_suppressed_flag` 等正式落地准备字段。
   - 这里靠近正式定档语义，未来若展示 warning，只能作为附录式人工复核提示，不得参与 `formal_band_draft` 或 score stage prerequisites。

4. 评分标尺草案：`exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B评分标尺与档位映射草案.md`
   - 说明档位到分值映射草案，但仍声明不生成人物正式分数、不排名、不出总榜。
   - 不适合展示 cluster warning 命中，避免 warning 被误读为分值依据。

5. 内部闭环收尾：`exports/markdown_views/第五项B/人工审核/自动裁判链/试点闭环/第五项B三人试点内部闭环收尾.md`
   - 输出内部试算区间、内部试算分和扩展试点状态。
   - 不适合承载 warning 命中详情；最多只能在未来概述“仍需人工复核的 display-only warning 已另见自动结算草案”。

审计搜索摘要：

- `rg` 命中显示 `export_i5b_auto_adjudication.py` 是当前 `auto_band_direction`、`candidate_strength`、规则敏感点、正式落地表和评分映射草案的主要生成入口。
- `tests/test_i5b_auto_adjudication.py` 已断言自动导出生成规则视图、正式落地表和评分映射草案，同时不输出 `| score |`、`| ranking |`、`| rank |` 等正式结果表头。
- `tests/test_validate_i5b_cluster_adjudication_configs.py` 已锁定 warning config 中禁止 `final_score`、`ranking`、`definitive_band`，也禁止 `person`、`cluster_id`、`evidence_id`、`auto_band_direction`、`candidate_strength` 等绑定或决策字段。
- `data/adjudication_batches/*.jsonl` 已存在 `rule_pressure_summary` 与 `net_adjudication_draft`，但它们是批次草案层，不应被 warning config 写回或覆盖。

## 2. 只展示，不决策的边界

未来即使业务脚本读取 `data/configs/人工复核配置/第五项B_证据簇裁判提示.json`，也只能产生展示对象，允许字段限于：

- `warning_rule_id`
- `warning_type`
- `warning_message`
- `matched_reason`
- `matched_terms`
- `matched_fields`
- `required_human_review`
- `display_only`
- `no_score_effect`

未来集成不得写入或改变：

- `auto_band_direction`
- `candidate_strength`
- `net_adjudication_draft`
- `formal_band_draft`
- `internal_score_trial`
- `formal_score`
- `ranking`
- `leaderboard`

关键原则：

1. warning 命中不等于裁判结论。
2. warning 命中不等于强度调整。
3. warning 命中不等于人物负面定性。
4. warning 命中只能提醒人工 reviewer 检查某个风险点。
5. warning section 的所有输出必须显式带 `display_only: true` 和 `no_score_effect: true`。

## 3. 匹配逻辑草案

未来如果接入展示层，匹配逻辑应保守、可解释、只读。

允许从 evidence cluster 派生匹配材料：

- `trigger_terms`：若未来 cluster 层存在该字段，只作为文本命中来源。
- `five_axis_assessment`：只读取其中的 residual / directness / structurality 等描述性值，不改写评估。
- `cross_item_split`：用于检测相邻项污染提示，例如统一功业、军功、行政成效、财政整饬、政权安全、司法严酷等。
- `polarity`：只能用于判断 `polarity_scope` 是否适用。
- `candidate_strength`：只能转换为匹配标签，例如 `candidate_strength_3`，不能被 warning 改写。
- `linked_evidence_ids`：只能用于读取 linked evidence cards 的文本字段，不能让 warning rule 绑定具体 id。

允许从 linked evidence cards 派生匹配材料：

- `trigger_terms`
- `trigger_family`
- `scoring_effect`
- `cross_item_split`
- `evidence_role`
- `cluster_role`
- `upper_bound_flag`
- `mitigation_flag`
- `strength` 转换出的只读标签，例如 `strength_3`

禁止匹配方式：

- 不允许基于 `person_name` 直接触发。
- 不允许基于 `cluster_id` 直接触发。
- 不允许基于 `evidence_id` 直接触发。
- 不允许 warning rule 反向改写 cluster 字段。
- 不允许 warning rule 反向改写 evidence card 字段。
- 不允许 warning rule 修改 `rule_sensitive_points` 的既有规则结论。

建议匹配步骤：

1. 对每个 cluster 构造只读文本包：cluster 的 `cross_item_split`、`five_axis_assessment` 值、`polarity`、`candidate_strength` 标签、linked cards 的 `trigger_terms` 与 `scoring_effect` 等。
2. 跳过 `enabled=false` 规则，除非后续 PR 明确把“展示 disabled 规则”改为“读取但仍 display-only”的新阶段。
3. 对可展示规则做 `trigger_terms` 交集匹配，同时检查 `polarity_scope` 与 `evidence_strength_scope`。
4. 生成 display-only warning dict。
5. 不写回任何 `data/*.jsonl`，只传给 markdown renderer。

## 4. 输出位置草案

推荐未来只在以下位置增加“人工复核提示”栏目：

1. 证据簇结算草案
   - 位于每个 cluster 行之后或同一人物的 `证据簇自动结算` 表后。
   - 标题建议为 `人工复核提示（display-only）`。

2. 规则敏感点清单
   - 增加一个独立区块说明 warning rule 类型和展示边界。
   - 不写具体人物、不写具体 cluster 命中，避免清单变成半自动裁判表。

3. 自动结算草案中的 warning section
   - 放在 `触发的规则敏感点` 与 `自动结算结论` 之间更安全。
   - 这样 reviewer 先看既有规则敏感点，再看额外 warning，最后才看到 `auto_band_direction`。

不得出现的位置：

- 正式分数。
- 排名。
- 总榜。
- 任何可被误读为最终定档的字段。
- `formal_band_draft` 所在表头附近，除非明确标注为附录和 no-score-effect。

## 5. 数据结构草案

未来脚本生成的展示对象应为临时 dict，不写回 data。

建议结构：

```python
{
    "cluster_id": "ADJ-I5B-...",
    "warning_rule_id": "I5B-CLUSTER-WARN-...",
    "warning_type": "adjacent_item_contamination",
    "warning_message": "提示人工检查是否把统一功业、军功、开国叙事、行政成效或财政整饬回填到第五项B。",
    "matched_terms": ["军功", "行政成效"],
    "matched_fields": ["cluster.cross_item_split", "card.trigger_terms"],
    "matched_reason": "trigger_terms matched read-only cluster/card text; polarity_scope and evidence_strength_scope matched.",
    "required_human_review": True,
    "display_only": True,
    "no_score_effect": True,
}
```

硬边界：

- 不写回 `data/evidence_clusters.jsonl`。
- 不写回 `data/evidence_cards.jsonl`。
- 不写入 `data/adjudication_batches/*.jsonl`。
- 不写入 `search_logs`、`sources` 或任何 batch 文件。
- 不把该对象传入 `evaluate_person()` 的决策分支。
- 只作为导出显示层临时结构。

## 6. 测试方案

未来真正接入时，应先新增测试再改导出脚本。

测试建议：

1. 当前阶段：`enabled=false` 的规则不应被业务脚本读取，除非后续 PR 明确改变阶段定义。
2. 若后续允许读取规则，也只能生成 display-only warning section，不改变 `auto_band_direction`。
3. warning 命中前后，`candidate_strength` 不变。
4. warning 命中前后，`net_adjudication_draft` 不变。
5. warning section 不包含 `final_score`、`ranking`、`leaderboard`。
6. validator 继续拦截 forbidden result fields。
7. validator 继续拦截 `person`、`cluster_id`、`evidence_id` 绑定。
8. 没有规则命中时，导出保持原样或只显示 `无额外提示`。
9. 测试不只检查 warning 存在，还必须检查 `display_only: true`、`no_score_effect: true` 和 no-score/no-rank 边界。
10. 对相邻项污染提示，应测试 warning 不会把相邻项词反向加入第五项B结论。

建议测试文件：

- `tests/test_i5b_cluster_warning_display.py`：只测 display-only 临时对象与 renderer。
- `tests/test_i5b_auto_adjudication.py`：只加最小回归断言，确保既有 `auto_band_direction`、`formal_band_draft`、score/ranking suppress 语义不变。
- `tests/test_validate_i5b_cluster_adjudication_configs.py`：继续覆盖 forbidden 字段和绑定字段。

## 7. 分阶段落地建议

### 第一刀：新增 loader，只读 disabled warning rules，但不接入导出

范围：

- 新增 loader 函数，例如 `load_i5b_cluster_warning_rules()`。
- 只返回 config rows，不在业务脚本里调用。
- 测试缺文件、空数组、四条 disabled 规则读取。

护栏：

- loader 不得过滤成“可执行规则”。
- loader 不得返回任何 decision object。
- PR body 必须写明“不接入导出”。

### 第二刀：导出脚本新增 display-only warning section，默认不启用或只在测试 fixture 中验证

范围：

- 新增纯函数，例如 `match_display_only_cluster_warnings(cluster, linked_cards, rules)`。
- 输出临时 warning dict。
- 测试 fixture 中验证 warning section 的文本和 no-score-effect。

护栏：

- 不改变 `evaluate_cluster()` 的返回决策字段。
- 不改变 `evaluate_person()` 的 `auto_band_direction` 分支。
- 不改变正式落地表、评分映射草案、内部闭环字段。

### 第三刀：人工确认后再允许展示到正式 markdown views

范围：

- 只在自动结算草案和规则敏感点清单中展示。
- 如果要进入正式落地表，只能作为附录，且必须继续标注 display-only。

护栏：

- 仍不改变自动草案字段。
- 仍不改变评分、定档、排名、总榜。
- 高风险 warning rule 或 enabled 语义变化必须另开 PR 人工确认。

## 8. 风险与护栏

1. warning 被误用为裁判结论
   - 护栏：字段名统一使用 `warning_*`，输出必须带 `display_only`。

2. warning 被解释为强度调整
   - 护栏：测试必须断言 `candidate_strength` 前后不变。

3. 规则命中被误读为人物负面定性
   - 护栏：禁止 person 触发，文案写“提示人工检查”，不写“该人物存在某结论”。

4. 相邻项污染提示本身反而造成污染
   - 护栏：相邻项 warning 只能提示“检查是否回填”，不能把相邻项词写入第五项B结论。

5. 输出位置靠近正式定档表导致误读
   - 护栏：优先放在自动草案和规则敏感点清单；正式落地表默认不展示。

6. 测试只检查存在 warning 而不检查无 score effect
   - 护栏：每个 display warning 测试必须同时断言 no score / no ranking / no field mutation。

7. enabled 语义漂移
   - 护栏：当前 `enabled=false` 不应被业务脚本读取；若未来要读取 disabled rules 作展示，需要先重命名阶段或新增明确字段，避免“disabled 但被读取”的语义混乱。

8. warning 反向驱动规则敏感点
   - 护栏：`rule_sensitive_points` 继续由现有规则逻辑生成，warning 只附加展示。

## 9. 本 PR 不做事项

本 PR 只做 display-only 集成设计审计。

明确不做：

- 不改 `data/*.jsonl`。
- 不改 evidence cards。
- 不改 evidence clusters。
- 不改 adjudication batches。
- 不改 `search_logs`。
- 不改 `sources`。
- 不改 `data/configs/**/*.json`。
- 不改 `scripts/`。
- 不改 `tests/`。
- 不改 `exports/`。
- 不新增 loader。
- 不让业务脚本读取 warning config。
- 不改变任何导出结果。
- 不改变评分、定档、排名、总榜。
