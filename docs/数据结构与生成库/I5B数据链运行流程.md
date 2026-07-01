# I5B 数据链运行流程

本文是第五项B“用人与授权”当前 PostgreSQL 数据链的执行手册。它说明从检索包到正式子项结果的运行步骤、关键表、计算明细表和重算路径；评分语义仍以分项规则和证据规则文档为准。

## 入口和边界

执行前先读：

- 根目录 `AGENTS.md`
- `data/query_profile_batches/AGENTS.md`
- `scripts/dev/AGENTS.md`
- `docs/分项规则/第五项统治者政治素质/B用人与授权.md`
- `docs/证据规则/证据簇计算公式.md`

当前链路：

```text
data/query_profile_batches/*.jsonl
-> scripts/dev/source_excerpt_pool.py
-> scripts/dev/object_pool_importer.py
-> src_docs / raw_objs / emp_objs / obj_srcs / obj_attrs
-> evd_clusters + evd_cluster_calc_details
-> emp_item_results + emp_item_result_calc_details
```

检索包、摘录池和临时 payload 都不是证据。只有回源、人工判断、完成相邻项切分并写入对象链的材料，才可进入证据簇。

## 核心数据表

- `eval_items`、`eval_rules`：I5B 初始规则表。
- `emps`：皇帝主表。
- `src_docs`：史源文献粒度。
- `raw_objs`：原始对象粒度，不预合并、不提前评分。
- `emp_objs`：皇帝-对象关系，同一原始对象可绑定不同皇帝。
- `obj_srcs`：对象-史源-规则链，必须同时写 `obj_id` 和 `emp_obj_id`。
- `obj_attrs`：对象属性；`talent_quality` 必须有 `doc_id`，属性史源最好也出现在该对象 `obj_srcs`。
- `evd_clusters`：证据簇，保存 `positive_signal`、`negative_signal`。
- `evd_cluster_calc_details`：证据簇计算明细，保存材料因子、`factor_refs`、覆盖关系和对象侧聚合。
- `emp_item_results`：I5B 子项结果，是公式输出，不是事实源。
- `emp_item_result_calc_details`：定分计算明细，保存规则输入、响应函数参数、`base_core` 和最终定分过程。

`obj_srcs.emp_obj_id -> emp_objs.id` 是防止跨皇帝串料的关键。生成证据簇时按具体皇帝对象链聚合，不只按 `raw_objs.id` 聚合。

## 1. 检索包持久化

人物级检索包持久化到：

```text
data/query_profile_batches/i5b_layered_retrieval_profiles_20260630.jsonl
```

要求：

- 一人一行 JSON object。
- 新增校准人物必须追加到同一批次文件，不能只留在 `.tmp`、日志或对话记忆里。
- `core_positive_objects`、`supplemental_objects`、`negative_or_reversal_objects` 默认都进入待回源队列。
- `adjacent_split_objects` 用于切分提示，默认不直接入分。
- 检索包不是证据，不能凭检索包内容写分、写档位或生成证据簇。

离线检查某个人的对象和查询计划：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/source_excerpt_pool.py `
  --profile data/query_profile_batches/i5b_layered_retrieval_profiles_20260630.jsonl `
  --person 朱祐樘 `
  --output .tmp/source-excerpts/zhuyoutang_offline.json `
  --format json `
  --offline `
  --include-adjacent
```

默认必须遍历并登记检索包对象。若显式使用 `--max-queries` 或 `--max-queries-per-object`，输出中的 `skipped_search_plans` 必须被视为待处理缺口。

## 2. 摘录和回源

召回辅助工具：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/source_excerpt_pool.py `
  --profile data/query_profile_batches/i5b_layered_retrieval_profiles_20260630.jsonl `
  --person 刘彻 `
  --output .tmp/source-excerpts/liuche_full.json `
  --format json `
  --include-adjacent `
  --pages-per-query 8 `
  --context-chars 420 `
  --max-passages-per-page 4 `
  --request-delay 1.0 `
  --max-retries 4 `
  --retry-backoff 3.0
