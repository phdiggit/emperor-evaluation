# 文档与脚本登记

## 本目录负责什么

本目录只放 docs/scripts registry 及其登记说明，是机器可读治理状态和登记规则入口。

## 本目录不负责什么

本目录不是业务规则目录，不放评分、证据、数据 schema、展示规范或分项规则正文。

## 与相邻目录的边界

- docs 当前事实源和规则正文分别进入对应功能目录。
- scripts 协作规范进入 [`../展示与协作/scripts目录规范.md`](../展示与协作/scripts目录规范.md)。
- registry 只登记路径、生命周期、迁移状态和审计关系，不替代文档正文。

## 当前索引

- [`docs_registry.json`](docs_registry.json)
- [`scripts_registry.json`](scripts_registry.json)

## 后续新增文件限制

新增文件必须直接服务 docs/scripts 登记。不得把业务规则、评分语义或可重建生成物放入本目录。

## 规则入口决策表

| 需求 | 写入位置 |
| --- | --- |
| 长期业务规则正文 | 对应 `docs/` 功能目录 |
| docs 生命周期、引用和候选动作 | `docs_registry.json` |
| scripts 当前实现路径、retired wrapper 和 required tests | `scripts_registry.json` |
| scripts 协作和目录规范 | `../展示与协作/scripts目录规范.md` |
| 仓库级边界和安全规则 | 根 `AGENTS.md` |
