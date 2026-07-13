# V4 文档导航

`docs/` 是 V4 当前规则、架构、契约和验收门禁的事实层。当前已有离线 HistoricalEpisode Kernel、通过真实数据库验证的 G3A PostgreSQL Core Registry，以及通过局部失效与真实库零写入重跑验证的 G3B 同步 Core Shadow Runner；仍没有 worker 或 scorer。

当前实现状态为 `M1 conditional_pass / G2-Core passed_for_shadow_implementation / G3A passed_shadow_registry / G3B passed_sync_local_invalidation / G3R minimum_sufficient_relation_slice_passed / G3C rule_evidence_unit_shadow_ready / G3D judgment_shadow_readiness_passed / G3E source_gap_inventory_complete / G3F source_gap_input_gate_passed / G3G rule_evidence_shadow_delta_ready_for_projection_rebuild / G3H incremental_judgment_shadow_rerun_passed, formal scoring blocked`。G3H 只重建 3 个变化 Projection，逐字段复用 1 个 Projection/Judgment review，4 项 readiness 全部通过，形成 1 个 `positive`、3 个 `mixed` shadow candidate。正式 Relation、正式事实输入、RuleEvidenceUnit、Projection、Judgment、factor values、Score、新 blind、V3/生产数据库和生产切换继续关闭。

## 文档状态

文档顶部使用以下状态：

- `draft`：正在形成，不能作为实现依据；
- `review_ready`：内容完整，可进入人工审查；
- `accepted`：当前有效，可驱动实现；
- `superseded`：已被新版本替代，仅保留历史；
- `legacy_reference_only`：只可用作 V3 经验或反例。

D0 文档 Gate 所需的领域、证据、输入类型、状态机、覆盖度、智能体边界和四份契约均已人工接受。
`01-V3教训与V4约束.md` 与 `08-V3并行运行与迁移方案.md` 仍为
`review_ready`，它们不阻断 Historical Episode Kernel 的离线实现，但在涉及 V3 迁移或生产并行前必须另行接受。
最高层评分标准是人工复核保留的业务标准；若与 V4 新文档冲突，必须开专门审查，不得静默选择一方。

## 阅读路径

### 业务上位规则

1. `项目总纲/皇帝综合评价体系评分标准.md`
2. `00-V4项目章程.md`
3. `项目总纲/总规则.md`

### 架构与数据语义

4. `01-V3教训与V4约束.md`
5. `02-领域模型.md`
6. `03-证据与历史事件模型.md`
7. `04-规则输入类型与投影模型.md`
8. `05-任务状态机与增量失效.md`

### 质量、安全与迁移

9. `06-覆盖度与验收标准.md`
10. `07-智能体边界与成本预算.md`
11. `08-V3并行运行与迁移方案.md`
12. `09-V4测试与验证策略.md`
13. `10-G2.5盲测与去Oracle化.md`
14. `11-G2.6事件边界与关系模型.md`
15. `12-G2.6D.1契约硬化与Graph-G3前置条件.md`
16. `13-G2.6E-Graph-Blind-Holdout结果.md`
17. `14-G2.6F原子边界与关系处置硬化.md`
18. `15-G2.6G物化阻断与v2.4身份契约.md`
19. `16-G2.6H责任域措辞阻断与v2.6边界.md`
20. `17-G2.6I盲测结果与Assertion证据扇出阻断.md`
21. `18-G2.6J-AssertionEvidence扇出硬化.md`
22. `19-G2.6J盲测结果与史源切片阻断.md`
23. `20-G2.6K0史源切片开发资格.md`
24. `21-G2终止与G3A核心Shadow决策.md`
25. `22-G3A核心Registry首个实现切片.md`
26. `23-G3B同步CoreShadowRunner.md`
27. `24-G3R候选Blocking首个切片.md`
28. `25-G3REndpoint双审合同.md`
29. `26-G3REndpoint受控双审结果.md`
30. `27-G3REndpoint裁决结果.md`
31. `28-G3R细类型Relation与图约束首个切片.md`
32. `29-G3R细类型Relation定向补证复核.md`
33. `30-G3REndpoint样本与裁决明细.md`
34. `31-G3R评分最小充分Relation重解释.md`
35. `32-G3C最小RuleEvidenceUnitShadow.md`
36. `33-G3DProjection与JudgmentShadowReadiness.md`
37. `34-G3EJudgment缺口定向库存检索.md`
38. `35-G3F缺口输入Gate.md`
39. `36-G3GRuleEvidenceUnitShadowDelta.md`
40. `37-G3HProjection增量重建与Readiness重跑.md`

### 契约与试点规则

41. `contracts/史源缓存服务契约.md`
42. `contracts/事实抽取服务契约.md`
43. `contracts/历史事件包契约.md`
44. `contracts/规则判断结果契约.md`
45. `证据规则/证据裁量总则.md`
46. `证据规则/史料检索与回源工作流.md`
47. `分项规则/第五项统治者政治素质/B用人与授权.md`

## 目录职责

| 目录 | 负责 | 不负责 |
| --- | --- | --- |
| `项目总纲/` | 最高层评分结构、项目总规则、发布边界 | 具体服务接口、运行参数 |
| `证据规则/` | 史源、断言、冲突、归因和入证门槛 | 单个规则公式、数据库表 |
| `分项规则/` | 分项业务语义、输入类型、边界和反例 | 通用证据规则、基础设施 |
| `contracts/` | 稳定输入输出、幂等、版本和失败语义 | 具体语言、框架和部署 |

## 当前禁止事项

- 不把 V3 表结构或脚本名称写成 V4 领域事实。
- 不以 Markdown 文件数量替代业务对象设计。
- 不创建空 `scripts/`、`db/`、`tests/` 目录表示“已开工”。
- 不先写 Schema 再倒推领域模型。
- 不把模型 prompt 当作业务契约。
- 不把 shadow 与正式发布混为一谈。
