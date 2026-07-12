# JSONL batch archive

`archive/data/jsonl_batches/` 仅保留历史追溯材料。

这里的文件不是当前事实源，不得被 `build_db`、validator 或 exporter 当作默认输入。

后续任务若需要重新启用某个归档文件，必须通过受审查的 `data/batches/<batch_id>/` manifest 或 canonical 合并路径重新进入当前数据层，不得直接从 archive 读取。
