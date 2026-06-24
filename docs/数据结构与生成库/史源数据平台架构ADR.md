# 史源数据平台架构 ADR

## 1. 状态与结论

Status: Accepted / ADR

Decision: PostgreSQL + RabbitMQ + PostgreSQL FTS 起步；JSONL 短期保留但不继续无限扩张。

本 ADR 只确定目标架构和迁移边界，不实现数据库 schema、队列、worker、抓取器或搜索引擎。当前仓库的 JSONL、SQLite 和 Markdown 导出继续服务试点与验证；未来新增史源全文、段落、检索任务和复核状态时，应向数据平台模型收束，而不是继续扩张平行 JSONL 文件。

#236 是 schema / worker 前的实现设计收口。具体可靠投递、任务状态机、第一版 PostgreSQL 表清单、中文古文检索、史源快照和 JSONL 切库方案见《史源数据平台实现设计.md》。

## 2. 为什么现在要定架构

当前项目以 `data/*.jsonl` 为事实源，`scripts/build/build_db.py` 读取 canonical JSONL 后生成 SQLite，本地导出再服务人工复核与 Markdown 阅读。这套 JSONL + SQLite + Markdown 试点足以支撑早期字段校验、证据卡裁量和小范围导出。

随着项目进入史源数据平台阶段，继续只靠 JSONL 文件会遇到以下问题：

- 300 皇帝池子上限会放大人物、子项和史源范围的组合数量。
- 多子项、多人物、多史源会形成大量交叉引用。
- 一张证据卡可能对应多个史源段落，单一 `source_id` 字段不足以表达完整回源链。
- 史源全文和段落级定位需要独立建模，不能只把短引文塞进证据卡。
- 关键词、人物、子项、史源范围和证据状态需要复合检索。
- 检索、抓取、解析、索引、候选召回和复核不能继续按人物串行推进。

因此本阶段先定目标架构：用 PostgreSQL 承载可审计事实链和强关系模型，用 RabbitMQ 承载并发任务调度，用 PostgreSQL FTS 提供起步搜索能力，再按进入条件接入增强搜索层。

## 3. 核心需求

- 可审计事实链：从检索画像、搜索任务、抓取记录、史源段落、证据卡、证据组到裁判结论都能追溯。
- 史源全文和段落定位：保留 source document、passage、位置、版本和回源状态。
- 多对多引用关系：一张证据卡可引用多个史源段落，一个史源段落也可支撑多个候选或证据卡。
- 并发抓取、解析、索引、候选召回：任务拆成可重试、可限速、可去重的 job。
- 人工复核与数据质量状态：候选、草稿、退回、已回源、已裁判等状态进入结构化模型。
- 本地 Codex / VSCode 工作流：仍支持小样本 fixture、导入导出和本地生成库，不要求开发者安装全套服务才能阅读文档或跑轻量测试。
- 不把配置层重新膨胀：`project_config.yml` 只保留人工运行入口。
- 不让 JSONL 文件数量随人物或子项线性爆炸，尤其禁止形成“每个皇帝一个 JSONL”“每个子项一个 JSONL”“每个皇帝 x 子项一个 JSONL”的扩张模式。

## 4. 目标数据模型

本 ADR 只描述目标表方向，不定义 schema。第一版 schema 草案以《史源数据平台实现设计.md》为准。

目标模型至少包含：

- `persons`
- `person_aliases`
- `subitems`
- `src_hosts`
- `src_docs`
- `doc_revs`
- `passages`
- `passage_people`
- `query_profiles`
- `search_tasks`
- `search_hits`
- `cand_matches`
- `evd_cards`
- `evd_src_links`
- `clusters`
- `cluster_evd`
- `review_items`
- `jobs`
- `job_runs`
- `job_deps`
- `outbox`
- `imports`
- `import_rows`

关键关系：

