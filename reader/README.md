# 综合阅读层：帝王三镜

以人物为入口，并列呈现统治绩效、九轴人物画像与历史影响。阅读层负责排版、导航和追溯；评分、归责、准入及跨体系边界见[共同合同](../docs/项目总纲/皇帝综合评价体系合同.md)和[项目登记的分项合同](../config/project.yml)。

## 构建与检查

在仓库根目录运行：

```powershell
python v4.py reader
```

该命令调用`build_site.py`，先生成不入Git的大型Markdown阅读视图，再依次构建军事档案、全部阅读页面与人物数据、第一项来源缓存，检查页面和缓存同值，最后将完整静态站点打包到`.tmp/pages-site/`。新检出后先构建，再预览或运行依赖生成页面的测试；只生成Markdown用`python v4.py reading-views`。

历史影响、第二项C3／C4和第三项AB／C的Markdown入口为轻量总览，人物正文在旁边同名`-逐人阅读/`目录；长正文继续分页。正文和来源完整保留，生成与校验同时覆盖索引及全部分片。需要整份导出时运行`python v4.py reading-views --combined-output .tmp/reading-views-combined`；常规预览继续打开原路径。

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

B三轴及逐条依据的完整来源对象统一保存于本人的`public_b_source_catalog`，各处用`source_refs`保留原有顺序和重复采用；只合并字段、值与字段顺序均相同的对象。编辑来源保留登记ID，正文和引用须同步维护。公开构建、来源校验和阅读视图经`third_item_b_sources.expand_readings`展开；悬空引用、内嵌副本、重复或未使用的登记对象均报错。

第三项总表不另存汇总文案、材料列表和`public_military_cost`副本；完整公开记录由`third_public_record`按同一人物ID从现行AB、C等组件组装。普通成本正文保留在`global_cost_credit_profile`，重大军事净毁损说明保留在`public_military_net_loss`；组装不修改来源，跨人物引用报错。

综合榜的证据评价公开标签与正文只保存在`evidence_assessment.public_projection`。证据裁决敏感性结果通过顶层`ranking_source`声明总榜来源，不复制逐人证据评价和审慎区间；正式命令核验当前总榜并重建敏感性结果，阅读渲染显式传入总榜记录，按人物ID关联。身份缺失、重复、集合或名称不匹配、重新内嵌副本均报错；此关联不改变评分、情景计算或名次。

第三／第四项更新字段的归属由`third_fourth_public_fields.py`显式登记。评分同步按人物、轴、战略链或材料包的稳定ID保留本对象的公开字段，禁止按数组位置移接；新增对象不继承其他来源的公开副本。公开刷新只清理列明的派生字段，正文和来源目录默认保留；A／B阅读计算字段的更新及AB旧A轴正文副本的移除在调用处明确声明。新增公开字段或含公开内容的对象列表须登记维护归属与身份规则，未知字段、重复或缺失身份均报错。

第二项C4的正文只维护`public_reading_sections`六个分栏，`recovery_public_record`按既定顺序拼接阅读正文，不重复保存`public_story`。D1／D3保留原始采用引文`excerpt`及定位信息，`second_item_d1_d3_public.public_record`沿用既有格式规则生成`public_excerpt`，不另存展示副本；原始引文仍须与史源逐字核验。

第四项各轴公开字段只在正式记录的`axis_results`内维护，人物级不另存轴投影、材料拼接列表或汇总文案副本；读取时按轴代码定位，汇总按A/B/C顺序组装，缺失或重复轴均报错。

主态低谷与净恢复的逐人阅读页用`governance-state-recovery-report --write`刷新，以`governance-state-recovery-verify`核对；不额外维护跨项文件哈希。军事人才刷新保留身份和已裁档位，不从父战役重新生成裁决。

## 公众展示总原则

先讲人物做了什么、面对什么条件、留下什么结果，再展开定档理由和来源；字段、指数、权重和计算放在折叠区。

- 第一项按统一成果、创业条件、组织整合、本人统帅、战争代价展开；保留各项的分阶段归责和材料限制。
- 第二项按正式机制说明经历、本人作用和结果。没有合格节点就说明证据边界，不造占位卡；某阶段不另计，不等于整组材料无效。
- 第三项A分开接班基础与本人增量；B分开原始率、实际采用率和复核状态；C使用下节的共同正文。
- 第四项不计分的材料仍可保留事实；零值说明是没有独立变化、复核后不计，还是正负相抵。
- M1讲本人行动和定档，链接已登记战役、人才及比较对象；人才生涯档位不参与画像换算。比较对象不足时说明例外，不补造战绩或档案。

具体评分、归责和去重规则见上表所列合同。展示不另定义评分规则，也不从数量、篇幅或名望生成解释。

综合榜正式JSON不保存`component_details`展示副本；阅读构建通过`composite_details.reading_records`按规范池人物ID与各项正式来源生成完整明细。总榜结算仍校验各项明细与合成结果同值，阅读构建检查就绪人物集合、身份及重复ID，不回写正式记录。

