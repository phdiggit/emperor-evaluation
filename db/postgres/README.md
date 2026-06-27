# PostgreSQL 基础 schema 契约

`001_init.sql` 是皇帝综合评价体系后续 PostgreSQL 目标主库的第一版 schema 契约。它用于固定采集、史源版本、段落、候选匹配、证据链、任务、outbox 和导入审计的基础表结构，供后续 worker skeleton、导入 dry-run 和采集试点继续对齐。

当前状态：

- 不接生产服务。
- 不替代 JSONL 写源。
- 不改变现有 JSONL -> SQLite -> Markdown 流程。
- 不要求 CI 或本地开发环境安装 PostgreSQL。
- 不包含 migration runner、Docker Compose、RabbitMQ worker 或 outbox dispatcher。

第一版 schema 只覆盖采集与证据链，不实现最终评分表、裁判发布表、外部搜索索引表、RabbitMQ queue / exchange 配置，也不复制 SQLite thematic anchor 的三张同构表。真实连接、迁移执行器、Docker Compose、worker、outbox dispatcher 和 JSONL 切库逻辑都留给后续 PR。

## 本地 bootstrap 检查

`scripts/platform/postgres_bootstrap.py` 只用于本地开发库 opt-in 检查 `001_init.sql` 是否能在隔离 schema 中执行。默认 `--check` 只报告 DSN 与 Python PostgreSQL driver 是否可用，不连接数据库、不执行 DDL；`--sql-only` 只输出包装后的 SQL。

需要真实 apply 时，在本地 `.env` 或 shell 中设置 `EMPEROR_EVAL_PG_DSN`，也兼容旧的 `PG_SEARCH_BENCH_DSN`：

```bash
python scripts/platform/postgres_bootstrap.py --check
python scripts/platform/postgres_bootstrap.py --sql-only
python scripts/platform/postgres_bootstrap.py --apply --schema emperor_eval_bootstrap_check --drop-schema-after
```

`--apply` 会先创建指定 schema，并将 `search_path` 设为该 schema 与 `public` 后再执行 `001_init.sql`。清理只删除临时 schema，不会提交 `.env`、迁移 JSONL、连接 RabbitMQ，或写入 worker/crawler/parser。

## JSONL 导入 dry-run

`scripts/platform/jsonl_import_dry_run.py` 用于 opt-in 验证当前 canonical JSONL 主表是否可以被逐行解析、映射并写入导入审计表。它不迁移 JSONL，不切换写源，不写业务事实表，也不把结果写入 Markdown exports。

默认和 contract report 都不会连接数据库：

```bash
python scripts/platform/jsonl_import_dry_run.py --check
python scripts/platform/jsonl_import_dry_run.py --contract-report
```

需要真实写入本地 PostgreSQL 审计表时，只使用本地 shell 或 `.env` 中的 `EMPEROR_EVAL_PG_DSN`，不使用旧 search benchmark DSN，也不依赖 `psql`：

```bash
python scripts/platform/jsonl_import_dry_run.py --apply --schema emperor_eval_import_dry_run --drop-schema-after
```

`--apply` 会在隔离 schema 中执行 `001_init.sql`，然后只写入 `imports` 和 `import_rows`。使用 `--drop-schema-after` 时，命令结束前会 `DROP SCHEMA CASCADE` 清理该隔离 schema。

## JSONL target 映射契约

`scripts/platform/jsonl_target_mapping.py` 固定 canonical JSONL 到 PostgreSQL staging/target 的映射规则。它只输出 contract report，不连接 PostgreSQL、不迁移 JSONL、不切换写源、不写业务事实表，也不生成 evidence card、分值、排名或 RabbitMQ worker。

```bash
python scripts/platform/jsonl_target_mapping.py --contract-report
```

详细规则见 [`docs/数据结构与生成库/JSONL到PostgreSQL映射规则.md`](../../docs/数据结构与生成库/JSONL到PostgreSQL映射规则.md)。G1 批准后的 G2 mapping approval package 使用：

```bash
python scripts/platform/jsonl_postgres_mapping_approval_package.py --package-report
python scripts/platform/jsonl_postgres_mapping_approval_package.py --markdown-report
```

该包覆盖已批准 manifest 的 11 个顶层 `data/*.jsonl`。`events.jsonl` 与 `trigger_terms.jsonl` 当前作为 staging-only 输入；thematic anchors 可对齐 `anchors` 基础表候选字段，但 `anchor_links` 正式 target table 与 link 语义仍是后续审批项。进入正式 target business table 仍必须另开 PR，并等待 G2 / G3。

