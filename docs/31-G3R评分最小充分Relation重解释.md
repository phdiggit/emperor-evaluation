# `appointment_delegation` 评分最小充分 Shadow 实施摘要

> 状态：`persistent_roster_shadow_ready_second_rule_reuse_next`
>
> 日期：2026-07-13
>
> 实现基准：`13ea96e5b0d42c9a6d86c8ba516ad6cfc1b08f16`

## 1. 结论

V4 已完成以下 shadow 链：

```text
Episode endpoint proposals
→ 评分必要 Relation / scoring-arc-only
→ RuleEvidenceUnit draft
→ Projection draft
→ Judgment readiness / shadow direction
→ 缺口定向输入
→ RuleEvidenceUnit delta
→ 局部 Projection 重建与 Judgment 复用
```

当前结果：

- 15 项 endpoint direct proposal；
- 13 项宽口径 Relation proposal；
- 2 项 `scoring_arc_only`；
- 0 项评分语义 unresolved；
- 4 个 `appointment_delegation` RuleEvidenceUnit draft；
- 4 个 Projection draft；
- 4 个 Judgment shadow candidate；
- 方向为 1 个 `positive`、3 个 `mixed`；
- `blocked_evidence=0`；
- Episode 重复消费为 0；
- 正式 Relation、RuleEvidenceUnit、Projection、Judgment、45 分得分和数据库业务写入均为 0；4 个 ScoreContribution 仅限 `shadow_demo_only`。

这说明评分单元与增量 readiness 已具备原型，但还没有形成可交付的评分结果。

## 2. 评分最小充分 Relation

评分必要关系使用：

```yaml
relation_family: authority_change | mandate_or_outcome | explicit_causal
relation_direction:
scope_match:
same_scoring_arc: yes | no | uncertain
ruler_responsibility: direct | partial | none | uncertain
evidence_directness: explicit | strongly_implied | trajectory_only
fine_type:
fine_type_status: resolved | not_required_for_scoring
evidence_assertion_refs: []
```

`proposed_relation` 只用于逐对关系确实改善评分归责、方向、结果、去重或追溯的情况。`scoring_arc_only` 表示两个 Episode 属于同一评分决策弧，但不值得制造一条历史关系边。粗关系足以评分时，`fine_type=null` 合法。

## 3. RuleEvidenceUnit

评分 links 组成 7 个候选分量。规则边界审查后形成 4 个 RuleEvidenceUnit draft，排除 3 个不适用分量，0 unresolved。每个 draft 声明皇帝、人物、决策弧、Episode 成员角色、证据和四个 readiness 问题：

```text
delegation_quality
supervision_quality
correction_timeliness
net_effect
```

`evidence_gap` 不是负向判断，也不是零分。

## 4. Projection 与 Judgment readiness

首轮 Judgment shadow 使用四个观察维度：

```text
person_task_fit
authority_clarity
feedback_handling
attributable_outcome
```

当前观察值仅用于 readiness：

```text
positive_signal
negative_signal
mixed_signal
evidence_gap
not_applicable
```

定向补证与 delta 后，3 个变化单元重建 Projection，1 个未变化 Projection 与 Judgment review 逐字段复用；4 个 Projection 均通过 readiness，形成 1 个 positive 与 3 个 mixed candidate。

## 5. 当前代码边界

活动实现：

- `relation_scoring_arc.py`
- `rule_evidence_shadow.py`
- `judgment_source_gap.py`
- `source_gap_input_gate.py`
- `rule_evidence_delta.py`
- `projection_judgment_shadow.py`
- `projection_readiness_rerun.py`

这些模块已经由 `src/emperor_v4/eval.py` 的 `appointment-delegation-shadow` 命令串成统一、离线、零模型的 scored shadow 重放链。Relation v2 合同使用实际 Episode semantic version 形成端点版本引用，并把皇帝责任与证据直接性纳入 Relation 语义身份；缺失或不一致的版本身份一律 fail closed。source-gap input gate v2 对 `not_found_stop` 项逐项跳过并保留审计记录，不再阻断同一清单中的可继续候选。

