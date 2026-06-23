# docs/AGENTS.md

本文件约束 `docs/**` 范围内的长期稳定行为规则。仓库级高压线仍以根 `AGENTS.md` 为入口；Issue / PR / 任务卡优先级更高。

## 适用范围与优先级

- 修改、审查、新增或治理 `docs/**` 文件前，先读取本文件和任务点名的治理文档。
- 根 `AGENTS.md` 负责全仓边界；本文件负责文档类型、事实源、生成物、引用和清理纪律。
- 当前逐文件生命周期、引用和候选动作以 `docs/agent_rules/docs_registry.json` 为准，本文件不维护项目状态日志。

## 文档类型

- `canonical_spec`：长期规范、强约束和标准。
- `operational_guide`：当前运行手册、入口说明和执行流程。
- `active_design`：仍在使用的设计、裁量边界或业务决策文档。
- `generated_view`：由脚本或测试生成、可重建的文档。
- `audit_record`、`migration_record`、`historical_snapshot`：审计、迁移和阶段快照。
- `config_explanation`：配置结构、字段含义和维护说明。
- `unknown`：无法可靠判断，必须人工确认。

## 事实源与生成物

- 规范、运行手册和当前决策文档属于长期事实源。
- `docs/皇帝综合评价体系评分标准.md` 是项目驱动文档，也是当前评分业务语义的最高层 canonical spec；下位文档冲突必须显式记录。
- 普通 docs 清理 PR 不得归档、删除、移动或降级该驱动文档；修订其正文必须另开专门 PR 并经用户明确确认。
- docs 当前规范层优先保留稳定方法论、说明和规则；实例数据、配置值、当前批次状态和可重建产物应分别回到 `data/`、`data/configs/` 或 `exports/`，并通过 registry 登记迁移预算。
- Markdown 生成物必须追溯到 generator；不得用手改生成文档代替修改生成器。
- 生成物不是事实源；若与 `data/*.jsonl`、配置或 generator 冲突，先回到源头核对。
- 配置说明可以解释结构和维护口径，但不得绕过 validator 或 registry。

## 引用与替代关系

- 判断文档状态时同时检查 README、AGENTS、scripts、tests、workflow 和其他 docs 的引用。
- 无入链引用不等于无价值；必须检查是否含唯一事实、历史决策或审计链。
- 日期后缀不等于过期；必须识别历史价值和替代文档。
- `replacement_path` 必须真实存在，并且能覆盖被替代文档的必要事实。

## 清理、归档和删除纪律

- 清理、归档和删除第一轮只做诊断和候选清单；第二轮才允许小批量执行。
- 一次性审计、迁移记录和历史快照可以进入 archive 候选，但不自动删除。
- `archive/docs/**` 保存历史审计价值材料，不属于 `docs/` 当前层，也不是当前规范事实源。
- archive 文档不得在普通业务 PR 中重新激活或删除；重新激活必须另开 PR 并更新 registry。
- 归档移动必须同步更新 `archived_document_paths`、引用和治理报告。
- active 文档引用 archive 时必须明确其为历史背景；`archive/docs/README.md` 是归档导航入口。
- 删除候选必须有明确替代路径或可重建证明，并要求人工确认。
- `unique_source_risk=true` 的文档不得直接提出删除。
- 删除前必须确认不是测试、脚本、README、AGENTS、workflow 或 generator 的依赖。
- 不按“文件名旧”“无引用”“看起来重复”直接删除或归档。

## 中文路径与编码

- 中文 Markdown、JSON 和说明文件默认使用 UTF-8 no BOM。
- 中文路径和 diff 范围核对优先用 `git -c core.quotepath=false ...` 或仓库工具。
- 长中文 Markdown 正文避免用 PowerShell inline 字符串写入。

## 验证要求

- 修改 docs registry、docs 规则或 docs 工具后，运行 `python scripts/dev/docs_tool.py check --registry docs/agent_rules/docs_registry.json`。
- 涉及 `scripts/**`、`tests/**` 或 validation 入口时，继续运行 `python scripts/validate/validate_all.py` 和适用 pytest。
- 验证命令若生成范围外副产物，记录通过结果后清理，再只做范围核对。

## registry 与治理报告

- `docs/agent_rules/docs_registry.json` 是文档生命周期、引用和候选动作的机器可读事实源。
- `exports/governance/文档治理盘点报告.md` 是人工审阅入口，保存本轮统计、候选清单和后续批次建议。
- AGENTS 只保存稳定规则，不逐文件枚举当前状态。
