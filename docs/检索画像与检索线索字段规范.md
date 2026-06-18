# 检索画像与检索线索字段规范

本规范用于固定 `query_profile` 与 `search_log` 的长期内容格式。它补充《第五项B正式工作流模板》和《数据层级与批次文件治理规则》，解决“生成 query 之前，画像应如何组织”的问题。

## 一、定位

`query_profile` 是检索前置画像，不是证据、不是裁量、不是定档。

它只回答三个问题：

1. 本项目/本人物应当查哪些方向？
2. 哪些方向最容易漏查或偏查？
3. 后续 `search_log` 为什么从这些方向生成？

`search_log` 是具体检索线索，不是证据卡。

它只回答三个问题：

1. 这条线索要查什么？
2. 当前状态是什么？
3. 回源后是否转为 `source` / `evidence_card` / `rejected`？

## 二、query_profile 分层

### 1. 项目级 query_profile

项目级画像定义某一子项的通用检索框架。长期保存在 `data/query_profiles.jsonl`。

建议字段：

```json
{
  "query_profile_id": "QRY-I5B-001",
  "schema_version": "1.0",
  "profile_scope": "project_level",
  "item": "第五项",
  "subitem": "第五项B",
  "status": "active",
  "search_modes": [],
  "positive_dimensions": [],
  "negative_dimensions": [],
  "reversal_dimensions": [],
  "source_scopes": [],
  "reverse_search_required_when": [],
  "thematic_anchor_targets": [],
  "cross_item_split_notes": [],
  "coverage_policy": "覆盖检索方向，不规定每个方向必须等量建卡。",
  "evidence_policy": "query_profile 不直接作为证据或评分依据。",
  "note": ""
}
```

项目级画像应偏稳定，避免频繁为单个案例修改。若某人物出现特殊问题，应放入人物级画像。

### 2. 人物级 query_profile

人物级画像定义某人物在某子项中的检索范围。可先存入 `data/query_profile_batches/*.jsonl`，阶段收束后再合并进 `data/query_profiles.jsonl` 或归档。

建议字段：

```json
{
  "query_profile_id": "QRY-I5B-LIUBANG-20260618",
  "schema_version": "1.0",
  "profile_scope": "person_level",
  "profile_role": "person_level_query_profile",
  "inherits_from": "QRY-I5B-001",
  "person": "刘邦",
  "item": "第五项",
  "subitem": "第五项B",
  "status": "batch_pending_merge",
  "positive_dimensions": [],
  "negative_dimensions": [],
  "reversal_or_balance_dimensions": [],
  "cross_item_risks": [],
  "priority_search_ids": [],
  "coverage_policy": "每个关键维度至少有检索入口，但不要求每个入口都转证据卡。",
  "evidence_policy": "只有回源、直接相关、可裁量、有新维度或强度价值的材料才建证据卡。",
  "retention_policy": "阶段收束后合并进 canonical query_profiles 或归档/删除批次文件。",
  "note": ""
}
```

人物级画像应避免写成小传、印象评价或预裁量结论。它只组织检索方向。

## 三、search_log 字段规范

`search_log` 是从 `query_profile` 派生出的具体检索线索。长期主表为 `data/search_logs.jsonl`，批次文件可暂存于 `data/search_log_batches/*.jsonl`。

建议字段：

```json
{
  "search_id": "SRCH-I5B-LIUBANG-POS-SHIREN-001",
  "query_profile_id": "QRY-I5B-LIUBANG-20260618",
  "person": "刘邦",
  "item": "第五项",
  "subitem": "第五项B",
  "polarity": "positive",
  "trigger_family": "识人拔擢",
  "query_terms": [],
  "result_summary": "",
  "status": "lead_needs_source_review",
  "derived_from_dimension": "positive_dimensions: 识人拔擢",
  "expected_source_scope": [],
  "cross_item_watch": [],
  "next_action": "source_review",
  "linked_source_ids": [],
  "linked_evidence_ids": [],
  "rejection_reason": null,
  "note": ""
}
```

## 四、状态枚举

### query_profile.status

建议使用：

- `active`：长期有效。
- `batch_pending_merge`：批次文件中，待合并或归档。
- `archived`：已归档，不再生成新 search_log。
- `superseded`：已被新版本替代。

### search_log.status

建议使用：

- `lead_needs_source_review`：只有线索，待回源。
- `source_review_pending`：已定位来源，待核。
- `source_verified_candidate`：已回源，可考虑建卡。
- `evidence_found_card_created`：已建证据卡。
- `rejected_irrelevant`：不归本项。
- `rejected_duplicate`：重复材料。
- `rejected_low_value`：同类厚度补充，无新维度或强度价值。
- `needs_human_review`：需人工判断。

## 五、覆盖原则

1. `query_profile` 负责覆盖方向，不负责制造证据数量。
2. `search_log` 负责记录检索入口，不负责保证结论平衡。
3. 每个关键维度可以有多条史料证据。
4. 多条同类材料可以增强结构性，但不得按条数机械加分。
5. 同类证据达到代表性覆盖后，后续同类材料只增厚元数据，除非提供新维度、强反证、反转材料或相邻项切分价值。
6. 强正、强负、极正、极负候选必须触发反向检索和相邻项切分复核。

## 六、禁止事项

- 禁止把 `query_profile` 写成预设结论。
- 禁止用 `query_profile` 代替证据卡。
- 禁止要求每个画像点都必须产出一张证据卡。
- 禁止把 `search_log` 的存在视为已回源。
- 禁止用同类史料堆条数来机械抬高强度。
- 禁止在生成 query 时只覆盖人物最著名的正负两端，而忽略授权、反馈、表达安全、人才生态和相邻项切分。

## 七、长期组织方式

推荐长期保留三类文件：

1. 正式流程模板：说明步骤和边界。
2. 字段规范：说明 JSONL 应怎么写。
3. canonical 数据主表：保存结构化数据。

不推荐长期保留大量平行解释性文档。若某条规则已经稳定，应合并进模板或字段规范；若只是某轮任务判断，应作为批次文件、PR comment 或临时草稿处理。
