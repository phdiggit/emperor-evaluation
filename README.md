# 皇帝综合评价体系重构

本项目已重启，当前处于重构初期。工程骨架已经建立，但尚未开始新评分，也未迁移旧评分、旧排名、旧加总表或旧正式评分记录。

旧版所有评分、加总、排名、正式定档结果全部废弃。旧数据只可作为历史归档，不得作为新评分依据，不得回填到新体系。

## 当前状态

- 工程骨架已建立。
- `data/*.jsonl` 是事实源。
- `data/templates/*.json` 只是填写模板，不进入 `build_db` 导入流程。
- `evidence_cache.sqlite` 是生成物，不进 Git。
- Markdown 是审阅导出视图，不是主源。
- 文件治理与批次/主表边界以 `docs/数据层级与批次文件治理规则.md` 为准；已合并的 correction batch 不应长期留存。
- 下一阶段是迁移规则和已回源史料，不迁移旧评分。
- 当前可先阅读 `docs/数据规范.md`、`docs/ID命名规范.md` 和 `docs/第五项B试点计划.md`。
- 已进入第五项B试点准备；当前只生成矩阵骨架，不代表完成检索或评分。
- 任务005A已开始记录第五项B三人试点待回源检索线索；这些线索不代表已回源证据，不参与定档定分。

## 新流程

规则 → 正负证触发词 → 本地证据库 → 正负证矩阵 → 回源证据卡 → 相邻项切分 → 负证拦截 → 定档定分 → Markdown 导出

所有新评分必须经过正负证矩阵、证据卡、相邻项切分、负证拦截、定档定分流程。当前阶段只建设规则、数据结构和审阅出口，不生成总榜或排名。

本仓库禁止迁移旧评分、旧排名、旧加总表、旧正式评分记录和旧证据卡；未回源材料只能作为 `search_logs.jsonl` 的待回源线索。

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

该命令会同时导出证据卡索引和第五项B三人试点检索线索视图等基础审阅页；第五项B自动结算草案、自动结算规则敏感点清单和正式定档落地表由下方的 `export_i5b_auto_adjudication.py` 生成。

单独导出第五项B自动结算视图：

```bash
python scripts/export_i5b_auto_adjudication.py
```

导出第五项B三人试点矩阵骨架：

```bash
python scripts/run_matrix.py
```

运行测试：

```bash
pytest -q
```
