# G2 终止与 G3A 核心 Shadow 决策

> 状态：`accepted`
>
> 日期：2026-07-13
>
> 决策代码：`ADR-G2-CORE-G3A-SPLIT-20260713`

## 1. 决策

原 S1—S5 阈值不变，但不再把通用 EpisodeRelation 图作为 HistoricalEpisode Core shadow persistence 的前置条件。
G2 调试循环到此结束，分成三个独立资格轨道：

| 轨道 | 状态 | 结论 |
| --- | --- | --- |
| G2-Core / S1—S3 | `passed_for_shadow_implementation` | 允许进入 G3A/G3B Core shadow |
| G2-Relation / S4 | `deferred_not_qualified` | 原 strict precision 90%、recall 85% 阈值不变 |
| G2-Rule / S5 | `blocked_by_relation_track` | 旧 Rule Gold stale，不得放行 |
| G3A-Core-Registry | `authorized_for_implementation` | 仅隔离 V4 Episode Core |
| G3B-Core-Runner | `planned_after_g3a` | 仅同步、事务化、幂等与局部失效 |
| G3R-Relation | `experimental_independent_track` | 不再阻断 G3A/G3B |
| G3C-Formal-Projection | `blocked` | 不得规则投影、判断或评分 |

这不是把 S4 失败改名为成功。G2-Core 的依据来自已开封 I/J 开发集，只授权 shadow implementation，不构成新的 blind
qualification，也不降低正式 Relation、RuleEvidenceUnit 或评分门槛。

## 2. 决策依据

I/J 的 Source v2、atomic support、零导航噪声和 lineage 已收敛；S3 分别为 100%/100% 与 87.5%/93.33%，达到开发门槛。
S4 在 Relation Gold v2 下仍只有 50%/73.33% 与 40%/25%。I 仍需补至少 2 条正确边并删除约 10 条误报；J 仍需把
正确边从 2 条提高到至少 7 条、消除额外候选并修正类型错配。它不是最后一公里。

现行 Relation audit 对同一 evaluation context 使用全 pair 枚举；I/J 共处置 254 对。该方式适合一次性 ontology 审计，
不适合作为生产默认候选生成路径。Relation 的候选资格必须在 G3R 先经过确定性 blocking，而不是让所有 Episode pair 自动取得
模型审查资格。

## 3. 小型 Relation 可学习性实验

任务代码：`g2-relation-learnability-v1`。

实验从 I/J 已开封开发产物中机械冻结 27 对：9 个既有严格命中正例、9 个额外候选边界例、9 个按稳定 hash 选择的
`distinct_unrelated` 负例。分层清单由协调层保存，两个 reviewer 只读取相同的 endpoint episode summary/evidence；均禁止读取
Historical/Relation Gold、candidate relation、score、分层清单和对方输出。

reviewer 只回答：

```yaml
direct_relation: yes | no | insufficient
coarse_type: authority_change | mandate_or_outcome | explicit_causal | null
```

预注册硬停条件与结果：

| 指标 | 门槛 | 结果 | 判定 |
| --- | ---: | ---: | --- |
| direct relation 一致率 | ≥ 90% | 27/27，100% | 通过 |
| coarse type 一致率 | ≥ 80% | 24/27，88.89% | 通过 |

三个分歧全部发生在 coarse type，direct relation 无分歧。该结果仅说明 Relation track 值得以粗类型、候选 blocking 和双审协议
继续研究；它是 post-Gold open-development agreement，不测量对 Gold 的准确率，不是 S4 pass，也不授权今天重跑完整 S4。

因此本轮明确不创建 policy v3、不重审 254 对、不重冻 Rule Gold、不创建新 blind holdout。

## 4. Relation 职责降级

G3R 优先研究真正影响首条 `appointment_delegation` 规则的关系：

- 授权或续权；
- 撤权；
- 直接结果；
- 显式因果后续。

`continues`、`same_mandate_phase`、`promotion_after`、`context_for` 暂降为非阻断 narrative metadata。规则消费层可用
`appointment_or_delegation`、`execution`、`outcome_or_feedback`、`revocation`、`context` 等成员角色表达共同消费意图，
但在 G3R/S4 与新 S5 通过前不得形成正式 RuleEvidenceUnit、Projection 或 Score。

## 5. G3A/G3B 最小范围

G3A Core Registry 只覆盖：

```text
source_documents
source_passages
assertions
historical_episodes
historical_episode_versions
episode_participants
episode_assertion_dispositions
review_artifacts
boundary_review_cache
```

Relation reviewer 输出最多保存为 `relation_review_artifact` / `relation_proposal`，不是 accepted core fact，不触发规则投影或计分。

G3B 同步 shadow runner 只验证：

- 重复输入零新增；
- 同义证据只提升 evidence version；
- 语义变化创建新 semantic version；
- 一个 ReviewUnit 变化只失效局部对象；
- 无变化重跑零模型调用、零业务写入。

未证明同步路径确有需要前，不引入 worker/outbox。

## 6. 未授权事项

本决策不授权：

- 连接或修改 V3 数据库；
- 使用任何生产 PostgreSQL 实例、真实 DSN 或凭据；
- 恢复 V3 worker 或部署生产服务；
- accepted EpisodeRelation、RuleEvidenceUnit、RuleProjection、Judgment 或 ScoreContribution；
- 正式评分、排名、生产切换；
- 新 blind holdout 或把本次开发一致性实验包装成 blind pass。

V4 shadow Schema、migration、同步事务 adapter、I/J proposed shadow 数据与真实数据库级验证已在
`22-G3A核心Registry首个实现切片.md` 完成；G3A 已通过，下一阶段进入 G3B 同步 Core Shadow Runner。

## 7. 对既有文档的影响

- `20-G2.6K0史源切片开发资格.md` 的 S1—S4 数据和失败结论保持有效；其原“完整资格后才能进入任何 G3”计划由本决策取代。
- `11-G2.6事件边界与关系模型.md` 的全 pair 处置保留为 G2.6K0 审计历史，不再是生产默认候选生成契约。
- `06-覆盖度与验收标准.md` 的原 G3 合并 Gate 拆为 G3A、G3B、G3R、G3C；S4/S5 与正式评分阈值不变。
- 更早的失败报告仍是不可改写的历史证据；其中“PostgreSQL G3 未授权”描述的是当时状态，不回溯改写。
