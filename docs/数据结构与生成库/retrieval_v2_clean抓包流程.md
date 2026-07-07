# retrieval_v2 clean 抓包流程

本文约束 retrieval_v2 的 clean 抓包、候选片段、Codex 判读和缺口补抓流程。它是运行流程文档，不定义评分语义，不替代 `eval_rules`、`eval_rule_material_policies`、`fact_relation_predicate_options` 等规则表。

## 目标

retrieval_v2 的抓包产物必须由皇帝名单和规则契约驱动，最终交付可被对象池和证据簇消费的材料事实单元。主控只负责看控制面板、验收报告和少量异常，不手工补写事实。

一个抓到的 claim 可以服务多个 rule，但必须拆成独立的 `claim_rule_bindings`。同一原文可以同时给 primary rule 和 secondary rule 提供线索，不能因为本轮任务只测试一个 rule 就丢弃可复用事实。

`secondary_binding_candidates` 必须作为长期 `claim_rule_binding_candidates` 候选池保留。当前只有 I5B / delegation 可消费时，候选只记录来源 item / rule、候选 rule、理由和置信度，不进入本轮计分；未来其他 item / rule contract 上线后，再由候选解析工具把同一 claim 追加为新的正式 rule binding，不能依赖人工记忆回翻旧包。

新抓包优先由 judge worker 在读史料上下文时输出 `secondary_binding_candidates`：抓包端负责宽抓宽标，顺手记录任人信任、团队、发现人才、容才、反亲私等正式候选，以及权力控制、政治品格、认知纠错、关键决策、军事边疆结果、历史负债等 future hint；消费端负责硬过滤、入库和窄入分，不为普通候选重新起智能体读史料。

`personnel_political_wide` 是 `i5b_item_wide_shadow` 的语义升级版：它仍复用 `rule_code="i5b_item_wide"` 的包外壳，避免新表和正式入分链改造，但在 task、candidate payload 和 summary 中额外写入 `capture_profile="personnel_political_wide"`、`fact_schema="political_action_v1"`、`candidate_route_table_version="personnel_political_v0_1"`。它覆盖 I5B 当前 formal candidates，并给 I5C / I5D / I5E / I6 / I3 / I7 留 future hints；`primary_bindings` 必须为空，所有候选归属都进入 `secondary_binding_candidates`，由消费端窄验晋升或停留为 future hint。

I5B-wide 抓包只能先做 shadow pilot，不能直接全量替代 single-rule clean runner。启用 `retrieval_v2_clean_runner.py --i5b-wide-shadow-pilot` 时，runner 会在 task、candidate payload 和 summary 写入 `capture_mode="i5b_wide_shadow"`、`formal_consumption_source=false`，用于在既有单 rule 任务外壳上评估宽标候选。启用 `--i5b-item-wide-shadow-pilot` 时，runner 会写入 `capture_mode="i5b_item_wide_shadow"`，把 `rule_code` 改为 `i5b_item_wide`，并要求 judge 输出 I5B item-wide material pool。启用 `--personnel-political-wide-shadow-pilot` 时，runner 会写入 `capture_mode="personnel_political_wide_shadow"`，继续复用 `i5b_item_wide` 包外壳，但强制 judge 输出 `political_action_v1` 事实骨架和跨项候选路由。所有 shadow run 都必须使用独立 `run_root`，不直接进入正式消费。正式全量 I5B-wide 等消费端完成 `appointment_trust` / `team_building` 晋升、factorization 和 scorer 闭环后再开启。

`--i5b-item-wide-shadow-pilot` 只保证包形态和判读 prompt 是 item-wide；如果输入仍来自旧 `delegation` task 文件，source/object discovery 仍继承原任务的发现边界，不能宣称已经覆盖整个 I5B。真正的 item-wide 覆盖必须由 item-wide taskgen / discovery profile 生成对象、史源和查询计划，再交给同一 shadow 判读链路验收。

I5B-wide / personnel-political-wide shadow 的 claim 应优先沉淀事实结构层，而不是 rule 专属因子预判。judge 可在每条 claim 中补 `fact_payload`、`evidence_spans` 和 `claim_completeness`：`fact_payload.fact_schema` 固定为 `political_action_v1`，并记录 `actor`、`object`、`action_type`、`event_scope`、`office_or_domain`、`outcome`、`cost_or_damage`、`time_context`、`source_span_refs`、`confidence`、`completeness`；`evidence_spans` 用 `action / object / outcome / reason / institution / context` 短原文 span 指向 `source_slice_ref`，第一版不要求模型给字符 offset；`claim_completeness` 只标 `has_action_span`、`has_object_span`、`has_outcome_span`、`outcome_same_event_chain`、`needs_source_extension`。这些字段只帮助消费端少读全文、少起子进程，不等于最终 factor label、score、supporting/exclude 或人物画像判断。

