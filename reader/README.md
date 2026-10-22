# 综合阅读层：帝王三镜

以人物为入口，并列呈现统治绩效、九轴人物画像与历史影响。阅读层负责排版、导航和追溯；评分、归责、准入及跨体系边界见[共同合同](../docs/项目总纲/皇帝综合评价体系合同.md)和[项目登记的分项合同](../config/project.yml)。

## 构建与检查

在仓库根目录运行：

```powershell
python v4.py reader
```

该命令调用`build_site.py`，依次构建军事档案、全部阅读页面与人物数据、第一项来源缓存，检查页面和缓存同值，再将完整静态站点打包到`.tmp/pages-site/`。新检出后先构建，再预览或运行依赖生成页面的测试。

局部更新页面用`python reader/build.py`；第一项来源变化另运行`python reader/build_first_item_reader_cache.py`，军事登记或档案说明变化另运行`python reader/build_military_archive.py`。前两项命令加`--check`只读核对当前生成物。

## 本地预览

人物详情通过`fetch`读取分片，完整浏览须使用HTTP服务：

```powershell
python -m pip install -r reader/requirements.txt
python reader/serve.py
```

访问`http://127.0.0.1:8765/reader/index.html`。本地服务把正式Markdown／JSON转为只读阅读页，对`reader/data/`直接返回原始数据；军事档案读取正式分片时使用`?raw=1`，与线上加载一致。

## 信息结构

| 层级 | 内容与交互 |
| --- | --- |
| 人物总览 | 搜索、朝代与样本筛选、排序和选择对照；默认历史顺序，也可按统治绩效或历史影响浏览 |
| 人物阅读 | 三体系概览，随后按主题展开完整事实、裁决、反证与来源 |
| 并列对照 | 相同维度对齐；“突出差异”只改强调样式，不隐藏同档依据或重置展开状态 |
| 依据展开 | 来源、采用范围、个人责任、反事实与证据限制，可定位到具体材料 |

首页保留筛选及展开状态；清除筛选不清空对照。手机端压缩介绍，不裁切人物评价和依据。人物称呼使用正式记录，缺称号才回退本名。统治绩效筛选不重排名；能力无排序入口，历史影响同档不另排名。

掌权时期是身份背景，各体系仍用各自合同规定的取证窗口。人物页和对照须说明该区别，不给画像补造时间边界。八轴雷达只辅助展示能力结构，空值不补零，不用面积或均值评价整体能力；C5独立展示。

## 数据与解释边界

- 从`config/project.yml`定位正式来源，以`ruler_id`连接。第一项按登记的Markdown真源读取，其余按正式JSON／裁决输入读取；投影不得反向覆盖裁决。
- 上游维护经历、归责、材料作用、定档理由、限制和来源。各人物页、专页、详情与对照共享上游公开字段；浏览器不拼接事实、补写判词或按字数截取正文。
- 史料原文、既有摘要、项目裁决及相关材料汇集分别标明。引用定位只证明来源连续性，不自动证明逐句支持；缺证、未知状态或未定义代码显式提示，不猜配、不删掉难译部分。
- 只有已定义术语可确定性映射；复杂判词须回到上游复核。画像映射不作用于净收益正文，不全局替换中文词语，不从分数或声望生成额外人物标签。
- 未入榜、不适用、无档结案、待补证、待重裁和零值分别展示。全池专页按本分项正式集合构建，不因综合榜未就绪而漏人；回链只指向实际存在的人物页或就绪详情。

## 分项编辑与刷新

