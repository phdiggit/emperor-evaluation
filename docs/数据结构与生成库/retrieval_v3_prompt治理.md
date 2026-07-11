# retrieval_v3 prompt 治理

本文约束 retrieval_v3 抓包、判读、因子化和复核任务的 prompt 增量治理。目标不是让 prompt 更完整，而是在保证质量的前提下降低长期 prompt 负担。

## 核心原则

抓包可以宽，事实结构要稳，入分必须窄；prompt 必须更窄。

新增事实类型、召回方向或评分边界时，优先选择结构化配置、检索 profile、route table、validator 或消费端短因子表。只有这些位置都无法表达，且缺口会稳定反复出现，才允许进入长期 prompt。

## 分层

retrieval_v3 prompt 分四层治理：

| 层级 | 放什么 | 不放什么 |
| --- | --- | --- |
| 长期核心 prompt | 输出 JSON 契约、硬安全边界、原子事实拆分、入分门禁 | 人名个案、长例词表、可由 validator 检查的枚举 |
| profile / source discovery | 召回词、史源页偏好、对象族补源方向 | 评分解释、最终因子档位 |
| route table / schema | candidate lane、hint status、payload 字段、有限枚举 | 自由文本裁判理由 |
| report / validator | 缺字段、越界 hint、route/profile 问题、prompt budget 指标 | 让模型事中自审纠错 |

## Prompt 增量准入

任何长期 prompt 增量必须先回答四个问题：

1. 是否可以放到检索 profile，而不是 judge prompt。
2. 是否可以放到 route table 或 payload schema，而不是自然语言说明。
3. 是否可以由 report / validator 事后发现，而不是要求模型事中记住。
4. 是否会在至少两个以上人物或对象族中稳定复用。

只有四项都不能替代，才允许新增长期 prompt 文本。

## 禁止模式

- 不为单个历史人物追加长期例词。
- 长期 source discovery profile 只收机制词，不收人名、官署名、个案事件名；人名和个案词只能进入一次性补抓任务。
- 不把一次消费端误判直接写成 judge prompt 新规则。
- 不把现代抽象标签当作主要检索词塞入长期 prompt。
- 不在抓包 prompt 中输出正式因子 label、数值或完整评分公式。
- 不为了召回一个缺口，把相邻项规则全文塞入当前任务。
- 不把可用脚本检查的字段枚举反复写成大段自然语言。

## 缺口处理顺序

遇到胡惟庸这类缺口时，处理顺序固定为：

1. 判断是 source recall、candidate routing、claim schema、factorization 还是 scorer 缺口。
2. 如果是 source recall，先补 source discovery profile、对象族检索策略或对象补源任务。
3. 如果是 routing，先补 candidate route table 或 payload profile。
4. 如果源片段已经召回但核心对象多条事实没有拆成 claim，标 `object_claim_undercoverage`，进入 `source_pack_refinement` 队列，不进入 recall term overlay。
5. 如果是 schema，补有限字段和 validator。
6. 如果只是个案表达不稳，生成复核 worklist，不改长期 prompt。
7. 只有机制级语义缺失时，才给长期 prompt 增加一句抽象规则。

`appointment_delegation` 负向缺口要先排除“源页不足”：如果当前材料主要来自本纪编年，只看到任相、谋反、伏诛、废官等处置结果，而没有看到任内权责滥用、治理损害或授权链条失控，应先对具名对象触发本传、列传或纪事本末补源。补源命中后，若现有通用机制词已经能召回 `宠任`、`专擅`、`威福`、`封事`、`不奏`、`径行` 等事实链，不得再为该个案增加 `刘基`、`总中书政`、具体卷号等长期 prompt 或长期 profile 词。

对象补源优先使用 `scripts/dev/retrieval_v3_candidate_source_refiner.py` 的 judge/candidate gap source presearch；只有自动搜索无法稳定命中目标本传或交叉源时，才允许在 shadow task 中临时追加 pinned `source_documents` 做诊断。pinned source 只能进入 tmp 报告或一次性补抓任务，不得直接写回正式 profile。

`personnel_political_wide` 的通用质量门禁高于单个 rule：如果同一核心对象在 source passages、本传、列传或本纪交叉材料中出现多条可复用 `political_action_v1` 事实，不得只输出一条代表性 claim。任命、授权、委任、留守、镇守、总制、提督、出使、采纳、保全、处置、纠偏、约束、撤权、惩戒、平乱、出征、防边等动作，只要带具体任务/职责/制度/事件，并带结果、代价、持续复用、权力变化或治理反馈，应尽量拆成独立原子 claim 并分别路由。预算不足、共同任务链对象未拆全或本传/本纪显示仍有未拆事实时，写 `coverage_gap`：`gap_type=object_claim_undercoverage`、`queue=source_pack_refinement`、`recommended_action=run_object_source_refiner`、`do_not_add_recall_terms=true`。

