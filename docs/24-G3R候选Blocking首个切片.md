# G3R 候选 Blocking 首个切片

> 状态：`blocking_slice_passed_development_only`
>
> 日期：2026-07-13
>
> 实现代码：`G3R-RELATION-BLOCKING-SLICE-1`

## 1. 结论

G3R 已建立首个确定性、可审计的 Relation 候选 blocking，但 Relation 仍为实验性工作流，S4 仍未通过。新路径不再把同一
`evaluation_context` 下的全部 Episode pair 默认送审；冻结的 G2.6K0 全配对代码仅保留为历史开发审计协议。

本切片只生成 `proposed_for_relation_review` 候选，不生成 accepted EpisodeRelation，不写 PostgreSQL，不调用模型，也不触发
RuleEvidenceUnit、规则投影或评分。

## 2. Blocking 合同

一个 pair 至少命中以下一个信号才有审查资格：

- 两端共享只出现在当前 context 至多 6 个 Episode、且不是全 context 公共背景的 endpoint 实体；
- 两端共享同一 SourcePassage；
- 两端具有相同 focal person，且规范时间最小间隔不超过 10 年。

候选包含稳定 `candidate_code`、两端 Assertion refs、blocking reasons、信号值、频率或时间窗口及独立 evidence hash。
候选身份只由 endpoints、输入 Assertion 版本和 policy version 决定；增加不相关 Episode 不改变既有候选身份。

未通过 blocking 的 pair 语义固定为：

```text
not_review_eligible_not_distinct_unrelated
```

它表示“没有进入本轮 Relation 审查资格”，不表示已经证明两端无关。只有进入候选集的 pair 才能在后续独立 reviewer 中得到
`related`、`distinct_unrelated` 或 `unresolved` 处置。

## 3. 与旧全配对协议隔离

旧 `build_relation_review_plan` 继续服务已冻结的 G2.6K0 审计证据，不在本切片中改写。新
`build_relation_candidate_blocks` 从只含 Core Episode basis 的视图和 blind input 生成候选，拒绝 Historical Gold、旧 Relation
review 和 score 字段。实际候选构建不读取 Gold。

开放开发集 Gold 只在 builder 完成后由独立审计脚本计算候选召回，不能进入候选理由、候选身份或运行时输入。

## 4. I/J 开放开发集审计

| 数据集 | Episode | context 内理论 pair | blocking 候选 | 不送审 pair | 减少比例 | 可映射 Gold pair 候选召回 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| I | 26 | 205 | 119 | 86 | 41.95% | 15/15，100% |
| J | 15 | 49 | 19 | 30 | 61.22% | 4/4，100% |

J 的 8 条 Gold relation 中另有 4 条至少一个 Gold Episode 无法与当前 S3 Episode 按完整 core Assertion 集精确映射；这些关系不能
用于判断 blocking recall，也不能被记成 blocking 漏召。该缺口继续保留为 Episode boundary 前置限制。

审计重跑完全确定，模型调用、数据库写入、正式 Relation 数量均为 0。

## 5. 当前未通过项

该结果只证明候选 blocking 在 I/J 开放开发集上保留了所有当前可映射 Gold endpoint pair，并显著减少送审量。它尚未证明：

- 新候选集上的 endpoint evidence reviewer 准确率；
- 独立双审 direct/coarse 一致性可在完整候选分布复现；
- 细类型 Relation version 与 graph invariants；
- S4 strict precision ≥ 90%、strict recall ≥ 85%；
- J 的 4 条未映射 Gold relation 已恢复。

因此 G3R 仍为 `deferred_not_qualified`，G3C 继续阻断。下一切片应只对 blocking 候选建立 endpoint evidence review 请求与粗类型
处置，不恢复全 pair，也不接入正式持久化或评分。
