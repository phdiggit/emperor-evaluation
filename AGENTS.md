# AGENTS.md

本仓库是“皇帝综合评价体系”工作区。执行任务时先守边界，再动手。

## 优先级

1. Issue / PR 的变更白名单与禁止事项
2. 本 `AGENTS.md`
3. 当前会话里已确认可用的仓库规则与约定

上层规则和下层偏好冲突时，以上层规则为准。

## 基本原则

- 能用本地事实和命令判断的，先判断再行动，不先泛问。
- 范围明确时，一次完成白名单内必要步骤；只有范围、风险或外部状态会明显影响结果时才暂停确认。
- 只读诊断保持只读；需要改文件时，先确认最小改动路径。
- 修改前后都核对 `git diff --name-only`；白名单外改动必须还原。
- `exports/markdown_views/` 是导出视图层，不是事实源；除非任务明确要求，不批量重写旧导出。
- `data/*_batches/` 是过渡批次层；确认唯一数据源前不删除。
- 清理、归档、删除候选第一轮只写诊断或候选清单，不直接删改。

## GitHub

- 远端读写默认优先用已认证的 `gh` CLI；只有 `gh` 不可用、未认证、权限不足或确实做不到时才退回 connector，并说明原因。
- GitHub 写操作先用最少读取确认目标，再执行一次写入；不要对同一目标反复调用不同接口。
- 收到“返修 / 按审查意见修改 / fix review”时，先 checkout/fetch PR head 分支，并读取 PR 评论和 review threads。
- 返修后确认 local HEAD 与 PR head SHA 一致，并在回复或 PR 说明中写明。
- PR 说明必须包含最终 changed files 列表。
- 开 PR 后默认 ready for review；Issue 明确要求 draft 时才保持 draft。

## Shell 与编码

- 当前在 PowerShell 时使用 PowerShell 语法；不要使用 Bash 的 `&&` / `||`。需要串联时用分步命令，或 `; if ($LASTEXITCODE -eq 0) { ... }`。
- 当前在 Git Bash 时保持 Git Bash。需要复杂管道、重定向、命令串联时，可明确切到 Git Bash。
- 多关键词搜索优先用一条 `rg -n "A|B|C" <paths>`，避免复杂嵌套引号。
- 中文路径、状态和 diff 范围核对优先用 `git -c core.quotepath=false ...` 或 `python scripts/dev/repo_tool.py`。
- 中文文本读写、JSON / JSONL 结构化改写优先用仓库工具或 Python 标准库；JSON 输出用 UTF-8、`ensure_ascii=False`、稳定缩进。
- PR body、临时 Markdown、说明文件使用 UTF-8 无 BOM。

## 改动与验证

- 大范围改脚本前，先用 `rg` / `git grep` 精确定位，再做小补丁。
- 大脚本治理必须小步重构并有测试锁定；业务 PR 不顺手拆脚本。
- 涉及 `data/`、`scripts/`、`tests/`、`.github/workflows/` 或 validation 入口的 PR，开 PR 前运行 `python scripts/validate_all.py`。
- 验证命令若重写 `exports/`、generated docs 或禁止范围副产物，先记录结果，再清理副产物；清理后只做范围核对，不重复运行会再生成副产物的命令。

## 人工阅读型 Markdown 导出高压线

- 展示优化不得改变源数据、评分、定档、排名、warning 语义或裁判结论。
- 人工复核型 Markdown 默认纯 Markdown，不使用 HTML details。
- 不用宽表承载长字段、裁判说明、相邻项剥离说明、warning matched_fields 或 linked evidence 长字段。
- `linked_*`、`cross_item_split_signals / 相邻项剥离说明`、warning `matched_fields` 必须全量展示，不得截断。
- 详细规范见 `docs/人工阅读型Markdown导出规范.md`。

## 默认忽略

除非 Issue / PR / 用户请求明确点名，或为了清理已知生成副产物，不主动读取、总结或改写：

```text
exports/
logs/
tmp/
.cache/
.codex/
```

只做范围核对时，优先用 `git diff --name-only` / `git status --short`，不要展开读取目录内容。`docs/`、`tests/` 不默认全量扫描；仅在任务点名、PR diff 涉及、验证失败、或需要查某份具体规范/测试时按文件读取。