```

注意：

- `source_excerpt_pool.py` 只帮助定位，不写数据库。
- 摘录无命中不等于无史料；网络错误、源过滤过严或别字都会造成漏召回。
- 检索包内对象应逐个查，不能因为自动工具无命中就跳过。
- 相邻项材料可以保留为切分线索，但不能抽象扣分或抽象加分。
- Wikisource 在线召回默认启用请求间隔和 429/5xx 重试；大批量跑时优先提高 `--request-delay`、`--max-retries`、`--retry-backoff`，不要减少检索包对象覆盖。
- 输出中的 `throttle` 记录本次节流参数；`retry_events` 记录每次退避等待；`errors` 记录重试后仍失败的查询或页面。

## 3. 对象池导入

生成 payload 模板：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/object_pool_importer.py `
  --template-from-profile data/query_profile_batches/i5b_layered_retrieval_profiles_20260630.jsonl `
  --person 朱祐樘 `
  --output .tmp/object-payloads/zhuyoutang_template.json
```

导入前必须人工补完：

- `sources[*]`：史源信息。
- `objects[*].note`：只写对象身份或事件事实，不写规则、方向、评分。
- `objects[*].links[*]`：史源与 `rule_code`、`direction` 的关系。
- `objects[*].attrs[*]`：只写可回源属性；`talent_quality` 必须有 `doc_id`。

导入流程：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/object_pool_importer.py --input .tmp/object-payloads/zhuyoutang_payload.json --dry-run
python scripts/dev/object_pool_importer.py --input .tmp/object-payloads/zhuyoutang_payload.json
```

硬规则：

- `raw_objs` 必须保持原始粒度，不能加工合并。
- 所有 `raw_objs` 必须有至少一条 `obj_srcs`。
- `raw_objs.note` 不写规则、方向、档位、评分或“正负向”。
- `obj_srcs.note` 可以说明史料对规则维度的帮助，但仍应绑定具体对象和具体事实。

孤儿对象检查：

```powershell
$env:PYTHONUTF8='1'
python -c "import psycopg; from scripts.dev.evidence_cluster_workbench import resolve_dsn; \
conn=psycopg.connect(resolve_dsn('EMPEROR_EVAL_PG_DSN')); \
cur=conn.cursor(); cur.execute(\"select count(*) from raw_objs ro where not exists (select 1 from obj_srcs os where os.obj_id=ro.id)\"); \
print(cur.fetchone()[0]); conn.close()"
```

结果应为 `0`。

## 4. 证据簇计算

证据簇按 I5B 六个固定 `rule_code` 写入：

- `talent_discovery`
- `appointment_trust`
- `delegation`
- `team_building`
- `tolerate_talent`
- `anti_nepotism`

无材料的 rule 不生成 `evd_clusters`；结果层按 `positive_signal=0`、`negative_signal=0` 处理。

证据簇写入工具：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/evidence_cluster_workbench.py --help
```

当前推荐的可重放重算工具：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_factor_recalculator.py --input .tmp/i5b_factor_profile.json --dry-run
python scripts/dev/i5b_factor_recalculator.py --input .tmp/i5b_factor_profile.json --write-clusters --write-results
```

写回受影响证据簇后，必须复跑发现人才覆盖审计。已回源但史料不支撑进入 `talent_discovery` 的对象，只能通过 `--accepted-missing 皇帝:对象` 显式标注，不能静默跳过：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_talent_discovery_audit.py `
  --fail-on-gap `
  --accepted-missing 刘邦:曹参
```

证据簇计算明细写入 `evd_cluster_calc_details.calc_detail`，尤其是：

- `materials[*].obj_src_id`
- `materials[*].obj_key`
- `materials[*].obj_name`
- `materials[*].side`
- `materials[*].factor_refs`
- `materials[*].factor_values`
- `object_side_scores`
- `covered_material_ids`
- `scored_material_ids`
- `supporting_material_ids`
- `positive_signal`
- `negative_signal`

`factor_refs` 保存枚举标签，用于后续修改公式表乘数后直接代换重放；`factor_values` 保存当次实际取值，用于审计。
`obj_key` 必须来自稳定对象标识，例如 `obj_id` 或人工确认的对象 key；不得用 `obj_src_id`、材料行号或临时路径替代，否则会破坏同对象去重。
`covered_material_ids` 表示本簇覆盖的全部 `obj_srcs`，`scored_material_ids` 表示实际进入 `calc_detail.materials` 的计分材料，`supporting_material_ids` 只表示属性、身份或同对象补源材料，不直接入分。

## 5. 结果重算

结果层读取 `evd_clusters` 并写入 `emp_item_results`。当前 I5B 结果公式在：

```text
docs/分项规则/第五项统治者政治素质/B用人与授权.md
scripts/build/i5b_item_result_calculator.py
```

从明细表重放并试算：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_factor_recalculator.py `
  --from-details `
  --dry-run
```

