# docs 方法论导航

`docs/` 是当前规则、方法论、稳定操作说明和治理入口。生成视图在 `exports/`，历史治理材料在 `archive/docs/`；两者都不是当前规则事实源。

## 当前结构

```text
docs/
  README.md
  AGENTS.md
  00_project/
    README.md
  10_methodology/
    README.md
  20_dimensions/
    README.md
  30_operations/
    README.md
  agent_rules/
    README.md
    docs_registry.json
    scripts_registry.json
```

当前 `docs/` 根目录仍保留一批平铺式规则和方法论文档。这些文件是待迁移遗留入口，后续 PR 会分批用 `git mv` 迁入新目录；目录治理 PR 不顺手移动非白名单正文。

## 四层职责

| 层级 | 职责 | 当前入口 |
| --- | --- | --- |
| `00_project/` | 项目总纲、最高层业务语义、评分体系总结构、冲突时的优先级裁判 | [`00_project/README.md`](00_project/README.md) |
| `10_methodology/` | 跨大项、跨子项通用方法论，包括证据工作流、裁量、检索画像、数据和配置规范 | [`10_methodology/README.md`](10_methodology/README.md) |
| `20_dimensions/` | 七大项和子项专用规则、专用证据口径、执行模板和样板项目说明 | [`20_dimensions/README.md`](20_dimensions/README.md) |
| `30_operations/` | GitHub 协作、Markdown 显示、ID、scripts、人工协作和发布规范 | [`30_operations/README.md`](30_operations/README.md) |

## 推荐阅读顺序

1. 先读总纲和评分标准：[`皇帝综合评价体系评分标准.md`](皇帝综合评价体系评分标准.md)、[`总规则.md`](总规则.md)、[`数据层级与批次文件治理规则.md`](数据层级与批次文件治理规则.md)。
2. 再读通用方法论：证据工作流、证据强度、证据裁量、负证裁判、检索画像和数据规范。
3. 然后进入具体大项或子项：先确认大项边界，再读子项专用规则和执行模板。
4. 最后按操作规范执行：GitHub 发布、Markdown 显示、ID 命名、scripts 和治理工具。

## 第五项B定位

第五项B是已经跑通的样板项目，也是通用经验的来源之一。它可以为其他项目提供可抽象的经验，但不等同于全项目默认方法。

第五项B中跑通的通用经验，应先抽象到 `10_methodology/`，再由其他大项或子项复用；第五项B专用边界、模板和自动结算规则应进入 `20_dimensions/` 的子项层。

## 禁止事项

- 不用第五项B规则覆盖其他项。
- 不把 `archive/docs/` 当当前事实源。
- 不手改 generated export；生成物冲突时先找 generator。
- 不在目录治理 PR 中修改评分、档位、证据、排名或榜单等业务语义。
- 不在目录骨架 PR 中移动旧方法论文档正文或推进 Batch 3。