`personnel_political_v0_1` 候选路由表只定义“哪些事实值得保存、可能喂给谁”，不定义其他项的完整评分公式。`secondary_binding_candidates` 必须允许三种状态：`current_rule_candidate` 表示当前已有 rule 可被消费端窄验；`future_rule_hint` 表示未来评分项候选，不进入 factorization；`context_only` / `rejected` 表示已审但只作上下文或不再消费。第一版 lane 如下：I5B `delegation` / `appointment_trust` / `team_building` / `talent_discovery` / `tolerate_talent` / `anti_nepotism` 为 current；I5C `power_control`、I5D `political_character`、I5E `cognition_learning`、I6 `key_decision`、I3 `military_frontier_result`、I7 `historical_debt` 为 future。每个候选至少写 `candidate_item_code`、`candidate_lane`、`hint_status`、`direction`、`required_facts_present` 和来源 span 线索；入库时这些字段提升到 `claim_rule_binding_candidates` 同名列，原始 judge 输出仍保留在 `candidate_payload`。

I5B-wide 中的 `delegation` 候选必须显式区分自动入分候选和复核/支撑候选。只有同一材料同时证明授权/任命/权责配置、具名被授权者、具体任务或职责、同链条履职结果四项时，judge 才能在 `candidate_payload` 写 `scoring_candidate=true` 且 `usable_for_scoring_cluster=true`，并完整写出 `delegation_chain.has_authorization_or_office`、`has_named_delegate`、`has_task_or_responsibility`、`has_same_chain_outcome` 四个布尔值。任一项不满足时，可以保留 `rule_code="delegation"` 候选，但必须写 `scoring_candidate=false` 或 `usable_for_scoring_cluster=false`，留给 review/supporting。`candidate_payload.candidate_role` 必须直接使用消费侧 `object_role`：`delegated_actor`、`authority_recipient`、`authority_revoked_target`、`misdelegated_actor`；细分领域放 `delegation_domain=military|civil|fiscal|frontier|strategic|institutional`。三杰总评、单纯采纳计策、处置/诱执/撤权结局、人物画像材料不得标成可自动入分的 `delegation` candidate。

同一对象同时存在“封王/任官/总评”和“给兵、给金、遣使、命将、授权任务并有战果或治理结果”时，`delegation` 抓包优先抽取后者；前者通常只作 `appointment_trust`、`team_building` 或 `delegation` review/supporting。如果每对象 claim 预算不足，先丢弃较弱的封王/任官 review claim，也不要丢弃给兵/给金/遣使/命将后的同链条收益 claim；说降或归附后分兵、给兵、与俱收兵、会战、破敌、定地，属于高优先级 `delegation` 正向链。后续反叛、被诛、被废等政治风险不能挤掉同对象更早的正向授权收益链，二者必须拆成不同 claim。若同一片段中多个具名被授权者共同承担同一任务并共享结果，不能只把其他对象埋在某一个人的 `claim_summary` 中；对可作为消费对象的具名 delegate 应分别输出原子 claim。若因对象种子、切片或预算不足无法拆出某个具名对象，必须写 `coverage_gaps`，`object_name` 填未拆对象，诊断说明其被埋在共同任务链中，建议补对象/补源后重判。

shadow pilot 跑完先用 `scripts/dev/retrieval_v2_i5b_shadow_report.py --run-root <run_root>` 生成只读检测报告。主控优先看 `i5b_shadow_report.json` / `.md` 中的耗时、usage、formal / future secondary candidate 数、claim/passage 引用风险、事实骨架覆盖率、span 原文匹配风险、重复 claim 风险、处置性 negative 风险、judge anomaly 和 coverage gap；有 block 或明显 warning 时先调 prompt / 并发 / 补源策略，不把 shadow run 写入正式消费队列。

shadow pilot 试吃可以走完整消费链路，但 source pack 必须以 `draft` 写入，避免在 `accepted-packs` scope 下覆盖同 target / contract 的正式 single-rule 包。推荐顺序是：`retrieval_v2_intake_manifest.py build --emperor <目标>`、`retrieval_v2_intake_rows.py build`、`retrieval_v2_review_worklists.py build`、`retrieval_v2_import_executor.py apply --source-pack-status draft --execute`；随后对象消费必须带 `retrieval_v2_object_consumer.py apply --source-pack-code <shadow_pack_code>` 限定本包范围。完成对象链接后，`retrieval_v2_candidate_promoter.py --source-rule-code i5b_item_wide --scope active-targets --emperor <目标>` 只晋升 formal candidate；future hint、未上线 contract 和不能确定解析的候选继续停留在候选池，不进入因子化或 scorer。

shadow pilot 的后半链路也必须显式限定单包：`retrieval_v2_factorization_worklists.py worklist --source-pack-code <shadow_pack_code>` 生成因子化任务，验收 patch 后再由 `retrieval_v2_factorization_consumer.py apply-patch` 写入因子判断。`retrieval_v2_rule_scorer.py apply --source-pack-code <shadow_pack_code>` 只用于只读算分报告；显式 source pack 默认禁止 `--execute`，避免 draft shadow、历史包或局部包把正式 `target_rule_score_clusters` 覆盖掉。只有确认要把该包升级为正式 accepted 消费源，并处理好正式聚合表写入策略后，才允许讨论写库算分。

