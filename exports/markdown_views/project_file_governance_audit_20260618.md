# Project File Governance Audit 20260618

生成日期：2026-06-18  
范围：`docs/`、`data/`、`exports/markdown_views/`  
任务来源：issue #40

本审计只处理方法论补充、魏征误分类清理和文件治理复核。不新增史料、不新增 evidence card/evidence cluster，不生成分数、排名或总榜。

## 长期保留文件

- `README.md`
- `docs/证据裁量总则_讨论版.md`
- `docs/第五项B正式工作流模板.md`
- `docs/史料检索总则与项目-人物双轴工作流_讨论版.md`
- `docs/数据层级与批次文件治理规则.md`
- `docs/数据规范.md`
- `docs/第五项B边界说明.md`
- `docs/负证裁量与触发式裁判模块_讨论版.md`
- `docs/负证分案裁判机制.md`
- `data/query_profiles.jsonl`
- `data/search_logs.jsonl`
- `data/sources.jsonl`
- `data/evidence_cards.jsonl`
- `data/evidence_clusters.jsonl`
- `data/trigger_terms.jsonl`
- `exports/markdown_views/史料证据卡索引.md`
- `exports/markdown_views/第五项B三人试点检索线索.md`
- `exports/markdown_views/证据组裁量索引.md`
- `exports/markdown_views/项目检索包索引.md`
- `exports/markdown_views/第五项B_李世民净证据池.md`
- `exports/markdown_views/第五项B_刘秀净证据池.md`
- `exports/markdown_views/第五项B_刘庄净证据池.md`

## 阶段性保留文件

- `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl`
- `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`
- `exports/markdown_views/i5b_three_pilot_methodology_migration_audit_20260618.md`
- `exports/markdown_views/i5b_three_pilot_human_adjudication_reading_guide_20260618.md`
- `exports/markdown_views/i5b_three_pilot_net_adjudication_drafts_20260618.md`
- `exports/markdown_views/i5b_three_pilot_object_anchor_pregrade_checklist_20260618.md`
- `exports/markdown_views/第五项B三人净裁量草案.md`
- `exports/markdown_views/第五项B三人定档前人工裁判清单.md`
- `exports/markdown_views/第五项B三人正式定档草案.md`

说明：这些文件仍有审阅价值，但都不应被视为 canonical 主源。后续若已进入正式定档或对应信息已沉淀进长期规则，应继续压缩数量。

## 可归档文件

- `exports/markdown_views/i5b_three_pilot_methodology_migration_audit_20260618.md`
- `exports/markdown_views/i5b_three_pilot_human_adjudication_reading_guide_20260618.md`
- `exports/markdown_views/i5b_three_pilot_object_anchor_pregrade_checklist_20260618.md`

说明：三者本质上属于 2026-06-18 三人迁移阶段说明，已不宜继续承担当前规则的唯一入口。

## 可删除文件

- `data/evidence_card_correction_batches/i5b_lishimin_weizheng_trigger_family_correction_20260618.jsonl`

说明：该 correction 已合并入 canonical `data/evidence_cards.jsonl`，继续保留只会制造旧口径 residue。本轮已删除。

## 需要合并入 canonical 后删除或归档的 batch 文件

- `data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl`
- `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`

说明：两者当前仍承担迁移审计与对象锚点说明功能；若后续长期复用，应分别并入 `data/query_profiles.jsonl` 与 `data/thematic_anchors.jsonl`，否则应归档。

## 暂不处理但需后续 follow-up 的文件

- `exports/markdown_views/第五项B三人试点正负证矩阵.md`
  说明：仍保留旧的通用负向 trigger family 骨架；本轮不重跑矩阵脚本，但后续应决定是否给“谏臣身后信用反转”补单独矩阵行。
- `exports/markdown_views/第五项B三人正式定档表.md`
  说明：属于更晚阶段产物；本轮未改正式定档结论，只修方法论与证据口径。
- `exports/markdown_views/第五项B三人净裁量草案.md`
  说明：仍是阶段性草案，后续若进入正式定档，应把核心说明折叠进更少的正式视图。

## 本轮治理结论

- 已把“人才安全处置锚点”落实为证据卡/证据簇标签思路，而非独立多轴计算层。
- 已将魏征负证从旧误分类清理为 `谏臣身后信用反转`，并把单证口径调整为“中负封顶、不得上探强负”。
- 已把李世民混合负证 search log 拆成“功臣旧臣处置”与“魏征身后信用反转”两条，避免 canonical residue。
- 已删除已完成但未清理的 correction batch。
- 顶层入口 `README.md` 已补文件治理指引，减少 future drift。
