# Wikisource fixture-first parser

本目录只承载 #240 的离线 Wikisource 最小采集试点，不是生产 crawler。

- 本轮只读取本地 `tests/fixtures/wikisource/**` fixture，不访问公网。
- 本轮不连接 PostgreSQL / RabbitMQ，不写 PostgreSQL、JSONL、evidence card、score 或 rank。
- parser 只产出 source snapshot metadata、normalized text、token text、passage records 和稳定 hash，用来验证未来 `doc_revs -> passages` 的解析形状。
- 后续真实采集必须走 `src_hosts` 限速、`doc_revs` 快照、jobs/outbox runtime 和经审查的 adapter；不得把这里的 fixture parser 直接当长期抓取器。
- `zh.wikisource.org` 是 `source_host`，不是 `source_title`；正式 `source_title` 仍应是《史记》《后汉书》等原书名。

已知限制：

- HTML 支持范围刻意很小，只覆盖测试 fixture 中的 `mw-parser-output` 段落、常见导航噪音、编辑链接、脚注和 print footer。
- `token_text` 使用保守的字符级空格分隔策略，不是最终中文古文分词器；#241 benchmark 再决定是否替换。
- normalizer 保留繁体原文，不做简繁转换，只处理多余空白、全角空格和 fixture 覆盖的明显脚注标记。
