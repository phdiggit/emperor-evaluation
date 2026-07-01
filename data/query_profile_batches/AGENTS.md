# AGENTS.md

本文件只约束 `data/query_profile_batches/**` 内检索包的稳定边界。I5B 全流程执行手册见 [`../../docs/数据结构与生成库/I5B数据链运行流程.md`](../../docs/数据结构与生成库/I5B数据链运行流程.md)。

## 检索包口径

- 检索包是回源基准，不是证据、证据卡、档位、分值或排名。
- 人物级检索包必须持久化到同一批次 JSONL；不得只留在 `.tmp`、日志或对话上下文。
- `core_positive_objects`、`supplemental_objects`、`negative_or_reversal_objects` 默认都进入待回源队列。
- `adjacent_split_objects` 记录相邻项切分和排除提示。
- 脚本无命中、弱命中或命中非目标源，不得判定为无史料；继续人工补检或记录缺口。
- 显式 query cap 造成的 skipped plans 必须记录为待处理缺口，不得静默跳过检索包对象。

## 对象链红线

- `raw_objs` 必须保持原始粒度，不提前合并、定强弱或写评分加工。
- 所有 `raw_objs` 必须有 `obj_srcs` 史料链。
- `raw_objs.note` 只写对象身份或事件事实，不写规则、方向、评分、档位。
- `obj_srcs` 必须绑定具体 `emp_obj_id`，避免同一原始对象跨皇帝串料。
- `obj_attrs.talent_quality` 必须有 `doc_id`；属性史源最好同时出现在该对象 `obj_srcs`。

## 工具路由

- 召回和摘录定位使用 `scripts/dev/source_excerpt_pool.py`；它不写数据库。
- 已回源、已人工判断的对象 payload 才能交给 `scripts/dev/object_pool_importer.py`。
- 从对象链到证据簇、结果和日志的流程按 I5B 数据链运行流程文档执行。

## 验证

- 使用对象导入工具后，必须校验全库不存在无史源 `raw_objs`。
- 新增或补充人物检索包后，应离线遍历 profile，确认对象有 search plan 且 skipped plans 已显式记录。
