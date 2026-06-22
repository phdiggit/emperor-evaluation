# i5b_markdown_display.py 迁移前依赖审计

本文档记录 `scripts/i5b_markdown_display.py` 迁移到 `scripts/shared/` 前后的依赖面、公共 API、风险和维护要求。#196 已完成实迁，但本文保留迁移风险与验证要求，作为后续维护参考。

#196 已完成实迁：

- 新真实实现：`scripts/shared/i5b_markdown_display.py`
- 旧路径 wrapper：`scripts/i5b_markdown_display.py`

## 一、模块当前位置

- 新真实实现：`scripts/shared/i5b_markdown_display.py`
- 旧路径兼容 wrapper：`scripts/i5b_markdown_display.py`
- `DEFAULT_DISPLAY_CONFIG_PATH` 仍指向 `data/configs/导出展示配置/第五项B_markdown_view.json`

## 二、模块职责

- 字段中文标签：`display_field_label`
- 枚举值中文化：`display_value`
- 展示配置加载：`load_display_dictionary`
- Markdown 表格渲染：`render_markdown_table`
- Markdown kv 渲染：`render_markdown_kv`
- 长字段附录：`render_appendix_page` / `AppendixEntry`
- 人工审核表格字段：`human_review_table_fields`
- 机器字段名保留/隐藏策略：`keep_machine_field_name` 与 `display_field_label`
- 表格展示策略：`table_render_policy`、`list_render_policy`、`field_render_policies` 相关配置和渲染分支
- 长列表与表格单元格策略：`render_long_list`、`render_table_cell`

## 三、主要导入方

以下为本次审计使用的 ripgrep 结果，覆盖 `scripts/export/**`、`scripts/validate/**`、`tests/**` 和仍在 `scripts/` 根目录的脚本。

```text
scripts/export/export_i5b_auto_adjudication.py: from shared.i5b_markdown_display import human_review_table_fields as configured_human_review_table_fields
scripts/export/export_i5b_expanded_batch1.py: from shared.i5b_markdown_display import AppendixEntry, display_field_label, display_value, human_review_table_fields, load_display_dictionary, render_appendix_page, render_markdown_kv, render_markdown_table
scripts/export/export_i5b_net_evidence.py: from shared.i5b_markdown_display import AppendixEntry, display_field_label, display_value, human_review_table_fields, load_display_dictionary, render_appendix_page, render_markdown_table
scripts/export/export_i5b_views.py: from shared.i5b_markdown_display import display_field_label, display_value, human_review_table_fields, load_display_dictionary
scripts/export/export_project_doc_views.py: from shared.i5b_markdown_display import display_field_label, display_value, load_display_dictionary
scripts/validate/validate_human_readable_markdown_exports.py: from shared.i5b_markdown_display import display_field_label, human_review_table_fields, load_display_dictionary
scripts/run_matrix.py: from i5b_markdown_display import display_field_label, display_value, load_display_dictionary
tests/test_i5b_markdown_display.py: from shared.i5b_markdown_display import human_review_table_fields, load_display_dictionary, render_long_list, render_table_cell
tests/test_scripts_shared_directory_plan.py: asserts scripts/shared/__init__.py does not import i5b_markdown_display
tests/test_scripts_export_directory_layout.py: asserts i5b_markdown_display.py remains outside scripts/export/
```

## 四、被依赖的公共 API

当前被直接 import 的公共 API 如下：

- `AppendixEntry`
- `display_field_label`
- `display_value`
- `human_review_table_fields`
- `load_display_dictionary`
- `render_appendix_page`
- `render_markdown_kv`
- `render_markdown_table`
- `render_long_list`
- `render_table_cell`

另有配置路径和默认字段集合虽未全部被直接 import，但属于迁移时必须保持语义稳定的公共行为：

- `DEFAULT_DISPLAY_CONFIG_PATH`
- `DEFAULT_HUMAN_REVIEW_TABLE_FIELDS`
- `table_render_policy`
- `list_render_policy`
- `field_render_policies`
- `keep_machine_field_name`

## 五、迁移风险

- 展示语义变化风险：字段标签、枚举值中文化、布尔值中文化和列表展示策略会直接影响人工阅读型 Markdown。
- 人工审核表头白名单失效风险：`human_review_table_fields` 与 `DEFAULT_HUMAN_REVIEW_TABLE_FIELDS` 共同决定多类人工审核表格列顺序和列集合。
- 长字段附录链接变化风险：`AppendixEntry`、`render_table_cell`、`render_appendix_page`、`render_appendix_link` 与 anchor 生成规则共同决定附录链接和正文锚点。
- machine key 是否保留变化风险：`display_field_label` 根据 `keep_machine_field_name` 决定是否在中文标签后保留机器字段名。
- validator 与 exporter 同时依赖造成路径问题：`scripts/export/**` 与 `scripts/validate/**` 已改走 shared 新路径，旧路径 wrapper 必须继续可导入。
- 测试中旧路径 import 兼容风险：display 测试必须同时覆盖 `shared.i5b_markdown_display` 和旧路径 `i5b_markdown_display`。
- 展示配置路径漂移风险：`DEFAULT_DISPLAY_CONFIG_PATH` 依赖仓库根目录下 `data/configs/导出展示配置/第五项B_markdown_view.json`，后续维护不能因 shared 层级变化改变配置定位。

## 六、建议迁移策略

- #196 已单独实迁 `i5b_markdown_display.py`，没有并入普通 exporter、validator、pipeline 或业务数据 PR。
- 真实实现位于 `scripts/shared/i5b_markdown_display.py`。
- 旧路径 `scripts/i5b_markdown_display.py` 保留短 wrapper，并继续支持旧路径 import。
- 已迁移 exporter/validator 优先使用 shared 新路径；仍未迁移脚本允许继续走旧路径 wrapper。
- 后续维护必须继续验证旧路径 wrapper 和新路径模块都可 import。
- 后续维护必须跑人审导出 validator、机器审计导出相关验证、表头白名单测试和 display 相关测试。
- 后续维护必须确认字段标签、值映射、长字段附录、人工审核表头白名单、machine key 保留/隐藏策略没有语义变化。

## 七、本 PR 明确不做

- 不迁移 `config_loaders.py`。
- 不改展示策略。
- 不改展示配置。
- 不改 exporter 或 validator 导出/校验逻辑，仅更新 import 路径。
- 不改导出产物。
- 不改真实证据数据、评分、排名、正式定档、证据事实或证据簇裁判结论。
