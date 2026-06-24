# Wikisource fixture-first parser

本目录只承载 #240 的离线 Wikisource 最小采集试点、#241 的离线中文古文检索 benchmark，以及 #242 的可选 PostgreSQL 搜索实测 benchmark，不是生产 crawler。

- 本轮只读取本地 `tests/fixtures/wikisource/**` fixture，不访问公网。
- #241 benchmark 只读取本地 `tests/fixtures/source_search/**` fixture，并在内存中评估 query 召回。
- #242 PostgreSQL benchmark 只读取本地 fixture 并通过 `PG_SEARCH_BENCH_DSN` opt-in 连接本地 PostgreSQL；默认测试不要求 PostgreSQL / psql。
- 默认流程不连接 PostgreSQL / RabbitMQ，不写 PostgreSQL、JSONL、evidence card、score 或 rank；#242 只在显式设置 `PG_SEARCH_BENCH_DSN` 时连接本地 PostgreSQL。
- parser 只产出 source snapshot metadata、normalized text、token text、passage records 和稳定 hash，用来验证未来 `doc_revs -> passages` 的解析形状。
- 后续真实采集必须走 `src_hosts` 限速、`doc_revs` 快照、jobs/outbox runtime 和经审查的 adapter；不得把这里的 fixture parser 直接当长期抓取器。
- `zh.wikisource.org` 是 `source_host`，不是 `source_title`；正式 `source_title` 仍应是《史记》《后汉书》等原书名。

已知限制：

- HTML 支持范围刻意很小，只覆盖测试 fixture 中的 `mw-parser-output` 段落、常见导航噪音、编辑链接、脚注和 print footer。
- parser 默认 `token_text` 仍使用保守的字符级空格分隔策略，不是最终中文古文分词器。
- #241 的 `search_benchmark.py` 额外验证字符、2-3 gram、繁简/异体 query 规范化和 alias expansion；它是 benchmark 口径，不替代生产分词器或 PostgreSQL / pg_trgm 实测。
- #242 的 `postgres_search_benchmark.py` 只比较 PostgreSQL `tsvector`、`LIKE` 和 `pg_trgm` 在小 fixture 上的行为；结果只用于下一步调优判断，不等同生产检索质量结论。
- normalizer 保留繁体原文，不做简繁转换，只处理多余空白、全角空格和 fixture 覆盖的明显脚注标记。