`team_building` 是团队聚合公式，不按普通材料逐条乘法入分。消费端 worklist 会把人物画像中的 `talent_grade` 映射为 `talent_quality_factor`，子进程只判断材料是否作为团队成员 `score/supporting_only/exclude`，并选择同一目标团队级的 `role_complementarity_factor` 与 `long_term_stability_factor`。同一目标的 `score` 行必须使用一致团队级因子；生成 shadow 试吃任务时优先用足够大的 `--batch-size` 让同一目标 team_building 材料进入同一 batch。

当前 shadow pilot 的小批量起步命令可先加 `--taskgen-object-source-pages-per-object 1`。刘邦、曹操、李世民、赵匡胤试跑显示该参数能减少对象级补源页数和 judge 输入规模，claim/passage 风险和处置性 negative 风险可保持为 0；但它可能暴露别名或对象源页缺口，例如李世民轮次中李君羨、王玄策仍出现 `alias_missing`。处置性材料不足以证明任内损害时，judge 不应写 `negative_undercoverage`，只能写 `true_lack` 或交消费侧画像复核；`negative_undercoverage` 只用于已有治理损害、军政失败、人才结构损害或授权链条失控线索但证据闭环不足的可执行补抓缺口。`--taskgen-object-source-pages-per-object 1` 只能作为 shadow 起步档，正式默认值需等更多目标验证后再改。

已入库 accepted 包可以用 `scripts/dev/retrieval_v2_cross_rule_router.py` 做 deterministic backfill：默认扫描 `I5B / delegation` claims，按任用信任、团队、荐举、容才/处置边界、亲私朋党、权力控制和政治品格等材料线索补写 `claim_rule_binding_candidates`。正式候选仅限当前合同内 rule，例如 `appointment_trust`、`team_building`、`talent_discovery`、`tolerate_talent`、`anti_nepotism`；`power_control`、`political_character` 等未开 rule 只能写为 `hint_status="future_rule_hint"`。消费端必须同时要求 `candidate_contract_rule_id is not null` 且 `hint_status in ('formal_candidate', 'current_rule_candidate')`，才能进入当前 rule 消费；旧包中的 `candidate_payload.hint_status` 只作兼容回填和审计线索。

消费端用 `scripts/dev/retrieval_v2_candidate_promoter.py` 把可确定解析的 formal candidate 晋升为正式 `claim_rule_bindings`，并补齐目标 scoring role 对应的 `material_object_links`。该工具默认 dry-run，显式 `--execute` 才写库；future hint、缺少 contract rule、已解析候选和仅凭伏诛/被废/撤权等处置结果的候选不得自动晋升，只能进入后续复核或目标 rule 自己的判读。

消费侧新表迁移必须从建表阶段就带完整注释：所有表和字段都要写清楚语义、来源和幂等关系。带说明性质的字段值使用中文，且只写具体判断、来源、冲突原因、处置意见等信息熵高的文本；模板式说明、字段名复述和低信息套话宁可留空。字段名可保持英文稳定命名，但不要新增泛化 `note` 字段承载多种含义。取值有限的字段优先使用 PostgreSQL enum type，不用裸 `text` 承载状态机、方向、名称类型和队列状态。

正式流水线入口是 `scripts/dev/retrieval_v2_clean_runner.py`。它把任务生成、候选片段、机械别名补抓、候选重跑、Codex 判读和 summary 固化为同一条命令；主控默认只看 `summary.json`、coverage gaps 和少量异常文件。

`--emperor` 目标模式默认采用流式调度：某个目标的 taskgen 一完成，就立即进入候选片段和判读阶段，不等待同批所有目标的 taskgen 全部结束。需要和旧批处理口径对照时，可显式传 `--no-stream-taskgen`。

冷启动目标默认逐人并行 taskgen，`--taskgen-batch-size` 默认值为 1，以墙钟时间优先。需要节省 token / 额度时可调大该值，让同 rule 多个皇帝共享一次规则契约、材料策略、谓词选项和覆盖矩阵上下文；每个皇帝仍必须单独输出 `target_profile`、`object_seeds`、`source_documents` 和 `search_plan`，runner 会把 discovery 逐目标 merge 回各自 task skeleton。

耗时优化必须先过质量闸门。对同一组目标和同一 rule，候选 run 必须用 `scripts/dev/retrieval_v2_quality_gate.py` 对照已接受的基准 run；默认门槛是：不丢基准对象、可计分对象方向覆盖不回退、claims 不低于基准 90%、无切片对象为 block。primary binding 原始数量下降只作为 warning，避免把重复绑定数误当成质量。gap 增加先作为 warning，除非同时伴随对象覆盖、可计分方向覆盖或状态回退。当前 delegation 四人实验中，`runner_full_clean_4p_maxworkers4_20260705` 已通过 `delegation_four_clean_20260705_020212` 对照，可作为继续优化的质量基线；`source_strategy_probe_20260705_4p_judge_from_tasks` 未通过，只能作为实验数据，不得升为默认生产链路。

