# G3R 评分最小充分 Relation 重解释

> 状态：`minimum_sufficient_relation_slice_passed`
>
> 日期：2026-07-13
>
> 任务代码：`G3R-SCORING-F5271CA2964947EC00F1`

## 1. 结论

依据《皇帝综合评价体系评分标准》的最高驱动原则，冻结的 15 项 endpoint direct proposal 已按评分最小充分合同重新审查：

- 13 项形成评分有用的宽口径 Relation proposal；
- 2 项判为 `scoring_arc_only`，只建议共同进入 RuleEvidenceUnit，不强制逐对建边；
- 0 项 unresolved；
- identity、方向和有向环检查无错误；
- 正式 EpisodeRelation、正式 RuleEvidenceUnit 和数据库业务写入均为 0。

本切片通过只授权下一步 RuleEvidenceUnit shadow 设计，不表示正式 Relation、Projection、Judgment、Score 或生产切换已经开放。

## 2. 新合同

评分必要关系使用：

```yaml
relation_family: authority_change | mandate_or_outcome | explicit_causal
relation_direction:
scope_match:
same_scoring_arc: yes | no | uncertain
ruler_responsibility: direct | partial | none | uncertain
evidence_directness: explicit | strongly_implied | trajectory_only
fine_type:
fine_type_status: resolved | not_required_for_scoring
evidence_assertion_refs: []
```

`proposed_relation` 只用于逐对边确实改善评分归责、方向、结果、去重或追溯的情况。`scoring_arc_only` 表示两端属于同一评分决策弧，但逐对建边没有必要。只有同一评分弧、方向、皇帝归责或证据仍不明确时才允许 `unresolved`。

## 3. 15 项结果

| 处置 | 数量 |
| --- | ---: |
| `proposed_relation` | 13 |
| `scoring_arc_only` | 2 |
| `unresolved` | 0 |

Relation family 分布：

| family | 数量 |
| --- | ---: |
| `authority_change` | 9 |
| `mandate_or_outcome` | 4 |
| `explicit_causal` | 2 |

## 4. 三个隆科多边界案例

### 理籓院、修史任命 → 削太保、世职

形成 `authority_change / reduce / whole_person_status` proposal，`fine_type=null`，`fine_type_status=not_required_for_scoring`。该结论只说明皇帝使隆科多整体政治权力和地位显著收缩，不声称后件撤销了理籓院或修史职务。

### 收回服饰特典 → 夺爵、会鞫、禁锢

判为 `scoring_arc_only`。两端是同一清算决策弧的初始荣典收缩和最终政治权力终止，适合共同进入 RuleEvidenceUnit，但不建立虚假的直接撤销边。

### 收回服饰特典 → 削太保、世职并外派

判为 `scoring_arc_only`。两项是同一轮清算中的不同处分成员，分别标记特殊荣典收缩与官职、品秩收缩，不要求它们之间存在细类型 Relation。

## 5. 下一步边界

下一步只设计 `appointment_delegation` 的最小 RuleEvidenceUnit shadow：成员必须声明评分角色，严格保留皇帝归责、权责方向、结果、SourcePassage lineage 和重复消费控制。不得直接接受当前 13 条 Relation proposal，不得写正式 RuleProjection、Judgment 或 Score。
