# 皇帝综合评价体系 V4

V4 是一次受控架构重启。它保留 V3 的历史经验、失败样本和业务规则来源，但不继承 V3 的实现惯性、正式业务数据或生产运行链。

V4 的核心改变是：

> **历史事件优先，原子断言从属；增量失效优先，全表重建例外；确定性快通道优先，智能体只处理歧义。**

## 当前状态

- 分支：`retrieval-v4-event-first`
- 阶段：G2.6K0 开放开发资格；I/J 已通过 S1—S3，Relation/S4 阻断
- 试点：李世民、刘邦、朱元璋
- 首条纵向切片：第五项 B“用人与授权”中的 `appointment_delegation`
- 模式：`offline-first + report-only + shadow`
- 正式评分、排名和生产切换：全部关闭
- V3：release 与审计产物保留作只读对照；为避免争抢 wiki 流量，相关 worker 已按明确授权停止

当前已有离线 `src/emperor_v4`、轻量确定性测试、Graph evaluator 和试点 `eval` 产物；仍然**没有** V4 数据库、worker、migration、正式业务 scorer 或正式业务数据。

已证明：给定人工冻结 boundary、Gold linkage 与修复后的 evidence，Kernel 可以构造带 passage lineage 的 EpisodePacket。

G2.6E、G2.6G、G2.6H、G2.6I 与 G2.6J 均已失败冻结。G2.6J 对 7 个 singleton Gold Episode 达到 exact recall/precision 100%，但 31/38 passage 因缺主体/动作而只能作为 context，pairwise merge/split 无样本，2 条 candidate relation 均无 Gold 对应，且没有合格 `appointment_delegation` rule unit。该结果不能解释为 G2.6 通过。

当前已进入 G2.6K0，而不是继续制造新 blind holdout。Source Cache v2、section-aware deterministic slicer、S1—S5 机械早停和 8 场景离线 protocol smoke 已落地。I/J 的 source-v2 开发输入均通过 S1/S2。Boundary policy v2.10 修复跨 focal 硬分区后，I 的开放开发 episode recall/precision 为 100%/100%，J 为 87.5%/93.33%；两组均无灾难性合并、跨皇帝污染或 lineage 丢失，达到 S3 门槛。S4 严格关系 precision/recall 仅为 I 20.83%/21.74%、J 40%/25%，因此机械早停在 Relation graph；已冻结 Rule Gold 不被用于放行。PostgreSQL G3 和新 blind holdout 继续阻断。

## 文件树

```text
.
├─ .codex/config.toml
├─ AGENTS.md
├─ README.md
├─ config/
│  ├─ project.yml
│  ├─ pilot.yml
│  ├─ source-policy.yml
│  ├─ model-policy.yml
│  ├─ version-policy.yml
│  ├─ 君主别名.yml
│  └─ 所有君主.yml
├─ src/emperor_v4/
│  ├─ contracts/
│  ├─ domain/
│  ├─ application/
│  ├─ adapters/
│  └─ evaluation/
├─ tests/
├─ eval/
└─ docs/
   ├─ README.md
   ├─ 00-V4项目章程.md
   ├─ 01-V3教训与V4约束.md
   ├─ 02-领域模型.md
   ├─ 03-证据与历史事件模型.md
   ├─ 04-规则输入类型与投影模型.md
   ├─ 05-任务状态机与增量失效.md
   ├─ 06-覆盖度与验收标准.md
   ├─ 07-智能体边界与成本预算.md
   ├─ 08-V3并行运行与迁移方案.md
   ├─ contracts/
   │  ├─ 史源缓存服务契约.md
   │  ├─ 事实抽取服务契约.md
   │  ├─ 历史事件包契约.md
   │  └─ 规则判断结果契约.md
   ├─ 项目总纲/
   │  ├─ 皇帝综合评价体系评分标准.md
   │  └─ 总规则.md
   ├─ 证据规则/
   │  ├─ 证据裁量总则.md
   │  └─ 史料检索与回源工作流.md
   └─ 分项规则/第五项统治者政治素质/
      └─ B用人与授权.md
```

## 阅读顺序

1. `docs/项目总纲/皇帝综合评价体系评分标准.md`
2. `docs/00-V4项目章程.md`
3. `docs/项目总纲/总规则.md`
4. `docs/01-V3教训与V4约束.md`
5. `docs/02-领域模型.md`
6. `docs/03-证据与历史事件模型.md`
7. `docs/04-规则输入类型与投影模型.md`
8. `docs/05-任务状态机与增量失效.md`
9. `docs/06-覆盖度与验收标准.md`
10. `docs/07-智能体边界与成本预算.md`
11. `docs/08-V3并行运行与迁移方案.md`
12. `docs/contracts/` 与当前试点分项规则
13. `config/*.yml`

## 不可妥协约束

- `SourcePassage` 是可定位史料片段，`Assertion` 是来源断言，`HistoricalEpisode` 才是核心语义事实主体。
- 同一事件可以有多份史料和多个断言，但只能有一个当前 canonical episode。
- 语义版本和证据版本分离；新增同义证据不得默认让规则判断和分数失效。
- 人物、事件、规则投影、判断和分数各自有稳定身份与版本。
- 正常增量不得触发全库、整皇帝或整规则重建。
- 模型不能建立正式历史事实、正式判断或正式分数。
- 无变化重跑必须零模型调用、零业务写入。
- V3 与 V4 生产权限、数据库和队列严格隔离。

## 当前 Gate

- `M1 HistoricalEpisode Kernel`：`conditional_pass`
- qualification：`oracle_assisted_constructability_passed`
- `G2 Assertion & Episode`：`reopen_required`
- blind reconciliation：`open_development_regression_no_new_blind_authorized`
- G2.6K0 开放开发资格：`episode_boundary_qualified_relation_s4_blocked`
- G3 Episode Graph PostgreSQL：`blocked_by_g2_6k0`

进入 G3 前必须满足：

- Gold/Oracle 字段不进入 blind Kernel 输入；
- semantic fingerprint 不依赖 episode code；
- blind holdout 达到文档阈值且无灾难性 wrong merge；
- accepted episode 通过独立人工 Gate；
- 没有真实凭据、V3 运行配置或旧业务数据进入 V4。

第一阶段结束不代表可以正式评分，也不代表可以切换生产。
