# 皇帝综合评价体系重构

本项目已重启，当前处于重构初期。工程骨架已经建立，但尚未开始新评分，也未迁移旧评分、旧排名、旧加总表或旧正式评分记录。

旧版所有评分、加总、排名、正式定档结果全部废弃。旧数据只可作为历史归档，不得作为新评分依据，不得回填到新体系。

## 项目驱动文档

当前评分结构与业务口径以 [`docs/皇帝综合评价体系评分标准.md`](docs/皇帝综合评价体系评分标准.md) 为上位标准。当前仓库实现、数据迁移与子项进度若尚未完全对齐，应通过一致性审计和后续专门 PR 处理；新增入口不表示全部规则、数据和分数已完成迁移。

`docs/` 的方法论目录骨架与阅读顺序见 [`docs/README.md`](docs/README.md)。

## 当前状态

- 工程骨架已建立。
- `data/*.jsonl` 是事实源。
- `data/templates/*.json` 只是填写模板，不进入 `build_db` 导入流程。
- `evidence_cache.sqlite` 是生成物，不进 Git。
- Markdown 是审阅导出视图，不是主源。
- 文件治理与批次/主表边界以 `docs/数据结构与生成库/批次文件生命周期规则.md` 为准；已合并的 correction batch 不应长期留存。
- 下一阶段是迁移规则和已回源史料，不迁移旧评分。
- 当前可先阅读 `docs/数据结构与生成库/数据主表字段规范.md`、`docs/数据结构与生成库/稳定ID命名规范.md` 和 `exports/markdown_views/第五项B/人工审核/入口/第五项B试点计划.md`。
- 已进入第五项B试点准备；当前只生成矩阵骨架，不代表完成检索或评分。
- 任务005A已开始记录第五项B三人试点待回源检索线索；这些线索不代表已回源证据，不参与定档定分。
- V3.2 已确定 1440 正收益总盘、0—300 历史负债及各大项权重。当前方案 C 只表示实现和发布仍分阶段推进：子项证据、档位映射、规则与算法版本审查、回归验证和正式发布门槛未完成前，不发布人物正式分、排名、阶段总榜或总榜。

## 文件治理当前口径

当前继续采用 `data/*.jsonl` 事实源、SQLite 生成库、Markdown 审阅视图的三层结构；`docs/` 当前层只保留规则、方法论、运行说明和治理入口，`exports/governance/文档治理盘点报告.md` 作为按需生成的 docs 治理报告入口，历史治理诊断材料仅保留在 `archive/docs/` 追溯，不作为当前事实源。

当前不引入外部数据库、缓存或中间件。后续 P1 优先处理 `scripts/export/export_md.py` 拆分和指定导出机制，但这类拆分应另开专门 Issue。

多余文件、归档候选和删除候选必须另开专门 Issue 处理，不能在普通业务 PR 中顺手删除或移动。

## 新流程

规则 → 正负证触发词 → 本地证据库 → 正负证矩阵 → 回源证据卡 → 相邻项切分 → 负证拦截 → 定档定分 → Markdown 导出

所有新评分必须经过正负证矩阵、证据卡、相邻项切分、负证拦截、定档定分流程。当前阶段只建设规则、数据结构和审阅出口，不生成总榜或排名。

本仓库禁止迁移旧评分、旧排名、旧加总表、旧正式评分记录和旧证据卡；未回源材料只能作为 `search_logs.jsonl` 的待回源线索。

## 运行命令

校验证据 JSONL：

```bash
python scripts/validate/validate_evidence.py
```

生成 SQLite 运行库：

```bash
python scripts/build/build_db.py
```

导出 Markdown 审阅视图：

```bash
python scripts/export/export_md.py
```

该命令默认只运行 `main` profile，生成证据卡索引、证据组裁量索引、专题锚点索引和项目检索包索引等综合入口。子项细节、试点 batch、审计视图、自动结算必须显式指定 profile 或调用专用脚本；旧全量导出行为使用 `python scripts/export/export_md.py --profile all`。

查看可用导出 profile：

```bash
python scripts/export/export_md.py --list-profiles
```

单独导出第五项B自动结算视图：

```bash
python scripts/export/export_i5b_auto_adjudication.py
```

导出第五项B三人试点矩阵骨架：

```bash
python scripts/matrix/run_matrix.py
```

运行测试：

```bash
pytest -q
```

测试目录仍进入 Git 管理，缓存、覆盖率、SQLite 和临时导出副产物不进入版本控制。默认不排除 pytest marker；需要显式查看导出全量、集成、慢测、snapshot 或数据库相关测试时运行：

```bash
pytest -q -m "export_full or integration or slow or snapshot or db"
```

新增测试归类规则见 [`tests/README.md`](tests/README.md)。

## GitHub 发布

推荐使用本地持久认证而不是依赖 Codex 的临时 GitHub 会话。稳定做法是：

1. 将 `origin` 切到 SSH。
2. 用 `gh auth login` 保存长期登录态。
3. 通过 `scripts/publish_pr.ps1` 创建 PR，并在需要时切到 ready for review。

详细步骤见 [`docs/展示与协作/GitHub发布与认证规范.md`](docs/展示与协作/GitHub发布与认证规范.md)。