画像C1、C3、M4保留的入口单元处置记录使用`profile-unit-reason-catalog-v1`理由存储格式：文件级`reason_catalog`保存完整原文，各单元按`reason_ref`引用。读取与维护使用`profile_unit_reasons.load_unit_dispositions`和`write_unit_dispositions`，写入自动合并完全相同的理由；理由不同则分别保留。目录不得存在悬空引用、未使用条目、重复正文或单元内嵌副本；不按处置状态猜测理由，不改变单元身份、来源、顺序或采用关系。

M4逐条合作过程在人物页、双人对照及Markdown阅读页中完整展开集团、利益、本人安排、兑现、反馈、退出和反证。任务作为卡片标题，方向、强度、跨轴边界与来源合并在正文后的折叠区，人物反例总述收进裁决详情。画像正文提到档内比较时明确保留高、中、低位，人物等级徽标仍使用既定符号。

C2按当前计分情境展示取得信息、理解与更新过程；过程补充、归责边界、采用史源和反证放在正文后的来源区。非计分材料单列，不能与计分过程合并；证据下限显示其有界性质和重开条件。正式记录中的`source_review`保存实际采用段落及限制，网页与Markdown同源读取；清理文案不得据渠道存在、处罚烈度或战争结果自动生成认知正负证。

第二项C1—C4不落盘`public_calculation`生成副本；`second_item_c_reading.calculation_record`按当前正式字段生成原有计算说明，供Markdown、人物详情和全池页面共用。刷新只维护元数据与阅读视图，正式校验拒绝重新内嵌计算说明；人工正文、来源说明及证据绑定仍直接维护在正式记录。

M1人才登记投影使用`m1-registry-cells-v1`存储格式，保留成果难度、战役角色两份有序原列表；两段`<br>`拼接文本及配对列表由`profile_m1_projection.registry_projection`生成。独立维护的配对展示正文仍原样保存，不以拼接文本覆盖；列表长度或编号不匹配时拒绝生成。角色裁决及父链上下文不从人才登记反推。

第二项C1—C4的完整来源说明保存在各轴`public_source_note_catalog`，每人按`public_source_note_ref`引用；不同原文分别保留。`second_item_c_source_notes.source_note_records`供读取方展开原文，`compact_source_notes`供刷新时合并完全相同的说明。缺失、悬空引用、目录未使用条目和内嵌副本均报错，不根据其他人物或来源类型猜补说明。

## 第三项C证据阅读

人物页、详情与对照使用`third-item-c-public.js`，全池页由`build_third_c_collection`生成；两者读取同一份正式`public_reading`正文。每人只展示一次连贯评价，不再逐字段重复总述、正证与反证。档位与档内位置、战事摘要、来源和计算按需展开。

公开正文的`story`、`position_explanation`及`task_titles`须在正式C记录中明确编写；页面不得猜写战名、拼接正反证或推算新的位置理由。任务标题覆盖本人现存战略链，编号继续留作引用键。战略链配置不保存公开正文副本。

`combat_delivery_grade`与`final_grade`保存同值的主评和整体档，`joint_assessment`保留正式正反证及位置裁决。阅读整改不得改写这些字段或分数。生成的量表、计分、任务与对手窗口只供投影，不重新内嵌成为第二套真源。

材料的`source_passages`保存来源摘录及定位。改写摘要与标题时保留材料ID、任务绑定、来源路径及引文；摘录能否在对应来源锚点找到，仍由来源校验核对。

材料展示原编号、采用范围、来源和摘录。`source_passages`只证明摘录能在所指通读文件中找到，不冒充已复核古籍原文。补充材料与跨任期等边界核对分别列出，不能混成本人战争事实。

档位含义读公开`scale`，分数区间读现行联合计分区间。整体档与显式档内位置分别说明，不展示已退役的三轴短板或资格上限。待定保持空分，不改写为零分。

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

摘要加载失败时保留原页面；已发布页面遇到摘要引用失效时显示待复核提示，不展示过期正文。构建按当前主池核对三段摘要覆盖与每条引文，缺失或失效会报错，修复后才能生成新版本；此错误不表示正式评分失效。未入榜人物可引用评价池的就绪状态，不能保留已不提供的分项引用或把未入榜写成零分。来源撤回只使摘要待复核，正式改档不自动使摘要失效。`person-reading-notes.js`只处理概览，对照、首页和选人页不请求摘要，逐轴正文不另存摘要副本。

C5材料强度读正式`intensity`、`material_intensity`；缺失、未知或冲突分别提示，不从最终档位倒推。

代表情境直接读取正式过程字段：用人授权展示`evidence_title`与`lifecycle_narrative`；内部联盟按合作任务、集团、利益预期、本人选择、资源安排、交付、反馈、退出和反证分栏，保留完整过程判断及跨项边界。不以方向标签或来源链接代替过程正文；未提供正文时明确提示。

C1展示正式`cycle_basis`，按原有句段展开长过程，专题标题读取正式`evidence_title`。方向、材料用途和来源放在情境末尾；未列入正反例引用的正式代表材料仍须展示，计分材料与背景、归责及轴外边界分别呈现，不把边界材料混成负证。人物表现和定档理由说明当前判断，不叙述旧档位的升降过程。

