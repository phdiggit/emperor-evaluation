# 人工复核配置

本目录是人工复核配置主入口。

约定：

- 用户可编辑配置使用 formatted JSON。
- JSON 顶层使用 array，每个元素为 object。
- 中文内容必须 UTF-8 直写，不使用 `\uXXXX` 转义。
- 机器行式数据仍可在其他明确数据层使用 JSONL。

第五项B检索关键词配置主入口：

- `第五项B_检索关键词基础.json`
- `第五项B_检索关键词补丁.json`

分工：

- 基础配置记录第五项B通用检索画像，例如用人任贤、授权与分权、纳谏与表达入口、容人容错、功臣与重臣处置、高压控制与寒蝉风险。
- 补丁配置记录少量人物级检索补充，用于提示特定人物的常见检索词和噪音压制词。
- 两类配置只用于检索画像与人工复核辅助，不代表证据结论、评分、裁判结论、正式定档或排名。
- 新增或修改关键词后，必须运行 `python scripts/validate_review_configs.py`。

迁移状态：

- 未发现被跟踪的旧 `data/review_configs/search_keyword_profiles.jsonl`。
- 未发现被跟踪的旧 `data/review_configs/search_keyword_overrides.jsonl`。
- 旧 review config JSONL 未作为生产入口保留；当前主维护入口为本目录下的 formatted JSON。
