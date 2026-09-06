# 皇帝综合评价体系 V4

本仓库保存五大项评分的当前规则、可审计证据、确定性结算逻辑与唯一结果入口。各项当前状态与复核边界见项目配置及对应正式入口。已退役的模型抽取、浏览器检索、source-cache、shadow、数据库服务和部署链不再保留。

## 正式结果

- [皇帝功业与治理净收益榜](docs/评分结算/00-皇帝功业与治理净收益榜.md)
- [第一项：政权奠基与统一贡献及能力](docs/评分结算/第一项政权奠基与统一贡献及能力/01-第一项政权奠基与统一贡献及能力正式结算.md)
- [第二项：治国净收益](docs/评分结算/第二项治国净收益/01-第二项治国净收益正式结算.md)
- [第三项：军事与边疆净收益](docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.md)
- [第四项：文明与国家整合收益](docs/评分结算/第四项文明与国家整合收益/02-第四项文明与国家整合收益正式总榜.md)
- [第五项：统治者政治素质](docs/评分结算/第五项统治者政治素质/04-第五项统治者政治素质正式结算.md)

机器读取入口与范围统一记录在 [`config/project.yml`](config/project.yml)。最高业务规则是 [`docs/项目总纲/皇帝综合评价体系评分标准.md`](docs/项目总纲/皇帝综合评价体系评分标准.md)。

正式评价池按实际独立最高权力至少3年和证据可行性筛定。当前人数、待补对象及分项别名统一见[`正式评价对象范围`](docs/项目总纲/正式评价对象范围.md)及其机器入口`config/common/canonical-ruler-pool.json`，本页不另存人数副本。综合计算只读取`COMPOSITE_READY`对象；第一项不适用者取F=0。

## 保留范围

- `docs/项目总纲/`、`docs/分项规则/`：当前评分合同。
- `docs/评分结算/`：五项唯一正式结果与同值阅读视图；第一项使用 Markdown 结算源。
- `docs/公共成果/`、`docs/治理/`、`docs/史料通读产物/`：仍被评分结果引用的证据与公共登记。
- `config/project.yml`：项目状态、正式结果入口和保留的重建接口。
- `config/common/`：正式评价池、分项候选名册与实体身份；其中`canonical-ruler-pool.json`是综合范围唯一机器入口。`config/third-item/`保存第三项当前裁决输入；`config/military/`保存公共军事登记与人才登记的当前输入。
- `src/emperor_v4/evaluation/`：公共军事登记、第一项 Markdown 正式结算读取和第三项确定性结算逻辑。

## 验证

按 [AGENTS.md](AGENTS.md) 的改动类型选择检查，以下是按需使用的命令参考，不是每次必跑的步骤。使用当前 Python 环境；需要 UTF-8 子进程或托管能力时再加 `codex-win run --`。

局部维护先按分项及稳定人物ID定位当前记录、下游同步和复核范围。分项代码为`I1`—`I5`、`I2.A`、`I2.B1`、`I2.B2`、`I2.C1`—`I2.C4`、`I3.D`及`profile.M1`等八个画像轴；也支持`pool`和`composite`。

```powershell
python v4.py maintenance --component I2.B2 --ruler-id RULER-HAN-LIUHENG
python v4.py maintenance --component profile.M3 --polity 西汉 --verify
```

默认只读，按朝代分片定位人物；`--verify`检查当前分项，B2与M3支持选定人物的合同约束及阅读视图同值。`--related`额外执行关联轴校验。报告分别列出确定性下游、语义复核对象和刷新命令；`--sync`先校验当前源，再依次刷新列出的下游并回验，不自动重裁关联人物。源裁决和没有阅读视图生成器的源文档仍按局部patch维护。整池排名及覆盖检查读取对应完整组件，局部报告不代表全池语义验收。

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

全链改动或全池验收时，验证五项正式结果、唯一人物 ID、分值范围和排名顺序：

```powershell
python v4.py formal-settlements-verify
```

评价范围变更时重建或核对正式评价池：

```powershell
python v4.py canonical-ruler-pool
```

综合计分输入变化时重建综合总榜：

```powershell
python v4.py composite-ranking --write
```

需要评分回归时运行常规测试（不含 acceptance 与 presentation；单组件改动可指定相关测试路径）：

```powershell
python -m pytest -q
```

展示改动按影响选择相关测试，需要展示套件时运行 `python -m pytest -q -m presentation`；影响全链或明确要求完整验收时运行 `python -m pytest -q -m ""`。局部裁决优先使用维护报告中的组件校验，不默认重复运行全套测试。

第三项与综合总榜保留可重建命令；综合总榜直接读取第一项 Markdown 正式结算，第一项不再由 JSON 生成 Markdown。命令只读取 Git 中的当前公共登记、裁决配置和正式分项结果，不访问网络、模型或数据库。使用 `python v4.py --help` 查看入口。

## 边界

Git 是规则、证据和正式结果的历史载体。正式目录不维护过期阶段报告、失败日志或旧版本结果；可丢弃的诊断、脚本和草稿放 `.tmp/`，当前仍支撑裁决的审计与证据继续保留。数据库写入和生产部署不属于当前仓库执行链；跨项综合排名只允许读取`COMPOSITE_READY`对象并由正式命令确定性生成。

开发、验证、提交与整理按 [AGENTS.md](AGENTS.md) 和全局约定执行。授权交付完成、受影响下游同步、相关验证通过并核对改动范围后即结束，不额外要求全库清理或无关检查。
