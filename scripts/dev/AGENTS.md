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
- `retrieval_v2_runtime_paths.py` 是 retrieval_v2 运行资产路径解析 helper，默认从 NAS runtime config 生成 clean run、consumption output 和 source cache 路径；显式 `--use-local-runtime` 才回落到 repo-local `tmp/.tmp`。
- `retrieval_v2_clean_cli.py` 是 `retrieval_v2_clean_runner.py` 的 CLI 和调度层，承载默认流式 taskgen、batch taskgen、进度事件和命令行参数；未显式传 `--run-root` / `--source-cache-root` 时必须通过 `retrieval_v2_runtime_paths.py` 解析默认运行资产目录。canonical 命令入口仍是 `retrieval_v2_clean_runner.py`。
- `retrieval_v2_clean_summary.py` 和 `retrieval_v2_run_events.py` 分别承载 summary 汇总、judge anomaly 自审和 `run_events.jsonl` 事件日志；它们不抓源、不判读、不连接数据库。
- `retrieval_v2_intake_manifest.py` 是消费侧 accepted clean run 收货清单生成器，只从本地 summary / task / candidates / judge 产物派生 `source_pack_code`、闸门结果和计数；它不写数据库、不读旧对象池、不执行抓包。
- `retrieval_v2_intake_rows.py` 是消费侧 normalized staging JSONL 生成器，从 intake manifest 展开 source pack、artifact、document、passage、claim、primary binding、长期 `claim_rule_binding_candidates` 和 gap event 行；未显式传 `--output-root` 时通过 `retrieval_v2_runtime_paths.py` 写入 runtime consumption 目录，不写数据库、不读旧对象池。
- `retrieval_v2_review_worklists.py` 是消费侧对象身份与材料复核 worklist 生成器，从 normalized staging JSONL 生成 object resolution 和 material review 派工清单；它不读旧对象池、不自动归并对象、不写数据库。
- `retrieval_v2_idempotency_report.py` 是消费侧幂等风险报告和 schema 草案生成器，检查 normalized staging JSONL 的 code / natural key / alias 变体重复风险，并输出离线草案；它不写数据库、不修改输入 rowset。
- `retrieval_v2_diagnostics.py` 是消费侧只读诊断总控薄入口，实际实现拆在 `retrieval_v2_diagnostics_lib/`；当前聚合 readiness、coverage、duplicates、next-actions 和 score-chain，支持 `--type person --role emperor --name ...` 通用目标筛选。它只读 retrieval_v2 并输出 JSON/Markdown，不写库、不重算、不替代具体 consumer/scorer。
- `retrieval_v2_import_plan.py` 是消费侧入库 dry-run/upsert 计划生成器，从 normalized staging JSONL 和 review worklists 生成按表排序的只读导入计划；默认不连接数据库，显式 `--db-check` 也只读 retrieval_v2 target/rule 元数据，不执行 INSERT/UPDATE。
- `retrieval_v2_import_executor.py` 是消费侧入库执行器，从 normalized staging JSONL 和 review worklists 幂等 upsert source pack / material / binding / review queue / gap event 行；默认是 DB-backed dry-run 并 rollback，只有显式 `apply --execute` 才写库，且不得自动写入对象身份最终表。I5B item-wide shadow 试吃必须传 `--source-pack-status draft`，不得把 shadow 包写成 accepted 覆盖正式 accepted-packs。
- `retrieval_v2_cross_rule_router.py` 是已入库 accepted claim 的跨 rule 候选补路由器，从 appointment_delegation 等源 rule 的 claim deterministic 补写 `claim_rule_binding_candidates`；默认 DB-backed dry-run，只有显式 `--execute` 才写库。它只产生候选和 future hint，不替代目标 rule 判读、因子化或入分裁量。
- `retrieval_v2_claim_passage_audit.py` 是已入库 claim 的 summary/passage 对齐审计和返修回填工具；默认只读 dry-run，只有显式 `--execute` 才把疑似错位 claim 写入 `material_review_queue`，加 `--write-gap-events` 才同步写 `coverage_gap_events queue=codex_review` 交抓包侧补判。进入未清材料复核队列的 claim 不得自动晋升候选、派发因子化或继续入分。
- `retrieval_v2_claim_passage_repair.py` 是抓包侧 claim/passage 错位修包工具，从 `material_review_queue` 读取已阻断或待复核项，补入同 accepted pack 的 `candidate_slices` 上下文生成 Codex 修包任务；默认只生成 worklist / dry-run，只有显式 `apply-patch --execute` 才重链 `claim_source_passages`、补 repair source passage 或标记 claim 废弃。它不做因子化、不打分、不替代跨 rule 晋升。
- `retrieval_v2_passage_fulltext_backfill.py` 是已入库 accepted 包的 source passage 全文回填工具，从包 artifact 的 `candidates.final.json` 按 `passage_payload.slice_code` 找回完整 candidate slice 文本，只在当前 `raw_text` 是该 slice 前缀且 slice 更长时更新 `source_passages.raw_text/quote_hash/passage_payload`；默认 dry-run，显式 `--execute` 才写库，不改 claim、binding 或 review 队列。
- `retrieval_v2_candidate_promoter.py` 是消费侧 formal candidate 晋升器，把已验收且可确定解析的 `claim_rule_binding_candidates` 幂等转成目标 rule 的正式 `claim_rule_bindings`，并补齐对应 scoring role 的 `material_object_links`；默认 DB-backed dry-run，只有显式 `--execute` 才写库。它不从 future hint 晋升，不凭处置性材料自动生成负向入分 binding；消费 item-wide shadow 时用 `--source-rule-code i5b_item_wide --scope active-targets --emperor <目标>` 做单目标窄验。
- `retrieval_v2_consumer.py` 是消费侧统一入口，调度补全阶段、readiness 闸门和不可自动化 worklist；默认 dry-run/read-only，只有子命令显式 `--execute` 才写库，不承载定分裁量。验收已消费 clean 包时使用 `readiness --scope accepted-packs`，避免未消费的 active targets 阻塞已消费包收口。
- `retrieval_v2_target_person_consumer.py` 是消费侧目标皇帝人物补全执行器，从 `retrieval_targets.emperor_name` 幂等写入目标皇帝的 person object、人物画像、target object、皇帝身份和可确认朝代归属；它不从 clean claim 推断皇帝身份，不补人才等级。
- `retrieval_v2_object_consumer.py` 是消费侧对象解析执行器，只从 retrieval_v2 的 object_resolution_queue 和 material/binding 表消费已入库 clean 包；默认是 DB-backed dry-run 并 rollback，只有显式 `apply --execute` 才写 `objects`、`object_names`、`target_objects`、`material_object_links`，自动接受范围限于单一 person 名称队列项。处理 shadow 或单包试吃时必须传 `--source-pack-code <pack_code>` 限定范围，避免扫全库 ready 队列。
- `retrieval_v2_person_profile_consumer.py` 是消费侧人物画像补全执行器，只为新库当前 person objects 生成一人一画像；旧对象池只作为人才等级参考源，不全量迁移人物，不自动定级缺失对象。
- `retrieval_v2_person_context_consumer.py` 是消费侧人物归属与身份候选补全执行器，只为新库当前 person objects 幂等写入 `person_affiliations` / `person_roles`；旧对象池 period 和目标皇帝 period 只作参考上下文，材料角色只能生成待复核身份候选，不替代人工身份裁量。
- `retrieval_v2_material_review_tasks.py` 是消费侧 claim/passage 材料复核派工器，从 `material_review_queue` 生成包含原文 passage 的 Codex CLI 批次和 patch 路径；它只组织 `supported` / `unsupported` / `needs_context` 三类判读，不写库、不重判正负向、rule 归属或因子取值。
- `retrieval_v2_material_review_consumer.py` 是消费侧材料复核队列执行器，只消费已确认的 `material_review_queue` patch；默认 DB-backed dry-run 并 rollback，只有显式 `apply-patch --execute` 才写复核状态和 binding/candidate 复核状态，不自动改入分结论或因子。
- `retrieval_v2_factorization_worklists.py` 是消费侧入分决策和因子化 worklist 生成器，只读新库 clean 包、材料对象链接、规则材料策略和因子取值快照；它生成 `score/supporting_only/exclude` patch 模板，不写库、不重算、不读取评分规则文档。默认 `--scope accepted-packs` 只读最新通过的 accepted 包；处理 item-wide shadow 或单包试吃时必须传 `--source-pack-code <pack_code>` 明确读指定 passed 包。
- `retrieval_v2_factorization_tasks.py` 是因子化子任务 prompt、task code 和 `expected_outputs` 契约辅助模块；它不是 CLI 入口，不连接数据库、不消费 patch、不执行评分。
- `retrieval_v2_factorization_consumer.py` 是消费侧因子化 patch 执行器，只消费已校验的 `score/supporting_only/exclude` JSONL；默认 DB-backed dry-run 并 rollback，只有显式 `apply-patch --execute` 才写 `claim_rule_binding_factor_judgments` 和 `claim_rule_binding_factor_choices`。
- `retrieval_v2_rule_scorer.py` 是消费侧规则信号聚合执行器，只从已验收的因子化判定和因子选项表计算材料分、同对象折减和 target/rule 正负信号；默认 DB-backed dry-run 并 rollback，只有显式 `apply --execute` 才写规则聚合结果。处理 item-wide shadow 分数时传 `--source-pack-code <pack_code>` 做只读算分；显式 source pack 默认禁止 `--execute`，防止 draft 或旧包覆盖正式 target/rule 聚合分。
- `retrieval_v2_judgment_worklists.py` 是消费侧判断点派工和 patch 验收入口，从新库 readiness 缺口生成 JSONL workitems、Codex CLI prompt 批次，并把后台执行计划交给 `codex-win agent` 托管进程生命周期；它只验收结构化 patch 并显式 `--execute` 后写回画像/身份/归属候选，不替代评分、人才等级或身份裁量。
- `retrieval_v2_gap_handoff.py` 是消费侧覆盖缺口到 retrieval_v2 控制面队列的桥接工具，可从本轮 clean summary 生成 `gap_handoff.jsonl` / Markdown，或幂等写入 `coverage_gap_events` 并把 ready gap 转成 `retrieval_v2.jobs`；它不执行抓包、不调用 Codex、不写对象池。
- `retrieval_v2_gap_worker.py` 是抓包侧 gap job 调度工具，默认只把 `retrieval_v2.jobs` payload 或 jobs JSONL 合并成 clean runner 执行计划；显式 `run-plan --execute` 才执行命令。它不生成事实、不写对象池，默认 candidate-only 以节省 judge token。

