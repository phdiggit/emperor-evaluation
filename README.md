# 皇帝综合评价体系 V4

本仓库保存三套评价体系的当前规则、可审计证据、确定性结算逻辑与唯一结果入口。各项当前状态与复核边界见项目配置及对应正式入口。已退役的模型抽取、浏览器检索、source-cache、shadow、数据库服务和部署链不再保留。

## 正式结果

统治绩效、人物画像、历史影响是三套并列体系，不互相换分：

- [综合阅读层：帝王三镜](reader/index.html)（[设计与构建说明](reader/README.md)）：正式数据驱动的离线交互样稿，支持人物总览、三体系并列阅读、双人对照与依据展开；运行`python reader/build.py`更新展示。
- [人物画像九轴结算汇总](docs/评分结算/人物画像/九轴结算汇总.md)：八个能力轴与C5行为风格轴。
- [历史影响量级正式结算](docs/评分结算/历史影响/01-历史影响正式结算.md)（[合同](docs/项目总纲/历史影响评价总则.md)）：历史路径差异、长期足迹与个人归责。

统治绩效体系四项正式结果：

- [皇帝统治绩效综合评分榜](docs/评分结算/净收益/00-统治绩效综合评分榜.md)
- [第一项：政权奠基与统一贡献及能力](docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/01-第一项政权奠基与统一贡献及能力正式结算.md)
- [第二项：治国净收益](docs/评分结算/净收益/第二项治国净收益/01-第二项治国净收益正式结算.md)
- [第三项：军事与边疆净收益](docs/评分结算/净收益/第三项军事与边疆净收益/02-第三项正式结算.md)
- [第四项：文明与国家整合收益](docs/评分结算/净收益/第四项文明与国家整合收益/02-第四项文明与国家整合收益正式总榜.md)

机器读取入口与范围统一记录在 [`config/project.yml`](config/project.yml)。共同上位合同是[皇帝综合评价体系合同](docs/项目总纲/皇帝综合评价体系合同.md)，统治绩效结算公式见[皇帝统治绩效评价合同](docs/项目总纲/皇帝统治绩效评价合同.md)。

正式评价池按实际独立最高权力至少3年和证据可行性筛定。当前人数、待补对象及分项别名统一见[`正式评价对象范围`](docs/项目总纲/正式评价对象范围.md)及其机器入口`config/common/canonical-ruler-pool.json`，本页不另存人数副本。综合计算只读取`COMPOSITE_READY`对象；第一项不适用者取F=0。

## 聊天版评估包

运行 `python package_net_review.py`，生成 `.tmp/evaluation-packages/皇帝三体系评估包.zip`，供上传给聊天版临时会话阅读。

包内包含统治绩效、人物画像、历史影响三个体系的完整原始合同、正式结算 JSON 及其全部路由分片、Markdown 结算源/阅读视图、总榜所链接的综合分析阅读页，以及项目入口、正式人物池、总榜治理规模／复杂度的非计分分类源和 `docs/公共成果/` 下的 Markdown、JSON、文本资料。源文件逐字节复制，保留仓库路径；不再生成精简合同。包根目录只增加使用说明和文件清单，不打入代码、展示素材、过程审计及其他目录的完整史料库。结算记录中的依据和引用保留，但包外史料仍需另行补充，不能把包内阅读当作完整溯源。

默认只生成一个完整包，包含上述公共成果资料。`--output <路径.zip>` 可指定输出，`--list` 只查看入包清单；如需分开上传，使用 `--package contracts|settlements|profile-contract|profile-settlements|historical-impact-contract|historical-impact-settlements` 单选统治绩效、人物画像或历史影响的合同/结算，所有输出均为 ZIP。

## 保留范围

- `archive/`：[完整退役组件的最后有效合同、证据与结算](archive/README.md)，不进入现行评分或发布。