G2 获批后的 1C staging dry-run / diff verification 使用：

```bash
python scripts/platform/jsonl_staging_diff_verification.py --verification-report
python scripts/platform/jsonl_staging_diff_verification.py --markdown-report
```

该包只做离线聚合，核对 manifest row / ID / hash、orphan 引用、staging rows、resolver reference risk 和 lossy conversion 风险，固定为 `NO_NEW_GATE`。它不读取生产凭据、不连接 PostgreSQL、不写正式业务表，也不证明 production success；第一次正式业务数据写入前仍需 G3。

G3 获批后的第一次正式 PostgreSQL 业务写入执行包使用：

```bash
python scripts/platform/g3_postgres_business_write_execution.py --contract-report
python scripts/platform/g3_postgres_business_write_execution.py --execution-plan-json
python scripts/platform/g3_postgres_business_write_execution.py --operator-checklist-md
```

当前写入范围只允许 `data/sources.jsonl` URL host -> `src_hosts`，计划行数为 1。`--execute` / `--observe` 需要 G3 token、expected plan sha256 和 operator 环境中的 `EMPEROR_EVAL_PG_DSN`；默认报告不读取 DSN、不连接数据库。`src_docs`、`doc_revs`、`passages` 以及证据/关系目标表仍保持 blocked。

G4 获批后的 JSONL freeze 与 PostgreSQL unique write-source cutover 执行包使用：

```bash
python scripts/platform/g4_write_source_cutover_execution.py --contract-report
python scripts/platform/g4_write_source_cutover_execution.py --cutover-plan-json
python scripts/platform/g4_write_source_cutover_execution.py --operator-checklist-md
```

该包默认不读取 DSN、不连接数据库；`--execute` / `--observe` 才需要 G4 token、expected cutover plan sha256 和 operator 环境中的 `EMPEROR_EVAL_PG_DSN`。执行路径只允许在 `imports` 表写入 / 更新 `G4-WRITE-SOURCE-CUTOVER-ISSUE292` cutover marker，并先读回确认 G3 `src_hosts` 中已存在 `zh.wikisource.org`。G4 不写后续 source/passages/evidence/relationship 业务表，不启动 runtime，也不发布正式评分或排名。

G1-G4 完成观察后的 G5 前置边界包使用：

```bash
python scripts/platform/g5_runtime_boundary_package.py --contract-report
python scripts/platform/g5_runtime_boundary_package.py --boundary-md
```

该包只列出 G5 将允许 / 禁止的 runtime、RabbitMQ、network ingestion、production credentials 边界，不执行 G5，不读取 `.env`，不连接 PostgreSQL，不连接 RabbitMQ，不访问网络。G5 仍需用户显式批准；即使 G5 获批，也不等于 formal evidence、评分、分数或排名发布，也不批准 source/passages/evidence/cluster/anchor/relationship 业务表写入。

G5 获批后的 runtime execution / observation package 使用：

```bash
python scripts/platform/g5_runtime_execution.py --contract-report
python scripts/platform/g5_runtime_execution.py --execution-plan-json
python scripts/platform/g5_runtime_execution.py --operator-checklist-md
```

该包默认不读取 `.env`、不连接 PostgreSQL / RabbitMQ、不访问网络。`--execute` / `--observe` 必须带 G5 token、expected plan sha256，并由 operator 环境提供 `EMPEROR_EVAL_PG_DSN`、RabbitMQ URL / vhost / exchange / queue / routing key / prefetch / TLS 设置，以及 `G5_NETWORK_SOURCE_ALLOWLIST` 与 `G5_NETWORK_PILOT_URL`。缺任一生产凭据、RabbitMQ 配置或 allowlist 时只能返回 blocked/operator-required，不得伪造成功。成功执行只允许写入 `imports` 表的 `G5-RUNTIME-SMOKE-ISSUE292` audit marker；不写 source/passages/evidence/cluster/anchor/relationship 业务表，不发布 formal evidence、评分或排名，也不进入 Epic 2。

G5 execute / observe 已成功观察，execution plan sha256 为 `590b083e27e8d6f9b93c3742936ef043e17262abc041a0132d4bcf5364d0edbd`。成功事实包括 G3 `src_hosts` 读回、G4 cutover marker 读回、RabbitMQ binding smoke、outbox / worker runtime smoke、allowlisted network pilot，以及 `G5-RUNTIME-SMOKE-ISSUE292` marker 写入 / 读回。该状态仍不发布 formal evidence、评分或排名，也不进入 Epic 2。

