# G3R Endpoint 受控双审结果

> 状态：`adjudicated_endpoint_gate_passed`
>
> 日期：2026-07-13
>
> 实验代码：`G3R-ENDPOINT-SAMPLE-7D75C479870829643750`

## 1. 结论

G3R 在新 blocking 候选分布上完成一次 30 项受控双审。总体 direct agreement 为 93.33%，coarse type agreement 为
86.67%，均达到预设的 90% / 80% 可学习性阈值，说明候选 blocking 后的 endpoint direct/coarse 工作流值得继续。

4 项分歧现已完成隔离第三方裁决，adjudication 已清零，endpoint agreement Gate 通过。该结论仍不是 G3R/S4 pass，不生成
accepted EpisodeRelation，也不开放 G3C；裁决详情见[《G3R Endpoint 裁决结果》](27-G3REndpoint裁决结果.md)。

## 2. 样本冻结

样本只依据数据集配额、candidate code 和 blocking signal signature 机械抽取：

- I：从 119 个 blocking 候选中选 20；
- J：从 19 个 blocking 候选中选 10；
- 覆盖仅时间窗口、时间窗口加稀有 endpoint 实体、仅稀有 endpoint 实体等信号组合；
- 抽样未读取 Gold、旧 Relation、score、旧 reviewer 输出或任何判断标签；
- sample worklist 与 manifest 分离，reviewer 只获得 worklist。

## 3. 隔离双审结果

两个 reviewer 分别只读取相同 endpoint worklist，不读取 manifest、Gold、旧 Relation/review/score 或彼此输出。

| 范围 | 候选 | direct 一致 | direct rate | coarse 一致 | coarse rate | 待裁决 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| I | 20 | 19 | 95% | 18 | 90% | 2 |
| J | 10 | 9 | 90% | 8 | 80% | 2 |
| 合计 | 30 | 28 | 93.33% | 26 | 86.67% | 4 |

无分歧的 26 项中：

- 12 项形成 `proposed_direct_relation`；
- 14 项形成 `proposed_distinct_unrelated`；
- 这些仍只是 proposal，不是正式 Relation。

Reviewer B 首次输出把 evidence refs 写成占位字符串。中央验证器在任何一致性计算前拒绝全部结果；随后只按 worklist 把 refs
替换为左右端真实 Assertion refs，原 direct/coarse/reason 判断保持不变。修正后 30/30 通过 evidence lineage 校验。该过程验证了
结构错误不会被退出码或自报成功掩盖。

## 4. 失败关闭与裁决输入

4 项分歧已机械封装为独立 adjudication worklist，包含：

- 原 endpoint evidence；
- 两位 reviewer 的冻结判断、证据引用和理由；
- 原 sample task/hash 与 reviewer response hash；
- 禁止 Gold、旧 Relation 和 score 的裁决规则。

第三方裁决已按上述输入完成，4/4 分歧均形成有效 endpoint proposal，未留下 `insufficient`。裁决只清理 direct/coarse
proposal 分歧，没有直接接受细类型 Relation。

## 5. 当前判断

这次实验支持以下结论：

- blocking 后的 endpoint direct/coarse 两级识别达到继续研究阈值；
- 不需要恢复 254 对或 138 个 blocking 候选的全量长时间审查；
- 4 项 adjudication 已处理完毕，下一步只对 15 项 `proposed_direct_relation` 进入细类型 Relation version / graph invariants 小切片；
- S4 strict precision/recall 尚未重评，J 的 4 条边界未映射 Gold relation 仍未恢复；
- Relation 继续是独立实验轨，G3A/G3B 的 Core 状态不受影响，G3C 继续阻断。
