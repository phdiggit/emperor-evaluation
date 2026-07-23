# 皇帝综合评价体系 V4

本仓库只保留当前有效的评分规则、证据契约、运行实现和唯一 canonical 结果。Git 是唯一历史载体；工作树不保存阶段报告、失败运行、重复结果或旧状态镜像。

## 当前状态

- V3 已退役；V4 是唯一活动实现。
- 战役登记、治理登记、人才等级和政治风险是跨评分项公共基础，统一遵循 [`docs/证据规则/公共成果登记与人物画像规则.md`](docs/证据规则/公共成果登记与人物画像规则.md)；I5B 只消费公共当前值并投影本项因子。多会话并行按 [`docs/证据规则/单皇帝主控会话工作流.md`](docs/证据规则/单皇帝主控会话工作流.md) 认领和隔离，一个会话只主控一个皇帝。运行时子模型只并发处理首次大批量中性事实或本传 Assertion 草案；公共成果、窗口、人物档位、政治风险、I5B 和 Gold 由连续主会话裁决，成果阶段默认生成 worklist 并等待 `--outcome-review`，不再以子模型重试作为主路径。
- 第五项 B 的当前链路已统一为“三路中性材料 → HistoricalEpisode / HistoricalOutcomeCluster → 人物画像 → RuleEvidenceUnit → 因子语义确定性映射 → strongest-N 材料预算 → 加权净信号”。
- 皇帝链路的史源扫描必须以编年事件为单位：皇帝配置的《资治通鉴》卷次范围先做连续事件分段，姓名和别名只能绑定人物，不能决定主干事件单元是否被读取。同一连续篇章中出现的其他在位皇帝和评价主体一并沉淀为共享中性材料；“篇章在位者”与“本次评价入口”分离，同一事实可在李渊链投影为李世民臣子画像，也可在李世民链投影为其登基前生涯，不得重复抽取。模型前确定性判空无行动、命令、实施、制度、人事、军事或可观察结果信号的单元；事件单元内全部事实触发句均被确定性军事行动引文覆盖时，直接接纳中性行动事实并跳过通用模型，胜败和事件边界歧义保留到后置投影，不能反向阻止中性事实入流；混合内容仍须模型补足。通鉴中性事实通过合同后，才用其人物、纪年、地点和语义锚点定向回源本朝正史的本纪与列传，未形成事实的主干片段不得预先放大为唐书召回任务。《贞观政要》《通典》等专题材料由朝代级政书链一次扫描并冻结，皇帝链只读取匹配的当前中性材料补足治理细节。正史和专题史料不得与《通鉴》并列做全书首轮模型扫描，也不得按姓名窗口重新扫描同一事件。皇帝级总墙钟只作耗时观测；主控入口按史源清单、中性材料、成果投射、当前画像与 I5B 四个质量阶段监督执行，每阶段保存输入指纹、生产者合同、质量结果和临时产物 hash。未发布任务只有指纹完全一致才能跨 release 复用，发布后清理阶段缓存。
- 中性抽取模型阶段按相近 Prompt 体量记录成功子进程耗时；仍在运行的子进程一旦超过可比成功调用中位耗时的两倍，立即终止完整进程树并熔断当前批次。传输或超时异常先上抛给阶段监督器；监督器保留已完成片段，用新 runner 按批准批宽缩小后只恢复未完成任务，不在原 runner 内继续等待，也不重跑已验收上游阶段。内容或 Schema 校验失败只允许一次严格引文定向修订，之后交主会话；成果登记默认不启动子模型。
- 唯一当前三路输入指纹为 `f6ae0cb3ff59b3ee1cf4e5f24942cf70575513f649c9cb060f294a862297d878`，包含皇帝篇章236条、臣子列传588条、朝代文治135条。
- 李世民当前 I5B Gold 影子结果：75个 Episode、43个 REU、48条统一成果簇，本纪补证链接12条、治理结果支持7条，加权净信号 `17.993766`。
- 刘邦当前 I5B Gold 影子结果：38个 Episode、22个 REU、26条统一成果簇，本纪补证链接3条、治理结果支持2条；周勃“屠马邑”按毁灭性攻城校准为 `serious`、有断句争议的“屠浑都”不累计严重度后，加权净信号为 `8.188958`。
- 同一事件的正负 REU 共用中性 Episode；皇帝本纪只作明确 lineage 补证，文治结果由结果质量和团队人物交集确定性选择，同一皇帝决策按结算事件键只结算一次。
- 李世民18名、刘邦13名人物画像已进入总登记；其中当前团队预算成员的本传、窗口政治风险、三路 lineage 和统一成果簇覆盖完整，未进入团队建设预算的候选人仍保留画像并显式展示开放缺口。人才等级由成果角色、结果规模与规则路径确定性重算。戴胄因主导并实际运行国家级义仓系统评为 `top`；该专业能力判断不抹去政策的整体混合结果，义仓事项因后续挪用与负担不进入皇帝团队正向结果池。
- 每位皇帝只保留一个 `source-pack.json` 和一组 canonical `result.json` / `result.md`；`result.md` 固定为五项规则的计分详情表，未计分材料显示因子取值。
- 正式45分、档位和排名仍关闭；当前结果只表示五条 rule 的材料预算后净信号。
- 当前实现默认 `offline-first`、`report-only`、`shadow-first`；模型调用、正式评分写入和排名写入均为0。
- 人才 `historic` 当前采用 V11 分领域等价路径，军事与治理分别执行各自门槛，不再互相类比。军事先按主帅/主将责任过滤，再用 `A=1、S-=2、S=3、S+=4` 的战略权重表达“巅峰双成果”或“三项以上持续战略统帅”两类路径，避免穷举战役等级组合；权重只用于人才门槛，不改变战役定级和分项计分。文化单一作品路径仍限本人著成或最终定稿且具有文明奠基和长期基础使用的极少数成果。
- 固定顺序是“中性材料 → 无皇帝窗口成果总登记 → 皇帝窗口绑定 → 规则材料 → 计分”。总登记以 `outcome_kind` 区分战役、治理与谋略，每个独立结果只保存一次，含可观察结果、规模依据、人物角色、确定性 Episode、事实与史源；不保存分数或因子。谋略只供人物画像消费，不进入皇帝治理投影；各皇帝独立绑定表后置连接总登记，人物画像、I5B及其他项目只能消费连接结果，不建立评分专属事实副本。
- 战争最多登记为“战争终局背景 → 皇帝战役群父项 → 人物指挥子成果”三级树。战争终局只用于统一总成果校准，不进入 C1 或人才结算；C1 消费互不重叠的战役群，人才优先消费本人指挥子成果，同一人物不得同时消费祖先与后代节点。统治者控制分为授权、作战部署和前线指挥，并另记授权方式、控制范围与阻挠状态。战役字母档只表示已实现的战略结果，作战难度另以 `D0–D3` 登记；不利事实拆为战争成本、目标未完成和可归责失败，禁止用统一“过程负面”机械扣分。