G5 完成观察后的 G6 formal evidence 前置边界包使用：

```bash
python scripts/platform/g6_formal_evidence_boundary_package.py --contract-report
python scripts/platform/g6_formal_evidence_boundary_package.py --boundary-md
```

该包只列出 G6 将允许 / 禁止的 formal evidence release 边界，不批准 G6，不执行 release，不读取 `.env`，不连接 PostgreSQL / RabbitMQ，不访问网络，不读取 canonical JSONL，也不写 source/passages/evidence/cluster/anchor/relationship 业务表。G6 仍需用户显式批准；即使 G6 获批，也不等于评分规则、评分算法、正式分数、排名、破坏性 cleanup 或 Epic 2 入口获批。

G6 获批后的 formal evidence execution / observation package 使用：

```bash
python scripts/platform/g6_formal_evidence_execution.py --contract-report
python scripts/platform/g6_formal_evidence_execution.py --execution-plan-json
python scripts/platform/g6_formal_evidence_execution.py --operator-checklist-md
```

该包默认不读取 `.env`、不连接 PostgreSQL / RabbitMQ、不访问网络，不读取 canonical JSONL，也不写 source/passages/evidence/cluster/anchor/relationship 业务表。`--execute` / `--observe` 必须带 G6 token、expected plan sha256，并由 operator 环境提供 `EMPEROR_EVAL_PG_DSN`。执行路径先读回确认 G5 runtime marker，再只允许在 `imports` 表写入 / 更新 `G6-FORMAL-EVIDENCE-RELEASE-ISSUE292` formal evidence release audit marker；当前包不发布评分规则、评分算法、正式分数或排名，也不进入 Epic 2。

G6 execute / observe 已成功观察，execution plan sha256 为 `27c93eca232ce4654533cfdc28795be0e366574d182b0e8378ba41ffc242b858`。成功事实包括 G5 `G5-RUNTIME-SMOKE-ISSUE292` marker 读回通过，以及 `G6-FORMAL-EVIDENCE-RELEASE-ISSUE292` marker 写入 / 读回通过。该状态仍不写 source/passages/evidence/cluster/anchor/relationship 业务表，不发布评分规则、评分算法、正式分数或排名，也不进入 Epic 2。

G7 获批后的 rule change scope package 使用：

```bash
python scripts/platform/g7_rule_change_scope_package.py --contract-report
python scripts/platform/g7_rule_change_scope_package.py --scope-md
```

该包默认不读取 `.env`、不连接 PostgreSQL / RabbitMQ、不访问网络，不读取 canonical JSONL，不修改评分标准或分项规则正文，也不写 source/passages/evidence/cluster/anchor/relationship 业务表。G7 只允许准备明确规则变更 workset、审查子项规则定义 diff、记录不含正式分值的影响范围与边界回归测试；正式算法仍需 G8，正式分数 / 排名发布仍需 G9，破坏性清理仍需 G10，Epic 2 仍需 separate ready review。

G7 rule-change workset package 使用：

```bash
python scripts/platform/g7_rule_change_workset.py --workset-report
python scripts/platform/g7_rule_change_workset.py --workset-md
```

该 workset 声明下一批规则变更 PR 必须包含 changed rule paths、before / after diff summary、impact scope、boundary regression tests，并确认正式算法与发布仍由 G8 / G9 阻断。该 workset 不读取或修改评分标准、分项规则、证据规则正文，不读取 `.env`，不连接服务，不写业务表。

G7 实际规则变更实现已进入第五项B三核心覆盖门槛：单一维度三强正只有同时覆盖识人任用、授权专任、人才生态三类核心时，才可上探极正候选；同类强证堆叠默认强正封顶。本变更只修改规则正文、自动结算判定与边界测试，不连接服务、不写业务表、不发布正式算法、不发布正式分值或排名；下一步应进入 G8 boundary / approval package。

G8 已批准并释放第五项B正式算法版本 `i5b-formal-algorithm-v1`：自动结算方向现在可确定 V3.2 九档枚举、45 分档内区间和可重复候选值。该状态只发布规则/算法版本与聚合影响报告，不发布人物级正式分值、排名、leaderboard 或总榜。

G9 已批准并进入第五项B正式分值与子项排名发布：当前发布范围只包含第五项B人物正式分值和子项排名，不包含阶段总榜、总榜、G10 破坏性清理、source/passages 写入、evidence/cluster/anchor/relationship 业务表写入或 Epic 2 entry。

Epic5 评分引擎跨子项泛化 boundary / scope package 使用：

