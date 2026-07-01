# AGENTS.md

本文件约束 `scripts/dev/**` 下开发辅助工具。根 `AGENTS.md` 与 `scripts/AGENTS.md` 负责通用边界；对象池相关工具的具体口径以本文件为准。

## 职责边界

- `scripts/dev/**` 工具只做开发辅助、召回、校验、导入编排和本地报告，不承载正式评分、证据裁判、档位结论或排名语义。
- 开发工具可以降低重复劳动，但不能替代史料理解；工具输出必须经过人工或 Codex 阅读判断后，才能进入正式对象池或后续证据链。
- 涉及中文 JSON/Markdown 输出时使用 UTF-8、`ensure_ascii=False`、稳定缩进；不要用 PowerShell inline 传递长中文正文。

## 摘录池工具

- `source_excerpt_pool.py` 是 review-first 召回工具：从检索包生成对象查询计划，检索 Wikisource，抓取目标史料页附近摘录。
- 摘录池默认不写数据库；输出到显式指定文件或 `.tmp/**`，不得直接改正式 `data/**`。
- 摘录池的“无命中”只表示机器第一轮未召回，不得作为对象无史料、可跳过或可删除的依据。
- 摘录池应保留检索计划、标题过滤、错误记录和摘录上下文，便于继续人工补检。
- 网络超时、页面缺失或非目标源命中应记录为错误或弱命中，不应中断整个批次。

## 对象池导入工具

- `object_pool_importer.py` 只导入已经回源并人工判断过的对象载荷；不得把检索包对象或摘录池结果未经判断直接写库。
- `object_pool_importer.py --template-from-profile` 只从检索包生成待填写模板，属于 review-first 辅助；模板中的史源、方向、规则、note 和属性仍需阅读史料后补齐。
- 导入载荷可以使用单 payload 或 `payloads` 批量格式；对象属性放在对象自身 `attrs` 中，并且属性史源必须已经作为该对象的史料关联出现。
- 导入必须保持事务边界，支持 dry-run，并在提交前后校验不存在无史料 `raw_objs`。
- 导入载荷中的每个对象必须有至少一条史料关联；对象名唯一性依赖数据库约束和原始对象粒度，不在脚本里做加工合并。
- 写入 `obj_srcs` 时必须同时写 `obj_id` 与 `emp_obj_id`，冲突键使用 `emp_obj_id + doc_id + item_id + rule_id + direction`，避免同一原始对象跨皇帝覆盖史料。
- `raw_objs.note` 不写评分、方向、规则或相邻项切分；`obj_srcs.note` 写史料对规则维度和事实方向的帮助。

## 测试

- 修改 `source_excerpt_pool.py` 后运行 `python -m pytest tests/test_source_excerpt_pool.py -q`。
- 修改 `object_pool_importer.py` 后运行 `python -m pytest tests/test_object_pool_importer.py -q`。
- 同时修改两个工具时运行两组 focused tests；网络实测可用小样本验证，但不得要求测试依赖外网。
