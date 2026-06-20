# 人工复核配置

本目录是人工复核配置主入口。

约定：

- 用户可编辑配置使用 formatted JSON。
- JSON 顶层使用 array，每个元素为 object。
- 中文内容必须 UTF-8 直写，不使用 `\uXXXX` 转义。
- 机器行式数据仍可在其他明确数据层使用 JSONL。

第五项B检索关键词配置的预留主入口：

- `第五项B_检索关键词基础.json`
- `第五项B_检索关键词补丁.json`

迁移状态：

- 未发现被跟踪的旧 `data/review_configs/search_keyword_profiles.jsonl`。
- 未发现被跟踪的旧 `data/review_configs/search_keyword_overrides.jsonl`。
- 因无旧配置源，本次不凭空创建检索关键词内容。
