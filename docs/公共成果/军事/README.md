# 军事公共成果

本目录保存秦至唐战役登记与武将人才等级的当前 canonical 结果，只保留当前值，历史变更由 Git 承担。

- `01-秦至唐战役登记.json`：机器读取的完整父战役登记。
- `01-秦至唐战役登记.md`：战役登记人工阅读视图。
- `02-秦至唐武将人才等级.json`：只消费最新战役登记生成的人才等级结果。
- `02-秦至唐武将人才等级.md`：按等级与净值展示的人才等级阅读视图。

重建命令：

```powershell
python v4.py battle-parent-contract-registry
python v4.py military-talent-grade-registry
```

本目录不是并行历史库，不保留旧版、运行展开、checkpoint或审计中间结果。
