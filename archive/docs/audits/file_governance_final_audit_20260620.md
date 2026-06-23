# File Governance Final Audit 20260620

## 1. Executive summary

- complete status: **substantially complete**
- remaining unresolved: **no active blocker found**
- risk level: **low**

本轮复核后，原始 file-governance 计划中的主链路已经基本收口：

1. 冗余/敏感/留后文件已完成受控归档；
2. batch-to-canonical 吸收关系已完成审计，并对 query/search/thematic 三类关键批次给出 canonical 落点；
3. thematic anchor 已从单一聚合层扩展为 object / mechanism / event 多粒度 canonical lane；
4. canonical data integrity validator、`scripts/validate_all.py` 与 GitHub Actions `Validate` 已到位；
5. `scripts/export/export_md.py` 已完成多轮低风险模块化拆分；
6. 当前未发现活跃脚本、测试或 CI 仍把已归档 leavebehind 文件当作执行入口。

本轮未发现必须在本 PR 内继续处理的脚本、数据或 workflow 级问题。剩余事项主要是：

- 部分历史诊断/复核文档仍保留治理前或治理中状态描述；
- 这些引用在语义上属于历史快照，不构成活跃 source-of-truth 冲突；
- 若后续还要继续“文档口径收口”，建议单开 docs-only PR，避免把历史记录清洗和治理闭环审计混在一起。

## 2. File-governance completed items

以下事项本轮核查时均已处于完成态：

1. 冗余/敏感生成文件治理已完成，相关说明文档已落地。
2. formal-result leavebehind 文件已完成人审复核，并在确认后受控归档到 `archive/file_governance_20260619/`。
3. `query_profile_batches` 与 `search_log_batches` 已完成 exact-id canonical merge，并保留 `source_batch` 追溯。
4. `thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` 已完成 canonical lane 吸收，不再处于“待 schema 决策”的活跃未收口状态。
5. post-governance consistency audit 已完成，且未发现活跃脚本仍指向旧 formal-result leavebehind 文件。
6. `scripts/validate_canonical_data_integrity.py` 已保护 canonical JSONL 的 parseability、ID 唯一性、source traceability 与 thematic lane 语义。
7. `scripts/validate_all.py` 已提供统一验证入口。
8. `.github/workflows/validate.yml` 已在 PR / push to `GPT` 时执行统一验证入口与聚焦测试。
9. `scripts/export/export_md.py` 的 scaffold、I5B review-path、I5B net-evidence、expanded batch1、project-doc-view 五个低风险切片均已完成模块化拆分。

## 3. Remaining unresolved or human-decision items

### 当前无活跃 blocker

本轮没有发现需要立即升级为脚本/data 变更 issue 的矛盾规则，也没有发现“仍在使用但无人承认”的过渡文件。

### 仍可后续考虑，但不是本轮阻塞

1. `docs/项目文件治理诊断报告.md` 仍保留治理前的高风险判断与候选状态。
2. `docs/多余文件候选确认报告.md`、`docs/多余文件第二批最终引用复核.md`、`docs/多余文件第三批敏感候选复核.md` 仍保留历史筛查语境。
3. `docs/thematic_anchor_schema_decision_20260620.md` 与 `docs/thematic_anchor_multigranularity_schema_plan_20260620.md` 保留的是 schema 决策过程与迁移前状态，不应再被误读为“当前 unresolved tail”。

结论：

- 这些都更接近 **historical decision record**，不是活跃未收口项；
- 若后续要提高新读者可读性，可单独补一份“历史治理文档索引/时态说明”。

## 4. Stale-reference scan results

本轮重点检索了以下旧路径或高风险名词：

- `全局总标尺决策简报_讨论版.md`
- `第五项B三人正式定档草案.md`
- `第五项B三人正式定档表.md`
- `i5b_liubang_pregrade_adjudication_checklist_20260618.md`
- `thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl`
- `query_profile_batches`
- `search_log_batches`

分类规则：

- `active`：当前脚本/测试/活跃说明中仍作为现行入口或现行数据源使用；
- `archived-intentional`：明确描述归档动作、历史输入保留或历史决策过程；
- `stale`：继续以当前口径描述已被替代路径；
- `needs human decision`：当前证据不足，仍可能是唯一源或存在口径冲突。

