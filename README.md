# 皇帝综合评价体系 V4

V4 是一次受控架构重启。它保留 V3 的历史经验、失败样本和业务规则来源，但不继承 V3 的实现惯性、正式业务数据或生产运行链。

V4 的核心改变是：

> **历史事件优先，原子断言从属；增量失效优先，全表重建例外；确定性快通道优先，智能体只处理歧义。**

## 当前状态

- 分支：`retrieval-v4-event-first`
- 阶段：G2-Core 已结束，G3A Registry 与 G3B 同步局部失效已通过；G2-Relation/S4 独立阻断
- 试点：李世民、刘邦、朱元璋
- 首条纵向切片：第五项 B“用人与授权”中的 `appointment_delegation`
- 模式：`offline-first + report-only + shadow`
- 正式评分、排名和生产切换：全部关闭
- V3：release 与审计产物保留作只读对照；为避免争抢 wiki 流量，相关 worker 已按明确授权停止

当前已有离线 `src/emperor_v4`、轻量确定性测试、Graph evaluator、试点 `eval` 产物，以及隔离的 V4 PostgreSQL shadow 数据库与 migration；仍然**没有** worker、正式业务 scorer 或正式业务数据。

已证明：给定人工冻结 boundary、Gold linkage 与修复后的 evidence，Kernel 可以构造带 passage lineage 的 EpisodePacket。

G2.6E、G2.6G、G2.6H、G2.6I 与 G2.6J 均已失败冻结。G2.6J 对 7 个 singleton Gold Episode 达到 exact recall/precision 100%，但 31/38 passage 因缺主体/动作而只能作为 context，pairwise merge/split 无样本，2 条 candidate relation 均无 Gold 对应，且没有合格 `appointment_delegation` rule unit。该结果不能解释为 G2.6 通过。

G2.6K0 已结束，不再继续制造新 blind holdout。Source Cache v2、section-aware deterministic slicer、S1—S5 机械早停和 8 场景离线 protocol smoke 已落地。I/J 的 source-v2 开发输入均通过 S1/S2。Boundary policy v2.10 后，I 的开放开发 episode recall/precision 为 100%/100%，J 为 87.5%/93.33%；两组均无灾难性合并、跨皇帝污染或 lineage 丢失，达到 S3 shadow implementation 门槛。

S4 的 254 个 Episode pair 审计和 Relation Gold ontology audit v2 已冻结。历史 fine-type strict precision/recall 仍未达原阈值，只约束相应精细 Relation 发布。G3A/G3B 已完成隔离 PostgreSQL shadow 验证；G3R 形成 13 项宽口径 Relation proposal、2 项 scoring-arc-only、0 unresolved；G3C 形成 4 个 `appointment_delegation` RuleEvidenceUnit draft；G3D 形成 4 个中立 Projection draft、1 个 `mixed` Judgment shadow candidate、3 个 `blocked_evidence`。G3E/G3F 完成缺口定位和 proposal-only 输入 Gate；G3G 已把 3 个候选应用到 RuleEvidenceUnit shadow 副本。G3H 只重建 3 个变化 Projection，逐字段复用 1 个 Projection/Judgment review，4 项 readiness 全部通过，形成 1 个 `positive`、3 个 `mixed` shadow candidate。正式 Relation、正式事实输入、RuleEvidenceUnit、Projection、Judgment、factor values、Score、新 blind、V3/生产数据库和生产切换继续阻断。

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
├─ db/postgres/
│  └─ 001_g3a_episode_core.sql
├─ src/emperor_v4/
│  ├─ contracts/
│  ├─ domain/
│  ├─ application/
│  ├─ adapters/
│  ├─ evaluation/
│  └─ persistence/
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
- G2.6I/J blind 历史结果：`failed_closed`
- blind reconciliation：`closed_no_new_blind_authorized`
- G2-Core / S1—S3：`passed_for_shadow_implementation`
- G2-Relation / S4：`deferred_not_qualified`
- G2-Rule / S5：`blocked_by_relation_track`
- G3A Episode Core Registry：`passed_shadow_registry`
- G3B Core Shadow Runner：`passed_sync_local_invalidation`
- G3R Endpoint workflow：`endpoint_agreement_gate_passed_after_adjudication`
- G3R historical fine-type v1：`fine_relation_graph_gate_failed_closed_after_gap_review`，保留为历史诊断
- G3R scoring minimum-sufficient slice：`minimum_sufficient_relation_slice_passed`，13 项 Relation proposal、2 项 scoring-arc-only、0 unresolved
- G3C RuleEvidenceUnit shadow：`rule_evidence_unit_shadow_ready`，4 draft、3 not_applicable、0 unresolved
- G3D Projection/Judgment shadow readiness：`judgment_shadow_readiness_passed`，4 Projection draft、1 mixed candidate、3 blocked_evidence
- G3E Judgment source-gap inventory：`source_gap_inventory_complete_pending_input_gates`，1 Episode candidate、2 SourcePassage candidates
- G3F Source-gap input Gate：`source_gap_input_gate_passed_for_shadow_delta`，3 accepted、0 unresolved/rejected
- G3G RuleEvidenceUnit shadow delta：`rule_evidence_shadow_delta_ready_for_projection_rebuild`，3 updated、0 readiness gap
- G3H Projection/Judgment incremental rerun：`incremental_judgment_shadow_rerun_passed`，3 rebuilt、1 reused、4 candidates、0 blocked
- G3D Formal Projection / Judgment / Score：`blocked`

进入 G3A/G3B 前必须满足：

- Gold/Oracle 字段不进入 blind Kernel 输入；
- semantic fingerprint 不依赖 episode code；
- accepted episode 通过独立人工 Gate；
- 没有真实凭据、V3 运行配置或旧业务数据进入 V4。

G3C—G3H 当前只通过评分最小充分的 RuleEvidenceUnit、Projection、Judgment readiness、delta shadow 与增量重跑。历史 S4 fine-type 阈值继续约束精细 Relation 发布，S5、正式 factor schema 与 Score 专门 Gate 继续阻断正式 RuleEvidenceUnit、Projection、Judgment 和 Score。

第一阶段结束不代表可以正式评分，也不代表可以切换生产。
