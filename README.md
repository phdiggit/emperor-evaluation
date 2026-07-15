# 皇帝综合评价体系 V4

V4 是一次受控架构重启。它保留 V3 的历史经验、失败样本和业务规则来源，但不继承 V3 的长链编排、全表重建和脚本堆积。

> **评分标准最高驱动；历史事件优先；评分单元最小充分；增量失效优先；智能体只处理歧义。**

## 当前状态

- 分支：`retrieval-v4-event-first`
- 试点：李世民、刘邦、朱元璋
- 首条纵向切片：第五项 B `appointment_delegation`
- 模式：`offline-first + shadow-only`
- G3A Episode Core Registry：已通过隔离 PostgreSQL shadow 验证
- G3B Core Shadow Runner：已通过局部 semantic/evidence 失效与零写入重跑
- `appointment_delegation` scored shadow：4 个既有 RuleEvidenceUnit 已接入 V3 语义等价 shadow；6 项 V3 因子、5 条正负 factor material、确定性乘法公式与事件—人物密度聚合已完成
- V3 parity 增量复用：单个档位候选变化只重建对应 1 个 Judgment/Contribution，其余 3 个逐字段复用
- Factor Observation 资格门：`codex-win factorization-jsonl` 已完成首轮独立盲评；合同、lineage、正负材料结构和方向均通过，但档位仅 19/30 精确、存在 1 个非相邻错误，`real_agent_qualified=false`；延迟基准确定默认保持每批最多 4 单元，并在批间最多 4 路并发
- 模型固定复现：通过 `--respect-task-argv` 显式执行 `--model gpt-5.6-sol`，开发集为 20/30 精确，仍未达门槛；该复现不计为新资格盲评
- 新开放开发集：马周、张良、刘基、李善长已形成 4 个 V4 RuleEvidenceUnit 和 5 条正负材料；coverage-aware 对照为 28/29 已决档位精确、1 次正确拒判、零危险强判/错误拒判/非相邻/方向错误，`codex-win` 单批耗时 67.729 秒、总 token 24,863；该结果只用于调校，`real_agent_qualified=false`
- 封存资格集：房玄龄、李靖、萧何、徐达的 4 个评分单位已在 `3bfc9b6` 冻结后完成唯一一次盲评；25/30 档精确（83.33%）低于 85% 门槛，5 个偏差均为相邻档，决策状态、正负结构、方向与覆盖安全 Gate 全部通过；耗时 100.102 秒、总 token 26,152，未重跑且未回调 Gold/策略，`real_agent_qualified=false`
- 第五项 B 测试集组合已收束：五条 rule 共 100 个单元（68 个 open/opened、32 个 sealed）；`appointment_delegation` 36、`talent_discovery` 12、`tolerate_talent` 20、`anti_nepotism` 20、`team_building` 12，未来预排与模型授权均为 0
- 历史 sealed 资格结果：只有 `team_building` v1 通过（适用性 100%、因子 87.5%）；其余四条均未通过，尤其 `anti_nepotism` 为适用性 75%、因子 9.375%。当前 `team_building` v3 不继承 v1 资格，也不得由开放集推断生产泛化
- 第五项 B 因子语义已定版：五条 rule 共 24 个分类因子统一冻结在 `config/i5b-factor-semantics.yml`；任用授权 v6、识才 v2、容才 v3、反任人唯亲 v2、团队建设 v3 均有机器可校验的相邻档门槛，旧 Gold、旧报告与资格结论未改写
- 第五项 B 计分骨架已回归 V3 格式：材料分 `[-4,4]`、正负 rule signal、对象密度聚合、团队双轴人物池和 `0.19/0.36/0.21/0.18/0.06` 五权重已移植到 `config/i5b-scoring-policy.yml`；当前只产生 `weighted_raw_signal`，动态映射快照批准前不生成 45 分或排名
- V3 人物画像迁移已扩展到全部可用范围：242 份 `active + accepted + profile_complete` 画像保留原始人才档位、定级依据和政治风险 typed axes，另有11份补充画像，合计253份。V6—V8完成原档清洗，V9复核当时全部6名historic和66名top；V10在不覆盖V9的前提下纠正两项门槛错用：陈群由historic回到top，苏定方由top升historic。当前13名historic为司马迁、徐达、房玄龄、李绩、萧何、韩信、卫青、张良、曹参、李斯、李靖、班超、苏定方；统一有效分布为 historic13、top59、important123、usable55、ordinary3。制度寿命不等于制度净效果；军事区分战胜、决定性重创、战略征服和最终目标未完成，平壤未克不记作苏定方战场败仗。政治风险未用于人才扣档，所有既有版本均未覆盖。正式45分和排名仍关闭
- V4 PostgreSQL 的 `v4_person_profile` schema 已导入263个身份、242条 legacy ref、253份画像、1933条画像 lineage、253行一行可读目录、94条V6校准、157条V7校准、74条V8校准、72条V9校准、2条V10纠偏、12个团队窗口和56个窗口成员。`person_profile_current` 前列依次展示姓名、最新有效人才等级、政治风险状态、两轴有效依据及政治风险类别/严重度，并在多版本校准中每人只取最新有效层；所有导入原样第二次运行均为0写
- `team_building` scored shadow 已按V10最新有效画像链完成全部12个冻结测试窗口的工作集计算，能力正池与政治风险负池逐人正交、窗口级去重、结构观察和 ScoreContribution lineage 均已落地；这只表示冻结工作集成员齐全，不表示皇帝历史团队名录穷尽。代表性 raw net：刘邦 `5.990145114242`、朱元璋前期 `5.133605730062`/晚期 `1.503009608597`、李隆基前期 `4.124779125572`/晚期 `1.092957732299`、赵构 `-0.557999161405`。旧sealed只作已开封回归，动态映射、45分和排名仍为空
- 三条联合投影 rule 已生成确定性 ScoreContribution：`talent_discovery` 7个适用单元中6个可投影、仅非李世民单元1个仍缺版本化人物画像；`tolerate_talent` 23个中11个可投影、12个缺独立安全/因果后续或处置联合输入；`anti_nepotism` 对李世民2个适用单元全部投影，另4个未通过公共权力、私人因果或排挤损害 Gate 的候选显式排除为`not_applicable`，不按零材料处理。模型调用和分数数据库写入均为0
- 五条 rule 的统一 raw-signal readiness runner 已把“工作集投影状态”和“皇帝历史覆盖状态”强制分离。李世民五条 rule 均已完成历史覆盖；候选动态映射批次仍为空，因为容才尚有3个李世民单元证据不足，且尚无第二位五条规则均完成的皇帝。缺失候选、证据不足和同皇帝多团队窗口均不静默折算为0
- 李世民 V3 Claim 首批只读迁移与分层已完成：304条active Claim、295个canonical event group、629条direct evidence和168个source slice已冻结；275条代表Claim形成待V4回源复核候选，8条保留为证据成员，21条保留为未物化候选。V3路由仅作提示，识才/任用授权/容才/反任人唯亲分别提供17/174/103/15条候选，团队建设为0。首批source-rebind队列按稀缺rule优先、每rule 8条排入32个不同Claim；其余179条容量延后、53条门禁阻断、40条无I5B路由但全部保留，丢弃为0。人工碰撞审计识别23条Claim对既有工作集形成42个aggregate-component rule-slot，但精确lineage碰撞和完整事件等价均为0。32条预审仅保留4条新事件回源候选，另有2条既有聚合部件、6条跨rule主结算、14条错误路由、5条适用性不足和1条史源不足；正式V4 Assertion、历史覆盖接受、模型调用和数据库写入仍为0
- 李世民容才V4证据Source Cache入库已覆盖当前7个单元：求谏制度、魏徵生前与独立连续性、魏徵身后信用、虞世南、褚遂良、马周、戴胄，共9个当前有效文档、29个passage、85次有效首次写入；含被取代载荷在内历史写入106次，所有原样重跑均为0写。长期工作树只保留不可变输入、一个sourcepack、一个批次合同和一个收口审计，不保留逐单元fetch/dry-run/apply/rerun展开物。魏徵连续性三段只作联合因子support，不重复制度收益；虞世南、褚遂良和魏徵身后材料保留来源质量核校门，戴胄保留共同归责与结果边界人工裁决。剩余Source Cache抓取单元为0，但正式Assertion、Episode、RuleEvidenceUnit、分数和排名写入仍为0
- 跨人物制度检索回归已增加三轴合同：人物事件、皇帝制度、跨人物聚合缺一不可；李世民求谏案例在不提示章节名、段落位置或制度答案时，只能产出`candidate_only`制度候选，必须同时满足正式通道、多个独立运行观察、跨年、多表达者/正式主体和表达安全门槛，不得由智能体直接接受事实或计分
- 李世民五rule当前严格shadow净值已形成同一报告：识才`+4.015`、任用授权`+9.3902`、团队建设`+12.3635`、容才`+11.473`、反任人唯亲`+2.332`，按V3权重合成的declared-workset raw signal为`8.945`。团队建设49名候选已全部处置，24人进入核心计分名单，苏定方因主要成果在649年后排除出李世民窗口，其余24人保留为supporting-only而非零材料；跨rule审计覆盖58个结算组、0冲突。五条历史覆盖虽已完成，但容才仍有3个李世民单元证据不足，因此不生成45分、档位或排名
- 计分详情导出已接入`config/i5b-scoring-detail-display.yml`，所有数值因子和档位同时展示中文名称、英文稳定代码、数值和中文门槛说明。容才正向`feedback_entry`振幅已扩展至2.0：普通多次、跨阶段持续、高密度跨领域长期犯颜和制度化入口分别映射1.0、1.3、1.7和2.0。《贞观政要·求谏第四》所见正式求谏通道达到`institutionalized_feedback_entry=2.0`；魏徵个人映射`exceptional_dense_cross_domain_remonstrance=1.7`
- 已开封回归优化已启动：6 次离线模型调用覆盖四条失败 rule；识才关键检查 5/5、容才 39/40、反任人唯亲所有权 8/8 且关键检查 4/4，任用授权 17 个 canonical slot 结构 100% 保持、与旧 Gold 的五项模型因子一致 61/85。该结果只用于性能诊断，不是资格率
- 通用证据覆盖 Gate：`appointment_delegation` 与 `talent_discovery` 共用 `rule-factor-evidence-coverage-v1`；开放快照允许直接正证据确认，但禁止以“未找到”强推一次性、从未发生等缺失敏感档位，覆盖不足必须退出为 `insufficient_coverage`
- shadow 差异评审：已证明 1 个因子变化只局部失效 1 个评分单元，其余 3 个 Judgment/Contribution 精确复用
- 名单式离线入口：三位皇帝、四位臣子的 roster manifest 已贯通 Source Cache/Claim Extractor 快照、Episode Kernel 和 scored runner
- 包 C 持久化增量编排：已记录逐人物 stage、response hash、delta Episode、慢通道任务和失败恢复；无变化重跑复用同一记录
- 包 D 发现链补抽：V4 Claim Extractor 已按 `talent_discovery` 抽出魏徵旧阵营、识才依据、跨障碍与转化任用 4 条 Claim；陈平、魏徵各形成 1 个正向贡献，韩信与蓝玉按规则排除
- 包 D 名单增量复用：`talent_discovery` 已接入包 C 的持久化 roster 入口；无变化精确复用，新增魏徵 Assertion 只重建 1 个单元并复用其余 3 个 Judgment
- V4 配套服务源码治理：Source Cache 与 Claim Extractor 的活动实现已进入同一 Git 历史并完成不可变 cutover；旧服务分支只作迁移审计，当前分支后续 hardening 未经独立 Gate 不视为已部署
- V4 Source Cache 迁移：版本化请求、通用 SourceRevision、不可变 document/passage、fixture/真实 Wikisource adapter、PostgreSQL repository、job/lease worker 和 20 文件不可变 release 已进入当前 Git 历史；隔离服务器 Gate 已验证幂等、过期 lease 恢复与回滚
- V4 Claim Extractor 选择性迁入：旧 `rule_code` 提示分支已改为版本化 `talent_discovery_chain_v1` profile；v2 application、独立 PostgreSQL repository、job/lease 和当前 21 文件 release 已通过服务器隔离 Gate，冻结响应形成 4 条带 PassageSupport 的 Assertion
- V4 Claim Extractor 真实 provider shadow：改用 V4 Source Cache 三 passage 后生成 7 条 draft Assertion，四项发现链齐备，主簿重叠证据按 equivalent evidence 合并语义；未授权人物称谓保留原文并进入身份 slow lane
- 服务规模化 hardening：已完成按 job profile 路由、lease 覆盖模型 timeout、显式空结果、服务端稳定 draft identity、可信 subject 路由、Codex 子进程隔离、provider 模型/Prompt/Schema 策略进入缓存身份，以及 64 条输出饱和失败关闭；确定性 Claim 分片、结构化 coverage gap、多实例 worker 和 JudgmentObservationJob 仍待实现与资格测试，最新代码尚未切换服务器不可变 release
- 正式 45 分映射、排名、评分 worker 和生产切换：尚未开放