```bash
python scripts/platform/epic5_scoring_engine_scope_package.py --contract-report
python scripts/platform/epic5_scoring_engine_scope_package.py --scope-md
```

该包只做离线范围与接口草案：从第五项B已跑通的链路中抽象 `subitem_profile`、`evidence_profile`、`formal_grade_result`、`score_publication_result`，并选择第二项、第三项、第六项作为候选试点方向。当前包不发布任何新子项分值、不生成阶段总榜 / 最终总榜 / 跨子项 leaderboard，不做 #311 完整字典迁移，不写 source/passages 或 evidence/cluster/anchor/relationship 业务表，不进入 Epic 2 / Epic 3。

Epic5 最小接口契约 package 使用：

```bash
python scripts/platform/epic5_scoring_engine_interface_contract.py --contract-report
python scripts/platform/epic5_scoring_engine_interface_contract.py --interface-md
```

该包固化 `scripts/shared/scoring_engine_contracts.py` 的纯 Python 接口契约和边界校验：`ScoreRange`、`SubitemProfile`、`EvidenceProfile`、`NoOverridePolicy`、`FormalGradeResult`、`ScorePublicationResult`。它只验证 G8/G9 分离、no-override、候选值区间、G9 子项内发布和总榜/leaderboard 锁定，不读取数据、不连接服务、不发布任何新子项分值。

Epic5 试点子项 profile contract package 使用：

```bash
python scripts/platform/epic5_pilot_subitem_profile_contract.py --contract-report
python scripts/platform/epic5_pilot_subitem_profile_contract.py --profiles-md
```

该包只固定第二项治国净收益、第三项军事与边疆净收益、第六项关键历史决策能力的 `SubitemProfile` 合同：分值上限分别为 460、250、180；第六项按 60 / 50 / 70 的 A/B/C 分解承接 1500 总盘决策。它不包含 evidence profile、formal grade result 或 score publication result，不读取数据、不连接服务、不写业务表、不发布任何新子项分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。试点子项 evidence profile contract 已由后续包承接。

Epic5 试点子项 evidence profile contract package 使用：

```bash
python scripts/platform/epic5_pilot_subitem_evidence_profile_contract.py --contract-report
python scripts/platform/epic5_pilot_subitem_evidence_profile_contract.py --evidence-md
```

该包只定义第二项、第三项、第六项的 schema-only `EvidenceProfile` 合同模板：正向信号组、负向信号组、必要字段和相邻项剥离信号。模板 `person_id` 固定为 `__pilot_contract_template__`，不代表任何真实人物；本包不查史源、不读 JSONL、不构建 person-specific evidence profile、不产生 formal grade result 或 score publication result，不发布任何新子项分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。下一步应进入 formal grade result contract package。

Epic5 formal grade result contract package 使用：

```bash
python scripts/platform/epic5_formal_grade_result_contract.py --contract-report
python scripts/platform/epic5_formal_grade_result_contract.py --formal-grade-md
```

该包只定义第二项、第三项、第六项的 `FormalGradeResult` 合同模板：每份模板绑定试点 `SubitemProfile`、schema-only `EvidenceProfile`、九档枚举、档内区间、确定性 rerun key 和 no-override policy。模板 `person_id` 仍固定为 `__pilot_contract_template__`，`candidate_value` 只是合同占位值；本包不查史源、不读 JSONL、不构建真实人物 formal grade、不产生 `ScorePublicationResult`，不发布任何新子项分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。下一步应进入 score publication result contract package。

Epic5 score publication result contract package 使用：

```bash
python scripts/platform/epic5_score_publication_result_contract.py --contract-report
python scripts/platform/epic5_score_publication_result_contract.py --publication-md
```

该包只定义第二项、第三项、第六项的 `ScorePublicationResult` 合同模板：每份模板绑定 formal grade result 模板、G9 publication gate 要求、占位 formal score value、占位子项内 rank，并继续锁定 stage/final total table 与 cross-subitem leaderboard 为未发布。本包不查史源、不读 JSONL、不构建真实人物发布结果，不发布任何新子项分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。下一步应进入 deterministic rerun / impact report / publication report contract package。

Epic5 deterministic rerun / report contract package 使用：

```bash
python scripts/platform/epic5_deterministic_rerun_report_contract.py --contract-report
python scripts/platform/epic5_deterministic_rerun_report_contract.py --rerun-report-md
```

