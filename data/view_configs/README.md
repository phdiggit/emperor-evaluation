# `data/view_configs/` 兼容层说明

本目录下的以下旧碎配置文件目前保留，但都只作为短期 `fallback-only` 兼容层使用，不再是主维护入口：

- `i5b_trial_targets.jsonl`
- `i5b_expanded_batch1_targets.jsonl`
- `i5b_net_evidence_targets.jsonl`
- `i5b_expanded_candidate_pool.jsonl`

对应的主维护入口已迁移到以下两个中文 formatted JSON 文件：

- `data/configs/视图配置/第五项B_人物池.json`
- `data/configs/视图配置/第五项B_视图分组.json`

维护约定：

- 需要编辑第五项B人物主信息时，改 `第五项B_人物池.json`
- 需要编辑三人试点、扩展第一批、净证据导出目标等分组时，改 `第五项B_视图分组.json`
- 本目录中的旧 JSONL 不建议继续追加新主逻辑，只保留给现有脚本的短期 fallback
- 机器行式数据继续允许使用 JSONL；用户主维护入口优先使用可读性更高的 formatted JSON

当前旧配置与新主入口的对应关系：

- `configs/i5b_trial_targets.json` / `data/view_configs/i5b_trial_targets.jsonl`
  - 主入口：`data/configs/视图配置/第五项B_视图分组.json` 中的 `第五项B_三人试点`
- `data/view_configs/i5b_expanded_batch1_targets.jsonl`
  - 主入口：`data/configs/视图配置/第五项B_视图分组.json` 中的 `第五项B_扩展第一批`
- `data/view_configs/i5b_net_evidence_targets.jsonl`
  - 主入口：`data/configs/视图配置/第五项B_视图分组.json` 中的 `第五项B_净证据导出目标`
- `data/view_configs/i5b_expanded_candidate_pool.jsonl`
  - 主入口：`data/configs/视图配置/第五项B_人物池.json`
