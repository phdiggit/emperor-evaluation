# scripts/AGENTS.md

本文件只约束 `scripts/**` 范围内的长期稳定行为规则。仓库级规则仍以根 `AGENTS.md` 为入口；Issue / PR 白名单和禁止事项优先级更高。

## 适用范围与优先级

- 修改、迁移、审查或新增 `scripts/**` 文件前，先读取本文件和任务点名的审计文档。
- 根 `AGENTS.md` 负责全仓高压线；本文件负责 scripts 目录职责、wrapper、路径和验证纪律。
- 当前模块状态、wrapper、审计文档和专属测试以 `docs/agent_rules/scripts_registry.json` 为准，本文件不维护项目状态日志。

## 目录职责

- `scripts/dev/`：开发辅助工具，供 Codex、维护者和本地开发使用，不承载业务导出、评分、证据裁判或正式验证语义。
- `scripts/validate/`：validator 真实实现目录，新增 validator 默认放在这里。
- `scripts/export/`：exporter 真实实现目录，新增 exporter 默认放在这里。
- `scripts/build/`：数据库和其他构建步骤的真实实现目录；构建脚本测试不得直接覆盖真实工作区数据库，默认使用 `tmp_path` 或临时仓库。
- `scripts/matrix/`：矩阵规划和矩阵视图生成脚本的真实实现目录；matrix 测试默认使用 `tmp_path`、临时输出路径或临时仓库，不允许直接重写真实 `exports/**`。矩阵骨架不等于检索结果，不得写入评分或证据数据。
- `scripts/shared/`：多职责链共享实现目录，放置 exporter、validator、pipeline 共同依赖的工具。
- `scripts/` 根目录：仅允许 registry 登记的稳定入口、兼容 wrapper 和尚未迁移脚本；新增脚本不得无理由放回根目录。

## 真实实现与 wrapper

- 迁移后真实实现只能保留一份；旧路径 wrapper 只做 import/CLI 转发，不承载主逻辑。
- wrapper 不应定义 validate/export/build 等真实主逻辑函数，不应复制大段常量列表。
- 修改已迁移脚本时优先改 registry 指向的真实实现，再确认旧路径 wrapper 仍可 import 或运行。
- 同一职责链内的新旧入口都要保持兼容；普通功能 PR 不得把真实实现重新放回 `scripts/` 根目录。
- 仓库内部真实实现必须依赖 registry 指向的 canonical implementation，不得通过 legacy wrapper 相互调用；旧 wrapper 只服务外部兼容和明确的 compatibility tests。

## 路径和 import

- 移动 Python 文件必须核对 `__file__`、`parents[n]`、`ROOT` 和所有路径常量。
- import 优先使用当前分层目录的稳定路径；兼容旧路径只通过 wrapper 保留。
- 需要 Git 路径、中文路径或状态核对时，优先使用 `git -c core.quotepath=false ...` 或 `python scripts/dev/repo_tool.py`。
- JSON 输出必须 UTF-8 no BOM、`ensure_ascii=False`、稳定缩进和稳定排序。

## 迁移纪律

- 普通业务 PR 不顺手迁移其他脚本，也不顺手改业务语义。
- 同职责、同风险、同验证链的机械迁移可以批量处理；build、pipeline、matrix 类脚本按专门 PR 分阶段治理。
- 迁移任务先锁定影响面和测试，再做小步重构；不要通过批量替换绕过审计。
- 共享工具迁移必须单独治理，并保留旧路径 wrapper。

## 范围边界

- 不得修改 `exports/**`、`data/**`、SQLite 或数据库副产物，除非任务白名单明确允许。
- 本目录治理不得改变真实评分、排名、正式定档、证据事实、证据簇裁判结论或 Markdown 导出的业务格式和内容。
- 生成物不是事实源；需要改导出内容时先定位生成器。

## 验证要求

- 修改已登记模块前，读取 registry 指向的 `audit_docs`；开 PR 前运行 registry 指定测试及适用治理检查。
- 涉及 `scripts/**`、`tests/**` 或 validation 入口时，开 PR 前运行 `python scripts/validate_all.py`。
- scripts 治理 PR 还必须运行 `python scripts/dev/repo_tool.py agents-check` 和适用的 `scope-check`。
- scripts 治理 PR 还必须运行 `python scripts/dev/repo_tool.py canonical-imports-check`；`agents-check` 已包含 canonical import 检查。
- 验证命令若产生范围外副产物，记录通过结果后清理副产物，再只做范围核对命令。

## registry 与审计文档

- `docs/agent_rules/scripts_registry.json` 是当前实现路径、迁移状态、legacy wrapper、root exception、audit docs 和 required tests 的机器可读事实源。
- `docs/agent_rules/README.md` 说明规则分类；新增规则先按该表决定写入位置。
- 高风险模块的维护要求应放在审计文档或 registry，不继续堆进根 `AGENTS.md` 或本文件。