高速首轮和最终收货要分层。`runner_full_clean_4p_shard4_workers4_20260705` 的 4 人 clean 重测耗时约 106 秒，相比 `runner_full_clean_4p_maxworkers4_20260705` 的约 260 秒明显更快，但它相对质量基线仍有可计分负向方向回退，并由 summary 自审抓出 `mixed_claim_not_split` block。因此 `--judge-shard-size 4 --judge-shard-workers 4 --max-workers 4` 可以作为高速首轮候选配置；只有当 `summary.json` 中 `judge_anomaly_block_count=0`，且质量门禁没有 block，才可直接进入对象池。否则把 `judge_anomalies` 和 `coverage_gaps` 转为补判/补抓队列，不整批重跑。

```powershell
python scripts/dev/retrieval_v2_quality_gate.py `
  --baseline-run-root tmp/retrieval_v2_clean_runs/delegation_four_clean_20260705_020212 `
  --candidate-run-root tmp/retrieval_v2_clean_runs/runner_full_clean_4p_maxworkers4_20260705 `
  --format markdown `
  --fail-on-block
```

需要压缩 taskgen 墙钟时间时，可启用 `--taskgen-presearch`。该模式由脚本先按皇帝名、可选庙号/谥号/朝代和 rule 关键词检索 Wikisource，生成本轮 `source_documents` 与 `search_plan.presearch_hits`，再交给 Codex taskgen 补对象、别名和缺口；默认会关闭 Codex taskgen web search，避免重复搜索。无 search 的 presearch 模式下，runner 会保留脚本预搜索的 `source_documents`，并忽略 Codex 返回的新 source document，防止模型补出泛页、空页或未验证 URL；随后脚本再按 taskgen 新发现对象名做一轮对象级 Wikisource source presearch，默认每对象取 2 个页面候选，把具体对象页/卷页合并进 `source_documents`。第一轮候选切片后，如果仍有 `objects_without_slices`，runner 会默认在 presearch 模式下追加 1 轮候选缺口补源，按缺口对象名和当前 task 已有史源书名继续检索并重跑候选。若要对照质量，可显式加 `--taskgen-presearch-with-codex-search`，或用 `--no-taskgen-object-source-presearch` 关闭对象级补源；候选缺口补源可用 `--candidate-source-refine-rounds 0` 关闭。presearch 只读 `public.emps` 可选元数据、taskgen 新发现对象名、本轮 candidates 和公开搜索结果，不读旧 source pack、旧对象池或旧判读结果；启用 presearch 时为了墙钟时间优先，runner 对该目标使用逐人流式 taskgen，不进入 batch taskgen。

新目标必须先进入 retrieval_v2 控制面。`retrieval_v2_clean_runner.py --emperor ...` 只消费已存在的 `retrieval_targets` / `retrieval_intents`；如果报 `missing retrieval_v2 targets`，先用 `retrieval_v2_bootstrap.py --copy-rule-contract --seed-target <皇帝名>` 幂等同步规则契约并播种目标，再重跑 clean runner。该操作只写 retrieval_v2 控制面表，不写对象池、证据簇或正式评分结果。

每轮运行必须写 `run_events.jsonl`。该文件记录 `taskgen_start`、`taskgen_done`、`taskgen_object_source_presearch_start`、`taskgen_object_source_presearch_done`、`target_start`、`candidate_done`、`candidate_source_refine_start`、`candidate_source_refine_done`、`judge_done`、`target_done`、`pipeline_done` 等阶段事件；主控和控制面板优先读它判断慢尾、失败点和可提前收货目标。需要命令行实时显示时传 `--progress`，进度只写 stderr，stdout 仍保留最终 summary JSON。

clean Codex 子进程默认使用 `exec --ephemeral --ignore-user-config --ignore-rules`。`search=false` 时 runner 还会显式 `--disable standalone_web_search`、`--disable browser_use`、`--disable browser_use_external`，保证不会被用户全局配置、插件默认 prompt 或项目规则意外打开 web search / memory / 额外上下文；需要联网只能由 runner 显式传 `--search`。

## clean 输入边界

允许读取：

- 当前目标皇帝名单和目标 rule。
- `public.emps`、`public.eval_items`、`public.eval_rules`、`public.eval_rule_material_policies`、`public.fact_relation_predicate_options` 的当前表快照。
- retrieval_v2 当前运行自己的 `retrieval_targets`、`target_aliases`、`rule_contracts`、`retrieval_intents`、`source_documents`、`source_passages`、`coverage_gap_events`。
- 本轮运行目录内生成的缓存、候选片段、判读 JSON 和缺口报告。
- 共享原始史源页缓存，例如 `tmp/retrieval_v2_source_cache`；该缓存只能保存按公开 URL / Wikisource title 抓取的源页文本和抓取元数据，不得混入旧判读、旧对象 payload 或旧 source pack 摘录。
- 公开史源和公开检索结果。

