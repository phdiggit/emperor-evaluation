# 第五项B检索包索引长字段附录

## qry-i5b-001-negative_terms

### 负向检索词（negative_terms）

```text
[
  "疑忌",
  "诛",
  "杀",
  "赐死",
  "下狱",
  "坐死",
  "牵连",
  "阿党",
  "停婚",
  "仆碑",
  "身后追责",
  "信用反转",
  "谗",
  "佞",
  "近幸",
  "宠臣",
  "后宫干政",
  "宦官用事",
  "男宠用事",
  "误任",
  "错用",
  "群臣莫敢正言",
  "廷杖",
  "刑辱近臣"
]
```

## qry-i5b-liuche-20260618-positive_terms

### 正向检索词（positive_terms）

```text
[
  "识人拔擢：卫青、霍去病、张骞、主父偃、桑弘羊、公孙弘、董仲舒等多类型人才",
  "授权专任：军事、边疆外交、财政盐铁、策士建言等关键托付",
  "人才通道：贤良文学、茂才、征召、策问等入口机制",
  "反馈入口：政策/边疆/财政建言是否能进入决策"
]
```

## qry-i5b-liuche-20260618-negative_terms

### 负向检索词（negative_terms）

```text
[
  "权奸酷吏授权：张汤、杜周、江充等是否破坏表达安全和人才生态",
  "巫蛊与牵连：卫氏、太子、近臣、公卿被牵连对人才安全感的剩余影响",
  "任用风险：酷吏/近幸是否形成系统性负面用人生态"
]
```

## qry-i5b-liuche-20260618-cross_item_split_notes

### 相邻项剥离备注（cross_item_split_notes）

```text
[
  "开边收益、战役胜负切第一项/第三项",
  "财政政策效果切第二项或财政治理项",
  "巫蛊政权安全、储位政治切第五项C",
  "司法残酷、政治残酷性切第五项D",
  "皇帝认知与反省如轮台诏切第五项E或相应项目"
]
```

## qry-i5b-liuche-20260618-note

### 说明（note）

```text
I5B typical Batch A 刘彻确定性回源画像；query_profile 只解释 search_log 与 source/evidence 生成，不作为证据或评分依据。
```

## qry-i5b-liuheng-20260628-negative_terms

### 负向检索词（negative_terms）

```text
[
  "人才保护不足：贾谊受绛灌等排挤后被疏远外放",
  "旧臣结构约束：周勃、灌婴等老臣压力对新进人才通道的限制",
  "近幸偏私 / 宠臣任用 / 任人唯亲：邓通赐铜山铸钱线待回源判断是否构成第五项B直接任用风险"
]
```

## qry-i5b-liuheng-20260628-cross_item_split_notes

### 相邻项剥离备注（cross_item_split_notes）

```text
[
  "刑法宽平和制度成效切第二项",
  "边郡军事得失切第三项",
  "老臣政治平衡切第一项B或第五项C",
  "贾谊政策主张成败切第六项或第二项，不直接回填B项",
  "邓通赐铜山铸钱线需切分财政特许、个人私恩和后世结局；第五项B只保留近幸偏私或宠臣任用风险是否成立"
]
```

## qry-i5b-liuheng-20260628-note

### 说明（note）

```text
I5B typical Batch B1 刘恒持久回源画像；本批只转张释之、冯唐/魏尚、贾谊识才和疏远线。；邓通/近幸偏私 lane 保留为 lead_needs_source_review，不作为评分或人物特例。
```

## qry-i5b-liuzhuang-migration-20260618-cross_item_split_notes

### 相邻项剥离备注（cross_item_split_notes）

```text
[
  "西域战果和边疆收益切第一/第三项",
  "辅政后治理效果切第二项",
  "宗室控制和政权安全切第五项C",
  "司法严酷和政治残酷性切第五项D",
  "明章之治总体光环不得回填第五项B"
]
```

## qry-i5b-yangjian-20260618-positive_terms

### 正向检索词（positive_terms）

```text
[
  "识人拔擢：高颎、苏威、杨素、贺若弼、史万岁等开皇文武团队",
  "授权专任：中枢辅政、行军总管、文武分工与关键委任",
  "容谏反馈：高颎、苏威、柳彧等谏诤/政策反馈入口",
  "人才生态：开皇前中期功臣能臣合作秩序"
]
```

## qry-i5b-yangjian-20260618-cross_item_split_notes

### 相邻项剥离备注（cross_item_split_notes）

```text
[
  "开皇制度成效切第二项或制度治理项",
  "军事征伐结果切第一项/第三项",
  "储位政治和政权安全切第五项C",
  "杀戮/刑罚残酷切第五项D",
  "个人认知或晚年性格切第五项E或人物标签，不直接回填B项"
]
```

## qry-i5b-yangjian-20260618-note

### 说明（note）

```text
I5B typical Batch A 杨坚确定性回源画像；query_profile 只解释 search_log 与 source/evidence 生成，不作为证据或评分依据。
```

## qry-i5b-yingzheng-20260628-cross_item_split_notes

### 相邻项剥离备注（cross_item_split_notes）

```text
[
  "统一战争战果切第一项/第三项",
  "郡县制和制度建设切第二项A",
  "焚书坑儒的思想控制切第五项E，刑罚残酷性切第五项D",
  "赵高、扶苏、继承政治切第五项C或交接风险项"
]
```