## 当前架构

```text
输入皇帝 → 当前 source pack
→ 三路 neutral-material-intake
→ Rule Judge
→ HistoricalEpisode
→ HistoricalOutcomeCluster（战役/治理已实现结果）
→ RuleEvidenceUnit
→ 人才档位与窗口政治风险覆盖门禁
→ factor option → policy numeric mapping
→ strongest-N material budget
→ weighted raw net signal
```

PostgreSQL保存V4业务状态，Git保存规则、配置、契约和当前不可变输入。人物画像只使用 `v4_person_profile.person_profiles`，规范身份只使用 `v4_person_profile.person_identity_registry`。JSON/Markdown只允许作为当前只读输出；被新结果取代后直接删除。

皇帝篇章、臣子列传和朝代文治材料先进入同一 `neutral-material-intake`：只按上游稳定中性事实 ID 自动去重，跨来源仅因措辞相似不得自动合并。战役、治理与谋略结果随后统一编译为 `HistoricalOutcomeCluster`，并由一个确定性 `HistoricalEpisode` 支撑。PostgreSQL目标表只保存当前 `historical_episodes`、`historical_outcome_clusters`、`rule_evidence_units` 及成员关系；相同输入重跑零业务写入，历史只查 Git。

## 运行产物纪律

- Git只追踪当前规则、配置、每位皇帝唯一 source pack 和唯一结果。
- `tmp/**` 只允许保存当前运行所需的临时文件，成功收口后全部删除。
- 同侧事件结算仍受政策正3/负3预算约束；团队为正8/负3。未用满预算不扣分。
- source pack 中的因子只保存语义选项；数值必须由 `config/i5b-scoring-policy.yml` 确定性映射，篡改 source pack 或数值映射立即失败关闭。

## 当前入口

Windows仓库根目录：

```powershell
codex-win run -- python -m pip install -e .
```

首次克隆或 Python 环境变更后执行一次即可。项目使用 editable install，后续源码修改立即生效；所有新终端都可直接运行 `python -m emperor_v4...`，不再逐会话设置 `PYTHONPATH`。

```bash
python -m emperor_v4.eval model-policy --policy config/model-policy.yml
python -m emperor_v4.eval i5b-factor-semantics --contract config/i5b-factor-semantics.yml --output tmp/factor-semantics.json
python -m emperor_v4.eval i5b-scoring-policy --policy config/i5b-scoring-policy.yml --output tmp/scoring-policy.json
python v4.py i5b-run --ruler 李世民
python v4.py i5b-run --ruler 刘邦
python v4.py i5b-scoring-detail --ruler 李世民
python v4.py i5b-scoring-detail --ruler 刘邦 --person 周勃
python v4.py historical-gold-blind-run --ruler 李世民
python v4.py historical-gold-blind-run --ruler 刘邦
python v4.py historical-outcome-registry
python v4.py historical-outcome-dry-run --ruler 刘邦
python v4.py historical-outcome-dry-run --ruler 李世民
```

`historical-outcome-registry` 先重建 `eval/historical_outcome_registry/current.{json,md}`，再为每个皇帝生成独立窗口绑定；生成时必须能无损还原现有皇帝成果投影，否则失败关闭。人物画像按军事、治理、谋略和文化学术分别定档，总档取最高独立领域；两个领域分别达到 `top` 才能走显式全能型 `historic` 路径。总人物表列出所有具有成果或风险登记的人物，不以团队建设正八人、负三人预算截断；未完成全生涯本传与风险复核者只显示现有登记支持的档位下限。臣子详情使用 `--person`，显示该臣子的计分与未计分材料、当前人才档位、人才等级确立理由、对应规则、逐条成果类型/角色/规模/史源、窗口政治风险和 HistoricalEpisode。`historical-outcome-dry-run` 只计算将写入的当前行数与 migration 指纹，不读取 DSN、不打开数据库连接；本轮停在该边界。

### Google AI 无人值守宽搜

