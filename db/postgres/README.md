# PostgreSQL 基础 schema 契约

`001_init.sql` 是皇帝综合评价体系后续 PostgreSQL 目标主库的第一版 schema 契约。它用于固定采集、史源版本、段落、候选匹配、证据链、任务、outbox 和导入审计的基础表结构，供后续 worker skeleton、导入 dry-run 和采集试点继续对齐。

当前状态：

- 不接生产服务。
- 不替代 JSONL 写源。
- 不改变现有 JSONL -> SQLite -> Markdown 流程。
- 不要求 CI 或本地开发环境安装 PostgreSQL。
- 不包含 migration runner、Docker Compose、RabbitMQ worker 或 outbox dispatcher。

第一版 schema 只覆盖采集与证据链，不实现最终评分表、裁判发布表、外部搜索索引表、RabbitMQ queue / exchange 配置，也不复制 SQLite thematic anchor 的三张同构表。真实连接、迁移执行器、Docker Compose、worker、outbox dispatcher 和 JSONL 切库逻辑都留给后续 PR。
