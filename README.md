# 皇帝综合评价体系 V4

V4 是一次受控架构重启。它保留 V3 的历史经验、失败样本和业务规则来源，但不继承 V3 的长链编排、全表重建和脚本堆积。

> **评分标准最高驱动；历史事件优先；评分单元最小充分；增量失效优先；智能体只处理歧义。**

## 当前状态

- 分支：`retrieval-v4-event-first`
- 试点：李世民、刘邦、朱元璋
- 首条纵向切片：第五项 B `appointment_delegation`
- 模式：`offline-first + shadow-only`
- G3A Episode Core Registry：已通过隔离 PostgreSQL shadow 验证
- G3B Core Shadow Runner：已通过局部 semantic/evidence 失效与零写入重跑
- `appointment_delegation` scored shadow：4 个既有 RuleEvidenceUnit 已接入 V3 语义等价 shadow；6 项 V3 因子、5 条正负 factor material、确定性乘法公式与事件—人物密度聚合已完成
- V3 parity 增量复用：单个档位候选变化只重建对应 1 个 Judgment/Contribution，其余 3 个逐字段复用
- Factor Observation 资格门：`codex-win factorization-jsonl` 已完成首轮独立盲评；合同、lineage、正负材料结构和方向均通过，但档位仅 19/30 精确、存在 1 个非相邻错误，`real_agent_qualified=false`；延迟基准确定默认保持每批最多 4 单元，并在批间最多 4 路并发
- 模型固定复现：通过 `--respect-task-argv` 显式执行 `--model gpt-5.6-sol`，开发集为 20/30 精确，仍未达门槛；该复现不计为新资格盲评
- 新开放开发集：马周、张良、刘基、李善长已形成 4 个 V4 RuleEvidenceUnit 和 5 条正负材料；coverage-aware 对照为 28/29 已决档位精确、1 次正确拒判、零危险强判/错误拒判/非相邻/方向错误，`codex-win` 单批耗时 67.729 秒、总 token 24,863；该结果只用于调校，`real_agent_qualified=false`
- 封存资格集：房玄龄、李靖、萧何、徐达的 4 个评分单位已在 `3bfc9b6` 冻结后完成唯一一次盲评；25/30 档精确（83.33%）低于 85% 门槛，5 个偏差均为相邻档，决策状态、正负结构、方向与覆盖安全 Gate 全部通过；耗时 100.102 秒、总 token 26,152，未重跑且未回调 Gold/策略，`real_agent_qualified=false`
- 生产代表性抽样：现有 12 个已开封单元仅作回归证据；新的确定性抽样合同按 RuleEvidenceUnit 而非相关因子标签计数，规划 12 个开放开发槽位和 8 个匿名 sealed 槽位，覆盖 7 个时代族及角色、正负结构、归责、连续性、史源和 coverage 难点；20 个槽位尚未绑定候选或回源，当前不得声称具有生产代表性
- 通用证据覆盖 Gate：`appointment_delegation` 与 `talent_discovery` 共用 `rule-factor-evidence-coverage-v1`；开放快照允许直接正证据确认，但禁止以“未找到”强推一次性、从未发生等缺失敏感档位，覆盖不足必须退出为 `insufficient_coverage`
- shadow 差异评审：已证明 1 个因子变化只局部失效 1 个评分单元，其余 3 个 Judgment/Contribution 精确复用
- 名单式离线入口：三位皇帝、四位臣子的 roster manifest 已贯通 Source Cache/Claim Extractor 快照、Episode Kernel 和 scored runner
- 包 C 持久化增量编排：已记录逐人物 stage、response hash、delta Episode、慢通道任务和失败恢复；无变化重跑复用同一记录
- 包 D 发现链补抽：V4 Claim Extractor 已按 `talent_discovery` 抽出魏徵旧阵营、识才依据、跨障碍与转化任用 4 条 Claim；陈平、魏徵各形成 1 个正向贡献，韩信与蓝玉按规则排除
- 包 D 名单增量复用：`talent_discovery` 已接入包 C 的持久化 roster 入口；无变化精确复用，新增魏徵 Assertion 只重建 1 个单元并复用其余 3 个 Judgment
- V4 配套服务源码治理：已接受“同一 Git 历史、按现有包边界选择性迁入”的章程；当前服务 release 仍在旧冻结点分出的过渡分支，禁止整体 merge，待按合同测试逐步迁入
- V4 Source Cache 迁移：版本化请求、通用 SourceRevision、不可变 document/passage、fixture/真实 Wikisource adapter、PostgreSQL repository、job/lease worker 和 20 文件不可变 release 已进入当前 Git 历史；隔离服务器 Gate 已验证幂等、过期 lease 恢复与回滚
- V4 Claim Extractor 选择性迁入：旧 `rule_code` 提示分支已改为版本化 `talent_discovery_chain_v1` profile；v2 application、独立 PostgreSQL repository、job/lease 和当前 21 文件 release 已通过服务器隔离 Gate，冻结响应形成 4 条带 PassageSupport 的 Assertion
- V4 Claim Extractor 真实 provider shadow：改用 V4 Source Cache 三 passage 后生成 7 条 draft Assertion，四项发现链齐备，主簿重叠证据按 equivalent evidence 合并语义；未授权人物称谓保留原文并进入身份 slow lane
- 服务规模化 hardening：已完成按 job profile 路由、lease 覆盖模型 timeout、显式空结果、服务端稳定 draft identity、可信 subject 路由、Codex 子进程隔离、provider 模型/Prompt/Schema 策略进入缓存身份，以及 64 条输出饱和失败关闭；确定性 Claim 分片、结构化 coverage gap、多实例 worker 和 JudgmentObservationJob 仍待实现与资格测试，最新代码尚未切换服务器不可变 release
- 正式 45 分映射、排名、评分 worker 和生产切换：尚未开放