## 消费端因子化 prompt 治理

消费端 factorization prompt 只承载 JSON patch 契约、quote-only 证据原则、当前 rule 因子表、短边界和少量稳定校准。抓包缺口、route / schema 缺口、hint 适配 bug、scorer 计算问题不得通过追加 factorization prompt 解决。

消费端遇到错误时，先按以下顺序收口：

1. 判断材料是否缺 quote、span 错位、对象错配或 source recall 不足。
2. 判断候选 lane、`hint_status`、profile、required facts 和 scoring gate 是否表达清楚。
3. 判断有限枚举、hint confidence、factor refs、side 和 action 是否能由 worklist / validator 确定性检查。
4. 判断因子表或规则表是否缺档位、缺边界或旧逻辑残留。
5. 只有在 quote 充分、结构字段正确、规则表同步且仍反复误判时，才增加 factorization prompt 校准。

抓包端的 factor hint 只是有限枚举预填建议，不是正式裁判。消费端可以采纳、降档、改档或拒绝；拒绝理由优先写入 report / validator 输出，而不是要求模型在 prompt 内自审。

消费端长期 prompt 禁止加入单个历史人物、单个 claim、单个对象名或一次性补抓结论。个案问题进入复核 worklist、focused test、source discovery profile 或 prompt debt 清单；只有跨人物、跨对象族稳定复发的因子化偏差，才允许沉淀为长期 prompt 文本。

## 度量

每次调 prompt 前后至少记录：

- prompt 字符数或估算 tokens。
- judge input / output / reasoning tokens。
- wall time。
- claim_count、secondary_binding_count。
- 当前目标 rule 的 scoring candidate 数。
- route problem、profile problem、hint missing / invalid / offscope。
- 关键回归对象是否退化。

没有这些指标，不宣称 prompt 优化或质量提升。

## 运行资产目录

retrieval_v3 大包、normalized staging、feedback JSONL 和 shadow report 属于运行资产，不属于源码上下文。默认写入 NAS active runtime，避免 repo 内 `tmp/` 堆积后被 `rg`、diff 或 Codex 误扫。

当前 active runtime：

```text
\\192.168.1.37\data1\emperor-evaluation\runtime\active
```

常用子目录：

```text
retrieval_v3_clean_runs
retrieval_v3_consumption
retrieval_v3_feedback
retrieval_v3_reports
source_cache
```

冷归档目录：

```text
\\192.168.1.37\backups\code\emperor-evaluation\runtime-archive
```

新包运行默认由 `scripts/dev/retrieval_v3_runtime_paths.py` 读取 runtime path config。需要人工确认目录时先跑：

```text
python scripts/dev/retrieval_v3_runtime_paths.py new-run <run_name>
```

`retrieval_v3_clean_cli.py` 未显式传 `--run-root` / `--source-cache-root` 时默认写入 NAS clean run 和 source cache；`retrieval_v3_intake_rows.py build` 未显式传 `--output-root` 时默认写入 NAS consumption。临时本地测试才使用 `--use-local-runtime`。

repo 内只保留小型 handoff / pointer，不内嵌大 JSON、JSONL 或完整 report。需要读运行资产明细时，必须按精确路径、对象、claim 或 gap 读取；不要对 runtime 根目录做广义全文搜索。

## 回收

长期 prompt 增量不是永久豁免。满足任一条件时应回收：

- 对应规则已经沉淀到 schema / route table / validator。
- 最近回归包不再依赖该文字才能通过。
- 它只服务单个个案或低频对象族。
- 它增加了输出冗余、候选误路由或耗时。

回收优先顺序：删长例词，删重复解释，删可校验枚举说明，最后再压缩核心规则。

## 当前优先事项

1. 使用 `scripts/dev/retrieval_v3_prompt_governance.py run-root` 给宽包 run 建立 prompt budget 快照。
2. 使用 `scripts/dev/retrieval_v3_prompt_governance.py source-debt` 给 `retrieval_v3_candidate_prompt.py` 建立 prompt debt inventory，先识别可迁移内容，不直接删 prompt。
3. 将 source recall / 抽取优先级迁到 source discovery profile；推进到这一层时同步启动召回词采样治理，区分通用机制词、条件词、案例词和拒收词。
4. 将 AD / I5C 等有限枚举更多交给 schema 常量、validator 和 shadow report；prompt 只保留“不得输出正式 label / 数值”等硬边界。
5. 为每次宽包 report 增加 prompt size / shard size / token 指标对照。
6. 给 factorization prompt 建立同样的 prompt budget 快照。
7. 维护全链路 prompt debt 清单：新增原因、替代位置、回收条件。

