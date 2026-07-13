# G3R Endpoint 裁决结果

> 状态：`endpoint_agreement_gate_passed_after_adjudication`
>
> 日期：2026-07-13
>
> 实验代码：`G3R-ENDPOINT-SAMPLE-7D75C479870829643750`

## 1. 结论

30 项受控 endpoint 双审中的 4 项分歧已由隔离的第三方 reviewer 完成裁决。4/4 裁决输出通过中央 Schema、候选覆盖、
evidence lineage 和禁止输入检查，剩余 evidence gap 为 0，endpoint agreement Gate 通过。

裁决后形成：

- 15 项 `proposed_direct_relation`；
- 15 项 `proposed_distinct_unrelated`；
- 0 项 `insufficient`；
- 0 项正式接受的 EpisodeRelation；
- 0 次数据库业务写入。

原双审 direct agreement 93.33%、coarse type agreement 86.67% 是对 reviewer 一致性的度量，不因第三方裁决而重写。

## 2. 裁决隔离

裁决者只读取机械生成的 4 项 adjudication worklist。输入包含 endpoint evidence、两位 reviewer 的冻结输出及其引用，不包含
Gold、旧 Relation、score 或其他仓库判断材料。裁决者不得写正式事实、规则判断、分数或数据库。

中央程序独立验证：

- 输出 Schema 版本正确；
- 4 个 candidate code 唯一且完整覆盖；
- evidence refs 均属于相应左右 endpoint；
- 输出只使用允许的 direct/coarse proposal 枚举；
- 每项理由和裁决证据引用齐备。

## 3. Gate 边界

本次通过的是 endpoint direct/coarse agreement Gate，只证明该候选分布上的两级审查合同可继续进入小范围细化。它不表示：

- G3R 或 S4 已通过；
- strict precision/recall 已重新达到 90%/85%；
- 任一 proposal 已成为 accepted EpisodeRelation；
- G3C、正式 Projection、Judgment、Score 或生产切换已开放。

## 4. 下一步

该小切片已执行，结果见[《G3R 细类型 Relation 与图约束首个切片》](28-G3R细类型Relation与图约束首个切片.md)。15 项中 11 项形成
versioned proposal，4 项因细类型不能唯一确定而失败关闭；15 项 `proposed_distinct_unrelated` 未进入 Relation 物化。仍需按 S4
原门槛独立判断是否具备正式资格。