## retrieval_v2 子 Agent 批量任务

- 新会话、跨命令或跨子进程还要继续使用的临时脚本和 handoff 文件不得放仓库 `.tmp/**`；`.tmp/**` 会被 pytest session 或清理工具删除，只适合一次性报告、PR body 和可丢弃输出。需要稳定复用时使用 `tmp/**`、服务器 runtime 目录，或把脚本正式纳入 `scripts/dev/**`。
- `retrieval_v2_material_review_tasks.py`、`retrieval_v2_factorization_worklists.py`、`retrieval_v2_judgment_worklists.py` 等生成 Codex 子任务的工具，应把 prompt、task JSONL、patch、last message、log 全部放在 `tmp/**`，并通过 UTF-8 文件传递中文和 JSONL。
- 运行批量子任务时优先走工具自带 `run-plan` 子命令；没有专用封装时直接用 `codex-win agent run-plan --permission-profile tmp-jsonl-review --deny-policy deny-rewrite --git-snapshot minimal`。材料判读和因子化通常不需要 git 上下文，性能敏感时可改用 `--git-snapshot none`；只有诊断子进程需要 changed files 时才用 `--git-snapshot full`。
- 新生成的 `codex_tasks.jsonl` 应优先声明 `expected_outputs`，格式为 `kind=jsonl_patch`，并配置 `PATCH_JSONL_BEGIN` / `PATCH_JSONL_END` fallback；兼容旧任务可以读取顶层 `patch_path`，但新任务不要只靠旧 `patch_path` 让 codex-win 判断产物。
- 子 agent 只产出 review / patch / factorization JSONL，不直接 `--execute` 写数据库、不调用 scorer、不修改 schema、不运行抓包 runner。写库必须回到对应 consumer/promoter/scorer 工具，并先 dry-run 验证。
- 主控验收顺序：先 `codex-win agent collect` 看 run 是否完整，再用项目脚本 `recover-patches` / `validate-patch` / consumer dry-run 验 JSONL 覆盖率、枚举值、幂等键和 readiness，最后才允许显式 `--execute`。
- 对 retrieval_v2 因子化，子 agent 不应重判包侧已给出的普通正负向；只有材料 quote 与 summary 不一致、候选 role 不受 quote 支撑、factor sign 与 side 冲突、或 rule 明确要求复核时，才进入 `exclude` / `supporting_only` / 复核队列。
- 对 `team_building` 因子化，`talent_quality_factor` 使用人物画像中已有 `talent_grade` 映射，不临场定级；`role_complementarity_factor` 和 `long_term_stability_factor` 是同一目标团队级因子，同一目标内所有 score 行必须使用一致 label。生成 team_building 任务时优先让同一目标进入同一 batch，避免团队级因子拆批漂移。
- 记录耗时时只使用 `codex-win timer`、`codex-win run --log` 或 `results.jsonl` / `summary.json` 中的实测 `duration_sec`、usage；不得估算 per-person、per-batch 或 total timing。
- `retrieval_v2_candidate_source_refiner.py` 是 retrieval_v2 候选缺口补源层，从本轮 candidates 的 `objects_without_slices` / `source_missing` / `object_claim_undercoverage` / `alias_missing` 对象生成对象级 Wikisource 检索并合并新的 `source_documents`；它不读旧结果、不判读、不写库。
- `retrieval_v2_judge_shards.py` 是 retrieval_v2 judge 分片和聚合纯函数层，只切分本轮 candidates、构造 shard prompt、重写聚合 claim/passages/bindings ID；它不调用 Codex、不联网、不读写数据库。
- `retrieval_v2_candidate_prompt.py` 是 retrieval_v2 judge prompt 构造层，把本轮 candidates 和判读预算契约转成 Codex judge prompt；它不抓源、不判读、不写库。
- `retrieval_v2_alias_refiner.py` 是 retrieval_v2 覆盖缺口到别名补抓的调度层工具，从本轮 task / candidates / judge result 生成 alias patch、patched task 和可选 CLI alias-refiner prompt；它不联网、不写库、不读旧结果、不抽取事实，只有非机械称谓判断才交给 Codex CLI 子进程。
- `retrieval_v2_source_candidates.py` 是 retrieval_v2 抓包判读前的候选片段 builder，必须遵守 retrieval_v2 clean 抓包流程；它只负责抓取/缓存源页、按别名和 rule 关键词切片并生成瘦身 Codex prompt，记录 fetch errors 和 coverage gaps；它不读旧判读结果、不写库、不替代 source pack validator。
- `retrieval_v2_source_document_policy.py` 是 retrieval_v2 source document 门禁层，按目标 source strategy、史源 root 和总称实录目标 metadata 判断某个源页是否可进入候选切片；它不抓取、不判读、不写库。
- `retrieval_v2_quality_gate.py` 是 retrieval_v2 run 质量对照入口，用旧基准 run 和候选 run 的对象覆盖、claim 数、primary binding 数、无切片对象和状态做离线验收；它只读本地 run 目录，不联网、不读数据库、不替代人工抽样原文。
- `retrieval_v2_calibration_report.py` 是 retrieval_v2 调校 run 成本与质量汇总入口，聚合 summary、run_events、claim cache 命中、quality gate 和 alerts；它只读本地 run/cache，不联网、不写库、不调用 Codex。
- `retrieval_v2_prompt_governance.py` 是 retrieval_v2 prompt 预算和 prompt debt 快照入口，从本地 run_root、candidate JSON 或内置 debt 模板生成只读报告；它不调用 Codex、不联网、不写数据库、不替代质量验收。
- `retrieval_v2_recall_term_sampler.py` 是 retrieval_v2 召回词采样治理入口，从本地 candidates.final.json / run_root 的 candidate_slices 统计机制词、条件词、案例词和拒收词；它不联网、不调用 Codex、不写数据库、不直接修改长期 discovery profile。
- `retrieval_v2_recall_feedback.py` 是 retrieval_v2 消费反馈到召回 overlay 建议的只读汇总入口，从消费端 JSONL 统计 accepted/rejected/supporting_only 等状态和拒收原因；它不写 profile、不改 prompt、不写数据库，输出只用于下一轮 A/B 和人工 review。
- `retrieval_v2_source_gap_feedback.py` 是 retrieval_v2 消费端 `source_missing` / `object_claim_undercoverage` refinement 反馈到对象补源 refiner 的 shadow 桥接入口；它只读取 feedback JSONL 和本轮 task，生成 refined task、可选 candidates / focused prompt 和报告，不写 profile、不改 prompt、不写数据库。
- `retrieval_v2_calibration_package.py` 是 retrieval_v2 调校包入口，只跑对象源缓存 overlay、candidate-only 切片和对象政治叙事 sufficiency/claim budget 审计，输出画像候选信号；它不调用 Codex judge、不生成消费包、不写数据库、不替代正式人物画像裁量。
- `retrieval_v2_claim_cache.py` 是 retrieval_v2 claim-only 抽取后的最小 claim 管理闭环入口；`retrieval_v2_claim_cache_pg.py` 只把 filesystem claim cache 幂等写入 `claim_cache` / `claim_source_slices` / `claim_evidence` 并做库存审计，默认 DB-backed dry-run，显式 `--execute` 才写库；二者都不写正式 binding、不触发 factorization 或 scorer。
- `retrieval_v2_claim_extraction_worker.py` 是抓包侧 claim-only 抽取 worker，消费 `claim_extraction_jobs` 中的 uncovered candidates，显式 `once --execute` 才调用 Codex；它只产出 mini clean run 并回填 claim cache，不写消费端 binding、factorization 或 scorer。
- `retrieval_v2_object_source_cache.py` 是 retrieval_v2 对象级离线史源缓存入口，从当前对象表、历史 clean run 或显式 seed JSONL 生成人物源缓存、mention slice、coverage summary、agent review 占位队列和 PG schema 草案；第一版不调用 Codex、不写数据库、不替代抓包 judge 或消费端裁量。
- `retrieval_v2_object_source_cache_worker.py` 是抓包侧对象源缓存队列 worker，消费 `object_source_cache_jobs` 并执行 `build-shards` / `review-audit`；`claim-plan` 只把对象源缓存转成 claim-only candidates 并可选写入 `claim_extraction_jobs`，不调用 Codex、不导入 claim、不写对象池、不触发消费端或评分。
- `retrieval_v2_i5b_shadow_report.py` 是 I5B-wide shadow pilot 的只读检测报告入口，从本轮 `summary.json`、`run_events.jsonl`、candidate 和 judge 产物汇总耗时、usage、secondary candidate、claim/passage 风险、重复风险和处置性 negative 风险；它不写数据库、不改变包体、不替代人工抽样回源。
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
- `scoring_rule_table_sync.py` 是通用计分规则文档同步入口；负责按 item/rule/factor Markdown 格式抽取因子取值和总分权重，检查 retrieval_v2 规则表漂移，并为 `item_rule_score_weights` 生成可审阅 upsert SQL。未来其他分项复用该入口，不再复制 I5B 专用脚本。
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
