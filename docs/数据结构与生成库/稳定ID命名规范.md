# ID命名规范

稳定 ID 用于连接来源、证据卡、事件、触发词和检索留痕。ID 使用 ASCII；正文中的 `person` 字段仍保留中文姓名。

## ID 规则

- `source_id`：`SRC-来源缩写-卷或篇-序号`
  - 例：`SRC-HHS-MINGDIJI-001`
- `source_document_id`：`SDOC-来源缩写-版本或卷篇-序号`
  - 例：`SDOC-HHS-MINGDIJI-V1-001`
- `passage_id`：`SPG-来源缩写-卷或篇-段落序号`
  - 例：`SPG-HHS-MINGDIJI-0001`
- `evidence_id`：`EVD-子项代码-人物拼音或代号-正负-序号`
  - 例：`EVD-I5B-LIUZHUANG-NEG-001`
- `event_id`：`EVT-子项代码-人物拼音或代号-事件代号-序号`
  - 例：`EVT-I5B-LIUZHUANG-TINGZHANG-001`
- `trigger term_id`：`TRG-子项代码-正负-词族代号-序号`
  - 例：`TRG-I5B-NEG-TINGZHANG-001`
- `search_id`：`SRCH-子项代码-人物拼音或代号-正负-词族代号-序号`
  - 例：`SRCH-I5B-LIUXIU-NEG-RONGJIAN-001`

## 说明

- 子项代码示例：第五项B = `I5B`。
- ID 一旦进入事实源，不因后续评分变化而改名。
- 序号只用于去重，不表达强弱或排名。
