# 数据库说明

本项目当前采用 JSONL → SQLite → Markdown 的轻量数据工程流程。SQLite 是本地生成库和兼容缓存，不是最终主库。

## 数据角色

- `data/*.jsonl` 是事实源。
- `data/templates/*.json` 只是填写模板，不进入 `build_db` 导入流程。
- `evidence_cache.sqlite` 是生成物，不进 Git。
- Markdown 是导出视图，不是主源。

SQLite 数据库由 canonical `data/*.jsonl` 和 `db/sqlite/001_cache.sql` 生成，用于查询、校验和导出。当前 `build_db` 读取 8 个 canonical 主表，加上 `thematic_anchor_objects.jsonl`、`thematic_anchor_events.jsonl`、`thematic_anchor_mechanisms.jsonl` 三个 thematic anchor canonical lane。任何需要长期保留的事实，都应写回 JSONL，而不是只存在 SQLite 中。

未来史源数据平台以 PostgreSQL 为目标主库。SQLite 继续服务当前本地生成库和兼容缓存，不是最终主库，也不承载 `source_documents`、`source_passages`、`evidence_source_links` 或 thematic anchor 关系表的最终实现语义。`db/schema.sql` 与 `db/postgres/001_init.sql` 是 PostgreSQL schema 基线，不再作为 SQLite build 的输入。

未回源材料不得进入正式评分，只能保留为 `search_logs.jsonl` 的待回源线索。当前阶段不写入旧评分、旧排名、旧加总表、旧正式评分记录或旧证据卡。

## 核心表

### sources

记录来源信息，包括 source_id、题名、作者、朝代、卷次、位置、链接和备注。当前 evidence_cards 通过 source_id 引用 sources。长期模型中，这一关系会过渡为 evidence_cards 通过 evidence_source_links 引用 source_passages。

### evidence_cards

记录可验证证据卡。证据卡是后续评分、定档、负证拦截和 Markdown 导出的核心事实单元。

每条 evidence_card 至少包含人物、项目、子项、正负方向、强度、人工层级、来源、短摘、解释、触发词族、触发词、相邻项切分、评分影响和验证状态。

约束规则：

- polarity 只能是 `positive` 或 `negative`。
- strength 只能是 `1`、`2`、`3`、`4`。
- `positive` + `1` 必须对应 `human_level=弱正`。
- `positive` + `2` 必须对应 `human_level=中正`。
- `positive` + `3` 必须对应 `human_level=强正`。
- `positive` + `4` 必须对应 `human_level=极正`。
- `negative` + `1` 必须对应 `human_level=弱负`。
- `negative` + `2` 必须对应 `human_level=中负`。
- `negative` + `3` 必须对应 `human_level=强负`。
- `negative` + `4` 必须对应 `human_level=极负`。

### events

记录事件簇信息，用于支撑事件级拆分、主体归因、行为类型、结果、严重度和时间阶段。强负/极负证据应优先落到可拆分事件。

### trigger_terms

记录正负证触发词。`tier` 分为 `core` 与 `extended`：

- `core`：核心触发词，优先用于矩阵检索。
- `extended`：扩展触发词，用于补充召回和复核。

### search_logs

记录人物 × 正负证触发词矩阵的检索留痕，包括人物、项目、子项、正负方向、触发词族、检索词、结果状态、关联证据卡和备注。

矩阵格状态应能表达：

- `checked_no_hard_evidence`：已查无硬证。
- `evidence_found_card_created`：已查有硬证并转证据卡。
- `lead_needs_source_review`：有线索待回源。
- `routed_to_adjacent_item`：切入相邻项。

`result_status` 非空时只能使用上述限定值。

### thematic anchor lanes

`thematic_anchors` 记录 aggregate 专题锚点。`anchor_objects`、`anchor_events`、`anchor_mechanisms` 分别由 `data/thematic_anchor_objects.jsonl`、`data/thematic_anchor_events.jsonl`、`data/thematic_anchor_mechanisms.jsonl` 导入，用于承载对象、事件、机制三类多粒度 canonical lane。

三张 lane 表保留 `anchor_id`、`item`、`subitem`、`anchor_kind`、`anchor_scope`、`object_type`、`object_name`、`object_level`、`anchor_role`、`usable_for`、`cross_item_risks`、`consensus_level`、`review_status`、`linked_persons`、`source_batch`、`note` 和 `raw_json`。复杂字段继续以 JSON text 保存，`raw_json` 保留完整原始对象。

稳定连接和筛选字段只包括：

- `anchor_id`：lane 内主键，跨 lane 唯一性由 canonical integrity 校验继续守住。
- `item` / `subitem`：可与 `evidence_cards`、`evidence_clusters`、`query_profiles`、`search_logs` 做范围型联表；这种联表只表示同一范围，不表示一条 anchor 直接证明一张证据卡。
- `source_batch`：用于治理和审计追溯，不是业务事实外键。
- `review_status`：用于审核状态筛选，不是事实关系键。

不得把 `object_name`、`object_anchor`、`anchor_role`、`usable_for`、`cross_item_risks`、`linked_persons` 或 `raw_json` 当作稳定 join key。本轮不为三张 lane 表新增指向 `evidence_cards`、`evidence_clusters` 或 `query_profiles` 的外键；未来若需要 `anchor_id -> evidence_id`、`anchor_id -> cluster_id` 或人物关系，应另开扩展 PR 设计 link table。

## 运行库生成

建库脚本会先执行 `db/sqlite/001_cache.sql`，再导入 `data/*.jsonl`。JSONL 文件为空时，也应正常生成空库。

默认运行库文件：

```text
evidence_cache.sqlite
```
