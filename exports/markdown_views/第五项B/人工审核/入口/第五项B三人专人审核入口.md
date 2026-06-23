# 第五项B三人专人审核入口

本文由 `scripts/export/export_i5b_auto_adjudication.py` 生成，是第五项B三人试点人工审核的当前状态入口；旧 `docs/` 同名文件已退役，不再作为当前入口。

## 使用边界

- 本入口不是正式评分表。
- 本入口不生成正式分数、最终排名、总榜或人物级人工覆盖结论。
- 本入口不生成最终排名。
- 人工只核验数据质量、史料回源状态、上下文充分性、相邻项剥离、规则命中和算法版本，不逐人改写自动结算方向。
- 自动结算草案、证据链和 warning 都只是复核材料；异常结果应回到数据、规则或算法层修复。
- 人工审核主表隐藏 `evidence_id/source_id/cluster_id` 等机器字段；需要追踪时查看附录或机器审计视图。
- `exports/markdown_views/第五项B/机器审计/` 只用于代码审查、数据追踪和回源定位，不作为业务审核主入口。

## Canonical 入口层级

- 审核入口视图：`exports/markdown_views/第五项B/人工审核/入口/`
- 自动裁判链：`exports/markdown_views/第五项B/人工审核/自动裁判链/`
- 自动结算索引：`exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/第五项B三人自动结算草案.md`
- 规则敏感点：`exports/markdown_views/第五项B/人工审核/自动裁判链/规则敏感点/第五项B自动结算规则敏感点清单.md`
- 正式定档草案：`exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B三人正式定档落地表.md`
- 评分映射草案：`exports/markdown_views/第五项B/人工审核/自动裁判链/正式定档草案/第五项B评分标尺与档位映射草案.md`
- 证据卡索引：`exports/markdown_views/第五项B/人工审核/证据链/证据卡/第五项B人工审核证据卡索引.md`
- 证据簇索引：`exports/markdown_views/第五项B/人工审核/证据链/证据簇/第五项B人工审核证据簇索引.md`
- 机器审计视图：`exports/markdown_views/第五项B/机器审计/证据链/`

## 审核总流程

1. 先读三人自动结算索引。
2. 再读对应人物详情页。
3. 再读该人物人工审核净证据池。
4. 必要时查看人工审核证据卡索引和人工审核证据簇索引。
5. 需要代码追踪、数据追踪或回源定位时，再进入机器审计视图。
6. 最后回到人工复核工作台，只填写数据质量、回源、上下文、剥离和规则级复核状态。

## 试点人物入口

### 李世民

- 自动结算人物详情：
  - `exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/人物详情/李世民.md`
- 自动结算长字段附录：
  - `exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/附录/李世民_长字段附录.md`
- 净证据池：
  - `exports/markdown_views/第五项B/人工审核/证据链/净证据池/第五项B_李世民人工审核净证据池.md`
- 人工审核史料详情附录：
  - `exports/markdown_views/第五项B/人工审核/证据链/附录/李世民_人工审核史料详情附录.md`
- 数据质量核验栏位：回源状态、上下文充分性、相邻项剥离、证据方向一致性、规则命中异常。

### 刘秀

- 自动结算人物详情：
  - `exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/人物详情/刘秀.md`
- 自动结算长字段附录：
  - `exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/附录/刘秀_长字段附录.md`
- 净证据池：
  - `exports/markdown_views/第五项B/人工审核/证据链/净证据池/第五项B_刘秀人工审核净证据池.md`
- 人工审核史料详情附录：
  - `exports/markdown_views/第五项B/人工审核/证据链/附录/刘秀_人工审核史料详情附录.md`
- 数据质量核验栏位：回源状态、上下文充分性、相邻项剥离、证据方向一致性、规则命中异常。

### 刘庄

- 自动结算人物详情：
  - `exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/人物详情/刘庄.md`
- 自动结算长字段附录：
  - `exports/markdown_views/第五项B/人工审核/自动裁判链/自动结算草案/附录/刘庄_长字段附录.md`
- 净证据池：
  - `exports/markdown_views/第五项B/人工审核/证据链/净证据池/第五项B_刘庄人工审核净证据池.md`
- 人工审核史料详情附录：
  - `exports/markdown_views/第五项B/人工审核/证据链/附录/刘庄_人工审核史料详情附录.md`
- 数据质量核验栏位：回源状态、上下文充分性、相邻项剥离、证据方向一致性、规则命中异常。

## 旧路径禁用

以下旧路径若在历史分支或本地残留中出现，只能视为兼容层或待清理文件，不作为当前审核入口：

- `exports/markdown_views/第五项B_李世民净证据池.md`
- `exports/markdown_views/第五项B_刘秀净证据池.md`
- `exports/markdown_views/第五项B_刘庄净证据池.md`
- `exports/markdown_views/第五项B三人自动结算草案.md`
- `exports/markdown_views/第五项B自动结算草案_李世民.md`
- `exports/markdown_views/第五项B自动结算草案_刘秀.md`
- `exports/markdown_views/第五项B自动结算草案_刘庄.md`
- `exports/markdown_views/第五项B/自动结算草案/`
- `exports/markdown_views/第五项B/证据链/`

## 审核出口

审核出口只记录规则级复核、数据质量核验和发布门槛状态；不得把本文档、自动结算草案、证据链视图或 warning 直接转写成正式分数、最终排名、正式档位或裁判结论。
