# JSONL 到 PostgreSQL 映射规则

本文档是 canonical JSONL 主表进入 PostgreSQL staging/target 的契约入口。当前仓库仍以 JSONL 为写源，本规则不迁移 JSONL、不切换写源、不写业务事实表，也不生成 evidence card、分值、排名或裁判发布结果。

`scripts/platform/jsonl_target_mapping.py --contract-report` 输出机器可读 JSON report，用来暴露每个 canonical 文件的 target 倾向、direct 字段、payload 字段、reference risk、staging-only 边界、缺失 code、重复 code、未知字段和解析错误。该工具默认不连接 PostgreSQL，不访问公网，不依赖 `psql`，也不读取 `data/batches/**` 或 `archive/data/**`。

## 边界

- JSONL 仍是当前写源；PostgreSQL target 只是后续平台化目标。
- `jsonl_import_dry_run.py` 只验证逐行解析、payload hash 和 `imports` / `import_rows` 审计写入。
- 本映射契约只描述 staging/target 规则，不执行 staging 导入。
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
