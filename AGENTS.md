# AGENTS.md

本仓库是“皇帝综合评价体系”工作区。执行任务时先守边界，再动手。
English anchors are included for execution stability; Chinese remains the source wording for humans.

## 优先级 / Priority

执行顺序：Issue / PR 白名单与禁止事项 > 本 `AGENTS.md` > 当前会话已确认的仓库规则。冲突时以上层规则为准。
Priority: issue / PR allowlist and forbiddens > this `AGENTS.md` > confirmed local repo rules.

## 基本原则 / Basic Rules

- 先用本地事实和命令判断；范围明确时一次完成白名单内必要步骤。Use local facts first and complete in-scope work end to end.
- 只读诊断保持只读；需要改文件时，先锁定最小改动路径。Read-only means read-only; find the minimal edit path before writing.
- 任务卡“必读”默认指定位相关段落；大文件先用 `rg` / `git grep` / 定向行号读取，除非要整体重写，不得全文读取大型 exporter、registry、tests 或生成物。
- 修改前后核对 `git diff --name-only`；白名单外改动必须还原。Check diff scope before and after edits.
- 返工或收口先定位最小修改点；通常只确认 branch、PR head 和 `git status`。For repair or closeout, start from the smallest fix.
- 评分、证据、裁判、档位、分值和排名等业务语义先读 `docs/皇帝综合评价体系评分标准.md`；生成物不是事实源，冲突时不得静默覆盖。Generated outputs are views; find the generator before editing exports.
- 评分因子赋值 skill 只按 `docs/证据规则/评分因子赋值Skill治理.md` 的三档治理启用；只对不小比例系统性偏差的因子建窄 skill，小比例问题走诊断或 worklist，不做大而全通用 skill。
- 检索包→史料→对象池流程按 `data/query_profile_batches/AGENTS.md` 路由；retrieval_v2 clean 抓包、判读和补抓流程先读 `docs/数据结构与生成库/retrieval_v2_clean抓包流程.md`；配套开发工具按 `scripts/dev/AGENTS.md` 路由，根文件只保留入口指向。
- 清理、归档、删除和 `data/*_batches/` 治理，第一轮只写诊断或候选清单。Cleanup/archive/delete and batch-data governance start with diagnostics only.

## GitHub

- 远端读写默认优先用已认证的 `gh` CLI；只有 `gh` 不可用、未认证、权限不足或确实做不到时才退回 connector，并说明原因。Prefer authenticated `gh`.
- GitHub 写操作先用最少读取确认目标，再执行一次写入；不要对同一目标反复调用不同接口。Confirm target, then write once.
- 涉及 PR 创建、更新、审查、返修、review package、Issue/PR 评论或 GitHub 正文写入时，先读 `docs/展示与协作/GitHub发布与认证规范.md`。
- 开 PR 后默认 ready for review；Issue 明确要求 draft 时才保持 draft。Default PR state is ready for review.
- PR 说明必须包含最终 changed files 列表；创建或更新 PR 时默认生成/刷新 `Codex PR Review Package v1.1`，不做 merge decision。
- evidence 路径只用 repo-relative `path:Lx`，不用本地绝对路径；创建 PR 后顺手生成/更新审查包并读回验证 head/body 不 stale。
- PR timing / evidence batch timing 只使用 `codex-win timer` 和命令日志的实测结果；没有 timer 时写 `timing unavailable` / `precise timing unavailable`，不得估算 total、per-person 或 per-phase 时间，具体流程见 GitHub 发布规范。
- `pwsh` 中不要拼复杂 `gh --jq`；复杂 JSON 检查优先用 `codex-win gh pr-view`、Python JSON 解析或工具自带 verify。

## Shell 与编码 / Shell And Encoding

- Windows 上涉及 PowerShell 的命令默认使用 `pwsh.exe`；Python/pytest/validator/export/build/matrix 等子进程优先用 `codex-win run -- ...`；只有 5.1 专属兼容验证或任务明确要求时才用 `powershell.exe`。
- 在 `pwsh` 中使用 PowerShell 语法，可以使用 `&&` / `||`；需要 Bash 工具链、POSIX 管道、`.sh` 脚本或 Bash here-doc 时切到 Git Bash。
- 禁止用 `pwsh` / PowerShell inline、管道或 here-string 传递大段中文给 Python 或 `gh`；改用 UTF-8 临时 `.py` 文件、`codex-win body` / `repo_tool` 或 Git Bash here-doc。
- 多关键词搜索优先用一条 `rg -n "A|B|C" <paths>`，避免复杂嵌套引号。
- 中文路径、状态和 diff 范围核对优先用 `git -c core.quotepath=false ...`、`codex-win run -- git ...` 或 `python scripts/dev/repo_tool.py`。
- 中文文本、Markdown、JSON / JSONL 结构化改写优先用 `codex-win encoding`、仓库工具或 Python 标准库；输出用 UTF-8 no BOM、`ensure_ascii=False`、稳定缩进。