G3R—G3H 回归测试已按业务不变量合并到 `test_contracts.py`、`test_versioning.py` 和 `test_vertical_slice.py`，不再保留按微阶段镜像的测试模块。

## 6. 当前差异评审边界

以下纵向职责链已经完成：

1. 将四个观察维度升级为人工批准的有限 factor schema；
2. 实现确定性 Judgment evaluator；
3. 设计最小 ScoreContribution 公式、幂等键与版本；
4. 建立统一 `appointment_delegation` shadow runner；
5. 输出李世民、刘邦、朱元璋可追溯的 scored demo 报告。

差异评审已经形成首个人工口径结论：`authority_clarity` 只评价最终授权结果，韩信齐王授权记为 `positive`；请求、劝说和压力调整不降低该因子，也不另生成纳谏贡献。

名单式离线入口现可从三皇帝、四臣子 manifest 依次验证 Source Cache 与 Claim Extractor 冻结快照、运行确定性 Episode Kernel，并生成 scored shadow。首次运行处理 87 条 Assertion、78 个 Episode candidate、4 个评分单元；提供 prior record 时，无变化输入直接精确复用同一运行记录。

包 C 已增加持久化逐人物状态、服务响应 hash、变化 Episode 与 RuleEvidenceUnit 清单、慢通道 review job、原子 state 写入和故障后恢复。当前缓存无变化，因此服务调用、模型调用和数据库业务写入均为 0。

包 D 的首个复用切片已抽出通用有限因子 scored-shadow 内核，`appointment_delegation` 与 `talent_discovery` 均通过薄规则配置使用同一校验、Judgment、ScoreContribution、lineage 和汇总职责链。V4 Claim Extractor `claim_extraction_only:v9_talent_discovery` 已从缓存史料为魏徵补抽旧阵营、识才依据、跨障碍和转化任用 4 条 Claim，并通过既有 adapter 形成 Assertion；陈平和魏徵各生成 1 个 positive shadow contribution，韩信齐王授权与蓝玉晋升只作规则排除上下文。跨规则审计明确将 `appointment_delegation` 标为 supporting-only，不重复结算职位适配、授权质量或后续战果。

`appointment_delegation` 现已增加 V3 语义等价 shadow，不再把四项 readiness 观察直接按 `-1/0/+1` 等权平均。新链复用原有 4 个 RuleEvidenceUnit、Assertion lineage 和观察 fingerprint，从 Judgment 起局部失效；factor proposal 只允许提交有限 option code、理由和 Assertion refs，禁止携带数值。确定性层恢复 `appointment_importance × appointment_effect × continuity_factor × evidence_factor`、单材料封顶和正负侧事件—人物密度聚合。蓝玉决策弧在一个 Judgment 内拆为前期成功与后期授权控制负向两条 factor material，避免 mixed 被压成零分；陈平、韩信、魏徵也不再因同向观察机械同分。

Factor Observation 资格 harness 已形成同一纵向链：从现有 V4 judge 观察、事件摘要和 Assertion lineage 生成不含 V3 Gold、旧 proposal、数值映射与分数的四单元 worklist；响应校验只接受完整有限档位、理由、lineage 和方向一致的正负材料。对照器在调用后才读取人工 V3 校准，并执行 85% 档位精确率、100% 材料侧结构、零方向错误和零非相邻错误门槛。

