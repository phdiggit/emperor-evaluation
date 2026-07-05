# retrieval_v2 clean 抓包流程

本文约束 retrieval_v2 的 clean 抓包、候选片段、Codex 判读和缺口补抓流程。它是运行流程文档，不定义评分语义，不替代 `eval_rules`、`eval_rule_material_policies`、`fact_relation_predicate_options` 等规则表。

## 目标

retrieval_v2 的抓包产物必须由皇帝名单和规则契约驱动，最终交付可被对象池和证据簇消费的材料事实单元。主控只负责看控制面板、验收报告和少量异常，不手工补写事实。

一个抓到的 claim 可以服务多个 rule，但必须拆成独立的 `claim_rule_bindings`。同一原文可以同时给 primary rule 和 secondary rule 提供线索，不能因为本轮任务只测试一个 rule 就丢弃可复用事实。

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
- `revoked_or_failed_delegate`：撤权、误任、干预下属决策、亲信失职和授权后果失败。

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

## 验收口径

一个 retrieval_v2 source pack 至少满足以下条件才可进入对象池导入候选：

- clean 输入边界无违规。
- 核心 rule 的 `coverage_matrix` 已完成，或缺口已进入可追踪补抓队列。
- claims 都有可定位 source passage。
- primary binding 命中规则表中的材料策略或谓词选项。
- secondary binding candidate 不改变主 rule 判读，但保留给后续跨 rule 消费。
- `mixed` claim 已拆分，或保留为 `needs_review` 且不进入自动导入。
- `summary.json` 中 `judge_anomaly_block_count=0`；warning 必须进入抽样或补判队列，不能静默丢弃。
- `coverage_gaps` 可被机器转换为 `coverage_gap_events`。

主控验收只看 source pack manifest、coverage report、gap queue 和抽样原文。主控不在验收阶段手工补写对象事实。