该包只定义第二项、第三项、第六项的 deterministic rerun key、validator checklist、impact report template 与 publication report template 合同：rerun 输入排除 runtime state、史源检索和真实发布输入；validator 合同阻断真实人物发布、stage/final total table 和 cross-subitem leaderboard claim。本包不查史源、不读 JSONL、不构建真实人物发布结果，不发布任何新子项分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。后续可继续进入 #311 字典外置或非破坏性治理链路。

Issue #311 I5B rule/display dictionary externalization contract package 使用：

```bash
python scripts/platform/i5b_rule_display_dictionary_contract.py --contract-report
python scripts/platform/i5b_rule_display_dictionary_contract.py --dictionary-md
```

该包只盘点第五项B adapter 中仍硬编码在 Python 模块里的规则词表、档位映射和展示文案，并定义 versioned dictionary snapshot、loader 与 validator 合同。当前包不创建 PostgreSQL 字典表、不写 canonical dictionary、不迁移运行时 adapter，也不让普通导出脚本依赖 live DSN。

Issue #311 I5B dictionary snapshot loader / validator package 使用：

```bash
python scripts/platform/i5b_dictionary_snapshot_loader_validator.py --snapshot-report
python scripts/platform/i5b_dictionary_snapshot_loader_validator.py --validate-snapshot
python scripts/platform/i5b_dictionary_snapshot_loader_validator.py --snapshot-md
```

该包读取 repo 内 immutable snapshot `scripts/platform/i5b_dictionary_snapshots/i5b_rule_display_dictionary_snapshot_v1.json`，校验每个字典 item 的版本、scope、rule_id、locale、status、effective_from、gate_source、payload digest，并确认五类字典覆盖 contract inventory 的 14 个硬编码源符号。它仍不创建 PostgreSQL 字典表、不写 canonical dictionary、不迁移运行时 adapter，也不让普通导出脚本依赖 live DSN；下一步只能进入 runtime adapter dictionary readiness package 或单独 schema/config gate。

Issue #311 I5B runtime adapter dictionary readiness package 使用：

```bash
python scripts/platform/i5b_runtime_adapter_dictionary_readiness.py --readiness-report
python scripts/platform/i5b_runtime_adapter_dictionary_readiness.py --readiness-md
```

该包用 AST 只读核对 `rules.py`、`formal_algorithm.py` 与 adapter 展示函数中的 14 个硬编码符号，确认它们均已被 snapshot 覆盖，并列出 readthrough loader shim、rules.py 词表读取、formal algorithm 映射读取、display dictionary 读取和常量清理五段迁移批次。它不 import runtime adapter、不渲染 exports、不改变输出、不创建 PostgreSQL 字典表、不写 canonical dictionary；下一步只能进入 readthrough loader shim package。

Issue #311 I5B runtime dictionary readthrough shim 已新增：

```python
from export.dimension_adapters.i5b_people_delegation import dictionary_readthrough

snapshot = dictionary_readthrough.load_validated_dictionary_snapshot()
symbols = dictionary_readthrough.source_symbols_by_dictionary_type(snapshot)
```

该 shim 只读取 repo 内 immutable snapshot 并校验 digest / schema，提供按 `dictionary_type` 与 `rule_id` 查询的稳定 API。当前阶段不替换 `rules.py`、`formal_algorithm.py` 或 adapter 中的常量/展示文案，不渲染 exports，不创建 PostgreSQL 字典表，不写 canonical dictionary；下一步只能进入 `rules.py` 词表读取迁移。

Issue #311 `rules.py` keyword / rule dictionary readthrough 已启用：`HIGH_VALUE_ANCHOR_KEYWORDS`、`STARTUP_ANCHOR_KEYWORDS`、`BOUNDARY_ANCHOR_KEYWORDS`、`DIRECT_SAFETY_KEYWORDS`、`POSITIVE_CORE_KEYWORDS` 与 `RULE_SENSITIVE_POINTS` 现在从 immutable snapshot 的 `values_by_symbol` 初始化，并由 parity tests 锁定与原常量值一致。当前仍不迁移 `TRIAL_SCORE_MAP`、`DIMENSION_RULES`、`formal_algorithm.py` 或 adapter display text，不创建 PostgreSQL 字典表，不写 canonical dictionary；下一步只能进入 formal algorithm grade dictionary read package。

Issue #311 `formal_algorithm.py` grade / direction mapping readthrough 已启用：`FORMAL_GRADE_ENUM`、`FORMAL_GRADE_SPECS`、`AUTO_DIRECTION_TO_FORMAL_GRADE` 与 `FORMAL_GRADE_BAND_POSITION` 现在从 immutable snapshot 的 `values_by_symbol` 初始化，`FORMAL_GRADE_SPECS` 中的 percent 字符串在 runtime 转回 `Decimal`。当前仍不迁移 `rules.py` 的 `TRIAL_SCORE_MAP` / `DIMENSION_RULES` 或 adapter display text，不创建 PostgreSQL 字典表，不写 canonical dictionary；下一步只能进入 remaining `rules.py` grade / direction read package。

