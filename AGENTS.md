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
6. 涉及 GitHub 远端读写时，遵循“最小工具调用原则”：能用一次 `gh` 命令完成的，不拆成多次 connector/API 调用；已确认的 PR / issue 状态不重复确认，除非后续操作依赖最新状态或用户明确要求复核。

## 硬规则

执行时按下面顺序过脑：先看边界，再看 GitHub，再看 shell/编码，再看改动方法，最后看验证与提交。

### 任务边界

1. 先读 Issue / PR 说明，确认允许修改的文件白名单；不要全仓库盲扫。
2. 修改前后都运行 `git diff --name-only`，白名单外文件必须还原。
3. `exports/markdown_views/` 是导出视图层，不是事实源；除非 Issue 明确要求，不得批量重写旧导出。
4. `data/*_batches/` 是过渡批次层；确认唯一数据源前不得删除。
5. 文件清理、归档、删除候选第一轮只写诊断或候选清单，不直接删改。

### GitHub 操作

1. 涉及 GitHub 远端操作时，默认优先使用已认证的 `gh` CLI 完成读写（如读 Issue/PR、读评论、查 checks、创建/更新 PR、回复评论、merge、close issue）。只有在 `gh` 不可用、未认证、权限不足或明确无法完成该动作时，才退回 GitHub connector，并在回复或 PR 说明中写明退回原因。退回前先确认是不是只需要重新认证，而不是换工具。
2. GitHub 写操作（如 merge PR、close issue、更新 PR/issue、回复评论）默认按“先判断、后执行”处理：先用最少必要的读取确认目标动作，再执行一次写操作；不要为同一目标反复调用不同接口，也不要把 PR 更新接口和 issue 更新接口混用。
3. 收到“返修 / 按审查意见修改 / fix review”时，必须先 checkout/fetch PR head 分支，并读取 PR 评论和 review threads；不得在 base 分支重建文件或只改 PR 状态/PR body。
4. 返修后必须确认 local HEAD 与 PR head SHA 一致，并在回复或 PR 说明中写明。
5. PR 说明必须粘贴最终 changed files 列表。
6. 开 PR 后默认直接置为 ready for review；除非 Issue 明确要求 draft，否则不要保持 draft。

### Shell、路径与编码

1. 在 Windows 工作区中，仓库内常规命令默认优先使用 Git Bash（`D:\Git\bin\bash.exe`），尤其是 `git`、`gh`、`python`、`pytest`、`grep/find`、命令串联、重定向和管道操作。只有在需要 PowerShell 专属能力（如 `.ps1`、Windows 权限/环境处理、PowerShell 对象管道）时才使用 PowerShell。若当前已经在 PowerShell 环境，就直接用 PowerShell 等价语法，不要为了切 shell 绕路；若已在 Git Bash，就保持 Git Bash。
2. 在 PowerShell + Git Bash 混合环境里，不要写复杂嵌套引号命令，尤其不要为了多关键词检索去拼多段 `grep`、`printf`、转义换行或 shell 串联。多关键词搜索默认优先用一次 `rg -n "A|B|C" <paths>` 或等价的单条简单命令完成。
3. 处理中文路径、`git status`、`changed files`、白名单核对时，默认优先使用 `git -c core.quotepath=false status --short`、`git -c core.quotepath=false diff --name-only` 或仓库内 `python scripts/dev/repo_tool.py` 的现成能力；不要为了解码 Git quoted path 临时手写 Python / shell 转码脚本，除非先确认仓库内工具无法满足。
4. 读写仓库文本文件时，优先使用 `python scripts/dev/repo_tool.py read/write/replace ...`；这条优先级主要针对仓库内文本修改和需要保持编码稳定的场景，不是所有只读检索都必须走它。检索中文史料时可以先用 `rg` / `sed` / `git grep` 找位置和上下文，真正读准内容或要改写中文文本时再优先切到 `repo_tool`。不要裸用 `Get-Content` / `Set-Content` 读写中文或可能含中文的文本文件。
5. 结构化改写仓库内 JSON / JSONL 配置时，优先使用 Python 标准库或 `scripts/dev/repo_tool.py`；涉及中文 JSON 输出时必须使用 UTF-8、`ensure_ascii=False`、稳定缩进。不要使用临时 MCP / REPL 工具改写仓库文件。
6. 生成 PR body、临时 Markdown、说明文件时，默认使用 UTF-8 无 BOM；如果经 PowerShell 写入，必须显式指定 no BOM，避免正文开头混入 BOM 字符。

### 改动方法

1. 大范围改脚本前，先用 `rg` / `git grep` 精确定位旧常量、旧读取点、目标函数，再按文件做小补丁；不要先打一整块大 patch，失败后再回头逐段修上下文。
2. 大脚本治理必须小步重构并有测试锁定；不要在业务 PR 中顺手拆脚本。

### 验证与提交

1. 涉及 `data/`、`scripts/`、`tests/`、`.github/workflows/` 或 validation 入口的 PR，开 PR 前必须运行 `python scripts/validate_all.py`；若校验失败，不得提交或开 PR。纯文档改动且不影响验证链时可不运行。
2. 若验证命令会重写 `exports/`、generated docs 或其他禁止范围内副产物，先记录验证结果，再清理这些副产物；清理后只做 `git status` / `git diff --name-only` 范围核对，不再重复运行会重新生成副产物的命令，除非清理本身可能影响验证结论。

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
