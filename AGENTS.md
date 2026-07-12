# AGENTS.md

本仓库是“皇帝综合评价体系 V4”工作区。Issue / PR 的白名单和禁止事项优先于本文件。

## 事实源优先级

1. `docs/项目总纲/皇帝综合评价体系评分标准.md`
2. V4 领域模型与不可妥协约束
3. 分项规则
4. `config/*.yml`

发现冲突时必须显式记录，不得由代码、模型输出或旧数据静默覆盖。

## 数据与副作用

- 默认 report-only、offline-first、shadow-first。
- 模型只能在 `config/model-policy.yml` 允许的场景被调用；模型输出不得直接成为事实或评分。
- runtime 路径、并发、超时、凭据和部署参数不得写入核心项目配置。

## 工作区

- 修改前后运行 `git -c core.quotepath=false status --short` 和 `git diff --name-only`。
- 不覆盖用户已有改动，不默认 stash、clean、reset。
- 中文 Markdown、YAML、JSON 使用 UTF-8 no BOM；避免 PowerShell inline 传递长中文正文。
- 清理、归档和删除首先给出诊断；任务明确要求的 V4 初始化删除除外。
