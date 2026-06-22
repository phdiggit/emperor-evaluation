# scripts 共享工具依赖盘点

当前实现路径与迁移状态以 `docs/agent_rules/scripts_registry.json` 为准；本文保留依赖与风险说明。

本文件用于 shared 分层治理，记录共享工具依赖盘点、目录规划和迁移规则说明。#193 已迁移 `export_md_scaffold.py`，#194 已迁移 `i5b_cluster_warning_display.py`，#196 已迁移 `i5b_markdown_display.py`。`config_loaders.py` 已迁移到 `scripts/shared/`，旧路径保留兼容 wrapper；迁移前依赖审计见 `docs/config_loaders迁移前依赖审计.md`。

## 一、当前共享工具清单

- `scripts/config_loaders.py`（旧路径兼容 wrapper）
- `scripts/shared/config_loaders.py`（已迁移真实实现）
- `scripts/export_md_scaffold.py`（旧路径兼容 wrapper）
- `scripts/shared/export_md_scaffold.py`（已迁移真实实现）
- `scripts/i5b_markdown_display.py`（旧路径兼容 wrapper）
- `scripts/shared/i5b_markdown_display.py`（已迁移真实实现）
- `scripts/i5b_cluster_warning_display.py`（旧路径兼容 wrapper）
- `scripts/shared/i5b_cluster_warning_display.py`（已迁移真实实现）

当前状态：

已迁移：

```text
scripts/shared/export_md_scaffold.py
scripts/shared/i5b_cluster_warning_display.py
scripts/shared/i5b_markdown_display.py
scripts/shared/config_loaders.py
```

旧路径兼容 wrapper：

```text
scripts/export_md_scaffold.py
scripts/i5b_cluster_warning_display.py
scripts/i5b_markdown_display.py
scripts/config_loaders.py
```

## 二、共享工具职责

- `config_loaders.py`：集中加载配置、人物池、视图分组、检索关键词、证据簇裁判提示和各类路径配置；已迁移到 `scripts/shared/`，旧路径保留兼容 wrapper，详见 `docs/config_loaders迁移前依赖审计.md`。
- `export_md_scaffold.py`：提供 Markdown 表格、JSONL 读取、基础导出步骤和通用导出辅助；已迁移到 `scripts/shared/`，旧路径为兼容 wrapper。
- `i5b_markdown_display.py`：提供第五项B展示字段、值映射、长字段处理、附录策略和人工审核表头；已迁移到 `scripts/shared/`，旧路径为兼容 wrapper，维护要求详见 `docs/i5b_markdown_display迁移前依赖审计.md`。
- `i5b_cluster_warning_display.py`：提供第五项B证据簇 warning 的 display-only 匹配与展示辅助；已迁移到 `scripts/shared/`，旧路径为兼容 wrapper。

## 三、依赖方向

- `scripts/export/**` 依赖共享工具。
- `scripts/validate/**` 可能依赖共享工具。
- `tests/` 依赖共享工具。
- `scripts/export_md.py` 总入口依赖共享工具和 exporter。
- 共享工具不应反向依赖 exporter 或 validator。

## 四、未来目录规划

未来共享工具真实实现目录规划如下：

```text
scripts/
  dev/
  validate/
  export/
  shared/
    config_loaders.py
    export_md_scaffold.py
    i5b_markdown_display.py
    i5b_cluster_warning_display.py
```

`export_md_scaffold.py`、`i5b_cluster_warning_display.py`、`i5b_markdown_display.py` 与 `config_loaders.py` 已迁移到 `scripts/shared/`，旧路径保留兼容 wrapper。

## 五、后续迁移原则

- 共享工具迁移必须单独 PR。
- 每次最多迁移 1-2 个共享工具。
- 必须保留旧路径 wrapper。
- 迁移后新真实实现应放入 `scripts/shared/`。
- 旧路径 wrapper 只兼容 import，不承载主逻辑。
- 先迁低层工具，再迁高层工具。
- 普通 exporter 或 validator 迁移 PR 不得顺手迁移共享工具。

## 六、建议迁移顺序

1. `export_md_scaffold.py` 已迁移，后续修改应优先改 `scripts/shared/export_md_scaffold.py`，再确认旧路径 wrapper 可 import。
2. `config_loaders.py` 已迁移；后续修改应优先改 `scripts/shared/config_loaders.py`，再确认旧路径 wrapper 可 import。该工具牵涉配置读取、路径常量、人物池、视图分组、检索关键词和证据簇裁判提示，维护时必须保证配置路径和配置语义不变。
3. `i5b_cluster_warning_display.py` 已迁移，后续修改应优先改 `scripts/shared/i5b_cluster_warning_display.py`，再确认旧路径 wrapper 可 import。
4. `i5b_markdown_display.py` 已迁移，后续修改应优先改 `scripts/shared/i5b_markdown_display.py`，再确认旧路径 wrapper 可 import。该工具和第五项B展示语义更近，维护时需要保证字段标签、值映射、长字段附录、machine key 保留/隐藏策略和人工审核表头白名单语义不变。

## 七、本 PR 明确不做

- 不改变 `config_loaders.py` 的 API 行为、配置路径或业务语义。
- 不修改共享工具实现逻辑。
- 不修改 exporter 或 validator 真实实现。
- 不重新生成 `exports/**`。
