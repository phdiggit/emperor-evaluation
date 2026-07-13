# G3D Projection 与 Judgment Shadow Readiness

> 状态：`judgment_shadow_readiness_passed`
>
> 日期：2026-07-13
>
> 规则：`appointment_delegation`

## 1. 结论

G3C 通过的 4 个 RuleEvidenceUnit draft 已生成 4 个中立 RuleProjection draft，并完成 Judgment readiness 人工审查：

| 结果 | 数量 |
| --- | ---: |
| RuleProjection draft | 4 |
| Judgment shadow candidate | 1 |
| `blocked_evidence` | 3 |
| `blocked_rule_boundary` | 0 |

观察层记录 8 个正向信号、2 个负向信号和 2 个混合信号。只有 readiness 四问完整的鄂尔泰军务弧形成 `mixed` shadow direction；其余 3 个 Projection 虽然包含正向或负向证据，仍因关键证据缺口而不生成方向。

正式 Projection、正式 Judgment、factor values、Score 和数据库业务写入均为 0。

## 2. Projection shadow 合同

Projection draft 只保存：

- `rule_evidence_unit_draft` 输入引用及其 semantic fingerprint；
- rule/version/evaluation context；
- 皇帝、人物、决策弧、成员角色与 link 引用；
- Assertion lineage 与四个问题的 readiness；
- `applicability_status=applicable`、`projection_status=draft`。

它不复制史源原文，不修改 Episode，不产生正式 Projection ID，也不能直接进入 scorer。

## 3. Judgment readiness 合同

本阶段只允许四个观察维度：

```text
person_task_fit
authority_clarity
feedback_handling
attributable_outcome
```

每个维度只能使用：

```text
positive_signal
negative_signal
mixed_signal
evidence_gap
not_applicable
```

这些是 shadow observation，不是已批准的 `factor_values`。正负或混合信号必须引用当前 Projection 内的 Assertion；任一关键 readiness 或观察维度仍为 `evidence_gap` 时，必须 `blocked_evidence`，且 `shadow_direction=null`。

只有所有关键问题均不缺证据时，才允许生成 `positive | negative | mixed` shadow direction。即使如此，结果仍保持 `draft`，不能成为 accepted Judgment。

## 4. 四个真实案例

| 人物与决策弧 | 主要观察 | 处置 |
| --- | --- | --- |
| 鄂尔泰地方治理与边界任务 | 任命、采纳建议和明确授权均有正向信号；监督与净效果不足 | `blocked_evidence` |
| 鄂尔泰军务授权与苗疆复叛 | 先前功绩、明确授权、后续失败与削爵纠正并存 | `judgment_shadow_ready / mixed` |
| 隆科多权责收缩轨迹 | 连续纠错有正向信号；初始适配与任用净效果不足 | `blocked_evidence` |
| 周勃任相与复任 | 不适任及反馈后复任形成负向信号；复任净效果不足 | `blocked_evidence` |

周勃案例证明“明确负向信号”不等于可以立即形成负向 Judgment；鄂尔泰地方治理案例同样证明“多个正向信号”不等于可以绕过净效果缺口。

## 5. Gate 边界

本 Gate 通过表示：

- RuleEvidenceUnit 到中立 Projection draft 的身份、版本和 lineage 可稳定表达；
- 正负观察值域、证据引用和 readiness 阻断可以机械校验；
- shadow direction 与正负信号组合可以确定性校验。

本 Gate 不批准：

- 正式 Projection 或 Judgment；
- 将 observation 值域升级为正式 factor schema；
- 材料分值、因子倍率、衰减、权重或 ScoreContribution；
- 把 `blocked_evidence` 当作零分或负分；
- 生产数据库写入或生产 scorer。

后续 G3E 已针对 3 个 `blocked_evidence` 案例冻结最小问题和停止条件，并完成本地 source-v2 库存检索；结果见 [G3E Judgment 缺口定向库存检索](34-G3EJudgment缺口定向库存检索.md)。候选尚需输入 Gate，readiness 重跑仍未授权。
