# JSONL 到 PostgreSQL 映射规则

本文档是 canonical JSONL 主表进入 PostgreSQL staging/target 的契约入口。当前仓库仍以 JSONL 为写源，本规则不迁移 JSONL、不切换写源、不写业务事实表，也不生成 evidence card、分值、排名或裁判发布结果。

当前统一状态口径：

```yaml
current_phase: platform-schema-live-data-not-cutover
canonical_write_source: jsonl
postgres_schema_live: true
postgres_business_data_migrated: false
jsonl_write_frozen: false
postgres_unique_write_source: false
production_runtime_live: false
formal_scoring_released: false
formal_ranking_released: false
```

`imports` / `import_rows` 是导入审计表和 staging 原型输入，不等于业务 target migration；文件级 SHA 只能证明源文件或审计包身份，不能伪装成逐行 payload hash。真实 target importer、逐行 payload hash、业务 target table 写入和 reconciliation 留给 Epic 1 的 G1 canonical manifest approval 之后处理。

`scripts/platform/jsonl_target_mapping.py --contract-report` 输出机器可读 JSON report，用来暴露每个 canonical 文件的 target 倾向、direct 字段、payload 字段、reference risk、staging-only 边界、缺失 code、重复 code、未知字段和解析错误。该工具默认不连接 PostgreSQL，不访问公网，不依赖 `psql`，也不读取 `data/batches/**` 或 `archive/data/**`。

`scripts/platform/jsonl_staging_mapper.py` 复用本契约，从 `import_rows.payload` 生成隔离 schema 内的 staging row。它仍不迁移 JSONL、不切换写源、不写正式 target business tables；`--contract-report` 只给本地聚合报告，`--apply` 才读取 `EMPEROR_EVAL_PG_DSN` 并连接本地 PostgreSQL。

`scripts/platform/jsonl_unknown_field_triage.py --contract-report` 在本地离线扫描 canonical JSONL 和当前 mapping contract，按源文件把 staging unknown 字段归入 `mapping`、`payload`、`reference_risk`、`manual_review`、`suspected_deprecated`。该工具只报告字段名、分类、原因和行号追踪，不读取 batches/archive，不连接 PostgreSQL，不写 target 表。

## 边界

- JSONL 仍是当前写源；PostgreSQL target 只是后续平台化目标。
- `jsonl_import_dry_run.py` 只验证逐行解析、payload hash 和 `imports` / `import_rows` 审计写入。
- 本映射契约描述 staging/target 规则；`jsonl_staging_mapper.py` 只执行隔离 schema staging 原型，不进入正式 target 表。
- 所有 `linked_*`、`*_ids`、`source_id`、`cross_item*` 类引用必须先进入 reference risk，不得在本 PR 直接写外键。
- 从 staging 进入 target table 必须另开 PR，并在该 PR 中定义解析器、人工复核和回滚策略。

## 文件映射

### query_profiles.jsonl

目标倾向为 `query_profiles`。`query_profile_id` 可映射到 `query_profiles.code`；`profile_scope` 和 `status` 是 `scope/status` 候选；`item`、`subitem`、`person` 只作为范围过滤和后续解析依据。人物中文名不能直接作为 `persons` 外键，`item + subitem` 不能直接变成证据关系。

### search_logs.jsonl

目标倾向为 `search_tasks`，并在存在 URL 或 result entry 时后续拆分 `search_hits`。`search_id` 可映射到 `search_tasks.code`；`query` 可作为 `query_text` 候选；`query_profile_id`、`linked_source_ids`、`linked_evidence_ids` 必须进入 reference risk。search log 不是 evidence card。

### sources.jsonl

目标倾向为 `src_hosts`、`src_docs`、`doc_revs`、`passages`。`title/source_title`、`url/source_url`、`host/source_host` 可作为文档和 host 候选；`source_id` 只能作为 `src_docs.code` 或 `doc_revs.code` 候选，不能草率固定一对一关系。quote/context/raw text 类字段需要人工复核后才能成为 passage。