`source-debt` 报告只作为迁移清单，不是自动裁决。`case_term_in_prompt` 为 block 级别；`source_recall_terms_in_prompt` 默认迁往 source discovery profile；`finite_enum_verbatim`、`route_table_verbatim` 和 `profile_schema_verbatim` 默认迁往契约常量、route table、schema 或 validator。只有迁移后回归包质量不退化，才允许删除对应长期 prompt 文本。

## 召回词采样治理

`scripts/dev/retrieval_v3_recall_term_sampler.py` 是 source discovery 层的只读采样工具。它默认只统计本地 `candidates.final.json` 或 run_root 的 `candidate_slices.matched_rule_terms`，按 `core_term`、`conditional_term`、`case_term`、`reject_term` 分层，并输出 support、target/object/document diversity、role family 命中和案例词拒收原因。需要从原文盲挖 2-4 字 ngram 时，必须显式使用 `--include-text-ngrams`；该模式有机制字门槛和官职/历日/语法残片拒收，但仍只作为探索报告，不直接作为长期 profile 候选。

需要评估候选词是否值得进入下一步 profile review 时，可加 `--include-candidate-ab`。该报告只在现有 candidate slices 上统计 `text_hit_count`、`already_matched_count` 和 `new_text_hit_count`，用于判断某个词是否可能带来新增候选命中；它不重跑抓源、不调用 judge，也不能替代 source-only A/B 或最终宽包回归。

需要把 A/B 结果交给人工复核时，可加 `--output-profile-patch <path>` 生成 `recall_term_profile_patch_template`。该模板只写 `review_status=pending` 和 `accepted_for_profile=false`，并可附带 `review_suggestion` / `review_flags` 帮助快筛；suggestion 不是裁决，不得被当作已审 discovery profile 直接投递。只有人工改为 `accepted_for_profile=true` 或 `review_status=accepted` 后，才允许进入后续 candidate-only / source-only 对照。

如果需要记录一次显式人工接受，可在生成模板时传 `--accept-term <词>`。这只会把输出 patch 中对应词标为 `review_status=accepted` / `accepted_for_profile=true` 并追加 `accepted_by_explicit_term_list`，仍不写正式 profile、不投递抓包任务。

召回词先按静态 taxonomy 分层，再用采样报告验证边界。`personnel_political_wide` 的先验长期机制词覆盖六组：任用授权（如 `任用`、`委任`、`倚重`、`留守`、`从其计`）、权力滥用机制（如 `专擅`、`擅权`、`威福`、`封事`、`不奏`、`径行`、`匿奏`）、荐举识拔（如 `荐举`、`举荐`、`拔擢`、`求贤`）、容谏保全（如 `纳谏`、`进谏`、`保全`、`宽宥`、`复用`）、反亲私朋党（如 `谮害`、`朋党`、`请托`、`纳贿`）和权力控制（如 `收兵权`、`削藩`、`罢相`、`废丞相`、`制衡`）。

条件词也先验分层：军事行动词如 `将兵`、`发兵`、`引兵`、`举兵`、`起兵`、`统兵` 必须带军事授权近邻 guard；处置风险词如 `谋反`、`伏诛`、`下狱`、`赐死`、`族诛`、`连坐` 必须带任相、宠任、专擅、中书、党羽等近邻 guard；权力基础上下文词如 `权臣`、`宗室`、`外戚`、`宦官`、`藩王`、`功臣` 必须带控制、军权或滥权近邻 guard。`刘基`、`总中书政` 等个案词和正文样式词直接拒收。

需要把已接受词整理成最小审阅清单时，可加 `--output-profile-delta <path>`。delta 只读取本次 patch 中 `accepted_for_profile=true` 的词；低风险机制词输出为 `rule_terms / append_unique`，处置风险词和军事行动词输出为 `conditional_rule_terms / append_guarded_terms` 并附带 `requires_near_any` guard，个案/样式词即使被误接受也只进入 reject policy 不产生 proposed update。它仍声明 `writes_profile=false`，不能直接当作 profile 写回或 prompt 删除依据。

需要查看 delta 落入 profile 后的形态时，用 `scripts/dev/retrieval_v3_discovery_profiles.py --profile <profile.json> --recall-term-delta <delta.json> --output-preview <preview.json>`。preview 会生成 `rule_terms` 和 `recall_term_overlays`，用于后续 source-only / candidate-only 对照；源 profile 不会被修改。

需要直接做 source-only 对照时，用 `--from-task <task.json> --recall-term-delta <delta.json> --output-task-preview <task.preview.json>` 生成临时 task preview，再分别把原 task 和 preview task 交给 `retrieval_v3_source_candidates.py`。task preview 只追加顶层 `rule_terms` 和 `recall_term_overlays`，不覆盖原 task。

