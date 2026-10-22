# 综合阅读层：帝王三镜

以人物为入口，并列呈现统治绩效、九轴人物画像与历史影响。阅读层负责排版、导航和追溯；评分、归责、准入及跨体系边界见[共同合同](../docs/项目总纲/皇帝综合评价体系合同.md)和[项目登记的分项合同](../config/project.yml)。

## 构建与检查

在仓库根目录运行：

```powershell
python v4.py reader
```

该命令调用`build_site.py`，先生成不入Git的大型Markdown阅读视图，再依次构建军事档案、全部阅读页面与人物数据、第一项来源缓存，检查页面和缓存同值，最后将完整静态站点打包到`.tmp/pages-site/`。新检出后先构建，再预览或运行依赖生成页面的测试；只生成Markdown用`python v4.py reading-views`。

局部更新页面用`python reader/build.py`；第一项来源变化另运行`python reader/build_first_item_reader_cache.py`，军事登记或档案说明变化另运行`python reader/build_military_archive.py`。前两项命令加`--check`只读核对当前生成物。

整站构建与 CI 对每份输出只生成一次；`--check`用于独立核对已有产物，不在刚完成构建后重复执行。发布前由行为测试、源与阅读同值检查及站点打包完整性检查负责验收。

## 本地预览

人物详情通过`fetch`读取分片，完整浏览须使用HTTP服务：

```powershell
python -m pip install -r reader/requirements.txt
python reader/serve.py
```

访问`http://127.0.0.1:8765/reader/index.html`。本地服务把正式Markdown／JSON转为只读阅读页，对`reader/data/`直接返回原始数据；军事档案读取正式分片时使用`?raw=1`，与线上加载一致。

## 信息结构

| 页面 | 用途 |
|---|---|
| 人物总览 | 搜索、筛选、排序和选择对照；默认按历史顺序。 |
| 人物阅读 | 先看三体系概览，再展开各项事实、理由、反证和来源。 |
| 并列对照 | 同一维度并排阅读；突出差异只改变强调样式，不隐藏依据。 |

筛选和展开状态保留，清除筛选不清空对照。手机端可以缩短介绍，不能裁掉人物依据。画像不排名、不算总分；历史影响同档不另排名。各体系的取证时期按各自合同，不能只凭身份页的掌权时间推断。

## 数据与解释边界

数据入口由`config/project.yml`登记，以`ruler_id`连接。第一项读Markdown真源，其余读对应正式JSON。正文、理由、限制和来源在上游维护，人物页、对照页和专页使用同一份内容。

浏览器只排版、导航和转换已定义的显示标签，不编写历史判断。原文、项目判断和相关材料分别标明；有引用不等于已证明整句话，缺证或未知代码要明确显示。

未入榜、不适用、无档结案、待补证、待重裁和零分分开显示。专页按本分项正式名单覆盖，不因综合榜未就绪而漏人；链接只指向实际存在的页面。

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

第三项A正文只在结果信用输入的`axes.A1/A2.public_reading`维护，B正文只在AB正式记录的`axes.B1/B2/B4.public_reading`维护。AB与结果信用记录不再保存`public_axis_projections`副本，AB的A轴也不复制正文；Markdown与阅读页面按人物ID读取上述来源。

主态低谷与净恢复的逐人阅读页用`governance-state-recovery-report --write`刷新，以`governance-state-recovery-verify`核对；不额外维护跨项文件哈希。军事人才刷新保留身份和已裁档位，不从父战役重新生成裁决。

## 公众展示总原则

先讲人物做了什么、面对什么条件、留下什么结果，再展开定档理由和来源；字段、指数、权重和计算放在折叠区。