Issue #311 remaining `rules.py` grade / direction readthrough 已启用：`TRIAL_SCORE_MAP` 与 `DIMENSION_RULES` 现在也从 immutable snapshot 初始化，并由 parity tests 锁定与原常量值一致。当前仍不迁移 adapter display text，不创建 PostgreSQL 字典表，不写 canonical dictionary；下一步只能进入 display dictionary read package。

Issue #311 adapter display dictionary readthrough 已启用：`render_score_mapping_draft` 的静态段落与 `render_formal_person_section` 的标题 / 行模板现在从 immutable snapshot 初始化，并由 parity tests 锁定输出形态。当前仍不创建 PostgreSQL 字典表、不写 canonical dictionary、不让普通导出依赖 live DSN、不进入 G10；下一步只能进入 Python constant cleanup after readthrough package。

Issue #311 Python constant cleanup after readthrough 已完成只读审计：`scripts/platform/i5b_python_constant_cleanup_after_readthrough.py` 核对 `rules.py`、`formal_algorithm.py` 与 adapter 展示函数中登记的 14 个符号，确认 runtime Python 模块仍保留兼容公开接口，但不再承载旧的大段字典 literal 或 G8/G9 展示文案 literal。当前仍保留 immutable snapshot，不创建 PostgreSQL 字典表、不写 canonical dictionary、不发布新分值或排名、不进入 G10；下一步进入 #311 rule/display dictionary governance gate。

Issue #311 rule/display dictionary governance gate 已记录：当前 pre-G10 runtime 继续以 repo 内 immutable snapshot 作为离线发布工件；未来若要创建 PostgreSQL 字典表或写 canonical dictionary，必须单独 schema/write gate、单独 PR、单独审计。当前包不连接数据库、不读取 DSN、不渲染 exports、不发布新分值或排名、不进入 G10；下一步回到 Epic5 pre-G10 contract/schema/report/test/plumbing 工作。

Epic5 per-subitem G8 algorithm release gate contract 已新增：`scripts/platform/epic5_per_subitem_g8_algorithm_release_gate.py` 为第二项、第三项、第六项试点子项生成 G8 算法释放 gate 模板，复用 subitem profile、formal grade、deterministic rerun、impact report 与 publication report 合同。当前只定义 gate 检查项和禁止输出，不执行真实 G8 release，不查史源，不构建人物级结果，不发布新子项分值或排名，不生成阶段总榜、最终总榜或跨子项 leaderboard。

G10-0 cleanup inventory / mapping / restore plan package 使用：

```bash
python scripts/platform/g10_cleanup_inventory_plan.py --inventory-report
python scripts/platform/g10_cleanup_inventory_plan.py --inventory-md
```

该包只为 #331 锁定 G10 前清单：覆盖 scripts、docs、archives、generated exports、registry entries 与 tests 的候选资产分类，并给 retire / archive / delete 候选写明 replacement mapping 和 restore plan。当前包不读取 `.env`、不连接数据库或网络、不读取 canonical JSONL / batch payload / generated exports 内容，不移动、不删除、不归档文件，不发布新分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。后续执行顺序为 #332 字典最终收口、#333 历史资产退役、#334 脚本资产风险治理、#341 低风险脚本 lifecycle 实执行、#342 脚本治理规则固化、#335 G10 验收与路线同步。

G10-1 I5B rule/display dictionary final cleanup package 使用：

```bash
python scripts/platform/g10_i5b_dictionary_final_cleanup.py --cleanup-report
python scripts/platform/g10_i5b_dictionary_final_cleanup.py --cleanup-md
```

该包完成 #332 的只读收口：`RULE_RUNTIME_TEXT` 与 `FORMAL_ALGORITHM_DISPLAY` 已进入 immutable snapshot，`rules.py` / `formal_algorithm.py` / `adapter.py` 只保留符号、key、loader 调用和运行时不变量；`adapter.py`、`scripts/shared/i5b_markdown_display_defaults.py` 与相关测试中的剩余中文文本已按 display copy、display config source、test fixture 分类。当前包校验 snapshot digest、读穿引用和 legacy runtime copy 回归，但不创建 PostgreSQL 字典表、不写 canonical dictionary、不读取 live DSN、不移动/删除/归档文件，也不发布新分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。后续进入 #333 历史资产退役诊断。