- `docs/项目总纲/`、`docs/分项规则/`：当前评分合同。
- `docs/评分结算/`：统治绩效、人物画像与历史影响的正式结果及同值阅读视图；第一项使用 Markdown 结算源。
- `docs/展示成果/人物画像/`：雷达图、视频人物卡与文字小样的派生展示，按配置中的输出目录生成。
- `docs/公共成果/`、`docs/治理/`、`docs/史料通读产物/`：仍被评分结果引用的证据与公共登记。
- `config/project.yml`：项目状态、正式结果入口和保留的重建接口。
- `config/common/`：正式评价池、分项候选名册与实体身份；其中`canonical-ruler-pool.json`是综合范围唯一机器入口。`config/third-item/`保存第三项当前裁决输入；`config/military/`保存公共军事登记与人才登记的当前输入。
- `src/emperor_v4/evaluation/`：公共军事登记、第一项 Markdown 正式结算读取和第三项确定性结算逻辑。

## 验证

按 [AGENTS.md](AGENTS.md) 的改动类型选择检查，以下是按需使用的命令参考，不是每次必跑的步骤。使用当前 Python 环境；需要 UTF-8 子进程或托管能力时再加 `codex-win run --`。

局部维护先按分项及稳定人物ID定位当前记录、下游同步和复核范围。分项代码为`I1`—`I4`、`I2.A`、`I2.B1`、`I2.B2`、`I2.C1`—`I2.C4`、`I3.D`及`profile.M1`等九个画像轴；也支持`pool`和`composite`。

```powershell
python v4.py maintenance --component I2.B2 --ruler-id RULER-HAN-LIUHENG
python v4.py maintenance --component profile.C2 --polity 西汉 --verify
```

默认只读，按朝代分片定位人物；`--verify`检查当前分项，B2支持选定人物的合同约束及阅读视图同值。`--related`额外执行关联轴校验。报告分别列出确定性下游、语义复核对象和刷新命令；`--sync`先校验当前源，再依次刷新列出的下游并回验，不自动重裁关联人物。源裁决和没有阅读视图生成器的源文档仍按局部patch维护。整池排名及覆盖检查读取对应完整组件，局部报告不代表全池语义验收。

```powershell
python v4.py maintenance --component I2.B2 --ruler-id RULER-HAN-LIUHENG --sync
python v4.py formal-settlements-verify --item second_item
```

入口路径或登记变化时检查一致性：

```powershell
python v4.py project-entries-verify
python v4.py military-talent-verify
```

军事人才局部裁决直接维护当前人物记录及其有效来源；完成后运行`python v4.py military-talent-views --write`同步净值、统计和阅读视图，再执行上述校验。此命令保留人物ID与已裁档位，不从父战役重新生成身份或裁决，也不恢复退役人才生成器。

首次安装：

```powershell
python -m pip install -e .
```

全链改动或全池验收时，验证四项正式结果、唯一人物 ID、分值范围和排名顺序：

```powershell
python v4.py formal-settlements-verify
```

评价范围变更时重建或核对正式评价池：

```powershell
python v4.py canonical-ruler-pool
```

单轴入口登记或结算视图变化后，只刷新该轴的正式入口清单（省略`--axis`才做全量注册表生成）：

```powershell
python v4.py profile-manifest --axis C1 --write
```

M5当前裁决维护后，生成同值阅读页并检查身份窗口、来源与共同投影：

```powershell
python v4.py profile-markdown --axis M5 --write
python v4.py profile-m5-verify
```

历史影响只从当前裁决生成阅读页，不由四维自动算总档：

```powershell
python v4.py historical-impact-views --write
python v4.py historical-impact-verify
```

综合计分输入变化时重建综合总榜：

```powershell
python v4.py composite-ranking --write
```