### Scan table

| reference | classification | current assessment |
| --- | --- | --- |
| `docs/全局总标尺决策简报_讨论版.md` | `active` | 当前仍由 `scripts/export/export_md.py` -> `scripts/export_project_doc_views.py` 双写到 `docs/` 与 `exports/markdown_views/`，并被 `tests/test_global_score_scale_brief.py` 验证。不是陈旧路径。 |
| `exports/markdown_views/全局总标尺决策简报_讨论版.md` | `active` | 仍是现行导出视图之一，非 archive leftover。 |
| `第五项B三人正式定档草案.md` | `archived-intentional` | 当前只在归档说明、历史复核文档、旧治理审计中出现。未发现活跃脚本/测试把它当作当前正式入口。 |
| `第五项B三人正式定档表.md` | `archived-intentional` | 同上；当前正式入口已迁移到 `exports/markdown_views/第五项B三人正式定档落地表.md`。 |
| `i5b_liubang_pregrade_adjudication_checklist_20260618.md` | `archived-intentional` | 当前在归档说明与历史诊断文档中出现，归档位置明确，未发现活跃执行链引用。 |
| `data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl` | `active` + `archived-intentional` | 作为历史输入被保留，同时被 validator 和治理说明显式追踪 `source_batch`；不是 stale，也不是待删除。 |
| `query_profile_batches` | `active` + `archived-intentional` | 过渡批次层仍被规则文档允许保留，并被 validator 用于 traceability 校验；关键批次已 absorbed。 |
| `search_log_batches` | `active` + `archived-intentional` | 同上；既是过渡层，也有历史输入保留职责。 |
| `docs/项目文件治理诊断报告.md` 中对若干文件写成“需人工确认/删除候选” | `stale` | 这些表述反映治理前状态。当前它已是历史诊断快照，不应再当作现行治理状态说明。建议后续如需收口，可在新文档中明确“historical only”。 |

### Scan conclusion

1. 未发现必须立即修复的活跃 stale path。
2. 真正的“陈旧引用”主要集中在历史诊断文档，而不是脚本/测试/CI。
3. 这些陈旧表述目前风险可控，因为它们没有驱动活跃入口，只是需要读者具备“历史快照”意识。

## 5. Batch/canonical status table

以下表只回答当前批次层状态，不对 batch 做删除建议。

| batch area | representative files checked | status | canonical target / role | audit conclusion |
| --- | --- | --- | --- | --- |
| `query_profile_batches` | `i5b_three_pilot_profiles_migration_20260618.jsonl`, `i5b_next_four_profiles_20260618.jsonl`, `i5b_expanded_pilot_batch1_20260619.jsonl` | absorbed or intentionally retained | `data/query_profiles.jsonl` / historical input | 已有 absorbed 案例，并由 validator 追踪 `source_batch`；目录保留合理。 |
| `search_log_batches` | `i5b_next_four_20260618.jsonl`, `i5b_liubang_supplemental_safety_20260618.jsonl`, `i5b_expanded_pilot_batch1_20260619.jsonl` | absorbed or intentionally retained | `data/search_logs.jsonl` / historical input | 已有 absorbed 案例，并由 validator 追踪 `source_batch` 与 `source_status/source_polarity`。 |
| `thematic_anchor_batches` | `i5b_three_pilot_object_anchors_20260618.jsonl` | absorbed but intentionally retained | `data/thematic_anchor_objects.jsonl`, `data/thematic_anchor_mechanisms.jsonl`, `data/thematic_anchor_events.jsonl` | 已完成 canonical lane 吸收；保留是历史输入，不是 pending schema blocker。 |
| `source_batches` | expanded pilot / liubang / zhu yuanzhang micro supplement batches | active review-only historical input | source-layer staging and review artifacts | 当前仍被导出、测试或审阅路径使用，属于允许保留的批次层。 |
| `evidence_card_batches` | expanded pilot / liubang / supplement batches | active review-only historical input | evidence staging / review artifacts | 当前仍被审阅型导出和测试使用，不应在本轮治理中清理。 |
| `evidence_cluster_batches` | expanded pilot / liubang clusters | active review-only historical input | cluster staging / review artifacts | 当前仍被 review/export path 使用。 |
| `adjudication_batches` | expanded batch1 adjudication files | active review-only historical input | review / adjudication draft layer | 仍服务当前扩展试点导出链，不属于过时孤儿文件。 |
| `audit_batches` / `relative_band_batches` / `rule_boundary_batches` / `sweep_batches` | readiness / relative-band / rule-boundary / sweep files | active review-only historical input | governance / review support inputs | 当前模块化后的导出脚本仍在使用，状态清晰。 |

