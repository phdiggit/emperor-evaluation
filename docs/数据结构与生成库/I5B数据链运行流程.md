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
-> fact_relations / rule_evidence_units / rule_evidence_unit_members（影子层，当前不改正式算分）
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
- `fact_relations`、`rule_evidence_units`、`rule_evidence_unit_members`：规则承载对象影子层，用于拆分“对象有史料”和“rule 实际算谁”；当前只服务预览和审计，不替代正式证据簇输入。
- `eval_rule_factors`、`eval_rule_factor_options`：计分细则结构化镜像；从规则文档同步因子名、标签、数值和文档来源行。
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

## 3.1. 规则承载对象影子层

当对象链里同时存在人物、群体、事件和机制时，先用规则承载对象影子层判断“该 rule 算哪个对象，哪些对象只是上下文”。详细口径见 [`规则承载对象关系模型.md`](规则承载对象关系模型.md)。

当前影子层不改变正式算分。正式证据簇仍从 `evd_cluster_calc_details` 和对象链重放；影子层只用于发现以下问题：

- `anti_nepotism` 把机制、事件或笼统群体当成计分承载对象，而不是具体受宠任用对象；
- `tolerate_talent` 同一事实链里事件、机制、群体和人物重复入分；
- 某个 `rule_code` 的对象存在史料关联，但缺少清晰的 `scoring_role`；
- 同一 `obj_src_id` 在同一 rule 下被多个规则证据单元重复计分。

从当前计算明细生成候选 payload：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_rule_evidence_unit_candidate_builder.py `
  --emperor 武则天 `
  --rule-code tolerate_talent `
  --rule-code anti_nepotism `
  --output .tmp/rule-evidence-units/wuzetian_i5b_units.json `
  --format json
```

只读预览工具：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_rule_evidence_unit_preview.py `
  --input .tmp/rule-evidence-units/wuzetian_i5b_units.json `
  --format markdown `
  --fail-on-issue
```

将当前计算明细中的候选承载对象幂等写入影子表：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_rule_evidence_unit_db_sync.py `
  --all-emperors `
  --format markdown `
  --output .tmp/rule-evidence-units/i5b_shadow_sync.md
```

该同步只写 `rule_evidence_units` / `rule_evidence_unit_members`，默认保持 `score_mode=shadow`、`review_status=needs_review`，不改变正式证据簇或总分。`fact_relations` 需要在主谓宾关系明确后再写入，不从 `calc_detail` 自动合成。

从影子承载对象生成第一批事实关系候选：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_fact_relation_candidate_sync.py `
  --all-emperors `
  --format markdown `
  --output .tmp/rule-evidence-units/i5b_fact_relation_sync.md
```

该工具读取 `fact_relation_predicate_options` 词表，默认只处理 `anti_nepotism` / `tolerate_talent` 的具体 `person` 承载对象，写入 `fact_relations` 时保持 `review_status=needs_review`。机制、事件、群体不会被自动生成事实关系候选；它们应先作为 `rule_evidence_unit_members` 或人工确认后的上下文关系处理。

payload 的最小结构：

```json
{
  "emperor": "武则天",
  "item_code": "I5B",
  "units": [
    {
      "rule_code": "tolerate_talent",
      "causal_chain_key": "wuzetian-cruel-officials",
      "direction": "negative",
      "scoring_role": "harmed_talent",
      "scored_obj": {
        "name": "黑齿常之",
        "obj_type": "person",
        "obj_src_id": 1629
      },
      "members": [
        {
          "role": "mechanism_context",
          "name": "酷吏罗织机制",
          "obj_type": "mechanism",
          "obj_src_id": 966
        },
        {
          "role": "group_context",
          "name": "被诬陷牵连官员",
          "obj_type": "group",
          "obj_src_id": 968
        }
      ]
    }
  ]
}
```

影子层判断完成后，若确认当前 `obj_srcs` 或计算明细错承载，应回到对象链、证据簇明细和 factor profile 修正，再按正式流程重算。

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

`i5b_factor_recalculator.py --write-clusters` 或 `--write-results` 写库前会自动运行因子一致性 hard-error 审计。典型拦截对象包括：`handling_severity >= 2.5` 时材料注释同时写明“不等同于系统清洗”“象征性信用撤销”“轻处分”等低严重度边界；或 `tolerate_talent` 负向材料绑定了 `talent_quality` 为佞臣、大佞臣、历史级佞臣的施害者对象。旧明细中的 `disposition_severity` 仍会被审计识别。只读审计可单独运行：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_factor_consistency_audit.py `
  --cluster-formula evidence_cluster_signal_v3 `
  --fail-on-error
