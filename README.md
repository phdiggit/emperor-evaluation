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
- G3R—G3H：已形成评分最小充分 Relation、4 个 RuleEvidenceUnit draft、4 个 Projection/Judgment shadow candidate；其中 1 个 `positive`、3 个 `mixed`、0 个 evidence blocker
- 正式 factor values、ScoreContribution、排名、worker 和生产切换：尚未开放

当前实现已经证明：

```text
SourcePassage / Assertion
→ HistoricalEpisode
→ 评分必要 Relation 或 scoring-arc-only
→ RuleEvidenceUnit draft
→ Projection draft
→ Judgment readiness / shadow direction
```

但仓库还没有一条统一命令，把“名单与服务输出”直接跑成可阅读的评分报告。`src/emperor_v4/eval.py` 仍主要是早期分段命令，新 G3R—G3H 模块尚未接成一个纵向 runner。

## 下一份可见成果

下一交付物不是 G3I、G3J、G3K 三份新阶段文档，而是一个可运行的 `appointment_delegation` scored shadow demo。它必须在同一职责链中完成：

1. 批准四个有限因子：`person_task_fit`、`authority_clarity`、`feedback_handling`、`attributable_outcome`；
2. 实现确定性 Judgment evaluator，歧义项才进入智能体慢通道；
3. 批准最小 ScoreContribution 合同与公式版本，不引入完整总榜公式；
4. 建立一个统一 runner，从冻结服务输出或名单 manifest 生成 Episode、RuleEvidenceUnit、因子、贡献值和完整 lineage 报告；
5. 用李世民、刘邦、朱元璋各至少一条正向、负向或 mixed 案例展示结果。

这五项完成前，不再新增字母阶段、镜像测试模块或独立阶段总结文档。

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
- Factor schema：`pending`
- Deterministic Judgment evaluator：`pending`
- ScoreContribution：`pending`
- Integrated scored shadow runner：`pending`
- 正式评分和生产切换：`blocked`