下表命令均接在`python v4.py`后。先编辑权威源，再刷新投影／阅读视图并校验，最后运行`reader`更新所有展示。分值变化须先同步分项汇总、综合榜及受影响分析；第一项总Markdown按其真源维护，第二项汇总用`second-item-totals --write`，第三项用`third-item-current-settlement --write`，不为第四项另造重算器。可先用`maintenance`查询其支持组件的下游与校验范围，见[根目录操作说明](../README.md#安装与日常操作)。

| 对象 | 人工编辑位置 | 刷新与校验 |
| --- | --- | --- |
| 第一项A | 正式A Markdown中的公开成果、问题与正文；伴随JSON为同源公开成果投影 | `first-item-a-public-verify` |
| 第一项B1、军事成本 | B1 Markdown的经历与三项说明；计时／对手正式依据；成本JSON的`public_reading`和`public_source_records` | `first-item-b1-cost-public-verify` |
| 第一项B2 | 正式B2 Markdown的窗口、本人控制链、三项依据、问题与正文 | `first-item-b2-public-verify` |
| 第一项C | 正式C Markdown的本人引用、窗口、采用与去重；事实回源公共战役登记 | `first-item-c-public-verify` |
| 第二项A | 正式JSON的`public_story`、`public_adjudication_summary`、`public_evidence_items` | `second-item-a-public --write` → `second-item-a-verify` |
| 第二项B1 | 正式JSON的具体经历、本人责任、定档与逐材料解释 | `second-item-b1-public --write` → `second-item-b1-verify` |
| 第二项B2 | 正式记录的定档、事实、方向、阶段和史源 | `second-item-b2-public --write` → `second-item-b2-verify` |
| 第二项C1—C4 | 各正式JSON的人物正文、损害边界、材料关系、个人限制与史源 | `second-item-c-public --write` → `second-item-c-verify`；分项汇总核对用`formal-settlements-verify --item second_item` |
| 第二项D1、D3 | 两份正式JSON的经历、窗口、责任、定档与逐条史源 | `second-item-d1-d3-public --write`；省略`--write`校验 |
| 第三项A | `config/third-item/third-item-result-credit-adjudications.json`各A轴的`public_reading` | `third-fourth-item-public --write` → `formal-settlements-verify --item third_item` |
| 第三项B | AB正式JSON的B1、B2、B4各轴`public_reading` | `third-fourth-item-public --write` → `third-fourth-item-public-verify` |
| 第三项C | 正式C JSON的`public_reading`；战略链配置不保存正文副本 | 正文：`third-fourth-item-public --write` → `third-fourth-item-public-verify`；战略链写回与校验用`third-item-c-settlement`，写回才加`--write` |
| 第四项A／B／C | 正式JSON的轴与材料公开字段；C逐条史源为`public_c_result_reading.sources` | `third-fourth-item-public --write` → 对应`fourth-item-a/b/c-views --write` → `fourth-item-a/b/c-verify`（选实际轴命令） |
| 人物画像 | 对应轴正式JSON；M1正文直接维护在`public_reading` | `profile-markdown --axis <轴> --write` → `profile-manifest --axis <轴> --write` → 项目登记的轴校验；如`profile-m1-verify`、`profile-m5-verify`、`profile-c4-verify` |
| 历史影响 | 正式记录的`public_total_basis`、四维`public_basis`与`public_boundary` | `historical-impact-views --write` → `historical-impact-verify` |
| 军事人才 | 当前人物记录及其有效来源 | `military-talent-views --write` → `military-talent-verify`，再更新军事档案 |

主态低谷与净恢复的逐人阅读页用`governance-state-recovery-report --write`刷新，以`governance-state-recovery-verify`核对；不额外维护跨项文件哈希。军事人才刷新保留身份和已裁档位，不从父战役重新生成裁决。

## 公众展示总原则

默认先读人物做了什么、面对什么条件、留下什么结果；内部指标、变量与中间量放“规则与计算”。公开标题使用中文名称，原始字段保留于正式记录和详情数据。

第一项按“统一成果／起点、强敌与速度／组织与整合／本人统帅／战争代价”展示。A先显示`public_question`、`public_story`，再展开归属、尺度和证据；`public_boundary=null`时省略，不补空栏目。全国尺度与共同项目分配按[A合同](../docs/分项规则/第一项政权奠基与统一贡献及能力/00-规则与计分合同.md)区分，计算说明读取`reading_guide`及正式Markdown“计算”字段。共享成果说明本人承担部分，不用内部“控制信用、分账”等词代替人物经历。

B1独立展示起点、对手、效率三项，合计不解释成能力或纯速度；分阶段计时不合并为单一年数，浏览器不补对手或改工期。B2先展开职责，再呈现三项依据、限制与史料，不从名单、篇幅或画像档位换分。军事成本分别展示负担、损失与限度、定档依据和范围，来源逐一对应；负向成本用严重度刻度及档内位置，不反用能力等级。

第一项C只从公共战役登记解析本人结果、成员、具名行动或范围引用，不从M1或武将汇总反推。已定档战役按战果等级排列，保留“前线作战／战略统筹”、难度和档案链接；个人证据节点不伪装成新战争，不按名称猜档案，不另造含金量分。各第一项专页保留锚点和阅读位置，旧异步增强不得替换专页正文。

第二项A无节点时保留证据边界及空材料列表，不生成占位卡或数量总结。B1刷新不得用条数总括覆盖正文；B2中有效机制的零权重阶段不把整组变成背景。C区分逐条支持与相关材料汇集；D1、D3按各自合同分别展示行政连续性、长期资产旁证及交接安全窗口，不以同一观察期混用。

第三项A分开交班基础与本人增量，保留0档。B分列现行AB的`score_rate`、结果信用的`adjudicated_*_rate`和另存诊断率，明确B4复核状态；暂留现值不等于复核通过。第四项撤资格材料保留事实但不参与正向合成；零值区分未确认独立变化、复核后不计分与正负相抵，不借前后任或其他项目补写本人结果。

M1先讲本人行动与定档，再展开战役、行动及人才档案；比较分别选择同档同位和同档异位人物，前者不存在时明确标为同档邻位例外，并链接对方当前等级。人才生涯档位不参与M1换算，未证实的档案、战绩或直接指挥不得补造；单次操作可共享只读档案索引，修改后不跨操作沿用缓存。

## 第三项C证据阅读

`third-item-c-public.js`供人物页、详情、对照及全池页共享全文，C2／C3原始组件保留数据但不另造总评。三轴`public_reading.axes.*.arguments`说明材料作用，引用`evidence_items`具体条目；只有`C-DECISION`总评引用时明确显示具体战争证据缺口。

`source_passages`校验摘录位于所指通读文件及战事段落，不冒充古籍原文复核。`source_reviews.source_material_refs`关联本人物、本链已具来源摘录的补充材料；`boundary_material_refs`单列跨任期、仅载请求等范围核对，不作本人战争事实。建立定位不自动补三轴论证或改变评分，未定位的过程继续保留缺口。

三方面档义读取公开投影`scale`，分数区间读取`GRADE_RANGES`；三轴、原始档、资格上限、最终档及档内位置分开呈现，规则引用[现行C合同](../docs/分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md)，不在页面另写公式。显式档内裁决展示采用位置、替代理由与计算；分界状态区分已回源支持、待证、冲突及须重裁。第一方面公开名为“实战表现”，其判断说明由`third_item_c_public.py`统一提供，不用目标未成直接代替全役失败。

逐条论证按`evidence_ref`直达材料，完整链与相邻档论证使用显式`evidence_refs`；缺少关联即提示，不按战名猜配。材料集中展示正文、原编号、采用范围、来源及摘录；人物与材料锚点可分享，跨入口展开后聚焦对应材料，不丢失当前人物路由。旧父任务统计不冒充当前战略链数量。

## 轻量加载架构

| 产物 | 加载时机与校验 |
| --- | --- |
| `index.html` | 只内嵌首页所需身份、排序字段和轻量概览；搜索、筛选、排序、选人不先加载全部依据 |
| `data/people/<ruler_id>.json` | 单人页加载一人，对照加载两人；含完整正式投影与来源可用性，在页面内存中复用 |
| `data/third-item-c/` | 全池C页展开某人时加载其HTML详情；并发请求复用，材料与完整正文不截断 |
| C全文索引 | 仅选择完整正文搜索且输入查询后加载；索引覆盖全文，不只摘要 |
| `data/first-item/`、`data/military/` | 第一项来源缓存、战役／人才索引及证据分片 |

刷新页面后首次取人物详情须向服务端校验缓存；C详情和索引URL带内容版本。加载失败显示错误并可重试，不冒充零结果。构建及`--check`动态核对覆盖、文件名、引用和内容，构建只清理对应生成目录的失效分片。站点为纯静态HTML／JS／JSON，无运行时数据库或应用后端。

## 等级与公众展示

人物画像能力轴采用公开字母等级与档内位置，正式G档和雷达值保留在专业数据中；映射按[画像合同](../docs/项目总纲/皇帝人物画像评估体系合同.md)，页面不另存评分规则。C5描述权力运用与克制，不解释为能力，也不进入八轴雷达。

历史影响按[影响合同](../docs/项目总纲/历史影响评价总则.md)展示公众总档及四维，并常驻提示刻度不同；同字母不表示与画像同尺度。正文直接读取正式公开字段，不从四维重新拼装理由、平均计算或自动算总档。技术映射可折叠，但不得遮蔽分项及原文。

## 阅读层边界与人物摘要

`person-reading-notes.json`使用`reader-person-overviews-v2`，每人只允许`overview.outcome/profile/impact`三个摘要，每段只含`text`和`evidence`，每处定位只含`path`与`quote`。摘要可组织已有内容，不新增事实、规则、材料权重或归责，不省略影响原意的反证，不由分数、标签或原文前几句自动生成。

定位须指向该人物当前详情事实，引用原样显示并标为项目记录，链接返回正式入口。定位撤回仅令该摘要待复核，不改人物状态；正式改档本身不使摘要失效。未覆盖者用原页面；缺失、过期或加载失败均不得隐藏原始依据。

`person-reading-notes.js`只作用于人物概览，不介入分项正文；对照、首页和选人页不请求摘要。逐轴事实、反证与解释不得另存摘要文件，校验拒绝`axes`等额外字段；需通俗的正式解释时回上游复核。

C5材料强度直接展示父情境`intensity`及`material_intensity`，名称遵循画像合同。缺失、未知枚举、字段冲突分别提示，不从次数、方向或最终档位补填；强度不等于分数或伤害严重性，事实、方向和总体权衡各取正式记录。

## 构建产物与维护边界

| 文件 | 职责 |
| --- | --- |
| `*.template.html`、`*.js`、`*.css` | 布局、共享排版与交互；`lazy-details.js`负责人物分片加载，`home-interactions.js`负责首页与分项路由 |
| `public-copy.json`、`second-item-summaries.json`、`person-reading-notes.json` | 人工文案及摘要；只整理已有内容，不参与评分 |
| `military-reading-notes.json` | 带出处的军事补充摘要与核心交战时间，不参与定档 |
| `build.py`、军事档案／第一项缓存构建器、`build_site.py` | 投影、分片、校验和完整站点打包 |
| 非模板HTML、`data/`、`source-revision.json` | 可重建生成物，不手工编辑、不进入Git |

GitHub Actions在相关源变化后构建、检查并直接发布Pages artifact，不回写源码分支。发布前核对分支仍指向已验证提交，线上史源链接绑定该提交。`.tmp/pages-site/`只含运行页面、资源和阅读数据；本地完整史源阅读仍用`serve.py`。发布验收须对应到源提交的构建和行为检查，单看Pages成功不足以确认。

修改按影响选择已有组件与阅读测试。人物摘要重点运行`tests/test_reader_person_readability.py`和`tests/test_reader_public_boundaries.py`，复验人物／对照、缺失强度、撤回来源及加载失败；其他分项选对应测试。合并时先解决合同、源记录与生成器冲突，再重建，不拼接生成文案。测试验证合同、同源、只读及展示行为，不固定人物等级或历史批次数；结构通过不代替历史语义复核。
