# Post-G10 Script Governance Effect Audit (#348)

> 历史审计快照：本文记录 #348 / #347 阶段的脚本治理效果。#354 合并后，`scripts/platform/`、`scripts/platform/_retired/` 和 `scripts/source_ingest/` 均为 0 个 tracked 文件；本文中的脚本路径和 helper consolidation 建议只保留为历史审计背景，不再代表当前可运行入口或后续任务方向。

本审计按 #348 的 5A 原口径重新统计脚本治理效果。口径是 tracked files，而不是 PR 自报指标；`scripts/platform/_retired/` 作为 retained audit footprint 单独列出，不计为代码消失。

## Measurement Scope

- 5A baseline source: `皇帝综评_全局路线规划.md` 的 `5A.1 规模基线`，记录日期为 2026-06-25。
- 5A baseline is not the #345 merge commit. The #345 -> #347 comparison below is only the local Post-G10-S1 delta.
- Current ref: `78e7e746009124ce14e25b311c1b02c41f6bd4a9` (#347 merge commit)。
- 文件集合: 5A baseline 使用路线文档记录值；current / local delta 使用 `git ls-tree -r --name-only <ref>` / `git ls-files` 的 tracked files。
- 文本行: UTF-8 / UTF-8 BOM / UTF-16 可解码且无 NUL byte 的 tracked text files。
- Estimated code lines: 非空且不以常见注释前缀开头的行；这是比较用估算值，不替代语义审查。
- Active-root: 物理路径位于 `scripts/platform/*.py` 或同级文本文件，且不在 `scripts/platform/_retired/` 下。
- Active scripts top 20: registry `lifecycle_status=active` 且路径不在 `_retired` 下的 `scripts/platform/*.py`。

## Global 5A Baseline / Current

This is the main #348 comparison. It uses the original 5A baseline from the global roadmap instead of PR-local self-reported metrics.

| Metric | 5A baseline | Current after #347 | Delta |
| --- | ---: | ---: | ---: |
| tracked files | 477 | 563 | +86 |
| repository text lines | 89,600 | 91,965 | +2,365 |
| `scripts/` files | 113 | 158 | +45 |
| `scripts/` total lines | 34,182 | 47,973 | +13,791 |
| `scripts/` estimated code lines | 29,381 | 42,650 | +13,269 |
| `tests/` files | 121 | 159 | +38 |
| `tests/` total lines | 26,551 | 34,916 | +8,365 |
| `tests/` estimated code lines | 21,262 | 28,201 | +6,939 |
| `scripts/platform/` recursive files | 53 | 94 | +41 |
| `scripts/platform/` recursive total lines | 22,056 | 35,189 | +13,133 |
| `scripts/platform/` recursive estimated code lines | 19,150 | 31,664 | +12,514 |
| `scripts/platform/` active-root files | not separately listed | 74 | n/a |
| `scripts/platform/` active-root total lines | not separately listed | 26,130 | n/a |
| `scripts/platform/_retired/` files | not separately listed | 14 | n/a |
| `scripts/platform/_retired/` total lines | not separately listed | 8,137 | n/a |

## Post-G10-S1 Local Delta

This secondary table explains what #347 changed after #345. It is useful for path-movement interpretation, but it is not the original 5A baseline.

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| tracked files | 559 | 563 | +4 |
| repository text files | 412 | 416 | +4 |
| repository text lines | 90,723 | 91,965 | +1,242 |
| repository estimated code lines | 76,671 | 77,764 | +1,093 |
| `scripts/` files | 156 | 158 | +2 |
| `scripts/` total lines | 47,175 | 47,973 | +798 |
| `scripts/` estimated code lines | 41,945 | 42,650 | +705 |
| `tests/` files | 157 | 159 | +2 |
| `tests/` total lines | 34,483 | 34,916 | +433 |
| `tests/` estimated code lines | 27,820 | 28,201 | +381 |
| `scripts/platform/` recursive files | 92 | 94 | +2 |
| `scripts/platform/` recursive total lines | 34,391 | 35,189 | +798 |
| `scripts/platform/` recursive estimated code lines | 30,959 | 31,664 | +705 |
| `scripts/platform/` active-root files | 86 | 74 | -12 |
| `scripts/platform/` active-root total lines | 33,487 | 26,130 | -7,357 |
| `scripts/platform/` active-root estimated code lines | 30,082 | 23,446 | -6,636 |
| `scripts/platform/_retired/` files | 0 | 14 | +14 |
| `scripts/platform/_retired/` total lines | 0 | 8,137 | +8,137 |
| `scripts/platform/_retired/` estimated code lines | 0 | 7,325 | +7,325 |

## Interpretation

- Against the original 5A baseline, repository text lines are up 2,365 and `scripts/platform/` recursive lines are up 13,133. So #348 cannot conclude repository-wide code shrinkage.
- The #347 active-root reduction is still real in the local delta: `scripts/platform/` active-root dropped by 12 files and 7,357 text lines after #345.
- Repo-wide LOC reduction is not real even in the local delta: repository text lines increased by 1,242 and `scripts/platform/` recursive lines increased by 798.
- `_retired` is retained audit footprint: 14 files and 8,137 lines now live under `scripts/platform/_retired/`; these lines remain tracked and reviewable.
- #347 should be read as active-root cleanup plus first helper extraction, not as repository-wide code deletion.
- The delta is still useful because default/public routes are cleaner, top active-root retired files moved out of the default path, and active execution scripts now share fingerprint/redaction implementations.

## Top 20 Active Scripts

These are registry-active `scripts/platform/*.py` files outside `_retired`, sorted by current text lines.

| Rank | Path | Lines | Estimated code lines | Public CLI stable |
| ---: | --- | ---: | ---: | --- |
| 1 | `scripts/platform/g5_runtime_execution.py` | 893 | 812 | true |
| 2 | `scripts/platform/platform_chain_checkpoint.py` | 793 | 778 | true |
| 3 | `scripts/platform/cutover_readiness_matrix.py` | 715 | 665 | true |
| 4 | `scripts/platform/post_g10_script_lifecycle_finalization.py` | 647 | 588 | true |
| 5 | `scripts/platform/jsonl_evidence_clusters_resolver.py` | 623 | 549 | true |
| 6 | `scripts/platform/jsonl_staging_resolver_contract.py` | 623 | 576 | true |
| 7 | `scripts/platform/g6_formal_evidence_execution.py` | 601 | 539 | true |
| 8 | `scripts/platform/jsonl_evidence_cards_target_mapper.py` | 590 | 523 | true |
| 9 | `scripts/platform/jsonl_sources_target_mapper.py` | 579 | 516 | true |
| 10 | `scripts/platform/g4_write_source_cutover_execution.py` | 572 | 515 | true |
| 11 | `scripts/platform/jsonl_staging_mapper.py` | 559 | 487 | true |
| 12 | `scripts/platform/g3_postgres_business_write_execution.py` | 558 | 499 | true |
| 13 | `scripts/platform/jsonl_import_dry_run.py` | 531 | 472 | true |
| 14 | `scripts/platform/jsonl_target_mapping.py` | 527 | 490 | true |
| 15 | `scripts/platform/jsonl_query_search_target_mapper.py` | 491 | 440 | true |
| 16 | `scripts/platform/g10_cleanup_inventory_plan.py` | 481 | 451 | true |
| 17 | `scripts/platform/g10_completion_verification_handoff.py` | 467 | 428 | true |
| 18 | `scripts/platform/anchors_resolver_contract.py` | 461 | 401 | true |
| 19 | `scripts/platform/jsonl_anchors_target_mapper.py` | 450 | 396 | true |
| 20 | `scripts/platform/canonical_manifest_gate.py` | 446 | 407 | true |

## Duplicate Helper Families

This table counts repeated module-level helper/function names in active-root `scripts/platform/*.py` files outside `_retired`. It is a debt signal, not an automatic merge instruction; several names represent intentionally stable report/CLI contracts.

| Family | Active-root file count | Main interpretation |
| --- | ---: | --- |
| `report_as_json` | 65 | Very broad report boilerplate; consolidation could help but needs careful CLI compatibility. |
| `build_contract_report` | 46 | Contract package pattern; likely needs a shared report scaffold before deeper extraction. |
| `check_environment` | 12 | PostgreSQL/JSONL environment helper family; good candidate for next active helper extraction. |
| `is_psycopg_available` | 12 | Same DB availability pattern as `check_environment`; good candidate for shared helper. |
| `assert_report_has_no_blocked_terms` | 11 | Safety assertion family; could move toward a shared report-safety helper. |
| `integration_skip_reason` | 9 | Test/runtime environment gate helper; likely extractable with DB env helpers. |
| `relative_path` | 9 | Path formatting helper in migration/schema scripts; medium-value consolidation. |
| `resolve_dsn` | 9 | DB DSN resolution helper; high-value candidate because it touches repeated operational boundaries. |
| `build_adr_check` | 8 | Migration/ADR checker family; keep separate until ADR semantics are aligned. |
| `normalize_text` | 8 | Text normalization helper; possible shared helper after output semantics review. |
| `status_value` | 8 | Status formatting helper; low-risk but lower value than DB/env helpers. |
| `_relative` | 7 | G10/I5B report path helper; likely easy consolidation. |
| `_load_json` | 6 | Repeated registry/report JSON loader; easy consolidation candidate. |
| `build_blocked_relationship_writes` | 6 | Resolver/mapper safety helper; needs contract-level review before extraction. |
| `build_unresolved_references_by_file` | 5 | Evidence resolver helper; consolidate only with mapper/resolver contract tests. |
| `contains_connection_material` | 5 | Secret/connection detection family; overlaps with redaction work and is worth a focused pass. |
| `create_target_prototype_tables` | 5 | JSONL mapper DB prototype helper; consolidate only with isolated-schema tests. |
| `insert_target_rows` | 5 | JSONL mapper DB prototype helper; consolidate only with isolated-schema tests. |
| `stable_json_sha256` | 5 | Implementation is centralized in `scripts/platform/core/fingerprints.py`, but four active scripts keep thin compatibility wrappers. |
| `validate_isolated_schema` | 5 | JSONL mapper DB helper; good candidate for a mapper DB utility package. |

## Remaining Debt

- Registry duplicate capability groups still have explicit reasons/plans, so #342 guard remains satisfied.
- Active helper debt is not zero. The largest remaining families are report contract boilerplate, DB/env helpers, mapper DB helpers, path helpers, and compatibility wrappers.
- `stable_json_sha256` and `redact_secret` show the current state clearly: shared implementations exist, but some active public helper names remain as compatibility wrappers.
- Active large-script debt remains. `g5_runtime_execution.py`, `platform_chain_checkpoint.py`, `cutover_readiness_matrix.py`, and `post_g10_script_lifecycle_finalization.py` are now the largest registry-active scripts.

## Recommendation

Continue one more deep治理 pass only if it is scoped to active helper extraction, not broad script movement.

Recommended next issue:

- Target DB/env helper consolidation first: `check_environment`, `is_psycopg_available`, `integration_skip_reason`, `resolve_dsn`, and `validate_isolated_schema`.
- Keep report/contract boilerplate as a later design issue because `report_as_json` and `build_contract_report` are widespread public CLI/report patterns.
- Do not treat `_retired` growth as negative or as deletion; it is the retained audit footprint from #347.
- Do not use repo-wide LOC reduction as the success metric for the next pass. Use active-root helper count, active-root large-script line movement into shared helpers, and unchanged validation/default-route behavior.

Refs #348 #347 #346 #312 #287