当前实现已经证明：

```text
SourcePassage / Assertion
→ HistoricalEpisode
→ 评分必要 Relation 或 scoring-arc-only
→ RuleEvidenceUnit draft
→ Projection draft
→ 有限 factor option proposal（智能体/人工不得写数值）
→ deterministic V3 factor mapping / Judgment
→ shadow ScoreContribution / 皇帝级只读汇总
```

统一命令已经能从冻结 manifest 生成三位皇帝的可追溯 scored shadow 报告，并能比较基线与候选因子观察的局部失效范围。两条命令均为离线、零模型、零数据库写入和非正式接受。

Windows 仓库根目录先设置源码路径：

```powershell
$env:PYTHONPATH = "src"
```

```bash
python -m emperor_v4.eval appointment-delegation-shadow --manifest eval/appointment_delegation_scored_demo/manifest.yml --output eval/appointment_delegation_scored_demo/report.json
python -m emperor_v4.eval appointment-delegation-v3-parity-shadow --manifest eval/appointment_delegation_v3_parity_demo/manifest.yml --output eval/appointment_delegation_v3_parity_demo/report.json
python -m emperor_v4.eval appointment-delegation-factor-worklist --source-manifest eval/appointment_delegation_scored_demo/manifest.yml --output tmp/appointment_delegation_factor_worklist_v2.json
python -m emperor_v4.eval appointment-delegation-factor-gold --worklist eval/appointment_delegation_factor_agent_qualification/worklist_v2.json --parity-gold-manifest eval/appointment_delegation_v3_parity_demo/manifest.yml --source-manifest eval/appointment_delegation_scored_demo/manifest.yml --sample-role open_development --output tmp/appointment_delegation_factor_gold_v2.json
python -m emperor_v4.eval appointment-delegation-factor-batch-plan --source-manifest eval/appointment_delegation_scored_demo/manifest.yml --max-units-per-batch 4 --max-workers 4 --output tmp/factor_batch_plan.json
python -m emperor_v4.eval appointment-delegation-shadow-diff --request eval/appointment_delegation_scored_demo/shadow_diff_request.yml --output eval/appointment_delegation_scored_demo/shadow_diff_report.json
python -m emperor_v4.eval appointment-delegation-roster-shadow --manifest eval/appointment_delegation_roster_demo/manifest.yml --output eval/appointment_delegation_roster_demo/report.json
python -m emperor_v4.eval appointment-delegation-roster-shadow --manifest eval/appointment_delegation_roster_demo/manifest.yml --prior-record eval/appointment_delegation_roster_demo/report.json --state eval/appointment_delegation_roster_demo/state.json --output eval/appointment_delegation_roster_demo/report.json
python -m emperor_v4.eval talent-discovery-shadow --manifest eval/talent_discovery_scored_demo/manifest.yml --output eval/talent_discovery_scored_demo/report.json
python -m emperor_v4.eval talent-discovery-roster-shadow --manifest eval/talent_discovery_roster_demo/manifest.yml --output eval/talent_discovery_roster_demo/report.json
python -m emperor_v4.eval talent-discovery-roster-shadow --manifest eval/talent_discovery_roster_demo/manifest.yml --prior-record eval/talent_discovery_roster_demo/report.json --state eval/talent_discovery_roster_demo/state.json --output eval/talent_discovery_roster_demo/report.json
python -m emperor_v4.eval rule-test-set-admission --policy config/rule-test-set-policy.yml --output eval/rule_test_set_admission/report.json
python -m emperor_v4.eval i5b-opened-regression-contract --contract config/i5b-opened-regression-contract.yml --artifact-root . --output eval/i5b_test_set_portfolio/opened_regression_contract_report.json
python -m emperor_v4.eval i5b-factor-semantics --contract config/i5b-factor-semantics.yml --output eval/i5b_test_set_portfolio/factor_semantics_report.json
python -m emperor_v4.eval i5b-scoring-policy --policy config/i5b-scoring-policy.yml --output eval/i5b_test_set_portfolio/scoring_policy_report.json
python -m emperor_v4.eval model-policy --policy config/model-policy.yml
python -m emperor_v4.eval model-policy --policy config/model-policy.yml --stage named_subject_source_discovery
python -m emperor_v4.eval i5b-joint-projection-scored-shadow --rule-code talent_discovery --projection-input eval/i5b_joint_projection_scored_shadow/talent_discovery_projection_inputs.json --scoring-policy config/i5b-scoring-policy.yml --output eval/i5b_joint_projection_scored_shadow/talent_discovery_report.json
python -m emperor_v4.eval i5b-joint-projection-scored-shadow --rule-code tolerate_talent --projection-input eval/i5b_joint_projection_scored_shadow/tolerate_talent_projection_inputs.json --scoring-policy config/i5b-scoring-policy.yml --assertion-review eval/i5b_tolerate_talent_vertical/lishimin_assertion_drafts.json --output eval/i5b_joint_projection_scored_shadow/tolerate_talent_report.json
python -m emperor_v4.eval i5b-ruler-rule-coverage --manifest eval/i5b_ruler_rule_coverage/lishimin_manifest.yml --output eval/i5b_ruler_rule_coverage/lishimin_report.json
python -m emperor_v4.eval v3-claim-pilot --ruler 李世民 --source-freeze-ref v3-claim-freeze-20260715-lishimin-v1 --profile-package eval/v3_person_profile_migration/authorized_profile_promotion.json --profile-package eval/v3_person_profile_migration/supplemental_profile_promotion.json --output eval/v3_claim_migration/lishimin_source_snapshot.json --report eval/v3_claim_migration/lishimin_report.json
python -m emperor_v4.eval i5b-unified-raw-signal-readiness --appointment-report eval/i5b_appointment_delegation_historical_coverage/lishimin_scored_shadow_report_v1.json --team-report eval/i5b_team_building_historical_coverage/lishimin_scored_shadow_report_v2.json --joint-report eval/i5b_joint_projection_scored_shadow/talent_discovery_report.json --joint-report eval/i5b_joint_projection_scored_shadow/tolerate_talent_report.json --joint-report eval/i5b_joint_projection_scored_shadow/anti_nepotism_report.json --coverage-report eval/i5b_ruler_rule_coverage/lishimin_report.json --calibration-version i5b-multi-ruler-candidate-v1 --output eval/i5b_joint_projection_scored_shadow/unified_readiness_report.json
python -m emperor_v4.eval i5b-ruler-rule-net --manifest eval/i5b_ruler_rule_net/lishimin_manifest.yml --output eval/i5b_ruler_rule_net/lishimin_report.json
python -m emperor_v4.eval i5b-scoring-detail --manifest eval/i5b_scoring_detail/lishimin_manifest.yml --workspace-root . --format json --output eval/i5b_scoring_detail/lishimin_report.json
python -m emperor_v4.eval i5b-scoring-detail --manifest eval/i5b_scoring_detail/lishimin_manifest.yml --workspace-root . --format markdown --output eval/i5b_scoring_detail/lishimin_report.md
python -m emperor_v4.eval i5b-scoring-detail-select --catalog eval/i5b_scoring_detail/catalog.yml --selection eval/i5b_scoring_detail/selection_example.yml --workspace-root . --format markdown --output eval/i5b_scoring_detail/selection_example_report.md
python -m emperor_v4.eval v3-person-profile-export --source-freeze-ref v3-freeze-20260712 --output eval/v3_person_profile_migration/source_snapshot.json --report eval/v3_person_profile_migration/report.json
python -m emperor_v4.eval v3-person-profile-migration --source-freeze-ref v3-freeze-20260712 --authorization-ref user-authority:2026-07-15:v3-profile-axes-authoritative --supplemental-evaluations eval/v3_person_profile_migration/missing_team_profile_evaluations.yml --registry-profile eval/team_building_open_development/profile_snapshots.json --registry-profile eval/team_building_sealed_holdout/profile_snapshots.json --candidate-identity-manifest eval/episode_pilot_v1_identity_resolution.yml --team-worklist eval/team_building_open_development/worklist.json --team-worklist eval/team_building_sealed_holdout/worklist.json --artifact-dir eval/v3_person_profile_migration --output eval/v3_person_profile_migration/migration_report.json
python -m emperor_v4.runtime.source_cache --request eval/source_cache_v4_demo/request.yml --fixture-plan eval/source_cache_v4_demo/fixture_plan.yml --state eval/source_cache_v4_demo/state.json --service-release-sha f7022cb39a887325e3719f46188602ab52775905 --output eval/source_cache_v4_demo/rerun_report.json
python -m emperor_v4.runtime.source_cache_shadow --request eval/source_cache_v4_demo/request.yml --plan eval/source_cache_v4_demo/fixture_plan.yml --baseline-report eval/source_cache_v4_demo/report.json --service-release-sha f7022cb39a887325e3719f46188602ab52775905 --output eval/source_cache_v4_demo/wikisource_shadow_report.json
```

