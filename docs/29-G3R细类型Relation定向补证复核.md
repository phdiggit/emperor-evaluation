# G3R 细类型 Relation 定向补证复核

> 状态：`fine_relation_graph_gate_failed_closed_after_gap_review`
>
> 日期：2026-07-13
>
> 任务代码：`G3R-FINE-GAP-3CE30F2D53282D36C261`

> 后续解释：本文件保留细类型 policy v1 的历史失败关闭结果。该结果对评分链的阻断解释已由[《G3R 评分最小充分 Relation 重解释》](31-G3R评分最小充分Relation重解释.md)取代，不得把“fine type 不唯一”等同于“评分必要语义 unresolved”。

## 1. 结论

首轮细类型审查的 4 项 unresolved 已全部进行 SourcePassage 定向核对：

- 1 项由现有上下文补足，形成 `causal_followup` proposal；
- 3 项确认需要新的 Assertion 级证据，继续保持 unresolved；
- versioned Relation proposal 从 11 项增加到 12 项；
- 12 项图约束仍全部通过，无 invariant error；
- 细类型 Graph Gate 因 3 项 unresolved 未清零而继续失败关闭；
- 正式 EpisodeRelation 与数据库业务写入均为 0。

## 2. 已解决项

`RBC-AED36A09908D78FD4401` 的两端是蒙毅被杀与蒙恬被赐死。原 endpoint Assertion 摘要不足以证明直接因果，但两端
SourcePassage 构成连续原文：蒙毅被杀后，文本紧接“二世又遣使者之阳周”，并以“卿弟毅有大罪，法及内史”作为对蒙恬执行
处置的明确依据。因此该项从左端指向右端，细类型为 `causal_followup`，confidence 为 0.96，状态仍仅为 `proposed`。

## 3. 仍需补证项

| candidate | 当前缺口 |
| --- | --- |
| `RBC-1B5EF40E8FE602C1C2E7` | 多次递进收权之间缺少直接绑定同一授权对象或状态转换的 Assertion |
| `RBC-7DB5F37DCBA46F15191E` | 左端授予理籓院与修纂职务，右端削太保与世职；被削对象不是左端 Assertion 明确授予的职位 |
| `RBC-92189019556268DEDD10` | 两项相邻收权具有不同处分对象和独立决策，不能只凭文本相邻强判细类型 |

仓库当前 source-v2 输入中只存在已经进入 endpoint 的相同 Assertion 与 Passage，没有发现可直接补足上述三种语义槽位的新
Assertion。重复读取相同上下文不会消除缺口。

## 4. 审计说明

补证 response 与中央审计结果在仓库库存搜索前已经冻结。后续只读库存搜索的匹配范围过宽，输出中出现了一个
`historical_gold_relation_v2.json` 文件路径和重复 Assertion ref；没有打开或解析该文件的 Relation label、score 或判断内容，也没有
用该输出修改已冻结 response。该搜索不作为证据来源，后续 source inventory 必须显式排除 `*gold*` 与旧 Relation 产物。

## 5. 当前边界

下一步应建立只包含三项缺失语义槽位的 source-gap 请求：目标是同一授权对象的授予/撤销绑定，或两次处分间的明确直接转换。
在新 Assertion 经既有 SourcePassage lineage 和 Schema 校验进入输入前，不再重复细类型 reviewer。不得连接 V3 数据库，不得用
Gold、旧 Relation 或 score 反推，不得接受现有 12 项 proposal，也不得开放 G3C。
