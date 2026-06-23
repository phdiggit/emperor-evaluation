# agent rules 说明

本目录保存代理规则的机器可读事实源和说明文档。`AGENTS.md` 不承担项目状态日志；会频繁变化的脚本迁移状态和 docs 生命周期状态放入 registry，由开发工具和测试检查。

## 四层规则结构

1. 所有任务长期规则：根 `AGENTS.md`。
2. scripts 范围规则：`scripts/AGENTS.md`。
3. docs 范围规则：`docs/AGENTS.md`。
4. 脚本动态迁移状态：`docs/agent_rules/scripts_registry.json`。
5. docs 当前生命周期与候选动作：`docs/agent_rules/docs_registry.json`。
6. 单次任务规则：Issue / PR / Codex 任务卡。
7. 可自动判断的规则：`scripts/dev/repo_tool.py`、`scripts/dev/docs_tool.py`、pytest 或 validator。

## 新增规则分类决策表

| 规则类型 | 放置位置 |
| --- | --- |
| 所有任务都适用 | 根 `AGENTS.md` |
| 只适用于 scripts | `scripts/AGENTS.md` |
| 只适用于 docs | `docs/AGENTS.md` |
| 当前路径或迁移状态 | `docs/agent_rules/scripts_registry.json` |
| docs 当前生命周期、引用和候选动作 | `docs/agent_rules/docs_registry.json` |
| 可机器验证 | `repo_tool`、`docs_tool` 或测试 |
| 当前任务临时要求 | Issue / PR 任务卡 |
| 历史背景或设计解释 | `docs/` 下专题文档 |

## 维护原则

- 根 `AGENTS.md` 只保留稳定、高优先级、跨任务适用的执行规则和路由规则。
- `scripts/AGENTS.md` 只保留 scripts 范围长期稳定的行为规则，不记录当前还剩哪些脚本未迁移。
- `docs/AGENTS.md` 只保留 docs 范围长期稳定的行为规则，不记录逐文件候选状态。
- `scripts_registry.json` 是脚本实现路径、retired wrapper 审计映射、root exception、审计文档和 required tests 的当前事实源。
- `docs_registry.json` 是 docs 当前生命周期、引用关系、generator 候选、proposed action 和内容归置建议的状态事实源。
- `project_driver_paths` 保存项目上位驱动文档路径，不是普通候选列表；driver 文档不能被常规 archive/delete 批次吸收。
- driver 的业务语义高于下位 docs，但不高于用户、Issue / PR 任务约束和 AGENTS 执行安全规则。
- 生命周期回答“这份文档当前如何治理”；内容归置回答“文档主体内容长期应由 docs、配置、canonical data、exports 还是 archive 承载”。两者是正交维度，不应互相替代。
- `content_role` 描述文档主体内容角色；`placement_action` 描述推荐目标态动作；`placement_targets` 记录后续吸收、生成、拆分或归档的精确候选路径。
- `archived_document_paths` 是旧路径到历史归档路径的审计映射，表示旧路径已退役；不表示旧路径继续存在或可作为当前入口。
- archive 状态属于 docs registry 的动态事实；根 `AGENTS.md` 不记录逐文件归档状态。
- `retired_legacy_wrappers` 只记录旧路径曾对应的 module id，便于检查旧 import 回流；不表示旧路径仍可 import 或运行。
- docs registry 是状态事实源，AGENTS 不承担逐文件项目状态日志。
- 能由代码检查的规则，应优先放进 `repo_tool`、`docs_tool` 或 pytest，不只依赖自然语言提醒。
