# scripts 共享工具依赖盘点

本文件用于 shared 分层治理，记录共享工具依赖盘点、目录规划和迁移规则说明。#193 已迁移 `export_md_scaffold.py`，#194 已迁移 `i5b_cluster_warning_display.py`。`i5b_markdown_display.py` 未迁移；已完成迁移前依赖审计，详见 `docs/i5b_markdown_display迁移前依赖审计.md`。

## 一、当前共享工具清单

- `scripts/config_loaders.py`
- `scripts/export_md_scaffold.py`（旧路径兼容 wrapper）
- `scripts/shared/export_md_scaffold.py`（已迁移真实实现）
- `scripts/i5b_markdown_display.py`（未迁移；已完成迁移前依赖审计）
- `scripts/i5b_cluster_warning_display.py`（旧路径兼容 wrapper）
- `scripts/shared/i5b_cluster_warning_display.py`（已迁移真实实现）

当前状态：

已迁移：

```text
scripts/shared/export_md_scaffold.py
scripts/shared/i5b_cluster_warning_display.py
```

旧路径兼容 wrapper：

```text
scripts/export_md_scaffold.py
scripts/i5b_cluster_warning_display.py
```

仍未迁移：

```text
scripts/config_loaders.py
scripts/i5b_markdown_display.py
```

## 二、共享工具职责

- `config_loaders.py`：集中加载配置、人物池、视图分组、展示字典和各类路径配置。
- `export_md_scaffold.py`：提供 Markdown 表格、JSONL 读取、基础导出步骤和通用导出辅助；已迁移到 `scripts/shared/`，旧路径为兼容 wrapper。
- `i5b_markdown_display.py`：提供第五项B展示字段、值映射、长字段处理、附录策略和人工审核表头；未迁移，已完成迁移前依赖审计，详见 `docs/i5b_markdown_display迁移前依赖审计.md`。
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

`export_md_scaffold.py` 与 `i5b_cluster_warning_display.py` 已迁移到 `scripts/shared/`，旧路径保留兼容 wrapper。`config_loaders.py` 与 `i5b_markdown_display.py` 仍暂留 `scripts/` 根目录。

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
2. 再评估 `config_loaders.py`，因为它牵涉配置路径、人物池和展示配置，迁移前必须覆盖 import 与路径定位。
3. `i5b_cluster_warning_display.py` 已迁移，后续修改应优先改 `scripts/shared/i5b_cluster_warning_display.py`，再确认旧路径 wrapper 可 import。
4. `i5b_markdown_display.py` 未迁移；已完成迁移前依赖审计，详见 `docs/i5b_markdown_display迁移前依赖审计.md`。该工具和第五项B展示语义更近，迁移时需要保证字段标签、值映射、长字段附录、machine key 保留/隐藏策略和人工审核表头白名单语义不变。

## 七、本 PR 明确不做

- 不移动 `scripts/config_loaders.py`。
- 不移动 `scripts/i5b_markdown_display.py`。
- 不修改共享工具实现逻辑。
- 不修改 exporter 或 validator 真实实现。
- 不重新生成 `exports/**`。