首轮真实盲评由 `codex-win 0.1.0` 的 `factorization-jsonl` preset 调用 ChatGPT 登录下的 Codex CLI，权限画像禁止智能体使用网络工具、数据库、Git 读写和 Git snapshot。实际安全命令使用 `--ignore-user-config` 且未显式传入 `--model`；响应中的 `gpt-5.6-sol` 只是未外部验证的自声明，不能作为运行时模型证明。前两次输出仅因合同字段错误被拒绝且未读取 Gold；第三次监管与业务合同均通过。对照结果为 19/30 精确、10 个相邻错误、1 个非相邻错误，正负材料结构 4/4、方向错误为零。归因与规则上下文均为 5/5；主要偏差集中在任用效果、持续性和史源完整度，蓝玉负向效果被从人工 `poor_result` 高估为 `structural_continuing_damage`。因此 `real_agent_qualified=false`，四单元从此只作策略开发集，不再作为新的独立资格集；下一 Gate 是修订 guidance、冻结策略并建立新 sealed holdout，且任务命令必须显式固定模型。正式 45 分映射与排名继续阻断。

随后通过 `codex-win --respect-task-argv` 显式固定 `--model gpt-5.6-sol` 完成一次开发集复现，监管命令、任务快照和执行审计均能外部证明模型参数。结果为 20/30 精确、9 个相邻错误、1 个非相邻错误，正负结构和方向仍全部通过；重要性从首轮 3/5 降为 1/5，效果、持续性和史源各为 3/5，说明单次采样波动存在，但档位边界问题仍是主因。该响应使用 `development_replay_after_gold_opened`，即使达到阈值也不会产生 qualified 状态。

耗时优先基准进一步比较同一四单元 workload 的 `1×4`、`2×2` 并发和 `4×1` 并发：墙钟分别为 67.544、48.747、30.283 秒，但后两者 token 分别增加 76.64% 和 195.44%，且本次拆分没有改善档位质量。运行策略因此采用“每批最多 4 单元、批间最多 4 路并发”，不把单单元调用设为默认；完整审计只保留在 `eval/appointment_delegation_factor_agent_qualification/latency_benchmark.json`。

2026-07-14 起资格链切换到 coverage-aware Gold v2。当前开放开发 Gold 中 30 个因子判断拆为 29 个已决档位和 1 个正确拒绝落档；Gate 另行阻断覆盖不足却强行落档和已有正证据却错误拒绝。首批 8 个新候选在任何候选模型运行前冻结为 4 个开放开发单元和 4 个 sealed holdout；计划只记录人物、史料定位与输入 hash，不记录密封组预期档位。V3 fixture 仅作只读定位线索，候选必须重新经过 V4 构单和人工 Gold 审查后才能进入资格链。

开放开发四单元随后形成可运行的 V4 SourcePassage—Assertion—Episode—RuleEvidenceUnit 链。`codex-win` 以单个四单元批次、显式 `gpt-5.6-sol` 和无网络/数据库/Git 权限运行 67.729 秒，消耗 input 21,757、cached input 0、output 3,106、reasoning output 168，总 token 24,863。首次对照为 26/29 已决档位命中；人工复核后纠正两处 Gold 责任域错误，最终为 28/29、1 个相邻错误，决策状态 30/30、材料结构 4/4，且零危险强判、错误拒判、非相邻和方向错误。该数据已开封，只能证明策略开发门通过；正式资格仍只允许使用预先冻结且尚未向模型展开的房玄龄、李靖、萧何、徐达 sealed holdout。

房玄龄、李靖、萧何、徐达 sealed holdout 的 SourcePassage—Assertion—Episode—RuleEvidenceUnit、人工 Gold、盲评 worklist 和资格对照在模型运行前由 `3bfc9b6` 冻结。`codex-win` 随后只执行一次显式 `gpt-5.6-sol` 四单元盲评，权限继续禁止网络、数据库和 Git 读写；运行耗时 100.102 秒，消耗 input 22,685、cached input 0、output 3,467、reasoning output 553，总 token 26,152。结果为 25/30 精确，即 83.33%，低于 85% 门槛；5 个错误均为相邻档，归责 2 个、连续性 2 个、史源 1 个，决策状态 30/30、材料结构 4/4，且零危险强判、错误拒判、非相邻和方向错误。因此 `real_agent_qualified=false`。该 sealed holdout 已开封，禁止重跑、修改其 Gold 或据此降低门槛；后续只能在新开放样本上校准上述三类档位边界，再冻结策略并另建全新 sealed holdout。

