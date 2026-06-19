# AGENTS.md

本仓库是“皇帝综合评价体系”工作区。执行任何任务时，优先遵守 Issue / PR 中的变更白名单与禁止事项。

## 硬规则

1. 先读 Issue / PR 说明，确认允许修改的文件白名单；不要全仓库盲扫。
2. 修改前后都运行 `git diff --name-only`，白名单外文件必须还原。
3. PR 说明必须粘贴最终 changed files 列表。
4. 开 PR 后默认直接置为 ready for review；除非 Issue 明确要求 draft，否则不要保持 draft。
5. 收到“返修 / 按审查意见修改 / fix review”时，必须先 checkout/fetch PR head 分支，并读取 PR 评论和 review threads；不得在 base 分支重建文件或只改 PR 状态/PR body。
6. 返修后必须确认 local HEAD 与 PR head SHA 一致，并在回复或 PR 说明中写明。
7. `exports/markdown_views/` 是导出视图层，不是事实源；除非 Issue 明确要求，不得批量重写旧导出。
8. `data/*_batches/` 是过渡批次层；确认唯一数据源前不得删除。
9.  文件清理、归档、删除候选第一轮只写诊断或候选清单，不直接删改。
10. 大脚本治理必须小步重构并有测试锁定；不要在业务 PR 中顺手拆脚本。
11. 读写仓库文本文件时，优先使用 `python scripts/dev/repo_tool.py read/write/replace ...`；不要裸用 `Get-Content` / `Set-Content` 读写中文或可能含中文的文本文件。

## 默认忽略

除非 Issue 明确要求，不要主动读取、总结或改写：

```text
exports/
logs/
tmp/
.cache/
.codex/
```

## 默认禁止

- 修改旧索引、旧三人视图、旧净证据池、旧定档表，除非列入白名单。
- 把补证、readiness、human review package 自动升级为正式结论。
- 把军功、政权安全、财政绩效、司法严酷等相邻项内容直接回填到当前子项。