### evidence_cards.jsonl

目标倾向为 `evd_cards` 和 `evd_src_links`。`evidence_id` 可映射到 `evd_cards.code`；`polarity`、`strength`、`human_level`、`quote_short`、`interpretation`、`cross_item_split`、`scoring_effect` 是 `evd_cards` 候选字段。`source_id` 不是 `passage_id`，必须在 source/passages 解析完成后再考虑 `evd_src_links`。

### evidence_clusters.jsonl

目标倾向为 `clusters` 和 `cluster_evd`。`cluster_id` 可映射到 `clusters.code`；`summary`、`adjudication_status`、`candidate_strength`、`polarity` 是 `clusters` 候选字段。`linked_evidence_ids` 必须等 evidence card code 解析完成后才能进入 `cluster_evd`。

### thematic_anchors*.jsonl

当前 PostgreSQL schema 尚无正式 `anchors` / `anchor_links` target table，因此 `thematic_anchors.jsonl`、`thematic_anchor_objects.jsonl`、`thematic_anchor_events.jsonl`、`thematic_anchor_mechanisms.jsonl` 全部标记为 `staging_only` 和 candidate mapping。`linked_persons`、`linked_evidence_ids`、`linked_cluster_ids` 只进入 reference risk；`item + subitem` 只作为范围过滤，anchor 本身不直接证明 evidence。

## Contract Report

推荐命令：

```bash
python scripts/platform/jsonl_target_mapping.py --contract-report
python scripts/platform/jsonl_target_mapping.py --source-root tests/fixtures/jsonl_import --contract-report
```

report 的稳定字段包括：

```text
mode
mapping_version
files_seen
files_missing
files
unmapped_files
unknown_fields_by_file
missing_required_fields_by_file
duplicate_codes_by_file
invalid_json_by_file
reference_risk_summary
staging_only_files
limitations
```

该 report 是后续 staging mapper 的输入契约，不是迁库执行结果。

## Staging Mapper Report

推荐命令：

```bash
python scripts/platform/jsonl_staging_mapper.py --check
python scripts/platform/jsonl_staging_mapper.py --contract-report
python scripts/platform/jsonl_staging_mapper.py --apply --schema emperor_eval_staging_mapper --drop-schema-after
```

`--contract-report` 的稳定字段包括：

```text
mode
mapping_version
default_tests_require_postgres
source_files
rows_total
rows_mapped
rows_with_reference_risk
rows_with_unknown_fields
rows_with_validation_errors
staging_only_files
target_table_candidates
limitations
```

`--apply` 输出隔离 schema 内的 `import_rows`、`staging_rows`、reference risk 行数、unknown field 行数、validation error 行数、staging-only 行数和 drop 后 schema 状态。该报告不得包含真实 DSN、密码、主机，也不得包含分值、排名或榜单输出。

## Unknown Field Triage Report

推荐命令：

```bash
python scripts/platform/jsonl_unknown_field_triage.py --contract-report
python scripts/platform/jsonl_unknown_field_triage.py --source-root tests/fixtures/jsonl_import --contract-report
```

`--contract-report` 的稳定字段包括：

```text
mode
triage_version
mapping_version
source_files
rows_by_file
observed_unknown_fields_by_file
decisions_by_file
decision_counts
unclassified_fields_by_file
remaining_unknown_fields_by_file
limitations
```

分类语义：

- `mapping`：字段语义和候选 target 已足够明确，可进入现有 direct / candidate / range-filter 映射。
- `payload`：保留原值作为业务上下文或审计 payload，不直接写关系。
- `reference_risk`：存在 resolver / FK 风险，只作为 reference-risk 数据保留。
- `manual_review`：字段语义或 target 位置仍不清楚，继续留在 staging unknown。
- `suspected_deprecated`：疑似迁移、过渡或旧字段，只作诊断；原值仍保留在 staging payload。

该报告是 unknown-field 分诊视图，不生成结论、不删除字段、不迁移 JSONL，也不证明任何证据关系。