M5按正式`process_narrative`展示完整过程与边界，沿用已有段落及任务分解等小标题；未标方向时不从标题或档位推断。归责、跨轴边界和来源置于卡片末尾，反例总述放入裁决详情，不复制整段逐案正文。Markdown同步展示所选过程的完整文字，不能只取首行。展示条目数不等于独立复杂任务数，补齐展示不改变评分依据。

C3按正式`evidence_detail`逐条展示人物或任务，小标题取自原有条目；没有逐条材料时展示`lifecycle_narrative`。方向标签、评价边界与来源合并在卡片末尾；完整过程与条目有差异时保留在其中。反例总述放入裁决详情，与逐案材料分层呈现。公众文案直接说明当前认定、理由和适用范围，不用“退出强负证”“正式剔除”等审查操作代替结论。

C3卡片标题按实际人物与任务主题书写，不因其处于第二张卡就统一标为负向；反例总述区分已证失误、独立过程证据不足与本人归责边界，不复制正向任用材料充当反例。概览引用随正文调整重新核对，仍指向说明同一事实的当前字段。

C5在“进一步核对”内直接按正式`public_evidence_points`逐案展示，正式情境的方向与强度索引置于末尾折叠区。案件说明区分必要制伏、威胁受控后的处分及家属扩大，不因政治竞争身份整体豁免。定档理由、情境方向、单位引用与正文必须对应同一组当前事实；旧导入审计可以保留退役情境的来源定位，但不冻结当前裁决。E3按现行C5合同核对持续性与独立情境，不用事件烈度、人数或段落数量替代覆盖。

C4展开正式`parent_chains`的全部制度过程与适用边界，按具体制度命名，保留`mechanism`以及已有的问题、选择、职责规则、运行和修订字段。方向、归责、采用范围与来源放在正文之后，反例总述和`architecture_review`放入裁决详情；Markdown同步完整展开，不按字符数截断。整合设计的组成部分、背景和证据缺口不因展示成为新的独立计分设计；适用性直接读取正式`applicability`，不把材料少解释为不适用或低能力。

M2按正式`consumption_status`分别展示计分外交过程与不计分边界，读取全部`parent_chains`的标题、完整`cycle_basis`及已登记的身份转换、归责和来源采用。内部安置、婚姻背景、臣使独立成果和证据缺口不因展示而计分；旧材料的方向标签不能推翻现行采用范围。“未显示外交能力”保留其终局类别与限制，不借背景负向材料改写成已证反复失能。Markdown与人物详情共用当前正式事实，概览引文同步核对。

人物画像展开某轴后，主要表现与正式`grade_basis`的整体理由在同一阅读层显示，避免只见局部正例却不见整体低档的解释；档内定位和材料限制保留在进一步核对中。两段规范化后完全相同时只显示一份；定档理由仅以表现段落结尾时仍须保留前面的独立判断。人物页与对照页共用此规则，军事统帅继续使用专属公开说明。

历史影响的主链与四维来源只消费正式`source_ref_indices`，不以人物相关资料自动补链。来源卡保留采纳段落、采用说明、使用范围、记录中的核对方式及人物／情境／字段定位；类型与核对方式标签由`historical_impact.SOURCE_DISPLAY`共享，未知代码明确提示。未单独绑定来源与已绑定项目材料但没有外部原典链接分开说明。人物页、对照页提供全部登记来源及独立的相关事实入口，正式Markdown同步展示这些信息；原史未逐句核对的边界不因链接存在而消失。

## 构建产物与维护边界

| 文件 | 职责 |
| --- | --- |
| `*.template.html`、`*.js`、`*.css` | 布局、共享排版与交互；`lazy-details.js`负责人物分片加载，`home-interactions.js`负责首页与分项路由 |
| `public-copy.json`、`second-item-summaries.json`、`person-reading-notes.json` | 人工文案及摘要；只整理已有内容，不参与评分 |
| `military-reading-notes.json` | 带出处的军事补充摘要与核心交战时间，不参与定档 |
| `build.py`、军事档案／第一项缓存构建器、`build_site.py` | 投影、分片、校验和完整站点打包 |
| 非模板HTML、`data/`、`source-revision.json` | 可重建生成物，不手工编辑、不进入Git |

第二项显示名称、档位映射和量表上限统一由`second-item-display.js`提供，先于使用它的脚本加载。`second-item-reading.js`直接输出最终分数文案；公开正文渲染器负责各自内容，不再通过后置脚本反复改写分数或页面措辞。

`GPT`相关源变化后，GitHub Actions构建、检查并发布Pages。发布前核对分支仍是已验证提交，史源链接绑定该提交；发布任务串行，不回写源码。`.tmp/pages-site/`只放运行资源，本地史源阅读使用`serve.py`。验收同时检查工作流和线上版本。

按影响选择已有测试；人物摘要重点检查`tests/test_reader_person_readability.py`和`tests/test_reader_public_boundaries.py`。冲突先解决源文件再重建。测试检查规则和展示行为，不固定人物裁决；文字是否符合史实仍由人工判断。
