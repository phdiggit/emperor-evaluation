# 皇帝综合评价体系 V4

本仓库保存五大项评分的当前规则、可审计证据、确定性结算逻辑与唯一结果入口。第四项正在全池复审，当前快照及其合成榜不是复核终榜；其余分项保持各自当前结算状态。已退役的模型抽取、浏览器检索、source-cache、shadow、数据库服务和部署链不再保留。

## 正式结果

- [皇帝功业与治理净收益榜](docs/评分结算/00-皇帝功业与治理净收益榜.md)
- [第一项：政权奠基与统一贡献及能力](docs/评分结算/第一项政权奠基与统一贡献及能力/01-第一项政权奠基与统一贡献及能力正式结算.md)
- [第二项：治国净收益](docs/评分结算/第二项治国净收益/01-第二项治国净收益405分正式结算.md)
- [第三项：军事与边疆净收益](docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.md)
- [第四项：文明与国家整合收益](docs/评分结算/第四项文明与国家整合收益/02-第四项正式结算汇总.md)
- [第五项：统治者政治素质](docs/评分结算/第五项统治者政治素质/04-第五项统治者政治素质正式结算.md)

机器读取入口与范围统一记录在 [`config/project.yml`](config/project.yml)。最高业务规则是 [`docs/项目总纲/皇帝综合评价体系评分标准.md`](docs/项目总纲/皇帝综合评价体系评分标准.md)。

当前正式评价池为184人，由201人候选全集按实际独立最高权力至少3年和证据可行性筛定。其中174人当前综合计算就绪并进入总榜，10人因第二项尚无正式分留在池内待结算；第一项适用范围已经闭合，不适用者在综合公式中取F=0。第二项缺口补齐前不得进入综合分和总排名。逐人状态及分项别名映射见[`正式评价对象范围`](docs/项目总纲/正式评价对象范围.md)；机器入口为`config/common/canonical-ruler-pool.json`。

## 保留范围

- `docs/项目总纲/`、`docs/分项规则/`：当前评分合同。
- `docs/评分结算/`：五项唯一正式 JSON 与 Markdown 阅读视图。
- `docs/公共成果/`、`docs/治理/`、`docs/史料通读产物/`：仍被评分结果引用的证据与公共登记。
- `config/project.yml`：项目状态、正式结果入口和保留的重建接口。
- `config/common/`：正式评价池、分项候选名册与实体身份；其中`canonical-ruler-pool.json`是综合范围唯一机器入口。`config/third-item/`保存第三项当前裁决输入；`config/military/`保存公共军事登记与人才登记的当前输入。
- `src/emperor_v4/evaluation/`：公共军事登记、第一项 Markdown 正式结算读取和第三项确定性结算逻辑。

## 验证

首次安装：

```powershell
codex-win run -- python -m pip install -e .
```

验证五项正式 JSON、唯一人物 ID、分值范围和排名顺序：

```powershell
codex-win run -- python v4.py formal-settlements-verify
```

重建或核对正式评价池：

```powershell
codex-win run -- python v4.py canonical-ruler-pool
```

重建综合总榜：

```powershell
codex-win run -- python v4.py composite-ranking --write
```

运行离线测试：

```powershell
codex-win run -- python -m pytest -q
```

第三项与综合总榜保留可重建命令；综合总榜直接读取第一项 Markdown 正式结算，第一项不再由 JSON 生成 Markdown。命令只读取 Git 中的当前公共登记、裁决配置和正式分项结果，不访问网络、模型或数据库。使用 `python v4.py --help` 查看入口。

## 边界

Git 是规则、证据和正式结果的唯一历史载体。工作树不保存阶段报告、失败运行、旧版本结果或兼容分支；需要追溯时使用 Git 历史。数据库写入和生产部署不属于当前仓库执行链；跨项综合排名只允许读取`COMPOSITE_READY`对象并由正式命令确定性生成。
