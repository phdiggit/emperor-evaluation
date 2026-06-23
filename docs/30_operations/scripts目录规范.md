# scripts 目录规范

本规范用于区分开发辅助工具、校验脚本、导出脚本、共享工具和后续目录治理边界。`scripts/` 根目录不再保留 Python wrapper；Python CLI 统一使用分层 canonical 路径。

当前脚本实现路径、retired wrapper 审计记录、`root_exceptions`、`audit_docs` 和 `required_tests` 均以 `docs/agent_rules/scripts_registry.json` 为当前事实源；本文只保留稳定架构规则和少量示例。

## scripts/dev/

`scripts/dev/` 是开发辅助工具目录，供 Codex、维护者和本地开发使用。

这类脚本用于本地读写、范围核对、PR body 生成、仓库上下文快照和类似维护动作，不应参与业务导出、评分逻辑、证据裁判或正式验证语义。

新增给 Codex 或开发者使用的辅助轮子，必须优先放入 `scripts/dev/`。不得把新的开发辅助脚本直接放入 `scripts/` 根目录。

## scripts/validate/

`scripts/validate/` 是 validator 真实实现目录。新增 validator 应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

已迁移的旧路径已经退役，不再保留 `scripts/*.py` 兼容 wrapper。修改 validator 时，应优先修改 `scripts/validate/` 下真实实现，并验证 canonical CLI。

`scripts/validate/validate_all.py` 是全量校验总入口的真实实现。后续修改校验顺序、子命令路径或退出语义时，应优先修改新路径，不得把真实实现重新放回 `scripts/` 根目录。

## scripts/export/

`scripts/export/` 是导出脚本真实实现目录。新增 exporter 应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

已迁移 exporter 的真实实现应位于 `scripts/export/`。`scripts/` 根目录旧 exporter 已退役；旧路径不再作为 import 或命令入口。

`scripts/export/export_md.py` 是 Markdown 导出总入口的真实实现。后续修改导出顺序、路径常量、目标人物或配置读取时，应优先修改新路径，不得把真实实现重新放回 `scripts/` 根目录。

## scripts/build/

`scripts/build/` 是数据库和其他构建步骤的真实实现目录。新增构建脚本应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

数据库构建测试应隔离到 `tmp_path` 或临时仓库，避免直接删除、覆盖或重新创建真实工作区的 `evidence_cache.sqlite`。根目录退役路径审计记录继续由 `docs/agent_rules/scripts_registry.json` 管理。

## scripts/matrix/

`scripts/matrix/` 是矩阵规划和矩阵视图生成脚本的真实实现目录。矩阵脚本可以生成人工审核使用的矩阵骨架，但矩阵骨架不等于检索结果，不得写入评分、证据事实、search logs、evidence cards 或数据库副产物。

矩阵测试必须隔离输出，默认使用 `tmp_path`、临时输出路径或临时仓库，避免直接重写真实工作区的 `exports/**`。当前路径、retired wrapper 和迁移状态继续由 `docs/agent_rules/scripts_registry.json` 管理。

## scripts/shared/

`scripts/shared/` 是共享工具真实实现目录。新增被 exporter、validator、pipeline 共同依赖的工具，应放入这里，不应继续把共享主逻辑直接放在 `scripts/` 根目录。

共享工具真实实现位于 `scripts/shared/`；旧路径 wrapper 已退役，不再保留兼容 import。共享工具迁移必须单独开 PR；普通 exporter 或 validator 迁移 PR 不得顺手迁移共享工具。

维护高风险共享工具时，应先读取 registry 指向的审计文档。审计文档保留依赖、风险和验证说明；registry 负责当前路径和 required tests。

## scripts/ 根目录

`scripts/` 根目录不再保留 Python 脚本。当前唯一登记的稳定根入口是 `scripts/publish_pr.ps1`，其由 registry `root_exceptions` 管理。

新增 validator 不应继续放在 `scripts/` 根目录。新增 exporter 应放入 `scripts/export/`。新增共享工具应放入 `scripts/shared/`。build、pipeline、matrix 类脚本使用各自分层目录，不得顺手改变业务语义。

`scripts/*.py` 根文件不得存在；如旧路径需要审计保留，只能写入 registry 的 `retired_legacy_wrappers`：

- 旧 wrapper 路径 -> registry module id；
- 旧路径必须位于 `scripts/` 根目录且为 `.py`；
- retired path 不表示旧路径仍可运行。

## retired wrapper 原则

legacy Python wrappers 已集中退役；不得恢复旧路径 import/CLI 兼容层，不得在 `scripts/` 根目录新增 `*.py`。

修改已迁移脚本时，应优先修改 registry 指向的真实实现，并按 registry 的 `required_tests` 补充验证。

`retired_legacy_wrappers` 是审计映射，不是兼容承诺。README、用户 CLI、测试和自动化必须使用 canonical 路径。canonical import 状态和根目录 Python 回流由 `repo_tool` 自动检查。

## 迁移节奏

迁移按职责链分批推进：validator、exporter、shared、build、pipeline、matrix 等职责域不要在普通功能 PR 中混迁。

同职责、同风险、同验证链的机械迁移可以批量处理；跨职责或高风险共享工具迁移必须拆分 PR。

任何目录治理都应先锁定影响面和测试，再拆分迁移，避免顺手改动业务数据、评分、排名、正式定档、证据事实或证据簇裁判结论。

## 路径漂移检查

移动 Python 文件必须核对 `__file__`、`parents[n]`、`ROOT` 和所有路径常量。迁移后验证 canonical import/CLI，不再验证旧路径 import/CLI。

治理 PR 开 PR 前应运行：

```text
python scripts/dev/repo_tool.py agents-check
python scripts/dev/repo_tool.py canonical-imports-check
python scripts/dev/repo_tool.py scope-check ...
python scripts/validate/validate_all.py
```

如验证命令生成 `exports/**`、数据库或其他范围外副产物，应先记录通过结果，再清理副产物并只做范围核对。
