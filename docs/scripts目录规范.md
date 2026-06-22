# scripts 目录规范

本规范用于区分开发辅助工具、校验脚本、导出脚本、共享工具和后续目录治理边界。目录治理应分批、小步推进，不在一个 PR 中搬空 `scripts/` 根目录。

当前脚本实现路径、wrapper 对应关系、未迁移根脚本、`audit_docs` 和 `required_tests` 均以 `docs/agent_rules/scripts_registry.json` 为当前事实源；本文只保留稳定架构规则和少量示例。

## scripts/dev/

`scripts/dev/` 是开发辅助工具目录，供 Codex、维护者和本地开发使用。

这类脚本用于本地读写、范围核对、PR body 生成、仓库上下文快照和类似维护动作，不应参与业务导出、评分逻辑、证据裁判或正式验证语义。

新增给 Codex 或开发者使用的辅助轮子，必须优先放入 `scripts/dev/`。不得把新的开发辅助脚本直接放入 `scripts/` 根目录。

## scripts/validate/

`scripts/validate/` 是 validator 真实实现目录。新增 validator 应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

已迁移的旧路径可以在 `scripts/` 根目录保留兼容 wrapper。兼容 wrapper 只负责转发到 `scripts/validate/` 下的真实实现，不承载大段重复逻辑。修改已迁移 validator 时，应优先修改 `scripts/validate/` 下真实实现，再确认旧路径 wrapper 仍可运行。

`scripts/validate/validate_all.py` 是全量校验总入口的真实实现。后续修改校验顺序、子命令路径或退出语义时，应优先修改新路径，不得把真实实现重新放回 `scripts/` 根目录。

## scripts/export/

`scripts/export/` 是导出脚本真实实现目录。新增 exporter 应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

已迁移 exporter 的真实实现应位于 `scripts/export/`。`scripts/` 根目录旧 exporter 只作为兼容 wrapper，负责保留旧路径 import 或旧命令入口，不承载主逻辑。

`scripts/export/export_md.py` 是 Markdown 导出总入口的真实实现。后续修改导出顺序、路径常量、目标人物或配置读取时，应优先修改新路径，不得把真实实现重新放回 `scripts/` 根目录。

## scripts/build/

`scripts/build/` 是数据库和其他构建步骤的真实实现目录。新增构建脚本应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

数据库构建测试应隔离到 `tmp_path` 或临时仓库，避免直接删除、覆盖或重新创建真实工作区的 `evidence_cache.sqlite`。根目录脚本当前状态继续由 `docs/agent_rules/scripts_registry.json` 管理。

## scripts/shared/

`scripts/shared/` 是共享工具真实实现目录。新增被 exporter、validator、pipeline 共同依赖的工具，应放入这里，不应继续把共享主逻辑直接放在 `scripts/` 根目录。

后续迁移共享工具时必须保留旧路径 wrapper。旧路径 wrapper 只负责兼容 import，不承载主逻辑。共享工具迁移必须单独开 PR；普通 exporter 或 validator 迁移 PR 不得顺手迁移共享工具。

维护高风险共享工具时，应先读取 registry 指向的审计文档。审计文档保留依赖、风险和验证说明；registry 负责当前路径和 required tests。

## scripts/ 根目录

`scripts/` 根目录只保留 registry 登记的历史脚本、尚未迁移的 build / matrix / pipeline 类脚本、稳定入口和必要的旧路径兼容 wrapper。

新增 validator 不应继续放在 `scripts/` 根目录。新增 exporter 应放入 `scripts/export/`。新增共享工具应放入 `scripts/shared/`。build、pipeline、matrix 类脚本后续再分批治理，不得顺手迁移。

每个 `scripts/*.py` 根文件必须满足二选一：

- 是 registry 中某个 module 的 `legacy_wrapper`；
- 出现在 registry 的 `root_exceptions` 中。

## wrapper 原则

旧路径 wrapper 只做 import/CLI 转发，不承载主逻辑，不复制大段常量列表，不定义 validate/export/build 等真实主逻辑函数。

修改已迁移脚本时，应优先修改 registry 指向的真实实现，并按 registry 的 `required_tests` 补充验证。若 wrapper 因历史兼容需要超过默认长度，应在 registry 中登记 `max_wrapper_lines` 和 `exception_reason`。

## 迁移节奏

迁移按职责链分批推进：validator、exporter、shared、build、pipeline、matrix 等职责域不要在普通功能 PR 中混迁。

同职责、同风险、同验证链的机械迁移可以批量处理；跨职责或高风险共享工具迁移必须拆分 PR。

任何目录治理都应先锁定影响面和测试，再拆分迁移，避免顺手改动业务数据、评分、排名、正式定档、证据事实或证据簇裁判结论。

## 路径漂移检查

移动 Python 文件必须核对 `__file__`、`parents[n]`、`ROOT` 和所有路径常量。迁移后应同时验证新路径和旧路径 import/CLI。

治理 PR 开 PR 前应运行：

```text
python scripts/dev/repo_tool.py agents-check
python scripts/dev/repo_tool.py scope-check ...
python scripts/validate_all.py
```

如验证命令生成 `exports/**`、数据库或其他范围外副产物，应先记录通过结果，再清理副产物并只做范围核对。
