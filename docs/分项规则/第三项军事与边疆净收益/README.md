# 第三项“军事与边疆净收益”规则入口

本目录只保存第三项的规则、边界和结算合同，不保存皇帝结算结果或通读史料。

- [`国防安全/00-规则与结算合同.md`](国防安全/00-规则与结算合同.md)：A1、A2、B1、B2、B4；
- [`军事体系有效性/00-规则与计分合同.md`](军事体系有效性/00-规则与计分合同.md)：C1、C2、C3与C总体档；
- [`军事成本收益比/00-规则与结算合同.md`](军事成本收益比/00-规则与结算合同.md)：D事件准入、组合档和档内计分。

正式结果统一从[`docs/评分结算/第三项军事与边疆净收益`](../../评分结算/第三项军事与边疆净收益/README.md)读取；共同计分材料统一从[`docs/史料通读产物/唐以前编年`](../../史料通读产物/唐以前编年/README.md)回源。

## 总权重与合并合同

第三项范围为-40至250分。D不独立加分，只形成固定成本扣分：

- A1、A2各60分，共A120。改善按每档`0／0.25／0.5／0.75／1.0`归责；守成按`NONE／TESTED／SEVERE／HISTORIC=0／10／25／40`裁决，HISTORIC另过现实压力、主要归责、非自致、终点不降和持续有效五门。
- B80消费B1控制规模与B2战略价值，并由B4交班成熟度修正：`B80=80×(0.55×B1率+0.45×B2率)×(0.70+0.30×B4率)`。
- C50继续只评价军事体系实战兑现、持续作战与可靠性，不受成本系数折算。
- D按现有成本档与档内位置读取`factor`，换算`cost_debit=80×(1-factor)`；ML为0至40分的严重度扣分下限。

```text
第三项 = A120 + B80 + C50 - max(cost_debit, |military_net_loss_penalty|)
```

只对最终总分保留两位小数。factor表由[`config/third-item/third-item-cost-credit-factors.json`](../../../config/third-item/third-item-cost-credit-factors.json)唯一给出；现有排序和坡度不变。普通成本与ML取高，不叠加。

成本保留两种不混用的视图：

1. `D_local_cost_profile`沿用D消费者范围，第三项C或第一项已经整链消费的对象不恢复进D分。
2. `global_cost_credit_profile`用于换算固定成本扣分和校验ML门；它恢复第三项C能力层独占消费、但发生于本人正式统治窗口的直接军事成本。

第一项创业统一与政权取得整链继续全部排除；第二项财政民生结果、第四项文明损害和第五项人物素质均不得进入全局成本系数或军事净毁损门。军事安全、边疆控制、军事体系和本方军事资源毁损的跨期尾部只在第三项内部结算，不另设历史负债扣分。201人的A120/B80逐轴裁决唯一读取[`config/third-item/third-item-result-credit-adjudications.json`](../../../config/third-item/third-item-result-credit-adjudications.json)，军事净毁损裁决读取[`config/third-item/third-item-military-net-loss-penalties.json`](../../../config/third-item/third-item-military-net-loss-penalties.json)；201人总榜已完成回放。

所有分区写入器完成AB/C及D重建后，必须统一调用current settlement writer，重建固定成本扣分、ML取高值和竞争排名；不得返回旧乘数公式。第一项闭合窗口内的成果若仅作为第三项起点存量，必须同时从A本人正向信用、B新增控制包和D成果/成本链排除。
