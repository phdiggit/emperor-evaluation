# `appointment_delegation` 评分最小充分 Shadow 实施摘要

> 状态：`persistent_roster_shadow_ready_second_rule_reuse_next`
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
- 正式 Relation、RuleEvidenceUnit、Projection、Judgment、45 分得分和数据库业务写入均为 0；4 个 ScoreContribution 仅限 `shadow_demo_only`。

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

这些模块已经由 `src/emperor_v4/eval.py` 的 `appointment-delegation-shadow` 命令串成统一、离线、零模型的 scored shadow 重放链。Relation v2 合同使用实际 Episode semantic version 形成端点版本引用，并把皇帝责任与证据直接性纳入 Relation 语义身份；缺失或不一致的版本身份一律 fail closed。source-gap input gate v2 对 `not_found_stop` 项逐项跳过并保留审计记录，不再阻断同一清单中的可继续候选。

G3R—G3H 回归测试已按业务不变量合并到 `test_contracts.py`、`test_versioning.py` 和 `test_vertical_slice.py`，不再保留按微阶段镜像的测试模块。

## 6. 当前差异评审边界

以下纵向职责链已经完成：

1. 将四个观察维度升级为人工批准的有限 factor schema；
2. 实现确定性 Judgment evaluator；
3. 设计最小 ScoreContribution 公式、幂等键与版本；
4. 建立统一 `appointment_delegation` shadow runner；
5. 输出李世民、刘邦、朱元璋可追溯的 scored demo 报告。

差异评审已经形成首个人工口径结论：`authority_clarity` 只评价最终授权结果，韩信齐王授权记为 `positive`；请求、劝说和压力调整不降低该因子，也不另生成纳谏贡献。

名单式离线入口现可从三皇帝、四臣子 manifest 依次验证 Source Cache 与 Claim Extractor 冻结快照、运行确定性 Episode Kernel，并生成 scored shadow。首次运行处理 87 条 Assertion、78 个 Episode candidate、4 个评分单元；提供 prior record 时，无变化输入直接精确复用同一运行记录。

包 C 已增加持久化逐人物状态、服务响应 hash、变化 Episode 与 RuleEvidenceUnit 清单、慢通道 review job、原子 state 写入和故障后恢复。当前缓存无变化，因此服务调用、模型调用和数据库业务写入均为 0。

包 D 的首个复用切片已抽出通用有限因子 scored-shadow 内核，`appointment_delegation` 与 `talent_discovery` 均通过薄规则配置使用同一校验、Judgment、ScoreContribution、lineage 和汇总职责链。`talent_discovery` 首批 4 个 gold case 中，陈平生成 1 个 positive shadow contribution；魏徵因发现链三项直接证据缺失而阻断；韩信齐王授权与蓝玉晋升只作规则排除上下文。跨规则审计明确将 `appointment_delegation` 标为 supporting-only，不重复结算职位适配、授权质量或后续战果。

在正式接受 Gate 通过前，仍不开放正式 Judgment、45 分档位、总榜或生产切换。

## 7. 历史审计

早期 fine-type Relation 失败继续保留在 `24-*` 至 `29-*` 历史审计中，只用于说明精细历史关系图尚未达到发布阈值。逐条 endpoint 展开和 G3C—G3H 微阶段说明已从长期文档层移除，结构化运行产物应保存在 `eval/` 或外部 artifact。
