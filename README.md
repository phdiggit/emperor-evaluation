# 皇帝综合评价体系 V4

本仓库只保留当前有效的评分规则、证据契约、运行实现和唯一 canonical 结果。Git 是唯一历史载体；工作树不保存阶段报告、失败运行、重复结果或旧状态镜像。

## 当前状态

- V3 已退役；V4 是唯一活动实现。
- 第五项 B 五条 rule 已进入版本化 shadow，并完成李世民皇帝级历史覆盖收口。
- 当前李世民 rule raw signal：
  - `talent_discovery`: `+4.864`
  - `appointment_delegation`: `+9.823`
  - `team_building`: `+7.632`
  - `tolerate_talent`: `+5.996`
  - `anti_nepotism`: `+1.760`
- 按既定五权重合成的 declared-workset raw signal 为 `7.248`。
- `tolerate_talent` 仍有3个李世民单元证据不足；批量动态映射还缺少第二位五rule完整皇帝。因此正式45分、档位和排名保持关闭。
- 当前实现默认 `offline-first`、`report-only`、`shadow-first`；模型调用、正式评分写入和排名写入均为0。

## 当前架构

```text
Source Cache
→ Claim Extractor
→ Assertion review
→ HistoricalEpisode / RuleEvidenceUnit
→ deterministic factor projection
→ shadow ScoreContribution
→ ruler rule-net / scoring detail
```

PostgreSQL保存V4业务状态，Git保存规则、配置、契约和当前不可变输入。JSON/Markdown只允许作为当前只读输出；被新结果取代后直接删除。

## 历史覆盖预算与产物

- 单位皇帝的五条rule共用15分钟硬截止时间，从首次领取候选任务开始计时，resume不重置；到点停止领取，已超时返回的结果丢弃并保留失败checkpoint。
- 材料搜索以计分政策的同侧3条结算预算为停止边界；边界稳定后不为“更完整”继续穷尽材料。智能体调用上限可放宽，但不得突破wall-clock预算。
- Git只追踪当前规则、配置、合同、当前工作流必需的不可变输入和唯一canonical结果。
- `tmp/i5b_historical_coverage/**`保存运行中的work package、checkpoint、phase artifact和state；成功后删除，失败时只保留继续运行所需checkpoint。
- `logs/i5b_historical_coverage/**`可短期保留计时与失败诊断，但始终不进入Git。数据库复跑审计、resume报告、increment和被替代版本在收口后删除。

## 当前入口

Windows仓库根目录：

```powershell
$env:PYTHONPATH = "src"
```

```bash
python -m emperor_v4.eval model-policy --policy config/model-policy.yml
python -m emperor_v4.eval i5b-factor-semantics --contract config/i5b-factor-semantics.yml --output tmp/factor-semantics.json
python -m emperor_v4.eval i5b-scoring-policy --policy config/i5b-scoring-policy.yml --output tmp/scoring-policy.json
python -m emperor_v4.eval i5b-scoring-detail-export --ruler 李世民
```

最后一条命令默认导出该皇帝全部五条rule，同时生成
`tmp/i5b_scoring_detail/<皇帝>/scoring-detail.md` 和 `scoring-detail.json`。
需要筛选时可重复传入 `--rule` 或 `--person`。

## 当前事实源

1. `docs/项目总纲/皇帝综合评价体系评分标准.md`
2. `docs/00-V4项目章程.md`
3. `docs/项目总纲/总规则.md`
4. 当前领域、证据与服务契约
5. 当前分项规则
6. `config/*.yml`

当前状态只维护在本文件和 `config/project.yml`。历史过程、旧结论和被删除产物需要时从Git查看。

## 下一步

- 补齐 `tolerate_talent` 3个 `insufficient_projection` 单元。
- 选择第二位皇帝完成五rule小cohort。
- 在多皇帝校准完成前，继续禁止正式45分、档位和排名。
