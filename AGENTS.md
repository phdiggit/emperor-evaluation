# AGENTS.md

本仓库是“皇帝综合评价体系”工作区。执行任务时先守边界，再动手。
English anchors are included for execution stability; Chinese remains the source wording for humans.

## 优先级 / Priority

执行顺序：Issue / PR 白名单与禁止事项 > 本 `AGENTS.md` > 当前会话已确认的仓库规则。冲突时以上层规则为准。
Priority: issue / PR allowlist and forbiddens > this `AGENTS.md` > confirmed local repo rules.

## 基本原则 / Basic Rules

- 先用本地事实和命令判断；范围明确时一次完成白名单内必要步骤。Use local facts first and complete in-scope work end to end.
- 只读诊断保持只读；需要改文件时，先锁定最小改动路径。Read-only means read-only; find the minimal edit path before writing.
- 修改前后核对 `git diff --name-only`；白名单外改动必须还原。Check diff scope before and after edits.
- 返工或收口先定位最小修改点；通常只确认 branch、PR head 和 `git status`。For repair or closeout, start from the smallest fix.
- 生成物不是事实源；改导出内容前先定位生成器，除非任务明确要求，不批量重写旧导出。Generated outputs are views; find the generator before editing exports.
- 清理、归档、删除和 `data/*_batches/` 治理，第一轮只写诊断或候选清单。Cleanup/archive/delete and batch-data governance start with diagnostics only.

## GitHub

- 远端读写默认优先用已认证的 `gh` CLI；只有 `gh` 不可用、未认证、权限不足或确实做不到时才退回 connector，并说明原因。Prefer authenticated `gh`.
- GitHub 写操作先用最少读取确认目标，再执行一次写入；不要对同一目标反复调用不同接口。Confirm target, then write once.
- 收到“返修 / 按审查意见修改 / fix review”时，先 checkout/fetch PR head 分支，并读取 PR 评论和 review threads。For fix review, inspect PR context first.
- 返修后确认 local HEAD 与 PR head SHA 一致，并在回复或 PR 说明中写明。After repair, confirm local HEAD equals PR head.
- PR 说明必须包含最终 changed files 列表。PR body must include final changed files.
- 开 PR 后默认 ready for review；Issue 明确要求 draft 时才保持 draft。Default PR state is ready for review.

## Shell 与编码 / Shell And Encoding

- 当前在 PowerShell 时使用 PowerShell 语法；不要使用 Bash 的 `&&` / `||`。需要串联时用分步命令，或 `; if ($LASTEXITCODE -eq 0) { ... }`。
- 当前在 Git Bash 时保持 Git Bash。需要复杂管道、重定向、命令串联时，可明确切到 Git Bash。
- 多关键词搜索优先用一条 `rg -n "A|B|C" <paths>`，避免复杂嵌套引号。
- 中文路径、状态和 diff 范围核对优先用 `git -c core.quotepath=false ...` 或 `python scripts/dev/repo_tool.py`。
- 中文文本读写、JSON / JSONL 结构化改写优先用仓库工具或 Python 标准库；JSON 输出用 UTF-8、`ensure_ascii=False`、稳定缩进。
- 临时 Markdown、说明文件使用 UTF-8 no BOM。

## GitHub 正文安全 / GitHub Body Safety

- 禁止用 PowerShell inline 字符串直接写大段 Markdown PR body。
- 凡 PR body、长 issue comment、长 review comment 中包含中文、Markdown 代码围栏、反引号、长文件清单或多段列表，必须先用 `scripts/dev/pr_body_tool.py` 生成并校验 UTF-8 no BOM 文件。
- 更新 PR body 必须使用 `gh pr edit --body-file <已校验文件>`，或使用 `scripts/dev/pr_body_tool.py apply`；不得使用 `gh pr edit --body "...大段正文..."`。
- PR body 更新失败时，不反复调试 BOM；报告“PR body 更新失败/待人工处理”，并保留本地正文文件和验证事实。
- 提交前必须检查 GitHub 正文不含 `???`、U+FFFD、控制字符、损坏代码围栏。

## 脚本治理 / Script Governance

- 任务涉及 `scripts/**` 时，修改前必须读取 `scripts/AGENTS.md`。
- 开发工具、validator、exporter 和共享工具按 `scripts/AGENTS.md` 分层；`scripts/` 根目录不再保留 Python wrapper，只允许 registry `root_exceptions` 登记的非 Python 稳定入口。
- 修改已迁移脚本时只改 canonical 真实实现，并验证 canonical import/CLI；不得恢复已退役 wrapper。
- 普通功能 PR 不顺手迁移其他职责域；迁移任务按同一职责链成批处理。
- 当前路径、迁移状态、retired wrapper 审计记录、审计文档和专属测试以 `docs/agent_rules/scripts_registry.json` 为准。
- scripts 治理 PR 开 PR 前必须运行适用测试、`python scripts/validate/validate_all.py`、scope-check 和 agents-check。

## 改动与验证 / Changes And Validation

- 大范围改脚本前，先用 `rg` / `git grep` 精确定位，再做小补丁。Locate precisely before large script edits.
- 机械替换只在白名单路径内做；测试文件只改展示断言，不全局替换 fixture key。Keep mechanical rewrites scoped.
- 大脚本治理必须小步重构并有测试锁定；业务 PR 不顺手拆脚本。Keep business PRs scoped.
- 涉及 `data/`、`scripts/`、`tests/`、`.github/workflows/` 或 validation 入口的 PR，开 PR 前运行 `python scripts/validate/validate_all.py`。
- 验证命令若生成或重写 `exports/`、generated docs 或其他范围外副产物，先记录通过结果，再清理副产物；清理后只做 `git status`、`git diff --name-only`、`git diff --check` 等范围核对，不重复运行会再次生成副产物的全量命令。

## 人工阅读型 Markdown 导出高压线 / Human-Readable Markdown Exports

- 展示优化不得改变源数据、评分、定档、排名、warning 语义或裁判结论。Display-only changes must not alter data or adjudication semantics.
- 人工复核型 Markdown 默认纯 Markdown，不使用 HTML details。Pure Markdown by default; no HTML details.
- 不用宽表承载长字段、裁判说明、相邻项剥离说明、warning matched_fields 或 linked evidence 长字段。No wide tables for long fields.
- `linked_*`、`cross_item_split_signals / 相邻项剥离说明`、warning `matched_fields` 必须全量展示，不得截断。Must show full content; no truncation.
- 详细规范见 `docs/人工阅读型Markdown导出规范.md`。

## 默认忽略 / Default Ignore

除非 Issue / PR / 用户请求明确点名，或为了清理已知生成副产物，不主动读取、总结或改写：

```text
exports/
logs/
data/configs/
tmp/
.cache/
.codex/
```

只做范围核对时，优先用 `git diff --name-only` / `git status --short`，不要展开读取目录内容。`docs/`、`tests/` 不默认全量扫描；仅在任务点名、PR diff 涉及、验证失败、或需要查某份具体规范/测试时按文件读取。
