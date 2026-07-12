# Hardcoded Content / Configuration Inventory (2026-06-20)

## 1. Executive Summary

本次审计聚焦 `scripts/export_md.py` 模块化后仍留在脚本内的硬编码内容、配置形态数据、模板文案与规则边界。结论如下：

- 当前导出/校验链整体可用，现阶段最大风险不是“代码无法维护”，而是“模板内容、结构化配置、规则决策、结果保护语句”混放在脚本里，后续若直接外置，容易误把受保护规则改成普通配置。
- 低风险、最值得优先外置的对象主要是：
  - 输出路径常量；
  - 表头/列集合；
  - 候选池行数据；
  - 非评分类导出文案模板。
- 现阶段最不适合直接外置的是 `scripts/export_i5b_auto_adjudication.py` 中与档位、试算区间、规则敏感点、自动结算启用边界直接相连的内容；这些更接近“受保护规则决策”，不应被当作普通 YAML/JSON 配置开放修改。
- `scripts/validate_all.py` 与 `scripts/validate_canonical_data_integrity.py` 的核心判断逻辑应继续留在代码中；其中少量路径常量可以未来参数化，但语义守卫与特殊锚点约束不应轻率降级为普通配置。
- `tests/*.py` 中大多数硬编码文本/样例行属于测试夹具，原则上分类为 `test_fixture_ok`，不应因为“看起来写死了”就被误列为治理对象。

总体建议：

- 第一阶段只外置“路径 + 视图列 + 非结果型模板文案 + 候选池结构化行数据”。
- 第二阶段再讨论“规则说明文档模板化”。
- 评分映射、正式结果保护语句、自动结算规则敏感点继续保持人工确认保护，不纳入可自由调整的普通配置层。

## 2. Category Definitions

| category | 含义 | 典型例子 |
| --- | --- | --- |
| `logic_ok` | 适合继续留在代码中的执行逻辑、数据流、排序、过滤、校验、渲染控制 | SQL 查询、JSONL 解析、导出步骤调度 |
| `path_config_candidate` | 未来可外置的路径、文件名、导出目标定位 | `exports/markdown_views/...`、`docs/...` |
| `view_config_candidate` | 未来可外置的视图列、表头、导出视图包含字段 | 表头数组、列顺序、目标视图字段集 |
| `structured_data_candidate` | 本质上更像结构化业务数据，而不是代码逻辑 | 候选池行、人物目标清单、导出 target 映射 |
| `template_content_candidate` | 本质上更像 Markdown 模板/说明文案的内容 | 长段落导出文案、固定说明标题、说明性列表 |
| `rule_decision_candidate` | 已触及工作流规则、规则启用边界、人工复核边界，不应作为普通用户配置开放修改 | 自动结算触发边界、人工复核前置条件、特殊锚点守卫 |
| `protected_scoring_or_result_candidate` | 已直接触及正式分数、档位映射、总标尺或结果保护语义，必须继续受人工确认保护 | 试算分值映射、正式出分禁止语句、总榜抑制语句 |
| `test_fixture_ok` | 测试样例、断言文本、临时路径、模拟行数据，继续留在测试里即可 | pytest 样例 JSON 行、tmp 路径 |
| `unclear_needs_human_decision` | 介于规则、模板、结构化数据、可配置逻辑之间，后续若要外置需先人工定边界 | 自动结算关键词表、规则敏感点与启发式的分界 |

## 3. File-by-File Inventory

