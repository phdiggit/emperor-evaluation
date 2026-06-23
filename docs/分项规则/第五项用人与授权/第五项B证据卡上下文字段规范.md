# 第五项B证据卡上下文机制

本文档定义第五项B证据卡的上下文持久化机制。该机制只服务人工审核、回源复核和可追溯展示，不改变数据事实，不自动改变评分，不自动改变证据强度，也不自动改变证据簇裁判结论。

## 1. 字段含义

`quote_short` 是史料短摘，只用于快速识别证据内容，不等于完整原始史料上下文。遇到一句话说不清、必须结合前后文才能定证的材料，应使用以下上下文字段补充记录：

| 字段 | 含义 |
| --- | --- |
| `quote_context` | 必要上下文原文或较长摘录，可比 `quote_short` 更长。 |
| `context_summary` | 上下文摘要，用白话说明前因后果。 |
| `context_scope` | 上下文范围，例如同段前后两句、本传同一事件段、诏令全文摘要、同一案件前后段。 |
| `context_required` | 是否必须阅读上下文才能定证，布尔值。 |
| `context_status` | 上下文状态，可用 `missing`、`pending`、`supplied`、`source_verified`。 |
| `context_effect` | 上下文对定证的影响，可用 `strengthen`、`limit`、`reverse`、`split_only`、`neutral`。 |
| `source_locator` | 更精确来源定位，可细到卷、篇、传、段落、条目、页码或电子文本锚点。 |
| `adjudication_bridge` | 裁判桥接说明，解释上下文为何支持当前 `evidence_role`、`scoring_effect` 或 `cross_item_split`。 |

## 2. 必须标记上下文的情形

以下情况必须标记 `context_required = true`：

1. 短摘含代词、转折、追述、评价语。
2. 涉及前后事件因果。
3. 涉及人物身份转换。
4. 涉及后效能否回填。
5. 涉及政权安全、司法残酷、战功、治绩、盛世光环等相邻项剥离。
6. 单句无法判断是正证、负证、中性背景还是反证。
7. 一句话可能被误读，需要前后文限定。

## 3. 补字段规则

若 `context_required = true`，原则上必须补齐：

1. `quote_context`
2. `context_summary`
3. `context_scope`
4. `context_effect`
5. `adjudication_bridge`

若上下文暂未补齐，应标记 `context_status = missing` 或 `context_status = pending`。该证据不得直接进入稳定裁判，只能进入“需回源 / 需上下文”队列，等待人工回看原始材料。

若 `context_status = supplied` 或 `context_status = source_verified`，必须能从 `quote_context`、`context_summary`、`context_scope`、`context_effect` 与 `adjudication_bridge` 复原从史料上下文到第五项B裁判标签之间的判断路径。

## 4. 展示与校验

第五项B Markdown 展示字典必须提供上下文字段中文标签和值标签。净证据池、证据卡索引等证据链视图在证据卡含上下文字段时应展示这些字段；字段缺失时不得报错。

`quote_context`、`context_summary`、`adjudication_bridge` 属于长上下文字段，应进入可定位附录链接，表格内不得直接塞入长上下文。附录必须全量展示原字段，不使用 HTML details，不使用 `……（共N项）` 截断。

validator 只校验已声明 `context_required = true` 的证据卡，不要求历史证据卡立即全部补上下文。

## 5. 裁判边界

上下文机制不得直接用于自动升档或降档。`quote_context` 不是评分自动规则输入，只服务人工审核和可追溯性。

当 `context_effect = reverse` 时，应回看证据方向、证据强度和裁判桥接说明。当 `context_effect = split_only` 时，该材料只能用于相邻项剥离，不得直接回填第五项B正负分。
