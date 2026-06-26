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