禁止读取：

- 旧 `source-packs`、旧 query profile、旧对象 payload、旧对象池明细、旧 `source_excerpt_pool` 结果。
- 旧评分结果、旧计算明细、旧人工补写材料和上一次 Codex 对同一任务的回答。
- 评分规则 Markdown 正文。运行时只能读规则表、材料策略表和谓词表。
- Codex 本地 memory、插件记忆或非本轮任务目录中的临时总结。

## 阶段契约

1. 规则契约快照
   - `retrieval_v2_bootstrap.py` 从源库复制规则、材料策略和谓词契约。
   - 每个目标皇帝按每个核心 rule 生成 `target_rule_requirements` 和 `retrieval_intents`。
   - `selection_priority` 越小越优先；特殊材料筛选口径必须在表中表达，不能靠读 Markdown 补充。

2. 任务生成
   - `retrieval_v2_task_skeleton.py` 先从目标皇帝、目标 rule、规则契约、材料策略和谓词选项生成稳定 task skeleton。
   - task skeleton 必须包含 `source_strategy`，由规则和目标 metadata 生成，至少说明 `source_hints`、核心源页类型和对象发现族；Codex taskgen 只能按该策略补对象和史源，不得把策略降级或改写。
   - 子进程读取 task skeleton、规则契约和公开史源，只补 `object_seeds`、`source_documents`、可选 `target_profile` 别名、规则查询词、`search_plan`、`generation_notes`。
   - `target_code`、`rule_code`、`coverage_matrix`、`secondary_rule_candidates` 等稳定字段由脚本保护，Codex discovery 不得覆盖。
   - 任务生成阶段可以联网检索，但必须使用独立运行目录和独立 Codex 会话，不得复用旧同题结果。
   - 可选 `--taskgen-presearch` 只负责把公开 Wikisource 搜索命中预填到 skeleton；Codex taskgen 仍必须输出对象种子和缺口判断。若未开启 `--taskgen-presearch-with-codex-search`，Codex taskgen 不再自行联网搜索。
   - 脚本 presearch 和对象级补源必须按查询史源 hint 过滤 Wikisource title root：查 `舊唐書` 只能收 `舊唐書/...`，查 `漢書` 不能收 `後漢書/...`，查 `隋書` 不能收 `全隋文/...`。被过滤的搜索命中可留在 `search_plan.*hits` 并标记 `source_root_mismatch`，但不得进入 `source_documents`。
   - 正史或编年史的同源版本卷页可以进入，例如 `宋史(四庫全書本)/卷283` 可按 `宋史` root 处理；但 `宋史演義`、`宋史紀事本末`、文集和奏议等不同 root 仍不得冒充 `宋史`。
   - `明實錄`、`清實錄` 这类总称史源必须结合目标 metadata 收紧到对应实录 root；例如康熙目标不能把 `雍正朝實錄/...` 作为本轮材料，朱棣目标不能因 `明實錄` 泛称收进 `大明太祖高皇帝實錄/...`。
   - Wikisource root page 只能作为发现脚手架，`source_kind=wikisource_root_page` 不得进入候选片段和 judge prompt。搜索根页 snippet 中若出现对象名和卷号，可由脚本推导出具体 `史源/卷N` 页面；只有具体卷页才可作为 `wikisource_page` 抓取和切片。
   - 注疏、目录或索引类命中本身不得进入 `source_documents`。但如果其 snippet 明确包含允许史源 root、目标或对象名以及卷号，可以由脚本反推出 canonical 正源卷页，例如 `史記三家註` 摘要中的“卷六 秦始皇本紀第六”可派生 `史記/卷006`；进入候选的只能是派生后的正源卷页，不是注疏页本身。
   - `taskgen discovery produced invalid task: ['source_documents is empty']` 不是主控手工补材料的信号。先检查 `task.preseed.json`、`taskgen_last_message.json` 和 `search_plan.presearch_hits`：若有公开检索命中但全部被过滤，应修 source root / 卷页推导策略；若确无可用核心史源，再进入缺口队列。
   - 对象级补源默认按 `source_strategy.source_hints` 的前两个核心源系展开，例如唐代对象同时搜 `舊唐書` 和 `新唐書`；候选缺口补源使用同一套 source hint 上限。需要压缩时间时只能通过 CLI 参数调低上限，不得在代码中把高密度目标单独降标。
   - 正式运行由 `retrieval_v2_clean_runner.py` 调用 taskgen；也可传入已有 `--task` 只跑后续候选、补别名和判读阶段。
   - 已验收的 retrieval_v2 discovery profile 可以复用到同一目标和同一 rule，跳过 Codex taskgen；跨 rule 复用必须重新套当前 rule 的 task skeleton 和 coverage matrix。
   - `retrieval_v2_clean_runner.py --discovery-profile-root <dir>` 会扫描可用 profile，并在 taskgen 后把新 profile 写回该目录；主控不应逐人手工传 profile 文件。
   - 复用 profile 时，`summary.json` 中 `taskgen_mode=discovery_profile` 且 `taskgen_elapsed_seconds=0.0`；冷启动时为 `skeleton_discovery`，其耗时和 token 用量必须单独进入 summary。
   - 批量 taskgen 产物进入各人 summary 时使用 `taskgen_mode=batch_skeleton_discovery`，并保留 `batch_code`、`batch_size`、`batch_elapsed_seconds` 和均摊 token 用量；完整 batch prompt、events 和 last message 存在 `taskgen_batches/<batch_code>/`。
   - 前置公开检索产物进入各人 summary 时使用 `taskgen_mode=preseeded_skeleton_discovery`，并写 `task.preseed.json`；`summary.clean_policy.taskgen_presearch` 和 `taskgen_search_enabled` 用于区分压缩耗时测试与普通 cold taskgen。