G10-2 historical asset retirement manifest package 使用：

```bash
python scripts/platform/g10_historical_asset_retirement.py --retirement-report
python scripts/platform/g10_historical_asset_retirement.py --retirement-md
```

该包完成 #333 的可审计退役执行包：按 #331 inventory 覆盖 Epic5 pre-G10 contract packages、docs registry lifecycle maps、archive docs historical records、archive/data batch history、generated exports 五类候选，写出 changed / removed / archived path manifest、replacement mapping 与 restore instructions。当前实际移动、删除、归档路径数为 `0`；`archive/data`、`data/batches` 与 `exports` 的 destructive action 因存在 batch review context、registry / tests 引用和恢复 gate 要求而继续 deferred。当前包不读取 batch payload 或 generated export 正文，不连接数据库或网络，不发布新分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。后续进入 #334 script asset risk governance。

G10-3 script asset risk governance package 使用：

```bash
python scripts/platform/g10_script_asset_risk_governance.py --script-delta-report
python scripts/platform/g10_script_asset_risk_governance.py --script-delta-md
```

该包完成 #334 的 Script Delta：只读核对 `scripts_registry.json` 的 platform lifecycle，确认 `transitional_scripts_without_sunset = 0`、`retired_scripts_in_default_validate_or_public_cli = 0`，并为 gate / report / redaction / fingerprint / evidence / mapping / resolver / schema / migration / seed 等重复能力族给出保留或收束理由。新增测试用坏 registry fixture 证明无 sunset transitional 与 retired default route 会被抓出，避免只做 report 文本镜像。当前包不改普通业务行为，不连接数据库或网络，不移动、删除或归档文件，不发布新分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。后续已拆分为 #341 低风险脚本 lifecycle 实执行、#342 registry lifecycle guard，再回 #335 G10 completion verification and roadmap handoff。

G10-2b low-risk script lifecycle execution package 使用：

```bash
python scripts/platform/g10_low_risk_script_lifecycle_execution.py --lifecycle-report
python scripts/platform/g10_low_risk_script_lifecycle_execution.py --lifecycle-md
```

该包完成 #341 的低风险 lifecycle 实执行：`anchors_schema_proposal.py`、`formal_ddl_live_rehearsal.py`、`formal_ddl_rehearsal.py`、`formal_schema_draft.py`、`schema_changing_formal_schema_update.py`、`schema_diff_draft_renderer.py` 在 `scripts_registry.json` 中由 `audit_only` 推进为 `retired`，replacement 均指向 `scripts/platform/platform_chain_checkpoint.py`，并为每个影响项记录 restore instruction。当前实际移动、删除、归档路径数仍为 `0`，不触碰 `data/`、`archive/data/` 或 `exports/`，不发布新分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。后续进入 #342 脚本治理规则固化，再回 #335 / #340 修订最终 handoff。

G10-3b script governance enforcement 使用：

```bash
python scripts/validate/validate_script_lifecycle_registry.py
python scripts/validate/validate_script_lifecycle_registry.py --guard-report
```

该 guard 完成 #342 的长期仓库检查：`validate_all.py` 会强制执行 registry lifecycle guard，确认 transitional script 必须有 `sunset_milestone`，retired script 不得进入默认 validate route 或 public CLI，duplicate capability group 若存在多个成员必须有保留理由或治理计划。坏 lifecycle fixture、retired default/public route fixture 和缺少理由的 duplicate fixture 都由 outcome-level tests 锁定。当前 guard 不读取 `.env`，不连接数据库或网络，不读取 batch payload 或 generated export 正文，不触碰 `data/`、`archive/data/` 或 `exports/`，不发布新分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。后续回 #335 / #340 修订最终 handoff。

G10-4 completion verification and roadmap handoff package 使用：

```bash
python scripts/platform/g10_completion_verification_handoff.py --completion-report
python scripts/platform/g10_completion_verification_handoff.py --completion-md
```

该包完成 #335 的 G10 收尾验收：汇总 #332 / #333 / #334 / #341 / #342 结果，记录 #336—#339、#343、#344 均已 merge，确认除当前 handoff PR 外 open ready PR count 为 `0`、registry dangling references 为 `0`、G10 report complete、低风险 lifecycle 实执行完成且 registry lifecycle guard 已接入 `validate_all`，并列出 focused tests、`validate_all`、governance checks 和 full pytest 的验证矩阵。当前包只做状态验收和路线交接，不新增退役范围，不移动、删除或归档文件，不连接数据库或网络，不发布新分值、排名、阶段总榜、最终总榜或跨子项 leaderboard。后续进入 post-G10 follow-up gates；任何 deferred destructive cleanup 仍必须单独 gate。