所有需要联网发现的工作流共用一套串行 Chrome 桥接，不依赖会随页面跳转失效的控制台脚本。政治风险、人物生平与评价、人才成就、文臣治理举措、皇帝政策等只是不同 `purpose_code`，扩展不写死业务场景。首次在 `chrome://extensions` 开启开发者模式并“加载已解压的扩展程序”：

```text
src/emperor_v4/infrastructure/google_ai_extension
```

此后先提交版本化 manifest，再启动本机队列；`--open-worker` 先打开带 `gai_bridge=1` 标记的普通 Google 启动页，扩展领取任务后才进入 Google AI，避免把空白 worker 保存成 `Google AI Bridge` 会话：

```powershell
python -m emperor_v4.infrastructure.google_ai_bridge --queue tmp/google_ai_bridge enqueue --manifest tmp/google_ai_manifest.json
python -m emperor_v4.infrastructure.google_ai_bridge --queue tmp/google_ai_bridge serve --open-worker
```

成功结果可直接转换为通用待回源定位清单，不绑定 I5B，也不写数据库或事实链：

```powershell
python -m emperor_v4.application.discovery_source_backfill --results-dir tmp/google_ai_bridge/results --output tmp/google_ai_backfill_worklist.json
```

桥接只负责串行领取、超时、结果指纹、Google 页面来源和原子落盘。结构化 discovery 合同使用
`response_mode: structured_discovery` 保留现有严格字段校验；其他 Prompt/输出合同使用
`response_mode: free_text` 原样持久化回答，再由对应模板的下游解析器校验业务字段。桥接层不得按
`purpose_code` 写死新的评分项、人物画像或其他业务模板。

I5B 的文臣治理成果和皇帝政策走同一桥接。先用 UTF-8 JSON 文件按边界优先级提供本轮人物（`[{"person_ref":"...","person_name":"...","aliases":[]}]`）；按 `person_ref` 去重后最多为前12人生成治理宽搜，超限人物留作 deferred，再单独追加一项不占人物名额的皇帝政策宽搜。入选人物的焦点内独立线索不按固定条数截断；文臣结果仅在首轮回源时按可定位性排序取三条，皇帝政策不设条数上限，回源只受本轮总时间墙约束：

```powershell
python -m emperor_v4.application.google_ai_discovery_prompt --policy config/google-ai-discovery-prompt.yml --i5b-ruler-ref PER-TAIZONG --i5b-ruler-name 唐太宗 --i5b-ruler-dynasty 唐 --input-version i5b-v1 --civil-people tmp/i5b_taizong_civil_people.json --output tmp/i5b_taizong_manifest.json
python -m emperor_v4.infrastructure.google_ai_bridge --queue tmp/i5b_taizong_google enqueue --manifest tmp/i5b_taizong_manifest.json
python -m emperor_v4.application.discovery_source_backfill --results-dir tmp/i5b_taizong_google/results --i5b-ruler-ref PER-TAIZONG --i5b-ruler-name 唐太宗 --i5b-ruler-dynasty 唐 --output tmp/i5b_taizong_backfill_worklist.json
python -m emperor_v4.adapters.source_text_index build-jsonl --input tmp/tang-core-pages.jsonl --output tmp/tang_source_index.sqlite3
$sourceIndexRoot = "X:\emperor-evaluation\runtime\active\source_text_indexes\tang-core-current"
python -m emperor_v4.adapters.source_text_index recall-report --index "$sourceIndexRoot\tang-core.sqlite3" --input "$sourceIndexRoot\full-recall-input.json" --output "$sourceIndexRoot\full-recall-report.json"
python -m emperor_v4.adapters.subject_mention_index build --source-index "$sourceIndexRoot\tang-core.sqlite3" --input "$sourceIndexRoot\subject-mention-plan.json" --output "$sourceIndexRoot\subject-mentions.sqlite3"
python -m emperor_v4.adapters.subject_mention_index report --source-index "$sourceIndexRoot\tang-core.sqlite3" --mention-index "$sourceIndexRoot\subject-mentions.sqlite3" --output "$sourceIndexRoot\subject-mention-report.json" --window-chars 440 --merge-gap-chars 60
python -m emperor_v4.adapters.subject_mention_index shared-review-plan --report "$sourceIndexRoot\subject-mention-report.json" --output "$sourceIndexRoot\subject-shared-review-plan.json" --review-tiers A B
python -m emperor_v4.adapters.ruler_neutral_person_recall --ruler 李世民 --records "$runtimeRoot\ruler-neutral-records.jsonl" --people "$runtimeRoot\people.json" --output "$runtimeRoot\ruler-person-recall-plan.json" --batch-count 4
python -m emperor_v4.adapters.person_lifecycle_scan --manifest "$runtimeRoot\person-scan-task-manifest.json" --results-dir "$runtimeRoot\person-scan-results" --source-dir "$runtimeRoot\person-scan-source-plaintext" --output "$runtimeRoot\person-lifecycle-fanout.json"
python -m emperor_v4.adapters.subject_mention_index review-worklist --report "$sourceIndexRoot\subject-mention-report.json" --output "$sourceIndexRoot\subject-review-worklist.json"
python -m emperor_v4.adapters.subject_mention_index refetch --worklist "$sourceIndexRoot\subject-review-worklist.json" --state-dir "$sourceIndexRoot\subject-review-source-cache" --output "$sourceIndexRoot\subject-review-refetch-result.json" --max-workers 6 --timeout-seconds 30 --max-attempts 3
python -m emperor_v4.evaluation.i5b_source_review_projector --decision tmp/i5b-source-review-decision.json --refetch-result "$sourceIndexRoot\subject-review-refetch-result.json" --output-dir tmp/i5b-source-review-projection --max-workers 5 --per-task-timeout-seconds 75 --wall-clock-budget-seconds 120
python v4.py i5b-current-value --ruler 李世民
python -m emperor_v4.runtime.person_rebuild_shadow i5b-backfill --worklist tmp/i5b_taizong_backfill_worklist.json --local-source-index "$sourceIndexRoot\tang-core.sqlite3" --state-dir tmp/i5b_taizong_source_state --output-dir tmp/i5b_taizong_source_reports --service-release-sha <40位提交SHA> --max-workers 6
```

