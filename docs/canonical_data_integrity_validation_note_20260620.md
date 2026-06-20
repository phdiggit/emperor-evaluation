# Canonical Data Integrity Validation Note 20260620

新增独立校验脚本：

- `python scripts/validate_canonical_data_integrity.py`

可选最小测试入口：

- `pytest -q tests/test_canonical_data_integrity.py`

## 覆盖范围

脚本会直接校验以下 canonical JSONL 文件的可解析性与关键 invariant：

- `data/query_profiles.jsonl`
- `data/search_logs.jsonl`
- `data/thematic_anchors.jsonl`
- `data/thematic_anchor_objects.jsonl`
- `data/thematic_anchor_mechanisms.jsonl`
- `data/thematic_anchor_events.jsonl`

## 保护的回归点

1. `query_profiles.jsonl` 不得出现重复 `query_profile_id`
2. `search_logs.jsonl` 不得出现重复 `search_id`
3. `thematic_anchors.jsonl` 不得出现重复 `anchor_id`
4. thematic anchor 三个 lane 文件内不得重复 `anchor_id`
5. thematic anchor 三个 lane 文件之间不得跨文件重复 `anchor_id`
6. 来自 `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl` 的 canonical 行必须保留 `source_batch`
7. 来自 `data/search_log_batches/i5b_next_four_20260618.jsonl` 的 canonical 行必须保留 `source_batch`
8. 上述 search log 行若存在 `source_status` / `source_polarity`，则不得为空
9. 来自 `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 的 lane 行必须保留 `source_batch`
10. `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 必须继续位于 `data/thematic_anchor_events.jsonl` 且 `anchor_kind=event`
11. `ANCH-I5B-MECHANISM-SHENTUGANG-EXPRESSION-SAFETY-20260618` 必须继续位于 `data/thematic_anchor_mechanisms.jsonl` 且 `anchor_kind=mechanism`
12. `search_logs.jsonl` 中若 `source_polarity=neutral`，则 canonical `polarity` 允许为 `negative`，但原始 `source_polarity=neutral` 必须保留

## 设计边界

- 这是独立 hardening 校验，不改动任何 canonical 数据
- 不重构 `scripts/validate_evidence.py`
- 依赖保留的 source batch 作为追溯输入做 exact-id 对照
