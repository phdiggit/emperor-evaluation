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

V3 语义等价 scored shadow 已复用现有 SourcePassage、Assertion、HistoricalEpisode、RuleEvidenceUnit 与四维 Judgment readiness 观察。首轮独立 Factor Observation 盲评已由 `codex-win` 在禁用智能体网络工具、数据库和 Git 上下文的权限画像下运行；材料正负结构为 4/4、归因与规则上下文档位全部命中，但总精确率只有 63.33%，未通过 85% 门槛。随后用 `--respect-task-argv` 明确固定 `gpt-5.6-sol` 做开发集复现，精确率为 66.67%，仍有 1 个非相邻错误；该复现强制 `real_agent_qualified=false`。由于四单元 Gold 已用于对照，不能继续把同一集合当作独立资格集。下一步是：

1. 保持每批最多 4 个评分单元、批间最多 4 路并发，以墙钟耗时为主要性能目标并完整记录 token；
2. 把当前四单元冻结为策略开发集，针对任用效果、持续性和史源完整度修订 option guidance，保留已命中的归因和规则上下文定义；
3. 冻结新策略后另建未参与调校的 sealed holdout，再按 `>= 85%` 精确率、`100%` 材料侧结构、零方向错误和零非相邻错误重新资格测试；
4. 保持 `shadow_demo_only`，不引入 45 分映射、排名或生产评分写入；
5. Claim 侧已完成缓存身份、饱和门禁和错误分类硬化；分片、结构化 gap 与 worker tier 不与本轮评分质量 Gate 混线。

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