第二项组件变动后，`python v4.py second-item-totals --write`同步汇总与四张阅读页；A制度建设的人物正文、定档理由和逐节点事实直接维护在正式JSON，`python v4.py second-item-a-public --write`只同步逐字证据投影及Markdown阅读段，不从权重或数量生成历史解释；B2反馈与约束的公开裁决投影使用`python v4.py second-item-b2-public --write`，该命令保留直接维护在正式记录中的定档说明与逐条正文，只刷新结构元数据并同步Markdown；`reader/second-item-b2.html`提供全池入口，概览、对照与详情使用同一正文及逐条史源，C1—C4财政民生结果的公开裁决投影使用`python v4.py second-item-c-public --write`。第三、第四项公开裁决投影使用`python v4.py third-fourth-item-public --write`，可用`python v4.py third-fourth-item-public-verify`单独校验。第二项正式校验同时核对组件抄录、竞争排名、公开字段及阅读同值。

第二项C的人物正文、损害证据边界、逐条史源和个人限制直接维护在正式JSON；已绑定的逐条依据与尚未建立逐条支持关系的相关材料汇集分别展示，明确采用范围和推断性质。`second-item-c-public --write`保留正文与来源，只同步计算说明、元数据和四张Markdown阅读视图。`reader/second-item-c.html`提供全部正式C记录入口，详情与对照只展示同一上游字段。修改后运行`python v4.py second-item-c-verify`、`python v4.py formal-settlements-verify --item second_item`及阅读层构建和检查；结构、引用定位与同值通过不代表史源已在语义上证明对应事实。

第二项D的具体经历、当前定档说明、观察窗口、本人责任、限制及逐条史源直接维护在D1、D3正式JSON；原文转录、既有摘要和评价判断分别标明。`python v4.py second-item-d1-d3-public --write`保留全部公开正文与引用，只刷新元数据及两张Markdown；不加`--write`校验来源、正文和阅读视图。详情、概览与对照使用同一上游字段，原文摘录和来源逐条展开；随后运行第二项正式校验及阅读层构建、检查。公开文案维护不改评分。

第三、第四项公开文案使用明确的中文术语及绑定原句的完整转述，未知代码或英文必须补充转述后才能生成，不得删除字母或拼接残句。校验同时比较完整公开投影与非公开评分来源；结构校验不代替文意复核。修改转述后重建公开字段，再运行`python reader/build.py`及`python reader/build.py --check`。合并时先解决合同、源记录与生成器冲突，再重建公开投影和`reader/data/people/`，不要手工拼接生成文案。Pages成功不代表Build reader成功，发布验收须确认对应提交的构建与行为检查均通过。

第三项A的具体经历、定档说明、本人责任、评价时期和来源直接维护在结果信用正式JSON各轴的`public_reading`中。公开投影保留正文并核对来源定位，只刷新基于合同的计算和档位说明，同步AB正式JSON及Markdown；人物页、第三项详情与对照页使用同一正文。修改后运行`python v4.py third-fourth-item-public --write`、`python v4.py formal-settlements-verify --item third_item`和阅读层构建／检查。判词与计分矛盾须先核对现行归责与交班依据，不为展示修改分数。

第三项B正文与逐条来源维护在AB正式JSON的B1／B2／B4各轴`public_reading`；原始率、实际采用率及另存诊断率分列，B4复核状态随正式来源明确展示。现值暂留不等于复核通过。上述公开投影命令保留正文、核对现行来源并同步空间快照与B合成计算、Markdown；随后构建阅读层，人物页、详情和对照使用同一正文。失效过程引用替换为现行区域及归责依据，不恢复已退役文件，不因展示整理改变评分。

主态低谷与净恢复 V4 已统一启用（L有限修正，历史K不计分）；可用 `python v4.py governance-state-recovery-verify` 校验，或用 `python v4.py governance-state-recovery-report --write` 刷新逐人阅读页。启用与刷新不做跨项文件哈希同步。

