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
- `appointment_delegation` scored shadow：有限 factor schema、确定性 Judgment、4 个 shadow ScoreContribution 与统一 runner 已完成
- shadow 差异评审：已证明 1 个因子变化只局部失效 1 个评分单元，其余 3 个 Judgment/Contribution 精确复用
- 名单式离线入口：三位皇帝、四位臣子的 roster manifest 已贯通 Source Cache/Claim Extractor 快照、Episode Kernel 和 scored runner
- 包 C 持久化增量编排：已记录逐人物 stage、response hash、delta Episode、慢通道任务和失败恢复；无变化重跑复用同一记录
- 包 D 发现链补抽：V4 Claim Extractor 已按 `talent_discovery` 抽出魏徵旧阵营、识才依据、跨障碍与转化任用 4 条 Claim；陈平、魏徵各形成 1 个正向贡献，韩信与蓝玉按规则排除
- 包 D 名单增量复用：`talent_discovery` 已接入包 C 的持久化 roster 入口；无变化精确复用，新增魏徵 Assertion 只重建 1 个单元并复用其余 3 个 Judgment
- V4 配套服务源码治理：已接受“同一 Git 历史、按现有包边界选择性迁入”的章程；当前服务 release 仍在旧冻结点分出的过渡分支，禁止整体 merge，待按合同测试逐步迁入
- V4 Source Cache 迁移：版本化请求、通用 SourceRevision、不可变 document/passage、fixture/真实 Wikisource adapter、PostgreSQL repository、job/lease worker 和 20 文件不可变 release 已进入当前 Git 历史；隔离服务器 Gate 已验证幂等、过期 lease 恢复与回滚
- V4 Claim Extractor 选择性迁入：已把旧 `rule_code` 提示分支改为版本化 `talent_discovery_chain_v1` extraction profile；冻结 `e27bbff` 响应以零模型、零数据库 shadow 复现 4 Claim / 4 Assertion
- 正式 45 分映射、排名、worker 和生产切换：尚未开放

当前实现已经证明：

```text
SourcePassage / Assertion
→ HistoricalEpisode
→ 评分必要 Relation 或 scoring-arc-only
→ RuleEvidenceUnit draft
→ Projection draft
→ 有限 factor values
→ deterministic Judgment
→ shadow ScoreContribution / 皇帝级只读汇总
```

统一命令已经能从冻结 manifest 生成三位皇帝的可追溯 scored shadow 报告，并能比较基线与候选因子观察的局部失效范围。两条命令均为离线、零模型、零数据库写入和非正式接受。

```bash
python -m emperor_v4.eval appointment-delegation-shadow --manifest eval/appointment_delegation_scored_demo/manifest.yml --output eval/appointment_delegation_scored_demo/report.json
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

scored shadow demo、首轮因子差异裁定、名单入口、包 C 持久化增量编排，以及包 D 的 `talent_discovery` Claim 补抽、评分和 roster 增量复用均已完成。包 D 下一步是：

1. 以同一通用内核扩展 `team_building`，不复制独立流水线；
2. 先冻结团队快照、团队成员集合和单人事件的去重边界；
3. 保持 roster 增量、Claim/Assertion lineage 和跨规则重复结算审计；
4. 保持 `shadow_demo_only`，不引入 45 分映射、排名或生产评分写入。

在人工差异评审形成明确结论前，不再新增字母阶段、镜像测试模块或独立阶段总结文档。

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

配套服务源码迁移与评分规则扩展并行推进。Source Cache 已在服务器独立临时数据库完成 migration、无变化复用、过期 lease 回收和不可变 release 前进/回滚演练，临时库已删除，历史 unit 与生产指针均未切换。Claim Extractor 已完成 extraction profile 与冻结响应 shadow；下一 Gate 是 v2 application/job/release 纵切，正式 cutover 仍须等待两项服务共同通过。

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
- Deterministic Judgment evaluator：`passed_shadow_demo_only`
- ScoreContribution：`passed_shadow_demo_only`
- Integrated scored shadow runner：`passed_shadow_demo_only`
- Shadow difference review runner：`ready_for_human_review`
- Offline roster scored runner：`passed_cache_ensure_shadow`
- Persistent incremental orchestration：`passed_shadow_runtime`
- 正式评分和生产切换：`blocked`
