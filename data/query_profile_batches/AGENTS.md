# AGENTS.md

本文件只约束 `data/query_profile_batches/**` 内检索包的稳定边界。I5B 全流程执行手册见 [`../../docs/数据结构与生成库/I5B数据链运行流程.md`](../../docs/数据结构与生成库/I5B数据链运行流程.md)。

## 检索包口径

- 检索包是回源基准，不是证据、证据卡、档位、分值或排名。
- 人物级检索包必须持久化到同一批次 JSONL；不得只留在 `.tmp`、日志或对话上下文。
- `core_positive_objects`、`supplemental_objects`、`negative_or_reversal_objects` 默认都进入待回源队列。
- `adjacent_split_objects` 记录相邻项切分和排除提示。
- 人物、臣僚、机构、事件等对象若有本名、字、封爵、官称、庙号、谥号、常见异写或史书称谓，应在检索画像或候选对象中保留别名线索；别名用于补检和对象归并，不等同于新增对象。
- 脚本无命中、弱命中或命中非目标源，不得判定为无史料；继续人工补检或记录缺口。
- 显式 query cap、超时、连续错误或别名未检索造成的 skipped plans 必须记录为待处理缺口，不得静默跳过检索包对象。声明过别名的对象，只有所有可用别名都检索或明确排除后，才可按无命中处理。

## 对象链红线

- `raw_objs` 必须保持原始粒度，不提前合并、定强弱或写评分加工。
- 同一历史对象不得因本名、官称、爵号、谥号或别名差异重复插入；对象 payload 应交由别名归一层归并到 canonical object。
- 所有 `raw_objs` 必须有 `obj_srcs` 史料链。
- `raw_objs.note` 只写对象身份或事件事实，不写规则、方向、评分、档位。
- `obj_srcs` 必须绑定具体 `emp_obj_id`，避免同一原始对象跨皇帝串料。
- `obj_attrs.talent_quality` 必须有 `doc_id`；属性史源最好同时出现在该对象 `obj_srcs`。

## 工具路由

- 召回和摘录定位使用 `scripts/dev/retrieval_v3_clean_runner.py` 与对象级 source cache；默认不写数据库。
- 已回源 claim 通过 retrieval v3 material intake、candidate review、identity 与 binding consumer 进入正式链。
- 对象别名归一和重复对象拦截使用 `scripts/dev/object_pool_aliases.py`；检索不到可用史料时，应先尝试对象别名补检，再记录缺口或跳过。
- 从 claim 到评分与覆盖报告的流程按 I5B 数据链运行流程文档执行。

## 验证

- 使用对象导入工具后，必须校验全库不存在无史源 `raw_objs`。
- 新增或补充人物检索包后，应离线遍历 profile，确认对象有 search plan 且 skipped plans 已显式记录。