第一项 C 的事实真源是公共战役登记。正式 C Markdown 逐条绑定公共本人结果、成员、具名行动或范围说明，声明采用、窗口及同情境去重；缺证先回源补登记，不从 M1、武将汇总或旧判词反推。`python v4.py first-item-c-public-verify`验证全部当前对象、本人引用、源路径、处置和档分同值；阅读页`reader/first-item-c.html`默认展示逐人问题与经历，职责后再展开评价、胜败和逐条公共原字段。分值改判同步第一项总视图、综合榜与相关分析，再构建主阅读页和逐人缓存。

人物画像 M1 的公开正文直接维护在正式 JSON 各人的 `public_reading`：先讲本人行动和定档、档内位置，再按需展开战役、本人行动与武将档案。比较选择一位同档同位、另一位同档异位人物，显示对方当前正式等级并直达 `/profile/M1`；当前池没有其他同位对象时，只能使用明确标注的同档邻位例外。武将人物级档位不参与M1换算；没有独立武将档案或未证实具体本人行动时，不补造档案、战绩和直接指挥。修改后运行 `python v4.py profile-markdown --write --axis M1`、`python v4.py profile-manifest --write --axis M1`、`python v4.py profile-m1-verify`，并构建、检查阅读层；同一操作共享只读档案索引，不跨修改保留缓存。

第一项 B1 的逐人阅读问题、阅读正文、起点、对手和效率说明维护在 B1 正式 Markdown；计时阶段、具名对手及计算参数维护在正式入口登记的 B1 计时与对手依据。`python v4.py first-item-b1-cost-public-verify`核对来源、公式与正式分数，再用`python reader/build.py`及`python reader/build_first_item_reader_cache.py`同步展示。分数变动须先同步第一项总表并运行`python v4.py composite-ranking --write`，相关分析按其命令重建。阅读层直接展示上游内容，不补对手、不改工期；分阶段效率不合并成单一年数。军事成本正式 JSON 的`public_reading`分别维护战争负担、实际损失与限度、定档依据和范围；`public_source_records`逐一对应正式来源，具名区分材料汇集、通读摘要与范围规则，原书链接不冒充逐句证明。责任时期、证据缺口及逐事补充史源同步保留，完整依据与来源分层展开；阅读层不加工历史解释。

第一项 B2 的评价窗口、本人控制链、三项档位依据及逐人阅读问题、正文维护在 B2 正式 Markdown。`python v4.py first-item-b2-public-verify`校验完整覆盖、公开投影与档位换分；修改后同步第一项总阅读视图，有分值变化时重建综合榜及相关分析，再运行`python reader/build.py`与`python reader/build_first_item_reader_cache.py`。`reader/first-item-b2.html`覆盖全部适用人物，人物主页、对照与详情使用同一上游正文；默认显示问题、经历与三个分数，逐层展开职责、裁决限制和史料，浏览器不补写组织事实或推断本人控制。

第四项 C 全池阅读页为`reader/fourth-item-c.html`，覆盖正式 C 记录的完整集合，独立于综合榜就绪状态。它与人物概览、详情、对照使用同一`fourth-item-c-public.js`正文和导航；跨页以正式人物标识定位，详情以`#net/人物标识/fourth/c`定位 C 卡。仅为已有阅读人物页及已就绪详情提供回链，池外单项不生成虚假人物入口。姓名、经历、来源和零值说明均可全文搜索；构建与`--check`核对全池内容，评分与原引用保持不变。

第四项 C 的逐条史源入口维护在材料 `public_c_result_reading.sources`，原引用与链接严格同值；位置理由、零值原因和复核范围维护在轴级 `public_reading`。人物概览、详情与对照共同展示完整来源和只读合成步骤，区分无独立材料、复核后不计分与正负相抵。修改后运行 `python v4.py third-fourth-item-public --write`、`python v4.py fourth-item-c-views --write`、`python v4.py fourth-item-c-verify`及阅读层构建／检查。来源与说明维护不改变评分；未知链接不猜配，原引记述不冒充古籍逐字原文。

