# I5B Batch B5 source/object coding plan

Issue: #366
Batch: `i5b_typical_batch_b5_ming_qing_closure_20260630`
Persons: 朱棣、朱瞻基、朱由检、皇太极、玄烨、弘历

This file is a review-first planning table only. Canonical fact rows still belong in
`data/*.jsonl` and `data/experimental/*.jsonl`; batch-local JSONL fact files are not
reintroduced here.

## Coding contract

- Source-verified lanes may create legacy `evidence_cards` / `evidence_clusters`,
  legacy object anchors, and diagnostic-only `objects` / `object_evaluations`.
- `adjacent_only` lanes create no object row and no legacy object anchor.
- `obj_id` / `oeval_id` stay null unless a numeric id exists; `obj_code` /
  `oeval_code` stay compact.
- Object names must be real persons, teams, events, mechanisms, institutions,
  policies, relationships, or source statements. Scoring labels stay in
  `category`, `relation`, or `residual`.
- Experimental rows remain `diagnostic_only=true` and
  `feeds_formal_scoring=false`.

## Batch row target

| store group | planned rows | note |
| --- | ---: | --- |
| `query_profiles` | 6 | one person-level profile per B5 person |
| `search_logs` / `query_lane_coverage` | 18 | 12 source/object lanes + 6 adjacent-only lanes |
| `sources` / `source_packs` | 12 | source-verified lanes only |
| `evidence_cards` / `evidence_clusters` | 12 | one card/cluster per source/object lane unless second-pass review downgrades |
| `anchors` / `object_anchor_coverage` | 12 | source/object lanes only; no adjacent-only anchors |
| `experimental/objects` | 11 | 朱由检 uses one 袁崇焕 object with positive and negative evaluations |
| `experimental/object_evaluations` | 18 | 12 object evaluations + 6 adjacent-only processing outcomes |

## Source/object coding plan

