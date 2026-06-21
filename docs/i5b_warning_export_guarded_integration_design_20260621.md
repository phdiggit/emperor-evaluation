# 第五项B display-only warning 导出受控接入设计审计

## 1. 当前可用组件

本次审计只设计未来接入方式，不修改真实导出脚本、不新增开关实现、不改变任何导出结果。

当前已经可用的组件有四层：

1. 配置 loader
   - `scripts/config_loaders.py` 已提供 `load_i5b_cluster_warning_rules()`、`get_i5b_cluster_warning_rules(...)`、`get_i5b_cluster_warning_rule(rule_id)`。
   - loader 只读取 `data/configs/人工复核配置/第五项B_证据簇裁判提示.json`，返回原始 rule dict list。
   - loader 不评估规则、不匹配 cluster、不渲染 markdown、不生成 decision object。

2. display-only matcher
   - `scripts/i5b_cluster_warning_display.py` 已提供 `match_display_only_cluster_warnings(cluster, linked_cards, rules)`。
   - matcher 不读取配置文件、不调用 loader、不写 data、不修改输入对象。
   - matcher 只读取 cluster/card 的只读文本字段，返回 display-only warning dict。
   - warning dict 的字段限制在 `warning_rule_id`、`warning_type`、`warning_message`、`matched_terms`、`matched_fields`、`matched_reason`、`required_human_review`、`display_only`、`no_score_effect` 等展示字段内。
   - matcher 不返回 `candidate_strength`、`auto_band_direction`、`net_adjudication_draft`、`formal_score`、`ranking` 等结果字段。

3. test-only renderer
   - `render_display_only_cluster_warning_section(warnings)` 只把 warning dict list 渲染为 `## 人工复核提示（display-only）` markdown section。
   - renderer 不读取文件、不写文件、不调用导出脚本。
   - renderer 会拒绝 `formal_score`、`ranking`、`final_score`、`definitive_band`、`final_band`、`leaderboard`、`auto_band_direction`、`candidate_strength`、`net_adjudication_draft`、`person`、`evidence_id`、`linked_evidence_ids` 等危险字段。

4. validator
   - `scripts/validate_i5b_cluster_adjudication_configs.py` 要求配置文件存在、顶层为 array、每项为 object。
   - validator 要求 `rule_id` 唯一、`subitem = "第五项B"`、`enabled` 为 bool、`required_human_review = true`。
   - validator 当前禁止 `enabled=true`，报错信息为“第一阶段不允许启用证据簇裁判提示规则；只能保留 skeleton。”
   - validator 禁止结果字段、人物绑定字段、证据绑定字段、证据簇绑定字段和自动草案字段。

审计搜索摘要：

- 强制 `rg` 搜索命中大量 `data/evidence_cards.jsonl`、`data/evidence_clusters.jsonl`、`data/adjudication_batches/*.jsonl` 和评分/定档草案文档，这是因为这些文件已有 `candidate_strength`、`net_adjudication_draft`、score/ranking 禁止说明和第五项B材料。
- `scripts/export_i5b_auto_adjudication.py` 是当前自动结算草案、规则敏感点清单、正式定档落地表、评分标尺草案和内部闭环收尾的生成入口。
- `scripts/i5b_cluster_warning_display.py` 目前未被真实导出脚本 import。
- `tests/test_i5b_auto_adjudication.py` 已覆盖导出脚本不直接输出正式分、排名或总榜。
- `tests/test_i5b_cluster_warning_display.py` 已覆盖 matcher/renderer 的 display-only 输出、禁用字段、输入不可变和 enabled=true 被忽略。
- `tests/test_config_loaders.py` 已覆盖 warning loader 只读 disabled rules、过滤和无缓存污染。

## 2. 未来接入点

`scripts/export_i5b_auto_adjudication.py` 当前生成五类输出：

1. `exports/markdown_views/第五项B三人自动结算草案.md`
2. `exports/markdown_views/第五项B自动结算规则敏感点清单.md`
3. `exports/markdown_views/第五项B三人正式定档落地表.md`
4. `exports/markdown_views/第五项B评分标尺与档位映射草案.md`
5. `docs/第五项B三人试点内部闭环收尾.md` 与对应导出视图

未来最适合接入的位置是自动结算草案中的“规则敏感点”附近：

- 推荐插入点：`render_person_section(report)` 内部，放在“触发的规则敏感点”之后、“自动结算结论”之前。
- 理由：这里本来就是人工复核自动草案和规则敏感点的位置，warning section 更容易被理解为复核提示。
- 需要避免：不要把 warning section 放进 `auto_band_direction`、`confidence` 或自动特征表。

次选位置是规则敏感点清单中的说明区：

- 可以新增“display-only warning 规则说明”区块，解释 warning type 和使用边界。
- 不建议写入具体人物、具体 cluster 命中结果，避免规则敏感点清单变成半自动裁判表。

