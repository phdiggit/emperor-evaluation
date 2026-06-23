# Markdown表格显示约定

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
