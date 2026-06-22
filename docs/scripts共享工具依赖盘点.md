# scripts 共享工具依赖盘点

本文件用于 #192 的 shared 分层准备，只做依赖盘点、目录规划和迁移规则说明。本 PR 不移动共享工具、不改变 import 路径、不修改 exporter、validator 或共享工具真实实现。

## 一、当前共享工具清单

- `scripts/config_loaders.py`
- `scripts/export_md_scaffold.py`
- `scripts/i5b_markdown_display.py`
- `scripts/i5b_cluster_warning_display.py`

## 二、共享工具职责

- `config_loaders.py`：集中加载配置、人物池、视图分组、展示字典和各类路径配置。
- `export_md_scaffold.py`：提供 Markdown 表格、JSONL 读取、基础导出步骤和通用导出辅助。
- `i5b_markdown_display.py`：提供第五项B展示字段、值映射、长字段处理、附录策略和人工审核表头。
- `i5b_cluster_warning_display.py`：提供第五项B证据簇 warning 的 display-only 匹配与展示辅助。

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

本 PR 只允许新增 `scripts/shared/__init__.py` 占位，不导入旧模块，不迁移任何共享工具。

## 五、后续迁移原则

- 共享工具迁移必须单独 PR。
- 每次最多迁移 1-2 个共享工具。
- 必须保留旧路径 wrapper。
- 迁移后新真实实现应放入 `scripts/shared/`。
- 旧路径 wrapper 只兼容 import，不承载主逻辑。
- 先迁低层工具，再迁高层工具。
- 普通 exporter 或 validator 迁移 PR 不得顺手迁移共享工具。

## 六、建议迁移顺序

1. 先评估 `export_md_scaffold.py` 这类底层导出辅助，确认旧路径 wrapper 对 exporter、tests 和总入口透明。
2. 再评估 `config_loaders.py`，因为它牵涉配置路径、人物池和展示配置，迁移前必须覆盖 import 与路径定位。
3. 再评估 `i5b_markdown_display.py` 和 `i5b_cluster_warning_display.py`，这两个工具和第五项B展示语义更近，迁移时需要保证 warning、长字段和附录展示语义不变。

## 七、本 PR 明确不做

- 不移动 `scripts/config_loaders.py`。
- 不移动 `scripts/export_md_scaffold.py`。
- 不移动 `scripts/i5b_markdown_display.py`。
- 不移动 `scripts/i5b_cluster_warning_display.py`。
- 不修改共享工具实现逻辑。
- 不修改 exporter 或 validator 真实实现。
- 不重新生成 `exports/**`。