Post-G10 follow-up gates readiness package 使用：

```bash
python scripts/platform/post_g10_followup_gates_readiness.py --gates-report
python scripts/platform/post_g10_followup_gates_readiness.py --gates-md
```

该包在 #340 merge 后固化 `post_g10_ready_for_followup_gates_ready`：记录 #340 handoff merge commit，列出 8 个后续 gate，并将每个 gate 保持为 `requires_separate_ready_review`。当前包不批准、不执行 per-subitem G9 发布、leaderboard、阶段/最终总表、G10 destructive cleanup、source/passages 合并策略、evidence/cluster/anchor/relationship 写入或 Epic2 / Epic3 entry；#345 之后先进入 #346 script lifecycle finalization，#346 ready review / merge 后再选择单个 non-script follow-up gate。

Post-G10-S1 script lifecycle finalization package 使用：

```bash
python scripts/platform/post_g10_script_lifecycle_finalization.py --finalization-report
python scripts/platform/post_g10_script_lifecycle_finalization.py --finalization-md
```

该包在 #345 之后继续推进 #346，不再停在 readiness / report / handoff：`scripts_registry.json` 中剩余 24 个 `audit_only` / `superseded` / `transitional` platform script asset 已实际推进为 `retired`，并与 #341 已 retired-in-place 的 6 个低风险项合并为 30 个 non-active script asset 的最终 lifecycle manifest。每个影响项都记录最终决策、replacement、sunset / last required by 字段和 restore instruction；其中 13 个超过 500 行的大型 retired 脚本已移动到 documented retired location `scripts/platform/_retired/post_g10_s1`，其余 17 个 retained in place。该移动只处理 script assets，不删除、不归档，也不触碰 `data/`、`archive/data/` 或 `exports/`。

当前 #346 状态为 `post_g10_s1_script_lifecycle_finalization_ready`：updated registry entries 为 `24`，finalized non-active manifest item 为 `30`，documented retired location 移动数为 `13`，retained-in-place 数为 `17`，active platform root 中 retired script file 从 `30` 降到 `17`，active root line reduction 为 `8132`，`transitional_scripts_without_sunset = 0`，`retired_scripts_in_default_validate_or_public_cli = 0`，`duplicate_capability_groups_without_reason = 0`，remaining script governance debt 为 `0`。旧 report-only count 断言已由 outcome-level coverage 替换，`validate_script_lifecycle_registry.py` 与 `validate_all.py` 继续阻断无 sunset transitional、retired public/default route 和无理由 duplicate capability group。该阶段只处理 script assets，不碰高风险根目录，不切 runtime，不迁移生产数据，不发布新分值、排名、阶段总榜、最终总榜或跨子项 leaderboard，也不进入 Epic2 / Epic3。

## JSONL staging mapper prototype

`scripts/platform/jsonl_staging_mapper.py` 是 JSONL -> PostgreSQL staging 的隔离 schema 原型。它复用 `jsonl_import_dry_run.py` 的 `imports` / `import_rows` 审计写入，以及 `jsonl_target_mapping.py` 的映射契约，从 `import_rows.payload` 生成 `stg_jsonl_rows`。该工具不迁移 JSONL、不切换写源、不写正式 target business tables，也不依赖 `psql`。

默认命令不会连接数据库：

```bash
python scripts/platform/jsonl_staging_mapper.py --check
python scripts/platform/jsonl_staging_mapper.py --contract-report
```

需要真实执行时，只读取本地 shell 或 `.env` 中的 `EMPEROR_EVAL_PG_DSN`，不使用旧 search benchmark DSN：

```bash
python scripts/platform/jsonl_staging_mapper.py --apply --schema emperor_eval_staging_mapper --drop-schema-after
```

`--apply` 会在隔离 schema 中执行 `001_init.sql`、写入 dry-run 审计表、创建 staging 表、按 direct / candidate / payload / range_filter / reference_risk / unknown / validation_errors 分类 payload。`source_id`、`linked_*`、`*_ids` 和 `cross_item*` 等字段只进入 reference risk 或 validation，不会被转换为外键。events、trigger_terms 和 thematic anchor 文件保持 `staging_only=true`；anchors 只作为候选 target，anchor links、events 和 trigger terms 的正式 target 语义必须后续批准。
