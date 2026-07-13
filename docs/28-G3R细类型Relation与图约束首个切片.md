# G3R 细类型 Relation 与图约束首个切片

> 状态：`fine_relation_graph_gate_failed_closed`
>
> 日期：2026-07-13
>
> 任务代码：`G3R-FINE-732FC2722531F5372E76`

## 1. 结论

Endpoint Gate 后的 15 项 `proposed_direct_relation` 已全部进入细类型审查。中央验证得到：

- 11 项形成 versioned Relation proposal；
- 4 项为 `unresolved`，没有生成 Relation proposal；
- 11 项 proposal 的稳定身份、版本、evidence lineage、方向、环和纯传递冗余检查通过；
- 细类型 Graph Gate 因 unresolved 未清零而失败关闭；
- 正式 EpisodeRelation、数据库业务写入和模型正式接受均为 0。

这不是回退 endpoint Gate。Endpoint direct/coarse 合同仍已通过；本次结果说明粗类型为 direct 不等于证据足以唯一确定细类型。

## 2. 合同与版本

细类型 worklist 只机械选取裁决结果中的 15 项 direct proposal，绑定 endpoint task、worklist hash 和 final result hash。每项只能在
相应 coarse 类型允许的集合内选择：

| coarse type | 允许的 fine type |
| --- | --- |
| `authority_change` | `revokes`、`renews_authority`、`promotion_after` |
| `mandate_or_outcome` | `outcome_of`、`same_mandate_phase`、`continues` |
| `explicit_causal` | `causal_followup` |

证据不能唯一确定方向和细类型时必须输出 `unresolved`，不得为通过 Gate 强行映射。每项 resolved proposal 使用稳定 semantic
fingerprint 和 relation ID，endpoint 引用固定为 `@v1`，semantic/evidence version 均从 1 开始，状态固定为 `proposed`，evidence
状态固定为 `draft`。

## 3. 审查结果

11 项 proposal 的类型分布：

| relation type | 数量 |
| --- | ---: |
| `renews_authority` | 3 |
| `revokes` | 3 |
| `same_mandate_phase` | 2 |
| `outcome_of` | 1 |
| `continues` | 1 |
| `causal_followup` | 1 |

4 项失败关闭：

- `RBC-1B5EF40E8FE602C1C2E7`：两端都是不同阶段收权，后件并非撤销前件授予的权利；
- `RBC-7DB5F37DCBA46F15191E`：前件职位与后件被削职位没有被 endpoint 证据证明为同一授权；
- `RBC-92189019556268DEDD10`：同年两项并行收权措施无法在 authority coarse 集合内唯一选型；
- `RBC-AED36A09908D78FD4401`：蒙毅被杀与蒙恬被赐死仅显示同案处置，没有证明前件导致后件。

## 4. 图约束审计

11 项 proposal 通过：

- relation ID 与 semantic fingerprint 唯一；
- 每条边精确覆盖候选的两个 endpoint，且无自环；
- Assertion evidence 同时覆盖两端，并保留 SourcePassage lineage；
- 时间/因果边无有向环；
- 同类型边无可由已有路径完全表达的纯传递冗余。

图约束通过不覆盖 unresolved Gate。当前结果可作为 report-only proposal 证据，不能写为 accepted Relation。

## 5. 下一步边界

该定向核对已执行，结果见[《G3R 细类型 Relation 定向补证复核》](29-G3R细类型Relation定向补证复核.md)。现有 SourcePassage
解决 1 项，剩余 3 项确认需要新的 Assertion 级证据；不得扩大到 138 项全量审查，也不得把 12 项 proposal 提前接受。3 项清零后
仍需另行执行 S4 strict precision/recall，才能判断 G3R 是否取得正式资格。
