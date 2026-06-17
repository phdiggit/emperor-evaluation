# 第五项B三人试点矩阵说明

试点人物：李世民、刘秀、刘庄。

本任务只生成矩阵骨架，不代表完成检索。矩阵骨架不写入 `search_logs`；只有实际检索后才写入 `search_logs`。

矩阵骨架的作用是列出每个人需要检索的正负证词族、`core` 词、`extended` 词。

后续实际检索时，每个矩阵格必须落为：

- `checked_no_hard_evidence`
- `evidence_found_card_created`
- `lead_needs_source_review`
- `routed_to_adjacent_item`

## 三人选择原因

- 李世民：高位正证样本，用于检验极正与中负拦截并存。
- 刘秀：旧体系高位被强负证重新打开的样本，用于检验负证召回。
- 刘庄：旧体系正证漏检与负证强拦截并存的样本，用于检验正负双向检索。
