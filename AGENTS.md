# AGENTS.md

本仓库是“皇帝综合评价体系”工作区。执行任何任务时，优先遵守 Issue / PR 中的变更白名单与禁止事项。

## 执行优先级

1. Issue / PR 白名单与禁止事项
2. 本 `AGENTS.md`
3. 当前会话里已确认可用的仓库规则与约定
4. 其他默认习惯或工具偏好

如果上层规则和下层偏好冲突，以更高优先级为准。

## 执行偏好

1. 能用仓库内现成事实和本地命令判断的，先判断再行动，不先泛问。
2. 任务范围已经明确时，优先一次做完白名单内的全部必要步骤，避免碎片化来回确认。
3. 只有在范围、风险或外部状态会明显影响结果时，才暂停向用户确认。
4. 只读诊断任务保持只读；需要改文件时，先确认最小改动路径，再动手。
5. 不把“默认偏好”当成“必须执行”，也不把“可选优化”当成“必须等用户确认”。

## 硬规则

1. 先读 Issue / PR 说明，确认允许修改的文件白名单；不要全仓库盲扫。
2. 修改前后都运行 `git diff --name-only`，白名单外文件必须还原。
3. PR 说明必须粘贴最终 changed files 列表。
4. 开 PR 后默认直接置为 ready for review；除非 Issue 明确要求 draft，否则不要保持 draft。
5. 收到“返修 / 按审查意见修改 / fix review”时，必须先 checkout/fetch PR head 分支，并读取 PR 评论和 review threads；不得在 base 分支重建文件或只改 PR 状态/PR body。
6. 返修后必须确认 local HEAD 与 PR head SHA 一致，并在回复或 PR 说明中写明。
7. 涉及 GitHub 远端操作时，优先使用已认证的 `gh` CLI（如读 Issue/PR、读评论、查 PR 状态、创建/更新 PR、回复评论、查看 checks）；只有在 `gh` 不可用、未认证、权限不足或明确无法完成该动作时，才退回 GitHub connector，并在回复或 PR 说明中写明退回原因。退回前先确认是不是只需要重新认证，而不是换工具。
8. 在 Windows 工作区中，仓库内常规命令默认优先使用 Git Bash（`D:\Git\bin\bash.exe`），尤其是 `git`、`gh`、`python`、`pytest`、`grep/find`、命令串联、重定向和管道操作。只有在需要 PowerShell 专属能力（如 `.ps1`、Windows 权限/环境处理、PowerShell 对象管道）时才使用 PowerShell。若当前已经在 PowerShell 环境，就直接用 PowerShell 等价语法，不要为了切 shell 绕路；若已在 Git Bash，就保持 Git Bash。
9. `exports/markdown_views/` 是导出视图层，不是事实源；除非 Issue 明确要求，不得批量重写旧导出。
10. `data/*_batches/` 是过渡批次层；确认唯一数据源前不得删除。
11. 文件清理、归档、删除候选第一轮只写诊断或候选清单，不直接删改。
12. 大脚本治理必须小步重构并有测试锁定；不要在业务 PR 中顺手拆脚本。
13. 读写仓库文本文件时，优先使用 `python scripts/dev/repo_tool.py read/write/replace ...`；这条优先级主要针对仓库内文本修改和需要保持编码稳定的场景，不是所有只读检索都必须走它。检索中文史料时可以先用 `rg` / `sed` / `git grep` 找位置和上下文，真正读准内容或要改写中文文本时再优先切到 `repo_tool`。不要裸用 `Get-Content` / `Set-Content` 读写中文或可能含中文的文本文件。
14. 涉及 `data/`、`scripts/`、`tests/`、`.github/workflows/` 或 validation 入口的 PR，开 PR 前必须运行 `python scripts/validate_all.py`；若校验失败，不得提交或开 PR。纯文档改动且不影响验证链时可不运行。

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