结论：

- `data/*_batches/` 当前不存在“看起来像唯一主数据却无人承认”的目录；
- 关键批次文件要么已 absorbed，要么仍被活跃 review/export 链路使用，要么被治理文档明确为历史输入保留；
- 没有发现必须在本 PR 内发起 archive/delete 的对象。

## 6. Formal-result protection status

### 当前保护状态

1. `第五项B三人正式定档草案.md` 与 `第五项B三人正式定档表.md` 已归档到 `archive/file_governance_20260619/`。
2. 当前正式入口仍是 `exports/markdown_views/第五项B三人正式定档落地表.md`。
3. `i5b_formal_result_leavebehind_archive_note_20260620.md` 已明确记录“仅归档，不改写内容，不改评分/档位/排名/裁判结论”。
4. `docs/数据层级与批次文件治理规则.md` 仍把正式定档落地表列为应保留的正式成果导出。
5. `docs/post_file_governance_consistency_audit_20260620.md` 已确认旧 formal-result leavebehind 不再被活跃脚本/测试当作入口。

### 风险判断

- accidental archive/delete risk: **low**
- source-of-truth confusion risk: **low to medium**, 但主要来自历史文档阅读歧义，而非活跃脚本误用

### 当前结论

formal-result / scoring / ranking 文件整体仍处于受保护状态，没有发现本轮需要进一步移动或删除的正式结果文件。

## 7. Current canonical entrypoints

### For users

当前对普通使用者最清晰的入口是：

1. `python scripts/validate/validate_all.py`
   - 统一本地验证入口；
   - 顺序执行 `validate_evidence.py` 与 `validate_canonical_data_integrity.py`。
2. `.github/workflows/validate.yml`
   - 对 PR 到 `GPT` 和 push 到 `GPT` 自动执行统一验证。
3. canonical data files under `data/`
   - `data/query_profiles.jsonl`
   - `data/search_logs.jsonl`
   - `data/sources.jsonl`
   - `data/evidence_cards.jsonl`
   - `data/evidence_clusters.jsonl`
   - `data/thematic_anchors.jsonl`
   - `data/thematic_anchor_objects.jsonl`
   - `data/thematic_anchor_mechanisms.jsonl`
   - `data/thematic_anchor_events.jsonl`
4. current formal-result export entrypoint
   - `exports/markdown_views/第五项B三人正式定档落地表.md`

### For Codex / contributors

当前对 Codex 和维护者最清晰的治理入口是：

1. `docs/validation_entrypoints_20260620.md`
2. `docs/数据层级与批次文件治理规则.md`
3. `docs/batch_canonical_absorption_audit_20260620.md`
4. `docs/post_file_governance_consistency_audit_20260620.md`
5. `scripts/validate_canonical_data_integrity.py`
6. `scripts/validate_all.py`

结论：

- “当前入口是什么”已经比治理前清晰得多；
- 仍然存在的是历史文档较多，而不是现行入口缺失。

## 8. Recommended next phase

推荐下一阶段不再做 archive/delete 动作，而是转入轻量维护型治理：

1. 如有需要，补一份“历史治理文档索引/时态说明”，把 `docs/项目文件治理诊断报告.md` 这类文件标记为 historical snapshot。
2. 继续保持 docs-only 收口与脚本/data 变更分离。
3. 若未来新增 batch-to-canonical absorption，再优先复用现有 validator / audit note 模式，不重建新治理框架。
4. `scripts/export/export_md.py` 若继续模块化，可按同样小切口推进，但这已经不再属于 file-governance 主链任务。

## 9. Repository change statement

本次仓库改动仅新增本审计文档：

- 历史路径：`docs/file_governance_final_audit_20260620.md`

除此之外：

- 未修改 data files
- 未修改 batch files
- 未修改 exports
- 未修改 archive contents
- 未修改 scoring/adjudication conclusions
- 未修改 rankings