3. 候选片段
   - `retrieval_v2_source_candidates.py` 只负责抓取、缓存、别名命中和片段切分。
   - 候选片段 builder 不写库，不读取旧判读结果，不替代 source pack validator。
   - 候选片段 builder 必须再次执行 source root 门禁；即使 Codex taskgen 直接给出错页，错页也只能进入 `skipped_source_documents`，不能进入 fetch、slice 或 judge。
   - `retrieval_v2_clean_runner.py` 默认使用共享原始史源页缓存；如需完全隔离可传 `--run-local-source-cache`。
   - 候选片段 builder 会对 strong / medium 别名做机械简繁、异体和常见职官字形展开，用于减少无意义 alias-refiner 轮次；这只是命中策略，不改变对象身份裁量。
   - 同对象、同文档、定位相邻或重叠的候选窗口应在进入 judge prompt 前合并；`stats.raw_candidate_slices` 保留压缩前数量，`stats.candidate_slices` 是实际交给判读的数量。
   - 抓取错误、限流、空页面和别名未检全都必须写进 `fetch_errors` 或 `coverage_gaps`，不得静默跳过。
   - runner 的 person summary 必须汇总 `fetch_error_count` 和 `fetch_errors`，方便补抓进程直接定位失败 source document。
   - `retrieval_v2_candidate_source_refiner.py` 消费本轮 candidates 中的 `objects_without_slices`、`source_missing` 和 `alias_missing` 对象名，按 task 已有史源书名生成对象级 Wikisource 搜索并合并新的 `source_documents`；补到新 source 后必须重跑候选片段，不能直接把搜索命中交给 judge。

4. Codex 判读
   - 判读子进程只看本轮 prompt、候选片段和结构化契约。
   - 判读阶段不联网，不读 memory，不读用户配置，不读项目规则，不读旧项目产物。
   - 高密度目标可由 `retrieval_v2_clean_runner.py --judge-shard-size <N> --judge-shard-workers <M>` 按对象分片判读；每个 shard 只处理自己的 `candidate_slices`，不得为 shard 外对象报缺口。
   - 对象分片按候选文本量做均衡，不按对象原始顺序硬切；高密度对象应优先被摊开，避免单个 shard 拖慢全局。
   - 分片 judge 的 claim、passage 和 binding 由 runner 聚合并重写 ID，避免不同子进程都输出 `CLM-001` / `PAS-001` 造成撞码。
   - 判读预算服务吞吐量，不改变评分语义：同一对象、同一谓词、同一方向、同一事实类型的多个切片必须合并为代表 claim；每个对象默认最多 2 个可消费 material claim，只有清晰正负拆分或授权/撤权/失败拆分时才超过。
   - 负向 `delegation` 必须看材料本身是否证明授权对象在任内造成具体治理损害、军政任务失败、人才结构损害或授权链条失控；`伏诛`、`被废`、`被杀`、`罢免`、`削权`、`撤权`、`下狱` 等处置结果不能单独构成可计分 negative claim / binding，应作为 neutral/context 或不可计分材料交给消费侧结合人物画像判断。
   - 输出必须包含 `claims`、`primary_bindings`、`secondary_binding_candidates`、`coverage`、`coverage_gaps`。
   - `direction=mixed` 不能直接消费，必须拆成至少一个授权事实和一个结果、撤权、失误或负面后果事实。
   - runner summary 会自动执行 judge anomaly 自审：`mixed` claim 若带可计分 binding 但没有负向拆分或缺口，记为 `mixed_claim_not_split` block；负向 claim 若不可计分且未进入负向缺口队列，记为 warning。

