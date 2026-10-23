# 皇帝综合评价体系 V4

本仓库维护统治绩效、九轴人物画像、历史影响三套并列体系的现行合同、证据、正式裁决和确定性工具。三套体系不互相换分；共同边界见[综合评价体系合同](docs/项目总纲/皇帝综合评价体系合同.md)。

## 正式结果

| 入口 | 内容 |
| --- | --- |
| [综合阅读层：帝王三镜](reader/README.md) | 人物总览、三体系并列阅读、双人对照和依据展开 |
| [统治绩效综合榜](docs/评分结算/净收益/00-统治绩效综合评分榜.md) | 前四项净收益与综合排名；分项结果见[结算导航](docs/评分结算/README.md) |
| [九轴人物画像](docs/评分结算/人物画像/九轴结算汇总.md) | 八个能力轴与独立的权力运用风格轴 |
| [历史影响](docs/评分结算/历史影响/01-历史影响正式结算.json) | 公众总档与四维独立判断 |

正式入口、权威来源及命令读取 [config/project.yml](config/project.yml)；当前人数、身份、适用性和就绪状态读取[规范人物池](config/common/canonical-ruler-pool.json)，准入说明见[正式评价对象范围](docs/项目总纲/正式评价对象范围.md)。本页不另存分数、人数或公式副本。

## 安装与日常操作

```powershell
python -m pip install -e .
python v4.py reading-views
python v4.py --help
```

核心安装用于评分维护；雷达图或视频人物卡另装 `python -m pip install -e ".[presentation]"`。阅读层本地服务的依赖与预览方式见[阅读层说明](reader/README.md#本地预览)。

以下命令均接在 `python v4.py` 后；加 `--help` 查看参数。原分项命令及独立脚本继续可用。

| 操作 | 命令 |
| --- | --- |
| 定位裁决与受影响下游 | `maintenance --component <分项代码>`，可加 `--ruler-id` 或 `--polity` |
| 校验所选组件 | 上述命令加 `--verify`；`--related` 追加关联组件校验 |
| 同步确定性下游 | 上述命令加 `--sync`；随后按需运行 `reader` |
| 完整构建阅读站点 | `reader`，输出 `.tmp/pages-site/` |
| 重建大型阅读文档 | `reading-views`；加`--check`只读核对 |
| 导出评估包 | `package`；`package --list` 只列清单 |

`maintenance`支持 `I1`—`I4`、第二项各组件、`I3.D`、`profile.<轴代码>`、`pool`及`composite`。例如：

```powershell
python v4.py maintenance --component I2.B2 --ruler-id RULER-HAN-LIUHENG
python v4.py maintenance --component profile.C2 --polity 西汉 --verify
```

默认只读。报告区分确定性下游与需人工复核的关联裁决；`--sync`先校验源，再刷新报告列出的下游并回验，不自动重裁。B2支持选定人物校验，其他检查可能覆盖完整组件；局部报告不代表全池历史语义验收。源裁决及无生成器的源文档仍需局部编辑。各分项的正文位置、刷新顺序和专用校验见[阅读维护表](reader/README.md#分项编辑与刷新)。

## 聊天版评估包

`python v4.py package`默认生成 `.tmp/evaluation-packages/皇帝三体系评估包.zip`；`--output <路径.zip>`指定文件，`--package`可单选某体系的合同或结算，具体选项见命令帮助。

包内逐字节复制三体系原始合同、正式 JSON 及路由分片、Markdown 结算源／保留的阅读视图、综合分析、项目入口、规范人物池、治理规模与复杂度分类源，以及 `docs/公共成果/` 下的 Markdown、JSON、文本。不入Git的大型阅读视图从当前正式来源在内存中生成，清单标为`GENERATED`；不依赖本地是否已有副本，不写回评分或证据。保留仓库路径，另附使用说明与清单；不生成精简合同，不包含代码、展示素材、过程审计或其他目录的完整史料库。包外来源仍须另行补充，入包不代表完成全部溯源。

## 验证

项目JSON统一使用UTF-8无BOM、LF换行、紧凑值和记录级换行，保持标准JSON及原有字段顺序；字符串内部空白不变。生成器共用`emperor_v4.json_format.json_text`。`python v4.py json-format`统一Git管理的JSON（含归档）及现有阅读层JSON产物；加`--check`只检查，格式不一致时非零退出。临时目录、依赖及其他忽略的本地数据不在范围内；终端输出和HTML内嵌数据保持各自展示方式。

按 [AGENTS.md](AGENTS.md#实现与验证) 选择受影响范围；分项维护优先使用组件校验，不默认叠加全套检查。

| 改动 | 检查或同步入口 |
| --- | --- |
| 正式入口或登记 | `python v4.py project-entries-verify` |
| 评价池 | `python v4.py canonical-ruler-pool`只读核对，确认修改时加`--write` |
| 综合计分输入 | `python v4.py composite-ranking --write`，再同步实际受影响分析和阅读层 |
| 军损解释情景 | `python v4.py cost-sensitivity --write`；基准档位变化先复核案例 |
| 证据解释情景 | 综合榜重建后运行`python v4.py evidence-sensitivity --write` |
| 全链结算一致性 | `python v4.py formal-settlements-verify`；可用`--item`限定分项 |
| 常规回归 | `python -m pytest -q`；局部改动指定相关测试文件 |
| 展示或完整验收 | `python -m pytest -q -m presentation`或`python -m pytest -q -m ""`；展示测试需可选依赖 |

敏感性分析遵循[裁决不确定性与敏感性合同](docs/证据规则/裁决不确定性与敏感性合同.md)，省略`--write`只读核对。现有史料审慎区间不是统计置信区间，分析不改正式评分。结构、引用与同值检查不代替史料语义审查。

## 保留范围

[文档导航](docs/README.md)说明合同、正式结果与证据目录职责。[归档](archive/README.md)保存完整退役组件的最后有效材料，其他历史版本由 Git 保存。

`config/`保存入口、身份及当前裁决输入；`src/emperor_v4/evaluation/`保存读取、校验、确定性结算与投影逻辑。`reader/`保存模板、代码与人工文案，生成页面和数据不进入 Git。展示制作位于`docs/展示成果/`和`emperor-cards/`，临时脚本、日志及诊断放`.tmp/`。

历史影响、画像M1／M4／M5／C1／C2／C3／C5、第二项C3／C4／D1／D3、第三项AB／C及第四项B的Markdown是可完整重建的阅读视图，不进入Git。新检出后先运行`reading-views`再校验；完整阅读站点构建与CI会先生成这些文件。正文仍完整保留在JSON，原有路径与局部刷新命令有效。第三项AB同时读取正式AB记录与本人信用裁决，不以旧Markdown补正文。第一项Markdown真源、财政民生C1／C2等承担证据引用的阅读文档及含独立人工内容的Markdown继续保留。

## 边界

执行约定见[AGENTS.md](AGENTS.md)，评分与证据边界见现行合同。结算和验证离线运行，不使用模型、网络或外部数据库；阅读站点的静态发布流程另见[阅读层说明](reader/README.md#构建产物与维护边界)。旧服务与 shadow 执行链已退役，仍被当前裁决引用的史料或审计不得仅凭名称删除。