第四项 B 的经历、本人责任、比较起点、定档理由与逐条史源直接维护在正式 JSON 的 B 轴及 B 材料 `public_reading`；`third-fourth-item-public --write`只投影正文，不改变评分。`python v4.py fourth-item-b-views --write`同步正式阅读视图，`python v4.py fourth-item-b-verify`校验三轴合同、正文、来源及视图同值；再运行阅读层构建与检查。人物页、详情、对照和`reader/fourth-item-b.html`共用完整正文，撤资格材料保留事实但不标作正向成果；零分区分未确认独立变化、材料复核后不计分与正负相抵，不用前后任或其他项目事实补写本人教育结果。

阅读概览与详情均保留完整公开文字，不按字数或前几句生成摘要。第二项 A/B1 的概览和专用正文读取同一正式公开裁决，专用正文独立展示范围、计算与来源，不依赖旧渲染器中转。B1的具体经历、本人责任、定档理由及逐材料解释直接维护在正式JSON，`python v4.py second-item-b1-public --write`只投影正文并刷新档内指数计算，随后以`python v4.py second-item-b1-verify`及`python reader/build.py --check`校验；刷新不得用条数总括覆盖人物正文，也不改变评分。画像正文仅映射明确的代码和档位，不全局改写中文词语；公开净收益正文不经过画像术语映射。

军损数量解释试点见[军事成本裁决敏感性](docs/评分结算/净收益/综合分析/01-军事成本裁决敏感性.md)。相关正式输入变动后运行`python v4.py cost-sensitivity --write`，只读核对省略`--write`；案例基准档位变化须先复核案例。分析不改正式评分，且不把被排除假设纳入证据允许范围。

证据解释遵循[裁决不确定性与敏感性合同](docs/证据规则/裁决不确定性与敏感性合同.md)。运行`python v4.py composite-ranking --write`按[军事成本逐人复核](config/common/prudent-military-cost-grade-reviews.json)、[C1—C3低置信终裁](config/second-item/c1-c2-c3-low-confidence-terminal-adjudications.json)与[治理联合候选](config/common/prudent-governance-grade-scenarios.json)为入榜者生成现有史料审慎分数区间，再运行`python v4.py evidence-sensitivity --write`及`python reader/build.py`同步[当前分析](docs/评分结算/净收益/综合分析/02-证据裁决敏感性.md)与阅读层。区间不是统计置信区间或未来史料的绝对界；单点只表示本轮语料未留下具体有源异档。已闭合的终裁端点按声明的配对或组合规则消费，其他条件候选不得冒称已采信分数或名次。

需要评分回归时运行常规测试（不含 acceptance 与 presentation；单组件改动可指定相关测试路径）：

```powershell
python -m pytest -q
```

展示改动按影响选择相关测试，需要展示套件时运行 `python -m pytest -q -m presentation`；影响全链或明确要求完整验收时运行 `python -m pytest -q -m ""`。局部裁决优先使用维护报告中的组件校验，不默认重复运行全套测试。

第三项与综合总榜保留可重建命令；综合总榜直接读取第一项 Markdown 正式结算，第一项不再由 JSON 生成 Markdown。命令只读取 Git 中的当前公共登记、裁决配置和正式分项结果，不访问网络、模型或数据库。使用 `python v4.py --help` 查看入口。

## 边界

Git 是规则、证据和正式结果的历史载体。正式目录不维护过期阶段报告、失败日志或旧版本结果；可丢弃的诊断、脚本和草稿放 `.tmp/`，当前仍支撑裁决的审计与证据继续保留。数据库写入和生产部署不属于当前仓库执行链；跨项综合排名只允许读取`COMPOSITE_READY`对象并由正式命令确定性生成。

开发、验证、提交与整理按 [AGENTS.md](AGENTS.md) 和全局约定执行。授权交付完成、受影响下游同步、相关验证通过并核对改动范围后即结束，不额外要求全库清理或无关检查。

C4画像局部校验：`python v4.py profile-c4-verify`。