5. 缺口补抓
   - `needs_refinement` 不是主控待办，而是抓包链路的自动补抓信号。
   - 每个缺口事件必须有幂等键，重复缺口只更新状态和审计记录，不重复派发同一任务。
   - 候选阶段对象无切片时，先由 `retrieval_v2_candidate_source_refiner.py` 做对象级补源；补源轮数由 `--candidate-source-refine-rounds` 控制，默认在 `--taskgen-presearch` 模式下为 1。
   - `alias_missing` 先交给 `retrieval_v2_alias_refiner.py` 做机械简繁/异体别名补丁并重跑候选片段；只有弱别名噪声、封号、官职、字、称谓等需要史学判断的缺口，才生成 CLI alias-refiner prompt。
   - 如果候选片段已通过动态字形变体命中对象，则不再为了同一个机械变体强行增加一次 alias-refiner 轮次；需要持久化到 discovery profile 的 raw alias 由后续 profile 审计或显式 alias patch 处理。
   - `retrieval_v2_clean_runner.py` 默认在判读前处理候选阶段 `alias_missing`；判读后如果仍出现可机械修复的 `alias_missing`，继续 patch task 并重跑候选和判读，直到达到 `max_alias_refine_rounds`。
   - 补抓任务仍遵守 clean 输入边界。

## 规则覆盖矩阵

每个 rule 都应有覆盖矩阵。矩阵不替代计分规则，只描述本轮抓包必须覆盖哪些对象族、事实类型和正负方向。通用字段如下：

```json
{
  "rule_code": "delegation",
  "role_families": [
    {
      "family_code": "military_delegate",
      "target_min_claims": 2,
      "required_directions": ["positive", "negative"],
      "objects_checked": [],
      "gaps": []
    }
  ],
  "secondary_rule_hints": [
    {
      "rule_code": "team_building",
      "reason": "同一任用事实可能支撑团队建设成员和角色互补"
    }
  ]
}
```

矩阵必须进入任务生成产物和判读产物。后续控制面板只看矩阵状态判断是否需要补抓，不要求主控逐条阅读原文。

## delegation 覆盖要求

`delegation` 容易被武将授权案例占满，因此必须显式覆盖以下对象族：

- `military_delegate`：将领任命、方面军、战役指挥、边防和军政委任。
- `civil_delegate`：宰辅、尚书、地方行政、财政、屯田、法制、选官和后勤治理委任。
- `strategic_delegate`：谋臣、参谋、规划者、顾问式授权和关键决策采纳。
- `revoked_or_failed_delegate`：撤权、误任、干预下属决策、亲信失职和授权后果失败；处置性结局本身不等于负向授权，必须同时证明任内具体治理 / 人才结构损害。

如果 `civil_delegate` 或 `revoked_or_failed_delegate` 完全无 claim，不能直接判定为 ready。必须生成 `coverage_gap_events`，让后续补抓子进程按缺口继续找材料。

## 别名强度

别名机制服务两个目标：避免漏检，以及避免把同一对象重复导入对象表。

- `strong`：本名、字、稳定异名、常见正史写法。
- `medium`：在目标时代和上下文中高度指向该对象的官职、封爵或尊称。
- `weak`：谥号、爵号、泛称、容易重名的官号或只在后世语境稳定的称呼。

弱别名不能独立把片段排到高置信命中。弱别名命中必须有目标皇帝、时代、官职、同段人物或事件共同确认。发现弱别名噪声时，生成 `weak_alias_noise` 缺口，补强别名策略，而不是把噪声材料交给判读。

## 缺口到任务的映射

- `source_missing`：补充史源页、卷目或页面标题。
- `alias_missing`：补充 strong/medium 别名并重跑候选切片。
- `predicate_missing`：补充该谓词的查询词和事实类型。
- `civil_undercoverage`：扩大文官、行政、财政、法制、选官和后勤对象族。
- `negative_undercoverage`：扩大撤权、误任、失败、干预和负面后果对象族。
- `weak_alias_noise`：降低弱别名排序或要求上下文共现。
- `fetch_error`：重试、换源或人工标记短期不可达。
- `true_lack`：只有在 strong/medium 别名、核心史源和相关对象族都检索过后才允许使用。

## 控制面 gap handoff

消费进程通知抓包进程不得依赖聊天消息，正式通知源是 retrieval_v2 控制面队列。

两段机制：

1. 消费进程幂等写入 `retrieval_v2.coverage_gap_events`。幂等键按 `target_code + rule_code + source_pack_code + gap_type + family_code + object_name + predicate` 组成；clean 产物尚无 `source_pack_code` 时，交接工具必须从 `run_root + target_code + rule_code` 派生稳定 `RUN-...` fallback，不能留下空槽。首次插入事件状态写 `ready`；重复写入只刷新诊断和 payload，不得把 `queued`、`running`、`retry_wait`、`deferred`、`resolved`、`blocked` 或 `cancelled` 改回 `ready`。队列按处理面分流：`source_pack_refinement` 处理补源、补别名、fetch error、predicate / civil / negative undercoverage；`codex_review` 处理补判、mixed claim 拆分和 anomaly；`object_payload_or_source_review`、`material_classification_review`、`policy_block_review` 留给消费侧或人工复核。
2. 抓包调度器只轮询可执行 gap，并幂等转成 `retrieval_v2.jobs`。例如 `source_missing`、`alias_missing`、`predicate_missing` 和 `negative_undercoverage` 进入 `codex_source_pack_refine` 或 search/fetch/refine job；`mixed_claim_not_split` 进入 `codex_material_review`。clean runner 本身不常驻监听数据库。

