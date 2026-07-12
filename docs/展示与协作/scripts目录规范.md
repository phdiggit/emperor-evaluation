# scripts 目录规范

当前仓库只保留 retrieval v3 native workflow 及其直接依赖。

## 当前目录

- `scripts/dev/`：retrieval v3 采集、claim、消费、覆盖控制和评分工具。
- `scripts/dev/server_runtime/`：v3 worker 运行模板。
- `scripts/build/`：I5B item raw signal 计算器。
- `scripts/shared/`：agent runtime 与项目配置共享实现。
- `scripts/validate/`：当前项目配置验证器。

`scripts/` 根目录不保留脚本入口，不提供旧 wrapper。

## 稳定约束

- 检索脚本和测试统一使用 `retrieval_v3` 命名。
- 数据库默认使用 `EMPEROR_EVAL_RETRIEVAL_V3_DSN` 与 `retrieval_v3` schema。
- 不恢复旧 schema routing、旧 DSN 默认值或跨数据库数字 ID 关联。
- 写库必须显式 `--execute`；默认只读或 rollback dry-run。
- 当前实现、测试和行数预算以 `docs/文档与脚本登记/scripts_registry.json` 为准。

## 验证

```text
python -m compileall -q scripts tests
python -m pytest -q
git diff --check
```