当前实现已经证明：

```text
SourcePassage / Assertion
→ HistoricalEpisode
→ 评分必要 Relation 或 scoring-arc-only
→ RuleEvidenceUnit draft
→ Projection draft
→ 有限 factor option proposal（智能体/人工不得写数值）
→ deterministic V3 factor mapping / Judgment
→ shadow ScoreContribution / 皇帝级只读汇总
```

统一命令已经能从冻结 manifest 生成三位皇帝的可追溯 scored shadow 报告，并能比较基线与候选因子观察的局部失效范围。两条命令均为离线、零模型、零数据库写入和非正式接受。

Windows 仓库根目录先设置源码路径：

```powershell
$env:PYTHONPATH = "src"
```

```bash
python -m emperor_v4.eval appointment-delegation-shadow --manifest eval/appointment_delegation_scored_demo/manifest.yml --output eval/appointment_delegation_scored_demo/report.json
python -m emperor_v4.eval appointment-delegation-v3-parity-shadow --manifest eval/appointment_delegation_v3_parity_demo/manifest.yml --output eval/appointment_delegation_v3_parity_demo/report.json
python -m emperor_v4.eval appointment-delegation-factor-worklist --source-manifest eval/appointment_delegation_scored_demo/manifest.yml --output tmp/appointment_delegation_factor_worklist_v2.json
python -m emperor_v4.eval appointment-delegation-factor-gold --worklist eval/appointment_delegation_factor_agent_qualification/worklist_v2.json --parity-gold-manifest eval/appointment_delegation_v3_parity_demo/manifest.yml --source-manifest eval/appointment_delegation_scored_demo/manifest.yml --sample-role open_development --output tmp/appointment_delegation_factor_gold_v2.json
python -m emperor_v4.eval appointment-delegation-factor-batch-plan --source-manifest eval/appointment_delegation_scored_demo/manifest.yml --max-units-per-batch 4 --max-workers 4 --output tmp/factor_batch_plan.json
python -m emperor_v4.eval appointment-delegation-shadow-diff --request eval/appointment_delegation_scored_demo/shadow_diff_request.yml --output eval/appointment_delegation_scored_demo/shadow_diff_report.json
python -m emperor_v4.eval appointment-delegation-roster-shadow --manifest eval/appointment_delegation_roster_demo/manifest.yml --output eval/appointment_delegation_roster_demo/report.json
python -m emperor_v4.eval appointment-delegation-roster-shadow --manifest eval/appointment_delegation_roster_demo/manifest.yml --prior-record eval/appointment_delegation_roster_demo/report.json --state eval/appointment_delegation_roster_demo/state.json --output eval/appointment_delegation_roster_demo/report.json
python -m emperor_v4.eval talent-discovery-shadow --manifest eval/talent_discovery_scored_demo/manifest.yml --output eval/talent_discovery_scored_demo/report.json
python -m emperor_v4.eval talent-discovery-roster-shadow --manifest eval/talent_discovery_roster_demo/manifest.yml --output eval/talent_discovery_roster_demo/report.json
python -m emperor_v4.eval talent-discovery-roster-shadow --manifest eval/talent_discovery_roster_demo/manifest.yml --prior-record eval/talent_discovery_roster_demo/report.json --state eval/talent_discovery_roster_demo/state.json --output eval/talent_discovery_roster_demo/report.json
python -m emperor_v4.runtime.source_cache --request eval/source_cache_v4_demo/request.yml --fixture-plan eval/source_cache_v4_demo/fixture_plan.yml --state eval/source_cache_v4_demo/state.json --service-release-sha f7022cb39a887325e3719f46188602ab52775905 --output eval/source_cache_v4_demo/rerun_report.json
python -m emperor_v4.runtime.source_cache_shadow --request eval/source_cache_v4_demo/request.yml --plan eval/source_cache_v4_demo/fixture_plan.yml --baseline-report eval/source_cache_v4_demo/report.json --service-release-sha f7022cb39a887325e3719f46188602ab52775905 --output eval/source_cache_v4_demo/wikisource_shadow_report.json
```

