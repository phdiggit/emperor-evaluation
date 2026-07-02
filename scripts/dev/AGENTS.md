# AGENTS.md

本文件只约束 `scripts/dev/**` 下的开发辅助工具。I5B 数据链的完整执行步骤见 [`../../docs/数据结构与生成库/I5B数据链运行流程.md`](../../docs/数据结构与生成库/I5B数据链运行流程.md)。

## 职责边界

- `scripts/dev/**` 只放开发、诊断、召回、导入、校验、重算辅助和本地报告工具。
- 开发工具不得替代正式评分规则、证据裁量、档位结论或人工回源判断。
- 涉及中文 JSON/Markdown 读写时使用 UTF-8、`ensure_ascii=False` 和稳定排序；不要用 `pwsh` / PowerShell inline 传递长中文正文。

## 摘录召回工具

- `source_excerpt_pool.py` 是 review-first 召回工具入口，真实实现拆在 `source_excerpt_pool_lib/`；只生成对象、查询计划和摘录候选。
- 摘录输出默认写 `.tmp/**`；不得直接覆盖正式 `data/**`。
- 摘录池的“无命中”不是“无史料”；网络错误、目标页缺失、别字和过滤过严都应进入缺口复核。
- Wikisource 限流、超时和 5xx 应通过工具内置节流与重试处理；不要通过减少检索包对象覆盖来躲避限流。
- 若显式使用 query cap，工具必须报告 skipped plans；调用方不得静默跳过检索包对象。

## 对象导入工具

- `object_pool_importer.py` 只导入已经回源并人工判断过的对象 payload。
- `--template-from-profile` 只生成待填写模板；模板中的史源、规则、方向和 note 必须人工补全。
- 导入前先 dry-run；正式提交前必须校验不存在无史源 `raw_objs`。
- payload 中每个对象至少有一条史料链接，并保持原始对象粒度。
- `raw_objs.note` 不写规则、方向、评分或档位；`obj_srcs.note` 写史料事实对规则维度的具体帮助。

## 证据簇和重算工具

- `evidence_cluster_workbench.py`、`i5b_factor_recalculator.py` 只能基于已回源对象链和已确认 factor profile 写入 `evd_clusters` / `emp_item_results`。
- `i5b_calc_breakdown.py` 是只读明细表拆解工具，用于按皇帝/规则调出证据簇计算过程和定分计算过程，不写数据库。
- `i5b_rule_object_coverage_audit.py` 是只读 rule 对象覆盖审计工具。普通 rule 用它从 `emp_objs` 全量检查是否漏挂目标 `rule_code`；`team_building` 用它检查自动团队候选是否已进入计算明细。
- `i5b_factor_consistency_audit.py` 是只读因子一致性审计工具，用于检查高严重度等因子是否和材料注释发生明显冲突；`i5b_factor_recalculator.py --write-clusters/--write-results` 写库前会自动执行 hard-error 审计。
- `i5b_factor_table_sync.py` 是只读规则文档抽取、计分细则表同步和 `calc_detail.factor_refs` 对表审计工具；默认只输出 JSON/Markdown、生成可审阅 upsert SQL 或审计报告，不直接写库或替代人工规则裁量。
- `i5b_health_check.py` 是 I5B 重算后的一键只读健康检查入口，汇总因子一致性、规则承载预览、事实关系 gap 和评分简表；它不重算、不写库。
- `i5b_fact_relation_candidate_sync.py` 是事实关系候选同步工具，从 `rule_evidence_units` 与 `fact_relation_predicate_options` 生成 `fact_relations` 候选；默认只处理 `anti_nepotism` / `tolerate_talent` 的具体 person，不自动 accepted，不改变正式算分输入。
- `i5b_fact_relation_gap_summary.py` 是事实关系 gap 汇总工具，从 `rule_evidence_units`、predicate catalog 和 `fact_relations` 检查非人物承载、方向不匹配、缺失关系等缺口；它只读，不写库。
- `i5b_rule_evidence_unit_candidate_builder.py` 是只读规则证据单元候选生成器，从当前 `evd_cluster_calc_details` 和对象链还原“谁正在计分”，输出待人工确认的 shadow payload；它默认不写库，不自动合并因果链。
- `i5b_rule_evidence_unit_preview.py` 是只读规则承载对象影子层预览工具，用于检查某个 I5B rule 的计分承载对象、上下文成员和同一因果链重复入分风险；它不写库、不替代正式证据簇计算。
- `i5b_rule_evidence_unit_issue_summary.py` 是规则承载预览问题汇总工具，从当前 calc_detail 重建候选并汇总 preview block/warning，用于新皇帝或重算后的 gap 阀门；它只读，不写库。
- `i5b_rule_evidence_unit_db_sync.py` 是规则证据单元影子表同步工具，只把候选 payload 幂等写入 `rule_evidence_units` / `rule_evidence_unit_members` 供人工审计；它不得合成未经确认的 `fact_relations`，也不得改变正式算分输入。
- `i5b_talent_discovery_audit.py` 是只读覆盖审计工具，用于对比检索包 `POS-TALENT-RECOGNITION` 与最新 `talent_discovery` 入簇对象；补链或重算前必须先看缺口，写回受影响证据簇后必须用 `--fail-on-gap` 复跑。已回源但不支撑进入 `talent_discovery` 的对象，用 `--accepted-missing 皇帝:对象` 显式标注，不得静默忽略。
- 计算明细写入 `evd_cluster_calc_details` 与 `emp_item_result_calc_details`；JSONL 日志不再参与当前计算、审查或重放流程。
- 修改规则内部乘数后，先同步 `eval_rule_factor_options`，再从明细表 `--from-details` 重放并重算；`--from-details` 默认从细则表读因子值，`--factor-source docs` 只用于本地 fixture 或迁移排障。新增史料对象时先补对象链和受影响证据簇，再用明细表重放检查全量结果。

## 测试

- 修改 `source_excerpt_pool.py` 或 `source_excerpt_pool_lib/` 后运行 `python -m pytest tests/test_source_excerpt_pool.py -q`。
- 修改 `object_pool_importer.py` 后运行 `python -m pytest tests/test_object_pool_importer.py -q`。
- 修改证据簇、重算、计分细则表、规则承载影子层或健康检查工具后运行对应 focused tests：`tests/test_evidence_cluster_workbench.py`、`tests/test_i5b_factor_recalculator.py`、`tests/test_i5b_factor_consistency_audit.py`、`tests/test_i5b_factor_table_sync.py`、`tests/test_i5b_calc_breakdown.py`、`tests/test_i5b_item_result_calculator.py`、`tests/test_i5b_rule_evidence_unit_candidate_builder.py`、`tests/test_i5b_rule_evidence_unit_db_sync.py`、`tests/test_i5b_rule_evidence_unit_preview.py`、`tests/test_i5b_rule_evidence_unit_issue_summary.py`、`tests/test_i5b_fact_relation_candidate_sync.py`、`tests/test_i5b_fact_relation_gap_summary.py`、`tests/test_i5b_health_check.py`。