从明细表重放并写回：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_factor_recalculator.py `
  --from-details `
  --write-clusters `
  --write-results
```

该路径适用于“只改规则内部乘数因子”的重算。若新增或删除史料对象，必须先补对象链和受影响证据簇，再用明细表重放做全量一致性检查。

## 6. 常见重算场景

只改规则内部乘数：

1. 修改分项规则文档中的因子表。
2. 运行 `i5b_factor_recalculator.py --from-details --dry-run`。
3. 检查结果。
4. 运行 `--write-clusters --write-results` 写回。

新增史料或对象：

1. 补检索包或确认已有检索包对象。
2. 回源史料。
3. 用 `object_pool_importer.py` dry-run 和导入。
4. 为受影响 rule 更新 factor profile。
5. 写回受影响 `evd_clusters`。
6. 运行 `i5b_talent_discovery_audit.py --fail-on-gap`；确有已回源不支撑入 rule 的对象，用 `--accepted-missing 皇帝:对象` 显式列出。
7. 从明细表重放，确认全量结果一致。

改结果层公式：

1. 更新分项规则文档和 `scripts/build/i5b_item_result_calculator.py`。
2. 提升 `item_result_formula_i5b_*` 版本。
3. 用现有 `evd_clusters` 重算 `emp_item_results`。
4. 更新 `emp_item_result_calc_details` 并记录验证命令。

## 7. 查漏检查

检索包对象和数据库对象应定期比对。重点看：

- 已有 `emp_item_results` 的皇帝是否都有 query profile。
- 每个 query profile 对象是否都有 search plan。
- `core_positive_objects`、`supplemental_objects`、`negative_or_reversal_objects` 是否已回源或记录待回源原因。
- `adjacent_split_objects` 是否保留为相邻项切分线索。

缺口报告建议写入 `.tmp/**`，例如：

```text
.tmp/i5b_profile_object_gap_report.json
.tmp/i5b_current_profile_traversal_report.json
```

缺口报告不是正式证据，但应作为下一轮补源清单。
其中 `talent_discovery` 是硬阀门：新皇帝写回证据簇后必须跑 `i5b_talent_discovery_audit.py --fail-on-gap`。如果缺口属于“已检索且已回源，但当前史料不支撑进入发现人才”，应使用 `--accepted-missing` 留下可见例外；其他缺口必须回到检索、回源或对象链编码补齐。

## 8. 禁止做法

- 不得用预期分数倒置确定证据簇或因子取值。
- 不得用抽象事件名直接跨项扣分；必须绑定具体对象、具体史料和具体规则维度。
- 不得把检索包当证据。
- 不得因工具数量限制遗漏检索包对象。
- 不得把无命中当成无材料。
- 不得为无材料 rule 生成空证据簇。
- 不得在 `raw_objs.note` 写方向、规则、评分或档位。
- 不得只改结果层公式处理某一事件；应回到对象、史料、证据簇和规则内部因子。

## 9. 最小验证

涉及本链路的常用 focused tests：

```powershell
python -m pytest tests/test_source_excerpt_pool.py tests/test_object_pool_importer.py -q
python -m pytest tests/test_i5b_factor_recalculator.py tests/test_evidence_cluster_workbench.py tests/test_i5b_item_result_calculator.py -q
python -m py_compile scripts/dev/source_excerpt_pool.py scripts/dev/object_pool_importer.py scripts/dev/evidence_cluster_workbench.py scripts/dev/i5b_factor_recalculator.py scripts/build/i5b_item_result_calculator.py
```

涉及 `scripts/**` 或 `docs/**` 的 PR，还应按根目录和对应目录 `AGENTS.md` 运行适用的治理检查。
