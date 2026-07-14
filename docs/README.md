# V4 文档导航

`docs/` 只保留长期有效的业务规则、领域契约、架构决策和必要审计摘要。运行展开、逐条 reviewer 明细和短命阶段报告应放入 `eval/<run>/` 或外部 artifact，不作为默认阅读路径。

## 当前实现

- HistoricalEpisode Kernel：可用于 shadow implementation
- G3A PostgreSQL Core Registry：通过
- G3B 同步局部失效：通过
- G3R—G3H `appointment_delegation` shadow：4 个 RuleEvidenceUnit / Projection / Judgment candidate 已通过 readiness
- Factor schema、ScoreContribution、统一 scored runner：已完成 shadow demo；首个因子差异已人工裁定
- 三皇帝名单式离线 `cache_mode=ensure` 编排：已贯通服务快照、Episode Kernel 与 scored runner
- 包 C：逐人物持久化状态、response hash、delta Episode、慢通道清单和失败恢复已通过 shadow 验证
- 正式评分、排名和生产切换：关闭

当前实现摘要统一见 [《G3R 评分最小充分 Relation 重解释》](31-G3R评分最小充分Relation重解释.md)。

## 日常阅读路径

### 业务上位规则

1. `项目总纲/皇帝综合评价体系评分标准.md`
2. `00-V4项目章程.md`
3. `项目总纲/总规则.md`

### 领域与证据

4. `02-领域模型.md`
5. `03-证据与历史事件模型.md`
6. `04-规则输入类型与投影模型.md`
7. `05-任务状态机与增量失效.md`
8. `06-覆盖度与验收标准.md`
9. `07-智能体边界与成本预算.md`
10. `09-V4测试与验证策略.md`

### 契约与试点规则

11. `contracts/史源缓存服务契约.md`
12. `contracts/事实抽取服务契约.md`
13. `contracts/历史事件包契约.md`
14. `contracts/规则判断结果契约.md`
15. `证据规则/证据裁量总则.md`
16. `证据规则/史料检索与回源工作流.md`
17. `分项规则/第五项统治者政治素质/B用人与授权.md`
18. `31-G3R评分最小充分Relation重解释.md`

## 历史审计

`10-*` 至 `23-*` 记录 G2.5、G2.6 与早期 Core 实验，只在定位历史回归时读取。它们不是活动实施计划，也不得驱动新增字母阶段。

原 `24-*` 至 `30-*` 的 Relation 微阶段文档已由 `31-G3R评分最小充分Relation重解释.md` 取代并从工作树删除；需要追溯 endpoint blocking、双审和细类型失败时使用 Git 历史及对应 `eval/` artifact。原 G3C—G3H 六份短命阶段文档也已合并进 `31`。

## 文档生命周期

文档顶部状态：

- `draft`：未形成稳定结论；
- `review_ready`：可人工审查；
- `accepted`：当前有效；
- `superseded`：仅作历史参考；
- `legacy_reference_only`：只可用作 V3 经验或反例。

新增长期文档必须满足至少一项：

- 改变评分业务规则；
- 改变稳定领域契约；
- 改变生产/数据安全边界；
- 记录不可逆架构决策。

单次运行结果、模型审查明细、增量重跑报告和微阶段状态不得新增长期文档。被新结论取代的阶段文档应在同一提交中合并或删除。

## 目录职责

| 目录 | 负责 | 不负责 |
| --- | --- | --- |
| `项目总纲/` | 评分结构、总规则、发布边界 | 服务接口、运行参数 |
| `证据规则/` | 史源、断言、冲突、归因和入证门槛 | 单规则公式、数据库表 |
| `分项规则/` | 分项业务语义、输入类型、边界和反例 | 通用基础设施 |
| `contracts/` | 稳定输入输出、幂等、版本和失败语义 | 框架和部署 |
| `eval/` | 冻结样本、运行结果和审计 artifact | 长期业务规则 |

## 当前禁止事项

- 不把 V3 表结构或脚本名写成 V4 领域事实。
- 不以文档、测试或阶段数量替代用户可见结果。
- 不为每个实现模块建立镜像测试文件。
- 不把模型 prompt 当作业务契约。
- 不把 shadow 与正式评分混为一谈。