不建议接入的位置：

- 正式定档落地表：靠近 `formal_band_draft`，容易被误读为正式定档依据。
- 评分映射草案：靠近分值区间，容易被误读为分数影响。
- 内部闭环收尾：已有内部试算区间和内部试算分，warning 放在这里会增加“影响试算”的误读风险。

## 3. 默认关闭方案

未来实现必须默认关闭，建议同时设计函数参数和 CLI 参数：

```python
def render_auto_adjudication(include_display_warnings: bool = False) -> str:
    ...

def export_auto_adjudication(include_display_warnings: bool = False) -> tuple[Path, Path, Path, Path]:
    ...
```

CLI 建议：

```text
python scripts/export_i5b_auto_adjudication.py --include-display-warnings
```

默认关闭要求：

1. 不传参数时导出结果内容级保持不变。
2. 若未来测试需要更严格，可对默认关闭输出做字节级 snapshot 比对。
3. 默认关闭时不调用 `load_i5b_cluster_warning_rules()`。
4. 默认关闭时不调用 `match_display_only_cluster_warnings(...)`。
5. 默认关闭时不调用 `render_display_only_cluster_warning_section(...)`。
6. 默认关闭时导出中不得出现 `人工复核提示（display-only）`。

不建议优先使用环境变量。环境变量不易从测试和 PR body 中看清楚，容易导致本地导出意外变化。若未来需要 CI 或批量导出控制，也应在函数/CLI 参数稳定后再考虑环境变量。

## 4. display-only 数据流

未来开启 `include_display_warnings=True` 后，数据流应为：

1. loader 读取 warning rules
   - 调用 `load_i5b_cluster_warning_rules()`。
   - 只把 rows 当作 display-only warning source。
   - 不把 rows 转成裁判规则、强度规则或档位规则。

2. 对每个 cluster 找 linked evidence cards
   - 复用 `evaluate_cluster(row, evidence_lookup)` 周边已有的 evidence lookup。
   - 只能通过 `linked_evidence_ids` 读取 card 文本，不得把 warning rule 绑定具体 id。

3. matcher 生成 display-only warning dict
   - 调用 `match_display_only_cluster_warnings(cluster, linked_cards, rules)`。
   - 当前 matcher 会忽略 `enabled=true`，只接受 `enabled=false` 且 `required_human_review=true` 的规则作为 display-only 提示来源。
   - 命中依据必须来自只读 cluster/card 文本或只读 scope 标签。

4. renderer 生成 warning markdown section
   - 调用 `render_display_only_cluster_warning_section(warnings)`。
   - 输出必须保留 `display_only`、`required_human_review`、`no_score_effect` 三个明确标识。

5. 只插入自动结算草案 display section
   - 建议每个人物的 `证据簇自动结算` 表后可以按 cluster 聚合展示。
   - 也可以先在测试 fixture 中只渲染一个合并 section，不更新真实 markdown views。

6. 不写回任何 data
   - 不写回 `data/evidence_cards.jsonl`。
   - 不写回 `data/evidence_clusters.jsonl`。
   - 不写入 `data/adjudication_batches/*.jsonl`。
   - 不写入 `exports/` 之外的事实源。

7. 不进入任何决策分支
   - warning 输出不得传入 `evaluate_person(...)` 的 `auto_band_direction` 决策逻辑。
   - warning 输出不得改变 `auto_band_direction`。
   - warning 输出不得改变 `candidate_strength`。
   - warning 输出不得改变 `net_adjudication_draft`。
   - warning 输出不得改变 `formal_band_draft`。
   - warning 输出不得改变 `internal_score_trial` 或内部试算字段。

## 5. 应该新增的测试

未来实现 PR 至少应新增或修改以下测试：

1. 默认关闭时，导出不包含 `人工复核提示（display-only）`。
2. 默认关闭时，既有 expected strings 或 snapshot 保持不变。
3. 开启开关后，只在自动结算草案出现 display-only warning section。
4. 开启开关后，warning section 不出现在评分标尺草案、正式定档落地表、排名/总榜相关输出。
5. 开启前后 `auto_band_direction` 不变。
6. 开启前后 `candidate_strength` 不变。
7. 开启前后 `net_adjudication_draft` 不变。
8. renderer 输出不包含 `final_score`、`ranking`、`leaderboard`。
9. no warning 命中时建议显示 `无额外提示`；如果未来选择“不展示 section”，必须在实现 PR 中固定一种行为并写入测试。
10. `enabled=true` 的外部异常 rule 不会被 matcher 执行。
11. validator 仍负责拒绝配置里的 `enabled=true`。
12. 默认关闭路径应断言不会调用 loader，可用 monkeypatch 将 loader 替换成抛错函数来证明。
13. 开启路径应使用测试 fixture rules，不得依赖真实导出结果更新。
14. 测试必须同时断言 `display_only=true`、`required_human_review=true`、`no_score_effect=true`。