```

写回受影响证据簇后，还应按目标 rule 从 `emp_objs` 全量扫对象覆盖。普通 rule 用于发现对象已入库但漏挂目标 `rule_code`；`team_building` 用于检查自动团队候选是否已进入计算明细：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_rule_object_coverage_audit.py `
  --emperor 李世民 `
  --rule-code team_building `
  --fail-on-gap
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

## 4.1. 计分细则表同步

计分规则文档仍是人工语义源；`eval_rule_factors` 和 `eval_rule_factor_options` 是供脚本读取、审计和后续稳定重算使用的结构化镜像。同步范围包括：

- `docs/证据规则/证据簇计算公式.md` 中 I5B 当前使用的默认因子：`directness_factor`、`attribution_factor`、`source_factor`、`context_factor`。
- `docs/分项规则/第五项统治者政治素质/B用人与授权.md` 中的共享业务因子、rule 专用因子和 `obj_attrs.value_text -> talent_quality_factor` 等属性映射。

查看文档抽取结果：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_factor_table_sync.py --format markdown
```

生成可审阅的 PostgreSQL upsert SQL：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_factor_table_sync.py `
  --render-upsert-sql `
  --output .tmp/i5b_factor_options_upsert.sql
```

同步检查可用 `--expected-json` 对比从表中导出的 JSON 快照，并用 `--fail-on-diff` 作为 CI 或本地阀门。后续若把证据簇重算脚本切到表读数，必须先保证 `factor_refs` 的标签能在 `eval_rule_factor_options` 中唯一命中；无法命中的旧标签应先迁移明细或重算证据簇，不得在计算器里静默 fallback 到裸数字。

若本地已配置 PostgreSQL DSN，可直接做只读表快照或文档-表同步检查：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_factor_table_sync.py --dump-db-json

python scripts/dev/i5b_factor_table_sync.py `
  --check-db-sync `
  --fail-on-diff

python scripts/dev/i5b_factor_table_sync.py `
  --audit-calc-details `
  --fail-on-diff
```

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

`--from-details` 默认从 `eval_rule_factor_options` 读取当前因子取值；只有本地 fixture 或迁移排障需要旧文档解析时，才显式加 `--factor-source docs`。

该路径适用于“只改规则内部乘数因子”的重算。若新增或删除史料对象，必须先补对象链和受影响证据簇，再用明细表重放做全量一致性检查。
写回路径会先执行因子一致性 hard-error 审计；若审计失败，应回到对应 `obj_srcs.note` 和 `factor_refs` 修正材料编码，不得通过改总分或结果层公式绕过。

写回证据簇和结果后，应刷新影子承载层与事实关系候选，再运行只读健康检查：

```powershell
$env:PYTHONUTF8='1'
python scripts/dev/i5b_rule_evidence_unit_db_sync.py `
  --all-emperors `
  --format markdown `
  --output .tmp/rule-evidence-units/i5b_shadow_sync.md

python scripts/dev/i5b_fact_relation_candidate_sync.py `
  --all-emperors `
  --format markdown `
  --output .tmp/rule-evidence-units/i5b_fact_relation_sync.md

python scripts/dev/i5b_health_check.py `
  --output .tmp/i5b/i5b_health_check.md `
  --fail-on-issue
