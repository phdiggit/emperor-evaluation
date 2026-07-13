# V4 文档导航

`docs/` 是 V4 当前规则、架构、契约和验收门禁的事实层。当前已有离线 HistoricalEpisode Kernel 原型、轻量测试和 Oracle-assisted 试点评估；仍没有数据库 Schema、worker 或 scorer。

当前实现状态为 `M1 conditional_pass / G2.6J failed_closed / G2.6K0 S4 blocked`。G2.6K0 已建立 Source Cache v2、确定性 section-aware slicer、S1—S5 机械早停和 8 场景 protocol smoke；I/J 的开放开发输入已通过 S1/S2，Boundary policy v2.10 后也达到 S3 episode 门槛。独立 Relation review 与 Relation Gold ontology audit v2 已完成；修订后的开发 Gold 下，I/J strict precision/recall 分别为 50%/73.33% 和 40%/25%，仍未通过 S4。旧 Rule Gold 不再用于当前 Relation ontology 放行。新 blind holdout 与 PostgreSQL G3 仍未授权。

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

### 契约与试点规则

24. `contracts/史源缓存服务契约.md`
25. `contracts/事实抽取服务契约.md`
26. `contracts/历史事件包契约.md`
27. `contracts/规则判断结果契约.md`
28. `证据规则/证据裁量总则.md`
29. `证据规则/史料检索与回源工作流.md`
30. `分项规则/第五项统治者政治素质/B用人与授权.md`

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
