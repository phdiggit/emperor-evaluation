# 第五项 B：用人与授权（V4 业务规则）

> 状态：`review_ready`  
> 当前阶段：定义输入类型、边界和首条纵向切片；数值因子与公式待后续专门 Gate。

## 1. 核心问题

> 统治者能否识别、任用、授权、保护和组织人才，并限制亲旧近幸对公共任用的污染？

本项评价统治者本人的用人判断与组织行为，不以臣子最终名气替代皇帝责任，也不把所有臣子成就自动归功于皇帝。

## 2. 五个 rule

```text
talent_discovery
appointment_delegation
team_building
tolerate_talent
anti_nepotism
```

## 3. 输入类型

| rule_code | input_type |
| --- | --- |
| `talent_discovery` | episode |
| `appointment_delegation` | episode |
| `team_building` | person_snapshot |
| `tolerate_talent` | episode |
| `anti_nepotism` | episode + aggregate_context |

首轮只实现 `appointment_delegation`。其余规则完成契约和 gold cases 后再进入实现。

## 4. `talent_discovery`

评价：

- 是否识别此前未进入核心视野的人才；
- 是否接受有效荐举并完成试用/拔擢；
- 是否突破身份、阵营或既有偏见；
- 是否形成可重复的人才发现渠道。

不计入：

- 普通升迁；
- 对已有名臣的常规任命；
- 只有“任官”而无发现链；
- 后世因其成名反推皇帝早已识才。

coverage unit：一次独立发现/引入事件。  
scoring unit：被发现人物的一次独立识别链。

## 5. `appointment_delegation`

评价：

> 皇帝是否把合适的人放到合适的岗位、任务或权责链上，并产生可解释的反馈？

一个完整 episode 通常包含：

- 皇帝的任用、授权、复用或托付动作；
- 被任用者；
- 具体岗位、任务或责任域；
- 权责边界；
- 履职结果或合理反馈；
- 皇帝后续监督、延续、纠错或失误。

### 正向

- 关键任务与人才适配；
- 权责清楚；
- 结果良好；
- 在逆阻力下作出正确用人；
- 能根据反馈持续使用或纠正安排。

### 负向

- 明显不适任仍委以关键权责；
- 私人偏爱、轻率判断或错误授权造成明确损害；
- 权责设计失当；
- 在清楚负面反馈后继续错误任用；
- 对关键任务造成可归因的失败或治理损害。

### 不自动计入

- 单纯官职记载；
- 单纯赏罚、诛废或政治结局；
- 臣子取得成果但看不出皇帝任用/授权链；
- 战役胜负本身；
- 与任用安排没有直接关系的后期清洗；
- 同一任命、职责和结果拆成三次重复贡献。

coverage unit / scoring unit：一次独立任用—职责—反馈 episode。

## 6. `team_building`

评价一个冻结时间窗内的整体人才结构：

- 人才质量；
- 核心岗位覆盖；
- 决策、行政、军事、纠错等功能互补；
- 团队持续性；
- 对单一亲信或单一类型人才的依赖；
- 关键岗位长期空缺或劣币驱逐良币。

必须消费 canonical person 集合和 PersonProfileSnapshot；同一人物跨事件、阶段或 target 只计一次。不得从单条 episode 临场给人物定级。

## 7. `tolerate_talent`

评价：

- 容纳直言和不同意见；
- 保护能臣的人身与表达安全；
- 允许专业判断；
- 在冲突后修复授权信用；
- 负向伤害、压制、冤杀或系统性堵塞反馈。

负向必须区分：

- 人物确有重大过错；
- 皇帝责任；
- 一般刑罚；
- 政治结局；
- 对人才安全和组织纠错的实际损害。

## 8. `anti_nepotism`

评价：

- 是否限制外戚、宗室、近幸、宦官、宠臣和私人网络污染任免；
- 是否维持公开、专业或可纠错的选任渠道；
- 是否纵容小圈子长期垄断关键岗位；
- 是否因亲疏取代能力与公共责任。

单个亲属任职不自动负向；需判断能力、程序、岗位和结构性影响。长期制度可使用 aggregate_context，个案仍使用 episode。

## 9. 人物画像

人才质量因子只能来自有版本的 PersonProfileSnapshot。

原则：

- 能力等级与负面政治风险正交；
- 覆盖不足只影响 confidence/readiness，不机械降档；
- 人物画像不能因本 rule 需要而临场调整；
- 历史级/顶级守门员标准属于人物画像规则，不在本项重复实现。

## 10. 跨规则边界

- 发现人才与任用授权分开：发现是进入视野，任用是岗位/任务适配。
- 任用授权与军事成果分开：本项看用人判断，军事项看战争净收益。
- team_building 与单事件分开：团队是集合快照。
- 容才与任用结果分开：表达/安全和岗位效果是不同属性。
- 反任人唯亲与一般任用失误分开：前者关注私人渠道污染。

## 11. 首条纵向切片验收

