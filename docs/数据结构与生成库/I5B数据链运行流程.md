# I5B retrieval v3 数据链运行流程

## 当前链路

```text
clean/source candidate
-> object source cache
-> claim extraction/cache
-> claim event group
-> rule-neutral material intake
-> claim route
-> candidate review
-> identity gate
-> binding
-> factorization
-> rule scorer
-> item raw signal
-> coverage controller / convergence
```

所有入口均位于 `scripts/dev/retrieval_v3_*.py`。默认数据库为 `EMPEROR_EVAL_RETRIEVAL_V3_DSN`，默认 schema 为 `retrieval_v3`。

## 安全边界

- 默认只读或 rollback dry-run。
- claim import、candidate/binding consumer、factorization apply、event-group apply 和 scorer execute 必须显式开启。
- 未经用户明确授权，不执行 PG 写入、event-group apply 或 scorer `--execute`。
- 不迁移旧表整库数据，不接入已退役控制面，不按裸 `claim_id` 跨数据库补 lineage。
- scorer detail 的 target 皇帝、claim 皇帝和 v3 source pack target 必须一致，否则硬失败。

## 三人验收范围

当前扩展范围只包括刘邦、朱元璋、李世民；其他皇帝必须等三人准确性验收完成后再开启。

## 验证

```text
python -m compileall -q scripts tests
python -m pytest -q
```