## 下一份可见成果

V3 语义等价 scored shadow 和两轮开发集仍只作回归证据。生产代表性合同已把统计单位固定为 RuleEvidenceUnit，并形成 32 单元组合：12 个已开封回归单元、12 个新开放开发槽位和 8 个未来 sealed 槽位。新槽位覆盖既有集合完全缺失的朝代范围、纯负向材料、监督或非正式角色、压缩/多源/冲突史源、缺结果与覆盖不足场景；sealed 槽位只暴露结构配额，不暴露人物和预期档位。下一步是：

1. 保持每批最多 4 个评分单元、批间最多 4 路并发，以墙钟耗时为主要性能目标并完整记录 token；
2. 先为 12 个开放开发槽位绑定候选人物和史料定位，经 V4 回源、最小充分 Episode 构单与人工结构审查后，再生成 Gold；V3 只能提供只读定位线索；
3. 开放开发集重点校准 `direct`/`direct_under_pressure`、`stable`/`long_term_multi_stage` 和 `standard`/`complete_direct_chain`，同时验证新史源和负向结构没有引入新的系统误差；
4. 开放候选与策略冻结后才为 8 个 sealed 槽位绑定不同人物；仍按 `>= 85%` 已决档位精确率、`100%` 决策状态与材料侧结构、零错误强行落档、零错误拒绝、零方向错误和零非相邻错误资格测试；
5. 20 个新单元按每批 4 单元预计 5 次模型调用、最多 4 路并发和 2 个波次；当前观测基线估算纯模型墙钟约 200.204 秒、总 token 约 130,760，不包含人工回源和 Gold 审查；
6. 保持 `shadow_demo_only`，不引入 45 分映射、排名或生产评分写入。

在上述硬化形成可运行结果前，不新增字母阶段、镜像测试模块或独立阶段总结文档。

## 用户目标链路

目标交互保持为：

```text
皇帝 / 臣子名单
→ 离线史源缓存（允许预热）
→ 相关史料与 Assertion 抽取
→ HistoricalEpisode
→ 按评分规则生成 RuleEvidenceUnit
→ 规则内有限因子赋值
→ 确定性计分与追溯报告
```

首条规则打通后，再扩展：

