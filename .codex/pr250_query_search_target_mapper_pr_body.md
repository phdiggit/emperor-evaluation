## Summary

- 新增 `jsonl_query_search_target_mapper.py`，提供 query_profiles / search_tasks target mapper prototype。
- 支持离线 `--contract-report` 与 opt-in `--apply --schema ... --drop-schema-after`。
- 新增 contract 与 integration 测试，锁定离线报告、resolver 边界、隔离 schema 写入与清理行为。

## Scope

- 本 PR 只新增 target mapper prototype 与对应测试。
- 未修改 canonical JSONL。
- 未修改 `db/postgres/001_init.sql`。
- 未修改 docs、README、AGENTS 或 workflow。

## Target Mapping Behavior

- `query_profile_id` 映射为 prototype `query_profiles.code`。
- `profile_scope` 映射为 prototype `query_profiles.scope`。
- `status` 映射为 prototype `query_profiles.status`。
- `search_id` 映射为 prototype `search_tasks.code`。
- `query` 映射为 prototype `search_tasks.query_text`。
- `query_terms`、payload fields、range/filter fields 与 reference-risk fields 只进入 payload 或 report 计划。
- `--apply` 复用现有 import dry-run / staging mapper 路径，再在隔离 schema 内重建 relaxed prototype target tables，避免生产 FK 约束要求未解析关系。

## Resolver / Safety Boundary

- 未写正式 target business tables。
- 未切换 JSONL 写源。
- 未连接 PostgreSQL，除非 `--apply` opt-in。
- 未使用 `psql` 或 shell database subprocess。
- 未使用 `PG_SEARCH_BENCH_DSN`。
- 未生成评分、排名或裁判结论。
- `item` / `subitem` / `person` 不直接写 FK 或 evidence relationship。
- `query_profile_id` 未有可靠 resolver output 前不写 query_profile FK。
- `linked_*`、`*_ids`、`cross_item*` 不写 FK、不写 `search_hits`、不写 evidence/source relationship tables。
- thematic anchor 文件继续 staging-only。

## Validation

- `pytest -q tests/test_jsonl_query_search_target_mapper_contract.py` - passed, 11 tests.
- `pytest -q tests/test_jsonl_query_search_target_mapper_integration.py` - passed, 1 test.
- `pytest -q tests/test_jsonl_staging_resolver_contract.py tests/test_jsonl_staging_mapper_contract.py` - passed, 22 tests.
- `python scripts/platform/jsonl_query_search_target_mapper.py --contract-report` - passed.
- `python scripts/platform/jsonl_staging_resolver_contract.py --contract-report` - passed.
- `python scripts/platform/jsonl_unknown_field_triage.py --contract-report` - passed.
- `python scripts/platform/jsonl_staging_mapper.py --contract-report` - passed.
- `python scripts/dev/repo_tool.py agents-check` - passed.
- `python scripts/dev/repo_tool.py canonical-imports-check` - passed.
- `python scripts/validate/validate_all.py` - passed.
- `git diff --check` - passed.
- `python scripts/dev/repo_tool.py scope-check --forbid 'data/**' --forbid 'archive/data/**' --forbid 'db/schema.sql' --forbid 'db/postgres/001_init.sql' --forbid 'exports/markdown_views/**' --forbid 'docs/皇帝综合评价体系评分标准.md' --forbid 'docs/分项规则/**' --forbid 'docs/证据规则/**'` - passed.

## Final Changed Files

```text
scripts/platform/jsonl_query_search_target_mapper.py
tests/test_jsonl_query_search_target_mapper_contract.py
tests/test_jsonl_query_search_target_mapper_integration.py
```

## Known Limits

- This is a prototype mapper for query/search targets only.
- It does not implement durable resolver output for query profile FK, person FK, subitem FK, source/evidence relationships, `search_hits`, sources, passages, evidence, clusters, or anchors.
- It intentionally creates relaxed prototype tables inside the opt-in isolated schema because the production table shape requires resolver-backed FKs.