- 第一项按统一成果、创业条件、组织整合、本人统帅、战争代价展开；保留各项的分阶段归责和材料限制。
- 第二项按正式机制说明经历、本人作用和结果。没有合格节点就说明证据边界，不造占位卡；某阶段不另计，不等于整组材料无效。
- 第三项A分开接班基础与本人增量；B分开原始率、实际采用率和复核状态；C使用下节的共同正文。
- 第四项不计分的材料仍可保留事实；零值说明是没有独立变化、复核后不计，还是正负相抵。
- M1讲本人行动和定档，链接已登记战役、人才及比较对象；人才生涯档位不参与画像换算。比较对象不足时说明例外，不补造战绩或档案。

具体评分、归责和去重规则见上表所列合同。展示不另定义评分规则，也不从数量、篇幅或名望生成解释。

## 第三项C证据阅读

`third-item-c-public.js`供人物页、详情、对照及全池页共用完整正文。三轴论证按`evidence_ref`连接具体材料；只有总评引用时，说明缺少具体战争依据，不按战名猜配。

材料展示原编号、采用范围、来源和摘录。`source_passages`只证明摘录能在所指通读文件中找到，不冒充已复核古籍原文。补充材料与跨任期等边界核对分别列出，不能混成本人战争事实。

档位含义读公开`scale`，分数区间读`GRADE_RANGES`。三轴、原始档、资格上限、最终档和档内位置分开显示；人工选择的档内位置同时展示理由和计算。已支持、待证、冲突、须重裁分别标明。

人物与材料锚点可分享，跨入口打开后定位到对应材料，不丢失当前人物。

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

画像的公开字母、档内位置和雷达映射按[画像合同](../docs/项目总纲/皇帝人物画像评估体系合同.md)。八个能力轴可画雷达，空值不补零，不用面积或均值评价整体；C5单列权力运用风格。

历史影响按[影响合同](../docs/项目总纲/历史影响评价总则.md)显示总档和四维。两套字母刻度不同，页面须说明；历史影响总档直接读取正式判断，不平均四维或自动重算。

## 阅读层边界与人物摘要

`person-reading-notes.json`只写人物概览，格式为`reader-person-overviews-v2`：每人有`overview.outcome/profile/impact`三个摘要，每段含`text`和`evidence`，每处依据含`path`与`quote`。

摘要可以整理已有内容，不能增加事实、分数解释或归责，也不能省略会改变意思的反证。引用须对应本人当前详情，原样显示并链接正式入口；不按分数或原文前几句自动生成。

摘要缺失、过期或加载失败时保留原页面。来源撤回只使摘要待复核，正式改档不自动使摘要失效。`person-reading-notes.js`只处理概览，对照、首页和选人页不请求摘要，逐轴正文不另存摘要副本。

C5材料强度读正式`intensity`、`material_intensity`；缺失、未知或冲突分别提示，不从最终档位倒推。

## 构建产物与维护边界

| 文件 | 职责 |
| --- | --- |
| `*.template.html`、`*.js`、`*.css` | 布局、共享排版与交互；`lazy-details.js`负责人物分片加载，`home-interactions.js`负责首页与分项路由 |
| `public-copy.json`、`second-item-summaries.json`、`person-reading-notes.json` | 人工文案及摘要；只整理已有内容，不参与评分 |
| `military-reading-notes.json` | 带出处的军事补充摘要与核心交战时间，不参与定档 |
| `build.py`、军事档案／第一项缓存构建器、`build_site.py` | 投影、分片、校验和完整站点打包 |
| 非模板HTML、`data/`、`source-revision.json` | 可重建生成物，不手工编辑、不进入Git |

`GPT`相关源变化后，GitHub Actions构建、检查并发布Pages。发布前核对分支仍是已验证提交，史源链接绑定该提交；发布任务串行，不回写源码。`.tmp/pages-site/`只放运行资源，本地史源阅读使用`serve.py`。验收同时检查工作流和线上版本。

按影响选择已有测试；人物摘要重点检查`tests/test_reader_person_readability.py`和`tests/test_reader_public_boundaries.py`。冲突先解决源文件再重建。测试检查规则和展示行为，不固定人物裁决；文字是否符合史实仍由人工判断。