## 下一份可见成果

李世民五条 rule 的皇帝级历史覆盖已经全部收口。识才补齐张玄素版本化人物画像后，李世民3个识才单元全部可投影，raw net由`2.926`升至`4.015`；反任人唯亲只结算2个适用单元，raw net为`2.332`，另4个候选明确排除为`not_applicable`。

团队建设不再沿用9人临时名单。49名候选已经逐项处置：24人进入626—649核心计分名单，苏定方因主要成果落在李世民窗口之后排除，其余24人保留为supporting-only。补充回源使用9份文档、15个passage，Source Cache首跑45次写入、原样复跑0写；15个新增成员事实通过独立delta职责链首跑105次业务写入、原样复跑0写。团队正信号`13.285117252338`、负信号`0.921600000000`、raw net`12.363517252338`。

统一结算现覆盖58个canonical group、58次消费、45个数值投影、13个证据不足项和5条rule，精确键冲突为0。五条rule按既定权重合成raw signal为`8.945`；所有ScoreContribution仍为shadow，正式45分、tier和排名均为空。

当前唯一的李世民规则内硬阻断是容才3个单元仍为`insufficient_projection`；批量动态映射还要求至少第二位五条rule均完成的皇帝，因此候选批次仍为空。下一份可见成果转向历史覆盖campaign真实执行器：把现有925个皇帝×rule任务规划合同接入通用Source Cache、Claim Extractor、Episode Kernel和scored shadow handler，而不是复制人物专项runtime。

