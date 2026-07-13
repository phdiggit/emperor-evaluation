# G3R Endpoint 双审合同

> 状态：`executed_and_adjudicated`
>
> 日期：2026-07-13
>
> 实现代码：`G3R-ENDPOINT-REVIEW-SLICE-2`

## 1. 结论

G3R blocking 候选已经能够转换为最小 endpoint evidence 双审 worklist，并能对两个隔离 reviewer 的结构化输出执行完整性、证据
lineage、一致性与失败关闭校验。本切片只建立请求和处置合同，尚未对 I/J 全部候选执行 reviewer，因此不是 G3R/S4 pass。

worklist 不包含 Historical Gold、旧 Relation review、candidate relation、score、sample manifest 或另一 reviewer 输出。运行时会重新生成
blocking 结果并与传入报告精确比较，防止候选清单或计数被修改后继续送审。

## 2. Reviewer 输出合同

每个 reviewer 必须独立、完整且唯一覆盖 worklist 中全部候选，并为每项输出：

```yaml
candidate_code: RBC-...
direct_relation: yes | no | insufficient
coarse_type: authority_change | mandate_or_outcome | explicit_causal | null
evidence_assertion_refs: [左端至少一条, 右端至少一条]
reason: 非空说明
```

约束如下：

- `yes` 必须选择三个粗类型之一；
- `no` 或 `insufficient` 的 `coarse_type` 必须为 `null`；
- evidence refs 只能来自当前候选两端，并且必须同时覆盖左右端；
- reviewer 必须声明未读取禁止输入、未读取另一 reviewer 输出、未执行正式接受；
- 缺项、重复项、未知候选、单端 evidence、非法枚举或 worklist hash 不一致均失败关闭。

## 3. 双审汇总

汇总器要求两个不同 reviewer，对每个候选分别比较 direct 与 coarse 结果：

- direct/coarse 完全一致且不是 `insufficient`，才形成 `proposed_direct_relation` 或
  `proposed_distinct_unrelated`；
- 任一分歧或任一方为 `insufficient`，结果固定为 `needs_adjudication`；
- direct agreement 低于 90%、coarse agreement 低于 80%，或仍有 adjudication 项时，agreement Gate 不通过；
- 即使 agreement Gate 通过，输出也只是 proposal，不是 accepted EpisodeRelation。

## 4. I/J Worklist

已从 G3R blocking 报告生成确定性 UTF-8 worklist：

| 数据集 | task code | 候选数 | reviewer 执行 | 模型调用 | 数据库写入 | 正式 Relation |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| I | `G3R-ENDPOINT-57940DFFCD562DB66F8E` | 119 | 未执行 | 0 | 0 | 0 |
| J | `G3R-ENDPOINT-D23B3A2D849000704859` | 19 | 未执行 | 0 | 0 | 0 |

相同输入重建得到相同 task code、worklist hash、候选顺序和 evidence 内容。每个候选保留独立稳定 code，可按 candidate 粒度恢复或
重试，不依赖整批模型输出作为唯一状态。

## 5. 后续边界

后续 30 项受控双审已经执行，结果见 `26-G3REndpoint受控双审结果.md`；4 项分歧也已完成隔离裁决，结果见
`27-G3REndpoint裁决结果.md`。endpoint agreement Gate 已通过，但不得直接对 138 个候选恢复长时间全量审查；下一步仅允许对
15 项 direct proposal 进入细类型 Relation version / graph invariants 小切片，仍不得直接接受 Relation。G3C 继续阻断。
