# G3A 核心 Registry 首个实现切片

> 状态：`postgres_shadow_registry_passed`
>
> 日期：2026-07-13
>
> 实现代码：`G3A-CORE-REGISTRY-SLICE-1`

## 1. 结论

G3A Episode Core Registry 已在独立 V4 PostgreSQL 数据库中通过。九张授权表的 migration、空库/完整合同/部分污染三态
bootstrap、同步事务 adapter、I/J Boundary-to-Core handoff、真实数据库幂等与回滚均已验证。Relation、规则投影、评分、worker
和 outbox 仍未进入数据库。

## 2. 实现范围

PostgreSQL migration 只创建：

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

Migration 使用单事务，禁止默认删除、清空或重建；稳定身份、semantic/evidence version、artifact idempotency 和 boundary cache
均有数据库约束。`historical_episodes` 的活动版本指针使用 deferred composite foreign key 指向完整版本记录。

离线 `InMemoryCoreRegistry` 与真实 `PostgresCoreRegistry` 共同实现同一事务语义：

- SourcePassage 仅接受 v2，并要求精确 document content version lineage；
- Assertion 必须引用已持久化 passage；
- Episode assertion link 必须与 Assertion/Passage 一致；
- 首次 Episode 从 semantic/evidence v1 开始；
- evidence-only revision 只增加 evidence version，不重复 participant 行；
- semantic revision 连续增加 semantic version；
- 相同输入重跑零业务写入、零模型调用；
- 任一引用或稳定身份冲突使整批失败，不提交部分状态。

`build_g3a_core_registry_batch` 将冻结的 Source v2 与 Boundary proposal 映射为 Source、Assertion、Episode、Disposition、
ReviewArtifact 和 Boundary cache；不会输出 EpisodeRelation 或 RuleEvidenceUnit。

## 3. Relation 与评分隔离

Schema 没有 EpisodeRelation、RuleEvidenceUnit、RuleProjection、Judgment、ScoreContribution、outbox 或 worker 表。Relation 输出
只能以 `relation_review_artifact` 或 `relation_proposal` 保存，artifact status 不允许 `accepted`。该输出不是核心历史事实，也不能触发
规则投影或计分。

## 4. 验证

```text
G3A focused tests
20 passed

python -m compileall -q src
python -m pytest -q
133 passed, 1 skipped

授权 DSN 注入的真实 PostgreSQL integration
1 passed
```

测试覆盖：

- 九张表白名单与禁止表集合；
- migration 事务性、非破坏性和数据库幂等约束；
- 首次写入与无变化重跑；
- evidence-only 与 semantic revision；
- participant 语义版本行为；
- 批次原子失败；
- Relation accepted artifact 拒绝；
- 稳定身份冲突失败关闭。

真实数据库执行结果：

| 检查 | 结果 |
| --- | --- |
| 数据库创建与连接 | 通过 |
| 首次 schema bootstrap | `applied` |
| 第二次 schema bootstrap | `reused`，0 写入 |
| 临时 schema adapter integration | 通过，测试后已删除 |
| I/J shadow 首次写入 | 通过 |
| I/J shadow 无变化重跑 | 0 业务写入，0 模型调用 |
| 残留临时 schema | 0 |
| active Episode version 孤儿 | 0 |
| 非 proposed Episode version | 0 |
| 禁止表 | 0 |

持久化计数：12 个 SourceDocument version、45 个 SourcePassage、77 个 Assertion、41 个 HistoricalEpisode/Version、
106 个 EpisodeParticipant role、77 个 EpisodeAssertionDisposition、17 个 ReviewArtifact 与 17 个 Boundary cache entry。

集成前发现并关闭两个合同问题：Boundary cache 不能以全数据集 input hash 作为单元唯一键；同一 passage/semantic key 的多个
Assertion 可能保留不同 legacy lineage，不能被数据库唯一约束静默合并。最终分别使用 cache key 主键，以及
`assertion_id` 主键加非唯一 semantic 检索索引。

## 5. G3B 后续状态

G3B 同步 Core Shadow Runner 已随后通过，详见 `23-G3B同步CoreShadowRunner.md`。G3A/G3B 仍然：

- 不增加 worker/outbox；
- 不连接 V3 或生产数据库；
- 不进入 G3R/G3C 的正式 Relation、规则投影或评分。