## 用户目标链路

目标交互保持为：

```text
皇帝 / 臣子名单
→ 离线史源缓存（允许预热）
→ 相关史料与 Assertion 抽取
→ HistoricalEpisode
→ 按评分规则生成 RuleEvidenceUnit
→ 规则内有限因子赋值
→ 确定性计分与追溯报告
```

五条 rule 均已进入版本化 shadow；后续按皇帝级历史覆盖逐条收口：

- `talent_discovery`
- `team_building`
- `tolerate_talent`
- `anti_nepotism`

规模化只允许复用稳定契约、缓存和增量任务；不得复制五套独立流水线。

配套服务源码迁移与评分规则扩展并行推进。Source Cache 与 Claim Extractor 已完成服务器不可变 cutover，并通过首条真实服务 job 观察。数据库复用早期 G3A 已创建的 `emperor_eval_v4`；Source Cache 经 1 次 Wikisource 请求写入 1 个 document revision 和 3 个 passages，Claim 经状态目录权限修复后在第 2 次 attempt 生成 7 条 draft assertions。两项重复投递均为零写，最小权限服务角色无权写 `public` 正式表。Live drafts 与先前 shadow 覆盖相同七个事实概念，但措辞和 semantic key 不做字面复现，因此仍是 `passed_for_draft_only`，不自动成为正式 Assertion。两个 timer 保持启用，V3、正式评分和排名未改变；服务收口后回到 `team_building` scored shadow 复用。

