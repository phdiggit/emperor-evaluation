# 皇帝综合评价体系重构

本项目已重启，当前处于重构初期。工程骨架已经建立，但尚未开始新评分，也未迁移旧评分、旧排名、旧加总表或旧正式评分记录。

旧版所有评分、加总、排名、正式定档结果全部废弃。旧数据只可作为历史归档，不得作为新评分依据，不得回填到新体系。

## 当前状态

- 工程骨架已建立。
- `data/*.jsonl` 是事实源。
- `evidence_cache.sqlite` 是生成物，不进 Git。
- Markdown 是审阅导出视图，不是主源。
- 下一阶段是迁移规则和已回源史料，不迁移旧评分。

## 新流程

规则 → 正负证触发词 → 本地证据库 → 正负证矩阵 → 回源证据卡 → 相邻项切分 → 负证拦截 → 定档定分 → Markdown 导出

所有新评分必须经过正负证矩阵、证据卡、相邻项切分、负证拦截、定档定分流程。当前阶段只建设规则、数据结构和审阅出口，不生成总榜或排名。

## 运行命令

校验证据 JSONL：

```bash
python scripts/validate_evidence.py
```

生成 SQLite 运行库：

```bash
python scripts/build_db.py
```

导出 Markdown 审阅视图：

```bash
python scripts/export_md.py
```

运行测试：

```bash
pytest -q
```
