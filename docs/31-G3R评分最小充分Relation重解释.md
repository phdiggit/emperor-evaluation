# `appointment_delegation` 评分最小充分 Shadow 实施摘要

> 状态：`g3r_g3h_shadow_chain_passed_factor_score_pending`
>
> 日期：2026-07-13
>
> 实现基准：`13ea96e5b0d42c9a6d86c8ba516ad6cfc1b08f16`

## 1. 结论

V4 已完成以下 shadow 链：

```text
Episode endpoint proposals
→ 评分必要 Relation / scoring-arc-only
→ RuleEvidenceUnit draft
→ Projection draft
→ Judgment readiness / shadow direction
→ 缺口定向输入
→ RuleEvidenceUnit delta
→ 局部 Projection 重建与 Judgment 复用
```

当前结果：

- 15 项 endpoint direct proposal；
- 13 项宽口径 Relation proposal；
- 2 项 `scoring_arc_only`；
- 0 项评分语义 unresolved；
- 4 个 `appointment_delegation` RuleEvidenceUnit draft；
- 4 个 Projection draft；
- 4 个 Judgment shadow candidate；
- 方向为 1 个 `positive`、3 个 `mixed`；
- `blocked_evidence=0`；
- Episode 重复消费为 0；
- 正式 Relation、RuleEvidenceUnit、Projection、Judgment、factor values、ScoreContribution 和数据库业务写入均为 0。

这说明评分单元与增量 readiness 已具备原型，但还没有形成可交付的评分结果。

## 2. 评分最小充分 Relation

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

`proposed_relation` 只用于逐对关系确实改善评分归责、方向、结果、去重或追溯的情况。`scoring_arc_only` 表示两个 Episode 属于同一评分决策弧，但不值得制造一条历史关系边。粗关系足以评分时，`fine_type=null` 合法。

## 3. RuleEvidenceUnit

评分 links 组成 7 个候选分量。规则边界审查后形成 4 个 RuleEvidenceUnit draft，排除 3 个不适用分量，0 unresolved。每个 draft 声明皇帝、人物、决策弧、Episode 成员角色、证据和四个 readiness 问题：

```text
delegation_quality
supervision_quality
correction_timeliness
net_effect
```

`evidence_gap` 不是负向判断，也不是零分。

## 4. Projection 与 Judgment readiness

首轮 Judgment shadow 使用四个观察维度：

```text
person_task_fit
authority_clarity
feedback_handling
attributable_outcome
```

当前观察值仅用于 readiness：

```text
positive_signal
negative_signal
mixed_signal
evidence_gap
not_applicable
```

定向补证与 delta 后，3 个变化单元重建 Projection，1 个未变化 Projection 与 Judgment review 逐字段复用；4 个 Projection 均通过 readiness，形成 1 个 positive 与 3 个 mixed candidate。

## 5. 当前代码边界

活动实现：

- `relation_scoring_arc.py`
- `rule_evidence_shadow.py`
- `judgment_source_gap.py`
- `source_gap_input_gate.py`
- `rule_evidence_delta.py`
- `projection_judgment_shadow.py`
- `projection_readiness_rerun.py`

这些模块尚未接入统一用户入口。`src/emperor_v4/eval.py` 不能用一个命令重放 G3R—G3H 整条链。

## 6. 下一交付物

下一步必须在一个纵向职责链中完成：

1. 将四个观察维度升级为人工批准的有限 factor schema；
2. 实现确定性 Judgment evaluator；
3. 设计最小 ScoreContribution 公式、幂等键与版本；
4. 建立统一 `appointment_delegation` shadow runner；
5. 输出李世民、刘邦、朱元璋可追溯的 scored demo 报告。

在以上结果完成前，不新增微阶段顶层文档，不为每个模块建立镜像测试文件，不开放正式 Judgment、总榜或生产切换。

## 7. 历史审计

早期 fine-type Relation 失败继续保留在 `24-*` 至 `29-*` 历史审计中，只用于说明精细历史关系图尚未达到发布阈值。逐条 endpoint 展开和 G3C—G3H 微阶段说明已从长期文档层移除，结构化运行产物应保存在 `eval/` 或外部 artifact。