## 子 Agent 与批量任务 / Subagents And Batch Tasks
- 批量、后台或并发 Codex 子任务优先用 `codex-win agent run-plan`；它只负责进程监管、权限画像、输出契约和结果收集，不替代 retrieval_v2 readiness、dry-run、幂等校验、patch 验收、scorer 或落库逻辑。patch / review / factorization 类默认用 `--permission-profile tmp-jsonl-review --deny-policy deny-rewrite --git-snapshot minimal`，只写 `tmp/**`；无 git 上下文用 `none`，需要 diff stat/name-status 才用 `full`。
- `codex_tasks.jsonl` 应声明 `task_code`、`prompt_path`、`last_message_path`、`log_path` 和 `expected_outputs`；JSONL patch 用 `expected_outputs.kind=jsonl_patch` 与 `PATCH_JSONL_BEGIN` / `PATCH_JSONL_END` fallback，不只依赖旧式顶层 `patch_path`。prompt、workitems、patch 和 last message 一律通过 UTF-8 文件传递。
- 子 agent 结果不得只看退出码；必须检查 `results.jsonl` / `summary.json` 的 `status`、`error_type`、`permission_analysis`、`deny_resolution`、`output_analysis`，再交给项目脚本验收。源码写入才用 `repo-editor`，用户明确接受风险才用 `bypass`；后台 run 用 `status`、`wait`、`collect` 收尾，异常后先 `cleanup-stale`。

## GitHub 正文安全 / GitHub Body Safety

- 禁止用 `pwsh` / PowerShell inline 字符串直接写大段 Markdown PR body。
- PR body、长 issue comment、长 review comment 的生成、校验、写回和坏字符检查按 `docs/展示与协作/GitHub发布与认证规范.md` 执行。

## 脚本治理 / Script Governance

- 任务涉及 `scripts/**` 先读 `scripts/AGENTS.md`；涉及 `docs/**` 先读 `docs/AGENTS.md`。
- 开发工具、validator、exporter 和共享工具按 `scripts/AGENTS.md` 分层；`scripts/` 根目录不再保留 Python wrapper，只允许 registry `root_exceptions` 登记的非 Python 稳定入口。
- 修改已迁移脚本时只改 canonical 真实实现，并验证 canonical import/CLI；不得恢复已退役 wrapper。
- 普通功能 PR 不顺手迁移其他职责域；迁移任务按同一职责链成批处理。
- 当前路径、迁移状态、retired wrapper 审计记录、审计文档和专属测试以 `docs/文档与脚本登记/scripts_registry.json` 为准。
- scripts 治理 PR 开 PR前必须运行适用测试、`python scripts/validate/validate_all.py`、scope-check 和 agents-check。

## 改动与验证 / Changes And Validation

- 大范围改脚本前，先用 `rg` / `git grep` 精确定位，再做小补丁。Locate precisely before large script edits.
- 机械替换只在白名单路径内做；测试文件只改展示断言，不全局替换 fixture key。Keep mechanical rewrites scoped.
- 大脚本治理必须小步重构并有测试锁定；业务 PR 不顺手拆脚本。Keep business PRs scoped.
- 涉及 `data/`、`scripts/`、`tests/`、`.github/workflows/` 或 validation 入口的 PR，开 PR 前先用 `codex-win test plan --base origin/GPT --head HEAD` 规划，再用 `codex-win run -- python scripts/validate/validate_all.py` 与 focused tests；full pytest 同一 head SHA 最多一次。
- 验证命令若生成或重写 `exports/`、generated docs 或其他范围外副产物，先记录通过结果，再用 `codex-win cleanup generated --profile emperor-markdown-exports --config .codex/generated-cleanup.json --target .` dry-run 后按需 `--apply` 清理；清理后只做范围核对，不重复运行会再次生成副产物的全量命令。

- 人工阅读型 Markdown 导出规则路由到 `docs/AGENTS.md` 和 `docs/展示与协作/人工阅读型Markdown导出规范.md`。

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
