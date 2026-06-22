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
scripts/validate_evidence.py
scripts/validate/validate_evidence.py
scripts/validate_canonical_data_integrity.py
scripts/validate/validate_canonical_data_integrity.py
scripts/validate_view_configs.py
scripts/validate/validate_view_configs.py
scripts/validate_chinese_view_configs.py
scripts/validate/validate_chinese_view_configs.py
scripts/validate_review_configs.py
scripts/validate/validate_review_configs.py
scripts/validate_config_comments.py
scripts/validate/validate_config_comments.py
scripts/validate_config_readability.py
scripts/validate/validate_config_readability.py
scripts/validate_all.py
scripts/validate/validate_all.py
```

兼容 wrapper 只负责转发到 `scripts/validate/` 下的真实实现，不承载大段重复逻辑。修改已迁移 validator 时，应优先修改 `scripts/validate/` 下真实实现，再确认旧路径 wrapper 仍可运行。

`scripts/validate/validate_all.py` 是全量校验总入口的真实实现。`scripts/validate_all.py` 只作为旧路径兼容 wrapper，保留既有命令和 import 入口；后续修改校验顺序、子命令路径或退出语义时，应优先修改新路径，不得把真实实现重新放回 `scripts/` 根目录。

当前已迁移 validator 真实实现：

- `validate_evidence.py`
- `validate_canonical_data_integrity.py`
- `validate_view_configs.py`
- `validate_chinese_view_configs.py`
- `validate_review_configs.py`
- `validate_i5b_cluster_adjudication_configs.py`
- `validate_config_comments.py`
- `validate_human_readable_markdown_exports.py`
- `validate_config_readability.py`

上述文件在 `scripts/` 根目录的同名旧路径均只作为兼容 wrapper。剩余 build、matrix、pipeline 类脚本暂未迁移，后续仍按小 PR 分批治理。

## scripts/export/

`scripts/export/` 是导出脚本真实实现目录。新增 exporter 应放入这里，不应继续把主逻辑直接放在 `scripts/` 根目录。

已迁移 exporter 的真实实现应位于 `scripts/export/`。`scripts/` 根目录旧 exporter 只作为兼容 wrapper，负责保留旧路径 import 或旧命令入口，不承载主逻辑。

当前已迁移 exporter：

- `export_i5b_auto_adjudication.py`
- `export_i5b_views.py`
- `export_i5b_net_evidence.py`
- `export_i5b_expanded_batch1.py`
- `export_project_doc_views.py`
- `export_md.py`

`scripts/export/export_md.py` 是 Markdown 导出总入口的真实实现。`scripts/export_md.py` 只作为旧路径兼容 wrapper，保留既有命令和 import 入口；后续修改导出顺序、路径常量、目标人物或配置读取时，应优先修改新路径，不得把真实实现重新放回 `scripts/` 根目录。

`export_md_scaffold.py` 已归入 `scripts/shared/`。build、matrix、pipeline 类脚本暂不迁移，后续按小 PR 分批治理。

## scripts/shared/

`scripts/shared/` 是共享工具真实实现目录。新增被 exporter、validator、pipeline 共同依赖的工具，应放入这里，不应继续把共享主逻辑直接放在 `scripts/` 根目录。

当前根目录共享工具均已迁移到 `scripts/shared/`，旧路径仅保留兼容 wrapper。

已迁移共享工具：

- `export_md_scaffold.py`：真实实现位于 `scripts/shared/export_md_scaffold.py`，旧路径 `scripts/export_md_scaffold.py` 只作为兼容 wrapper。修改该工具时优先改新路径。
- `i5b_cluster_warning_display.py`：真实实现位于 `scripts/shared/i5b_cluster_warning_display.py`，旧路径 `scripts/i5b_cluster_warning_display.py` 只作为兼容 wrapper。修改该工具时优先改新路径。
- `i5b_markdown_display.py`：真实实现位于 `scripts/shared/i5b_markdown_display.py`，旧路径 `scripts/i5b_markdown_display.py` 只作为兼容 wrapper。修改该工具时优先改新路径。
- `config_loaders.py`：真实实现位于 `scripts/shared/config_loaders.py`，旧路径 `scripts/config_loaders.py` 只作为兼容 wrapper。修改该工具时优先改新路径，并参考 `docs/config_loaders迁移前依赖审计.md`。

后续迁移共享工具时必须保留旧路径 wrapper。旧路径 wrapper 只负责兼容 import，不承载主逻辑。共享工具迁移必须单独开 PR，每次最多迁移 1-2 个共享工具，普通 exporter 或 validator 迁移 PR 不得顺手迁移共享工具。

`i5b_markdown_display.py` 的后续维护必须保留旧路径 `scripts/i5b_markdown_display.py` wrapper，并不得改变字段标签、值映射、长字段附录、人工审核表头白名单、machine key 保留/隐藏策略或相关展示语义。该模块的迁移影响面已记录在 `docs/i5b_markdown_display迁移前依赖审计.md`。

`config_loaders.py` 已迁移到 `scripts/shared/config_loaders.py`，旧路径 `scripts/config_loaders.py` wrapper 必须保留，并不得改变配置路径、配置语义、人物池读取、视图分组读取、关键词配置读取、证据簇提示读取或 comments 排除规则。该模块的迁移影响面已记录在 `docs/config_loaders迁移前依赖审计.md`。

## scripts/

`scripts/` 根目录当前仍保留历史脚本、尚未迁移的 build / matrix / pipeline 类脚本和必要的旧路径兼容 wrapper。剩余根目录 validator 真实实现已完成迁移。

新增 validator 不应继续放在 `scripts/` 根目录。新增 exporter 应放入 `scripts/export/`。新增共享工具应放入 `scripts/shared/`。build、pipeline、matrix 类脚本后续再分批治理，不得顺手迁移。

任何后续目录治理都应先锁定影响面和测试，再拆分迁移，避免顺手改动业务数据、评分、排名、正式定档、证据事实或证据簇裁判结论。
