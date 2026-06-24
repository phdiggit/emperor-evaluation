# PostgreSQL 基础 schema 契约

`001_init.sql` 是皇帝综合评价体系后续 PostgreSQL 目标主库的第一版 schema 契约。它用于固定采集、史源版本、段落、候选匹配、证据链、任务、outbox 和导入审计的基础表结构，供后续 worker skeleton、导入 dry-run 和采集试点继续对齐。

当前状态：

- 不接生产服务。
- 不替代 JSONL 写源。
- 不改变现有 JSONL -> SQLite -> Markdown 流程。
- 不要求 CI 或本地开发环境安装 PostgreSQL。
- 不包含 migration runner、Docker Compose、RabbitMQ worker 或 outbox dispatcher。

第一版 schema 只覆盖采集与证据链，不实现最终评分表、裁判发布表、外部搜索索引表、RabbitMQ queue / exchange 配置，也不复制 SQLite thematic anchor 的三张同构表。真实连接、迁移执行器、Docker Compose、worker、outbox dispatcher 和 JSONL 切库逻辑都留给后续 PR。

## 本地 bootstrap 检查

`scripts/platform/postgres_bootstrap.py` 只用于本地开发库 opt-in 检查 `001_init.sql` 是否能在隔离 schema 中执行。默认 `--check` 只报告 DSN 与 Python PostgreSQL driver 是否可用，不连接数据库、不执行 DDL；`--sql-only` 只输出包装后的 SQL。

需要真实 apply 时，在本地 `.env` 或 shell 中设置 `EMPEROR_EVAL_PG_DSN`，也兼容旧的 `PG_SEARCH_BENCH_DSN`：

```bash
python scripts/platform/postgres_bootstrap.py --check
python scripts/platform/postgres_bootstrap.py --sql-only
python scripts/platform/postgres_bootstrap.py --apply --schema emperor_eval_bootstrap_check --drop-schema-after
```

`--apply` 会先创建指定 schema，并将 `search_path` 设为该 schema 与 `public` 后再执行 `001_init.sql`。清理只删除临时 schema，不会提交 `.env`、迁移 JSONL、连接 RabbitMQ，或写入 worker/crawler/parser。

## JSONL 导入 dry-run

`scripts/platform/jsonl_import_dry_run.py` 用于 opt-in 验证当前 canonical JSONL 主表是否可以被逐行解析、映射并写入导入审计表。它不迁移 JSONL，不切换写源，不写业务事实表，也不把结果写入 Markdown exports。

默认和 contract report 都不会连接数据库：

```bash
python scripts/platform/jsonl_import_dry_run.py --check
python scripts/platform/jsonl_import_dry_run.py --contract-report
```

需要真实写入本地 PostgreSQL 审计表时，只使用本地 shell 或 `.env` 中的 `EMPEROR_EVAL_PG_DSN`，不使用旧 search benchmark DSN，也不依赖 `psql`：

```bash
python scripts/platform/jsonl_import_dry_run.py --apply --schema emperor_eval_import_dry_run --drop-schema-after
```

`--apply` 会在隔离 schema 中执行 `001_init.sql`，然后只写入 `imports` 和 `import_rows`。使用 `--drop-schema-after` 时，命令结束前会 `DROP SCHEMA CASCADE` 清理该隔离 schema。