本地全文索引是不可裁剪的召回底座。当前语料、索引、召回输入和影子报告统一保存在 NAS 的 `X:\emperor-evaluation\runtime\active\source_text_indexes\tang-core-current`；仓库 `tmp/**` 只作可删除的构建暂存，不是长期数据位置。大索引先在本地临时路径构建，校验身份和 SHA-256 后再发布到 NAS，避免直接在 SMB 目录构建半成品。`recall-report` 的 UTF-8 JSON 输入按对象提供 `works`、`recall_terms`、`attribution_terms`、`priority_terms`、显式朝代 `page_ranges` 和可选的 `priority_window_chars`；姓名命中页全部输出，不设 Top-K，也不受 FTS 候选上限影响。完整姓名只在本地标记明确归责，不触发第二次联网查询；主题词只在姓名附近的字符窗内增加优先级。仅短称出现或未命中主题的本朝页面仍完整保留。

I5B 当前值命令只消费当前 source pack：事件材料通过 Gate 后按 strongest-N 预算结算，团队保持正8、负3；它不会合并旧基线，也不会生成45分、档位或排名。

李世民、刘邦的完整 I5B Gold 同时冻结公共成果、人物画像、五条规则投射、团队正8/负3代表池、各规则正负净信号和加权 raw signal；任用授权预算按聚合后的任用对象或责任群体计数，责任链仅在对象内部递减与封顶，不得把内部链条数误报为已占用预算单元。

`historical-gold-blind-run` 先从 current source pack 在内存生成影子结果，生成完成后才读取冻结 Gold 并比较；它不覆盖 canonical 结果，不调用模型，不连接数据库，也不写正式评分。Gold 只能揭示生成链偏差，禁止为了通过门禁反向修改冻结期望。

当前链路不接受正向任用授权手填材料：人物画像由当前战役、治理与谋略登记重算，发现人才的人才质量因子随画像确定性更新；正向任用授权的重要性读取参与者在授权当时的结构化责任范围，效果与持续性再分别读取成果规模和运行观察。避免任人唯亲材料必须通过公共权力作用 Gate。皇帝计分详情末尾直接列出完整治理、战役和人物谋略登记；上游登记变化后，重跑同一命令即重建画像、团队正负池、功能互补、Episode、REU、材料预算和导出。

`i5b-scoring-detail` 默认同样从当前 source pack 在内存中重建后导出，`--person` 只过滤展示对象，不读取可能过期的 canonical `result.json`；只有显式传入 `--result` 时才按指定结果快照导出。`--output` 可省略：皇帝详情默认写入 `tmp/i5b_scoring_detail/<皇帝>/scoring-detail.md`，臣子详情默认写入 `tmp/i5b_scoring_detail/<皇帝>/persons/<臣子>.md`；显式路径仍优先。

任用材料投影按责任对象最多5路并行，单对象75秒、全阶段120秒硬截止且不自动重试。智能体只输出带短引用码的原子观察和 disposition，服务端映射回精确 revision 段落并确定性推导连续性；只有 `coverage_complete=true` 才替换既有 shadow 材料，不完整草案仅保留 gap，不得用残缺摘要覆盖现有事实。

`subject_mention_index build` 在全文索引之外生成可重建的 `subject-mentions.sqlite3`，只固化人物称谓或指定皇帝核心篇章中“上曰、上谓、诏”等上下文标记的原文偏移，不复制正文。标题中的姓名不计作事件命中，但本传标题可为后续短称提供结构归责。`report` 围绕偏移生成约 440 字的展示窗口，邻近窗口只在合并后不超过配置窗口加间距时合并；A/B/C/D 判定另只检查每个主体偏移前后 120 字，避免把同一展示窗口中其他人的行动误归给当前主体。A 层同时具备主体、行动、实施和结果锚点，进入首轮人工复核；B 层只在 A 层不足时复核；C/D 完整保留但不进入当前回源。A 层窗口再生成稳定 `MENTIONCLUSTER`：同页必须距离不超过 800 字且共享锚点；跨书必须同时满足纪年一致、主题一致、行动或实施一致以及实施或结果一致。证据不足时保持独立窗口，不用语义猜测强行合并。主题词仍只影响排序，全部无主题窗口保留。旁路库会绑定全文索引 identity 和页面 revision，漂移时关闭；相同输入重建和相同报告重跑均为零写入。它们仍只是回源定位影子，不是 `SourcePassage`、Assertion 或评分史源。

`review-worklist` 将 A 层 cluster 物化为审阅卡，并按 `page_title + revision_ref` 生成去重的 `refetch_pages`。卡片只汇总既有纪年、主题、行动、实施和结果锚点，不生成新的历史结论；缺纪年、单书、纯隐含皇帝主语、无主题锚点和跨书合并都显式标记。所有页面初始均为 `refetch_status: not_started`，生成待办本身不联网，也不代表已批准回源。

