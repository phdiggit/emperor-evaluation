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

包内包含统治绩效、人物画像、历史影响三个体系的完整原始合同、正式结算 JSON 及其全部路由分片、Markdown 结算源/阅读视图，以及项目入口、正式人物池和总榜治理规模／复杂度的非计分分类源。源文件逐字节复制，保留仓库路径；不再生成精简合同。根目录只增加使用说明和文件清单，不打入代码、展示素材、过程审计及完整史料库。结算记录中的依据和引用保留，但包外史料仍需另行补充，不能把包内阅读当作完整溯源。

默认只生成一个完整包。`--output <路径.zip>` 可指定输出，`--list` 只查看入包清单；如需分开上传，使用 `--package contracts|settlements|profile-contract|profile-settlements|historical-impact-contract|historical-impact-settlements` 单选统治绩效、人物画像或历史影响的合同/结算，所有输出均为 ZIP。

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
```

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

第二项组件变动后，`python v4.py second-item-totals --write`同步汇总与四张阅读页；A制度建设的公开逐节点正式投影使用`python v4.py second-item-a-public --write`，B2反馈与约束的公开裁决投影使用`python v4.py second-item-b2-public --write`，C1—C4财政民生结果的公开裁决投影使用`python v4.py second-item-c-public --write`。第三、第四项公开裁决投影使用`python v4.py third-fourth-item-public --write`，可用`python v4.py third-fourth-item-public-verify`单独校验。第二项正式校验同时核对组件抄录、竞争排名、公开字段及阅读同值。

第三、第四项公开文案使用明确的中文术语及绑定原句的完整转述，未知代码或英文必须补充转述后才能生成，不得删除字母或拼接残句。校验同时比较完整公开投影与非公开评分来源；结构校验不代替文意复核。修改转述后重建公开字段，再运行`python reader/build.py`及`python reader/build.py --check`。合并时先解决合同、源记录与生成器冲突，再重建公开投影和`reader/data/people/`，不要手工拼接生成文案。Pages成功不代表Build reader成功，发布验收须确认对应提交的构建与行为检查均通过。

主态低谷与净恢复 V4 已统一启用（L有限修正，历史K不计分）；可用 `python v4.py governance-state-recovery-verify` 校验，或用 `python v4.py governance-state-recovery-report --write` 刷新逐人阅读页。启用与刷新不做跨项文件哈希同步。

第一项本人统帅的公开说明直接维护在 C 正式 Markdown 的“公开裁决依据”“公开责任边界”中，战役列表只读取“统一链战役清单”。修改后运行`python v4.py first-item-c-public-verify`，再重建`reader/build.py`与`reader/build_first_item_reader_cache.py`；阅读层不猜测角色、不生成战役条目，也不因展示列表而省略责任与限制。

第一项 B1 的“公开起点说明”“公开对手说明”“公开效率说明”维护在 B1 正式 Markdown；军事成本的公开依据、责任时期、证据缺口与补充链接维护在成本正式 JSON。运行`python v4.py first-item-b1-cost-public-verify`核对覆盖与字段，再重建阅读数据及第一项缓存。页面直接展示公开字段，分阶段效率不合并成单一年数，成本依据与缺口不截断；原始计分记录保留在规则折叠项和来源入口。

阅读概览与详情均保留完整公开文字，不按字数或前几句生成摘要。第二项 A/B1 的概览和专用正文读取同一正式公开裁决，专用正文独立展示范围、计算与来源，不依赖旧渲染器中转。画像正文仅映射明确的代码和档位，不全局改写中文词语；公开净收益正文不经过画像术语映射。

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