- `src_host -> src_doc -> doc_rev -> passage`：一份逻辑史源文档可有多次不可变抓取快照，段落引用 `doc_rev_id`。
- `passage <-> evd_card`：通过 `evd_src_links` 表达多对多引用。证据卡不再被单个 `source_id` 限死。
- `query_profile -> search_task -> search_hits -> fetch job -> doc_rev`：检索画像生成具体任务，搜索命中保存候选 URL 和拒绝状态，再进入抓取任务。
- `jobs -> job_runs / job_deps / outbox`：统一任务表承载 search、fetch、parse、match、draft、review_notify 等执行类型，不再拆成多张阶段 job 表。
- `candidate_match -> evidence draft / search_log / review queue`：候选命中先进入草稿、检索留痕或人工复核队列，不直接写成正式证据。

`evd_cards`、`clusters`、后续 `adjudications` 和后续 `score_records` 之间必须保留明确边界。证据卡记录原子材料，证据组记录多证据裁量，裁判决策记录人工或规则裁判，评分记录只在正式定档流程中产生。第一版暂不实现最终评分表。

## 5. 并发采集工作流

未来工作流不能按人物串行。RabbitMQ 承载任务队列，不同 worker 可并发消费 search、fetch、parse、match、draft、review_notify 等任务，避免单人单子项长链条阻塞整个批次。

PostgreSQL 记录任务状态、幂等键、`attempt_count`、`max_attempts`、`next_run_at`、`locked_by`、`locked_at`、`lease_until`、`job_runs`、`job_deps` 和 `outbox`。队列只负责调度与投递，canonical 状态不放在 RabbitMQ 里。

任务粒度建议为：

```text
person + subitem + search_mode + source_scope + query_terms/source_hint
```

实现设计已经覆盖：

- 失败重试和最大尝试次数。
- dead-letter queue 和人工介入入口。
- 站点、史源或供应方级限速。
- query、URL、source document 和 passage 的去重。
- 回源状态、解析状态、索引状态和复核状态的持久化。
- manual ACK、publisher confirms、outbox 和 worker 幂等。

## 6. 搜索索引层

起步阶段使用 PostgreSQL FTS / JSONB / pg_trgm 等能力，提供本地和服务端初期检索能力。中文古文无空格，不能笼统假定默认 FTS 足够；第一阶段应采用 PostgreSQL 元数据过滤、应用侧中文/古文规范化与分词、GIN `tsvector`、`pg_trgm` 辅助模糊匹配的组合，并对单字、两字词、异体、繁简转换和人物别名做 benchmark。

增强阶段可以接入 Redis Search 或 OpenSearch。增强搜索层只承担热索引、召回加速、多字段搜索体验和复杂查询性能优化，不替代 PostgreSQL 的 canonical 事实源。

MongoDB / Atlas Search 文档搜索体验强，适合作为备选方案继续观察。但当前项目的核心约束是证据链强关系、版本审计、外键和事务，因此 MongoDB 不作为第一主库。

Redis 不是 canonical 事实源。Redis 可作为缓存、热索引、任务去重辅助或搜索加速候选，但不得承载唯一事实链。

SQLite FTS5 可作为本地原型或生成索引，适合 Codex / VSCode 工作流中的轻量离线验证，但不作为最终主库。

## 7. JSONL / SQLite / PostgreSQL 边界

当前 JSONL 继续保留，短期仍作为事实源、导入来源、小样本 fixture 和 PR 审阅载体。现有 `data/*.jsonl`、`data/*_batches/*.jsonl` 和主表字段规范不在本 ADR 中迁移或删除。

SQLite 继续作为当前本地生成库和兼容缓存。`scripts/build/build_db.py` 仍可从 JSONL 生成 `evidence_cache.sqlite`，用于本地查询、校验和导出。

PostgreSQL 是目标主库。未来进入数据平台原型时，应优先按目标模型设计导入、引用、任务和审计结构，不设计“JSONL -> SQLite -> MongoDB”的多次搬家路线。