- `talent_discovery`
- `team_building`
- `tolerate_talent`
- `anti_nepotism`

规模化只允许复用稳定契约、缓存和增量任务；不得复制五套独立流水线。

配套服务源码迁移与评分规则扩展并行推进。Source Cache 与 Claim Extractor 已完成服务器不可变 cutover，并通过首条真实服务 job 观察。数据库复用早期 G3A 已创建的 `emperor_eval_v4`；Source Cache 经 1 次 Wikisource 请求写入 1 个 document revision 和 3 个 passages，Claim 经状态目录权限修复后在第 2 次 attempt 生成 7 条 draft assertions。两项重复投递均为零写，最小权限服务角色无权写 `public` 正式表。Live drafts 与先前 shadow 覆盖相同七个事实概念，但措辞和 semantic key 不做字面复现，因此仍是 `passed_for_draft_only`，不自动成为正式 Assertion。两个 timer 保持启用，V3、正式评分和排名未改变；服务收口后回到 `team_building` scored shadow 复用。

上述线上观察仍对应旧不可变 release。当前分支的规模化 hardening 只有在 focused/full pytest、隔离 PostgreSQL migration、不可变 release 校验和明确 cutover 后才会影响服务器运行；不得把 Git 分支更新解释为已部署。

## 核心阅读顺序

1. `docs/项目总纲/皇帝综合评价体系评分标准.md`
2. `docs/00-V4项目章程.md`
3. `docs/项目总纲/总规则.md`
4. `docs/02-领域模型.md`
5. `docs/03-证据与历史事件模型.md`
6. `docs/04-规则输入类型与投影模型.md`
7. `docs/05-任务状态机与增量失效.md`
8. `docs/06-覆盖度与验收标准.md`
9. `docs/09-V4测试与验证策略.md`
10. `docs/31-G3R评分最小充分Relation重解释.md`（当前实现摘要）
11. `docs/contracts/` 与当前分项规则

历史盲测和阶段审计不是日常阅读入口。

## 不可妥协约束

- `SourcePassage` 是可定位史料片段，`Assertion` 是来源断言，`HistoricalEpisode` 是事件型规则的核心语义主体。
- 同一事件可以有多份史料，但只能有一个当前 canonical episode。
- 语义版本和证据版本分离；新增同义证据不得默认触发重判。
- 人物、事件、评分单元、Projection、Judgment 和 ScoreContribution 各自有稳定身份与版本。
- 正常增量不得触发全库、整皇帝或整规则重建。
- 模型不能建立正式历史事实、正式判断或正式分数。
- 无变化重跑必须零模型调用、零业务写入。
- V3 与 V4 数据库、队列和发布链严格隔离。

## 当前 Gate

- G2-Core / S1—S3：`passed_for_shadow_implementation`
- 历史精细 Relation / S4：`deferred_not_qualified`，只约束精细知识图发布
- G3A：`passed_shadow_registry`
- G3B：`passed_sync_local_invalidation`
- G3R 评分最小充分 Relation：`passed`
- G3C RuleEvidenceUnit shadow：`passed`
- G3D—G3H Judgment readiness 与 delta：`passed_shadow_only`
- Factor schema：`passed_shadow_demo_only`
- V3 semantic parity factor/schema/formula：`passed_shadow_demo_only`
- Factor Judgment proposal contract：`passed_shadow_demo_only`
- Deterministic Judgment evaluator：`passed_shadow_demo_only`
- ScoreContribution：`passed_shadow_demo_only`
- Integrated scored shadow runner：`passed_shadow_demo_only`
- Shadow difference review runner：`ready_for_human_review`
- Offline roster scored runner：`passed_cache_ensure_shadow`
- Persistent incremental orchestration：`passed_shadow_runtime`
- Claim cache policy/saturation hardening：`code_ready_pending_full_test_and_cutover`
- Claim sharding / structured gaps / worker tiers：`not_implemented_or_qualified`
- Factor Observation agent：`independent_blind_run_completed_not_qualified`
- 正式评分和生产切换：`blocked`
