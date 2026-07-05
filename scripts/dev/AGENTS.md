# AGENTS.md

本文件只约束 `scripts/dev/**` 下的开发辅助工具。I5B 数据链的完整执行步骤见 [`../../docs/数据结构与生成库/I5B数据链运行流程.md`](../../docs/数据结构与生成库/I5B数据链运行流程.md)；retrieval_v2 clean 抓包、判读和补抓流程见 [`../../docs/数据结构与生成库/retrieval_v2_clean抓包流程.md`](../../docs/数据结构与生成库/retrieval_v2_clean抓包流程.md)。

## 职责边界

- `scripts/dev/**` 只放开发、诊断、召回、导入、校验、重算辅助和本地报告工具。
- 开发工具不得替代正式评分规则、证据裁量、档位结论或人工回源判断。
- 涉及中文 JSON/Markdown 读写时使用 UTF-8、`ensure_ascii=False` 和稳定排序；不要用 `pwsh` / PowerShell inline 传递长中文正文。

## 摘录召回工具

- `source_excerpt_pool.py` 是 review-first 召回工具入口，真实实现拆在 `source_excerpt_pool_lib/`；只生成对象、查询计划和摘录候选。
- `i5b_*source_pack*` 与 `i5b_*query_profile*` 工具当前以 I5B 为默认 adapter；采集链公共元数据使用 `workflow_code` / `source_scope`，新增评分项复用时必须隔离输出文件名、job payload 和 handoff 契约，不得在公共库里继续写死 I5B。
- 在线抓取属于离线采集准备步骤；I5B 主链优先使用已审计的 source pack，通过 `source_excerpt_pool.py --source-pack` 从本地页文生成摘录候选。
- `i5b_source_pack_fetcher.py` 是离线史料包抓取入口，从 query profile 调 Wikisource search/fetch 并写 `manifest.json`、`src_docs.jsonl`、`pages/*.txt`、`excerpts.jsonl` 和 `fetch_report.json`；输出默认在 `.tmp/**`，不得写正式 `data/**`。
- `i5b_source_pack_fetcher.py --candidate-discovery` 是抓包前候选对象发现，不是抓包后验收；它把发现候选临时合并到 `candidate_inventory` 再生成搜索计划。
- `fetch_report.json` 的 `object_coverage.objects_with_unsearched_aliases` 是硬缺口：声明过别名但别名查询被 cap、超时或连续错误跳过时，不能把该对象按“无史料”跳过；`objects_with_exhausted_alias_searches` 才表示已声明别名都搜过但仍无页面命中。
- `i5b_source_pack_worker.py` 是抓包 job worker，轮询 workflow 的 `jobs_dir`，把 `workflow_code`、`source_scope` 和 job 选项透传给 fetcher；它只消费 job 文件并写日志/状态，不做 profile 裁量。
- `i5b_source_pack_audit.py` 是离线史料包审计入口，检查 `manifest.json`、`src_docs.jsonl`、本地页文和可选 `excerpts.jsonl` 的 src_key 关系；通过后才进入摘录池或对象 payload 生成。
- `i5b_source_pack_status.py` 是只读抓包状态台账入口，汇总全名单、query profile、jobs 和 source-packs，回答缺检索包、半成品、已投未跑、成功、失败和需补检索包等状态。
- `i5b_source_pack_control_board.py` 是只读总控减负入口，汇总 handoff / status，生成 ready 队列、补包队列和建议子进程派工单；它不投递 jobs、不写回 profile、不替代评分裁决。
- `i5b_query_profile_refiner.py` 是只读检索包补强候选生成器，从状态台账和 source pack 覆盖缺口生成待审 patch 候选；它不联网、不投抓包队列、不直接修改 query profile。
- `i5b_query_profile_refiner_daemon.py` 是 refiner 的周期刷新入口，只生成台账和补强报告，不消费 jobs、不调用 Wikisource。
- `i5b_source_pack_runtime_supervisor.py` 只用于同一服务内拉起抓包 worker、refiner daemon 和可选 pipeline daemon 等独立子进程；不得把它们的业务逻辑耦合到一起。
- `i5b_source_pack_pipeline_daemon.py` 是采集层流水线调度入口，读取状态台账、refiner 候选和显式传入的已审 seed report，按 fingerprint 去重后写派生 query profile 并投递下一轮抓包 job；它不得写回 canonical query profile，不替代人工对象裁量。seed report 只有带 `accepted_for_profile=true` 或 `review_status=accepted` 的条目才可投递。
- `i5b_source_pack_handoff.py` 是批次 Codex 交接契约工具，用于初始化、校验和汇总 source pack 批次验收目录；它只检查交接契约和 source pack 审计，不替代人工回源裁量。
- `retrieval_v2_bootstrap.py` 是抓包控制面 v2 的初始化入口，只创建 `retrieval_v2` schema、复制规则契约快照并播种检索目标；它不创建对象池、证据簇、总分或正式评分结果表。
- `retrieval_v2_contracts.py` 是 retrieval_v2 clean 抓包的共享契约层，只放覆盖矩阵模板、角色族、二级 rule hint、缺口类型等纯函数和常量；它不联网、不连库、不读取旧结果、不做判读。
- `retrieval_v2_task_skeleton.py` 是 retrieval_v2 taskgen 骨架和 discovery profile 复用层，从规则契约生成稳定 task 字段，并把 Codex discovery 只合并到对象、别名、史源和查询词等发现字段；它不联网、不写库、不判读。
- `retrieval_v2_discovery_profiles.py` 是 retrieval_v2 discovery profile 的生成、扫描、校验、选择和写回工具；profile 只复用对象、别名、史源和发现说明，必须重新套当前 rule 的 task skeleton 与 coverage matrix。
- `retrieval_v2_batch_taskgen.py` 是 retrieval_v2 多目标 taskgen prompt 和 batch discovery 解析层，只共享同一 rule 契约上下文，不合并不同皇帝的对象事实；输出必须逐目标 merge 回各自 task skeleton。
- `retrieval_v2_taskgen_preseed.py` 是 retrieval_v2 taskgen 前置公开检索层，只用皇帝元数据、taskgen 新发现对象名和 Wikisource search 生成本轮候选 source documents / search hints；它不得读取旧 source pack、旧对象池、旧判读结果或写数据库。
- `retrieval_v2_clean_runner.py` 是 retrieval_v2 clean 抓包的正式流水线入口，编排 taskgen、候选切片、机械别名补抓、候选重跑、Codex 判读、可选对象分片 judge 聚合和 summary；它只写本轮 `run_root` 和可复用原始史源页 cache，不写数据库，不读旧 source pack / 对象池 / 判读结果。
- `retrieval_v2_clean_cli.py` 是 `retrieval_v2_clean_runner.py` 的 CLI 和调度层，承载默认流式 taskgen、batch taskgen、进度事件和命令行参数；canonical 命令入口仍是 `retrieval_v2_clean_runner.py`。
- `retrieval_v2_clean_summary.py` 和 `retrieval_v2_run_events.py` 分别承载 summary 汇总、judge anomaly 自审和 `run_events.jsonl` 事件日志；它们不抓源、不判读、不连接数据库。
- `retrieval_v2_candidate_source_refiner.py` 是 retrieval_v2 候选缺口补源层，从本轮 candidates 的 `objects_without_slices` / `source_missing` / `alias_missing` 对象生成对象级 Wikisource 检索并合并新的 `source_documents`；它不读旧结果、不判读、不写库。
- `retrieval_v2_judge_shards.py` 是 retrieval_v2 judge 分片和聚合纯函数层，只切分本轮 candidates、构造 shard prompt、重写聚合 claim/passages/bindings ID；它不调用 Codex、不联网、不读写数据库。
- `retrieval_v2_candidate_prompt.py` 是 retrieval_v2 judge prompt 构造层，把本轮 candidates 和判读预算契约转成 Codex judge prompt；它不抓源、不判读、不写库。
- `retrieval_v2_alias_refiner.py` 是 retrieval_v2 覆盖缺口到别名补抓的调度层工具，从本轮 task / candidates / judge result 生成 alias patch、patched task 和可选 CLI alias-refiner prompt；它不联网、不写库、不读旧结果、不抽取事实，只有非机械称谓判断才交给 Codex CLI 子进程。
- `retrieval_v2_source_candidates.py` 是 retrieval_v2 抓包判读前的候选片段 builder，必须遵守 retrieval_v2 clean 抓包流程；它只负责抓取/缓存源页、按别名和 rule 关键词切片并生成瘦身 Codex prompt，记录 fetch errors 和 coverage gaps；它不读旧判读结果、不写库、不替代 source pack validator。
- `retrieval_v2_source_document_policy.py` 是 retrieval_v2 source document 门禁层，按目标 source strategy、史源 root 和总称实录目标 metadata 判断某个源页是否可进入候选切片；它不抓取、不判读、不写库。
- `retrieval_v2_quality_gate.py` 是 retrieval_v2 run 质量对照入口，用旧基准 run 和候选 run 的对象覆盖、claim 数、primary binding 数、无切片对象和状态做离线验收；它只读本地 run 目录，不联网、不读数据库、不替代人工抽样原文。
- `i5b_next_stage_queue_runner.py` 是 source pack handoff 后的收货批处理入口，只消费已通过 `next_stage_queue.jsonl` 的 ready 人物，生成摘录报告和对象 payload 骨架到 `.tmp/**`；它不写数据库、不替代对象规则裁量。
- `i5b_next_stage_control_board.py` 是 ready 包消费后的总控减负入口，聚合 next-stage 骨架、对象 payload 子进程候选、review 报告和占位符审计结果，生成缺交付派工单与可 dry-run payload 清单；它不写数据库、不替代对象规则裁量。对象 payload 子进程完成后，先用该板确认主控工作区已看到候选文件，再关闭子进程。
- `i5b_query_profile_seed_builder.py` 是半成品检索包种子候选生成器，从本地已登记 search/source/evidence/anchor 行抽取同人对象候选；显式 `--source-discovery` 时可小规模 search/fetch Wikisource 页面全文来发现候选，但仍不直接升级 profile、不投抓包队列。
- 摘录输出默认写 `.tmp/**`；不得直接覆盖正式 `data/**`。
- 摘录池的“无命中”不是“无史料”；网络错误、目标页缺失、别字和过滤过严都应进入缺口复核。
- Wikisource 限流、超时和 5xx 应通过工具内置节流与重试处理；不要通过减少检索包对象覆盖来躲避限流。
- 若显式使用 query cap，工具必须报告 skipped plans；调用方不得静默跳过检索包对象。