上述线上观察仍对应旧不可变 release。当前分支的规模化 hardening 只有在 focused/full pytest、隔离 PostgreSQL migration、不可变 release 校验和明确 cutover 后才会影响服务器运行；不得把 Git 分支更新解释为已部署。

## 核心阅读顺序

1. `docs/项目总纲/皇帝综合评价体系评分标准.md`
2. `docs/00-V4项目章程.md`
3. `docs/项目总纲/总规则.md`
4. `docs/02-领域模型.md`
5. `docs/03-证据与历史事件模型.md`
6. `docs/04-规则输入类型与投影模型.md`
7. `docs/05-任务状态机与增量失效.md`
8. `docs/06-覆盖度与验收标准.md`
9. `docs/09-V4测试与验证策略.md`
10. `docs/31-G3R评分最小充分Relation重解释.md`（当前实现摘要）
11. `docs/contracts/` 与当前分项规则

历史盲测和阶段审计不是日常阅读入口。

## 不可妥协约束

- `SourcePassage` 是可定位史料片段，`Assertion` 是来源断言，`HistoricalEpisode` 是事件型规则的核心语义主体。
- 同一事件可以有多份史料，但只能有一个当前 canonical episode。
- 语义版本和证据版本分离；新增同义证据不得默认触发重判。
- 人物、事件、评分单元、Projection、Judgment 和 ScoreContribution 各自有稳定身份与版本。
- 正常增量不得触发全库、整皇帝或整规则重建。
- 模型不能建立正式历史事实、正式判断或正式分数。
- 无变化重跑必须零模型调用、零业务写入。
- V3 已废弃，不再承担运行、评分或发布；V4 可按需只读查询 V3 数据库作迁移、回归和差异诊断，但业务写入、队列和发布链不回流 V3。

