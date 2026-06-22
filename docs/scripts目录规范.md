# scripts 目录规范

本规范用于区分开发辅助工具、校验脚本、业务脚本和后续目录治理边界。目录治理应分批、小步推进，不在一个 PR 中搬空 `scripts/` 根目录。

## scripts/dev/

`scripts/dev/` 是开发辅助工具目录，供 Codex、维护者和本地开发使用。

典型示例：

- `repo_tool.py`
- `pr_body_tool.py`

这类脚本用于本地读写、范围核对、PR body 生成和类似维护动作，不应参与业务导出、评分逻辑、证据裁判或正式验证语义。

新增给 Codex 或开发者使用的辅助轮子，必须优先放入 `scripts/dev/`。不得把新的开发辅助脚本直接放入 `scripts/` 根目录。

## scripts/validate/

`scripts/validate/` 是 validator 真实实现目录。新增 validator 应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

已迁移的旧路径可以在 `scripts/` 根目录保留兼容 wrapper，例如：

```text
scripts/validate_config_comments.py
scripts/validate/validate_config_comments.py
```

兼容 wrapper 只负责转发到 `scripts/validate/` 下的真实实现，不承载大段重复逻辑。修改已迁移 validator 时，应优先修改 `scripts/validate/` 下真实实现，再确认旧路径 wrapper 仍可运行。

## scripts/export/

`scripts/export/` 是导出脚本真实实现目录。新增 exporter 应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

已迁移 exporter 的真实实现应位于 `scripts/export/`。`scripts/` 根目录旧 exporter 只作为兼容 wrapper，负责保留旧路径 import 或旧命令入口，不承载主逻辑。

当前已迁移 exporter：

- `export_i5b_auto_adjudication.py`
- `export_i5b_views.py`
- `export_i5b_net_evidence.py`
- `export_i5b_expanded_batch1.py`
- `export_project_doc_views.py`

本阶段只分批迁移低风险 exporter。`export_md.py`、`export_md_scaffold.py` 以及 build、matrix、pipeline 类脚本暂不迁移，后续按小 PR 分批治理。

## scripts/shared/

`scripts/shared/` 是共享工具真实实现目录。新增被 exporter、validator、pipeline 共同依赖的工具，应放入这里，不应继续把共享主逻辑直接放在 `scripts/` 根目录。

当前根目录共享工具暂不迁移：

- `config_loaders.py`
- `export_md_scaffold.py`
- `i5b_markdown_display.py`
- `i5b_cluster_warning_display.py`

后续迁移共享工具时必须保留旧路径 wrapper。旧路径 wrapper 只负责兼容 import，不承载主逻辑。共享工具迁移必须单独开 PR，每次最多迁移 1-2 个共享工具，普通 exporter 或 validator 迁移 PR 不得顺手迁移共享工具。

## scripts/

`scripts/` 根目录当前仍保留历史脚本、总入口、尚未迁移脚本和必要的旧路径兼容 wrapper。

新增 validator 不应继续放在 `scripts/` 根目录。新增 exporter 应放入 `scripts/export/`。新增共享工具应放入 `scripts/shared/`。业务导出总入口、build、pipeline、matrix 类脚本后续再分批治理，不得顺手迁移。

任何后续目录治理都应先锁定影响面和测试，再拆分迁移，避免顺手改动业务数据、评分、排名、正式定档、证据事实或证据簇裁判结论。