| file | notable hardcoded items | primary classification | inventory note |
| --- | --- | --- | --- |
| `scripts/export_md.py` | `DB_PATH`、多组导出路径、通用表头、`I5B_TRIAL_TARGETS`、`I5B_SUBITEM` | `path_config_candidate` / `view_config_candidate` / `structured_data_candidate` | 适合作为后续“导出入口配置层”的第一批整理对象；主导出逻辑、调度顺序仍应保持 `logic_ok`。 |
| `scripts/export_md_scaffold.py` | `ExportStep`、表格转义、通用导出驱动、唯一值汇总 | `logic_ok` | 这里基本是稳定脚手架；没有明显值得外置的长内容。 |
| `scripts/export_i5b_views.py` | I5B review-path 导出路径、表头、固定节标题、说明文案、`not_for_scoring` 相关输出语句 | `path_config_candidate` / `view_config_candidate` / `template_content_candidate` / 少量 `rule_decision_candidate` | 适合将“路径、列、非结果型说明文案”分离；但 workflow-stage 与“不用于正式出分”的边界语句不要无保护地下沉成普通配置。 |
| `scripts/export_i5b_net_evidence.py` | 净证据导出路径、目标人物/文件映射、卡片/证据簇表头、净证据说明语句 | `path_config_candidate` / `view_config_candidate` / `structured_data_candidate` / `template_content_candidate` | `I5B_NET_EVIDENCE_TARGETS` 未来可做结构化配置；“不代表最终档位/分数/排名”的语句需保留治理保护意识。 |
| `scripts/export_i5b_expanded_batch1.py` | expanded batch1 输出路径、表头、`EXPANDED_BATCH1_PERSONS`、批次说明文案、阶段性工作流语句 | `path_config_candidate` / `view_config_candidate` / `structured_data_candidate` / `template_content_candidate` / 少量 `rule_decision_candidate` | 这里很适合作为后续“结构化人选清单 + 模板文案”分层试点。 |
| `scripts/export_project_doc_views.py` | 全局总标尺简报路径、候选池路径、`I5B_EXPANDED_CANDIDATE_POOL_ROWS`、长篇简报正文、候选池文案 | `path_config_candidate` / `structured_data_candidate` / `template_content_candidate` / `rule_decision_candidate` / `protected_scoring_or_result_candidate` | 这是最明显的“文案/数据/规则混放”点。候选池行最适合先外置；总标尺简报正文则必须先拆出受保护段与普通说明段。 |
| `scripts/export_i5b_auto_adjudication.py` | `TRIAL_SCORE_MAP`、关键词集合、`RULE_SENSITIVE_POINTS`、`DIMENSION_RULES`、正式定档/试算导出路径、正式结果保护语句 | `protected_scoring_or_result_candidate` / `rule_decision_candidate` / `unclear_needs_human_decision` / 少量 `path_config_candidate` | 这是当前最不宜直接配置化的脚本。它混合了启发式逻辑、规则决策、试算分值与正式结果保护边界。未来任何外置都应先拆出保护层。 |
| `scripts/validate_all.py` | `VALIDATION_STEPS` 及其脚本路径 | `logic_ok` / 少量 `path_config_candidate` | 现状足够轻量。若未来出现多套验证 profile，再考虑外置；当前没必要。 |
| `scripts/validate_canonical_data_integrity.py` | canonical 文件路径、批次路径、特殊锚点 ID、source traceability 约束 | `logic_ok` / `path_config_candidate` / `rule_decision_candidate` | 路径可未来参数化，但 Chu Wang Ying 事件锚点与申屠刚机制锚点守卫属于规则保护，不宜当普通配置。 |
| `tests/*.py` | `tmp_path`、mock 路径、样例 JSONL 行、断言文案、受保护结果断言 | 绝大多数为 `test_fixture_ok` | 测试里的硬编码主要是保护当前行为，不属于生产配置债务。个别断言文本同时充当治理护栏，但仍应归类为测试夹具。 |

## 4. High-Value Externalization Candidates

优先级最高、收益最大、风险最低的候选如下：

1. `scripts/export_project_doc_views.py` 中的 `I5B_EXPANDED_CANDIDATE_POOL_ROWS`
   - 这是典型的结构化行数据。
   - 未来更适合迁到 `data/view_configs/*.jsonl` 或专门的候选池配置文件。
   - 外置后仍可保持当前渲染逻辑不变。

2. `scripts/export_md.py`、`scripts/export_i5b_net_evidence.py`、`scripts/export_i5b_expanded_batch1.py` 中的路径与表头
   - 这类内容稳定、可枚举、低语义风险。
   - 适合整合进 `config/export_profiles.yml` 或 `config/project_doc_views.yml`。

3. `scripts/export_i5b_views.py`、`scripts/export_i5b_expanded_batch1.py` 中的非结果型固定说明文案
   - 例如视图用途说明、阶段性导出提醒、字段含义提示。
   - 更适合转成模板内容，而不是继续混在 Python 函数体里。

4. `scripts/export_i5b_net_evidence.py` 中的人物-导出目标映射
   - 更像结构化视图配置，而不是执行逻辑。
   - 可作为后续第二批外置对象。

## 5. Items That Should Stay in Code

以下内容建议继续保留在代码中：

- `scripts/export_md_scaffold.py` 的导出脚手架、表格转义、步骤编排；
- 各导出脚本中的数据库读取、JSONL 解析、行构造、排序、过滤、拼表逻辑；
- `scripts/validate_all.py` 的顺序执行控制；
- `scripts/validate_canonical_data_integrity.py` 的 parse/去重/跨文件冲突检测逻辑；
- `scripts/export_i5b_auto_adjudication.py` 中纯执行性逻辑：
  - `read_jsonl`
  - `read_json`
  - `markdown_table`
  - `contains_any`
  - `infer_dimension`
  - `has_direct_safety_hard_evidence`
  - 各类 report 组装与导出控制逻辑

原因：

- 这些部分的本质是行为，而不是内容；
- 一旦外置，容易把“可执行判断”错误降级成“静态配置拼接”；
- 对测试和回归保护也不利。

## 6. Items That Should Become User-Adjustable Config

适合未来变成“可调整但不触及正式结果”的配置对象：

- 导出目标路径与双写路径：
  - `docs/...`
  - `exports/markdown_views/...`
- 各类 Markdown 表头与列顺序；
- 候选池结构化行；
- 非正式结果型的视图目标集合，例如 I5B 三人试点 target 集；
- 净证据视图的目标文件/对象映射；
- 扩展批次的人物列表、批次行清单等纯枚举数据。

