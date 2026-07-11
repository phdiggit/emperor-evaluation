# scripts/AGENTS.md

本目录只保留 retrieval v3 当前工作流及其直接依赖。

## 目录职责

- `scripts/dev/`：retrieval v3 采集、claim cache、消费、覆盖控制和评分辅助工具。
- `scripts/dev/server_runtime/`：v3 worker 的 systemd 与 shell 运行模板。
- `scripts/build/`：当前 I5B item raw signal 计算器。
- `scripts/shared/`：当前工作流共享配置与 agent runtime。
- `scripts/validate/`：仅保留当前项目配置验证器。

## 命名与数据库

- 当前检索脚本、模块、测试和运行命令统一使用 `retrieval_v3` 命名。
- 所有数据库入口默认使用 `EMPEROR_EVAL_RETRIEVAL_V3_DSN` 和 `retrieval_v3` schema。
- 不得恢复 v2 wrapper、v2 schema routing、旧 DSN 默认值或跨数据库数字 ID 关联。
- 显式写库仍必须使用各工具的 `--execute`；默认保持只读或 rollback dry-run。

## 修改与验证

- 移动或改名后同步更新 import、CLI、server runtime、registry 和对应测试。
- 当前测试面以 `tests/current_workflow_tests.txt` 为准；仓库不再保留非当前工作流测试。
- 提交前至少运行 `python -m compileall -q scripts tests`、`python -m pytest -q` 和 `git diff --check`。
- `docs/文档与脚本登记/scripts_registry.json` 只登记真实存在的当前实现与测试。
