# 第五项 B：用人与授权（V4 业务规则）

> 状态：`scored_shadow_demo_ready`
> 当前阶段：`appointment_delegation` 已完成纵向 scored shadow，`talent_discovery` 已复用同一有限因子与 ScoreContribution runner 完成首个切片；正式 45 分汇总和生产计分仍关闭。

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
| `appointment_delegation` | episode / rule_evidence_unit |
| `team_building` | person_snapshot |
| `tolerate_talent` | episode |
| `anti_nepotism` | episode + aggregate_context |

首轮 `appointment_delegation` 已完成。第二条 `talent_discovery` 已冻结规则边界和首批 gold cases，并复用同一 scored-shadow 内核；其余规则完成契约和 gold cases 后再进入实现。

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

一个完整评分单元通常包含：

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
- 单纯赏罚、政治结局；
- 臣子取得成果但看不出皇帝任用/授权链；
- 战役胜负本身；
- 与任用安排没有直接关系的后期处置；
- 同一任命、职责和结果拆成三次重复贡献。

coverage unit / scoring unit：一次独立任用—职责—反馈 episode，或按同一评分决策弧去重后的 RuleEvidenceUnit。

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
- 负向伤害、压制或系统性堵塞反馈。

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

## 12. `appointment_delegation` 有限因子与 shadow contribution

`talent_discovery` 使用同一有限值域和均值公式，但因子语义独立：

```text
recognition_novelty
recognition_basis
barrier_crossing
conversion_to_use
```

首批 gold cases 的结论是：陈平“归汉—复核经历与能力—跨越诋毁—拜护军中尉”构成正向发现链；魏徵当前 Assertion 只证明擢拜，缺少进入视野、识才依据和跨阵营障碍的直接证据，必须 `blocked_evidence`；韩信齐王授权是既有核心将领的授权调整，蓝玉拜大将军是既有将领晋升，均不适用于人才发现。`talent_discovery` 只结算进入有效视野，`appointment_delegation` 只作为 supporting-only rule 承接岗位、授权和反馈，禁止重复结算。

已批准四个有限因子：

```text
person_task_fit
authority_clarity
feedback_handling
attributable_outcome
```

每个因子只允许：

```text
positive | mixed | negative | unknown | not_applicable
```

处理规则：

- `unknown` 表示关键证据缺口，Judgment 必须 `needs_review`，不得生成 ScoreContribution；
- `not_applicable` 不是零分，从公式分母排除；四项均不适用时只作 supporting context；
- `mixed` 表示同一因子正负证据并存，在 shadow 公式中计 0，但必须保留混合方向和证据理由；
- `positive / mixed / negative` 分别映射为 `+1 / 0 / -1`；
- shadow contribution 为适用因子点数均值，范围 `[-1, 1]`，只比较评分单元信号，不是第五项 B 的 45 分正式得分；
- 任一 `mixed`，或正负因子同时存在，Judgment direction 为 `mixed`；否则按全正或全负确定方向。

`authority_clarity` 只评价最终授权载体、责任域和权责方向是否明确，不因请求、劝说或压力下调整自动降档。决策调整过程可作为同一任用链的 `feedback_handling` 证据，但不得仅因出现进言者而另生成“纳谏”贡献。韩信齐王授权据此记为 `authority_clarity=positive`。

该 evaluator 只消费冻结的 RuleEvidenceUnit、有限因子证据和版本；不调用模型。战役、治理等实际收益只作为用人反馈，不在本规则重复结算。

仍未批准：材料权重、衰减、各 rule 权重、正负上限、45 分档位映射、总榜和生产 scorer。

## 13. 当前实现摘要

`appointment_delegation` 已完成评分最小充分 shadow：

- 13 条宽口径 Relation proposal；
- 2 条 `scoring_arc_only`；
- 4 个 RuleEvidenceUnit draft；
- 4 个 Projection / Judgment shadow candidate；
- 1 个 positive、3 个 mixed；
- evidence blocker 与 Episode 重复消费均为 0；
- 3 个变化 Projection 局部重建，1 个未变化结果精确复用。

G3R—G3H 的结果证明评分单元、lineage、readiness 和增量缓存合同可行。当前 scored demo 已用统一命令将冻结 Source/Assertion 输入串到 factor、Judgment、ScoreContribution 和皇帝级 shadow 汇总；结果仍不得解释为正式 45 分评分。完整实施摘要见 [《评分最小充分 Shadow 实施摘要》](../../31-G3R评分最小充分Relation重解释.md)。

Relation v2 使用实际 Episode semantic version 作为端点版本身份，并将 `ruler_responsibility` 与 `evidence_directness` 纳入语义指纹；source-gap input gate v2 会跳过并审计 `not_found_stop` 项，同时继续处理同批可补证候选。相关回归按合同、版本和纵向不变量集中维护，不再按 G3R—G3H 微阶段镜像拆分。

统一入口：

```bash
python -m emperor_v4.eval appointment-delegation-shadow --manifest eval/appointment_delegation_scored_demo/manifest.yml --output eval/appointment_delegation_scored_demo/report.json
python -m emperor_v4.eval appointment-delegation-shadow-diff --request eval/appointment_delegation_scored_demo/shadow_diff_request.yml --output eval/appointment_delegation_scored_demo/shadow_diff_report.json
python -m emperor_v4.eval appointment-delegation-roster-shadow --manifest eval/appointment_delegation_roster_demo/manifest.yml --output eval/appointment_delegation_roster_demo/report.json
python -m emperor_v4.eval appointment-delegation-roster-shadow --manifest eval/appointment_delegation_roster_demo/manifest.yml --prior-record eval/appointment_delegation_roster_demo/report.json --state eval/appointment_delegation_roster_demo/state.json --output eval/appointment_delegation_roster_demo/report.json
python -m emperor_v4.eval talent-discovery-shadow --manifest eval/talent_discovery_scored_demo/manifest.yml --output eval/talent_discovery_scored_demo/report.json
```
