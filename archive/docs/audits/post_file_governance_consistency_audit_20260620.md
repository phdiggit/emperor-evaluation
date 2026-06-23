# Post File Governance Consistency Audit 20260620

本报告对应 post-governance consistency pass。目标是确认当前活跃工作流不再指向已归档 leavebehind 文件，并复核 thematic anchor 新 canonical lanes 的可解析性与可发现性。

## 1. Searched files and validation commands

本轮主要执行了以下检索与校验：

- 搜索旧正式定档路径与当前正式入口：
  - `rg -n -e "第五项B三人正式定档草案" -e "第五项B三人正式定档表" -e "第五项B三人正式定档落地表" docs scripts tests exports data archive`
- 搜索 thematic anchor canonical 文件引用：
  - `rg -n -e "thematic_anchor_objects.jsonl" -e "thematic_anchor_events.jsonl" -e "thematic_anchor_mechanisms.jsonl" -e "thematic_anchors.jsonl" docs scripts tests data`
- 搜索本地未收口/未解决表述：
  - `rg -n -e "未解决" -e "待处理" -e "待归档" -e "needs canonical import first" -e "needs migration" -e "remaining" -e "broad tail" -e "unresolved" docs -g "*.md"`
- 读取并人工复核：
  - `docs/batch_canonical_absorption_audit_20260620.md`
  - `docs/数据层级与批次文件治理规则.md`
  - `docs/数据规范.md`
  - `docs/项目文件治理诊断报告.md`
- thematic anchor JSONL 解析校验：
  - `data/thematic_anchors.jsonl`
  - `data/thematic_anchor_objects.jsonl`
  - `data/thematic_anchor_mechanisms.jsonl`
  - `data/thematic_anchor_events.jsonl`

## 2. Stale references found

### A. Archived formal-result leavebehind references

结论：

- 未发现活跃脚本或测试仍把 `第五项B三人正式定档草案.md` / `第五项B三人正式定档表.md` 当作当前执行入口。
- 活跃脚本与测试当前指向的是 `exports/markdown_views/第五项B三人正式定档落地表.md`。

已确认的活跃入口引用：

- `scripts/export_i5b_auto_adjudication.py`
- `tests/test_i5b_auto_adjudication.py`
- `docs/第五项B评分标尺与档位映射草案.md`
- `docs/第五项B评分映射总标尺对齐审计.md`

发现仍引用旧路径的文档类型：

- 历史治理/复核文档
- 归档说明文档
- 候选确认/敏感复核文档

处理结果：

- 这些历史性引用本轮未强行改写路径正文，因为它们描述的是归档前状态或归档动作本身，属于历史引用，不属于活跃工作流误指向。

### B. Open task sanity / stale unresolved wording

发现一处需要更新的非历史状态文档：

- `docs/batch_canonical_absorption_audit_20260620.md` 仍把 thematic anchor batch 写成 `needs deeper schema investigation`。

处理结果：

- 已更新为：thematic anchor batch 已完成 canonical lane 吸收，原始 batch 仅作为历史输入保留。

发现仍保留旧状态的文档：

- `docs/项目文件治理诊断报告.md`
- `docs/多余文件候选确认报告.md`
- `docs/多余文件第二批最终引用复核.md`
- `docs/多余文件第三批敏感候选复核.md`

处理结论：

- 这些文档属于历史诊断/候选复核快照，本轮保留为历史引用，不当作“当前仍未收口的活跃任务说明”。

## 3. Current official entrypoint confirmation

当前正式入口仍是：

- `exports/markdown_views/第五项B三人正式定档落地表.md`

确认依据：

- `scripts/export_i5b_auto_adjudication.py` 的正式导出路径常量指向该文件。
- `tests/test_i5b_auto_adjudication.py` 的断言也指向该文件。
- 相关评分映射/对齐文档仍把它当作当前正式入口。

## 4. Thematic anchor JSONL validation summary

本轮已解析以下 4 个 thematic anchor JSONL：

- `data/thematic_anchors.jsonl`
- `data/thematic_anchor_objects.jsonl`
- `data/thematic_anchor_mechanisms.jsonl`
- `data/thematic_anchor_events.jsonl`

校验结果：

- 4 个文件都可正常按 JSONL 解析。
- 新增三条 canonical lane 内部无重复 `anchor_id`。
- 三条 canonical lane 之间无重复 `anchor_id`。
- `ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618` 仍位于 `data/thematic_anchor_events.jsonl`。
- `data/thematic_anchors.jsonl` 本轮未修改。

lane 行数摘要：

- `data/thematic_anchor_objects.jsonl`: 10
- `data/thematic_anchor_mechanisms.jsonl`: 1
- `data/thematic_anchor_events.jsonl`: 1

## 5. Discoverability and file changes

本轮已更新的 discoverability / 规范文档：

- `docs/数据规范.md`
- `docs/数据层级与批次文件治理规则.md`

更新内容：

- 把 `data/thematic_anchor_objects.jsonl`
- `data/thematic_anchor_events.jsonl`
- `data/thematic_anchor_mechanisms.jsonl`

显式加入 canonical thematic anchor 说明，避免仓库只暴露 `data/thematic_anchors.jsonl` 这一 aggregate 层而遗漏新 lanes。

本轮未修改：

- 脚本
- 测试
- archived files
- batch files
- 评分/排名/裁判结论相关内容

## 6. Remaining follow-up

当前没有发现需要立刻修的活跃脚本/测试 stale path。

后续若要继续收口，可单独考虑：

- 是否把历史治理诊断文档整体迁入更明确的历史区；
- 是否把 thematic anchor lane 解析校验纳入现有 validator 或测试，但这不属于本轮必须动作。
