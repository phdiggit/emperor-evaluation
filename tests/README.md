# tests 目录治理

`tests/` 继续进入 Git 管理；测试运行产生的缓存、覆盖率文件、SQLite 数据库、临时 Markdown 导出和 `.tmp/` 内容不得提交。

默认 PR 守门使用：

```bash
pytest -q
```

本次只登记 marker，不设置默认排除项，因此 `pytest -q` 仍会运行现有测试集。需要显式查看重型或导出相关测试时使用：

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
