# tests 目录治理

`tests/` 继续进入 Git 管理；测试运行产生的缓存、覆盖率文件、SQLite 数据库、临时 Markdown 导出和 `.tmp/` 内容不得提交。

默认开发守门使用：

```bash
pytest -q
```

默认只收集 `current_workflow_tests.txt` 登记的 retrieval v3 native claim-cache 当前链条，包括 claim/object-source、candidate/binding、factorization/scorer 和运行配置测试。历史 exporter、旧批次评分、旧对象池以及 docs/agents/legacy-wrapper 等独立治理测试不再进入默认收集；治理继续分别使用 `validate_all.py`、`docs_tool.py check --worktree`、`repo_tool.py agents-check` 和 CI 点名测试。

需要运行全部历史工作流时显式使用：

```bash
pytest -q --all-workflows
```

点名单个未登记测试文件时仍会运行，便于窄回归：

```bash
pytest -q tests/test_object_pool_importer.py
```

需要按 marker 查看重型或导出相关测试时使用：

```bash
pytest -q -m "export_full or integration or slow or snapshot or db"
```

新增测试按以下口径归类：

- `export_full`：运行 `export_md.py --profile all/detail/i5b-*`、真实 exporter CLI，或可能重写 `exports/**` 的测试。
- `integration`：跨多个脚本、真实仓库布局、Git、文档登记表或导出目录的测试。
- `slow`：明显不适合每个小 PR 默认快速反馈的长耗时测试。
- `snapshot`：golden/snapshot 风格输出检查；必须保持小而明确，不把整篇大型 Markdown 作为默认快照。
- `db`：构建、读取或检查 SQLite / 数据库副产物的测试。

新增 exporter 测试优先使用 `tmp_path` 或 monkeypatch 到临时输出目录。确需覆盖真实导出入口时，必须加上相应 marker，并确认测试结束后不留下可提交的生成物。
