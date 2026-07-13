# G3H Projection 增量重建与 Readiness 重跑

> 状态：`incremental_judgment_shadow_rerun_passed`
>
> 日期：2026-07-13
>
> 规则：`appointment_delegation`

## 1. 结论

G3G 的 RuleEvidenceUnit shadow delta 已按 semantic fingerprint 做局部失效：只重建 3 个变化单元的 Projection，未变化的鄂尔泰军务 Projection 及其既有 Judgment review 逐字段复用。4 个 Projection 均通过 Judgment shadow readiness，原有 3 个 `blocked_evidence` 已解除。

| 结果 | 数量 |
| --- | ---: |
| Projection draft | 4 |
| 重建 Projection | 3 |
| 复用 Projection | 1 |
| 重新审查 Judgment | 3 |
| 复用 Judgment review | 1 |
| Judgment shadow candidate | 4 |
| `blocked_evidence` | 0 |
| `blocked_rule_boundary` | 0 |
| `positive` direction | 1 |
| `mixed` direction | 3 |
| `negative` direction | 0 |

`all_projection_readiness_passed=true`。本 Gate 只确认输入完整性、方向合同和局部失效行为，不构成正式 Projection、Judgment、factor values、ScoreContribution 或排名。

## 2. 增量失效结果

- `projection_rebuild_unit_refs` 中 3 个单元的 semantic fingerprint 已变化，均产生新的确定性 `projection_code`；
- `unchanged_unit_refs` 中 1 个单元的 Projection 与 G3D 输入逐字段一致；
- 复用 Projection 对应的 Judgment reviewer row 与 G3D response 逐字段一致，未进行隐式重判；
- 3 个重建项完整保留更新后的 Assertion、SourcePassage、Episode/context lineage 与 semantic/evidence version；
- 未发生全规则重建、模型调用、正式接受或数据库写入。

这验证了“语义变化局部重建、未变化结果精确复用”的最小缓存合同。新增纯同义证据但 semantic fingerprint 不变时，仍不得默认触发 Judgment 重判。

## 3. 四个 Shadow 方向

### 鄂尔泰地方治理：`positive`

新增 outcome Episode 补足治理净效果；任命适配、授权边界、反馈处理和可归责结果四项均为 `positive_signal`。

### 鄂尔泰军务：`mixed`

该项未变化，完整复用 G3D 结果。既有功绩与后续复叛失败并存，保持 `mixed`。

### 隆科多权责轨迹：`mixed`

新增 context Assertion 补足初始履职背景；授权边界与连续纠错为正向信号，但终局权力终止与负向后果并存，因此为 `mixed`。

### 周勃任相与复任：`mixed`

授权边界可定位，但人岗不适配、反馈后的再次任用及新增终局结果均为负向信号。当前尚无获准的因子权重或聚合公式，有限方向合同规定正负信号并存时必须输出 `mixed`，不得擅自将三项负向观察加权为正式 `negative`。

## 4. 信号与副作用审计

4 个候选共包含：

- `positive_signal`：10；
- `negative_signal`：3；
- `mixed_signal`：3；
- `evidence_gap`：0。

所有信号引用均在各自 Projection 的 Assertion 白名单内。`formal_acceptance_performed=false`，正式 Projection、Judgment、Score 和数据库写入均为 0。

## 5. 后续 Gate

G3H 结束后，可以单独设计正式 factor schema、方向聚合和 ScoreContribution Gate；在这些上位规则被人工接受前，当前 4 项只能保留为 shadow candidate。不得把本次 direction 当作正式评分，也不得写入 V4 正式业务状态或替换 V3 服务。