前提条件：

- 配置层必须与“规则层”和“结果保护层”分开；
- 不能把“可配置”误解为“可随意改变结论边界”。

## 7. Items That Must Stay Protected Behind Human Confirmation

以下内容虽然形式上像“写死的数据/文案”，但实质上已经触及规则、分值或正式结果边界，后续即便外置，也必须放在受保护层并配合人工确认：

1. `scripts/export_i5b_auto_adjudication.py` 中的 `TRIAL_SCORE_MAP`
   - 这已不是普通显示配置，而是试算区间与试算分的规则表达。

2. `scripts/export_i5b_auto_adjudication.py` 中的 `RULE_SENSITIVE_POINTS`
   - 它们是规则级复核的核心问题清单，不能被当作普通文案表自由编辑。

3. `scripts/export_i5b_auto_adjudication.py` 中与正式结果抑制相关的语句
   - 如“不正式出分”“不排名”“不生成总榜”“不得直接推分”。
   - 这些语句承载的是治理边界，不是普通模板装饰。

4. `scripts/export_project_doc_views.py` 中全局总标尺简报里关于“方案 C 已采纳/已规则级确认”的段落
   - 这些段落已经包含规则决策状态，不应作为普通模板自由改写。

5. `scripts/validate_canonical_data_integrity.py` 中的特殊锚点守卫
   - `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618`
   - 申屠刚机制锚点约束
   - 它们是防语义退化的明确治理护栏。

## 8. Proposed Low-Risk First Externalization Slice

推荐的第一刀：

1. 先不碰 `scripts/export_i5b_auto_adjudication.py`；
2. 从 `scripts/export_project_doc_views.py` 抽出：
   - `I5B_EXPANDED_CANDIDATE_POOL_ROWS`
   - 候选池导出路径
3. 同时可顺带抽出非评分类导出脚本中的表头数组与输出路径：
   - `scripts/export_md.py`
   - `scripts/export_i5b_net_evidence.py`
   - `scripts/export_i5b_expanded_batch1.py`

原因：

- 这一刀基本不需要改业务渲染语义；
- 主要影响“数据/模板承载位置”，不影响规则判定；
- review 成本低，也更容易补 focused tests。

不建议的第一刀：

- 直接抽 `TRIAL_SCORE_MAP`；
- 直接抽 `RULE_SENSITIVE_POINTS`；
- 直接模板化全局总标尺决策简报的全部正文。

## 9. Proposed Future Config File Layout

以下布局值得后续 issue 评估，但本次不实现：

```text
config/export_profiles.yml
config/project_doc_views.yml
config/rule_decisions/global_scale.yml
config/rule_decisions/scoring_mode.yml
templates/project_doc_views/*.md.j2
data/view_configs/*.jsonl
```

建议分工：

- `config/export_profiles.yml`
  - 放导出目标路径、双写路径、视图开关、视图分组。

- `config/project_doc_views.yml`
  - 放非评分类项目文档视图的表头、段落顺序、候选池数据源定位。

- `data/view_configs/*.jsonl`
  - 放候选池行、target 行、纯枚举视图数据。

- `templates/project_doc_views/*.md.j2`
  - 放低风险 Markdown 模板正文。

- `config/rule_decisions/global_scale.yml`
  - 仅在未来真的建立“受保护规则配置层”时再考虑；不能和普通模板/路径配置混放。

- `config/rule_decisions/scoring_mode.yml`
  - 同上，只有在确认存在严格审核流程时才值得建立。

## 10. Boundary Cases Needing Human Decision

以下对象最容易在未来治理中被误分类，建议单独开 issue 先定边界：

1. `scripts/export_i5b_auto_adjudication.py` 的关键词集合与 `DIMENSION_RULES`
   - 一部分像启发式逻辑；
   - 一部分又明显影响规则输出；
   - 归为普通结构化数据还是受保护规则配置，需要人来拍板。

2. `scripts/export_project_doc_views.py` 中“全局总标尺简报”的长文案
   - 其中有些只是背景说明；
   - 有些已经是规则确认状态陈述；
   - 需要拆分出普通模板段与受保护规则段。

3. `scripts/export_i5b_views.py`、`scripts/export_i5b_expanded_batch1.py` 中的阶段性 workflow 文案
   - 有些只是视图说明；
   - 有些已经在表达“不定档/不出分/不排名”的治理边界。

## 11. Explicit Non-Changes Statement

本次 PR 仅做库存审计文档，不做以下操作：

- 不外置模板；
- 不移动任何脚本常量；
- 不创建新的 config/template/data 文件；
- 不修改 `scripts/*.py`；
- 不修改 `tests/*.py`；
- 不修改 `data/*.jsonl` 或 `data/*_batches/*.jsonl`；
- 不修改 `exports/` 下既有导出；
- 不修改评分、定档、排名、总榜或任何正式结果结论。