## 对象导入工具

- `object_pool_importer.py` 只导入已经回源并人工判断过的对象 payload。
- `object_pool_aliases.py` 是对象池身份别名解析层，负责 `raw_obj_aliases` 幂等建表、别名归一、冲突检查和导入时 canonical object 归并；它不承载计分事实。
- `i5b_object_pool_detail.py` 是只读对象池明细工具，用于按皇帝或对象名列出 `emp_objs`、对象属性、`obj_srcs` 史料材料、关联 rule 和对象材料计分；它不写库、不补规则、不替代覆盖审计。
- `i5b_object_pool_integrity_audit.py` 是对象池重导入前的只读完整性闸门，遍历 `raw_objs`、`raw_obj_aliases`、`emp_objs`、`obj_srcs`、`obj_attrs`、规则策略、影子承载层和计算明细引用；它只报告断链、错链、缺源、属性冲突和策略漂移，不修库、不导入、不重算。
- `i5b_object_payload_audit.py` 是对象 payload 候选入库前的只读闸门，复用 importer 结构校验并拦截 `TODO` / `TODO_RULE_CODE` / `TODO_TALENT_QUALITY` / `TODO-SRC` 占位符；它不写数据库。
- `i5b_object_payload_import_batch.py` 是控制板 ready payload 的批量导入器，读取 `i5b_next_stage_control_board.py` JSON 输出，跳过已有成功回执，只调用 `object_pool_importer.py` 导入新增 payload，并把成功导入写入 `tmp/**` 回执。跨 Codex 子进程的 live handoff 不要放在仓库 `.tmp/**`，pytest 会在 session 结束时清理该目录。
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
- `rule_material_policy.py` 是规则材料选择策略读取层，运行时工具应从 `eval_rule_material_policies` 读取计分承载、上下文角色、对象类型过滤和覆盖审计策略；除同步/迁移工具外，不得在运行时从评分规则文档推断 rule 材料筛选口径。
- `i5b_finite_values.py` 是 I5B 有限取值与别名归一的中央 registry；新写入入口不得各自手写 `period`、`rule_code`、`direction`、`talent_quality`、对象属性码等枚举。
- `i5b_finite_value_audit.py` 是只读 DB 有限取值审计入口，检查已入库对象链是否残留英文朝代别名、未知属性码、未知 rule/subitem/direction 和同名皇帝重复分支；它不修库、不重算。
- `i5b_health_check.py` 是 I5B 重算后的一键只读健康检查入口，汇总因子一致性、规则承载预览、事实关系 gap、有限取值审计和评分简表；它不重算、不写库。
- `i5b_initial_factor_profile.py` 是无 `calc_detail` 新皇帝或缺失首轮 rule 计算明细的因子化派工入口；`worklist` 只读对象链生成可交给 Codex 子进程的批次，`patch-to-profile` 只验收 patch 并汇总为 `i5b_factor_recalculator.py --input` profile，不连接数据库、不替代人工因子裁量。普通材料 patch 以 `obj_src_id` 为主键；`team_building` 的 `emp_objs` 成员 patch 以 `emp_obj_id` 为主键，不得伪造史料材料 ID。
- `i5b_pending_material_worklist.py` 是只读 pending 因子化派工入口，从健康检查登记的 `pending_material_ids` 补齐对象、史源和 note，生成可交给 Codex 子进程处理的 JSON/Markdown worklist；它不写库、不自动赋因子。
- `i5b_pending_factor_patch.py` 是 pending 因子化交付验收入口，校验子进程填写的 patch JSONL 是否覆盖 batch 全部材料、target_action 是否合法、计分材料 factor label 是否来自候选项，并复用规则承载对象槽位政策拦截不允许作为计分承载的对象类型；它不连接数据库、不修改 calc_detail。
- `i5b_pending_factor_patch_apply.py` 是 pending patch 应用入口，把已验收 patch 写回 `evd_cluster_calc_details.calc_detail` 的 `materials` / `supporting_material_ids` / `excluded_material_ids` / `pending_material_ids`；默认 dry-run，正式落库必须显式 `--write`，写完后仍需用 `i5b_factor_recalculator.py --from-details --write-clusters --write-results` 重放结果。
- `i5b_fact_relation_candidate_sync.py` 是事实关系候选同步工具，从 `rule_evidence_units` 与 `fact_relation_predicate_options` 生成 `fact_relations` 候选；默认只处理 `anti_nepotism` / `tolerate_talent` 的具体 person，不自动 accepted，不改变正式算分输入。
- `i5b_fact_relation_gap_summary.py` 是事实关系 gap 汇总工具，从 `rule_evidence_units`、predicate catalog 和 `fact_relations` 检查非人物承载、方向不匹配、缺失关系等缺口；它只读，不写库。
- `i5b_hard_merit_handoff.py` 是硬通货交付验收工具，校验 `hard_merit_attrs.jsonl` / `fact_relation_hints.jsonl`，并把可复用事实链映射为待审候选；它不连接数据库、不写 `obj_attrs`、不写 `fact_relations`。
- `i5b_authority_eval_handoff.py` 是权威评价交付验收工具，校验 `authority_eval_attrs.jsonl`，并生成 `talent_quality` 待审候选；它不连接数据库、不写 `obj_attrs`、不替代人才等级人工确认。
- `i5b_authority_eval_distribution_audit.py` 是权威评价分布复核工具，从已交付 `authority_eval_attrs.jsonl` 中筛出疑似抬高的 `顶级人才` / `重要人才` / 历史级单源候选，以及高才具对象 `talent_profile_note` 中提示的负面边界，生成复核 worklist；它只读，不改 JSONL、不写 `obj_attrs`。
- `i5b_authority_eval_attr_sync.py` 是权威评价属性同步工具，把已通过 handoff / distribution audit 的 `talent_quality_proposal` 和可选 `talent_profile_note` 写入 `obj_attrs`；默认 dry-run，正式写入必须显式 `--write` 并设置 `I5B_OBJECT_POOL_IMPORT_UNFREEZE=1`。
- `i5b_rule_evidence_unit_candidate_builder.py` 是只读规则证据单元候选生成器，从当前 `evd_cluster_calc_details` 和对象链还原“谁正在计分”，输出待人工确认的 shadow payload；它默认不写库，不自动合并因果链。
- `i5b_rule_evidence_unit_preview.py` 是只读规则承载对象影子层预览工具，用于检查某个 I5B rule 的计分承载对象、上下文成员和同一因果链重复入分风险；它不写库、不替代正式证据簇计算。
- `i5b_rule_evidence_unit_issue_summary.py` 是规则承载预览问题汇总工具，从当前 calc_detail 重建候选并汇总 preview block/warning，用于新皇帝或重算后的 gap 阀门；它只读，不写库。
- `i5b_rule_evidence_unit_db_sync.py` 是规则证据单元影子表同步工具，只把候选 payload 幂等写入 `rule_evidence_units` / `rule_evidence_unit_members` 供人工审计；它不得合成未经确认的 `fact_relations`，也不得改变正式算分输入。
- `i5b_talent_discovery_audit.py` 是只读覆盖审计工具，用于对比检索包 `POS-TALENT-RECOGNITION` 与最新 `talent_discovery` 入簇对象；补链或重算前必须先看缺口，写回受影响证据簇后必须用 `--fail-on-gap` 复跑。已回源但不支撑进入 `talent_discovery` 的对象，用 `--accepted-missing 皇帝:对象` 显式标注，不得静默忽略。
- 计算明细写入 `evd_cluster_calc_details` 与 `emp_item_result_calc_details`；JSONL 日志不再参与当前计算、审查或重放流程。
- 修改规则内部乘数后，先同步 `eval_rule_factor_options`，再从明细表 `--from-details` 重放并重算；运行时默认从细则表读因子值，不从规则文档推断当前取值。新增史料对象时先补对象链和受影响证据簇，再用明细表重放检查全量结果。

