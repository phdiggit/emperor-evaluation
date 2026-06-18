# 第五项B三人试点·人工裁判阅读导航

生成日期：2026-06-18  
状态：人工裁判阅读说明  
范围：李世民、刘秀、刘庄  
项目：第五项B《用人与授权》

> 本文件回答：人工裁判应依据哪些信息、按什么顺序阅读、每一步看什么。它不定档、不计分、不排名。

## 一、推荐阅读顺序

### 第一步：看净裁量草案

文件：

```text
exports/markdown_views/i5b_three_pilot_net_adjudication_drafts_20260618.md
```

目的：先看每人的正负关系、对象锚点影响和当前停点。

重点看：

- 李世民：负证是否不足以强拦截；魏征反转怎么备注。
- 刘秀：强负表达安全是否构成高档位上探拦截。
- 刘庄：楚王英案后续牵连剥离第五项C/D后，B项剩余强度是否仍强。

### 第二步：看对象锚点与定档前人工裁判清单

文件：

```text
exports/markdown_views/i5b_three_pilot_object_anchor_pregrade_checklist_20260618.md
```

目的：确认每个人涉及哪些对象锚点，哪些问题必须人工裁判。

重点看：

- 对象锚点是否确实会影响证据权重；
- 正负证据是否属于同一维度；
- 是否存在同一对象正负反转；
- 是否触发高档位拦截。

### 第三步：看对象锚点池

文件：

```text
data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl
```

目的：确认对象池本身，而不是只看审计视图里的说明。

重点看：

- `object_type`
- `object_level`
- `anchor_role`
- `usable_for`
- `cross_item_risks`
- `consensus_level`
- `status`

说明：对象池只校准第五项B证据权重，不评价对象本身综合排名。

### 第四步：看证据组

文件：

```text
data/evidence_clusters.jsonl
```

目的：确认正负证据组是否已完成相邻项切分和候选强度判断。

重点 cluster：

```text
ADJ-I5B-LISHIMIN-POS-TALENT-ECOSYSTEM-001
ADJ-I5B-LISHIMIN-NEG-TALENT-RISK-001
ADJ-I5B-LIUXIU-POS-TALENT-AUTHORIZATION-001
ADJ-I5B-LIUXIU-NEG-REMONSTRANCE-SAFETY-001
ADJ-I5B-LIUZHUANG-POS-TALENT-AUTHORIZATION-001
ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001
```

重点字段：

- `summary`
- `five_axis_assessment`
- `candidate_strength`
- `upper_probe`
- `cross_item_split`
- `adjudication_status`

### 第五步：必要时回看原子证据卡

文件：

```text
data/evidence_cards.jsonl
```

目的：当证据组结论有疑问时，回到原子证据卡检查原文短摘和解释是否支撑。

重点 evidence：

```text
EVD-I5B-LISHIMIN-POS-RONGJIAN-WEIZHENG-001
EVD-I5B-LISHIMIN-NEG-WEIZHENG-001
EVD-I5B-LIUXIU-NEG-HANXIN-001
EVD-I5B-LIUXIU-NEG-HUANTAN-001
EVD-I5B-LIUXIU-NEG-TINGZHANG-001
EVD-I5B-LIUZHUANG-NEG-YIJI-001
```

注意：

```text
EVD-I5B-LISHIMIN-NEG-WEIZHENG-001 的 trigger_family 应按 correction batch 修正为“谏臣身后信用反转”，不是“疑忌杀害”。
```

### 第六步：看 correction batch

文件：

```text
data/evidence_card_correction_batches/i5b_lishimin_weizheng_trigger_family_correction_20260618.jsonl
```

目的：明确记录魏征 trigger_family 的纠偏口径。

后续字段规范化时，应将该 correction 合并回 canonical evidence_cards。

## 二、人工裁判最小输入

人工裁判至少需要以下材料：

```text
1. 净裁量草案
2. 对象锚点与定档前人工裁判清单
3. 对象锚点池
4. evidence_clusters
5. 必要 evidence_cards
6. correction batch
```

若只做快速裁判，优先看 1、2、3。若要复核史料支撑，再看 4、5、6。

## 三、三人裁判问题压缩版

### 李世民

```text
1. 正向强正是否成立？
2. 负向是否只到中负，不构成强负拦截？
3. 魏征是否作为“顶级谏臣身后信用反转”备注，而非疑忌杀害？
4. 张亮、侯君集是否维持边界负证，不抬成强负？
```

### 刘秀

```text
1. 正向强正是否成立？
2. 负向强负是否成立？
3. 强负是否构成高档位上探拦截？
4. 是否存在上探极负风险，还是只保留强负拦截？
```

### 刘庄

```text
1. 正向是否只能维持中正？
2. 班超线是否因帝王直接归属较弱，不能上调？
3. 楚王英案后续牵连剥离第五项C/D后，B项剩余是否仍为强负？
4. 廷杖线未可靠回源，是否继续排除？
```

## 四、禁止事项

人工裁判前不得生成：

- 正式档位；
- 分数；
- 排名；
- 阶段总榜；
- 横向排序结论。
