# G3F 缺口输入 Gate

> 状态：`source_gap_input_gate_passed_for_shadow_delta`
>
> 日期：2026-07-13
>
> 规则：`appointment_delegation`

## 1. 结论

G3E 锁定的 3 个候选已完成 proposal-only 输入 Gate：

| Gate 结果 | 数量 |
| --- | ---: |
| `accepted_for_shadow_delta` | 3 |
| `unresolved` | 0 |
| `rejected` | 0 |
| 现有 Episode arc member | 1 |
| context Assertion 候选 | 1 |
| 新 SourcePassage 候选 | 1 |
| 新 Assertion 候选 | 2 |
| 新 Episode 候选 | 1 |

`shadow_delta_authorized=true`，表示下一步可以把这些候选应用到 RuleEvidenceUnit shadow 副本并重算语义/证据版本；当前 `readiness_rerun_authorized=false`，因为 delta 尚未物化和审计。

正式 Assertion、Episode、RuleEvidenceUnit、Projection、Judgment、Score 和数据库写入均为 0。

## 2. 鄂尔泰：现有 Episode arc review

候选：`EP-8CB3B50DDAB3A262F495@v1`。

审查依据：

- 与当前单元人物一致；
- 时间为雍正四年，处于鄂尔泰云贵治理任期；
- 原文承接已获认可的改土归流方案；
- 同时记录破寨、降寨、安抚户口、皇帝嘉奖和真除云贵总督；
- 可补充当前单元缺少的履职结果与皇帝反馈。

处置：`same_scoring_arc / episode_arc_member / outcome`。该结论只授权把冻结 Episode 作为 RuleEvidenceUnit shadow 成员，不创建正式 Relation。

## 3. 隆科多：context Assertion boundary review

来源：现有 `SP-3C5A229F9056917E5728`。

候选 Assertion 概括：胤禛称隆科多前期颇著勤劳并因此予以异数，后因交结专擅、诸事欺隐而收回所赐特典。

SourcePassage v2 的 content hash、span、section 和 lineage 已通过合同校验。原文是皇帝对前期表现及后期失误的连续归因，但不是独立任命或结果事件，因此处置为：

```text
context_for_rule_evidence_unit
member_role=context
proposed_episode_ref=null
```

这避免为了补 `person_task_fit` 和净效果而伪造新 Episode。

## 4. 周勃：连续结果 Passage 与 Episode boundary review

原复任 Passage `SP-4160FC757A0360C18492` 的连续上下文记载：复任十余月后，文帝令周勃率先就国，周勃再次免相。

G3F 生成一个确定性 SourcePassage v2 候选：

- raw text 只包含该直接后续结果；
- span 紧接原复任 Passage；
- content hash 与 raw text 一致；
- 通过 `antecedent` link 保留原复任 Passage lineage；
- 不包含后续入狱等与本缺口无关材料。

基于该 Passage 的 Assertion 候选通过 AssertionDraft 与 PassageSupport 校验，处置为 `core_of_new_episode / outcome`。新 Episode 仍以 `EP-SHADOW-*` 标识，不能冒充正式 Episode。

## 5. Gate 边界

输入 Gate 通过只证明：

- Passage 原文、hash、span 与连续关系可验证；
- Assertion 的主体、动作、人物归属、支持字段和 proposal-only provenance 合法；
- Episode/context 边界与当前规则的最小补证问题匹配；
- 候选没有读取 Gold、旧判断或分数。

它不批准：

- 将候选写入正式事实表；
- 接受正式 Relation 或 RuleEvidenceUnit；
- 直接修改已有 Projection/Judgment；
- 生成 factor values 或 Score。

后续 G3G 已将 3 个候选应用到 RuleEvidenceUnit shadow 副本，并通过成员去重、semantic/evidence version、fingerprint 和 lineage 审计；结果见 [G3G RuleEvidenceUnit Shadow Delta](36-G3GRuleEvidenceUnitShadowDelta.md)。Projection 重建与 readiness 重跑现已授权。
