# config_loaders.py 迁移前依赖审计

本文档记录 `scripts/config_loaders.py` 迁移到 `scripts/shared/` 的依赖面、公共 API、路径常量、迁移风险和验证要求。本次实迁只移动真实实现并保留旧路径 wrapper，不改变任何配置读取行为或业务语义。

## 一、模块当前位置

- 当前真实实现：`scripts/shared/config_loaders.py`
- 旧路径兼容入口：`scripts/config_loaders.py`
- 旧路径 `scripts/config_loaders.py` 必须保留短 wrapper。

## 二、模块职责

- 加载第五项B人物池：`load_i5b_person_pool`
- 加载视图分组：`load_i5b_view_groups`、`get_i5b_group`、`get_i5b_group_persons`
- 加载三人试点、扩展第一批、净证据导出目标：`get_i5b_trial_config`、`get_i5b_trial_targets`、`get_i5b_expanded_batch1_targets`、`get_i5b_net_evidence_targets`
- 加载扩展候选池：`get_i5b_expanded_candidate_pool_rows`
- 加载检索关键词基础配置：`load_i5b_keyword_profiles`、`get_i5b_keyword_profiles`
- 加载检索关键词补丁配置：`load_i5b_keyword_overrides`、`get_i5b_keyword_overrides`
- 加载证据簇裁判提示配置：`load_i5b_cluster_warning_rules`、`get_i5b_cluster_warning_rules`、`get_i5b_cluster_warning_rule`
- 为 exporter / validator / tests 提供统一配置入口和路径常量。
- 当前模块不加载第五项B markdown view 展示字典；该职责已由 `scripts/shared/i5b_markdown_display.py` 承担。但它与 markdown view 相关导出目标、人工审核目标和证据链目标存在间接耦合。

## 三、主要导入方

以下为本次审计使用的 ripgrep 结果，覆盖 `scripts/export/**`、`scripts/validate/**`、`scripts/run_matrix.py`、`tests/**` 和仍在 `scripts/` 根目录的脚本。

```text
scripts/export_md.py: import config_loaders
scripts/run_matrix.py: import config_loaders
scripts/export/export_i5b_auto_adjudication.py: import config_loaders
scripts/export/export_i5b_auto_adjudication.py: from config_loaders import load_i5b_cluster_warning_rules
scripts/export/export_i5b_expanded_batch1.py: import config_loaders
scripts/export/export_i5b_net_evidence.py: import config_loaders
scripts/export/export_project_doc_views.py: import config_loaders
scripts/validate/validate_human_readable_markdown_exports.py: import config_loaders
tests/test_config_loaders.py: spec-loads scripts/config_loaders.py and monkeypatches loader paths
tests/test_config_comments.py: spec-loads scripts/config_loaders.py and checks config loader paths do not point to comments files
tests/test_export_i5b_expanded_batch1.py: monkeypatches export module config_loaders.I5B_VIEW_GROUPS_PATH
tests/test_export_i5b_net_evidence.py: monkeypatches net evidence module config_loaders.I5B_VIEW_GROUPS_PATH
tests/test_export_md_trial_targets.py: monkeypatches export_md.config_loaders.I5B_VIEW_GROUPS_PATH
tests/test_export_project_doc_views.py: monkeypatches doc_views.config_loaders.I5B_PERSON_POOL_PATH
tests/test_i5b_auto_adjudication.py: uses auto.config_loaders trial config and view group path
tests/test_run_matrix.py: monkeypatches run_matrix.config_loaders.I5B_VIEW_GROUPS_PATH
```

## 四、被依赖的公共 API

当前真实公共 API 和路径常量如下：