生产代表性不再以同一材料内的 6 个相关因子判断充当独立样本。`appointment_delegation_factor_representativeness_v1` 以 RuleEvidenceUnit 为统计单位，将现有 12 个已开封单元明确限定为回归证据，并规划 12 个新开放开发槽位和 8 个匿名 sealed 槽位。组合配额覆盖 7 个时代族、5 类角色、纯正向/纯负向/正负混合结构，以及普通直接归责、压力取舍、多主体归责、短期/稳定/跨阶段/缺失敏感连续性、完整/标准/压缩/多源/冲突史源和 coverage 难点。确定性报告显示结构配额无缺口，但 20 个新槽位尚未绑定人物、回源或建立 Gold，因此 `qualification_claim_allowed=false`。按当前四单元批次基线预计需 5 次模型调用、2 个并发波次、纯模型墙钟约 200.204 秒和约 130,760 token；人工史源与 Gold 审查不在估算内。

随后 12 个开放开发单元完成回源、人工 Gold 和两轮策略校准，factor policy 冻结为 v4；最终开放门为 96/96 决策状态一致、12/12 连续性已决档位精确、总体已决档位 79/92 精确（85.87%），且零危险强判、错误拒判、跨档和方向错误。8 个新 sealed 单元在 `80f0de8` 冻结后只执行一次两批并行盲评，墙钟 107.369 秒、总 token 60,796；结果仅 5/8 单元材料侧结构一致，在可对齐的 54 个因子中已决档位 35/49 精确（71.43%），决策状态 52/54，虽仍为零危险强判、跨档和方向错误，但未通过资格门。该 sealed 已开封，禁止重跑、后调 Gold 或降低阈值。

至此组合中的 32 个 RuleEvidenceUnit 已全部开封，但“开封完成”不等于“生产代表性完成”。按候选实际史源和语义重新核对后，组合仍缺缺失敏感连续性、单次任务、多源 join 和冲突证据四个最低配额；正式资格和 45 分写入继续关闭。完整身份表、门禁结果与 13 个模型任务的耗时/token 汇总统一保存在 `eval/appointment_delegation_factor_representativeness/portfolio_32_opened_report.json`，不再新增阶段文档。

离线史源缓存与 Claim 抽取现已纳入 V4 配套服务源码治理：活动实现最终必须与 V4 位于同一 Git 历史，并按 `contracts/adapters/application/persistence/runtime` 现有边界选择性迁入。当前 `e27bbff` release 仍是过渡分支上的可追溯构建，禁止整体 merge；迁入时把按 rule code 分支的提示策略改为版本化 extraction profile，并在冻结请求 shadow 对比后完成不可变部署切换。

Source Cache 第一段重构性迁移已由 `32dbf81` 落入 V4 主线：复用既有 SourcePassage v2 与确定性切片器，新建通用 SourceRevision 合同、fixture provider、幂等 ensure 用例、shadow repository 和薄 runtime。固定 Wikisource revision `2020238` 首次生成 1 个不可变 document 与 3 个 passage；无变化重跑精确复用同一响应，provider、网络、模型和数据库调用均为 0。该结果只证明离线合同纵切，不等于真实 adapter 或服务器切换完成。

第二段由 `d439f63` 接入真实 Wikisource adapter、共享 source plan、refresh/content-version 测试和独立 `v4_source_cache` PostgreSQL repository/migration 合同。真实 API shadow 与固定 revision 的 document/passage identity、content hash、原文及 span 全部一致；refresh 的新 revision 产生新 document identity，旧结果仍可读取。PostgreSQL migration 尚未执行，job/lease、不可变发布和服务器 unit 切换仍属下一 Gate。

`f7022cb` 进一步修正 repository 写入合同：缓存响应之外必须持久化并可读回完整 `SourceRevisionContent.raw_text`，相同 document revision 或 passage identity 出现不同内容时 fail-closed。Shadow JSON 状态升级到 schema v2；PostgreSQL `document_revisions` 同步保存 source host、revision、retrieved time、raw content 和 content hash。