`shared-review-plan` 不改变逐人物召回和 A/B/C/D 分层，只把入选层级中同一 `page_title + revision_ref` 的人物窗口组织成一个页面级模型批次。重叠原文合成共享 segment，非重叠原文保持为同一批次内的独立 segment；每个 member 继续保留自己的 `subject_ref + window_ref`，因此共享读取不等于共同归责。计划本身不调用模型、不联网、不写正式事实；后续中性抽取应按页面最多调用一次，再按明确 actor 关系确定性分发给人物画像和规则投影。

所有 Codex 结构化抽取在批量放行前必须经过 `structured_output_contract`：零调用阶段递归检查显式 `type`、严格 `required`、`additionalProperties: false`、禁用 `uniqueItems`，并核对任务实际通过 `argv` 传递同一 `--output-schema`；单任务 canary 随后关闭进程状态、`respect_task_argv`、工具事件、Token 上限和结果 Schema。只有报告达到 `ready_for_batch_fanout` 才能扩大并发。子进程只填充父进程冻结的合同，不得读取仓库、调用工具或自行修改 Schema；数组去重由确定性验收层完成。

皇帝侧中性材料已经抽取完成后，`ruler_neutral_person_recall` 以人物全名和显式别名一次召回记录中涉及的所有臣子，按文本负载均衡生成共享判读批次；每条记录只判读一次，再由 `build_ruler_neutral_person_fanout` 校验人物覆盖、Assertion 锚点、角色与画像资格后确定性分发。姓名命中只负责召回，任命对象、受处置者、被评价者和上下文人物不会自动取得实绩；共享批次也不合并不同人物的责任。整个计划和分发结果均为影子候选，模型调用预算按批次数而不是人物数计算。

共享模型输出使用 `config/shared-neutral-extraction-output.schema.json`。`shared_neutral_extraction` 会关闭缺页、缺 segment、引文不能逐字回指、actor 引用非本 segment 主体、无召回主体归责以及只靠 `mentioned_only` 强占事实归属的结果；通过后只生成 `shared-neutral-fact-fanout-v1` 影子候选。同一事实可分发给多个明确 actor，但 `affected_person`、`mentioned_only`、单纯授权者和 `context_only` 不具备人物实绩投影资格。通用 Prompt 排除未明示较大资源消耗、治理中断或严重政治影响的普通宴饮、大酺、游猎、巡幸和祭祀，并禁止输出评分项目或复用建议。该步骤不创建 HistoricalEpisode，不写人物画像、评分或排名。

朝代制度史使用 `dynasty_neutral_governance` 对修订号绑定的纯文本作一次规则中立扫描，再由不同评分项后置投影。事实链只保存行动、实施、可观察结果、成本负担、影响群体和人物贡献阶段；创设者、执行者、纠偏者与废止者不得因同处一链而混为共同责任。引文验收只忽略排版空白和纯数字编辑脚注锚点，简繁、异体字和标点变化仍失败关闭。该扫描不输出评分方向、规则复用建议或 factor，也不写 HistoricalEpisode、人物画像和评分。

跨朝政书按 `source_genre + source_work + target_scope` 显式限定目标朝代，卷内前代制度只有在原文明示被目标朝代继承、修改、废除或实际运用时才可进入同一事实链。

跨书结果先由 `dynasty_neutral_source_increment` 分类，再由 `dynasty_neutral_material_settlement` 确定性结算：`new_fact` 保留为独立中性候选；`same_fact_enrichment` 和 `same_fact_restatement` 通过共同 baseline 组成同一事实连通分量，后者只追加独立史源回指；`uncertain` 停在人工复核队列。结算器不拼接新的事实叙述，只输出当前材料组件、去重后的逐字 evidence 和检索用人物/领域索引。复核前连通分量不能直接投影 Episode；进入 Episode 前仍须 canonical person 解析和原子化审阅。通过验收的中性事实再由后置 RuleEvidenceUnit 决定规则相关性和方向。

`dynasty_neutral_material_atomization` 只消费复核队列和已经验真的引文编号，不联网、不补史实；拆分结果仍须完成人物与皇帝窗口解析。

`governance_achievement_candidate` 再把结算组件、未被增量命中的朝代基线和上述原子确定性编译为一次性消费集合；同一组件只进入一个模型任务。已有人物先绑定现有 `person_ref`，简繁由 OpenCC 统一；其余人名生成朝代内 provisional actor ref，机构和复数官署不冒充人物。模型只能在允许组件、人物和字段内作 `register / omit / uncertain` 判断，不能生成史源、ID、规则方向、Episode、REU或分数；审计器再确定性生成 `governance-achievement-registry-v1`。判断 policy 进入 `task_code` 指纹，Prompt 变化不会复用旧结果。影响尺度看已实现结果而不是法令名义覆盖：单案、窄条款、资格线或一次程序调整不得仅因“颁行天下”升为国家级，`stable_delivery` 与 `important_method_or_legacy` 也必须有运行或延续证据。

三路协同入口由 `emperor_v4.evaluation.neutral_material_intake.build_neutral_material_intake` 提供；`governance_fact_sets` 以稳定 `fact_ref` 和精确 `page@revision#quote` 史源回指接入制度史中性事实，缺少任一项即失败关闭。已接受的统一成果由 `outcome_records_from_registry` 转为当前 PostgreSQL 记录。只有底层事实、Episode 和成员责任全部解析后才具备写库条件；I5B消费成果簇和人物画像生成 REU，再由现有材料预算与公式结算。

