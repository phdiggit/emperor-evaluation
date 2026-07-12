# JSONL 到 PostgreSQL 映射规则

本文保留 JSONL 字段到未来 PostgreSQL staging/target 结构的规则说明。#354 合并后，原 `scripts/platform/` 映射、staging、approval、unknown-field triage 和 PostgreSQL 执行原型已经删除；本文不再提供当前可运行命令。

## 当前统一状态

```yaml
current_phase: workflow_only_cutdown_post_merge_verified
canonical_write_source: jsonl
sqlite_build_operational: true
postgres_schema_contract_retained: true
postgres_business_data_migrated: false
jsonl_write_frozen: false
postgres_unique_write_source: false
production_runtime_live: false
formal_scoring_released: false
formal_ranking_released: false
platform_scripts_tracked_files: 0
source_ingest_tracked_files: 0
```

## 当前边界

- `data/*.jsonl` 仍是当前事实源。
- 当前产品工作流是 JSONL -> SQLite cache -> Markdown/export views。
- PostgreSQL schema 只作为历史/未来 contract 保留，不代表当前业务写源。
- 本文的 mapping 内容只用于解释字段语义和未来候选映射，不是 migration 执行说明。
- 不再引用已删除的 `scripts/platform/` 或 `scripts/source_ingest/` 命令作为现行入口。

## 文件映射

### events.jsonl

当前 PostgreSQL schema 没有正式 events target table；`events.jsonl` 只能作为未来 staging-only 候选。`event_id`、`event_name`、`event_date`、`description` 是事件观察候选字段；`action_type`、`attribution_type`、`outcome`、`severity`、`time_phase` 只能作为候选字段保留。`source_id` 属于 reference risk，等待 source/passages resolver。

### query_profiles.jsonl

目标候选为 `query_profiles`。`query_profile_id` 可映射到 `query_profiles.code`；`profile_scope` 和 `status` 可作为 scope/status 候选；`item`、`subitem`、`person` 只作为范围筛选和后续 resolver 输入。

### search_logs.jsonl

目标候选为 `search_tasks`；处理 URL 或 result entry 时可候选进入 `search_hits`。`search_id` 可映射到 `search_tasks.code`；`query` 可作为 `query_text` 候选。`query_profile_id`、`linked_source_ids`、`linked_evidence_ids` 保留为 reference risk；search log 不是 evidence card。

### sources.jsonl

目标候选为 `src_hosts`、`src_docs`、`doc_revs`、`passages`。`title/source_title`、`url/source_url`、`host/source_host` 可作为文档和 host 候选；`source_id` 只能作为 `src_docs.code` 或 `doc_revs.code` 候选，不保证一对一关系。quote/context/raw text 需要人工审核后才可能成为 passage。

### evidence_cards.jsonl

目标候选为 `evd_cards` 和 `evd_src_links`。`evidence_id` 可映射到 `evd_cards.code`；`polarity`、`strength`、`human_level`、`quote_short`、`interpretation`、`cross_item_split`、`scoring_effect` 是 `evd_cards` 候选字段。`source_id` 不等于 `passage_id`，需等 source/passages 规则完成后再判断能否进入 `evd_src_links`。

### evidence_clusters.jsonl

目标候选为 `clusters` 和 `cluster_evd`。`cluster_id` 可映射到 `clusters.code`；`summary`、`adjudication_status`、`candidate_strength`、`polarity` 是候选字段。`linked_evidence_ids` 需要 evidence card code 解析后才可能进入 `cluster_evd`。

### thematic_anchors*.jsonl

当前 PostgreSQL schema 有 `anchors` 候选基础表，但没有正式 `anchor_links` target table。`thematic_anchors.jsonl`、`thematic_anchor_objects.jsonl`、`thematic_anchor_events.jsonl`、`thematic_anchor_mechanisms.jsonl` 只能作为 staging-only 候选。`anchor_id` 可作为 `anchors.code` 候选；`object_name` 可作为 `anchors.label` 候选；`anchor_kind` 可作为 `anchors.anchor_type` 候选。`linked_persons`、`linked_evidence_ids`、`linked_cluster_ids` 仍是 reference risk。

### trigger_terms.jsonl

当前 PostgreSQL schema 没有正式 trigger_terms target table；`trigger_terms.jsonl` 只能作为 staging-only 候选。`term_id`、`term`、`trigger_family` 是候选 direct 字段；`polarity`、`tier` 是候选字段；`item`、`subitem` 只作为范围筛选和后续 subitem resolver 输入。

## 后续规则

任何重新启用 PostgreSQL mapping、staging、source-ingest 或 production runtime 的动作都必须另开 issue，先定义当前产品价值、数据边界、危险动作、验证策略和回滚方式，再通过新 PR 实现。历史 ADR 与 Git history 可以提供背景，但不能自动恢复为当前入口。