| person | planned lane/search suffix | source locator | planned object | class | outcome | relation | category | source/evidence decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 朱棣 | `POS-YAOGUANGXIAO` | `明史/卷145，姚广孝传，成祖论功与眷注段` | 姚广孝 | person | objectized | 谋议采纳与功臣信任 | 创业谋臣识用 | 可转正证。 |
| 朱棣 | `NEG-XIEJIN` | `明史/卷147，解缙传，议储后下狱死段` | 解缙 | person | objectized | 文臣言事后的信用与安全处置 | 谏臣/文臣安全 | 可转负证；储位政治和党争切第五项 C。 |
| 朱棣 | `CUT-ADJACENT` | `明史相关本纪/列传` | none | none | adjacent_only | 靖难、北伐、迁都、内阁制度切分 | 相邻项剥离 | 只记录处理 outcome；不建 object row。 |
| 朱瞻基 | `POS-YANGSHIQI` | `明史/卷148，杨士奇传，宣宗眷待辅臣段` | 杨士奇 | person | objectized | 中枢辅臣信任与任用 | 宰辅团队信任 | 可转正证；仁宣治绩、财政行政结果切第二项。 |
| 朱瞻基 | `NEG-NEISHUTANG` | `明史/卷304，宦官一，宣宗设内书堂段` | 内书堂宦官读书机制 | mechanism | objectized | 近侍人才通道扩张 | 近臣任用风险 | 可转边界负证；宦官权力控制主效应切第五项 C。 |
| 朱瞻基 | `CUT-ADJACENT` | `明史相关本纪/列传` | none | none | adjacent_only | 汉王案、仁宣治绩、制度成效切分 | 相邻项剥离 | 只记录处理 outcome；不建 object row。 |
| 朱由检 | `POS-YUANCHONGHUAN-AUTH` | `明史/卷259，袁崇焕传，崇祯元年召对与督师段` | 袁崇焕 | person | objectized | 危局中任用边臣督师 | 高阶将臣授权 | 可转正证；辽东战果、平台策成败切第三项。 |
| 朱由检 | `NEG-YUANCHONGHUAN-SAFETY` | `明史/卷259，袁崇焕传，被逮磔死段` | 袁崇焕 | person | objectized | 高阶督师冤狱处置 | 将臣安全 | 可转负证；通敌风险、边防安全和司法残酷切第五项 C/D。 |
| 朱由检 | `CUT-ADJACENT` | `明史相关本纪/列传` | none | none | adjacent_only | 辽东战局、流寇、亡国财政压力切分 | 相邻项剥离 | 只记录处理 outcome；不建 object row。 |
| 皇太极 | `POS-FANCHENG` | `清史稿/卷232，范文程传，太宗任用参机务段` | 范文程 | person | objectized | 汉臣谋议采纳与文馆任用 | 异质人才整合 | 可转正证。 |
| 皇太极 | `POS-NINGWANWO` | `清史稿/卷232，宁完我传，太宗纳制度建议段` | 宁完我 | person | objectized | 汉臣制度建议采纳 | 反馈与制度建议入口 | 可转正证；具体制度成效切第二项。 |
| 皇太极 | `CUT-ADJACENT` | `清史稿相关本纪/列传` | none | none | adjacent_only | 八旗军政、宗室贝勒处置、入关基础切分 | 相邻项剥离 | 当前不硬凑负证；只记录处理 outcome。 |
| 玄烨 | `POS-SHILANG` | `清史稿/卷260，施琅传，授靖海将军平台段` | 施琅 | person | objectized | 采纳荐举并授专任将帅 | 将帅授权专任 | 可转正证；台湾战果和海疆治理切第三项/第二项。 |
| 玄烨 | `NEG-MINGZHU` | `清史稿/卷269，明珠传，朋党与罢斥段` | 明珠 | person | objectized | 近臣朋党与反馈扭曲 | 近臣任用风险 | 可转负证；储位/索额图政治和权力控制切第五项 C。 |
| 玄烨 | `CUT-ADJACENT` | `清史稿相关本纪/列传` | none | none | adjacent_only | 三藩、台湾、俄事、储位党争切分 | 相邻项剥离 | 只记录处理 outcome；不建 object row。 |
| 弘历 | `POS-AGUI` | `清史稿/卷318，阿桂传，乾隆任用军机与将帅段` | 阿桂 | person | objectized | 长期军政任用与将帅授权 | 将帅/军机任用 | 可转正证；十全武功战果和边疆收益切第三项。 |
| 弘历 | `NEG-HESHEN` | `清史稿/卷319，和珅传，宠任与败露段` | 和珅 | person | objectized | 近臣宠任造成反馈与吏治风险 | 近臣任用风险 | 可转负证。 |
| 弘历 | `CUT-ADJACENT` | `清史稿相关本纪/列传` | none | none | adjacent_only | 十全武功、文字狱、财政民变和疆域结果切分 | 相邻项剥离 | 只记录处理 outcome；不建 object row。 |

## Adjacent-only no-object plan

| person | adjacent-only lane | object row | legacy object anchor | reason |
| --- | --- | --- | --- | --- |
| 朱棣 | `CUT-ADJACENT` | no | no | 靖难合法性、迁都、北伐、制度建设主要归第一/二/三项或第五项 C。 |
| 朱瞻基 | `CUT-ADJACENT` | no | no | 仁宣治绩、财政休养、汉王案。 |
| 朱由检 | `CUT-ADJACENT` | no | no | 辽东战局、流寇、财政崩溃和亡国结果。 |
| 皇太极 | `CUT-ADJACENT` | no | no | 八旗军事、宗室控制和入关基础主要切第三项或第五项 C。 |
| 玄烨 | `CUT-ADJACENT` | no | no | 三藩、台湾、俄事、储位党争等结果项或权力控制项不建对象。 |
| 弘历 | `CUT-ADJACENT` | no | no | 战争结果、文字狱政治品格、财政民变和疆域收益。 |

## Second-pass JSONL checks

- Extract exact short excerpts and context summaries from the listed source pages.
- Keep source locators stable and source URLs repo-relative in PR evidence.
- Verify no planned id/code collides with existing B1-B4 rows before appending.
- Update child manifest plus aggregate `i5b_typical_source_evidence` manifest only
  after canonical JSONL rows are written.
- Update focused tests for B5 object semantics and missing-evidence count change.