source candidate 产物生成后，用 `retrieval_v3_recall_term_sampler.py --source-ab-base <base.candidates.json> --source-ab-overlay <overlay.candidates.json> --source-ab-accepted-term <词> ... --output-source-ab-json <report.json> --output-source-ab-md <report.md>` 固化差异。报告只比较本地 `candidate_slices`，统计新增/减少切片、matched term 变化和 accepted term 新命中，不调用 judge；同时输出 `term_policy_recommendations`，区分可裸加的 `append_rule_term` 和必须带近邻条件的 `conditional_term`。

当前阶段的采样治理以降低 prompt 负担为目标，不追求把所有高频 ngram 都收入 profile。采样工具先用静态 taxonomy 判定长期机制词、条件词、上下文词和拒收词；再用句子残片过滤压低 `needs_taxonomy_review` 噪声。`分兵`、`屯田`、`军中` 等军事/行政背景词归为 `context_only`，不作为 personnel profile 长期召回词；`可与言乎`、`陛下乃疑`、`杀彭`、`某公言` 等半句 ngram 归为 `fragment_noise`。已知长期词和条件词优先判定，避免误伤 `信任`、`将兵`、`下狱`、`谋反`。

采样报告的用途是决定“哪些词可以进入候选 profile review”，不是自动改长期 prompt 或正式 discovery profile：

1. `reject_term` 不得进入长期 prompt 或长期 profile。
2. `case_term` 只用于一次性诊断、补抓或复核 worklist。
3. `conditional_term` 需要注明适用 role family，并先做 candidate-only A/B。
4. `core_term` 仍需人工 review 和小样本回归，确认不会显著增加噪声后才可进入 source discovery profile。

召回词治理的验收顺序固定为：采样报告 -> 人工确认候选词 -> candidate-only A/B -> prompt budget / quality gate 对照 -> 再考虑删除 judge prompt 中的同类召回说明。

## 消费反馈动态纠偏

动态纠偏只允许走“消费反馈 -> 下一轮 overlay 建议 -> A/B 验收”的离线闭环，不允许抓包过程中自动改长期 prompt、正式 discovery profile 或 DB。消费端参与方式是输出稳定 JSONL 反馈，不反向接管抓包策略。

最小反馈字段：

```json
{
  "claim_id": "CLM-...",
  "recall_terms": ["宠任"],
  "candidate_lane": "I5B.appointment_delegation",
  "rule_code": "appointment_delegation",
  "consumption_status": "accepted | rejected | supporting_only | future_hint_only",
  "reject_reason": "missing_required_fact | weak_same_chain | wrong_lane | context_only | duplicate | low_source_quality",
  "factor_hint_used": true,
  "factor_hint_overridden": false
}
```

抓包端用 `scripts/dev/retrieval_v3_recall_feedback.py --feedback-jsonl <feedback.jsonl> --output-json <report.json> --output-md <report.md>` 汇总反馈。报告按词输出 `promote_next_run_terms`、`demote_terms`、`context_only_terms`、`needs_human_review_terms` 和 `observe_terms`；这些桶只代表下一轮 overlay 候选，不是 profile 写回结果。没有 `recall_terms` / `matched_rule_terms` / `source_terms` / `trigger_terms` 的反馈行只计入 `rows_without_terms`，不得用于自动建议。

反馈 term 必须尽量是短语级史料/机制词，不应只输出单字触发 token。`将`、`相`、`谋`、`诛`、`信`、`反` 这类单字只可作为内部匹配痕迹，抓包端会按 `feedback_token_noise` 降噪；`丞相`、`中书`、`都督`、`总兵`、`大将` 等官职/机构上下文词会按 `feedback_context` 处理。真正可用于 overlay 判断的词应尽量是 `宠任`、`专擅`、`伏诛`、`下狱`、`保全`、`直言`、`妄杀` 这类可复用短语。

动态纠偏验收边界：

1. 高消费率且低拒收率的长期词或条件词，只能建议进入下一轮 overlay。
2. 高拒收率、`context_only` 或已在 taxonomy 中拒收的词，只能降权或保留为上下文/噪声。
3. `wrong_lane`、factor hint 覆盖频繁或 taxonomy 未分类的词，进入人工 review。
4. overlay 通过 source-only / candidate-only A/B 且质量不退化后，才允许进入 profile delta。

`conditional_rule_terms` 不得裸注入 `rule_terms`。source candidate 层只读取 task preview 中的 `recall_term_overlays[].conditional_terms_not_injected`，并要求条件词附近窗口内命中 `guard.requires_near_any` 后才把该词追加到 `matched_rule_terms` / `matched_conditional_recall_terms`。同一切片内远距离共现不算 guard 命中，`其党` 这类词也不能用自身或自身子串充当 guard。
