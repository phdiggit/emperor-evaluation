# G3G RuleEvidenceUnit Shadow Delta

> 状态：`rule_evidence_shadow_delta_ready_for_projection_rebuild`
>
> 日期：2026-07-13
>
> 规则：`appointment_delegation`

## 1. 结论

G3F 通过的 3 个 proposal-only 输入已应用到 G3C RuleEvidenceUnit shadow 副本：

| Delta 结果 | 数量 |
| --- | ---: |
| RuleEvidenceUnit draft 总数 | 4 |
| 更新单元 | 3 |
| 逐字段不变单元 | 1 |
| semantic version 递增 | 3 |
| evidence version 递增 | 3 |
| 新 Episode member | 2 |
| 新 context Assertion | 1 |
| 新 `scoring_arc_only` 引用 | 2 |
| 剩余 readiness gap | 0 |
| Episode 重复消费 | 0 |

3 个更新单元保持原 `unit_code`，semantic fingerprint 均发生变化，semantic/evidence version 均从 1 递增为 2。原本 readiness 完整的鄂尔泰军务单元逐字段保持不变。

`shadow_delta_gate_passed=true`、`readiness_rerun_authorized=true`。这只授权重建 3 个受影响的 Projection draft 并重跑 Judgment readiness，不批准正式事实、Projection、Judgment 或 Score。

## 2. 三个 Delta

### 鄂尔泰地方治理

- 新成员：`EP-8CB3B50DDAB3A262F495@v1`，role=`outcome`；
- 新增对应 Assertion 和 SourcePassage lineage；
- 新增确定性的 `G3F-ARC-*` scoring-arc-only 引用；
- `supervision_quality`、`net_effect` 从 `evidence_gap` 更新为 `ready`。

该更新改变评分单元的成员与结果语义，因此 semantic/evidence version 同时递增。

### 隆科多权责轨迹

- 不新增 Episode；
- 新增一个 context Assertion ref，支持前期勤劳、异数奖励与后期失误的连续归因；
- `net_effect` 从 `evidence_gap` 更新为 `ready`。

该 Assertion 引入此前不存在的评分语义，而非同义 evidence fanout，因此 semantic/evidence version 同时递增。若未来只是新增同义来源，不应复制本次升级策略。

### 周勃任相与复任

- 新成员：`EP-SHADOW-*` outcome Episode 候选；
- 新增对应 SourcePassage、Assertion lineage；
- 新增确定性的 `G3F-ARC-*` scoring-arc-only 引用；
- `net_effect` 从 `evidence_gap` 更新为 `ready`。

该更新改变评分单元的成员与后续结果语义，因此 semantic/evidence version 同时递增。

## 3. 身份与版本规则

- `unit_code` 是稳定评分单元身份，delta 不得因 fingerprint 改变而换号；
- semantic fingerprint 由 rule/version、aggregation policy、evaluation context、皇帝、人物、决策弧、成员及有评分语义的 context Assertion 组成；
- 成员或评分语义变化时 semantic version 递增；
- 支撑该语义的证据集合变化时 evidence version 递增；
- 新增纯同义 evidence fanout 默认只影响 evidence version，且不应自动重判；
- 同一次 delta 不得重复更新同一 unit，也不得让同一 Episode 被多个本规则单元消费。

## 4. Lineage 与副作用

每个更新单元保留：

- G3F input Gate task code；
- gap code；
- boundary disposition；
- 新 Episode/Assertion/scoring arc ref；
- SourcePassage refs；
- 更新前后 semantic fingerprint；
- 新 semantic/evidence version。

正式 Assertion、Episode、Relation、RuleEvidenceUnit、Projection、Judgment、Score 和数据库写入均为 0。

## 5. 下一步

上述步骤已由 [G3H Projection 增量重建与 Readiness 重跑](37-G3HProjection增量重建与Readiness重跑.md) 完成：3 个受影响 Projection 已重建，未变化 Projection 与 Judgment review 逐字段复用，4 项 readiness 全部通过。正式 factor schema、方向聚合和 ScoreContribution 仍须经过独立 Gate。