皇帝从文臣 `participants` 分离为 `ruler_links`；正式人物 ID 优先，临时人物 ID 只能按唯一规范名桥接，歧义即失败。多事实上游成果只在必要时走一次 lineage refinement，常规单事实成果确定性收窄；不支持成果的组件必须明确剔除。

推广以“朝代一次扫描、项目多次投影”为单位，不按皇帝或评分项重复扫书。质量门通过的当前材料以朝代、史源索引 identity、页面 revision 和抽取合同为复用键冻结；输入未变化时零模型调用，后续调度优化只使用尚未验收的书目。新增朝代先做少量高复用章节 canary，再依据新事实与补强比例决定是否扩卷；新增书目按经济、法律、军制、官制等领域先各选一部高密度主书，已有领域只有在当前材料缺项或独立史源补强价值明确时才增加第二部，避免同域全文重复扫描。书目仍优先覆盖正史志、会要政书、通制法典以及财政、选举、刑法、军制等可观察实施与结果较密集的篇章，并继续携带 edition/revision、篇卷、目标朝代和 source genre；低增量书目可停止扩卷，但不能据此宣称该领域没有史实。

```powershell
python -m emperor_v4.adapters.dynasty_neutral_governance prepare --source-manifest <plaintext-manifest.json> --output-root <scan-root> --output-schema config/dynasty-neutral-governance-output.schema.json
python -m emperor_v4.adapters.dynasty_neutral_governance audit --preparation <scan-root>/preparation.json --results-dir <scan-root>/results --output-schema config/dynasty-neutral-governance-output.schema.json --output <scan-root>/audit.json
python -m emperor_v4.adapters.dynasty_neutral_source_increment prepare --baseline-audit <baseline-audit.json> --candidate-audit <candidate-audit.json> --output-root <comparison-root> --output-schema config/dynasty-neutral-source-increment-output.schema.json
python -m emperor_v4.adapters.dynasty_neutral_source_increment audit --preparation <comparison-root>/preparation.json --result <comparison-root>/result.json --output-schema config/dynasty-neutral-source-increment-output.schema.json --output <comparison-root>/audit.json
python -m emperor_v4.adapters.dynasty_neutral_material_settlement --baseline-audit <baseline-audit.json> --candidate-audit <candidate-audit.json> --increment-audit <comparison-root>/audit.json --output <settlement.json>
python -m emperor_v4.adapters.dynasty_neutral_material_atomization prepare --settlement <settlement.json> --output-root <atomization-root> --output-schema config/dynasty-neutral-material-atomization-output.schema.json
python -m emperor_v4.adapters.dynasty_neutral_material_atomization audit --preparation <atomization-root>/preparation.json --result <atomization-root>/result.json --output-schema config/dynasty-neutral-material-atomization-output.schema.json --output <atomization-root>/audit.json
python -m emperor_v4.evaluation.governance_achievement_candidate prepare --baseline <baseline-audit.json> --settlement <settlement.json> --atomization <atomization-root>/audit.json --people <profiles-or-people.json> --dynasty-token <TANG> --output-root <achievement-root> --output-schema config/governance-achievement-candidate-output.schema.json
python -m emperor_v4.evaluation.governance_achievement_candidate audit --preparation <achievement-root>/preparation.json --results-dir <achievement-root>/results --output-schema config/governance-achievement-candidate-output.schema.json --registry-schema config/governance-achievement-registry.schema.json --ruler-aliases config/historical-entity-identities.yml --dynasty-name 唐 --output <achievement-root>/audit.json
python -m emperor_v4.evaluation.governance_achievement_lineage prepare --achievement-audit <achievement-root>/audit.json --candidate-preparation <achievement-root>/preparation.json --output-root <achievement-root>/lineage --output-schema config/governance-achievement-lineage-output.schema.json
python -m emperor_v4.evaluation.governance_achievement_lineage audit --achievement-audit <achievement-root>/audit.json --candidate-preparation <achievement-root>/preparation.json --lineage-preparation <achievement-root>/lineage/preparation.json --result <achievement-root>/lineage/result.json --output-schema config/governance-achievement-lineage-output.schema.json --registry-schema config/governance-achievement-registry.schema.json --output <achievement-root>/lineage/audit.json
python -m emperor_v4.evaluation.governance_achievement_registry --registry <lineage-audit.json> --profiles <profiles.json> --schema config/governance-achievement-registry.schema.json --team-report <team-report.json> --material-budget-report <material-budget-report.json> --scoring-policy config/i5b-scoring-policy.yml --output <impact.json>
```

人物列传或其他人物页的全生涯扫描结果由 `person_lifecycle_scan` 统一验收：任务、页面、revision、人物和 `person_scan_key` 必须完整闭合，每条 Assertion 与评价 lead 都必须逐字存在于任务绑定的 plaintext；通过后才确定性生成稳定 `PFACT` / `PLEAD` 引用并按 canonical person 分发。人物材料保留跨朝生涯，后置皇帝窗口再决定是否投影；同一页共享扫描不合并人物责任，且本步骤仍为零正式事实、画像和评分写入。

`refetch` 获取待办指定的Wikisource原始revision槽位内容，而不是会改变偏移的纯文本extract。页面按MediaWiki原生批量查询串行获取，避免逐页并发触发限流；已成功页面按 `page_title + revision_ref` 缓存在独立 state 目录。每个窗口都重新按原始偏移截取并核对文本哈希，revision或窗口漂移即关闭，不自动改用新版本。成功结果只是带精确lineage的影子 `MENTIONPASSAGE`，仍不启动Claim或写Assertion。

