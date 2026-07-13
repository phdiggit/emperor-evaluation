# G3C 最小 RuleEvidenceUnit Shadow

> 状态：`rule_evidence_unit_shadow_ready`
>
> 日期：2026-07-13
>
> 规则：`appointment_delegation`

## 1. 结论

G3R 冻结的 13 条评分 Relation proposal 与 2 条 `scoring_arc_only` 建议已按《皇帝综合评价体系评分标准》和分项规则聚合为 7 个候选分量：

| 结果 | 数量 |
| --- | ---: |
| RuleEvidenceUnit draft | 4 |
| `not_applicable` 分量 | 3 |
| `unresolved` 分量 | 0 |
| readiness 问题级证据缺口 | 4 |

全部 15 个上游评分 link 均被且仅被一个分量审查。Episode 重复消费为 0；正式 Relation、正式 RuleEvidenceUnit、Projection、Judgment、Score 和数据库业务写入均为 0。

因此，`appointment_delegation` 的最小 RuleEvidenceUnit shadow Gate 通过。该结论只证明评分输入单元的边界、角色、归责和 lineage 可以稳定表达，不批准正式规则判断或计分。

## 2. Shadow 合同

每个适用单元必须绑定：

- `rule_code=appointment_delegation`、rule version 与 aggregation policy version；
- 单一 evaluation context；
- 可由 endpoint Assertion 支持的皇帝归责；
- 单一被任用人物或冻结人物组合；
- 每个 Episode 的评分角色；
- 被消费的评分 Relation proposal 或 `scoring_arc_only` link；
- 覆盖每个 Episode 的 Assertion lineage；
- 用人授权质量、监督质量、纠错及时性和净效果四个问题的 readiness。

`readiness=evidence_gap` 只表示该问题现有证据不足，不能被解释为负向 Judgment 或零分。`scoring_arc_only` 只保留在单元 lineage 中，不伪造为正式 Relation member。

## 3. 四个 Draft 单元

| 皇帝 | 人物 | 决策弧 | Episode 数 | 结论边界 |
| --- | --- | --- | ---: | --- |
| 胤禛 | 鄂尔泰 | `appointment_to_mandate` | 3 | 任命、治理建议反馈与边界任务授权 |
| 胤禛 | 隆科多 | `authority_trajectory` | 5 | 任命后连续收权、纠错与终止 |
| 文帝 | 周勃相关冻结人物组合 | `authority_restoration` | 3 | 任相、履职反馈与复任 |
| 胤禛 | 鄂尔泰 | `appointment_feedback_correction` | 3 | 任命、军务授权、失败反馈与权责收缩 |

同一人物可以在不同职责域和独立任用决策弧中形成不同单元，但同一 Episode 不得在本次 workset 内重复消费。

## 4. 三个排除分量

- 扶苏、蒙恬安全链：只有连续处置，没有与之相连的任命、职责或授权起点；
- 萧瑀：献策解围与随后外放存在因果连续性，但缺少本 rule 的任命—职责—反馈链，更接近容才或认知边界；
- 李斯：只有受处置及结局，没有直接相连的任命或授权安排。

这些分量不是史实无效，也不是评分为零；它们只是不适合作为 `appointment_delegation` RuleEvidenceUnit。

## 5. 仍然关闭

本 Gate 之后仍不得：

- 将 draft 接受为正式 RuleEvidenceUnit；
- 生成正式 RuleProjection、Judgment、材料分值或汇总 Score；
- 因 readiness 缺口自动作负向判断；
- 将本次 shadow 结果写入生产或 V3 数据库；
- 用旧 RuleEvidenceUnit、Gold 或既有分数反向修正当前结果。

后续 G3D 已冻结 Projection/Judgment shadow 输入输出与人工门禁，并用 4 个真实 draft 完成正负案例验证；结果见 [G3D Projection 与 Judgment Shadow Readiness](33-G3DProjection与JudgmentShadowReadiness.md)。该结果仍不批准 formal Projection/Judgment。