- `ROOT`
- `I5B_PERSON_POOL_PATH`
- `I5B_VIEW_GROUPS_PATH`
- `I5B_KEYWORD_PROFILES_PATH`
- `I5B_KEYWORD_OVERRIDES_PATH`
- `I5B_CLUSTER_WARNING_RULES_PATH`
- `DEFAULT_I5B_ITEM`
- `DEFAULT_I5B_SUBITEM`
- `DEFAULT_I5B_NET_EVIDENCE_PATH_TEMPLATE`
- `I5B_CANDIDATE_POOL_REQUIRED_FIELDS`
- `load_json_array`
- `load_i5b_person_pool`
- `load_i5b_view_groups`
- `get_i5b_group`
- `get_i5b_group_persons`
- `get_i5b_trial_config`
- `get_i5b_trial_targets`
- `get_i5b_expanded_batch1_targets`
- `get_i5b_net_evidence_targets`
- `get_i5b_expanded_candidate_pool_rows`
- `load_i5b_keyword_profiles`
- `load_i5b_keyword_overrides`
- `row_matches_scope`
- `get_i5b_keyword_profiles`
- `get_i5b_keyword_overrides`
- `load_i5b_cluster_warning_rules`
- `get_i5b_cluster_warning_rules`
- `get_i5b_cluster_warning_rule`

说明：当前代码没有名为 `get_i5b_targets` 的函数；对应的真实目标入口是 `get_i5b_trial_targets`、`get_i5b_expanded_batch1_targets` 和 `get_i5b_net_evidence_targets`。后续迁移不得新增同名别名来改变 API 面，除非另开兼容性 PR。

## 五、路径风险

- 当前 `ROOT = Path(__file__).resolve().parents[1]`。迁移到 `scripts/shared/config_loaders.py` 后必须改为 `Path(__file__).resolve().parents[2]`。
- 所有 `data/configs/**` 路径不能漂移，尤其是 `视图配置`、`人工复核配置` 下的第五项B配置。
- `data/configs/配置说明/**` 只用于说明，不能被业务 loader 当真实配置读取。
- `*.comments.json` 文件不能被业务 loader 当真实配置读取。
- 中文路径必须保持 UTF-8 读取和写入，不得退化为系统默认编码。
- 测试通过 monkeypatch 替换路径常量时，不能误用真实配置路径，也不能把临时 `配置说明` 文件纳入业务 loader。

## 六、迁移风险

- exporter 和 validator 同时依赖该模块，路径改错会导致批量导出或验证失败。
- config comments validator 依赖 config loader 常量判断真实配置路径，常量漂移会影响 comments 排除规则。
- 人物池或视图分组读取错误会影响导出范围、试点目标、扩展第一批目标和矩阵运行目标。
- 检索关键词基础/补丁配置读取错误会影响人工复核和检索线索流程。
- 证据簇裁判提示配置读取错误会影响 warning display-only 流程。
- `load_json_array` 的顶层数组和对象校验语义不能改变，否则会改变配置错误暴露方式。
- shared 迁移后旧路径 wrapper 必须继续支持所有旧 import，包括 `import config_loaders` 和 `from config_loaders import load_i5b_cluster_warning_rules`。

## 七、迁移策略

- 单独 PR 实迁 `config_loaders.py`。
- 真实实现已迁移到 `scripts/shared/config_loaders.py`。
- 旧路径 `scripts/config_loaders.py` 保留短 wrapper。
- 已迁移 exporter/validator 优先改 shared 新路径；仍未迁移脚本允许继续走旧路径 wrapper。
- 必须验证所有路径常量不漂移，尤其是 `I5B_PERSON_POOL_PATH`、`I5B_VIEW_GROUPS_PATH`、`I5B_KEYWORD_PROFILES_PATH`、`I5B_KEYWORD_OVERRIDES_PATH` 和 `I5B_CLUSTER_WARNING_RULES_PATH`。
- 必须验证 config comments loader 不误读 `配置说明` 目录或 `*.comments.json` 文件。
- 必须验证人物池、视图分组、关键词基础/补丁、证据簇提示、导出目标和旧路径 import 兼容。

## 八、本 PR 明确不做

- 不改变 `config_loaders.py` API 行为。
- 不改变配置读取路径或业务语义。
- 不改配置读取逻辑。
- 不改真实配置文件。
- 不改 exporter、validator、pipeline 或 `scripts/shared/**` 实现。
- 不改导出产物。
- 不改真实证据数据、评分、排名、正式定档、证据事实或证据簇裁判结论。
