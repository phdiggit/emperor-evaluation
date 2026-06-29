# GitHub 发布与认证规范

本仓库的 GitHub 发布、PR 正文、评论和审查包流程以本地持久认证为准，不依赖 Codex 的会话型 GitHub 插件做长流程发布。
根 `AGENTS.md` 路由到本文件时，本文件的具体命令和优先级为执行规范。

## 推荐方案

1. `git` 远端使用 SSH。
2. `gh` CLI 负责创建 PR、补正文、切换 ready for review。
3. 认证信息只在本机长期保存，不依赖临时会话重连。

## 首次配置

### 1. 切换远端

将 `origin` 指向 SSH 地址：

```bash
git remote set-url origin git@github.com:phdiggit/emperor-evaluation.git
```

### 2. 登录 GitHub CLI

安装并登录 `gh` 后，后续 PR 操作都走本地 CLI：

```bash
gh auth login
```

### 3. 配置 SSH key

为当前机器准备 GitHub SSH key，并确保 SSH agent 可用。完成后，本地 `git push` 应该不再依赖 HTTPS 凭据。

## 常用发布流程

```bash
git push -u origin <branch>
codex-win body validate .tmp/pr-body.md
gh pr create --base GPT --head <branch> --title "<title>" --body-file .tmp/pr-body.md
```

Issue 明确要求 draft 时才使用 `--draft`；否则创建后应保持 ready for review。

## 约定

- 长时间运行的发布任务优先使用 SSH + `gh`，不要把发布稳定性押在临时插件会话上。
- 如果 `gh` 不可用，先补齐本机认证，再执行 PR 流程。
- 该规范只描述稳定发布链路，不改变仓库的数据或评分流程。

## GitHub 操作总则

- 远端读写默认优先用已认证的 `gh` CLI；只有 `gh` 不可用、未认证、权限不足或确实做不到时才退回 connector，并说明原因。
- GitHub 写操作先用最少读取确认目标，再执行一次写入；不要对同一目标反复调用不同接口。
- 收到“返修 / 按审查意见修改 / fix review”时，先 checkout/fetch PR head 分支，并读取 PR 评论和 review threads。
- 返修后确认 local HEAD 与 PR head SHA 一致，并在回复或 PR 说明中写明。
- PR 说明必须包含最终 changed files 列表。
- 开 PR 后默认 ready for review；Issue 明确要求 draft 时才保持 draft。
- evidence 路径只用 repo-relative `path:Lx`，不用本地绝对路径。
- PowerShell 中不要拼复杂 `gh --jq`；复杂 JSON 检查优先用 `codex-win gh pr-view`、Python JSON 解析或工具自带 verify。

## PR Review Package

- 创建或更新 PR 时默认生成/刷新 `Codex PR Review Package v1.1`；用户要求“PR review / 审查 / 机械事实层 / review pack”时也按此包输出，不做 merge decision。
- 若当前安装的 `codex-win` 支持 `review-pack`，优先用：

```bash
codex-win review-pack --pr <PR> --base GPT --scope-profile <profile> --config .codex/review-pack.json --output .tmp/review-pack.md
```

- 如果没有可用 scope profile 或 config，先尝试工具支持的最接近参数组合；工具不可用时才手工按 v1.1 模板生成，并说明原因。
- 需要把 review package 写回 PR body 时，优先用：

```bash
codex-win review-pack apply --pr <PR> --package-file .tmp/review-pack.md --body-file .tmp/pr-body.md
```

- 只需写回完整正文时，用 `codex-win body validate .tmp/pr-body.md` 后接 `codex-win body apply --pr <PR> --body-file .tmp/pr-body.md`。
- 不优先回退到 `scripts/dev/pr_body_tool.py`；只有 `codex-win` 不可用或任务明确要求时才使用仓库本地 PR body 工具，并说明原因。
- 包必须含 `HEAD SNAPSHOT LOCK`、Reviewer Quick Summary、Scope / Ownership、Commands Run、Protocol Compliance、Findings、Failed Checks Classification、Anti-bloat / Lifecycle Notes、Required Next Actions。
- 必须拉当前 PR head，列 changed files，跑 current-head 与 base-head pytest，区分 PR-induced / baseline / fixed baseline failures。
- 创建 PR 后顺手生成/更新审查包，并读回验证 title、body、base、head、draft 状态和 head SHA 不 stale。

## Timing 与命令日志

PR timing、evidence batch timing 和 review package timing 只使用 `codex-win timer` 与 `codex-win run --log` 的实测结果。没有 timer 时写 `timing unavailable` 或 `precise timing unavailable`，不得估算 total、per-person 或 per-phase 时间。

```bash
codex-win timer start --id <task-id> --state .tmp/codex-timer.json --restart
codex-win run --log .tmp/codex-commands.jsonl --summary "<summary>" -- <command...>
codex-win timer finish --id <task-id> --state .tmp/codex-timer.json --command-log .tmp/codex-commands.jsonl --output .tmp/codex-timing.json
codex-win review-pack --pr <PR> --base GPT --command-log .tmp/codex-timing.json --output .tmp/review-pack.md
codex-win review-pack apply --pr <PR> --package-file .tmp/review-pack.md --body-file .tmp/pr-body.md --command-log .tmp/codex-timing.json
```

## PR Body 与评论正文安全

- 禁止用 PowerShell inline 字符串直接写大段 Markdown PR body、issue comment、PR comment 或 review comment。
- 凡 PR body、长 issue comment、长 review comment 中包含中文、Markdown 代码围栏、反引号、长文件清单或多段列表，必须先写 `.tmp/bodies/*.md` 或 `.tmp/*.md` UTF-8 no BOM 文件，并用 `codex-win body normalize/validate` 校验。
- 更新 PR body 必须使用 `codex-win body apply`、`codex-win review-pack apply` 或 `codex-win gh pr-edit`；直接 `gh pr edit --body-file` 仅作等价 fallback；不得使用 `gh pr edit --body "...大段正文..."`。
- PR body 更新失败时，不反复调试 BOM；报告“PR body 更新失败/待人工处理”，并保留本地正文文件和验证事实。
- 提交前必须检查 GitHub 正文不含 `???`、U+FFFD、控制字符、损坏代码围栏。
