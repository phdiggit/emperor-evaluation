# agent rules 说明

本目录保存代理规则的机器可读事实源和说明文档。`AGENTS.md` 不承担项目状态日志；会频繁变化的脚本迁移状态放入 registry，由 `repo_tool` 和测试检查。

## 四层规则结构

1. 所有任务长期规则：根 `AGENTS.md`。
2. scripts 范围规则：`scripts/AGENTS.md`。
3. 动态迁移状态：`docs/agent_rules/scripts_registry.json`。
4. 单次任务规则：Issue / PR / Codex 任务卡。
5. 可自动判断的规则：`scripts/dev/repo_tool.py`、pytest 或 validator。

## 新增规则分类决策表

| 规则类型 | 放置位置 |
| --- | --- |
| 所有任务都适用 | 根 `AGENTS.md` |
| 只适用于 scripts | `scripts/AGENTS.md` |
| 当前路径或迁移状态 | `docs/agent_rules/scripts_registry.json` |
| 可机器验证 | `repo_tool` 或测试 |
| 当前任务临时要求 | Issue / PR 任务卡 |
| 历史背景或设计解释 | `docs/` 下专题文档 |

## 维护原则

- 根 `AGENTS.md` 只保留稳定、高优先级、跨任务适用的执行规则和路由规则。
- `scripts/AGENTS.md` 只保留 scripts 范围长期稳定的行为规则，不记录当前还剩哪些脚本未迁移。
- `scripts_registry.json` 是脚本实现路径、wrapper、root exception、审计文档和 required tests 的当前事实源。
- 能由代码检查的规则，应优先放进 `repo_tool` 或 pytest，不只依赖自然语言提醒。
