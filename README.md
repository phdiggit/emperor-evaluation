# 皇帝综合评价体系重构

本项目已重启，当前处于平台 schema 已 live、业务数据尚未切换写源的阶段。工程骨架和 PostgreSQL schema 基线已经建立，但尚未开始新评分，也未迁移旧评分、旧排名、旧加总表或旧正式评分记录。

旧版所有评分、加总、排名、正式定档结果全部废弃。旧数据只可作为历史归档，不得作为新评分依据，不得回填到新体系。

## 项目驱动文档

当前评分结构与业务口径以 [`docs/皇帝综合评价体系评分标准.md`](docs/皇帝综合评价体系评分标准.md) 为上位标准。当前仓库实现、数据迁移与子项进度若尚未完全对齐，应通过一致性审计和后续专门 PR 处理；新增入口不表示全部规则、数据和分数已完成迁移。

`docs/` 的方法论目录骨架与阅读顺序见 [`docs/README.md`](docs/README.md)。

## 当前状态

- 工程骨架已建立。
- `data/*.jsonl` 是事实源。
- 当前阶段：`platform-schema-live-data-not-cutover`。
- PostgreSQL schema 已完成 live apply；PostgreSQL 尚不是业务数据唯一写源。
- PostgreSQL business data 尚未迁移；`imports` / `import_rows` 只代表导入审计或脚手架记录，不等于正式 target business table 写入。
- `jsonl_write_frozen=false`，`postgres_unique_write_source=false`，`production_runtime_live=false`。
- `formal_scoring_released=false`，`formal_ranking_released=false`；不发布人物正式分、排名、阶段总榜或总榜。
- `data/configs/project_config.yml` 是当前全项目人工配置入口；展示细节、人工关键词表、正式评分规则和机器 registry 不放入该 YAML。
- `data/templates/*.json` 只是填写模板，不进入 `build_db` 导入流程。
- `evidence_cache.sqlite` 是生成物，不进 Git。
- Markdown 是审阅导出视图，不是主源。
- 文件治理与批次/主表边界以 `docs/数据结构与生成库/批次文件生命周期规则.md` 为准；已合并的 correction batch 不应长期留存。
- 后续 Epic / Gate 聚焦规则和已回源史料迁移；不迁移旧评分。
- 当前可先阅读 `docs/数据结构与生成库/数据主表字段规范.md`、`docs/数据结构与生成库/稳定ID命名规范.md` 和 `exports/markdown_views/第五项B/人工审核/入口/第五项B试点计划.md`。
- 已进入第五项B试点准备；当前只生成矩阵骨架，不代表完成检索或评分。
- 任务005A已开始记录第五项B三人试点待回源检索线索；这些线索不代表已回源证据，不参与定档定分。
- V3.2 已确定 1440 正收益总盘、0—300 历史负债及各大项权重。当前方案 C 只表示实现和发布仍分阶段推进：子项证据、档位映射、规则与算法版本审查、回归验证和正式发布门槛未完成前，不发布人物正式分、排名、阶段总榜或总榜。

## 文件治理当前口径

当前继续采用 `data/*.jsonl` 事实源和 Markdown 审阅视图；SQLite 生成库是本地兼容缓存，当前基线记录为 `sqlite_build_operational=true`。`python scripts/build/build_db.py` 由 `db/sqlite/001_cache.sql` 生成 SQLite cache schema，不再把 PostgreSQL 取向的 `db/schema.sql` 交给 SQLite 执行；`db/schema.sql` / `db/postgres/001_init.sql` 继续作为 PostgreSQL schema 基线。`docs/` 当前层只保留规则、方法论、运行说明和治理入口，`exports/governance/文档治理盘点报告.md` 作为按需生成的 docs 治理报告入口，历史治理诊断材料仅保留在 `archive/docs/` 追溯，不作为当前事实源。

当前不引入新的缓存或中间件；检索与评分消费统一收敛到 retrieval v3 PostgreSQL 工作流。

多余文件、归档候选和删除候选必须另开专门 Issue 处理，不能在普通业务 PR 中顺手删除或移动。

## 当前 I5B 数据链

第五项B当前只保留 retrieval v3 native workflow：

```text
source candidate -> claim cache -> event group -> material -> candidate
-> identity -> binding -> factor judgment -> rule score -> coverage controller
```

执行步骤见 [`docs/数据结构与生成库/I5B数据链运行流程.md`](docs/数据结构与生成库/I5B数据链运行流程.md)。所有检索数据库入口默认连接 `EMPEROR_EVAL_RETRIEVAL_V3_DSN` 的 `retrieval_v3` schema；不得按裸数字 ID 跨数据库拼接 lineage。

## 运行命令

安装 Python 依赖：

```bash
python -m pip install -r requirements.txt
```

运行当前保留的全部测试：

```bash
python -m pytest -q
```

校验全项目人工配置入口：

```bash
python scripts/validate/validate_project_config.py
```

编译检查当前脚本和测试：

```bash
python -m compileall -q scripts tests
```

查看 retrieval v3 coverage controller：

```bash
python scripts/dev/retrieval_v3_coverage_controller.py --help
```

查看 retrieval v3 scorer：

```bash
python scripts/dev/retrieval_v3_rule_scorer.py --help
```

生成只读 item raw signal：

```bash
python scripts/dev/retrieval_v3_i5b_item_raw_score.py --help
```

`tests/current_workflow_tests.txt` 列出当前全部测试；仓库不再保留其他工作流测试。

## GitHub 发布

推荐使用本地持久认证而不是依赖 Codex 的临时 GitHub 会话。稳定做法是：

1. 将 `origin` 切到 SSH。
2. 用 `gh auth login` 保存长期登录态。
3. 通过已认证的 `gh` CLI 发布；当前分支任务若明确禁止 PR，则只推送分支。

详细步骤见 [`docs/展示与协作/GitHub发布与认证规范.md`](docs/展示与协作/GitHub发布与认证规范.md)。
