# G3E Judgment 缺口定向库存检索

> 状态：`source_gap_inventory_complete_pending_input_gates`
>
> 日期：2026-07-13
>
> 规则：`appointment_delegation`

## 1. 结论

G3D 的 3 个 `blocked_evidence` Projection 已分别冻结最小补证问题，并只读检索当前 source-v2 input 与无 Gold 的 Episode blocking inventory：

| 库存结果 | 数量 |
| --- | ---: |
| 现有冻结 Episode 候选 | 1 |
| 现有 SourcePassage 候选 | 2 |
| `not_found_stop` | 0 |
| 待 Episode arc review | 1 |
| 待 Assertion/boundary review | 2 |

3 个 gap request 均有且只有一个最小候选，已达到本轮停止条件。没有执行外部抓取，没有读取 Gold、旧 Relation、旧 Judgment 或 score，也没有连接数据库。

库存命中不等于事实输入已经被接受。当前 `readiness_rerun_authorized=false`；正式 Assertion、Episode、Projection、Judgment、Score 和数据库写入均为 0。

## 2. 最小问题与停止条件

### 鄂尔泰地方治理与边界任务

问题：同一云贵任用期内，是否存在可归责的履职结果及皇帝反馈？

命中：冻结 Episode `EP-8CB3B50DDAB3A262F495@v1`。其 Assertion 记录鄂尔泰在仲家苗地破寨、降寨、安抚户口，并因成功迅速获嘉奖、真除云贵总督。

停止：已找到首个同时包含结果和皇帝反馈的同人物、同任用期 Episode，不再枚举其他战绩。该 Episode 仍需 `episode_arc_review`，确认是否与当前任命—治理建议—授权弧属于同一 scoring unit。

### 隆科多权责收缩轨迹

问题：是否有直接材料说明初始任用阶段的人岗表现，并足以与后期失误共同判断任用净效果？

命中：现有 `SP-3C5A229F9056917E5728` 原文含“前以隆科多、年羹尧颇著勤劳，予以异数”，并紧接交结专擅、欺隐与收回特典。

停止：同一 Passage 已覆盖前期表现归因和后期反馈，不再扩展隆科多全传。现有 Assertion 只结构化了收权动作，因此必须先执行 `assertion_boundary_review`，不能直接进入 Projection。

### 周勃任相与复任

问题：复任周勃后是否有直接后续履职或撤任结果？

命中：`SP-4160FC757A0360C18492` 的连续 `context_after` 记载复任十余月后文帝令周勃率先就国，周勃再次免相。

停止：已在复任句的同一连续原文找到首个直接结果，不再扩大检索。该句尚未成为独立 `raw_text` passage 和 Assertion，必须依次经过 `segmentation_assertion_boundary_review`。

## 3. 契约边界

库存 response 只能选择：

```text
existing_episode_candidate
source_passage_candidate
not_found_stop
```

每项必须声明所补 observation、readiness 问题、候选引用、后续 Gate、理由和停止条件。

- 现有 Episode 候选必须有 Episode、Assertion、SourcePassage lineage；
- SourcePassage 候选不得声称已经存在 accepted Assertion 或 Episode；
- `not_found_stop` 不得伪造候选；
- 路径中含 Gold、旧 Relation 或 Judgment 的库存文件一律拒绝；
- 任一候选未通过后续输入 Gate 前，不得重跑 Judgment readiness。

## 4. 下一步

下一步只处理这 3 个候选：

1. 鄂尔泰：审核现有结果 Episode 是否属于当前任用—反馈评分弧；
2. 隆科多：从现有 Passage 提出规则中立 Assertion，并做 boundary review；
3. 周勃：定向生成连续结果 Passage，再做 Assertion 与 boundary review。

后续 G3F 已完成这 3 个候选的输入 Gate，全部通过为 proposal-only shadow delta；结果见 [G3F 缺口输入 Gate](35-G3F缺口输入Gate.md)。候选尚未应用到 RuleEvidenceUnit，因此 readiness 重跑仍未授权。