## 测试

- 修改抓包、检索包、handoff、控制板或 ready 包消费工具后，运行对应 focused tests，至少覆盖：`tests/test_source_excerpt_pool.py`、`tests/test_i5b_source_pack_fetcher.py`、`tests/test_i5b_source_pack_worker.py`、`tests/test_i5b_source_pack_audit.py`、`tests/test_i5b_source_pack_handoff.py`、`tests/test_i5b_source_pack_status.py`、`tests/test_i5b_source_pack_control_board.py`、`tests/test_i5b_next_stage_queue_runner.py`、`tests/test_i5b_next_stage_control_board.py`、`tests/test_i5b_query_profile_refiner.py`、`tests/test_i5b_query_profile_refiner_daemon.py`、`tests/test_i5b_source_pack_runtime_supervisor.py`、`tests/test_i5b_source_pack_pipeline_daemon.py`、`tests/test_i5b_query_profile_seed_builder.py`。
- 修改对象导入、别名归一、对象明细、对象池完整性审计或 payload 闸门工具后，至少运行：`tests/test_object_pool_importer.py`、`tests/test_i5b_object_pool_detail.py`、`tests/test_i5b_object_pool_integrity_audit.py`、`tests/test_i5b_object_payload_audit.py`。
- 修改证据簇、重算、计分细则表、有限取值、规则材料策略、首轮/pending 材料派工、pending patch 验收/应用或明细拆解工具后，至少运行：`tests/test_evidence_cluster_workbench.py`、`tests/test_i5b_factor_recalculator.py`、`tests/test_i5b_factor_consistency_audit.py`、`tests/test_i5b_factor_table_sync.py`、`tests/test_rule_material_policy.py`、`tests/test_rule_material_policy_schema.py`、`tests/test_i5b_finite_values.py`、`tests/test_i5b_finite_value_audit.py`、`tests/test_i5b_initial_factor_profile.py`、`tests/test_i5b_pending_material_worklist.py`、`tests/test_i5b_pending_factor_patch.py`、`tests/test_i5b_pending_factor_patch_apply.py`、`tests/test_i5b_calc_breakdown.py`、`tests/test_i5b_item_result_calculator.py`。
- 修改硬通货、权威评价、人才等级同步或人才评价分布审计工具后，至少运行：`tests/test_i5b_hard_merit_handoff.py`、`tests/test_i5b_authority_eval_handoff.py`、`tests/test_i5b_authority_eval_distribution_audit.py`、`tests/test_i5b_authority_eval_attr_sync.py`。
- 修改规则承载影子层、事实关系、rule 覆盖审计或健康检查工具后，至少运行：`tests/test_i5b_rule_evidence_unit_candidate_builder.py`、`tests/test_i5b_rule_evidence_unit_db_sync.py`、`tests/test_i5b_rule_evidence_unit_preview.py`、`tests/test_i5b_rule_evidence_unit_issue_summary.py`、`tests/test_i5b_rule_object_coverage_audit.py`、`tests/test_i5b_fact_relation_candidate_sync.py`、`tests/test_i5b_fact_relation_gap_summary.py`、`tests/test_i5b_health_check.py`。
- 若不确定某工具的专属测试，以 `docs/文档与脚本登记/scripts_registry.json` 的 `required_tests` 为准，再叠加邻近链路测试和 `tests/test_scripts_dev_i5b_registry.py`。