未来切库必须走单向阶段：JSONL 唯一写源、导入 PostgreSQL staging 反复验证、冻结 JSONL 写入、全量导入并校验行数 / ID / 引用 / hash、PostgreSQL 成为唯一写源、JSONL 只作导出快照 / 小 fixture / 历史审计。本 ADR 不改动 `data/*.jsonl`，不迁移 batch，不删除过渡文件，也不改变当前生成链路。

## 8. 配置边界

沿用 #227 后的新口径：`project_config.yml` 只控制 active subitem、groups、defaults。短名单可直接写 `persons`，长清单用 `persons_ref` 或后续 `*_ref` 外置。

以下内容不回到人工配置层：

- 候选池。
- 检索关键词和 query terms。
- 抓取任务、解析任务、索引任务和候选召回任务。
- 检索日志、回源状态和 `source_passage`。
- 展示字段、表格列、warning 文案。

这些内容应进入数据平台模型、生成逻辑、视图配置或专门规则文档。配置层只保留人工选择当前要跑什么，不承载系统运行状态和大量业务数据。

## 9. 技术选型矩阵

| 技术 | 定位 | 优点 | 不作为当前主方案的原因或进入条件 |
| --- | --- | --- | --- |
| PostgreSQL | 目标主库 | 强关系、事务、外键、唯一约束、JSONB、FTS、审计链清晰 | 当前即作为主库优先方向；第一阶段先做 ADR 和最小原型，不在本 PR 实现 |
| MongoDB / Atlas Search | 文档库与搜索备选 | 文档模型自然，Atlas Search 体验强 | 不作为第一主库；只有当文档搜索体验压过强关系和事务需求时再评估 |
| SQLite FTS5 | 本地原型和生成索引 | 零服务依赖，适合小样本、本地 Codex / VSCode 工作流 | 不适合长期并发任务、多人协作和平台级主库 |
| Redis / Redis Search | 缓存、热索引、搜索加速候选 | 快速召回、热数据访问、可辅助去重和限速 | Redis 不做 canonical 事实源；进入条件是 PostgreSQL FTS 不足以支撑搜索性能或体验 |
| RabbitMQ | 第一阶段并发任务队列 | 成熟队列语义，适合 worker 调度、重试、dead-letter 和任务隔离 | 当前作为队列优先方向；本 PR 不安装、不启动、不新增 worker |
| Redis Streams | 轻量队列备选 | 部署简单，可复用 Redis 生态 | 不作为第一队列方案；仅在任务规模较轻、队列语义简单时评估 |
| Kafka | 大规模事件流备选 | 高吞吐、多订阅者、可回放事件流 | 第一阶段暂不引入；只有出现大规模事件流、多订阅者回放或跨系统同步需求时再进入 |

## 10. 后续 PR 序列

本 ADR 和 #236 实现设计收口之后建议按以下顺序推进：

```text
#237 PostgreSQL 基础 schema
#238 RabbitMQ worker skeleton + outbox dispatcher
#239 Wikisource 最小采集试点
#240 JSONL 导入 dry-run
#241 中文古文检索 benchmark
```

其中 #237 先落实表结构和连接键，#238 再落实 worker skeleton 与可靠投递，#239 才进入最小采集试点，#240 只做导入 dry-run，#241 用 benchmark 决定是否需要 OpenSearch。

## 严格非目标

本 ADR 明确不做以下事项：

- 不实现 PostgreSQL schema。
- 不新增 Docker Compose。
- 不安装或启动 PostgreSQL / RabbitMQ / Redis / MongoDB。
- 不修改 `db/schema.sql`。
- 不修改 `data/*.jsonl`。
- 不迁移或删除 batch JSONL。
- 不新增 search worker 代码。
- 不新增抓取器代码。
- 不修改评分标准。
- 不修改 `docs/分项规则/**`。
- 不修改 `exports/markdown_views/**`。
- 不生成正式分数、排名、总榜。