`i5b_source_review_quality_probe` 只接受上述精确回源 passage 和人工/主会话审阅后选择的语义档位；decision 不携带数值，所有 factor 数值均由 `config/i5b-scoring-policy.yml` 确定性映射。v2 要求人才与政治风险画像声明完整生涯覆盖，而每条计分 episode 的 `ruler_window` 必须等于当前皇帝窗口；跨朝实绩可以改变人物档位，不得倒算为当前皇帝功劳。皇帝政策的全部精确回源 passage 还必须闭合处置为 `counted`、`supporting` 或 `excluded`。探针复用现有材料预算、去重和 strongest-N 规则，只输出各 rule 净信号与 weighted raw signal；单皇帝不得生成45分、档位或排名，仍须等待跨皇帝动态映射快照。

汉籍全文资料库只作为低频影子定位和覆盖差异校准，不批量下载正文或整站结果。同一人物的查询词只保留“最短但仍可归责”的有效形式，例如 `玄龄` 已覆盖 `房玄龄` 时不再重复请求，而单字 `靖` 不取代 `李靖`。进阶检索只按宽主题提高处理优先级；专业检索的第二个词必须是已经得到正文或人工支持的锚点，不从宽主题自动猜谓词。两者都不得删除本地姓名召回页。可用 UTF-8 JSON 输入生成确定性的影子检索方案：

```powershell
python -m emperor_v4.adapters.hanchi_locator --input tmp/hanchi_lijing_plan_input.json --output tmp/hanchi_lijing_plan.json
python -m emperor_v4.adapters.hanchi_locator --input tmp/i5b_hanchi_policy_candidates.json --output tmp/i5b_hanchi_policy_plan.json
python -m emperor_v4.adapters.hanchi_locator --input tmp/i5b_hanchi_policy_candidates.json --output tmp/i5b_hanchi_policy_result.json --curl-template tmp/hanchi-curl.txt
python -m emperor_v4.evaluation.i5b_hanchi_policy_review backfill-worklist --hanchi-plan tmp/i5b_hanchi_policy_plan.json --hanchi-result tmp/i5b_hanchi_policy_result.json --ruler-ref <皇帝ref> --ruler-name <皇帝名> --output tmp/i5b_hanchi_policy_backfill.json
python -m emperor_v4.evaluation.i5b_hanchi_policy_review judge-worklist --backfill-worklist tmp/i5b_hanchi_policy_backfill.json --source-report tmp/source-report.json --max-concurrency 3 --output tmp/i5b_hanchi_policy_judge.json
python -m emperor_v4.evaluation.i5b_hanchi_policy_review merge --judge-worklist tmp/i5b_hanchi_policy_judge.json --result tmp/judge-result-1.json --result tmp/judge-result-2.json --output tmp/i5b_hanchi_policy_review-pack.json
```

规划输入包含 `subject_name`、`dynasty_scope`、现场简易检索所得的 `observed_simple_hits`，以及可选的 `broad_topics`、`professional_anchors`。每轮先从免费检索页取得一次当前 `hanjiquery` 表单状态，随后按“全部简易→全部进阶→必要的专业”严格串行直接 POST；每次响应都按浏览器成功控件规则刷新会话 URL、检索模式和 `_TTS_CONTROL`，不固化每日可能变化的表单值。过期或未回显本次检索词的响应失败关闭；无摘要响应只有同时通过检索词、模式、动态 action 和控制字段校验时才记作零命中。运行时 Copy-as-cURL 模板不写入仓库。单皇帝按 `person_ref` 去重后最多12个人物入口，政策入口不占名额。汉籍库的会话 URL和搜索摘要不是史源；按配置书目过滤并在本地以书卷段号去重后，仍须从稳定版本正文独立回源。

政策入口必须按稳定 `candidate_ref` 拆分，不得再把全部皇帝政策合并成一个笼统入口。相同的皇帝简易查询只实际 POST 一次并向各候选扇出，候选特定的进阶或专业查询分别执行；每个候选的查询方式、过滤书目、汉籍 locator、精确 passage 和 Judge disposition 全程保留。精确回源完成后按 `candidate_ref` 生成可并行 Judge 任务，正常结果通过合同后直接合并为 shadow review pack，主会话只处理无命中、回源不足或合同冲突，不重复语义复核。正式检索链声明 `google_used_for_retrieval: false`。

`i5b-backfill` 按文臣/皇帝政策对象拆分并行 Source Cache 请求，复用同一对象的缓存；它不启动 Claim。每名皇帝每轮最多启动12个人物检索入口：输入顺序即上游边界优先级，按 `person_ref` 稳定去重后截取；皇帝政策与责任群体不占人物名额，超限人物以 `deferred_boundary_candidate` 保留。`config/i5b-source-search-scope.yml` 按显式朝代分别配置文臣治理和皇帝政策书目，禁止根据皇帝姓名猜朝代。先在只读本地全文索引中定位候选卷，再仅向 Wikisource 获取首个能锚定该线索的当前 revision 正文；在线目录搜索不再属于主链，也不需要下载全站 dump。索引身份进入 Source Cache 指纹，索引内容变化会使旧缓存失效。`i5b_selection.deferred_discovery_leads` 记录未进文臣首轮的补充线索；政策线索不会因数量而延后。它不写 Assertion、数据库、评分或排名。

