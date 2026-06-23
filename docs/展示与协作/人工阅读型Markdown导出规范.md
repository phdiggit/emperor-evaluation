# 人工阅读型 Markdown 导出规范

本文档固定人工复核型 Markdown 导出的展示规则。它只约束阅读组织和字段呈现，不改变事实源、评分、定档、排名、warning 语义或裁判结论。

## 适用范围

- 适用于面向人工复核、人工裁判、试点草案、规则敏感点核对的 Markdown 导出。
- 典型对象包括 I5B 自动结算草案、按人物详情页、warning display-only 展示段和证据簇阅读稿。
- 只讨论导出视图的可读性，不把 Markdown 当作事实源。

## 事实与结论边界

- 展示优化不得改写 `data/**` 中的源数据。
- 展示优化不得改变评分、定档、排名、leaderboard、warning 匹配语义或证据簇裁判结论。
- 只允许调整标题、分节、索引、链接、字段名、字段展开方式和人工阅读顺序。
- 若展示内容与源数据或裁判逻辑冲突，以源数据和裁判逻辑为准。

## Markdown 形态

- 人工复核型 Markdown 默认使用纯 Markdown。
- 不使用 `<details>`、`<summary>`、`</details>` 等 HTML 折叠视图。
- 不依赖 Typora 对 HTML 与 Markdown 列表混排的兼容行为。
- 字段名应使用中文，并用加粗格式展示，例如 `**对象锚点**`。
- 详情页可以使用分节、短列表、编号列表和短表格，但不应把长字段塞进宽表。

## 表格使用边界

- 索引页允许使用短表格，因为它只承载人物、摘要、数量和详情页链接。
- 详情页不要使用宽表承载长字段、裁判说明、相邻项剥离说明、warning `matched_fields` 或 linked evidence 长字段。
- 证据簇明细、相邻项剥离说明、warning 命中字段等应使用卡片式段落、项目符号或编号列表。
- 不应恢复 `| cluster_id | polarity | cluster_type | ... |` 这类承载长字段的宽表布局。

## 字段完整性

- `linked_*` 字段必须全量展示，不得隐藏。
- `cross_item_split_signals / 相邻项剥离说明` 必须全量展示，不得隐藏。
- warning `matched_fields / 命中字段` 必须全量展示，不得截断。
- 不使用 `……（共N项）` 或类似文案截断长列表。
- 如果字段为空，应明确展示为空或“无”，不要通过省略制造歧义。

## Warning 展示

- warning 主标签应中文化，例如“回源核验提示”“单证不足提示”。
- warning 展示只服务人工复核，不得引入分数、排名、最终定档、leaderboard 或正式结论字段。
- `matched_fields` 使用中文字段名“命中字段”展示，但字段路径本身保留机器可追踪形式，例如 `linked_cards[0].scoring_effect`。
- `matched_fields` 列表按原匹配结果全量编号展示，不做去尾、不折叠、不摘要。

## 索引页与详情页

- 当人工复核稿过长时，优先使用“索引页 + 按人物详情页”的纯 Markdown 结构。
- 索引页应包含文档说明、人物列表、自动特征摘要、证据簇数量、人工复核提示数量和详情页链接。
- 详情页继续全量展示单个人物的自动特征、证据簇、linked 字段、相邻项剥离说明和 warning 命中字段。
- 相对链接应能在 Typora 中打开，例如 `[李世民详情](./第五项B自动结算草案_李世民.md)`。

## 验收检查

- 生成文件不含 `<details>`、`<summary>`、`</details>`。
- 生成文件不含 `……（共`。
- 详情页保留中文加粗字段名。
- 详情页完整展示 `linked_*`、`cross_item_split_signals / 相邻项剥离说明` 和 warning `matched_fields / 命中字段`。
- 索引页链接能跳转到对应详情页。

## 表格显示约定

以下内容由原 `Markdown表格显示约定.md` 并入，独立展示规范文档不再保留。

本文只说明人工阅读型 Markdown 表格的显示边界，不改变任何导出数据、裁判逻辑、评分、warning 语义或排名。

## 基本原则

1. Markdown pipe table 的渲染换行主要由阅读器/CSS 控制。
2. 导出层负责控制字段数量、字段顺序和长字段附录化。
3. 项目不通过在单元格内插入 `<br>` 强行控制换行。
4. 人工审核主表应保持短字段；长字段进入正文或附录链接。
5. Typora、GitHub、VS Code 对表格换行支持不同，不把具体阅读器样式写死进导出内容。

## 导出层职责

人工审核主表应优先使用 `view_profiles.human_review.table_fields` 控制字段白名单和字段顺序。需要保留长摘录、上下文、裁判桥接、相邻项剥离说明等长字段时，导出层应通过附录化或正文分段保留全量内容，而不是扩宽主表。

机器审计视图可以保留追踪字段；人工审核主表默认不混入机器审计字段。若人工审核确实需要展示证据或来源定位，应使用“证据编号”“来源编号”等中文业务表头。

## CSS参考

允许在阅读器或站点样式中参考以下换行策略，但这些样式不参与导出逻辑：

```css
.markdown-body table td,
.markdown-body table th {
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}
```

也可以选择不换行并横向滚动：

```css
.markdown-body table {
  display: block;
  overflow-x: auto;
  white-space: nowrap;
}
```
