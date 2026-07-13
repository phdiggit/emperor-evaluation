# G3B 同步 Core Shadow Runner

> 状态：`passed_sync_local_invalidation`
>
> 日期：2026-07-13
>
> 实现代码：`G3B-CORE-SHADOW-RUNNER-SLICE-1`

## 1. 结论

G3B 首个同步 Core Shadow Runner 已通过。Runner 以 `evaluation_context + atomic_event_key` 的规范哈希作为稳定事件身份锚点，
先读取该锚点对应的活动版本，再执行 semantic/evidence 分离的确定性版本决策，最后把最小写集交给 Core Registry 单事务提交。

该切片没有 worker、outbox、异步任务、Relation 正式表、规则投影或评分入口。G3R/G3C 状态不变。

## 2. 同步与局部失效合同

- 新身份锚点只能从 semantic/evidence v1 开始；
- 同一锚点即使观察批次生成了新的临时 Episode ID，也继续使用既有 Episode ID；
- 语义 payload 变化只增加目标 Episode 的 semantic version；
- 证据 payload 变化只增加目标 Episode 的 evidence version，不重复 participant 行；
- 全数据集 `input_hash` / `input_version` 不参与 Episode evidence hash，避免无关输入变化造成全局升版；
- 未变化 Episode 不进入 Registry 写集，产生零 Episode 写入和零模型调用；
- Disposition 自动映射到最终 Episode ID 和 semantic/evidence version；
- 任一 lineage、稳定身份或版本连续性错误使整个 Registry 批次回滚，修正后可同步重试。

当前切片不处理 Episode 删除、split 或 merge；这些变化不得被 runner 静默解释为普通升版，后续必须另设显式合同和门禁。

## 3. PostgreSQL 迁移

`historical_episodes` 增加非空且唯一的 `identity_anchor`。已授权 V4 shadow 库中的 41 个 I/J Episode 全部从冻结
Boundary handoff 回填锚点。由于 evidence hash 合同排除了全局编排 provenance，41 条既有版本只重算派生 hash；事实 payload、
活动版本和业务状态均未改写。

迁移后真实库审计结果：

| 检查 | 结果 |
| --- | --- |
| Episode / distinct identity anchor | 41 / 41 |
| 空或无效 identity anchor | 0 |
| 唯一约束 | 1 |
| I 数据集同步重跑 | 26 个 Episode 不变，0 业务写入，0 模型调用 |
| J 数据集同步重跑 | 15 个 Episode 不变，0 业务写入，0 模型调用 |
| 禁止表 | 0 |
| 残留临时 schema | 0 |
| 记录 DSN/口令 | 否 |

## 4. 验证范围

离线和真实 PostgreSQL 验证覆盖：

- 两个独立 Episode 中只修改一个责任字段，只有目标锚点产生 semantic v2；
- 只增加目标 Episode 的同义证据，只有目标锚点产生 evidence v2，participant 写入为 0；
- 全局 input provenance 变化不造成 Episode 版本扇出；
- 无变化重跑零业务写入、零模型调用；
- 失败批次不留下部分状态，合法重试成功；
- PostgreSQL 从 JSONB 恢复活动 packet，并在观察 ID 改变时按锚点续接既有 Episode ID；
- 临时 schema 完成 migration、runner 局部升版与回滚验证后删除。

## 5. 后续边界

G3B 同步局部失效基线已经建立，但这不授权异步化或评分。下一步可在 Core track 内补充显式删除/split/merge 提案合同及更大
shadow 变更样本；G3R 继续独立研究 Relation，只有 G3R/S4 和新冻结 S5 达到原门槛后才可讨论 G3C。