清单按原 `task_code` 和 `LEAD` 编号生成稳定回源任务，并按人物与具体文献页或待检书目合并 `source_batches`：同一页只回源一次，可同时支持 HistoricalEpisode、人才画像和政治风险画像候选。只有书名的线索必须提供 `--local-source-index`；没有索引时 Source Cache 以 `local_source_index_required` 关闭该批次，不退回在线宽搜。相同输入重跑不重写文件。Google、索引命中和站点搜索都只是定位线索，只有随后取得并锚定的 revision 正文才能生成影子 `SourcePassage`；它不得直接成为 Assertion 或评分材料。

人物全量重建每人固定生成三项串行宽搜：原子生平事件与重大人才成就、人才等级所需的权威评价定位、以及本人已实施且造成实质损害的政治风险。三项结果合并回源，不为 episodes 和画像重复抓取文献：

```powershell
python -m emperor_v4.application.google_ai_discovery_prompt --policy config/google-ai-discovery-prompt.yml --person-ref PER-V4-LIJING --person-name 李靖 --input-version person-rebuild-v1 --alias 李药师 --alias 卫国公 --output tmp/person_rebuild_lijing_manifest.json
python -m emperor_v4.infrastructure.google_ai_bridge --queue tmp/person_rebuild_lijing enqueue --manifest tmp/person_rebuild_lijing_manifest.json
python -m emperor_v4.infrastructure.google_ai_bridge --queue tmp/person_rebuild_lijing serve --open-worker
```

`dispatch` 只在同一人物的生平/成就、权威评价与政治风险三个焦点均完成时生成该人物回源清单；其他人物仍在宽搜不阻塞已就绪人物。回源与 Claim 使用独立进程消费这些文件，不放进 Chrome 串行循环。I5B 主链使用一个 900 秒墙钟入口：回源和 Claim 各最多 6 路并行，首轮每人只回源两部优先正史并合并同页线索；其余书目保留为 deferred 线索。只有 Claim 会启动 `gpt-5.6-luna / low` 后台进程；每个子进程的超时自动裁剪为总预算余量，单人瞬时失败最多自动重试一次。

```powershell
python -m emperor_v4.runtime.person_rebuild_shadow run-ready --results-dir tmp/person_rebuild_lijing/results --ready-dir tmp/person_rebuild_lijing/ready --source-state-dir tmp/person_rebuild_lijing/source_state --source-report-dir tmp/person_rebuild_lijing/source_reports --claim-state-dir tmp/person_rebuild_lijing/claim_state --claim-report-dir tmp/person_rebuild_lijing/claim_reports --shadow-output-dir tmp/person_rebuild_lijing/person_shadow --profiles config/claim-extraction-profiles.yml --output-schema config/claim-extraction-output.schema.json --codex-bin codex --model gpt-5.6-luna --reasoning-effort low --per-claim-timeout-seconds 180 --service-release-sha <40位提交SHA> --source-max-workers 6 --max-source-documents-per-person 2 --claim-max-workers 6 --claim-max-attempts-per-source 2 --wall-clock-budget-seconds 900
```

`assemble-ready` 只生成待人工复核的 HistoricalEpisode 与人物画像候选；史臣评价不伪装成事件，争议或被诬指控不进入本人政治风险。该步骤不写数据库、正式 Assertion、人物画像、评分或排名，无变化重跑不重写候选。

实际画像档位和 episode 必须由这些 `source_batches` 回源得到的同一组 `SourcePassage → Assertion` 投影，不允许两条独立事实链。到点停止领取新任务，超时返回只留在可丢弃 shadow state，不写本轮 claim report。当前输出仍为 shadow 候选，不写正式数据库、评分或排名。

manifest 使用 `google-ai-browser-manifest-v1`，每个任务必须包含稳定 `task_code`、`input_version`、`purpose_code`、`subject_ref`、`subject_name`、`query` 和 `requested_outputs`，并可携带 `downstream_context` 与质量要求。队列全局只发放一个 lease，每项检索使用独立 AI Mode 页面，避免长会话质量漂移；页面跳转或重载后自动续跑。默认最多等待 30 秒；正常情况下等生成结束且文本稳定后采集，截止时也只有结构完整、主体和长度合格且已有外链的回答才可提交。通用 discovery prompt 默认不限制独立线索数量，由焦点内检索类别、项目相关性、独立性和可回源性收束，并输出已检索类别、未覆盖类别与停止原因；调用方仍可为特定低预算任务设置上限。“候选发现”是项目工作流术语，不指历史上的档案召回或销毁。普通超时和单任务合同失败不阻断其他任务，只有限流或验证码才暂停队列。相同输入完成后重跑不会再触发检索，也不会重写结果。

Google AI 结果属于统一 discovery artifact：它只给 Source Cache 提供文献、篇章、事件和评价方向线索，统一 prompt 明确禁止生成古籍原文或引文候选。只有回源形成 `SourcePassage` 后才能进入 Claim Extractor；再经合同和接受门禁，才允许成为 Assertion、HistoricalEpisode、人物画像修订候选或评分材料。

项目统一检索 prompt 维护在 `config/google-ai-discovery-prompt.yml`。调用方只填写检索对象、焦点、可能改变的项目判断和需要返回的线索类型；不得为单个人物或 rule 另建 prompt runtime。

## 当前事实源

1. `docs/项目总纲/皇帝综合评价体系评分标准.md`
2. `docs/00-V4项目章程.md`
3. `docs/项目总纲/总规则.md`
4. 当前领域、证据与服务契约
5. 当前分项规则
6. `config/*.yml`

当前状态只维护在本文件和 `config/project.yml`。历史过程、旧结论和被删除产物需要时从Git查看。

正式45分、档位和排名只有在跨皇帝动态映射快照另行批准后才能开启；当前链不隐式生成这些字段。
