# AGENTS.md

本文件只约束 `scripts/dev/**` 下的开发辅助工具。I5B 数据链的完整执行步骤见 [`../../docs/数据结构与生成库/I5B数据链运行流程.md`](../../docs/数据结构与生成库/I5B数据链运行流程.md)。

## 职责边界

- `scripts/dev/**` 只放开发、诊断、召回、导入、校验、重算辅助和本地报告工具。
- 开发工具不得替代正式评分规则、证据裁量、档位结论或人工回源判断。
- 涉及中文 JSON/Markdown 读写时使用 UTF-8、`ensure_ascii=False` 和稳定排序；不要用 `pwsh` / PowerShell inline 传递长中文正文。

## 摘录召回工具

- `source_excerpt_pool.py` 是 review-first 召回工具，只生成对象、查询计划和摘录候选。
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
- `i5b_calc_breakdown.py` 是只读日志拆解工具，用于按皇帝/规则调出证据簇计算过程和定分计算过程，不写数据库。
- `i5b_talent_discovery_audit.py` 是只读覆盖审计工具，用于对比检索包 `POS-TALENT-RECOGNITION` 与最新 `talent_discovery` 入簇对象；补链或重算前必须先看缺口，写回受影响证据簇后必须用 `--fail-on-gap` 复跑。已回源但不支撑进入 `talent_discovery` 的对象，用 `--accepted-missing 皇帝:对象` 显式标注，不得静默忽略。
- 证据簇日志必须保留 `calc_detail.factor_refs`，保证修改规则内部乘数后可从日志重放。
- 新增史料对象时先补对象链和受影响证据簇，再用完整日志重放检查全量结果。

## 测试

- 修改 `source_excerpt_pool.py` 后运行 `python -m pytest tests/test_source_excerpt_pool.py -q`。
- 修改 `object_pool_importer.py` 后运行 `python -m pytest tests/test_object_pool_importer.py -q`。
- 修改证据簇或重算工具后运行相关 focused tests：`tests/test_evidence_cluster_workbench.py`、`tests/test_i5b_factor_recalculator.py`、`tests/test_i5b_item_result_calculator.py`。