建议测试文件分工：

- `tests/test_i5b_auto_adjudication.py`：覆盖默认关闭、开启后只插入自动结算草案、关键决策字段不变。
- `tests/test_i5b_cluster_warning_display.py`：继续覆盖 matcher/renderer 的纯函数行为和 forbidden 字段。
- `tests/test_config_loaders.py`：继续覆盖 loader 只读、过滤和无缓存污染。
- `tests/test_validate_i5b_cluster_adjudication_configs.py`：继续覆盖 forbidden result fields、绑定字段和 `enabled=true` 拦截。

## 6. 实现分刀建议

### 第一刀：默认关闭参数和内部纯调用路径

范围：

- 在 `export_i5b_auto_adjudication.py` 中新增 `include_display_warnings: bool = False` 参数。
- 只在函数内部建立可选调用路径。
- 只在测试 fixture 中开启。
- 不更新真实 markdown views。

护栏：

- 默认关闭时完全不调用 loader/matcher/renderer。
- 开启路径只生成临时 markdown section。
- 不改 `evaluate_cluster(...)`、`evaluate_person(...)` 的决策字段。

### 第二刀：fixture 中验证自动结算草案显示 warning section

范围：

- 用临时 evidence cards、clusters 和测试 rules 构造命中。
- 验证 section 只出现在自动结算草案。
- 验证 no warning 时显示 `无额外提示`。

护栏：

- 不提交真实 `exports/markdown_views/*.md` 变化。
- 不改变正式落地表、评分映射草案和内部闭环收尾。
- 不改变任何真实 data。

### 第三刀：人工确认后允许真实 markdown views 生成 display-only warning section

范围：

- 只有在人工确认后，才允许真实导出视图带 warning section。
- 仍只限自动结算草案或规则敏感点说明区。

护栏：

- 仍不改变 `auto_band_direction`。
- 仍不改变 `candidate_strength`。
- 仍不改变 `net_adjudication_draft`。
- 仍不改变评分、定档、排名、总榜。
- PR body 必须明确 warning 是人工复核提示，不是裁判结论。

## 7. 风险点

1. 默认开关误开导致导出视图突变
   - 护栏：默认关闭；默认关闭测试断言不出现 warning section；真实导出更新必须单独 PR。

2. warning section 被用户误读为裁判结论
   - 护栏：标题固定包含 `display-only`；每条 warning 显示 `no_score_effect=true`。

3. warning 命中被误读为人物负面定性
   - 护栏：matcher 不基于 person 触发；renderer 不输出 person 字段。

4. warning 插入位置靠近 `formal_band_draft` 造成误读
   - 护栏：默认不进入正式定档落地表；优先放在自动结算草案的规则敏感点附近。

5. matcher 使用 `candidate_strength` 作为匹配条件，被误以为修改了 `candidate_strength`
   - 护栏：只把 `candidate_strength` 转成 scope 标签；测试断言开启前后字段不变。

6. tests 只检查 warning 出现，没检查 no score effect
   - 护栏：测试必须同时检查 forbidden result fields 不出现，且 `no_score_effect=true`。

7. `enabled=false` 规则被读取的语义需要明确
   - 护栏：文档说明“读取 disabled rules 是 display-only 提示源，不是执行裁判”；validator 仍禁止 `enabled=true`。

8. warning section 反向影响规则敏感点
   - 护栏：`rule_sensitive_points` 仍由现有规则逻辑生成，warning section 只附加显示。

9. 导出脚本职责继续膨胀
   - 护栏：第一刀只接入纯函数调用；若逻辑增长，应后续拆出 helper，但不得在业务 PR 中顺手大拆脚本。

## 8. 本 PR 不做事项

本 PR 只做设计审计。

明确不做：

- 不改 `scripts/export_i5b_auto_adjudication.py`。
- 不改 `scripts/i5b_cluster_warning_display.py`。
- 不改 `scripts/config_loaders.py`。
- 不改 tests。
- 不改 data。
- 不改 configs。
- 不改 exports。
- 不新增 CLI 参数。
- 不新增真实接入。
- 不新增 loader。
- 不新增 matcher。
- 不新增 renderer。
- 不新增开关实现。
- 不改变任何导出结果。
- 不改变证据、裁判批次、评分、定档、排名、总榜。

## 9. Implementation note（2026-06-21）

- 已在 `scripts/export_i5b_auto_adjudication.py` 新增 `--include-display-warnings`。
- CLI 默认关闭 display-only warning 导出；默认不带参数时保持原导出行为，不生成 `人工复核提示（display-only）`。
- 开启后只在自动结算草案生成 display-only warning section，不进入正式定档落地表、评分映射草案或内部闭环收尾。
- 本 PR 不提交真实 `exports/` 变化。
- 真实 `exports/` 是否携带 warning section，仍需另开 PR 人工确认。

