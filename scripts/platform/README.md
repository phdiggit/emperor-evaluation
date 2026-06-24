# Runtime skeleton

本目录只定义 PostgreSQL jobs/outbox 与 RabbitMQ 风格投递之间的 runtime skeleton，不连接真实 PostgreSQL / RabbitMQ 服务，也不引入 `pika`、`aio-pika`、`psycopg` 等外部依赖。

- PostgreSQL `jobs` / `outbox` 是任务与投递状态事实源。
- RabbitMQ 后续 adapter 只应传递 `job_id`、`kind`、`schema_ver`、`trace_id` 轻消息字段。
- 投递语义按至少一次投递设计，正确性由 job 状态机和 handler 幂等保证。
- worker 使用 manual ACK 口径，必须在 repository 提交 `succeeded` / `retry_wait` / `dead_lettered` 后 ACK。
- `running` job 的 lease recovery 由后续真实 repository / lease sweeper 处理；skeleton 不直接重跑 `running`。
- DB commit 或 repository 标记失败时，fake runtime 会 `nack(requeue=False)` 并向上抛错，不会 ACK。
- outbox dispatcher 在 fake publisher confirm 成功后才 `mark_outbox_published`；confirm 失败或异常会 `mark_outbox_failed`。
- DLQ、retry、lease 续期和真实 publisher confirms 由后续真实 adapter 落地。