```

`i5b_health_check.py` 不重算、不写库，只汇总当前库里的因子一致性、规则承载预览、事实关系 gap 和评分简表。若刚改过 `calc_detail` 或对象承载关系，必须先运行上面的 shadow / fact candidate 同步命令，否则事实关系 gap 检查会看到旧影子层。

## 6. 常见重算场景

只改规则内部乘数：

1. 修改分项规则文档中的因子表。
2. 运行 `i5b_factor_table_sync.py --render-upsert-sql`，审阅后把细则表同步到 PostgreSQL。
3. 运行 `i5b_factor_table_sync.py --check-db-sync --fail-on-diff` 和 `--audit-calc-details --fail-on-diff`。
4. 运行 `i5b_factor_recalculator.py --from-details --dry-run`。
5. 检查结果。
6. 运行 `i5b_factor_consistency_audit.py --fail-on-error` 检查因子和材料注释是否自洽。
7. 运行 `--write-clusters --write-results` 写回；写库前会再次自动执行 hard-error 审计。
8. 运行 shadow / fact candidate 同步，再运行 `i5b_health_check.py --fail-on-issue`。

新增史料或对象：

1. 补检索包或确认已有检索包对象。
2. 回源史料。
3. 用 `object_pool_importer.py` dry-run 和导入。
4. 为受影响 rule 更新 factor profile。
5. 写回受影响 `evd_clusters`。
6. 运行 `i5b_rule_object_coverage_audit.py --rule-code <rule_code> --fail-on-gap`；普通 rule 若有已回源但不支撑入该 rule 的对象，用 `--accepted-missing 皇帝:对象` 显式列出。
7. 若受影响 rule 是 `talent_discovery`，运行 `i5b_talent_discovery_audit.py --fail-on-gap`；确有已回源不支撑入 rule 的对象，用 `--accepted-missing 皇帝:对象` 显式列出。
8. 运行 `i5b_factor_consistency_audit.py --fail-on-error`，确认高严重度等因子没有和材料注释冲突。
9. 从明细表重放，确认全量结果一致。
10. 运行 shadow / fact candidate 同步，再运行 `i5b_health_check.py --fail-on-issue`。

改结果层公式：

1. 更新分项规则文档和 `scripts/build/i5b_item_result_calculator.py`。
2. 提升 `item_result_formula_i5b_*` 版本。
3. 用现有 `evd_clusters` 重算 `emp_item_results`。
4. 更新 `emp_item_result_calc_details` 并记录验证命令。
5. 运行 `i5b_health_check.py --fail-on-issue`；如果未改证据簇明细，可不刷新 shadow / fact candidate。

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
通用 rule 对象覆盖也是硬阀门：普通 rule 检查某皇帝已有 `emp_objs` 的对象是否缺少目标 `rule_code` 的 `obj_srcs`；`team_building` 检查 `emp_objs` 中带 `talent_quality` 的人物对象是否进入 `team_quality_components`。该审计不从其他 rule 反推候选，而是直接扫描 `emp_objs` 全量对象。
因子一致性是另一道硬阀门：新写入或重放证据簇后必须跑 `i5b_factor_consistency_audit.py --fail-on-error`。如果 high-severity 因子被审计拦截，应修正具体材料因子或材料注释；不得把材料边界写成“非系统清洗”，同时给出系统清洗档位。
规则承载对象和事实关系 gap 是当前影子层硬阀门：重算后运行 `i5b_rule_evidence_unit_db_sync.py` 与 `i5b_fact_relation_candidate_sync.py` 刷新影子层，再用 `i5b_health_check.py --fail-on-issue` 确认 `rule_evidence_unit_preview` 和 `fact_relation_gap` 均为 0。

## 8. 禁止做法

- 不得用预期分数倒置确定证据簇或因子取值。
- 不得用抽象事件名直接跨项扣分；必须绑定具体对象、具体史料和具体规则维度。
- 不得把检索包当证据。
- 不得因工具数量限制遗漏检索包对象。
- 不得把无命中当成无材料。
- 不得为无材料 rule 生成空证据簇。
- 不得在 `raw_objs.note` 写方向、规则、评分或档位。
- 不得只改结果层公式处理某一事件；应回到对象、史料、证据簇和规则内部因子。
- 不得在材料注释已声明低严重度边界时，给出高严重度因子；因子取值必须能被该条 `obj_srcs.note` 中的具体事实支撑。

## 9. 最小验证

涉及本链路的常用 focused tests：

```powershell
python -m pytest tests/test_source_excerpt_pool.py tests/test_object_pool_importer.py -q
python -m pytest tests/test_i5b_factor_recalculator.py tests/test_i5b_factor_consistency_audit.py tests/test_i5b_factor_table_sync.py tests/test_i5b_factor_options_schema.py tests/test_evidence_cluster_workbench.py tests/test_i5b_item_result_calculator.py -q
python -m pytest tests/test_i5b_rule_evidence_unit_candidate_builder.py tests/test_i5b_rule_evidence_unit_db_sync.py tests/test_i5b_rule_evidence_unit_preview.py tests/test_i5b_rule_evidence_unit_issue_summary.py tests/test_i5b_fact_relation_candidate_sync.py tests/test_i5b_fact_relation_gap_summary.py tests/test_rule_evidence_units_schema.py -q
python -m pytest tests/test_i5b_calc_breakdown.py tests/test_i5b_health_check.py tests/test_scripts_dev_i5b_registry.py -q
python -m py_compile scripts/dev/source_excerpt_pool.py scripts/dev/object_pool_importer.py scripts/dev/evidence_cluster_workbench.py scripts/dev/i5b_factor_recalculator.py scripts/dev/i5b_factor_consistency_audit.py scripts/dev/i5b_factor_table_sync.py scripts/dev/i5b_rule_evidence_unit_candidate_builder.py scripts/dev/i5b_rule_evidence_unit_db_sync.py scripts/dev/i5b_rule_evidence_unit_preview.py scripts/dev/i5b_rule_evidence_unit_issue_summary.py scripts/dev/i5b_fact_relation_candidate_sync.py scripts/dev/i5b_fact_relation_gap_summary.py scripts/dev/i5b_health_check.py scripts/build/i5b_item_result_calculator.py
```

涉及 `scripts/**` 或 `docs/**` 的 PR，还应按根目录和对应目录 `AGENTS.md` 运行适用的治理检查。