Source Cache runtime Gate 已由 `6149569` 通过：新增持久化 job/job_run、数据库幂等键、`ready/retry_wait` 领取、过期 `running` lease 显式回收和 ACK 前业务提交职责链。服务器使用独立临时 PostgreSQL 数据库完成 migration 首次应用/二次零写复用、1 个 document revision、3 个 passage、9436 字原文、终态不重跑与 lease 第二次 attempt；临时库随后删除。由同一干净 commit 构建的 20 文件 allowlist archive 通过 SHA-256 校验，并在隔离 `current-drill` 指针完成前进与回滚；生产指针、历史 unit、正式评分表均未改动。下一 Gate 转入 Claim Extractor 选择性迁入和冻结响应 shadow。

Claim Extractor 选择性迁入的首个切片没有搬运旧 worker：旧 `e27bbff` 改动被还原为一个 `talent_discovery` 提示分支，V4 将其改写为配置中的 `talent_discovery_chain_v1` extraction profile，显式声明四项发现链和禁止事后倒推。冻结响应通过既有 adapter 在零模型、零数据库、零服务器 unit 改动下复现 4 Claim / 4 Assertion；下一 Gate 才实现 v2 application、持久化 job 和独立 release。

Claim Extractor runtime Gate 已由 `5b19e47` 通过：v2 application 强制唯一 passage lineage 与 `PassageSupport`，旧 v1 冻结响应只能经过确定性兼容层进入；缺失 support、越界 passage、重复 Assertion 或幂等冲突均 fail-closed。独立 `v4_claim_extractor` schema 保存 request、Assertion draft、request linkage、job 和 job_run；服务器临时数据库验证首次 migration、二次零写复用、终态不重跑和过期 lease attempt 2 恢复。18 文件 allowlist release 完成隔离前进/回滚，临时库已删除，生产 unit 未切换。该 Gate 只证明冻结 provider 的运行合同，真实模型 provider 仍须用同请求 shadow 后才可 cutover。

真实模型 provider shadow 在 `c8e3fb7` 收口为 draft-only 通过。审计先发现旧冻结响应的 4 条 Assertion 中有 3 条 evidence span 越出其自带窄 quote，因此不再以追平旧 Claim 为目标；改用 V4 Source Cache 的 3 条 passage 后，最终生成 7 条 Assertion，覆盖两项前序任用、当场识才判断、跨障碍召见/质问和转化任用。重叠的詹事主簿证据共享 semantic key，并以完全一致 payload 的两条 `equivalent_evidence` 表达；战役、地理移动、封爵和后续一般任务均被排除。建德、隐太子、皇太子、太宗保持来源表面形式并留给身份 slow lane。该轮模型调用、数据库写入、正式 Assertion 写入和 unit 切换分别为 1、0、0、0；只批准服务 draft 能力，不批准正式事实。

`talent_discovery` 已进一步接入包 C 的持久化 roster 入口：三皇帝四人物名单复用 6 个 Claim snapshot、91 条 Assertion 和 82 个 Episode candidate；首次构建 4 个评分单元，无变化重跑精确复用同一记录。新增魏徵 Assertion 的局部 delta 只重建 `REU-LSM-WEIZHENG-DISCOVERY-v1`，其余 3 个 Judgment 精确复用；服务调用、模型调用和数据库写入均为 0。

在正式接受 Gate 通过前，仍不开放正式 Judgment、45 分档位、总榜或生产切换。

## 7. 历史审计

早期 fine-type Relation 失败继续保留在 `24-*` 至 `29-*` 历史审计中，只用于说明精细历史关系图尚未达到发布阈值。逐条 endpoint 展开和 G3C—G3H 微阶段说明已从长期文档层移除，结构化运行产物应保存在 `eval/` 或外部 artifact。