短期没有常驻 worker 时，消费进程同时生成 `gap_handoff.jsonl` 或 `gap_handoff.md` 作为旁路交接视图；抓包主控下一轮用 `coverage_gap_events where status='ready' and queue='source_pack_refinement'` 认领。仓库工具：

```bash
python scripts/dev/retrieval_v2_gap_handoff.py emit \
  --summary tmp/retrieval_v2_clean_runs/<run_name>/summary.json \
  --output-jsonl tmp/retrieval_v2_clean_runs/<run_name>/gap_handoff.jsonl \
  --output-md tmp/retrieval_v2_clean_runs/<run_name>/gap_handoff.md

python scripts/dev/retrieval_v2_gap_handoff.py emit \
  --env-file .env --write-db \
  --summary tmp/retrieval_v2_clean_runs/<run_name>/summary.json

python scripts/dev/retrieval_v2_gap_handoff.py enqueue-jobs \
  --env-file .env --queue source_pack_refinement --limit 50

python scripts/dev/retrieval_v2_gap_worker.py plan \
  --events-jsonl tmp/retrieval_v2_clean_runs/<run_name>/gap_handoff.jsonl \
  --output tmp/retrieval_v2_clean_runs/<run_name>/gap_worker_plan.json

python scripts/dev/retrieval_v2_gap_worker.py run-plan \
  --plan tmp/retrieval_v2_clean_runs/<run_name>/gap_worker_plan.json
```

`retrieval_v2_gap_worker.py plan` 默认只生成 candidate-only clean runner 计划，同一 task 的多个 source-pack gap 会合并成一条命令；`codex_review` 只进入 material review 计划项，不调用 clean runner。只有显式执行 `run-plan --execute` 才会真正跑补抓命令；需要重判时在 plan 阶段使用 `--mode judge`。

## 验收口径

一个 retrieval_v2 source pack 至少满足以下条件才可进入对象池导入候选：

- clean 输入边界无违规。
- 核心 rule 的 `coverage_matrix` 已完成，或缺口已进入可追踪补抓队列。
- claims 都有可定位 source passage。
- `claim_summary` 必须被其 `source_passage_refs` 原文直接支撑；若 summary 与 passage 摘录明显错位，`retrieval_v2_import_plan.py` 会以 `claim_passage_mismatch` / `claim_passage_object_mismatch` 阻断导入，先回到补判或人工复核。
- 当 judge 只输出 `source_slice_refs` 而不显式输出 passages 时，抓包聚合器自动 materialize 的 `source_passages.quote/raw_text` 必须保留完整 candidate slice 文本，不得截断为 prompt 摘要长度。prompt 阶段可以瘦身，证据落库和消费端 quote-only 判读必须拿到完整原文片段，避免授权在前、战果在后时被截断。
- 对已经入库、但历史包因旧聚合逻辑只保留 120 字 passage 的 accepted 包，使用 `scripts/dev/retrieval_v2_passage_fulltext_backfill.py` 从包 artifact 的 `candidates.final.json` 回填完整 candidate slice 文本。该工具只在当前 `raw_text` 是完整 slice 前缀时更新 passage，不改 claim / binding；先 dry-run 核对 `planned_count`，再显式 `--execute` 写库。
- 对已入库的历史 accepted 包，使用 `scripts/dev/retrieval_v2_claim_passage_audit.py` 做只读审计；显式 `--execute` 后把疑似错位 claim 写入 `material_review_queue`，加 `--write-gap-events` 会同时写 `coverage_gap_events queue=codex_review` 交抓包侧补判。未清材料复核队列会阻断 candidate promoter 和 factorization worklist，避免错位 claim 继续自动入分。
- 消费侧 `scripts/dev/retrieval_v2_material_review_tasks.py` 只做窄复核：判断当前 `source_passages` 是否直接支撑 `claim_summary`，并把 `supported` / `unsupported` / `needs_context` 写回队列状态。它清理的是入分闸门，不等于修好了 accepted 包体。
- 抓包侧修包使用 `scripts/dev/retrieval_v2_claim_passage_repair.py`：从 `material_review_queue` 读取 `blocked` / `needs_review` 的错位 claim，补入同 accepted pack 的 `candidate_slices` 上下文，生成 `relink` / `rewrite` / `drop_claim` / `needs_source_refine` patch；显式 `apply-patch --execute` 后才重链 `claim_source_passages`、补 repair passage、改写 claim summary 或标记 claim 废弃。
- primary binding 命中规则表中的材料策略或谓词选项。
- secondary binding candidate 不改变主 rule 判读，但保留给后续跨 rule 消费。
- `mixed` claim 已拆分，或保留为 `needs_review` 且不进入自动导入。
- `summary.json` 中 `judge_anomaly_block_count=0`；warning 必须进入抽样或补判队列，不能静默丢弃。
- `coverage_gaps` 可被机器转换为 `coverage_gap_events`。

主控验收只看 source pack manifest、coverage report、gap queue 和抽样原文。主控不在验收阶段手工补写对象事实。