`appointment_delegation` 试点必须证明：

- 同一任用事件跨来源只形成一个 episode；
- 任命、职责和结果不重复计分；
- 跨皇帝人物正确归属；
- 成功与失败边界均有证据；
- 新增同义史料不触发重判；
- 一次真正新事件只处理局部 delta；
- 每个贡献可追溯到 passage；
- V3 对照差异有分类和人工裁定。

## 12. 尚未批准

当前未批准：

- 材料分值；
- 因子倍率；
- 衰减公式；
- 各 rule 权重；
- 正负上限；
- 正式档位映射；
- 生产 scorer。

这些必须在事件模型和 gold set 验证后单独审查。

## 13. G3C 最小 RuleEvidenceUnit shadow 结果

首轮 `appointment_delegation` shadow 已按评分最小充分原则完成：13 条评分 Relation proposal 与 2 条 `scoring_arc_only` 建议组成 7 个候选分量，经本规则边界审查形成 4 个 RuleEvidenceUnit draft、排除 3 个缺少任命/授权链的分量、0 unresolved；Episode 重复消费为 0。

每个 draft 只声明成员角色、皇帝归责、权责决策弧、证据 lineage 和四个问题的 readiness。问题级 `evidence_gap` 不得解释为负向判断或零分。具体审计见 [G3C 最小 RuleEvidenceUnit Shadow](../../32-G3C最小RuleEvidenceUnitShadow.md)。

该结果不改变本文件第 12 节：正式 RuleEvidenceUnit 接受、Projection、Judgment、材料分值、公式和生产 scorer 仍未批准。

## 14. G3D Projection/Judgment shadow readiness

4 个 RuleEvidenceUnit draft 已生成 4 个中立 Projection draft。人工正负案例审查形成 1 个 `mixed` Judgment shadow candidate、3 个 `blocked_evidence`；正向、负向和混合信号均由当前 Assertion 支持，但关键 readiness 缺口会机械阻断方向。具体结果见 [G3D Projection 与 Judgment Shadow Readiness](../../33-G3DProjection与JudgmentShadowReadiness.md)。

本阶段的四维 observation 只用于验证问题边界，不是已批准 factor values。正式方向、档位、材料分值、权重和 ScoreContribution 仍受第 12 节约束。

## 15. G3E Judgment 缺口库存检索

3 个 `blocked_evidence` 已各自冻结最小问题并完成本地库存检索：鄂尔泰地方治理命中 1 个现有结果 Episode；隆科多和周勃各命中 1 个现有 SourcePassage 候选。具体来源、停止条件和后续 Gate 见 [G3E Judgment 缺口定向库存检索](../../34-G3EJudgment缺口定向库存检索.md)。

库存命中不是正式事实接受。1 个 Episode arc review 与 2 个 Assertion/boundary review 完成前，不得更新 RuleEvidenceUnit 或重跑 Judgment readiness。

## 16. G3F 缺口输入 Gate

G3E 的 3 个候选已完成 proposal-only 输入 Gate：鄂尔泰结果 Episode 通过同一评分弧审查；隆科多 Passage 形成 context Assertion 候选但不新造 Episode；周勃连续原文形成新的 Passage、outcome Assertion 和 outcome Episode 候选。具体见 [G3F 缺口输入 Gate](../../35-G3F缺口输入Gate.md)。

上述候选只获准进入 RuleEvidenceUnit shadow delta。delta 物化与版本审计前，仍不得更新 Projection 或重跑 Judgment readiness。

## 17. G3G RuleEvidenceUnit shadow delta

3 个候选已应用到 RuleEvidenceUnit shadow 副本：3 个单元保持稳定 `unit_code` 并递增 semantic/evidence version，新增 2 个 Episode member、1 个 context Assertion 与 2 个 scoring-arc-only 引用；未受影响单元逐字段不变，剩余 readiness gap 和 Episode 重复消费均为 0。具体见 [G3G RuleEvidenceUnit Shadow Delta](../../36-G3GRuleEvidenceUnitShadowDelta.md)。

当前只授权重建受影响的 Projection draft 并重跑 Judgment readiness。正式 Judgment、factor values 和 ScoreContribution 仍受第 12 节约束。

## 18. G3H Projection 增量重建与 readiness 重跑

G3G 变化的 3 个单元已局部重建 Projection，未变化的鄂尔泰军务 Projection 与 Judgment review 逐字段复用。4 个 Projection 均通过 readiness，形成 1 个 `positive`、3 个 `mixed` shadow candidate，`blocked_evidence=0`。具体见 [G3H Projection 增量重建与 Readiness 重跑](../../37-G3HProjection增量重建与Readiness重跑.md)。

周勃项虽有三项负向观察，但授权清晰度为正向；在因子权重和聚合公式未批准前，正负信号并存只能机械输出 `mixed`，不得解释为正式负向评分。正式 Judgment、factor values、ScoreContribution 和排名仍受第 12 节约束。