## 当前 Gate

- G2-Core / S1—S3：`passed_for_shadow_implementation`
- 历史精细 Relation / S4：`deferred_not_qualified`，只约束精细知识图发布
- G3A：`passed_shadow_registry`
- G3B：`passed_sync_local_invalidation`
- G3R 评分最小充分 Relation：`passed`
- G3C RuleEvidenceUnit shadow：`passed`
- G3D—G3H Judgment readiness 与 delta：`passed_shadow_only`
- Factor schema：`passed_shadow_demo_only`
- V3 semantic parity factor/schema/formula：`passed_shadow_demo_only`
- Factor Judgment proposal contract：`passed_shadow_demo_only`
- Deterministic Judgment evaluator：`passed_shadow_demo_only`
- ScoreContribution：`passed_shadow_demo_only`
- Integrated scored shadow runner：`passed_shadow_demo_only`
- Shadow difference review runner：`ready_for_human_review`
- Offline roster scored runner：`passed_cache_ensure_shadow`
- Persistent incremental orchestration：`passed_shadow_runtime`
- Claim cache policy/saturation hardening：`code_ready_pending_full_test_and_cutover`
- Claim sharding / structured gaps / worker tiers：`not_implemented_or_qualified`
- Factor Observation agent：`independent_blind_run_completed_not_qualified`
- 正式评分和生产切换：`blocked`
