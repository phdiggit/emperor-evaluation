# 人工复核配置退役说明

本目录不再作为第五项B人工复核配置入口。

当前入口统一为：

```text
data/configs/project_config.yml
```

已退役内容：

- 人工长期维护的第五项B检索关键词基础 / 补丁配置。
- 第五项B专属证据簇裁判提示 JSON。
- 配置说明 comments 文件机制。

后续检索词由 Codex、search task generator 或 source passage / trigger_terms / existing evidence 抽取生成，人工只复核生成结果，不在本目录长期维护词表。

人工复核提示规则不再作为人工配置项暴露；现有 display-only warning 由脚本内部默认值承载，不出分、不定档、不排名、不自动发布、不改变证据或裁判语义。
