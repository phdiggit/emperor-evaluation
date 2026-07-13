# G3R Endpoint 30 个样本与 4 个裁决项明细

> 状态：`review_detail_export`
>
> 日期：2026-07-13
>
> 样本任务：`G3R-ENDPOINT-SAMPLE-7D75C479870829643750`
>
> 裁决任务：`G3R-ENDPOINT-ADJ-4AD222F69543DD5BCF97`

## 汇总

- 样本数：30（I 20、J 10）
- direct agreement：93.33%
- coarse type agreement：86.67%
- 裁决项：4
- 最终 direct proposal：15
- 最终 unrelated proposal：15
- 正式 EpisodeRelation：0
- 数据库写入：0

以下内容只来自 endpoint worklist、两位隔离 reviewer 输出、第三方裁决输出和中央重建结果；不包含 Gold、旧 Relation 或 score。

## 1. `RBC-0081934C748A6FA2EF6F`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 0, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`authority_change`
- 是否经裁决：`yes`

### 左端内容

- Episode：`EP-B0A50E55335DF389C0A6`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "office_holder"]
- 行为：任命
- 责任：保和殿大学士、兵部尚书、军机事务
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-3E4BF7BCFAD0F79EB24D27E5@SP-77CE39608B951673AAE2`
  - 时间：雍正十年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：授一等伯爵，世袭
  - 摘要：雍正十年，胤禛召鄂尔泰拜保和殿大学士兼兵部尚书，并办理军机事务；又因定苗疆功授一等伯爵世袭。
  - SourcePassage：`SP-77CE39608B951673AAE2`
- `K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-90899060763733DC3B193C3B@SP-77CE39608B951673AAE2`
  - 时间：雍正十年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：授一等伯爵，世袭
  - 摘要：雍正十年，胤禛召鄂尔泰拜保和殿大学士兼兵部尚书，并办理军机事务；又因定苗疆功授一等伯爵世袭。
  - SourcePassage：`SP-77CE39608B951673AAE2`

#### SourcePassage 原文与上下文

<details><summary><code>SP-77CE39608B951673AAE2</code> · eertai-liezhuan:3124-3180</summary>

上文：

> 績也。
> 是歲，永昌邊外孟連土司請歲納廠課六百，鶴慶邊外皦子請歲貢土物，鄂爾泰疏聞。上以邊外野夷向化，命減孟連廠課之半。皦子入貢，犒以鹽三百斤。九年，疏請重定烏蒙、鎮遠、東川、威寧營汛。別疏請興雲南水利，濬嵩明州楊林海，開墾周圍草塘，疏宜良、尋甸諸水，耕東川城北漫海，築浪穹羽河諸堤，修臨安諸處工，暨通粵河道，皆下部議行。

原文：

> 十年，召拜保和殿大學士，兼兵部尚書，辦理軍機事務。敘定苗疆功，部議進世職一等精奇尼哈番，上特命授一等伯爵，世襲。

下文：

> 師討準噶爾，六月，命鄂爾泰督巡陝、甘，經略軍務。九月，師破敵額爾德尼昭，鄂爾泰檄大將軍張廣泗遣兵截袞塔馬哈戈壁，斷敵北遁道。尋疏請屯田。十一年六月，還京師。入對，言準部未可驟滅，用兵久，敝中國，無益，上頗然之。
> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾

</details>

### 右端内容

- Episode：`EP-E04D5F70E470FF822210`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "advisor", "commander", "delegate"]
- 行为：授权
- 责任：陕甘、准噶尔军务
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C301B15B52EE1BEC59DF2AC8@SP-4C7F0FB3398E0306DC61`
  - 时间：雍正十年六月至九月
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰檄张广泗截衮塔马哈戈壁，断敌北遁道；寻疏请屯田
  - 摘要：雍正十年，胤禛命鄂尔泰督巡陕甘、经略准噶尔军务；鄂尔泰随后檄张广泗截断敌北遁道并疏请屯田。
  - SourcePassage：`SP-4C7F0FB3398E0306DC61`
- `K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C5C447885AC4E26346FA87F6@SP-4C7F0FB3398E0306DC61`
  - 时间：雍正十年六月至九月
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰檄张广泗截衮塔马哈戈壁，断敌北遁道；寻疏请屯田
  - 摘要：雍正十年，胤禛命鄂尔泰督巡陕甘、经略准噶尔军务；鄂尔泰随后檄张广泗截断敌北遁道并疏请屯田。
  - SourcePassage：`SP-4C7F0FB3398E0306DC61`

#### SourcePassage 原文与上下文

<details><summary><code>SP-4C7F0FB3398E0306DC61</code> · eertai-liezhuan:3181-3249</summary>

上文：

> 半。皦子入貢，犒以鹽三百斤。九年，疏請重定烏蒙、鎮遠、東川、威寧營汛。別疏請興雲南水利，濬嵩明州楊林海，開墾周圍草塘，疏宜良、尋甸諸水，耕東川城北漫海，築浪穹羽河諸堤，修臨安諸處工，暨通粵河道，皆下部議行。十年，召拜保和殿大學士，兼兵部尚書，辦理軍機事務。敘定苗疆功，部議進世職一等精奇尼哈番，上特命授一等伯爵，世襲。

原文：

> 師討準噶爾，六月，命鄂爾泰督巡陝、甘，經略軍務。九月，師破敵額爾德尼昭，鄂爾泰檄大將軍張廣泗遣兵截袞塔馬哈戈壁，斷敵北遁道。尋疏請屯田。

下文：

> 十一年六月，還京師。入對，言準部未可驟滅，用兵久，敝中國，無益，上頗然之。
> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾，焚掠黃平、施秉諸地。鄂爾泰以從前佈置未協，引咎請罷斥，並削去伯爵。上曰：「國家錫命之恩，有功則受，無功則辭，古今通義。」允其請，予休沐，

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-3E4BF7BCFAD0F79EB24D27E5@SP-77CE39608B951673AAE2`、`K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-90899060763733DC3B193C3B@SP-77CE39608B951673AAE2`、`K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C301B15B52EE1BEC59DF2AC8@SP-4C7F0FB3398E0306DC61`、`K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C5C447885AC4E26346FA87F6@SP-4C7F0FB3398E0306DC61`
- 理由：鄂尔泰获大学士、兵部尚书及军机职权后，同年又受命督巡陕甘并经略准噶尔，属于新增军务授权。

#### Reviewer B

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-3E4BF7BCFAD0F79EB24D27E5@SP-77CE39608B951673AAE2`、`K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C301B15B52EE1BEC59DF2AC8@SP-4C7F0FB3398E0306DC61`
- 理由：左端授鄂尔泰兵部尚书并办理军机事务，右端同年命其经略准噶尔军务并实际部署，属于该职权阶段的直接授权履职。

### 第三方裁决结果

#### Adjudicator C

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-3E4BF7BCFAD0F79EB24D27E5@SP-77CE39608B951673AAE2`、`K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-90899060763733DC3B193C3B@SP-77CE39608B951673AAE2`、`K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C301B15B52EE1BEC59DF2AC8@SP-4C7F0FB3398E0306DC61`、`K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C5C447885AC4E26346FA87F6@SP-4C7F0FB3398E0306DC61`
- 理由：左端先授鄂尔泰兵部尚书并令其办理军机事务，紧接着右端同年再明确授予督巡陕甘、经略准噶尔军务，属于其职权范围的直接新增与具体化。

---

## 2. `RBC-010E843741C5C96D1FC6`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 3, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-20A41678140708875884`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "office_holder"]
- 行为：其他
- 责任：改土归流
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-7059B4E874002BF28B65FE24@SP-8F060AB49BB51467623E`
  - 时间：雍正四年春
  - 命题：鄂尔泰 / 其他 / 云贵苗蛮土司治理
  - 结果：上深然之
  - 摘要：雍正四年，鄂尔泰疏陈制夷须改土归流，胤禛深然其议。
  - SourcePassage：`SP-8F060AB49BB51467623E`
- `K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-782D7C16F78CDA8B6A604113@SP-8F060AB49BB51467623E`
  - 时间：雍正四年春
  - 命题：鄂尔泰 / 其他 / 云贵苗蛮土司治理
  - 结果：上深然之
  - 摘要：雍正四年，鄂尔泰疏陈制夷须改土归流，胤禛深然其议。
  - SourcePassage：`SP-8F060AB49BB51467623E`

#### SourcePassage 原文与上下文

<details><summary><code>SP-8F060AB49BB51467623E</code> · eertai-liezhuan:431-1215</summary>

上文：

> 文為南邦黎獻集。以應得公使銀買穀三萬三千四百石有奇，分貯蘇、松、常三府備賑貸。察太湖水利，擬疏下游吳淞、白茆，役未舉。
> 三年，遷廣西巡撫，甫上官，調雲南，以巡撫治總督事。貴州仲家苗為亂二十餘年，巡撫石禮哈、提督馬會伯請用兵，上未即許。巡撫何世璂疏言仲家苗藥箭銛利，地勢險阻，用兵不易，上即命世璂招撫，久未定，詔諮鄂爾泰。

原文：

> 四年春，疏言：「雲、貴大患無如​​苗、蠻。欲安民必制夷，欲制夷必改土歸流。而苗疆多與鄰省相錯，即如東川、烏蒙、鎮雄，皆四川土府，東川距雲南四百餘里。去冬烏蒙攻掠東川，滇兵擊退，而川省令箭方至。烏蒙距雲南省城亦僅六百餘里，錢糧不過三百餘兩，取於下者百倍。一年四小派，三年一大派，小派計錢，大派計兩。土司娶子婦，土民三載不敢婚。土民被殺，親族尚出墊刀數十金，終身不見天日。東川雖已改流，尚為土目盤據，文武長寓省城，膏腴四百里無人敢墾。若改隸雲南，俾臣得相機改流，可設三府、一鎮。此事連四川者也。廣西土府、州、縣、峒、寨等一百五十餘員，分隸南寧、太平、思恩、慶遠四府。其為邊患，自泗城土府外，皆土目橫於土司。黔、粵以牂牁江為界，而粵屬西隆州與黔屬普安州越江互相鬥入。苗寨寥闊，將吏推諉。應以江北歸黔，江南歸粵，增州設營，形格勢禁。此事連廣西者也。滇邊西南界以瀾滄江，江外為車裡、緬甸、老撾諸境，其江內鎮沅、威遠、元江、新平、普洱、茶山諸夷，巢穴深邃，出沒魯魁、哀牢間，無事近患腹心，有事遠通外國。論者謂江外宜土不宜流，江內宜流不宜土。此雲南宜治之邊夷也。貴州土司向無鉗束群苗之責，苗患甚於土司。苗疆四圍幾三千餘里，千三百餘寨，古州踞其中，群寨環其外。左有清江可北達楚，右有都江可南通粵，蟠據梗隔，遂成化外。如欲開江路通黔、粵，非勒兵深入遍加剿撫不可。此貴州宜治之邊夷也。臣思前明流、土之分，原因煙瘴新疆，未習風土，故因地制宜，使之鄉導彈壓。今歷數百載，以夷治夷，即以盜治盜，苗、倮無追贓抵命之憂，土司無革職削地之罰。直至事上聞，行賄詳結，上司亦不深求，以為鎮靜，邊民無所控訴。若不剷蔓塞源，縱兵刑財賦事事整理，皆非治本。改流之法：計擒為上，兵剿次之；令其自首為上，勒獻次之。惟剿夷必練兵，練兵必選將。誠能賞罰嚴明，將士用命，先治內，後攘外，實邊防百世之利。」疏入，上深然之。

下文：

> 會石禮哈疏報遣兵擊破谷隆、長寨、者貢、羊城諸隘，擒其渠阿革、阿給及諸苗之從為亂者，上命交鄂爾泰按讞。五月，鄂爾泰遣兵三道入：一自谷隆，一自焦山，一自馬落孔。破三十六寨，降二十一寨，撫苗民五百餘戶、二千餘口，察出荒熟田地三萬畝。又以鎮遠土知府刁澣、霑益土知州安於籓素兇詐，計擒之；者樂甸土司刁聯鬥乞免死，改土歸流。鄂爾

</details>

### 右端内容

- Episode：`EP-2925036C0C00A20C391F`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "office_holder"]
- 行为：任命
- 责任：江苏布政使
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-390495B19DE153FFE920A9C3@SP-9E10DC378003B7EE70B0`
  - 时间：雍正元年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：特擢江苏布政使
  - 摘要：雍正元年，胤禛特擢鄂尔泰为江苏布政使。
  - SourcePassage：`SP-9E10DC378003B7EE70B0`
- `K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-9CDB502178A1BC5A34CD7653@SP-9E10DC378003B7EE70B0`
  - 时间：雍正元年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：特擢江苏布政使
  - 摘要：雍正元年，胤禛特擢鄂尔泰为江苏布政使。
  - SourcePassage：`SP-9E10DC378003B7EE70B0`

#### SourcePassage 原文与上下文

<details><summary><code>SP-9E10DC378003B7EE70B0</code> · eertai-liezhuan:233-254</summary>

上文：

> 初有屯泰者，以七村附太祖，授牛錄額真。子圖捫，事太宗，從戰大凌河，擊明將張理，陣沒，授備禦世職。雍正初，祀昭忠祠。
> 鄂爾泰，其曾孫也。康熙三十八年舉人。四十二年，襲佐領，授三等侍衛。從聖祖獵，和詩稱旨。五十五年，遷內務府員外郎。世宗在籓邸，偶有所囑，鄂爾泰拒之。世宗即位，召曰：「汝為郎官拒皇子，其執法甚堅。」深慰諭之。

原文：

> 雍正元年，充雲南鄉試考官，特擢江蘇布政使。

下文：

> 於廨中建春風亭，禮致能文士，錄其詩文為南邦黎獻集。以應得公使銀買穀三萬三千四百石有奇，分貯蘇、松、常三府備賑貸。察太湖水利，擬疏下游吳淞、白茆，役未舉。
> 三年，遷廣西巡撫，甫上官，調雲南，以巡撫治總督事。貴州仲家苗為亂二十餘年，巡撫石禮哈、提督馬會伯請用兵，上未即許。巡撫何世璂疏言仲家苗藥箭銛利，地勢險阻，用兵不易，上

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-7059B4E874002BF28B65FE24@SP-8F060AB49BB51467623E`、`K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-782D7C16F78CDA8B6A604113@SP-8F060AB49BB51467623E`、`K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-390495B19DE153FFE920A9C3@SP-9E10DC378003B7EE70B0`、`K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-9CDB502178A1BC5A34CD7653@SP-9E10DC378003B7EE70B0`
- 理由：江苏布政使任命与三年后的云贵改土归流建议分属不同地域和职责，端点证据没有直接授权或因果联系。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-7059B4E874002BF28B65FE24@SP-8F060AB49BB51467623E`、`K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-390495B19DE153FFE920A9C3@SP-9E10DC378003B7EE70B0`
- 理由：左端是雍正四年的云贵改土归流建议，右端是三年前的江苏布政使任命，证据未建立该任命与后续建议的直接承接。

---

## 3. `RBC-021981DDAB9325D8E22B`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 9, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-3E7EDCD49082BF8AF64C`
- 人物：obj-485798d73c4c10dd
- 角色：["delegate"]
- 行为：授权
- 责任：顾命辅政、皇位继承
- 责任族：`succession_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-8795461FDB493D995C9300AA@SP-0B53FC0B636ACD7FE703`
  - 时间：雍正十三年八月
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰与张廷玉捧御笔密诏，命高宗为皇太子
  - 摘要：雍正十三年，胤禛病重时命鄂尔泰同允禄、允礼、张廷玉等受顾命，并由鄂尔泰与张廷玉捧御笔密诏立弘历为皇太子。
  - SourcePassage：`SP-0B53FC0B636ACD7FE703`
- `K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-BAE794A278FD0C6055D5BFE0@SP-0B53FC0B636ACD7FE703`
  - 时间：雍正十三年八月
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰与张廷玉捧御笔密诏，命高宗为皇太子
  - 摘要：雍正十三年，胤禛病重时命鄂尔泰同允禄、允礼、张廷玉等受顾命，并由鄂尔泰与张廷玉捧御笔密诏立弘历为皇太子。
  - SourcePassage：`SP-0B53FC0B636ACD7FE703`

#### SourcePassage 原文与上下文

<details><summary><code>SP-0B53FC0B636ACD7FE703</code> · eertai-liezhuan:3426-3500</summary>

上文：

> 可驟滅，用兵久，敝中國，無益，上頗然之。
> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾，焚掠黃平、施秉諸地。鄂爾泰以從前佈置未協，引咎請罷斥，並削去伯爵。上曰：「國家錫命之恩，有功則受，無功則辭，古今通義。」允其請，予休沐，仍食俸。尋命留三等阿思哈尼哈番。

原文：

> 八月，世宗疾大漸，鄂爾泰仍以大學士與莊親王允祿，果親王允禮，大學士張廷玉，內大臣豐盛額、訥親、海望同被顧命。鄂爾泰與廷玉捧御筆密詔，命高宗為皇太子。

下文：

> 俄，皇太子傳旨命鄂爾泰等輔政。世宗崩，宣遺詔以鄂爾泰志秉忠貞，才優經濟，命他日配享太廟。高宗即位，命總理事務，進一等精奇尼哈番。乾隆二年十一月，辭總理事務，授軍機大臣；又辭兼管兵部，上不許，加拜他喇布勒哈番，合為三等伯，賜號襄勤。迭主會試，充領侍衛內大臣、議政大臣、經筵講官。
> 四年，南河河道總督高斌請開新運口，河東河道

</details>

### 右端内容

- Episode：`EP-8CB3B50DDAB3A262F495`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "advisor", "commander", "delegate"]
- 行为：战役
- 责任：云贵苗疆
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-4CBC696C9FC9785C0DD1-EVD-67DAEE66DEDC3961B2838399@SP-79573AD11A58384C8BAE`
  - 时间：五月至十月
  - 命题：鄂尔泰 / 战役 / 仲家苗
  - 结果：破三十六寨，降二十一寨；上嘉其成功速，真除云贵总督
  - 摘要：鄂尔泰遣兵三道入仲家苗地，破三十六寨、降二十一寨，因速成受嘉奖并真除云贵总督。
  - SourcePassage：`SP-79573AD11A58384C8BAE`
- `K0-A-G26I-A-CLMK-4CBC696C9FC9785C0DD1-EVD-9F0DDBA6863393E6201FE048@SP-79573AD11A58384C8BAE`
  - 时间：五月至十月
  - 命题：鄂尔泰 / 战役 / 仲家苗
  - 结果：破三十六寨，降二十一寨；上嘉其成功速，真除云贵总督
  - 摘要：鄂尔泰遣兵三道入仲家苗地，破三十六寨、降二十一寨，因速成受嘉奖并真除云贵总督。
  - SourcePassage：`SP-79573AD11A58384C8BAE`

#### SourcePassage 原文与上下文

<details><summary><code>SP-79573AD11A58384C8BAE</code> · eertai-liezhuan:1267-1418</summary>

上文：

> 靜，邊民無所控訴。若不剷蔓塞源，縱兵刑財賦事事整理，皆非治本。改流之法：計擒為上，兵剿次之；令其自首為上，勒獻次之。惟剿夷必練兵，練兵必選將。誠能賞罰嚴明，將士用命，先治內，後攘外，實邊防百世之利。」疏入，上深然之。
> 會石禮哈疏報遣兵擊破谷隆、長寨、者貢、羊城諸隘，擒其渠阿革、阿給及諸苗之從為亂者，上命交鄂爾泰按讞。

原文：

> 五月，鄂爾泰遣兵三道入：一自谷隆，一自焦山，一自馬落孔。破三十六寨，降二十一寨，撫苗民五百餘戶、二千餘口，察出荒熟田地三萬畝。又以鎮遠土知府刁澣、霑益土知州安於籓素兇詐，計擒之；者樂甸土司刁聯鬥乞免死，改土歸流。鄂爾泰疏報仲家苗悉定。上嘉其成功速，令議敘。旋條上經理仲苗諸事，報可。十月，真除雲貴總督。

下文：

> 四川烏蒙土司祿萬鍾為亂，侵東川。鄂爾泰請以東川改隸雲南，上從之。仍命會四川總督岳鍾琪按治，招其渠祿鼎坤出降。鄂爾泰令鼎坤招萬鍾，數往不就撫，乃檄總兵劉起元率師討之，破其所居寨。萬鍾走匿鎮雄土司隴慶侯所。五年，萬鍾詣鍾琪降，慶侯亦詣鍾琪請改土歸流。上命鍾琪以萬鍾、慶侯交鄂爾泰按讞。敘功，授世職拜他喇布勒哈番。三月，鎮沅

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-8795461FDB493D995C9300AA@SP-0B53FC0B636ACD7FE703`、`K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-BAE794A278FD0C6055D5BFE0@SP-0B53FC0B636ACD7FE703`、`K0-A-G26I-A-CLMK-4CBC696C9FC9785C0DD1-EVD-67DAEE66DEDC3961B2838399@SP-79573AD11A58384C8BAE`、`K0-A-G26I-A-CLMK-4CBC696C9FC9785C0DD1-EVD-9F0DDBA6863393E6201FE048@SP-79573AD11A58384C8BAE`
- 理由：仲家苗军事行动及真除总督发生在前，临终顾命与立储授权发生在后，两端事务不同且无直接承接。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-8795461FDB493D995C9300AA@SP-0B53FC0B636ACD7FE703`、`K0-A-G26I-A-CLMK-4CBC696C9FC9785C0DD1-EVD-67DAEE66DEDC3961B2838399@SP-79573AD11A58384C8BAE`
- 理由：雍正十三年的顾命立储与九年前的仲家苗战役属于不同职责和事件，仅共享鄂尔泰这一人物不足以形成直接关系。

---

## 4. `RBC-025CEBB117F5B5FCBAC1`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 6, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-C6DC6BAC25E2EC8A3B6B`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "office_holder"]
- 行为：处置
- 责任：苗疆户口赋役
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-ECB9F0717609409B6364-EVD-032B14F939A732A2C6A1CBEE@SP-8641D0BD1B967FF34A4F`
  - 时间：十一月
  - 命题：鄂尔泰 / 处置 / 长寨后路苗
  - 结果：编户口，定额赋；得旨嘉奖，进世职一等阿达哈哈番
  - 摘要：鄂尔泰招降长寨后路苗一百八十四寨，编户口、定额赋，获旨嘉奖并进世职。
  - SourcePassage：`SP-8641D0BD1B967FF34A4F`
- `K0-A-G26I-A-CLMK-ECB9F0717609409B6364-EVD-EB3E1C2E6C2890A0E94ACBBD@SP-8641D0BD1B967FF34A4F`
  - 时间：十一月
  - 命题：鄂尔泰 / 处置 / 长寨后路苗
  - 结果：编户口，定额赋；得旨嘉奖，进世职一等阿达哈哈番
  - 摘要：鄂尔泰招降长寨后路苗一百八十四寨，编户口、定额赋，获旨嘉奖并进世职。
  - SourcePassage：`SP-8641D0BD1B967FF34A4F`

#### SourcePassage 原文与上下文

<details><summary><code>SP-8641D0BD1B967FF34A4F</code> · eertai-liezhuan:1755-1796</summary>

上文：

> 如珍。泗城土知府岑映宸縱其眾出掠，又發兵屯者相，立七營。鄂爾泰疏劾，令諸道兵候檄進討，映宸乞免死存祀，改土歸流。鄂爾泰請映宸送浙江原籍，留其弟映翰奉祀。七月，發兵與湖北師會討定謬衝花苗，獲其渠，降其餘眾。威遠倮札鐵匠等、新平倮李百疊等應如珍為亂。九月，鄂爾泰檄臨元總兵孫宏本率師討之，獲札鐵匠，降李百疊。威遠、新平皆定。

原文：

> 十一月，招降長寨後路苗百八十四寨，編戶口，定額賦。得旨嘉獎，進世職一等阿達哈哈番。

下文：

> 十二月，攻破雲南倮窩泥種，取六茶山地千餘里，劃界建城，置官吏。
> 雲南南徼地與安南接，前總督高其倬疏言安南國界應屬內地者百二十里，請以賭咒河為界。安南國王黎維祹奏辯，上命鄂爾泰清察。鄂爾泰請與地八十里，於鉛廠山下小河內四十里立界，上從之，敕諭安南。六年，維祹表謝，上嘉其知禮，命復與四十里。旋討擒東川法戛土目祿天佑、則補土

</details>

### 右端内容

- Episode：`EP-E04D5F70E470FF822210`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "advisor", "commander", "delegate"]
- 行为：授权
- 责任：陕甘、准噶尔军务
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C301B15B52EE1BEC59DF2AC8@SP-4C7F0FB3398E0306DC61`
  - 时间：雍正十年六月至九月
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰檄张广泗截衮塔马哈戈壁，断敌北遁道；寻疏请屯田
  - 摘要：雍正十年，胤禛命鄂尔泰督巡陕甘、经略准噶尔军务；鄂尔泰随后檄张广泗截断敌北遁道并疏请屯田。
  - SourcePassage：`SP-4C7F0FB3398E0306DC61`
- `K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C5C447885AC4E26346FA87F6@SP-4C7F0FB3398E0306DC61`
  - 时间：雍正十年六月至九月
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰檄张广泗截衮塔马哈戈壁，断敌北遁道；寻疏请屯田
  - 摘要：雍正十年，胤禛命鄂尔泰督巡陕甘、经略准噶尔军务；鄂尔泰随后檄张广泗截断敌北遁道并疏请屯田。
  - SourcePassage：`SP-4C7F0FB3398E0306DC61`

#### SourcePassage 原文与上下文

<details><summary><code>SP-4C7F0FB3398E0306DC61</code> · eertai-liezhuan:3181-3249</summary>

上文：

> 半。皦子入貢，犒以鹽三百斤。九年，疏請重定烏蒙、鎮遠、東川、威寧營汛。別疏請興雲南水利，濬嵩明州楊林海，開墾周圍草塘，疏宜良、尋甸諸水，耕東川城北漫海，築浪穹羽河諸堤，修臨安諸處工，暨通粵河道，皆下部議行。十年，召拜保和殿大學士，兼兵部尚書，辦理軍機事務。敘定苗疆功，部議進世職一等精奇尼哈番，上特命授一等伯爵，世襲。

原文：

> 師討準噶爾，六月，命鄂爾泰督巡陝、甘，經略軍務。九月，師破敵額爾德尼昭，鄂爾泰檄大將軍張廣泗遣兵截袞塔馬哈戈壁，斷敵北遁道。尋疏請屯田。

下文：

> 十一年六月，還京師。入對，言準部未可驟滅，用兵久，敝中國，無益，上頗然之。
> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾，焚掠黃平、施秉諸地。鄂爾泰以從前佈置未協，引咎請罷斥，並削去伯爵。上曰：「國家錫命之恩，有功則受，無功則辭，古今通義。」允其請，予休沐，

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-ECB9F0717609409B6364-EVD-032B14F939A732A2C6A1CBEE@SP-8641D0BD1B967FF34A4F`、`K0-A-G26I-A-CLMK-ECB9F0717609409B6364-EVD-EB3E1C2E6C2890A0E94ACBBD@SP-8641D0BD1B967FF34A4F`、`K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C301B15B52EE1BEC59DF2AC8@SP-4C7F0FB3398E0306DC61`、`K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C5C447885AC4E26346FA87F6@SP-4C7F0FB3398E0306DC61`
- 理由：招降苗寨、编户定赋与多年后经略准噶尔是不同地区和任务，仅共享鄂尔泰本人。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-ECB9F0717609409B6364-EVD-032B14F939A732A2C6A1CBEE@SP-8641D0BD1B967FF34A4F`、`K0-A-G26I-A-CLMK-34942B202154E448F651-EVD-C301B15B52EE1BEC59DF2AC8@SP-4C7F0FB3398E0306DC61`
- 理由：长寨苗户口赋役处置与多年后的陕甘准噶尔军务授权，地域、对象和任务均不同，端点证据没有直接联系。

---

## 5. `RBC-04D30037E8AB1BFA01D5`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 1, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`mandate_or_outcome`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-20A41678140708875884`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "office_holder"]
- 行为：其他
- 责任：改土归流
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-7059B4E874002BF28B65FE24@SP-8F060AB49BB51467623E`
  - 时间：雍正四年春
  - 命题：鄂尔泰 / 其他 / 云贵苗蛮土司治理
  - 结果：上深然之
  - 摘要：雍正四年，鄂尔泰疏陈制夷须改土归流，胤禛深然其议。
  - SourcePassage：`SP-8F060AB49BB51467623E`
- `K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-782D7C16F78CDA8B6A604113@SP-8F060AB49BB51467623E`
  - 时间：雍正四年春
  - 命题：鄂尔泰 / 其他 / 云贵苗蛮土司治理
  - 结果：上深然之
  - 摘要：雍正四年，鄂尔泰疏陈制夷须改土归流，胤禛深然其议。
  - SourcePassage：`SP-8F060AB49BB51467623E`

#### SourcePassage 原文与上下文

<details><summary><code>SP-8F060AB49BB51467623E</code> · eertai-liezhuan:431-1215</summary>

上文：

> 文為南邦黎獻集。以應得公使銀買穀三萬三千四百石有奇，分貯蘇、松、常三府備賑貸。察太湖水利，擬疏下游吳淞、白茆，役未舉。
> 三年，遷廣西巡撫，甫上官，調雲南，以巡撫治總督事。貴州仲家苗為亂二十餘年，巡撫石禮哈、提督馬會伯請用兵，上未即許。巡撫何世璂疏言仲家苗藥箭銛利，地勢險阻，用兵不易，上即命世璂招撫，久未定，詔諮鄂爾泰。

原文：

> 四年春，疏言：「雲、貴大患無如​​苗、蠻。欲安民必制夷，欲制夷必改土歸流。而苗疆多與鄰省相錯，即如東川、烏蒙、鎮雄，皆四川土府，東川距雲南四百餘里。去冬烏蒙攻掠東川，滇兵擊退，而川省令箭方至。烏蒙距雲南省城亦僅六百餘里，錢糧不過三百餘兩，取於下者百倍。一年四小派，三年一大派，小派計錢，大派計兩。土司娶子婦，土民三載不敢婚。土民被殺，親族尚出墊刀數十金，終身不見天日。東川雖已改流，尚為土目盤據，文武長寓省城，膏腴四百里無人敢墾。若改隸雲南，俾臣得相機改流，可設三府、一鎮。此事連四川者也。廣西土府、州、縣、峒、寨等一百五十餘員，分隸南寧、太平、思恩、慶遠四府。其為邊患，自泗城土府外，皆土目橫於土司。黔、粵以牂牁江為界，而粵屬西隆州與黔屬普安州越江互相鬥入。苗寨寥闊，將吏推諉。應以江北歸黔，江南歸粵，增州設營，形格勢禁。此事連廣西者也。滇邊西南界以瀾滄江，江外為車裡、緬甸、老撾諸境，其江內鎮沅、威遠、元江、新平、普洱、茶山諸夷，巢穴深邃，出沒魯魁、哀牢間，無事近患腹心，有事遠通外國。論者謂江外宜土不宜流，江內宜流不宜土。此雲南宜治之邊夷也。貴州土司向無鉗束群苗之責，苗患甚於土司。苗疆四圍幾三千餘里，千三百餘寨，古州踞其中，群寨環其外。左有清江可北達楚，右有都江可南通粵，蟠據梗隔，遂成化外。如欲開江路通黔、粵，非勒兵深入遍加剿撫不可。此貴州宜治之邊夷也。臣思前明流、土之分，原因煙瘴新疆，未習風土，故因地制宜，使之鄉導彈壓。今歷數百載，以夷治夷，即以盜治盜，苗、倮無追贓抵命之憂，土司無革職削地之罰。直至事上聞，行賄詳結，上司亦不深求，以為鎮靜，邊民無所控訴。若不剷蔓塞源，縱兵刑財賦事事整理，皆非治本。改流之法：計擒為上，兵剿次之；令其自首為上，勒獻次之。惟剿夷必練兵，練兵必選將。誠能賞罰嚴明，將士用命，先治內，後攘外，實邊防百世之利。」疏入，上深然之。

下文：

> 會石禮哈疏報遣兵擊破谷隆、長寨、者貢、羊城諸隘，擒其渠阿革、阿給及諸苗之從為亂者，上命交鄂爾泰按讞。五月，鄂爾泰遣兵三道入：一自谷隆，一自焦山，一自馬落孔。破三十六寨，降二十一寨，撫苗民五百餘戶、二千餘口，察出荒熟田地三萬畝。又以鎮遠土知府刁澣、霑益土知州安於籓素兇詐，計擒之；者樂甸土司刁聯鬥乞免死，改土歸流。鄂爾

</details>

### 右端内容

- Episode：`EP-39C944ACEA99EFD07E97`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "office_holder"]
- 行为：任命
- 责任：广西巡抚、云南巡抚治总督事
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-F4012B00487969200E03E3D8@SP-6948AA368B32505B3F0B`
  - 时间：雍正三年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：迁广西巡抚，调云南，以巡抚治总督事
  - 摘要：雍正三年，鄂尔泰迁广西巡抚，旋调云南，以巡抚治总督事。
  - SourcePassage：`SP-6948AA368B32505B3F0B`
- `K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-FEC139373E8198C68E728304@SP-6948AA368B32505B3F0B`
  - 时间：雍正三年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：迁广西巡抚，调云南，以巡抚治总督事
  - 摘要：雍正三年，鄂尔泰迁广西巡抚，旋调云南，以巡抚治总督事。
  - SourcePassage：`SP-6948AA368B32505B3F0B`

#### SourcePassage 原文与上下文

<details><summary><code>SP-6948AA368B32505B3F0B</code> · eertai-liezhuan:331-356</summary>

上文：

> 稱旨。五十五年，遷內務府員外郎。世宗在籓邸，偶有所囑，鄂爾泰拒之。世宗即位，召曰：「汝為郎官拒皇子，其執法甚堅。」深慰諭之。雍正元年，充雲南鄉試考官，特擢江蘇布政使。於廨中建春風亭，禮致能文士，錄其詩文為南邦黎獻集。以應得公使銀買穀三萬三千四百石有奇，分貯蘇、松、常三府備賑貸。察太湖水利，擬疏下游吳淞、白茆，役未舉。

原文：

> 三年，遷廣西巡撫，甫上官，調雲南，以巡撫治總督事。

下文：

> 貴州仲家苗為亂二十餘年，巡撫石禮哈、提督馬會伯請用兵，上未即許。巡撫何世璂疏言仲家苗藥箭銛利，地勢險阻，用兵不易，上即命世璂招撫，久未定，詔諮鄂爾泰。四年春，疏言：「雲、貴大患無如​​苗、蠻。欲安民必制夷，欲制夷必改土歸流。而苗疆多與鄰省相錯，即如東川、烏蒙、鎮雄，皆四川土府，東川距雲南四百餘里。去冬烏蒙攻掠東川，滇兵

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-7059B4E874002BF28B65FE24@SP-8F060AB49BB51467623E`、`K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-782D7C16F78CDA8B6A604113@SP-8F060AB49BB51467623E`、`K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-F4012B00487969200E03E3D8@SP-6948AA368B32505B3F0B`、`K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-FEC139373E8198C68E728304@SP-6948AA368B32505B3F0B`
- 理由：鄂尔泰先调云南并以巡抚治总督事，随后在该治理职责中提出并获准云贵改土归流方案，属于同一授权履职阶段。

#### Reviewer B

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-G26I-A-CLMK-D36EFB0149DB883E0B8B-EVD-7059B4E874002BF28B65FE24@SP-8F060AB49BB51467623E`、`K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-F4012B00487969200E03E3D8@SP-6948AA368B32505B3F0B`
- 理由：右端授鄂尔泰云南巡抚治总督事，左端次年即由其就云贵治理提出并获采纳的改土归流方案，属于该区域任内的直接履职。

---

## 6. `RBC-0505E5B94439B9C747CF`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 2, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`mandate_or_outcome`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-39C944ACEA99EFD07E97`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "office_holder"]
- 行为：任命
- 责任：广西巡抚、云南巡抚治总督事
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-F4012B00487969200E03E3D8@SP-6948AA368B32505B3F0B`
  - 时间：雍正三年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：迁广西巡抚，调云南，以巡抚治总督事
  - 摘要：雍正三年，鄂尔泰迁广西巡抚，旋调云南，以巡抚治总督事。
  - SourcePassage：`SP-6948AA368B32505B3F0B`
- `K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-FEC139373E8198C68E728304@SP-6948AA368B32505B3F0B`
  - 时间：雍正三年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：迁广西巡抚，调云南，以巡抚治总督事
  - 摘要：雍正三年，鄂尔泰迁广西巡抚，旋调云南，以巡抚治总督事。
  - SourcePassage：`SP-6948AA368B32505B3F0B`

#### SourcePassage 原文与上下文

<details><summary><code>SP-6948AA368B32505B3F0B</code> · eertai-liezhuan:331-356</summary>

上文：

> 稱旨。五十五年，遷內務府員外郎。世宗在籓邸，偶有所囑，鄂爾泰拒之。世宗即位，召曰：「汝為郎官拒皇子，其執法甚堅。」深慰諭之。雍正元年，充雲南鄉試考官，特擢江蘇布政使。於廨中建春風亭，禮致能文士，錄其詩文為南邦黎獻集。以應得公使銀買穀三萬三千四百石有奇，分貯蘇、松、常三府備賑貸。察太湖水利，擬疏下游吳淞、白茆，役未舉。

原文：

> 三年，遷廣西巡撫，甫上官，調雲南，以巡撫治總督事。

下文：

> 貴州仲家苗為亂二十餘年，巡撫石禮哈、提督馬會伯請用兵，上未即許。巡撫何世璂疏言仲家苗藥箭銛利，地勢險阻，用兵不易，上即命世璂招撫，久未定，詔諮鄂爾泰。四年春，疏言：「雲、貴大患無如​​苗、蠻。欲安民必制夷，欲制夷必改土歸流。而苗疆多與鄰省相錯，即如東川、烏蒙、鎮雄，皆四川土府，東川距雲南四百餘里。去冬烏蒙攻掠東川，滇兵

</details>

### 右端内容

- Episode：`EP-42982548C35846BE890F`
- 人物：obj-485798d73c4c10dd
- 角色：["delegate"]
- 行为：授权
- 责任：安南国界清察
- 责任族：`border_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-5ECE1B7DD07CF82B6A34-EVD-1B575B8727E70EDC0E3796C0@SP-FECBE9CD20723BC635AA`
  - 时间：雍正五年至六年
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：请与地八十里并立界，上从之，敕谕安南
  - 摘要：胤禛命鄂尔泰清察安南边界，鄂尔泰请与地八十里并立界，胤禛从其议并敕谕安南。
  - SourcePassage：`SP-FECBE9CD20723BC635AA`
- `K0-A-G26I-A-CLMK-5ECE1B7DD07CF82B6A34-EVD-32FC7E10B9F625AF063F4363@SP-FECBE9CD20723BC635AA`
  - 时间：雍正五年至六年
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：请与地八十里并立界，上从之，敕谕安南
  - 摘要：胤禛命鄂尔泰清察安南边界，鄂尔泰请与地八十里并立界，胤禛从其议并敕谕安南。
  - SourcePassage：`SP-FECBE9CD20723BC635AA`

#### SourcePassage 原文与上下文

<details><summary><code>SP-FECBE9CD20723BC635AA</code> · eertai-liezhuan:1828-1919</summary>

上文：

> 奉祀。七月，發兵與湖北師會討定謬衝花苗，獲其渠，降其餘眾。威遠倮札鐵匠等、新平倮李百疊等應如珍為亂。九月，鄂爾泰檄臨元總兵孫宏本率師討之，獲札鐵匠，降李百疊。威遠、新平皆定。十一月，招降長寨後路苗百八十四寨，編戶口，定額賦。得旨嘉獎，進世職一等阿達哈哈番。十二月，攻破雲南倮窩泥種，取六茶山地千餘里，劃界建城，置官吏。

原文：

> 雲南南徼地與安南接，前總督高其倬疏言安南國界應屬內地者百二十里，請以賭咒河為界。安南國王黎維祹奏辯，上命鄂爾泰清察。鄂爾泰請與地八十里，於鉛廠山下小河內四十里立界，上從之，敕諭安南。

下文：

> 六年，維祹表謝，上嘉其知禮，命復與四十里。旋討擒東川法戛土目祿天佑、則補土目祿世豪；按治米貼土目祿永孝，論斬。永孝妻陸氏結倮儸為亂，檄總兵張耀祖討之，攻克門坎山。師入，獲陸氏。米貼平。廣西八達寨儂顏光色等為亂，提督田畯不能討。鄂爾泰遣兵往，儂殺光色以降。上命鄂爾泰總督雲、貴、廣西三省，發帑十萬犒師。旋又撫貴州拜克猛、長

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-F4012B00487969200E03E3D8@SP-6948AA368B32505B3F0B`、`K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-FEC139373E8198C68E728304@SP-6948AA368B32505B3F0B`、`K0-A-G26I-A-CLMK-5ECE1B7DD07CF82B6A34-EVD-1B575B8727E70EDC0E3796C0@SP-FECBE9CD20723BC635AA`、`K0-A-G26I-A-CLMK-5ECE1B7DD07CF82B6A34-EVD-32FC7E10B9F625AF063F4363@SP-FECBE9CD20723BC635AA`
- 理由：鄂尔泰调云南并治总督事后奉命清察云南与安南边界，属于该地方治理任命下的直接履职。

#### Reviewer B

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-G26I-A-CLMK-E0FBA4CE93A0BC45BD00-EVD-F4012B00487969200E03E3D8@SP-6948AA368B32505B3F0B`、`K0-A-G26I-A-CLMK-5ECE1B7DD07CF82B6A34-EVD-1B575B8727E70EDC0E3796C0@SP-FECBE9CD20723BC635AA`
- 理由：鄂尔泰受任云南巡抚治总督事后，奉命清察云南与安南边界并提出立界方案，右端是该区域任职阶段的明确授权履职。

---

## 7. `RBC-0AF9DCB2E0858A1CF4A3`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 2, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-9C04E14D1A7F0BDBF395`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "advisor", "commander", "delegate"]
- 行为：纳谏
- 责任：准噶尔军务
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-94D8BC65FAA7173BA5EC-EVD-29CD6C452724BF518EE6946C@SP-419097E684B9B3520C79`
  - 时间：雍正十一年六月
  - 命题：鄂尔泰 / 纳谏 / 准噶尔用兵方略
  - 结果：上颇然之
  - 摘要：雍正十一年，鄂尔泰入对称准噶尔不可骤灭、久用兵会敝中国且无益，胤禛颇然其言。
  - SourcePassage：`SP-419097E684B9B3520C79`
- `K0-A-G26I-A-CLMK-94D8BC65FAA7173BA5EC-EVD-88B313C12398F35097B561FE@SP-419097E684B9B3520C79`
  - 时间：雍正十一年六月
  - 命题：鄂尔泰 / 纳谏 / 准噶尔用兵方略
  - 结果：上颇然之
  - 摘要：雍正十一年，鄂尔泰入对称准噶尔不可骤灭、久用兵会敝中国且无益，胤禛颇然其言。
  - SourcePassage：`SP-419097E684B9B3520C79`

#### SourcePassage 原文与上下文

<details><summary><code>SP-419097E684B9B3520C79</code> · eertai-liezhuan:3249-3286</summary>

上文：

> 耕東川城北漫海，築浪穹羽河諸堤，修臨安諸處工，暨通粵河道，皆下部議行。十年，召拜保和殿大學士，兼兵部尚書，辦理軍機事務。敘定苗疆功，部議進世職一等精奇尼哈番，上特命授一等伯爵，世襲。
> 師討準噶爾，六月，命鄂爾泰督巡陝、甘，經略軍務。九月，師破敵額爾德尼昭，鄂爾泰檄大將軍張廣泗遣兵截袞塔馬哈戈壁，斷敵北遁道。尋疏請屯田。

原文：

> 十一年六月，還京師。入對，言準部未可驟滅，用兵久，敝中國，無益，上頗然之。

下文：

> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾，焚掠黃平、施秉諸地。鄂爾泰以從前佈置未協，引咎請罷斥，並削去伯爵。上曰：「國家錫命之恩，有功則受，無功則辭，古今通義。」允其請，予休沐，仍食俸。尋命留三等阿思哈尼哈番。
> 八月，世宗疾大漸，鄂爾泰仍以大學士與莊親

</details>

### 右端内容

- Episode：`EP-DF8029963C16AC87A745`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "advisor", "commander", "delegate"]
- 行为：授权
- 责任：办理苗疆事务处
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-09E0B242BD6FA098BEDF9561@SP-2F859BA3FA47D540E906`
  - 时间：雍正十三年
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰引咎请罢斥并削去伯爵，上允其请，仍食俸
  - 摘要：雍正十三年台拱苗复叛后，胤禛设办理苗疆事务处，命鄂尔泰等董其事；鄂尔泰引咎请削伯爵并获允。
  - SourcePassage：`SP-2F859BA3FA47D540E906`
- `K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-6E3AB872C5F44FDEF7DCC87B@SP-2F859BA3FA47D540E906`
  - 时间：雍正十三年
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰引咎请罢斥并削去伯爵，上允其请，仍食俸
  - 摘要：雍正十三年台拱苗复叛后，胤禛设办理苗疆事务处，命鄂尔泰等董其事；鄂尔泰引咎请削伯爵并获允。
  - SourcePassage：`SP-2F859BA3FA47D540E906`

#### SourcePassage 原文与上下文

<details><summary><code>SP-2F859BA3FA47D540E906</code> · eertai-liezhuan:3287-3413</summary>

上文：

> 召拜保和殿大學士，兼兵部尚書，辦理軍機事務。敘定苗疆功，部議進世職一等精奇尼哈番，上特命授一等伯爵，世襲。
> 師討準噶爾，六月，命鄂爾泰督巡陝、甘，經略軍務。九月，師破敵額爾德尼昭，鄂爾泰檄大將軍張廣泗遣兵截袞塔馬哈戈壁，斷敵北遁道。尋疏請屯田。十一年六月，還京師。入對，言準部未可驟滅，用兵久，敝中國，無益，上頗然之。

原文：

> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾，焚掠黃平、施秉諸地。鄂爾泰以從前佈置未協，引咎請罷斥，並削去伯爵。上曰：「國家錫命之恩，有功則受，無功則辭，古今通義。」允其請，予休沐，仍食俸。

下文：

> 尋命留三等阿思哈尼哈番。
> 八月，世宗疾大漸，鄂爾泰仍以大學士與莊親王允祿，果親王允禮，大學士張廷玉，內大臣豐盛額、訥親、海望同被顧命。鄂爾泰與廷玉捧御筆密詔，命高宗為皇太子。俄，皇太子傳旨命鄂爾泰等輔政。世宗崩，宣遺詔以鄂爾泰志秉忠貞，才優經濟，命他日配享太廟。高宗即位，命總理事務，進一等精奇尼哈番。乾隆二年十一月，辭

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-94D8BC65FAA7173BA5EC-EVD-29CD6C452724BF518EE6946C@SP-419097E684B9B3520C79`、`K0-A-G26I-A-CLMK-94D8BC65FAA7173BA5EC-EVD-88B313C12398F35097B561FE@SP-419097E684B9B3520C79`、`K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-09E0B242BD6FA098BEDF9561@SP-2F859BA3FA47D540E906`、`K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-6E3AB872C5F44FDEF7DCC87B@SP-2F859BA3FA47D540E906`
- 理由：准噶尔用兵意见与两年后台拱苗事务授权对象和职责不同，证据未显示直接延续。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-94D8BC65FAA7173BA5EC-EVD-29CD6C452724BF518EE6946C@SP-419097E684B9B3520C79`、`K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-09E0B242BD6FA098BEDF9561@SP-2F859BA3FA47D540E906`
- 理由：准噶尔用兵意见与两年后的办理苗疆事务及削爵是不同军务和不同处置，证据未表明前者导致或授权后者。

---

## 8. `RBC-10E0040D8CFE09F2A6E7`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 0, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-3E7EDCD49082BF8AF64C`
- 人物：obj-485798d73c4c10dd
- 角色：["delegate"]
- 行为：授权
- 责任：顾命辅政、皇位继承
- 责任族：`succession_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-8795461FDB493D995C9300AA@SP-0B53FC0B636ACD7FE703`
  - 时间：雍正十三年八月
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰与张廷玉捧御笔密诏，命高宗为皇太子
  - 摘要：雍正十三年，胤禛病重时命鄂尔泰同允禄、允礼、张廷玉等受顾命，并由鄂尔泰与张廷玉捧御笔密诏立弘历为皇太子。
  - SourcePassage：`SP-0B53FC0B636ACD7FE703`
- `K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-BAE794A278FD0C6055D5BFE0@SP-0B53FC0B636ACD7FE703`
  - 时间：雍正十三年八月
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰与张廷玉捧御笔密诏，命高宗为皇太子
  - 摘要：雍正十三年，胤禛病重时命鄂尔泰同允禄、允礼、张廷玉等受顾命，并由鄂尔泰与张廷玉捧御笔密诏立弘历为皇太子。
  - SourcePassage：`SP-0B53FC0B636ACD7FE703`

#### SourcePassage 原文与上下文

<details><summary><code>SP-0B53FC0B636ACD7FE703</code> · eertai-liezhuan:3426-3500</summary>

上文：

> 可驟滅，用兵久，敝中國，無益，上頗然之。
> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾，焚掠黃平、施秉諸地。鄂爾泰以從前佈置未協，引咎請罷斥，並削去伯爵。上曰：「國家錫命之恩，有功則受，無功則辭，古今通義。」允其請，予休沐，仍食俸。尋命留三等阿思哈尼哈番。

原文：

> 八月，世宗疾大漸，鄂爾泰仍以大學士與莊親王允祿，果親王允禮，大學士張廷玉，內大臣豐盛額、訥親、海望同被顧命。鄂爾泰與廷玉捧御筆密詔，命高宗為皇太子。

下文：

> 俄，皇太子傳旨命鄂爾泰等輔政。世宗崩，宣遺詔以鄂爾泰志秉忠貞，才優經濟，命他日配享太廟。高宗即位，命總理事務，進一等精奇尼哈番。乾隆二年十一月，辭總理事務，授軍機大臣；又辭兼管兵部，上不許，加拜他喇布勒哈番，合為三等伯，賜號襄勤。迭主會試，充領侍衛內大臣、議政大臣、經筵講官。
> 四年，南河河道總督高斌請開新運口，河東河道

</details>

### 右端内容

- Episode：`EP-DF8029963C16AC87A745`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "advisor", "commander", "delegate"]
- 行为：授权
- 责任：办理苗疆事务处
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-09E0B242BD6FA098BEDF9561@SP-2F859BA3FA47D540E906`
  - 时间：雍正十三年
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰引咎请罢斥并削去伯爵，上允其请，仍食俸
  - 摘要：雍正十三年台拱苗复叛后，胤禛设办理苗疆事务处，命鄂尔泰等董其事；鄂尔泰引咎请削伯爵并获允。
  - SourcePassage：`SP-2F859BA3FA47D540E906`
- `K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-6E3AB872C5F44FDEF7DCC87B@SP-2F859BA3FA47D540E906`
  - 时间：雍正十三年
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰引咎请罢斥并削去伯爵，上允其请，仍食俸
  - 摘要：雍正十三年台拱苗复叛后，胤禛设办理苗疆事务处，命鄂尔泰等董其事；鄂尔泰引咎请削伯爵并获允。
  - SourcePassage：`SP-2F859BA3FA47D540E906`

#### SourcePassage 原文与上下文

<details><summary><code>SP-2F859BA3FA47D540E906</code> · eertai-liezhuan:3287-3413</summary>

上文：

> 召拜保和殿大學士，兼兵部尚書，辦理軍機事務。敘定苗疆功，部議進世職一等精奇尼哈番，上特命授一等伯爵，世襲。
> 師討準噶爾，六月，命鄂爾泰督巡陝、甘，經略軍務。九月，師破敵額爾德尼昭，鄂爾泰檄大將軍張廣泗遣兵截袞塔馬哈戈壁，斷敵北遁道。尋疏請屯田。十一年六月，還京師。入對，言準部未可驟滅，用兵久，敝中國，無益，上頗然之。

原文：

> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾，焚掠黃平、施秉諸地。鄂爾泰以從前佈置未協，引咎請罷斥，並削去伯爵。上曰：「國家錫命之恩，有功則受，無功則辭，古今通義。」允其請，予休沐，仍食俸。

下文：

> 尋命留三等阿思哈尼哈番。
> 八月，世宗疾大漸，鄂爾泰仍以大學士與莊親王允祿，果親王允禮，大學士張廷玉，內大臣豐盛額、訥親、海望同被顧命。鄂爾泰與廷玉捧御筆密詔，命高宗為皇太子。俄，皇太子傳旨命鄂爾泰等輔政。世宗崩，宣遺詔以鄂爾泰志秉忠貞，才優經濟，命他日配享太廟。高宗即位，命總理事務，進一等精奇尼哈番。乾隆二年十一月，辭

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-8795461FDB493D995C9300AA@SP-0B53FC0B636ACD7FE703`、`K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-BAE794A278FD0C6055D5BFE0@SP-0B53FC0B636ACD7FE703`、`K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-09E0B242BD6FA098BEDF9561@SP-2F859BA3FA47D540E906`、`K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-6E3AB872C5F44FDEF7DCC87B@SP-2F859BA3FA47D540E906`
- 理由：办理苗疆事务与临终顾命、奉诏立储虽同年且同涉鄂尔泰，但为彼此独立的授权事项。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-4EBA934295D654CA6992-EVD-8795461FDB493D995C9300AA@SP-0B53FC0B636ACD7FE703`、`K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-09E0B242BD6FA098BEDF9561@SP-2F859BA3FA47D540E906`
- 理由：同年发生的顾命立储和办理苗疆事务分别属于继承与军事治理，端点没有相互授权、结果或因果表述。

---

## 9. `RBC-11A3281AFAD990318E0A`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 7, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-2925036C0C00A20C391F`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "office_holder"]
- 行为：任命
- 责任：江苏布政使
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-390495B19DE153FFE920A9C3@SP-9E10DC378003B7EE70B0`
  - 时间：雍正元年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：特擢江苏布政使
  - 摘要：雍正元年，胤禛特擢鄂尔泰为江苏布政使。
  - SourcePassage：`SP-9E10DC378003B7EE70B0`
- `K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-9CDB502178A1BC5A34CD7653@SP-9E10DC378003B7EE70B0`
  - 时间：雍正元年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：特擢江苏布政使
  - 摘要：雍正元年，胤禛特擢鄂尔泰为江苏布政使。
  - SourcePassage：`SP-9E10DC378003B7EE70B0`

#### SourcePassage 原文与上下文

<details><summary><code>SP-9E10DC378003B7EE70B0</code> · eertai-liezhuan:233-254</summary>

上文：

> 初有屯泰者，以七村附太祖，授牛錄額真。子圖捫，事太宗，從戰大凌河，擊明將張理，陣沒，授備禦世職。雍正初，祀昭忠祠。
> 鄂爾泰，其曾孫也。康熙三十八年舉人。四十二年，襲佐領，授三等侍衛。從聖祖獵，和詩稱旨。五十五年，遷內務府員外郎。世宗在籓邸，偶有所囑，鄂爾泰拒之。世宗即位，召曰：「汝為郎官拒皇子，其執法甚堅。」深慰諭之。

原文：

> 雍正元年，充雲南鄉試考官，特擢江蘇布政使。

下文：

> 於廨中建春風亭，禮致能文士，錄其詩文為南邦黎獻集。以應得公使銀買穀三萬三千四百石有奇，分貯蘇、松、常三府備賑貸。察太湖水利，擬疏下游吳淞、白茆，役未舉。
> 三年，遷廣西巡撫，甫上官，調雲南，以巡撫治總督事。貴州仲家苗為亂二十餘年，巡撫石禮哈、提督馬會伯請用兵，上未即許。巡撫何世璂疏言仲家苗藥箭銛利，地勢險阻，用兵不易，上

</details>

### 右端内容

- Episode：`EP-EDBD18D4AE9B0C49DF66`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "advisor", "commander", "delegate"]
- 行为：战役
- 责任：云贵苗疆军事镇压
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-AA64BE7F12BB57849E3A-EVD-E55AD6457C56EDB9DD73E662@SP-9721780954F823624E19`
  - 时间：雍正八年六月后
  - 命题：鄂尔泰 / 战役 / 乌蒙及东川响应诸寨
  - 结果：苗疆复定；上奖鄂尔泰及诸将，发帑犒师
  - 摘要：乌蒙陷落后，鄂尔泰集官兵分三路进攻，并檄张耀祖分道穷搜屠杀，苗疆复定。
  - SourcePassage：`SP-9721780954F823624E19`
- `K0-A-G26I-A-CLMK-AA64BE7F12BB57849E3A-EVD-FEE02B5E12F3A4F642E47FEE@SP-9721780954F823624E19`
  - 时间：雍正八年六月后
  - 命题：鄂尔泰 / 战役 / 乌蒙及东川响应诸寨
  - 结果：苗疆复定；上奖鄂尔泰及诸将，发帑犒师
  - 摘要：乌蒙陷落后，鄂尔泰集官兵分三路进攻，并檄张耀祖分道穷搜屠杀，苗疆复定。
  - SourcePassage：`SP-9721780954F823624E19`

#### SourcePassage 原文与上下文

<details><summary><code>SP-9721780954F823624E19</code> · eertai-liezhuan:2637-2941</summary>

上文：

> 聞，請罷斥，上慰諭之。烏蒙既陷，江外涼山、下方、阿驢，江內巧家營、者家海諸寨及東川祿氏諸土目皆起而應之，又令則補、以址諸寨要截江路，以則、以擢諸寨窺伺城邑，東川境內挖泥、矣氏、歹補、阿汪諸寨，東川境外急羅箐、施魯、古牛、畢古諸寨，及武定、尋甸、威寧、鎮雄所屬諸夷，遠近響應，殺塘兵，劫糧運，堵要隘，毀橋樑，所在屯聚為亂。

原文：

> 鄂爾泰集官兵萬數千人，土兵半之，分三路進攻：令總兵魏翥國攻東川；哈元生攻威寧，副將徐成貞副之；參將韓勳攻鎮雄。翥國師行，土目祿鼎明遣行刺，被創，以總兵官祿代將。師進，焚苗寨十三。遣游擊何元攻急羅箐，殺三百餘，降一百三十餘。游擊紀龍攻者家海，破寨，盡殲其眾。勳與苗兵遇於莫都，戰一晝夜，破寨四，殺數百人。進攻奎鄉，戰三日，殺二千餘。元生、成貞自威寧攻烏蒙，射殺其渠黑寡、暮末，連破寨八十餘，擊敗其眾數万，遂克烏蒙。鄂爾泰檄提督張耀祖督諸軍分道窮搜屠殺，刳腸截脰，分懸崖樹間，群苗讋栗。上獎鄂爾泰及諸將，以元生、成貞、勳為功首，發帑犒師。隴慶侯庶母二祿氏、四川沙馬土婦沙氏以不從亂，給誥命，賚銀幣。於是苗疆复定。

下文：

> 鄂爾泰令於雲、貴界上築橋，命曰庚戌橋，以年紀其績也。
> 是歲，永昌邊外孟連土司請歲納廠課六百，鶴慶邊外皦子請歲貢土物，鄂爾泰疏聞。上以邊外野夷向化，命減孟連廠課之半。皦子入貢，犒以鹽三百斤。九年，疏請重定烏蒙、鎮遠、東川、威寧營汛。別疏請興雲南水利，濬嵩明州楊林海，開墾周圍草塘，疏宜良、尋甸諸水，耕東川城北漫海，築浪穹羽

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-390495B19DE153FFE920A9C3@SP-9E10DC378003B7EE70B0`、`K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-9CDB502178A1BC5A34CD7653@SP-9E10DC378003B7EE70B0`、`K0-A-G26I-A-CLMK-AA64BE7F12BB57849E3A-EVD-E55AD6457C56EDB9DD73E662@SP-9721780954F823624E19`、`K0-A-G26I-A-CLMK-AA64BE7F12BB57849E3A-EVD-FEE02B5E12F3A4F642E47FEE@SP-9721780954F823624E19`
- 理由：江苏布政使任命与七年后的乌蒙军事行动相隔较远，职责地域不同且无端点证据直接连接。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-2BED082DB8613370A4DC-EVD-390495B19DE153FFE920A9C3@SP-9E10DC378003B7EE70B0`、`K0-A-G26I-A-CLMK-AA64BE7F12BB57849E3A-EVD-E55AD6457C56EDB9DD73E662@SP-9721780954F823624E19`
- 理由：江苏布政使任命与七年后的云贵苗疆镇压相隔较久且职责不同，只有人物相同，证据没有直接承接关系。

---

## 10. `RBC-12ECA510C1F1D7D215FD`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 3, "value": "obj-485798d73c4c10dd", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`authority_change`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-B0A50E55335DF389C0A6`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "office_holder"]
- 行为：任命
- 责任：保和殿大学士、兵部尚书、军机事务
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-3E4BF7BCFAD0F79EB24D27E5@SP-77CE39608B951673AAE2`
  - 时间：雍正十年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：授一等伯爵，世袭
  - 摘要：雍正十年，胤禛召鄂尔泰拜保和殿大学士兼兵部尚书，并办理军机事务；又因定苗疆功授一等伯爵世袭。
  - SourcePassage：`SP-77CE39608B951673AAE2`
- `K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-90899060763733DC3B193C3B@SP-77CE39608B951673AAE2`
  - 时间：雍正十年
  - 命题：胤禛 / 任命 / 鄂尔泰
  - 结果：授一等伯爵，世袭
  - 摘要：雍正十年，胤禛召鄂尔泰拜保和殿大学士兼兵部尚书，并办理军机事务；又因定苗疆功授一等伯爵世袭。
  - SourcePassage：`SP-77CE39608B951673AAE2`

#### SourcePassage 原文与上下文

<details><summary><code>SP-77CE39608B951673AAE2</code> · eertai-liezhuan:3124-3180</summary>

上文：

> 績也。
> 是歲，永昌邊外孟連土司請歲納廠課六百，鶴慶邊外皦子請歲貢土物，鄂爾泰疏聞。上以邊外野夷向化，命減孟連廠課之半。皦子入貢，犒以鹽三百斤。九年，疏請重定烏蒙、鎮遠、東川、威寧營汛。別疏請興雲南水利，濬嵩明州楊林海，開墾周圍草塘，疏宜良、尋甸諸水，耕東川城北漫海，築浪穹羽河諸堤，修臨安諸處工，暨通粵河道，皆下部議行。

原文：

> 十年，召拜保和殿大學士，兼兵部尚書，辦理軍機事務。敘定苗疆功，部議進世職一等精奇尼哈番，上特命授一等伯爵，世襲。

下文：

> 師討準噶爾，六月，命鄂爾泰督巡陝、甘，經略軍務。九月，師破敵額爾德尼昭，鄂爾泰檄大將軍張廣泗遣兵截袞塔馬哈戈壁，斷敵北遁道。尋疏請屯田。十一年六月，還京師。入對，言準部未可驟滅，用兵久，敝中國，無益，上頗然之。
> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾

</details>

### 右端内容

- Episode：`EP-DF8029963C16AC87A745`
- 人物：obj-485798d73c4c10dd
- 角色：["actor", "advisor", "commander", "delegate"]
- 行为：授权
- 责任：办理苗疆事务处
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-09E0B242BD6FA098BEDF9561@SP-2F859BA3FA47D540E906`
  - 时间：雍正十三年
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰引咎请罢斥并削去伯爵，上允其请，仍食俸
  - 摘要：雍正十三年台拱苗复叛后，胤禛设办理苗疆事务处，命鄂尔泰等董其事；鄂尔泰引咎请削伯爵并获允。
  - SourcePassage：`SP-2F859BA3FA47D540E906`
- `K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-6E3AB872C5F44FDEF7DCC87B@SP-2F859BA3FA47D540E906`
  - 时间：雍正十三年
  - 命题：胤禛 / 授权 / 鄂尔泰
  - 结果：鄂尔泰引咎请罢斥并削去伯爵，上允其请，仍食俸
  - 摘要：雍正十三年台拱苗复叛后，胤禛设办理苗疆事务处，命鄂尔泰等董其事；鄂尔泰引咎请削伯爵并获允。
  - SourcePassage：`SP-2F859BA3FA47D540E906`

#### SourcePassage 原文与上下文

<details><summary><code>SP-2F859BA3FA47D540E906</code> · eertai-liezhuan:3287-3413</summary>

上文：

> 召拜保和殿大學士，兼兵部尚書，辦理軍機事務。敘定苗疆功，部議進世職一等精奇尼哈番，上特命授一等伯爵，世襲。
> 師討準噶爾，六月，命鄂爾泰督巡陝、甘，經略軍務。九月，師破敵額爾德尼昭，鄂爾泰檄大將軍張廣泗遣兵截袞塔馬哈戈壁，斷敵北遁道。尋疏請屯田。十一年六月，還京師。入對，言準部未可驟滅，用兵久，敝中國，無益，上頗然之。

原文：

> 十三年，台拱苗复叛。上命設辦理苗疆事務處，以果親王、寶親王、和親王、鄂爾泰及大學士張廷玉等董其事。苗患日熾，焚掠黃平、施秉諸地。鄂爾泰以從前佈置未協，引咎請罷斥，並削去伯爵。上曰：「國家錫命之恩，有功則受，無功則辭，古今通義。」允其請，予休沐，仍食俸。

下文：

> 尋命留三等阿思哈尼哈番。
> 八月，世宗疾大漸，鄂爾泰仍以大學士與莊親王允祿，果親王允禮，大學士張廷玉，內大臣豐盛額、訥親、海望同被顧命。鄂爾泰與廷玉捧御筆密詔，命高宗為皇太子。俄，皇太子傳旨命鄂爾泰等輔政。世宗崩，宣遺詔以鄂爾泰志秉忠貞，才優經濟，命他日配享太廟。高宗即位，命總理事務，進一等精奇尼哈番。乾隆二年十一月，辭

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-3E4BF7BCFAD0F79EB24D27E5@SP-77CE39608B951673AAE2`、`K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-90899060763733DC3B193C3B@SP-77CE39608B951673AAE2`、`K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-09E0B242BD6FA098BEDF9561@SP-2F859BA3FA47D540E906`、`K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-6E3AB872C5F44FDEF7DCC87B@SP-2F859BA3FA47D540E906`
- 理由：鄂尔泰任大学士、兵部尚书并办军机后，又获办理苗疆事务授权，随后引咎获准削爵，构成明确扩权与撤权。

#### Reviewer B

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-C2B14640011A2746FDFE-EVD-3E4BF7BCFAD0F79EB24D27E5@SP-77CE39608B951673AAE2`、`K0-A-G26I-A-CLMK-FE95C5E0C0517AE0156B-EVD-09E0B242BD6FA098BEDF9561@SP-2F859BA3FA47D540E906`
- 理由：左端因苗疆功明确授鄂尔泰一等伯爵，右端因苗患与既往布置失当明确削去同一伯爵，构成爵位授予与撤销。

---

## 11. `RBC-154FE15C7084DDAC7047`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 6, "value": "隆科多"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 1, "value": "per-d7a0d148728a2905", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`authority_change`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-CE7668BC67364F6BCCB3`
- 人物：per-d7a0d148728a2905
- 角色：["actor"]
- 行为：处置
- 责任：尚书、阿尔泰边疆事务、俄罗斯边界
- 责任族：`border_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-81CD2E176E38EB56311A-EVD-29D21D7620B711A03DA7756C@SP-0D74002E50F358BA914A`
  - 时间：雍正四年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被罢尚书，改令料理边疆事务并勘议俄罗斯边界
  - 摘要：雍正四年，因家仆牛伦索贿案牵出隆科多受年羹尧等人贿赂，胤禛罢隆科多尚书，令其料理阿尔泰等路边疆事务，并随后命其勘议俄罗斯边界。
  - SourcePassage：`SP-0D74002E50F358BA914A`
- `K0-A-G26I-A-CLMK-81CD2E176E38EB56311A-EVD-3A45204976EFD0E248F0E1A9@SP-0D74002E50F358BA914A`
  - 时间：雍正四年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被罢尚书，改令料理边疆事务并勘议俄罗斯边界
  - 摘要：雍正四年，因家仆牛伦索贿案牵出隆科多受年羹尧等人贿赂，胤禛罢隆科多尚书，令其料理阿尔泰等路边疆事务，并随后命其勘议俄罗斯边界。
  - SourcePassage：`SP-0D74002E50F358BA914A`

#### SourcePassage 原文与上下文

<details><summary><code>SP-0D74002E50F358BA914A</code> · longkodo-liezhuan:667-757</summary>

上文：

> 處修城墾地，諭曰：「朕御極之初，隆科多、年羹堯皆寄以心腹，毫無猜防。孰知朕視為一德，彼竟有二心，招權納賄，擅作威福，欺罔悖負，朕豈能姑息養奸耶？向日明珠、索額圖結黨行私，聖祖解其要職，置之閒散，何嘗更加信用？隆科多、年羹堯若不知恐懼，痛改前非，欲如明珠等，萬不能也！殊典不可再邀，覆轍不可屢蹈，各宜警懼，毋自乾誅滅。」

原文：

> 四年，隆科多家僕牛倫挾勢索賕，事發，逮下法司，鞫得隆科多受羹堯及總督趙世顯、滿保，巡撫甘國璧、蘇克濟賄。讞上，上命斬倫，罷隆科多尚書，令料理阿爾泰等路邊疆事務。尋命勘議俄羅斯邊界。

下文：

> 初，隆科多與阿靈阿、揆敘相黨附，繼又與羹堯交結。至是，上盡發阿靈阿、揆敘及羹堯罪狀，宣示中外。又侍郎查嗣庭為隆科多所薦，坐悖逆誅死，上詰隆科多，隆科多不以實對。
> 五年，宗人府復奏劾輔國公阿布蘭以玉牒畀隆科多藏於家，阿布蘭坐奪爵幽禁。上命奪隆科多爵，召還京，命王大臣會鞫。以聖祖升遐，隆科多未在上前，妄言身藏匕首以防不測

</details>

### 右端内容

- Episode：`EP-FCFD782087AA082C69FE`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：处置
- 责任：爵位、王大臣会鞫、禁锢
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-81568A4018F0B4BEB88D17DF@SP-D956F21D41DA5C61DA95`
  - 时间：雍正五年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被夺爵、会鞫，免死后永远禁锢
  - 摘要：雍正五年，胤禛命夺隆科多爵并召还京会鞫；议罪当斩后，又因其为圣祖临终唯一承旨大臣而免正法，改为永远禁锢。
  - SourcePassage：`SP-D956F21D41DA5C61DA95`
- `K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-9F548774E29583AB92539DC4@SP-D956F21D41DA5C61DA95`
  - 时间：雍正五年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被夺爵、会鞫，免死后永远禁锢
  - 摘要：雍正五年，胤禛命夺隆科多爵并召还京会鞫；议罪当斩后，又因其为圣祖临终唯一承旨大臣而免正法，改为永远禁锢。
  - SourcePassage：`SP-D956F21D41DA5C61DA95`

#### SourcePassage 原文与上下文

<details><summary><code>SP-D956F21D41DA5C61DA95</code> · longkodo-liezhuan:839-1106</summary>

上文：

> 索賕，事發，逮下法司，鞫得隆科多受羹堯及總督趙世顯、滿保，巡撫甘國璧、蘇克濟賄。讞上，上命斬倫，罷隆科多尚書，令料理阿爾泰等路邊疆事務。尋命勘議俄羅斯邊界。
> 初，隆科多與阿靈阿、揆敘相黨附，繼又與羹堯交結。至是，上盡發阿靈阿、揆敘及羹堯罪狀，宣示中外。又侍郎查嗣庭為隆科多所薦，坐悖逆誅死，上詰隆科多，隆科多不以實對。

原文：

> 五年，宗人府復奏劾輔國公阿布蘭以玉牒畀隆科多藏於家，阿布蘭坐奪爵幽禁。上命奪隆科多爵，召還京，命王大臣會鞫。以聖祖升遐，隆科多未在上前，妄言身藏匕首以防不測；又自擬諸葛亮，奏稱「白帝城受命之日，即死期將至之時」；上躬祀壇廟，妄謂防刺客，令於案下搜查；上謁陵，妄奏「諸王心變」。具獄辭：大不敬之罪五，欺罔之罪四，紊亂朝政之罪三，黨姦之罪六，不法之罪七，貪婪之罪十六，凡四十一款，當斬，妻子入辛者庫，財產入官。上諭曰：「隆科多罪不容誅，但皇考升遐，大臣承旨者惟隆科多一人。今以罪誅，朕心有所不忍，可免其正法，於暢春園外築屋三楹，永遠禁錮；

下文：

> 妻子免入辛者庫，岳興阿奪官，玉柱發黑龍江。」
> 六年六月，隆科多死於禁所，賜金治喪。
>
>
> == 年羹堯 ==
> 年羹堯，字亮工，漢軍鑲黃旗人。父遐齡，自筆帖式授兵部主事，再遷刑部郎中。康熙二十二年，授河南道御史。四遷工部侍郎，出為湖廣巡撫。湖北武昌等七府歲徵匠役班價銀千餘，戶絕額缺，為官民累。遐齡請歸地丁徵收，下部議，從之

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-81CD2E176E38EB56311A-EVD-29D21D7620B711A03DA7756C@SP-0D74002E50F358BA914A`、`K0-A-G26I-A-CLMK-81CD2E176E38EB56311A-EVD-3A45204976EFD0E248F0E1A9@SP-0D74002E50F358BA914A`、`K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-81568A4018F0B4BEB88D17DF@SP-D956F21D41DA5C61DA95`、`K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-9F548774E29583AB92539DC4@SP-D956F21D41DA5C61DA95`
- 理由：隆科多先被罢尚书并外派边务，次年又被夺爵、会鞫和永久禁锢，是连续升级的撤权处置。

#### Reviewer B

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-81CD2E176E38EB56311A-EVD-29D21D7620B711A03DA7756C@SP-0D74002E50F358BA914A`、`K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-81568A4018F0B4BEB88D17DF@SP-D956F21D41DA5C61DA95`
- 理由：隆科多先被罢尚书并改派边疆事务，次年又被夺爵、召回会鞫和永久禁锢，构成连续升级的撤权处置。

---

## 12. `RBC-1B5EF40E8FE602C1C2E7`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 6, "value": "隆科多"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 2, "value": "per-d7a0d148728a2905", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`authority_change`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-24D3B7BF1A6C5FDBC7F4`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：收权
- 责任：赏赐特典
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`
  - 时间：雍正三年
  - 命题：胤禛 / 收权 / 隆科多
  - 结果：隆科多被追缴四团龙补服且不得复用双眼花翎、黄带、紫辔
  - 摘要：雍正三年，胤禛因隆科多与年羹尧交结专擅、诸事欺隐，命其缴还所赐服饰特典并不得复用双眼花翎、黄带、紫辔。
  - SourcePassage：`SP-3C5A229F9056917E5728`
- `K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-847B512654CC803D8249BD47@SP-3C5A229F9056917E5728`
  - 时间：雍正三年
  - 命题：胤禛 / 收权 / 隆科多
  - 结果：隆科多被追缴四团龙补服且不得复用双眼花翎、黄带、紫辔
  - 摘要：雍正三年，胤禛因隆科多与年羹尧交结专擅、诸事欺隐，命其缴还所赐服饰特典并不得复用双眼花翎、黄带、紫辔。
  - SourcePassage：`SP-3C5A229F9056917E5728`

#### SourcePassage 原文与上下文

<details><summary><code>SP-3C5A229F9056917E5728</code> · longkodo-liezhuan:375-438</summary>

上文：

> 。次子玉柱，自侍衛授鑾儀使。
> 雍正元年，與川陝總督年羹堯同加太保。
> 二年，兼領理籓院事。纂修《聖祖實錄》、《大清會典》並充總裁，監修《明史》。復與羹堯同賜雙眼花翎、四團龍補服、黃帶、紫轡。
> 三年，解步軍統領。玉柱以行止甚劣，奪官，交隆科多管束。羹堯得罪，上以都統範時捷疏劾欺罔貪婪諸狀，及妄劾道員金南瑛等，並下吏部議處。

原文：

> 上諭曰：「前以隆科多、年羹堯頗著勤勞，予以異數，乃交結專擅，諸事欺隱。」命繳上所賜四團龍補服，並不得復用雙眼花翎、黃帶、紫轡。

下文：

> 及議上，以時捷劾，請罷羹堯任；以妄劾南瑛，請嚴加治罪。上以前議徇庇，後議復過當，責隆科多有意擾亂，削太保及一等阿達哈哈番世職，命往阿蘭善等處修城墾地，諭曰：「朕御極之初，隆科多、年羹堯皆寄以心腹，毫無猜防。孰知朕視為一德，彼竟有二心，招權納賄，擅作威福，欺罔悖負，朕豈能姑息養奸耶？向日明珠、索額圖結黨行私，聖祖解其要職

</details>

### 右端内容

- Episode：`EP-FCFD782087AA082C69FE`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：处置
- 责任：爵位、王大臣会鞫、禁锢
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-81568A4018F0B4BEB88D17DF@SP-D956F21D41DA5C61DA95`
  - 时间：雍正五年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被夺爵、会鞫，免死后永远禁锢
  - 摘要：雍正五年，胤禛命夺隆科多爵并召还京会鞫；议罪当斩后，又因其为圣祖临终唯一承旨大臣而免正法，改为永远禁锢。
  - SourcePassage：`SP-D956F21D41DA5C61DA95`
- `K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-9F548774E29583AB92539DC4@SP-D956F21D41DA5C61DA95`
  - 时间：雍正五年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被夺爵、会鞫，免死后永远禁锢
  - 摘要：雍正五年，胤禛命夺隆科多爵并召还京会鞫；议罪当斩后，又因其为圣祖临终唯一承旨大臣而免正法，改为永远禁锢。
  - SourcePassage：`SP-D956F21D41DA5C61DA95`

#### SourcePassage 原文与上下文

<details><summary><code>SP-D956F21D41DA5C61DA95</code> · longkodo-liezhuan:839-1106</summary>

上文：

> 索賕，事發，逮下法司，鞫得隆科多受羹堯及總督趙世顯、滿保，巡撫甘國璧、蘇克濟賄。讞上，上命斬倫，罷隆科多尚書，令料理阿爾泰等路邊疆事務。尋命勘議俄羅斯邊界。
> 初，隆科多與阿靈阿、揆敘相黨附，繼又與羹堯交結。至是，上盡發阿靈阿、揆敘及羹堯罪狀，宣示中外。又侍郎查嗣庭為隆科多所薦，坐悖逆誅死，上詰隆科多，隆科多不以實對。

原文：

> 五年，宗人府復奏劾輔國公阿布蘭以玉牒畀隆科多藏於家，阿布蘭坐奪爵幽禁。上命奪隆科多爵，召還京，命王大臣會鞫。以聖祖升遐，隆科多未在上前，妄言身藏匕首以防不測；又自擬諸葛亮，奏稱「白帝城受命之日，即死期將至之時」；上躬祀壇廟，妄謂防刺客，令於案下搜查；上謁陵，妄奏「諸王心變」。具獄辭：大不敬之罪五，欺罔之罪四，紊亂朝政之罪三，黨姦之罪六，不法之罪七，貪婪之罪十六，凡四十一款，當斬，妻子入辛者庫，財產入官。上諭曰：「隆科多罪不容誅，但皇考升遐，大臣承旨者惟隆科多一人。今以罪誅，朕心有所不忍，可免其正法，於暢春園外築屋三楹，永遠禁錮；

下文：

> 妻子免入辛者庫，岳興阿奪官，玉柱發黑龍江。」
> 六年六月，隆科多死於禁所，賜金治喪。
>
>
> == 年羹堯 ==
> 年羹堯，字亮工，漢軍鑲黃旗人。父遐齡，自筆帖式授兵部主事，再遷刑部郎中。康熙二十二年，授河南道御史。四遷工部侍郎，出為湖廣巡撫。湖北武昌等七府歲徵匠役班價銀千餘，戶絕額缺，為官民累。遐齡請歸地丁徵收，下部議，從之

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-847B512654CC803D8249BD47@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-81568A4018F0B4BEB88D17DF@SP-D956F21D41DA5C61DA95`、`K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-9F548774E29583AB92539DC4@SP-D956F21D41DA5C61DA95`
- 理由：先收回隆科多服饰与特典，后进一步夺爵并永久禁锢，属于同一失势链中的连续撤权。

#### Reviewer B

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-81568A4018F0B4BEB88D17DF@SP-D956F21D41DA5C61DA95`
- 理由：隆科多先被收回服饰特典，后又被夺爵并禁锢，是对同一人的连续身份降等与撤权。

---

## 13. `RBC-1E561EF33BD82D2DBC5E`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 6, "value": "隆科多"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 3, "value": "per-d7a0d148728a2905", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`authority_change`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-BF7A3052DFD70BFD1863`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：任命
- 责任：理籓院、史书会典修纂
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`
  - 时间：雍正二年
  - 命题：胤禛 / 任命 / 隆科多
  - 结果：隆科多兼领理籓院事并充总裁、监修
  - 摘要：雍正二年，胤禛令隆科多兼领理籓院事，并在《圣祖实录》《大清会典》《明史》修纂中任总裁、监修。
  - SourcePassage：`SP-6E9C3B8CE114F78DACB8`
- `K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-F9D274993EFEAF194A59D615@SP-6E9C3B8CE114F78DACB8`
  - 时间：雍正二年
  - 命题：胤禛 / 任命 / 隆科多
  - 结果：隆科多兼领理籓院事并充总裁、监修
  - 摘要：雍正二年，胤禛令隆科多兼领理籓院事，并在《圣祖实录》《大清会典》《明史》修纂中任总裁、监修。
  - SourcePassage：`SP-6E9C3B8CE114F78DACB8`

#### SourcePassage 原文与上下文

<details><summary><code>SP-6E9C3B8CE114F78DACB8</code> · longkodo-liezhuan:249-286</summary>

上文：

> 實心任事，罷副都統、鑾儀使，在一等侍衛上行走。
> 五十年，授步軍統領。
> 五十九年，擢理籓院尚書，仍管步軍統領。
> 六十一年十一月，聖祖大漸，召受顧命。世宗即位，命與大學士馬齊總理事務，襲一等公，授吏部尚書。旋以總理事務勞，加一等阿達哈哈番，以其長子岳興阿襲。次子玉柱，自侍衛授鑾儀使。
> 雍正元年，與川陝總督年羹堯同加太保。

原文：

> 二年，兼領理籓院事。纂修《聖祖實錄》、《大清會典》並充總裁，監修《明史》。

下文：

> 復與羹堯同賜雙眼花翎、四團龍補服、黃帶、紫轡。
> 三年，解步軍統領。玉柱以行止甚劣，奪官，交隆科多管束。羹堯得罪，上以都統範時捷疏劾欺罔貪婪諸狀，及妄劾道員金南瑛等，並下吏部議處。上諭曰：「前以隆科多、年羹堯頗著勤勞，予以異數，乃交結專擅，諸事欺隱。」命繳上所賜四團龍補服，並不得復用雙眼花翎、黃帶、紫轡。及議上，以時捷劾

</details>

### 右端内容

- Episode：`EP-FCFD782087AA082C69FE`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：处置
- 责任：爵位、王大臣会鞫、禁锢
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-81568A4018F0B4BEB88D17DF@SP-D956F21D41DA5C61DA95`
  - 时间：雍正五年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被夺爵、会鞫，免死后永远禁锢
  - 摘要：雍正五年，胤禛命夺隆科多爵并召还京会鞫；议罪当斩后，又因其为圣祖临终唯一承旨大臣而免正法，改为永远禁锢。
  - SourcePassage：`SP-D956F21D41DA5C61DA95`
- `K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-9F548774E29583AB92539DC4@SP-D956F21D41DA5C61DA95`
  - 时间：雍正五年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被夺爵、会鞫，免死后永远禁锢
  - 摘要：雍正五年，胤禛命夺隆科多爵并召还京会鞫；议罪当斩后，又因其为圣祖临终唯一承旨大臣而免正法，改为永远禁锢。
  - SourcePassage：`SP-D956F21D41DA5C61DA95`

#### SourcePassage 原文与上下文

<details><summary><code>SP-D956F21D41DA5C61DA95</code> · longkodo-liezhuan:839-1106</summary>

上文：

> 索賕，事發，逮下法司，鞫得隆科多受羹堯及總督趙世顯、滿保，巡撫甘國璧、蘇克濟賄。讞上，上命斬倫，罷隆科多尚書，令料理阿爾泰等路邊疆事務。尋命勘議俄羅斯邊界。
> 初，隆科多與阿靈阿、揆敘相黨附，繼又與羹堯交結。至是，上盡發阿靈阿、揆敘及羹堯罪狀，宣示中外。又侍郎查嗣庭為隆科多所薦，坐悖逆誅死，上詰隆科多，隆科多不以實對。

原文：

> 五年，宗人府復奏劾輔國公阿布蘭以玉牒畀隆科多藏於家，阿布蘭坐奪爵幽禁。上命奪隆科多爵，召還京，命王大臣會鞫。以聖祖升遐，隆科多未在上前，妄言身藏匕首以防不測；又自擬諸葛亮，奏稱「白帝城受命之日，即死期將至之時」；上躬祀壇廟，妄謂防刺客，令於案下搜查；上謁陵，妄奏「諸王心變」。具獄辭：大不敬之罪五，欺罔之罪四，紊亂朝政之罪三，黨姦之罪六，不法之罪七，貪婪之罪十六，凡四十一款，當斬，妻子入辛者庫，財產入官。上諭曰：「隆科多罪不容誅，但皇考升遐，大臣承旨者惟隆科多一人。今以罪誅，朕心有所不忍，可免其正法，於暢春園外築屋三楹，永遠禁錮；

下文：

> 妻子免入辛者庫，岳興阿奪官，玉柱發黑龍江。」
> 六年六月，隆科多死於禁所，賜金治喪。
>
>
> == 年羹堯 ==
> 年羹堯，字亮工，漢軍鑲黃旗人。父遐齡，自筆帖式授兵部主事，再遷刑部郎中。康熙二十二年，授河南道御史。四遷工部侍郎，出為湖廣巡撫。湖北武昌等七府歲徵匠役班價銀千餘，戶絕額缺，為官民累。遐齡請歸地丁徵收，下部議，從之

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`、`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-F9D274993EFEAF194A59D615@SP-6E9C3B8CE114F78DACB8`、`K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-81568A4018F0B4BEB88D17DF@SP-D956F21D41DA5C61DA95`、`K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-9F548774E29583AB92539DC4@SP-D956F21D41DA5C61DA95`
- 理由：隆科多先获兼领理籓院及史书监修等职，后被夺爵会鞫并永久禁锢，构成授职后的明确撤权。

#### Reviewer B

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`、`K0-A-G26I-A-CLMK-D7FDB211437EE2C21569-EVD-81568A4018F0B4BEB88D17DF@SP-D956F21D41DA5C61DA95`
- 理由：左端明确增授隆科多理籓院及修史职权，右端其后夺爵、会鞫并禁锢，构成从授职到全面撤权的权力变化链。

---

## 14. `RBC-4B73B6AEC07EC188A1A1`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 4, "value": "陈平"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 1, "value": "obj-2b89622cefdec6e3|obj-a4785b7cc76ec776", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-4023C698252711CF1EAE`
- 人物：obj-2b89622cefdec6e3|obj-a4785b7cc76ec776
- 角色：["actor", "advisor", "office_holder"]
- 行为：荐举
- 责任：皇位继承
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-F03D58B34DB5A14317F1C5AA@SP-A5E7130D5F5040D99405`
  - 时间：高后八年后九月
  - 命题：陈平 / 荐举 / 代王
  - 结果：代王遂即天子位
  - 摘要：诛灭诸吕后，陈平等大臣迎立代王，陈平再拜称少帝等不当奉宗庙，请代王即天子位。
  - SourcePassage：`SP-A5E7130D5F5040D99405`
- `K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-FB7DEEBBAB75C44003CAD89F@SP-A5E7130D5F5040D99405`
  - 时间：高后八年后九月
  - 命题：陈平 / 荐举 / 代王
  - 结果：代王遂即天子位
  - 摘要：诛灭诸吕后，陈平等大臣迎立代王，陈平再拜称少帝等不当奉宗庙，请代王即天子位。
  - SourcePassage：`SP-A5E7130D5F5040D99405`

#### SourcePassage 原文与上下文

<details><summary><code>SP-A5E7130D5F5040D99405</code> · xiaowen-benji:976-1076</summary>

上文：

> 侯劉章、東牟侯劉興居、典客劉揭皆再拜言曰：「子弘等皆非孝惠帝子，不當奉宗廟。臣謹請（與）陰安侯列侯頃王后與瑯邪王、宗室、大臣、列侯、吏二千石議曰：『大王高帝長子，宜為高帝嗣。』願大王即天子位。」代王曰：「奉高帝宗廟，重事也。寡人不佞，不足以稱宗廟。願請楚王計宜者，寡人不敢當。」群臣皆伏固請。代王西鄉讓者三，南鄉讓者再。

原文：

> 丞相平等皆曰：「臣伏計之，大王奉高帝宗廟最宜稱，雖天下諸侯萬民以為宜。臣等為宗廟社稷計，不敢忽。願大王幸聽臣等。臣謹奉天子璽符再拜上。」代王曰：「宗室將相王列侯以為莫宜寡人，寡人不敢辭。」遂即天子位。

下文：

> 群臣以禮次侍。乃使太仆嬰與東牟侯興居清宮，奉天子法駕，迎于代邸。皇帝即日夕入未央宮。乃夜拜宋昌為衛將軍，鎮撫南北軍。以張武為郎中令，行殿中。還坐前殿。於是夜下詔書曰：「閒者諸呂用事擅權，謀為大逆，欲以危劉氏宗廟，賴將相列侯宗室大臣誅之，皆伏其辜。朕初即位，其赦天下，賜民爵一級，女子百戶牛酒，酺五日。」
> 孝文皇帝元年十

</details>

### 右端内容

- Episode：`EP-A8F03FDCD5BDC2FB7D75`
- 人物：obj-2b89622cefdec6e3|obj-a4785b7cc76ec776
- 角色：["actor", "advisor", "office_holder"]
- 行为：其他 | 纳谏
- 责任：宰相职责
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-8EF14805CF9E647500C6-EVD-1CE16ADA6A5B9EAF4F39A4C6@SP-734B5B5985637BC2C4B5`
  - 时间：孝文帝明习国家事后朝问丞相时
  - 命题：陈平 / 纳谏 / 刘恒
  - 结果：刘恒称善；周勃自知不如陈平，后陈平专为丞相
  - 摘要：刘恒问丞相职责时，陈平答以宰相应佐天子、理四时、镇抚四夷诸侯、亲附百姓并使百官任职，刘恒称善。
  - SourcePassage：`SP-734B5B5985637BC2C4B5`
- `K0-A-G26I-A-CLMK-8EF14805CF9E647500C6-EVD-BE4627850764C8564825855D@SP-734B5B5985637BC2C4B5`
  - 时间：孝文帝明习国家事后朝问丞相时
  - 命题：陈平 / 纳谏 / 刘恒
  - 结果：刘恒称善；周勃自知不如陈平，后陈平专为丞相
  - 摘要：刘恒问丞相职责时，陈平答以宰相应佐天子、理四时、镇抚四夷诸侯、亲附百姓并使百官任职，刘恒称善。
  - SourcePassage：`SP-734B5B5985637BC2C4B5`
- `K0-A-G26I-A-CLMK-8EF14805CF9E647500C6-EVD-D98F205069259F1DF7AEB636@SP-734B5B5985637BC2C4B5`
  - 时间：孝文帝明习国家事后朝问丞相时
  - 命题：陈平 / 纳谏 / 刘恒
  - 结果：刘恒称善；周勃自知不如陈平，后陈平专为丞相
  - 摘要：刘恒问丞相职责时，陈平答以宰相应佐天子、理四时、镇抚四夷诸侯、亲附百姓并使百官任职，刘恒称善。
  - SourcePassage：`SP-734B5B5985637BC2C4B5`
- `K0-A-G26I-A-CLMK-DF4485DA54A8BA2C0F69-EVD-B0B5F696F92FBDE194009D31@SP-734B5B5985637BC2C4B5`
  - 时间：文帝前元年
  - 命题：陈平 / 其他 / 文帝
  - 结果：帝乃称善，周勃自知不如陈平
  - 摘要：文帝询问宰相职责时，陈平说明宰相上佐天子、下遂万物、外镇诸侯四夷、内亲百姓，得到文帝称善。
  - SourcePassage：`SP-734B5B5985637BC2C4B5`
- `K0-A-G26I-A-CLMK-DF4485DA54A8BA2C0F69-EVD-D1E269C28775AB9BED464771@SP-734B5B5985637BC2C4B5`
  - 时间：文帝前元年
  - 命题：陈平 / 其他 / 文帝
  - 结果：帝乃称善，周勃自知不如陈平
  - 摘要：文帝询问宰相职责时，陈平说明宰相上佐天子、下遂万物、外镇诸侯四夷、内亲百姓，得到文帝称善。
  - SourcePassage：`SP-734B5B5985637BC2C4B5`

#### SourcePassage 原文与上下文

<details><summary><code>SP-734B5B5985637BC2C4B5</code> · chen-chengxiang-shijia:3757-3986</summary>

上文：

> 崩，平與太尉勃合謀，卒誅諸呂，立孝文皇帝，陳平本謀也。審食其免相。
> 孝文帝立，以爲太尉勃親以兵誅呂氏，功多；陳平欲讓勃尊位，乃謝病。孝文帝初立，怪平病，問之。平曰：「高祖時，勃功不如臣平。及誅諸呂，臣功亦不如勃。願以右丞相讓勃。」於是孝文帝乃以絳侯勃爲右丞相，位次第一；平徙爲左丞相，位次第二。賜平金千斤，益封三千戸。

原文：

> 居頃之，孝文皇帝既益明習國家事，朝而問右丞相勃曰：「天下一歳決獄幾何？」勃謝曰：「不知。」問：「天下一歳錢穀出入幾何？」勃又謝不知，汗出沾背，愧不能對。於是上亦問左丞相平。平曰：「有主者。」上曰：「主者謂誰？」平曰：「陛下即問決獄，責廷尉；問錢穀，責治粟內史。」上曰：「苟各有主者，而君所主者何事也？」平謝曰：「主臣！陛下不知其駑下，使待罪宰相。宰相者，上佐天子理陰陽，順四時，下育萬物之宜，外鎮撫四夷諸侯，內親附百姓，使卿大夫各得任其職焉。」孝文帝乃稱善。

下文：

> 右丞相大慚，出而讓陳平曰：「君獨不素教我對！」陳平笑曰：「君居其位，不知其任邪？且陛下即問長安中盜賊數，君欲彊對邪？」於是絳侯自知其能不如平遠矣。居頃之，絳侯謝病請免相，陳平專爲一丞相。
> 孝文帝二年，丞相陳平卒，諡爲獻侯。子共侯買代侯。二年卒，子簡侯恢代侯。二十三年卒，子何代侯。二十三年，何坐略人妻，棄市，國除。
> 始陳

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-F03D58B34DB5A14317F1C5AA@SP-A5E7130D5F5040D99405`、`K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-FB7DEEBBAB75C44003CAD89F@SP-A5E7130D5F5040D99405`、`K0-A-G26I-A-CLMK-8EF14805CF9E647500C6-EVD-1CE16ADA6A5B9EAF4F39A4C6@SP-734B5B5985637BC2C4B5`、`K0-A-G26I-A-CLMK-8EF14805CF9E647500C6-EVD-BE4627850764C8564825855D@SP-734B5B5985637BC2C4B5`、`K0-A-G26I-A-CLMK-8EF14805CF9E647500C6-EVD-D98F205069259F1DF7AEB636@SP-734B5B5985637BC2C4B5`、`K0-A-G26I-A-CLMK-DF4485DA54A8BA2C0F69-EVD-B0B5F696F92FBDE194009D31@SP-734B5B5985637BC2C4B5`、`K0-A-G26I-A-CLMK-DF4485DA54A8BA2C0F69-EVD-D1E269C28775AB9BED464771@SP-734B5B5985637BC2C4B5`
- 理由：迎立刘恒与其后来询问丞相职责虽共享君臣人物，但问答并非迎立事件的直接授权、结果或因果后件。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-F03D58B34DB5A14317F1C5AA@SP-A5E7130D5F5040D99405`、`K0-A-G26I-A-CLMK-8EF14805CF9E647500C6-EVD-1CE16ADA6A5B9EAF4F39A4C6@SP-734B5B5985637BC2C4B5`
- 理由：迎立代王与其后陈平回答宰相职责虽共享君臣人物，但后者不是前者的直接授权、结果或明确因果。

---

## 15. `RBC-4C8CD400EE25E2D21AA3`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 4, "value": "陈平"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 1, "value": "obj-2b89622cefdec6e3|obj-a4785b7cc76ec776", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-4023C698252711CF1EAE`
- 人物：obj-2b89622cefdec6e3|obj-a4785b7cc76ec776
- 角色：["actor", "advisor", "office_holder"]
- 行为：荐举
- 责任：皇位继承
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-F03D58B34DB5A14317F1C5AA@SP-A5E7130D5F5040D99405`
  - 时间：高后八年后九月
  - 命题：陈平 / 荐举 / 代王
  - 结果：代王遂即天子位
  - 摘要：诛灭诸吕后，陈平等大臣迎立代王，陈平再拜称少帝等不当奉宗庙，请代王即天子位。
  - SourcePassage：`SP-A5E7130D5F5040D99405`
- `K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-FB7DEEBBAB75C44003CAD89F@SP-A5E7130D5F5040D99405`
  - 时间：高后八年后九月
  - 命题：陈平 / 荐举 / 代王
  - 结果：代王遂即天子位
  - 摘要：诛灭诸吕后，陈平等大臣迎立代王，陈平再拜称少帝等不当奉宗庙，请代王即天子位。
  - SourcePassage：`SP-A5E7130D5F5040D99405`

#### SourcePassage 原文与上下文

<details><summary><code>SP-A5E7130D5F5040D99405</code> · xiaowen-benji:976-1076</summary>

上文：

> 侯劉章、東牟侯劉興居、典客劉揭皆再拜言曰：「子弘等皆非孝惠帝子，不當奉宗廟。臣謹請（與）陰安侯列侯頃王后與瑯邪王、宗室、大臣、列侯、吏二千石議曰：『大王高帝長子，宜為高帝嗣。』願大王即天子位。」代王曰：「奉高帝宗廟，重事也。寡人不佞，不足以稱宗廟。願請楚王計宜者，寡人不敢當。」群臣皆伏固請。代王西鄉讓者三，南鄉讓者再。

原文：

> 丞相平等皆曰：「臣伏計之，大王奉高帝宗廟最宜稱，雖天下諸侯萬民以為宜。臣等為宗廟社稷計，不敢忽。願大王幸聽臣等。臣謹奉天子璽符再拜上。」代王曰：「宗室將相王列侯以為莫宜寡人，寡人不敢辭。」遂即天子位。

下文：

> 群臣以禮次侍。乃使太仆嬰與東牟侯興居清宮，奉天子法駕，迎于代邸。皇帝即日夕入未央宮。乃夜拜宋昌為衛將軍，鎮撫南北軍。以張武為郎中令，行殿中。還坐前殿。於是夜下詔書曰：「閒者諸呂用事擅權，謀為大逆，欲以危劉氏宗廟，賴將相列侯宗室大臣誅之，皆伏其辜。朕初即位，其赦天下，賜民爵一級，女子百戶牛酒，酺五日。」
> 孝文皇帝元年十

</details>

### 右端内容

- Episode：`EP-4B989F5A9C45B8DB13BE`
- 人物：obj-2b89622cefdec6e3|obj-a4785b7cc76ec776
- 角色：["actor", "advisor", "office_holder"]
- 行为：任命 | 其他 | 让位
- 责任：丞相位次调整|丞相职位|右丞相
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-B0B3945159B8F95919B105D4@SP-CB7977B3B1CA4036E871`
  - 时间：文帝前元年十一月
  - 命题：文帝 / 任命 / 周勃
  - 结果：太尉勃为右丞相，并因诛诸吕功受赏
  - 摘要：文帝前元年，陈平以诛诸吕功不如周勃为由让位，周勃由太尉迁为右丞相；此后论诛诸吕功，周勃以下增户赐金。
  - SourcePassage：`SP-CB7977B3B1CA4036E871`
- `K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-C10A30C061E59D665E1B62D9@SP-CB7977B3B1CA4036E871`
  - 时间：文帝前元年十一月
  - 命题：文帝 / 任命 / 周勃
  - 结果：太尉勃为右丞相，并因诛诸吕功受赏
  - 摘要：文帝前元年，陈平以诛诸吕功不如周勃为由让位，周勃由太尉迁为右丞相；此后论诛诸吕功，周勃以下增户赐金。
  - SourcePassage：`SP-CB7977B3B1CA4036E871`
- `K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-088182DFE3EDFCA9996FCBF8@SP-25AB550D0E671F674756`
  - 时间：孝文帝初立后
  - 命题：陈平 / 其他 / 周勃
  - 结果：周勃为右丞相，陈平徙左丞相；陈平赐金千斤、益封三千户
  - 摘要：刘恒即位后，陈平称诛诸吕之功不如周勃，愿让右丞相位；刘恒于是徙陈平为左丞相，并赐金益封。
  - SourcePassage：`SP-25AB550D0E671F674756`
- `K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-3292E7BBE004424456D45B4A@SP-25AB550D0E671F674756`
  - 时间：孝文帝初立后
  - 命题：陈平 / 其他 / 周勃
  - 结果：周勃为右丞相，陈平徙左丞相；陈平赐金千斤、益封三千户
  - 摘要：刘恒即位后，陈平称诛诸吕之功不如周勃，愿让右丞相位；刘恒于是徙陈平为左丞相，并赐金益封。
  - SourcePassage：`SP-25AB550D0E671F674756`
- `K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-7F6A816D9F87101CE60218F8@SP-25AB550D0E671F674756`
  - 时间：孝文帝初立后
  - 命题：陈平 / 其他 / 周勃
  - 结果：周勃为右丞相，陈平徙左丞相；陈平赐金千斤、益封三千户
  - 摘要：刘恒即位后，陈平称诛诸吕之功不如周勃，愿让右丞相位；刘恒于是徙陈平为左丞相，并赐金益封。
  - SourcePassage：`SP-25AB550D0E671F674756`
- `K0-A-G26I-A-CLMK-C3CBA487A132FE5F09BD-EVD-31068B43B6B4AE13D86DAF30@SP-25AB550D0E671F674756`
  - 时间：文帝前元年十一月
  - 命题：陈平 / 让位 / 周勃
  - 结果：陈平徙为左丞相，周勃为右丞相
  - 摘要：文帝即位后，陈平称自己在诛诸吕中的功劳不如周勃，请让右丞相位给周勃。
  - SourcePassage：`SP-25AB550D0E671F674756`
- `K0-A-G26I-A-CLMK-C3CBA487A132FE5F09BD-EVD-DBE54333764EC1A5F837539A@SP-25AB550D0E671F674756`
  - 时间：文帝前元年十一月
  - 命题：陈平 / 让位 / 周勃
  - 结果：陈平徙为左丞相，周勃为右丞相
  - 摘要：文帝即位后，陈平称自己在诛诸吕中的功劳不如周勃，请让右丞相位给周勃。
  - SourcePassage：`SP-25AB550D0E671F674756`

#### SourcePassage 原文与上下文

<details><summary><code>SP-25AB550D0E671F674756</code> · chen-chengxiang-shijia:3631-3756</summary>

上文：

> 中，百官皆因決事。
> 呂嬃常以前陳平爲高帝謀執樊噲，數讒曰：「陳平爲相非治事，日飲醇酒，戲婦女。」陳平聞，日益甚。呂太后聞之，私獨喜。面質呂嬃於陳平曰：「鄙語曰『兒婦人口不可用』，顧君與我何如耳。無畏呂嬃之讒也。」
> 呂太后立諸呂爲王，陳平僞聽之。及呂太后崩，平與太尉勃合謀，卒誅諸呂，立孝文皇帝，陳平本謀也。審食其免相。

原文：

> 孝文帝立，以爲太尉勃親以兵誅呂氏，功多；陳平欲讓勃尊位，乃謝病。孝文帝初立，怪平病，問之。平曰：「高祖時，勃功不如臣平。及誅諸呂，臣功亦不如勃。願以右丞相讓勃。」於是孝文帝乃以絳侯勃爲右丞相，位次第一；平徙爲左丞相，位次第二。賜平金千斤，益封三千戸。

下文：

> 居頃之，孝文皇帝既益明習國家事，朝而問右丞相勃曰：「天下一歳決獄幾何？」勃謝曰：「不知。」問：「天下一歳錢穀出入幾何？」勃又謝不知，汗出沾背，愧不能對。於是上亦問左丞相平。平曰：「有主者。」上曰：「主者謂誰？」平曰：「陛下即問決獄，責廷尉；問錢穀，責治粟內史。」上曰：「苟各有主者，而君所主者何事也？」平謝曰：「主臣！

</details>

<details><summary><code>SP-CB7977B3B1CA4036E871</code> · xiaowen-benji:1264-1454</summary>

上文：

> 迎于代邸。皇帝即日夕入未央宮。乃夜拜宋昌為衛將軍，鎮撫南北軍。以張武為郎中令，行殿中。還坐前殿。於是夜下詔書曰：「閒者諸呂用事擅權，謀為大逆，欲以危劉氏宗廟，賴將相列侯宗室大臣誅之，皆伏其辜。朕初即位，其赦天下，賜民爵一級，女子百戶牛酒，酺五日。」
> 孝文皇帝元年十月庚戌，徙立故琅邪王泽为燕王。
> 辛亥，皇帝即阼，謁高廟。

原文：

> 右丞相平徙為左丞相，太尉勃為右丞相，大將軍灌嬰為太尉。諸呂所奪齊楚故地，皆復與之。
> 壬子，遣車騎將軍薄昭迎皇太后於代。皇帝曰：「呂產自置為相國，呂祿為上將軍，擅矯遣灌將軍嬰將兵擊齊，欲代劉氏，嬰留滎陽弗擊，與諸侯合謀以誅呂氏。呂產欲為不善，丞相陳平與太尉周勃謀奪呂產等軍。朱虛侯劉章首先捕呂產等。太尉身率襄平侯通持節承詔入北軍。典客劉揭身奪趙王呂祿印。益封太尉勃萬戶，賜金五千斤。

下文：

> 丞相陳平、灌將軍嬰邑各三千戶，金二千斤。朱虛侯劉章、襄平侯通、東牟侯劉興居邑各二千戶，金千斤。封典客揭為陽信侯，賜金千斤。」
> 十二月，上曰：「法者，治之正也，所以禁暴而率善人也。今犯法已論，而使毋罪之父母妻子同產坐之，及為收帑，朕甚不取。其議之。」有司皆曰：「民不能自治，故為法以禁之。相坐坐收，所以累其心，使重犯法，所

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-F03D58B34DB5A14317F1C5AA@SP-A5E7130D5F5040D99405`、`K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-FB7DEEBBAB75C44003CAD89F@SP-A5E7130D5F5040D99405`、`K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-B0B3945159B8F95919B105D4@SP-CB7977B3B1CA4036E871`、`K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-C10A30C061E59D665E1B62D9@SP-CB7977B3B1CA4036E871`、`K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-088182DFE3EDFCA9996FCBF8@SP-25AB550D0E671F674756`、`K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-3292E7BBE004424456D45B4A@SP-25AB550D0E671F674756`、`K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-7F6A816D9F87101CE60218F8@SP-25AB550D0E671F674756`、`K0-A-G26I-A-CLMK-C3CBA487A132FE5F09BD-EVD-31068B43B6B4AE13D86DAF30@SP-25AB550D0E671F674756`、`K0-A-G26I-A-CLMK-C3CBA487A132FE5F09BD-EVD-DBE54333764EC1A5F837539A@SP-25AB550D0E671F674756`
- 理由：陈平迎立刘恒与即位后的丞相位次调整时间相近，但端点证据未说明后者由前者直接导致。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-D761544EA4910FE96A84-EVD-F03D58B34DB5A14317F1C5AA@SP-A5E7130D5F5040D99405`、`K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-B0B3945159B8F95919B105D4@SP-CB7977B3B1CA4036E871`
- 理由：陈平参与迎立刘恒与刘恒即位后调整丞相位次是相邻政治背景，但端点未明示迎立行为直接导致该具体任命。

---

## 16. `RBC-59A9D4CF43AD84EC0425`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 3, "value": "周勃"}, {"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 3, "value": "文帝"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 1, "value": "obj-2b89622cefdec6e3|obj-a4785b7cc76ec776", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`authority_change`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-4B989F5A9C45B8DB13BE`
- 人物：obj-2b89622cefdec6e3|obj-a4785b7cc76ec776
- 角色：["actor", "advisor", "office_holder"]
- 行为：任命 | 其他 | 让位
- 责任：丞相位次调整|丞相职位|右丞相
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-B0B3945159B8F95919B105D4@SP-CB7977B3B1CA4036E871`
  - 时间：文帝前元年十一月
  - 命题：文帝 / 任命 / 周勃
  - 结果：太尉勃为右丞相，并因诛诸吕功受赏
  - 摘要：文帝前元年，陈平以诛诸吕功不如周勃为由让位，周勃由太尉迁为右丞相；此后论诛诸吕功，周勃以下增户赐金。
  - SourcePassage：`SP-CB7977B3B1CA4036E871`
- `K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-C10A30C061E59D665E1B62D9@SP-CB7977B3B1CA4036E871`
  - 时间：文帝前元年十一月
  - 命题：文帝 / 任命 / 周勃
  - 结果：太尉勃为右丞相，并因诛诸吕功受赏
  - 摘要：文帝前元年，陈平以诛诸吕功不如周勃为由让位，周勃由太尉迁为右丞相；此后论诛诸吕功，周勃以下增户赐金。
  - SourcePassage：`SP-CB7977B3B1CA4036E871`
- `K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-088182DFE3EDFCA9996FCBF8@SP-25AB550D0E671F674756`
  - 时间：孝文帝初立后
  - 命题：陈平 / 其他 / 周勃
  - 结果：周勃为右丞相，陈平徙左丞相；陈平赐金千斤、益封三千户
  - 摘要：刘恒即位后，陈平称诛诸吕之功不如周勃，愿让右丞相位；刘恒于是徙陈平为左丞相，并赐金益封。
  - SourcePassage：`SP-25AB550D0E671F674756`
- `K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-3292E7BBE004424456D45B4A@SP-25AB550D0E671F674756`
  - 时间：孝文帝初立后
  - 命题：陈平 / 其他 / 周勃
  - 结果：周勃为右丞相，陈平徙左丞相；陈平赐金千斤、益封三千户
  - 摘要：刘恒即位后，陈平称诛诸吕之功不如周勃，愿让右丞相位；刘恒于是徙陈平为左丞相，并赐金益封。
  - SourcePassage：`SP-25AB550D0E671F674756`
- `K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-7F6A816D9F87101CE60218F8@SP-25AB550D0E671F674756`
  - 时间：孝文帝初立后
  - 命题：陈平 / 其他 / 周勃
  - 结果：周勃为右丞相，陈平徙左丞相；陈平赐金千斤、益封三千户
  - 摘要：刘恒即位后，陈平称诛诸吕之功不如周勃，愿让右丞相位；刘恒于是徙陈平为左丞相，并赐金益封。
  - SourcePassage：`SP-25AB550D0E671F674756`
- `K0-A-G26I-A-CLMK-C3CBA487A132FE5F09BD-EVD-31068B43B6B4AE13D86DAF30@SP-25AB550D0E671F674756`
  - 时间：文帝前元年十一月
  - 命题：陈平 / 让位 / 周勃
  - 结果：陈平徙为左丞相，周勃为右丞相
  - 摘要：文帝即位后，陈平称自己在诛诸吕中的功劳不如周勃，请让右丞相位给周勃。
  - SourcePassage：`SP-25AB550D0E671F674756`
- `K0-A-G26I-A-CLMK-C3CBA487A132FE5F09BD-EVD-DBE54333764EC1A5F837539A@SP-25AB550D0E671F674756`
  - 时间：文帝前元年十一月
  - 命题：陈平 / 让位 / 周勃
  - 结果：陈平徙为左丞相，周勃为右丞相
  - 摘要：文帝即位后，陈平称自己在诛诸吕中的功劳不如周勃，请让右丞相位给周勃。
  - SourcePassage：`SP-25AB550D0E671F674756`

#### SourcePassage 原文与上下文

<details><summary><code>SP-25AB550D0E671F674756</code> · chen-chengxiang-shijia:3631-3756</summary>

上文：

> 中，百官皆因決事。
> 呂嬃常以前陳平爲高帝謀執樊噲，數讒曰：「陳平爲相非治事，日飲醇酒，戲婦女。」陳平聞，日益甚。呂太后聞之，私獨喜。面質呂嬃於陳平曰：「鄙語曰『兒婦人口不可用』，顧君與我何如耳。無畏呂嬃之讒也。」
> 呂太后立諸呂爲王，陳平僞聽之。及呂太后崩，平與太尉勃合謀，卒誅諸呂，立孝文皇帝，陳平本謀也。審食其免相。

原文：

> 孝文帝立，以爲太尉勃親以兵誅呂氏，功多；陳平欲讓勃尊位，乃謝病。孝文帝初立，怪平病，問之。平曰：「高祖時，勃功不如臣平。及誅諸呂，臣功亦不如勃。願以右丞相讓勃。」於是孝文帝乃以絳侯勃爲右丞相，位次第一；平徙爲左丞相，位次第二。賜平金千斤，益封三千戸。

下文：

> 居頃之，孝文皇帝既益明習國家事，朝而問右丞相勃曰：「天下一歳決獄幾何？」勃謝曰：「不知。」問：「天下一歳錢穀出入幾何？」勃又謝不知，汗出沾背，愧不能對。於是上亦問左丞相平。平曰：「有主者。」上曰：「主者謂誰？」平曰：「陛下即問決獄，責廷尉；問錢穀，責治粟內史。」上曰：「苟各有主者，而君所主者何事也？」平謝曰：「主臣！

</details>

<details><summary><code>SP-CB7977B3B1CA4036E871</code> · xiaowen-benji:1264-1454</summary>

上文：

> 迎于代邸。皇帝即日夕入未央宮。乃夜拜宋昌為衛將軍，鎮撫南北軍。以張武為郎中令，行殿中。還坐前殿。於是夜下詔書曰：「閒者諸呂用事擅權，謀為大逆，欲以危劉氏宗廟，賴將相列侯宗室大臣誅之，皆伏其辜。朕初即位，其赦天下，賜民爵一級，女子百戶牛酒，酺五日。」
> 孝文皇帝元年十月庚戌，徙立故琅邪王泽为燕王。
> 辛亥，皇帝即阼，謁高廟。

原文：

> 右丞相平徙為左丞相，太尉勃為右丞相，大將軍灌嬰為太尉。諸呂所奪齊楚故地，皆復與之。
> 壬子，遣車騎將軍薄昭迎皇太后於代。皇帝曰：「呂產自置為相國，呂祿為上將軍，擅矯遣灌將軍嬰將兵擊齊，欲代劉氏，嬰留滎陽弗擊，與諸侯合謀以誅呂氏。呂產欲為不善，丞相陳平與太尉周勃謀奪呂產等軍。朱虛侯劉章首先捕呂產等。太尉身率襄平侯通持節承詔入北軍。典客劉揭身奪趙王呂祿印。益封太尉勃萬戶，賜金五千斤。

下文：

> 丞相陳平、灌將軍嬰邑各三千戶，金二千斤。朱虛侯劉章、襄平侯通、東牟侯劉興居邑各二千戶，金千斤。封典客揭為陽信侯，賜金千斤。」
> 十二月，上曰：「法者，治之正也，所以禁暴而率善人也。今犯法已論，而使毋罪之父母妻子同產坐之，及為收帑，朕甚不取。其議之。」有司皆曰：「民不能自治，故為法以禁之。相坐坐收，所以累其心，使重犯法，所

</details>

### 右端内容

- Episode：`EP-8F713327303CD77AB91E`
- 人物：obj-2b89622cefdec6e3|obj-a4785b7cc76ec776
- 角色：["actor", "advisor", "office_holder"]
- 行为：任命
- 责任：丞相
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-8A2C6A39D211C2E21CAC-EVD-6114051970517A5364DF514A@SP-4160FC757A0360C18492`
  - 时间：文帝前二年十一月乙亥
  - 命题：文帝 / 任命 / 周勃
  - 结果：周勃复为丞相
  - 摘要：文帝前二年十一月，周勃再次出任丞相。
  - SourcePassage：`SP-4160FC757A0360C18492`

#### SourcePassage 原文与上下文

<details><summary><code>SP-4160FC757A0360C18492</code> · jianghou-zhoubo-shijia:1266-1282</summary>

上文：

> 呂產以呂王為漢相國，秉漢權，欲危劉氏。勃為太尉，不得入軍門。陳平為丞相，不得任事。於是勃與平謀，卒誅諸呂而立孝文皇帝。其語在呂后、孝文事中。
> 文帝既立，以勃為右丞相，賜金五千斤，食邑萬戶。居月餘，人或說勃曰：「君既誅諸呂，立代王，威震天下，而君受厚賞，處尊位，以寵，久之即禍及身矣。」勃懼，亦自危，乃謝請歸相印。上許之。

原文：

> 歲餘，丞相平卒，上復以勃為丞相。

下文：

> 十餘月，上曰：「前日吾詔列侯就國，或未能行，丞相吾所重，其率先之。」乃免相就國。
> 歲餘，每河東守尉行縣至絳，絳侯勃自畏恐誅，常被甲，令家人持兵以見之。其後人有上書告勃欲反，下廷尉。廷尉下其事長安，逮捕勃治之。勃恐，不知置辭。吏稍侵辱之。勃以千金與獄吏，獄吏乃書牘背示之，曰「以公主為證」。公主者，孝文帝女也，勃太子勝之尚

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-B0B3945159B8F95919B105D4@SP-CB7977B3B1CA4036E871`、`K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-C10A30C061E59D665E1B62D9@SP-CB7977B3B1CA4036E871`、`K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-088182DFE3EDFCA9996FCBF8@SP-25AB550D0E671F674756`、`K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-3292E7BBE004424456D45B4A@SP-25AB550D0E671F674756`、`K0-A-G26I-A-CLMK-AF9753A1BF9E93B90A6F-EVD-7F6A816D9F87101CE60218F8@SP-25AB550D0E671F674756`、`K0-A-G26I-A-CLMK-C3CBA487A132FE5F09BD-EVD-31068B43B6B4AE13D86DAF30@SP-25AB550D0E671F674756`、`K0-A-G26I-A-CLMK-C3CBA487A132FE5F09BD-EVD-DBE54333764EC1A5F837539A@SP-25AB550D0E671F674756`、`K0-A-G26I-A-CLMK-8A2C6A39D211C2E21CAC-EVD-6114051970517A5364DF514A@SP-4160FC757A0360C18492`
- 理由：周勃先由太尉转任右丞相，后在曾免相后再次明确复任丞相，属于同一相权的再次授予。

#### Reviewer B

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-65A0317817EF188EF25A-EVD-B0B3945159B8F95919B105D4@SP-CB7977B3B1CA4036E871`、`K0-A-G26I-A-CLMK-8A2C6A39D211C2E21CAC-EVD-6114051970517A5364DF514A@SP-4160FC757A0360C18492`
- 理由：左端首次任周勃为右丞相，右端明确记载岁余后复任其为丞相，属于同一相位的再次授任。

---

## 17. `RBC-67B87CE36E260E77BD36`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 3, "value": "周勃"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 1, "value": "obj-2b89622cefdec6e3|obj-a4785b7cc76ec776", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`authority_change`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-8D7B826E3CED49379E38`
- 人物：obj-2b89622cefdec6e3|obj-a4785b7cc76ec776
- 角色：["actor", "advisor", "office_holder"]
- 行为：其他
- 责任：右丞相
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-5DABE9A4B85288911760-EVD-645A7692ED3C00A514C70039@SP-FF68A5899C55639F65E1`
  - 时间：文帝前元年秋八月
  - 命题：周勃 / 其他 / 右丞相职务
  - 结果：谢病请归相印，右丞相勃免
  - 摘要：文帝前元年，周勃任右丞相时不能回答一年决狱和钱谷出入之数，自知才能远不如陈平，随后因自危而谢病请归相印并免相。
  - SourcePassage：`SP-FF68A5899C55639F65E1`
- `K0-A-G26I-A-CLMK-5DABE9A4B85288911760-EVD-88DD4A2A4E34D18BD310699B@SP-FF68A5899C55639F65E1`
  - 时间：文帝前元年秋八月
  - 命题：周勃 / 其他 / 右丞相职务
  - 结果：谢病请归相印，右丞相勃免
  - 摘要：文帝前元年，周勃任右丞相时不能回答一年决狱和钱谷出入之数，自知才能远不如陈平，随后因自危而谢病请归相印并免相。
  - SourcePassage：`SP-FF68A5899C55639F65E1`

#### SourcePassage 原文与上下文

<details><summary><code>SP-FF68A5899C55639F65E1</code> · jianghou-zhoubo-shijia:1177-1266</summary>

上文：

> 好文學，每召諸生說士，東鄉坐而責之：「趣為我語。」其椎少文如此。
> 勃既定燕而歸，高祖已崩矣，以列侯事孝惠帝。孝惠帝六年，置太尉官，以勃為太尉。十歲，高后崩。呂祿以趙王為漢上將軍，呂產以呂王為漢相國，秉漢權，欲危劉氏。勃為太尉，不得入軍門。陳平為丞相，不得任事。於是勃與平謀，卒誅諸呂而立孝文皇帝。其語在呂后、孝文事中。

原文：

> 文帝既立，以勃為右丞相，賜金五千斤，食邑萬戶。居月餘，人或說勃曰：「君既誅諸呂，立代王，威震天下，而君受厚賞，處尊位，以寵，久之即禍及身矣。」勃懼，亦自危，乃謝請歸相印。上許之。

下文：

> 歲餘，丞相平卒，上復以勃為丞相。十餘月，上曰：「前日吾詔列侯就國，或未能行，丞相吾所重，其率先之。」乃免相就國。
> 歲餘，每河東守尉行縣至絳，絳侯勃自畏恐誅，常被甲，令家人持兵以見之。其後人有上書告勃欲反，下廷尉。廷尉下其事長安，逮捕勃治之。勃恐，不知置辭。吏稍侵辱之。勃以千金與獄吏，獄吏乃書牘背示之，曰「以公主為證」。

</details>

### 右端内容

- Episode：`EP-8F713327303CD77AB91E`
- 人物：obj-2b89622cefdec6e3|obj-a4785b7cc76ec776
- 角色：["actor", "advisor", "office_holder"]
- 行为：任命
- 责任：丞相
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-8A2C6A39D211C2E21CAC-EVD-6114051970517A5364DF514A@SP-4160FC757A0360C18492`
  - 时间：文帝前二年十一月乙亥
  - 命题：文帝 / 任命 / 周勃
  - 结果：周勃复为丞相
  - 摘要：文帝前二年十一月，周勃再次出任丞相。
  - SourcePassage：`SP-4160FC757A0360C18492`

#### SourcePassage 原文与上下文

<details><summary><code>SP-4160FC757A0360C18492</code> · jianghou-zhoubo-shijia:1266-1282</summary>

上文：

> 呂產以呂王為漢相國，秉漢權，欲危劉氏。勃為太尉，不得入軍門。陳平為丞相，不得任事。於是勃與平謀，卒誅諸呂而立孝文皇帝。其語在呂后、孝文事中。
> 文帝既立，以勃為右丞相，賜金五千斤，食邑萬戶。居月餘，人或說勃曰：「君既誅諸呂，立代王，威震天下，而君受厚賞，處尊位，以寵，久之即禍及身矣。」勃懼，亦自危，乃謝請歸相印。上許之。

原文：

> 歲餘，丞相平卒，上復以勃為丞相。

下文：

> 十餘月，上曰：「前日吾詔列侯就國，或未能行，丞相吾所重，其率先之。」乃免相就國。
> 歲餘，每河東守尉行縣至絳，絳侯勃自畏恐誅，常被甲，令家人持兵以見之。其後人有上書告勃欲反，下廷尉。廷尉下其事長安，逮捕勃治之。勃恐，不知置辭。吏稍侵辱之。勃以千金與獄吏，獄吏乃書牘背示之，曰「以公主為證」。公主者，孝文帝女也，勃太子勝之尚

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-5DABE9A4B85288911760-EVD-645A7692ED3C00A514C70039@SP-FF68A5899C55639F65E1`、`K0-A-G26I-A-CLMK-5DABE9A4B85288911760-EVD-88DD4A2A4E34D18BD310699B@SP-FF68A5899C55639F65E1`、`K0-A-G26I-A-CLMK-8A2C6A39D211C2E21CAC-EVD-6114051970517A5364DF514A@SP-4160FC757A0360C18492`
- 理由：周勃先谢归相印获准免相，岁余后又明确复任丞相，构成同一职权的恢复。

#### Reviewer B

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-5DABE9A4B85288911760-EVD-645A7692ED3C00A514C70039@SP-FF68A5899C55639F65E1`、`K0-A-G26I-A-CLMK-8A2C6A39D211C2E21CAC-EVD-6114051970517A5364DF514A@SP-4160FC757A0360C18492`
- 理由：周勃先归还相印并免相，岁余后又明确复任丞相，是同一职权的撤离与重新授予。

---

## 18. `RBC-7DB5F37DCBA46F15191E`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 6, "value": "隆科多"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 1, "value": "per-d7a0d148728a2905", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`authority_change`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-BF7A3052DFD70BFD1863`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：任命
- 责任：理籓院、史书会典修纂
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`
  - 时间：雍正二年
  - 命题：胤禛 / 任命 / 隆科多
  - 结果：隆科多兼领理籓院事并充总裁、监修
  - 摘要：雍正二年，胤禛令隆科多兼领理籓院事，并在《圣祖实录》《大清会典》《明史》修纂中任总裁、监修。
  - SourcePassage：`SP-6E9C3B8CE114F78DACB8`
- `K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-F9D274993EFEAF194A59D615@SP-6E9C3B8CE114F78DACB8`
  - 时间：雍正二年
  - 命题：胤禛 / 任命 / 隆科多
  - 结果：隆科多兼领理籓院事并充总裁、监修
  - 摘要：雍正二年，胤禛令隆科多兼领理籓院事，并在《圣祖实录》《大清会典》《明史》修纂中任总裁、监修。
  - SourcePassage：`SP-6E9C3B8CE114F78DACB8`

#### SourcePassage 原文与上下文

<details><summary><code>SP-6E9C3B8CE114F78DACB8</code> · longkodo-liezhuan:249-286</summary>

上文：

> 實心任事，罷副都統、鑾儀使，在一等侍衛上行走。
> 五十年，授步軍統領。
> 五十九年，擢理籓院尚書，仍管步軍統領。
> 六十一年十一月，聖祖大漸，召受顧命。世宗即位，命與大學士馬齊總理事務，襲一等公，授吏部尚書。旋以總理事務勞，加一等阿達哈哈番，以其長子岳興阿襲。次子玉柱，自侍衛授鑾儀使。
> 雍正元年，與川陝總督年羹堯同加太保。

原文：

> 二年，兼領理籓院事。纂修《聖祖實錄》、《大清會典》並充總裁，監修《明史》。

下文：

> 復與羹堯同賜雙眼花翎、四團龍補服、黃帶、紫轡。
> 三年，解步軍統領。玉柱以行止甚劣，奪官，交隆科多管束。羹堯得罪，上以都統範時捷疏劾欺罔貪婪諸狀，及妄劾道員金南瑛等，並下吏部議處。上諭曰：「前以隆科多、年羹堯頗著勤勞，予以異數，乃交結專擅，諸事欺隱。」命繳上所賜四團龍補服，並不得復用雙眼花翎、黃帶、紫轡。及議上，以時捷劾

</details>

### 右端内容

- Episode：`EP-DF748EBD65DF45A1F2E5`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：处置
- 责任：太保、世职、阿兰善修城垦地
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-670D941EBDA7D75198CF793A@SP-B3BE0D6AB5794AAF665D`
  - 时间：雍正三年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被削太保及世职，并被派往阿兰善等处修城垦地
  - 摘要：雍正三年，胤禛责隆科多有意扰乱，削其太保及一等阿达哈哈番世职，并命其往阿兰善等处修城垦地。
  - SourcePassage：`SP-B3BE0D6AB5794AAF665D`
- `K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-88547DF5BB950030B2EF534C@SP-B3BE0D6AB5794AAF665D`
  - 时间：雍正三年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被削太保及世职，并被派往阿兰善等处修城垦地
  - 摘要：雍正三年，胤禛责隆科多有意扰乱，削其太保及一等阿达哈哈番世职，并命其往阿兰善等处修城垦地。
  - SourcePassage：`SP-B3BE0D6AB5794AAF665D`

#### SourcePassage 原文与上下文

<details><summary><code>SP-B3BE0D6AB5794AAF665D</code> · longkodo-liezhuan:465-541</summary>

上文：

> 、紫轡。
> 三年，解步軍統領。玉柱以行止甚劣，奪官，交隆科多管束。羹堯得罪，上以都統範時捷疏劾欺罔貪婪諸狀，及妄劾道員金南瑛等，並下吏部議處。上諭曰：「前以隆科多、年羹堯頗著勤勞，予以異數，乃交結專擅，諸事欺隱。」命繳上所賜四團龍補服，並不得復用雙眼花翎、黃帶、紫轡。及議上，以時捷劾，請罷羹堯任；以妄劾南瑛，請嚴加治罪。

原文：

> 上以前議徇庇，後議復過當，責隆科多有意擾亂，削太保及一等阿達哈哈番世職，命往阿蘭善等處修城墾地，諭曰：「朕御極之初，隆科多、年羹堯皆寄以心腹，毫無猜防。

下文：

> 孰知朕視為一德，彼竟有二心，招權納賄，擅作威福，欺罔悖負，朕豈能姑息養奸耶？向日明珠、索額圖結黨行私，聖祖解其要職，置之閒散，何嘗更加信用？隆科多、年羹堯若不知恐懼，痛改前非，欲如明珠等，萬不能也！殊典不可再邀，覆轍不可屢蹈，各宜警懼，毋自乾誅滅。」
> 四年，隆科多家僕牛倫挾勢索賕，事發，逮下法司，鞫得隆科多受羹堯及總督

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`、`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-F9D274993EFEAF194A59D615@SP-6E9C3B8CE114F78DACB8`、`K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-670D941EBDA7D75198CF793A@SP-B3BE0D6AB5794AAF665D`、`K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-88547DF5BB950030B2EF534C@SP-B3BE0D6AB5794AAF665D`
- 理由：隆科多先获兼领理籓院及监修等任命，次年被削太保和世职并外遣，属于明确撤权。

#### Reviewer B

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`、`K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-670D941EBDA7D75198CF793A@SP-B3BE0D6AB5794AAF665D`
- 理由：隆科多先获理籓院及修史职权，次年即被削太保与世职并外派，属于明确授职后的降等撤权。

---

## 19. `RBC-7ED7306ADF0036AF0DD5`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 6, "value": "隆科多"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 1, "value": "per-d7a0d148728a2905", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`yes`

### 左端内容

- Episode：`EP-24D3B7BF1A6C5FDBC7F4`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：收权
- 责任：赏赐特典
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`
  - 时间：雍正三年
  - 命题：胤禛 / 收权 / 隆科多
  - 结果：隆科多被追缴四团龙补服且不得复用双眼花翎、黄带、紫辔
  - 摘要：雍正三年，胤禛因隆科多与年羹尧交结专擅、诸事欺隐，命其缴还所赐服饰特典并不得复用双眼花翎、黄带、紫辔。
  - SourcePassage：`SP-3C5A229F9056917E5728`
- `K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-847B512654CC803D8249BD47@SP-3C5A229F9056917E5728`
  - 时间：雍正三年
  - 命题：胤禛 / 收权 / 隆科多
  - 结果：隆科多被追缴四团龙补服且不得复用双眼花翎、黄带、紫辔
  - 摘要：雍正三年，胤禛因隆科多与年羹尧交结专擅、诸事欺隐，命其缴还所赐服饰特典并不得复用双眼花翎、黄带、紫辔。
  - SourcePassage：`SP-3C5A229F9056917E5728`

#### SourcePassage 原文与上下文

<details><summary><code>SP-3C5A229F9056917E5728</code> · longkodo-liezhuan:375-438</summary>

上文：

> 。次子玉柱，自侍衛授鑾儀使。
> 雍正元年，與川陝總督年羹堯同加太保。
> 二年，兼領理籓院事。纂修《聖祖實錄》、《大清會典》並充總裁，監修《明史》。復與羹堯同賜雙眼花翎、四團龍補服、黃帶、紫轡。
> 三年，解步軍統領。玉柱以行止甚劣，奪官，交隆科多管束。羹堯得罪，上以都統範時捷疏劾欺罔貪婪諸狀，及妄劾道員金南瑛等，並下吏部議處。

原文：

> 上諭曰：「前以隆科多、年羹堯頗著勤勞，予以異數，乃交結專擅，諸事欺隱。」命繳上所賜四團龍補服，並不得復用雙眼花翎、黃帶、紫轡。

下文：

> 及議上，以時捷劾，請罷羹堯任；以妄劾南瑛，請嚴加治罪。上以前議徇庇，後議復過當，責隆科多有意擾亂，削太保及一等阿達哈哈番世職，命往阿蘭善等處修城墾地，諭曰：「朕御極之初，隆科多、年羹堯皆寄以心腹，毫無猜防。孰知朕視為一德，彼竟有二心，招權納賄，擅作威福，欺罔悖負，朕豈能姑息養奸耶？向日明珠、索額圖結黨行私，聖祖解其要職

</details>

### 右端内容

- Episode：`EP-BF7A3052DFD70BFD1863`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：任命
- 责任：理籓院、史书会典修纂
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`
  - 时间：雍正二年
  - 命题：胤禛 / 任命 / 隆科多
  - 结果：隆科多兼领理籓院事并充总裁、监修
  - 摘要：雍正二年，胤禛令隆科多兼领理籓院事，并在《圣祖实录》《大清会典》《明史》修纂中任总裁、监修。
  - SourcePassage：`SP-6E9C3B8CE114F78DACB8`
- `K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-F9D274993EFEAF194A59D615@SP-6E9C3B8CE114F78DACB8`
  - 时间：雍正二年
  - 命题：胤禛 / 任命 / 隆科多
  - 结果：隆科多兼领理籓院事并充总裁、监修
  - 摘要：雍正二年，胤禛令隆科多兼领理籓院事，并在《圣祖实录》《大清会典》《明史》修纂中任总裁、监修。
  - SourcePassage：`SP-6E9C3B8CE114F78DACB8`

#### SourcePassage 原文与上下文

<details><summary><code>SP-6E9C3B8CE114F78DACB8</code> · longkodo-liezhuan:249-286</summary>

上文：

> 實心任事，罷副都統、鑾儀使，在一等侍衛上行走。
> 五十年，授步軍統領。
> 五十九年，擢理籓院尚書，仍管步軍統領。
> 六十一年十一月，聖祖大漸，召受顧命。世宗即位，命與大學士馬齊總理事務，襲一等公，授吏部尚書。旋以總理事務勞，加一等阿達哈哈番，以其長子岳興阿襲。次子玉柱，自侍衛授鑾儀使。
> 雍正元年，與川陝總督年羹堯同加太保。

原文：

> 二年，兼領理籓院事。纂修《聖祖實錄》、《大清會典》並充總裁，監修《明史》。

下文：

> 復與羹堯同賜雙眼花翎、四團龍補服、黃帶、紫轡。
> 三年，解步軍統領。玉柱以行止甚劣，奪官，交隆科多管束。羹堯得罪，上以都統範時捷疏劾欺罔貪婪諸狀，及妄劾道員金南瑛等，並下吏部議處。上諭曰：「前以隆科多、年羹堯頗著勤勞，予以異數，乃交結專擅，諸事欺隱。」命繳上所賜四團龍補服，並不得復用雙眼花翎、黃帶、紫轡。及議上，以時捷劾

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-847B512654CC803D8249BD47@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`、`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-F9D274993EFEAF194A59D615@SP-6E9C3B8CE114F78DACB8`
- 理由：隆科多先获兼领理籓院及监修等职，次年被收回服饰特典，属于任职后的明确削权。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`
- 理由：收回服饰特典与此前兼领理籓院、修史任命涉及不同权益，左端未表明撤销右端所授职务，只有人物与时段相近。

### 第三方裁决结果

#### Adjudicator C

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-847B512654CC803D8249BD47@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-D05588EEE4308FAAC5907384@SP-6E9C3B8CE114F78DACB8`、`K0-A-G26I-A-CLMK-D3CECD6B36813D8C0D24-EVD-F9D274993EFEAF194A59D615@SP-6E9C3B8CE114F78DACB8`
- 理由：右端授予的是理籓院兼领及修史监修职务，左端收回的是另行赏赐的服饰特典；证据没有说明这些职务因此被撤销，两端只有同人和相近时段。

---

## 20. `RBC-92189019556268DEDD10`

- 数据集：`g2_6k0_g2_6i_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 6, "value": "隆科多"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 0, "value": "per-d7a0d148728a2905", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`authority_change`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-24D3B7BF1A6C5FDBC7F4`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：收权
- 责任：赏赐特典
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`
  - 时间：雍正三年
  - 命题：胤禛 / 收权 / 隆科多
  - 结果：隆科多被追缴四团龙补服且不得复用双眼花翎、黄带、紫辔
  - 摘要：雍正三年，胤禛因隆科多与年羹尧交结专擅、诸事欺隐，命其缴还所赐服饰特典并不得复用双眼花翎、黄带、紫辔。
  - SourcePassage：`SP-3C5A229F9056917E5728`
- `K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-847B512654CC803D8249BD47@SP-3C5A229F9056917E5728`
  - 时间：雍正三年
  - 命题：胤禛 / 收权 / 隆科多
  - 结果：隆科多被追缴四团龙补服且不得复用双眼花翎、黄带、紫辔
  - 摘要：雍正三年，胤禛因隆科多与年羹尧交结专擅、诸事欺隐，命其缴还所赐服饰特典并不得复用双眼花翎、黄带、紫辔。
  - SourcePassage：`SP-3C5A229F9056917E5728`

#### SourcePassage 原文与上下文

<details><summary><code>SP-3C5A229F9056917E5728</code> · longkodo-liezhuan:375-438</summary>

上文：

> 。次子玉柱，自侍衛授鑾儀使。
> 雍正元年，與川陝總督年羹堯同加太保。
> 二年，兼領理籓院事。纂修《聖祖實錄》、《大清會典》並充總裁，監修《明史》。復與羹堯同賜雙眼花翎、四團龍補服、黃帶、紫轡。
> 三年，解步軍統領。玉柱以行止甚劣，奪官，交隆科多管束。羹堯得罪，上以都統範時捷疏劾欺罔貪婪諸狀，及妄劾道員金南瑛等，並下吏部議處。

原文：

> 上諭曰：「前以隆科多、年羹堯頗著勤勞，予以異數，乃交結專擅，諸事欺隱。」命繳上所賜四團龍補服，並不得復用雙眼花翎、黃帶、紫轡。

下文：

> 及議上，以時捷劾，請罷羹堯任；以妄劾南瑛，請嚴加治罪。上以前議徇庇，後議復過當，責隆科多有意擾亂，削太保及一等阿達哈哈番世職，命往阿蘭善等處修城墾地，諭曰：「朕御極之初，隆科多、年羹堯皆寄以心腹，毫無猜防。孰知朕視為一德，彼竟有二心，招權納賄，擅作威福，欺罔悖負，朕豈能姑息養奸耶？向日明珠、索額圖結黨行私，聖祖解其要職

</details>

### 右端内容

- Episode：`EP-DF748EBD65DF45A1F2E5`
- 人物：per-d7a0d148728a2905
- 角色：["actor", "delegate", "office_holder", "subject"]
- 行为：处置
- 责任：太保、世职、阿兰善修城垦地
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-670D941EBDA7D75198CF793A@SP-B3BE0D6AB5794AAF665D`
  - 时间：雍正三年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被削太保及世职，并被派往阿兰善等处修城垦地
  - 摘要：雍正三年，胤禛责隆科多有意扰乱，削其太保及一等阿达哈哈番世职，并命其往阿兰善等处修城垦地。
  - SourcePassage：`SP-B3BE0D6AB5794AAF665D`
- `K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-88547DF5BB950030B2EF534C@SP-B3BE0D6AB5794AAF665D`
  - 时间：雍正三年
  - 命题：胤禛 / 处置 / 隆科多
  - 结果：隆科多被削太保及世职，并被派往阿兰善等处修城垦地
  - 摘要：雍正三年，胤禛责隆科多有意扰乱，削其太保及一等阿达哈哈番世职，并命其往阿兰善等处修城垦地。
  - SourcePassage：`SP-B3BE0D6AB5794AAF665D`

#### SourcePassage 原文与上下文

<details><summary><code>SP-B3BE0D6AB5794AAF665D</code> · longkodo-liezhuan:465-541</summary>

上文：

> 、紫轡。
> 三年，解步軍統領。玉柱以行止甚劣，奪官，交隆科多管束。羹堯得罪，上以都統範時捷疏劾欺罔貪婪諸狀，及妄劾道員金南瑛等，並下吏部議處。上諭曰：「前以隆科多、年羹堯頗著勤勞，予以異數，乃交結專擅，諸事欺隱。」命繳上所賜四團龍補服，並不得復用雙眼花翎、黃帶、紫轡。及議上，以時捷劾，請罷羹堯任；以妄劾南瑛，請嚴加治罪。

原文：

> 上以前議徇庇，後議復過當，責隆科多有意擾亂，削太保及一等阿達哈哈番世職，命往阿蘭善等處修城墾地，諭曰：「朕御極之初，隆科多、年羹堯皆寄以心腹，毫無猜防。

下文：

> 孰知朕視為一德，彼竟有二心，招權納賄，擅作威福，欺罔悖負，朕豈能姑息養奸耶？向日明珠、索額圖結黨行私，聖祖解其要職，置之閒散，何嘗更加信用？隆科多、年羹堯若不知恐懼，痛改前非，欲如明珠等，萬不能也！殊典不可再邀，覆轍不可屢蹈，各宜警懼，毋自乾誅滅。」
> 四年，隆科多家僕牛倫挾勢索賕，事發，逮下法司，鞫得隆科多受羹堯及總督

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-847B512654CC803D8249BD47@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-670D941EBDA7D75198CF793A@SP-B3BE0D6AB5794AAF665D`、`K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-88547DF5BB950030B2EF534C@SP-B3BE0D6AB5794AAF665D`
- 理由：同在雍正三年的两端分别收回隆科多特典并削太保与世职，属于连续撤权链。

#### Reviewer B

- direct：`yes`
- coarse type：`authority_change`
- evidence refs：`K0-A-G26I-A-CLMK-FA52BAF519D7EC49D5F5-EVD-61C57A7CD4C21E89F81A569A@SP-3C5A229F9056917E5728`、`K0-A-G26I-A-CLMK-E7DBABC04DF832493A5E-EVD-670D941EBDA7D75198CF793A@SP-B3BE0D6AB5794AAF665D`
- 理由：两端同在雍正三年对隆科多实施收回特典、削太保世职并外派的降等处置，构成同一撤权阶段。

---

## 21. `RBC-1CD704BF60E50B7CC781`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 4, "value": "二世"}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-5E0220496AB90354CD27`
- 人物：扶苏/蒙恬安全链|蒙恬
- 角色：["actor"]
- 行为：处置
- 责任：将军处置|蒙恬定罪赐死
- 责任族：`succession_governance`

#### Assertion evidence

- `K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`
  - 时间：二世时
  - 命题：二世使者 / 处置 / 蒙恬
  - 结果：蒙恬吞药自杀
  - 摘要：蒙恬吞药自杀
  - SourcePassage：`SP-83823BFDF4F83A39A3FE`
- `K0-A-CLMK-A8AA0FC70AFDBC8CF32E@SP-3BF160840AD337444F6D`
  - 时间：二世时
  - 命题：二世 / 处置 / 蒙恬
  - 结果：无
  - 摘要：无
  - SourcePassage：`SP-3BF160840AD337444F6D`
- `K0-A-CLMK-E98A9D0388EC3A8C142D@SP-0BAE005F4ACC6553731F`
  - 时间：二世时期
  - 命题：胡亥 / 处置 / 蒙恬
  - 结果：蒙恬吞药自杀
  - 摘要：蒙恬吞药自杀
  - SourcePassage：`SP-0BAE005F4ACC6553731F`

#### SourcePassage 原文与上下文

<details><summary><code>SP-0BAE005F4ACC6553731F</code> · 史記/卷088/蒙恬:1385-1888</summary>

上文：

> 死情實。且夫順成全者，道之所貴也；刑殺者，道之所卒也。昔者秦穆公殺三良而死，罪百里奚而非其罪也，故立號曰『繆』。昭襄王殺武安君白起。楚平王殺伍奢。吳王夫差殺伍子胥。此四君者，皆為大失，而天下非之，以其君為不明，以是籍於諸侯。故曰『用道治者不殺無罪，而罰不加於無辜』。唯大夫留心！」使者知胡亥之意，不聽蒙毅之言，遂殺之。

原文：

> 二世又遣使者之陽周，令蒙恬曰：「君之過多矣，而卿弟毅有大罪，法及內史。」恬曰：「自吾先人，及至子孫，積功信於秦三世矣。今臣將兵三十餘萬，身雖囚系，其勢足以倍畔，然自知必死而守義者，不敢辱先人之教，以不忘先主也。昔周成王初立，未離襁緥周公旦負王以朝，卒定天下。及成王有病甚殆，公旦自揃其爪以沈於河，曰：『王未有識，是旦執事。有罪殃，旦受其不祥。』乃書而藏之記府，可謂信矣。及王能治國，有賊臣言：『周公旦欲為亂久矣，王若不備，必有大事。』王乃大怒，周公旦走而奔於楚。成王觀於記府，得周公旦沈書，乃流涕曰：『孰謂周公旦欲為亂乎！』殺言之者而反周公旦。故《周書》曰『必參而伍之』。今恬之宗，世無二心，而事卒如此，是必孽臣逆亂，內陵之道也。夫成王失而復振則卒昌；桀殺關龍逢，紂殺王子比干而不悔，身死則國亡。臣故曰過可振而諫可覺也。察於參伍，上聖之法也。凡臣之言，非以求免於咎也，將以諫而死，願陛下為萬民思從道也。」使者曰：「臣受詔行法於將軍，不敢以將軍言聞於上也。」蒙恬喟然太息曰：「我何罪於天，無過而死乎？」良久，徐曰：「恬罪固當死矣。起臨洮屬之遼東，城塹萬餘里，此其中不能無絕地脈哉？此乃恬之罪也。」乃吞藥自殺。

下文：

> == 贊 ==
> 太史公曰：吾適北邊，自直道歸，行觀蒙恬所為秦筑長城亭障，塹山堙谷，通直道，固輕百姓力矣。夫秦之初滅諸侯，天下之心未定，痍傷者未瘳，而恬為名將，不以此時彊諫，振百姓之急，養老存孤，務修眾庶之和，而阿意興功，此其兄弟遇誅，不亦宜乎！何乃罪地脈哉？

</details>

<details><summary><code>SP-3BF160840AD337444F6D</code> · 史記/卷088/蒙恬:1385-1420</summary>

上文：

> 死情實。且夫順成全者，道之所貴也；刑殺者，道之所卒也。昔者秦穆公殺三良而死，罪百里奚而非其罪也，故立號曰『繆』。昭襄王殺武安君白起。楚平王殺伍奢。吳王夫差殺伍子胥。此四君者，皆為大失，而天下非之，以其君為不明，以是籍於諸侯。故曰『用道治者不殺無罪，而罰不加於無辜』。唯大夫留心！」使者知胡亥之意，不聽蒙毅之言，遂殺之。

原文：

> 二世又遣使者之陽周，令蒙恬曰：「君之過多矣，而卿弟毅有大罪，法及內史。

下文：

> 」恬曰：「自吾先人，及至子孫，積功信於秦三世矣。今臣將兵三十餘萬，身雖囚系，其勢足以倍畔，然自知必死而守義者，不敢辱先人之教，以不忘先主也。昔周成王初立，未離襁緥周公旦負王以朝，卒定天下。及成王有病甚殆，公旦自揃其爪以沈於河，曰：『王未有識，是旦執事。有罪殃，旦受其不祥。』乃書而藏之記府，可謂信矣。及王能治國，有賊臣言

</details>

<details><summary><code>SP-83823BFDF4F83A39A3FE</code> · 史記/卷088/蒙恬:1786-1888</summary>

上文：

> 旦沈書，乃流涕曰：『孰謂周公旦欲為亂乎！』殺言之者而反周公旦。故《周書》曰『必參而伍之』。今恬之宗，世無二心，而事卒如此，是必孽臣逆亂，內陵之道也。夫成王失而復振則卒昌；桀殺關龍逢，紂殺王子比干而不悔，身死則國亡。臣故曰過可振而諫可覺也。察於參伍，上聖之法也。凡臣之言，非以求免於咎也，將以諫而死，願陛下為萬民思從道也。

原文：

> 」使者曰：「臣受詔行法於將軍，不敢以將軍言聞於上也。」蒙恬喟然太息曰：「我何罪於天，無過而死乎？」良久，徐曰：「恬罪固當死矣。起臨洮屬之遼東，城塹萬餘里，此其中不能無絕地脈哉？此乃恬之罪也。」乃吞藥自殺。

下文：

> == 贊 ==
> 太史公曰：吾適北邊，自直道歸，行觀蒙恬所為秦筑長城亭障，塹山堙谷，通直道，固輕百姓力矣。夫秦之初滅諸侯，天下之心未定，痍傷者未瘳，而恬為名將，不以此時彊諫，振百姓之急，養老存孤，務修眾庶之和，而阿意興功，此其兄弟遇誅，不亦宜乎！何乃罪地脈哉？

</details>

### 右端内容

- Episode：`EP-5FDBD98C7EB596BE8056`
- 人物：李斯
- 角色：["actor"]
- 行为：制度高压
- 责任：督责之术
- 责任族：`institutional_governance`

#### Assertion evidence

- `K0-A-CLMK-7CE141A20E31B5506102@SP-93F1DE20E068869243A2`
  - 时间：群盗西略地、三川受案后
  - 命题：李斯 / 制度高压 / 二世
  - 结果：以书对曰贤主必行督责之术
  - 摘要：以书对曰贤主必行督责之术
  - SourcePassage：`SP-93F1DE20E068869243A2`

#### SourcePassage 原文与上下文

<details><summary><code>SP-93F1DE20E068869243A2</code> · 史記/卷087/李斯:5015-5123</summary>

上文：

> 遂以死于外，葬於會稽，臣虜之勞不烈於此矣』。然則夫所貴於有天下者，豈欲苦形勞神，身處逆旅之宿，口食監門之養，手持臣虜之作哉？此不肖人之所勉也，非賢者之所務也。彼賢人之有天下也，專用天下適己而已矣，此所貴於有天下也。夫所謂賢人者，必能安天下而治萬民，今身且不能利，將惡能治天下哉！故吾願賜志廣欲，長享天下而無害，為之奈何？

原文：

> 」李斯子由為三川守，群盜吳廣等西略地，過去弗能禁。章邯以破逐廣等兵，使者覆案三川相屬，誚讓斯居三公位，如何令盜如此。李斯恐懼，重爵祿，不知所出，乃阿二世意，欲求容，以書對曰：
>
> 夫賢主者，必且能全道而行督責之術者也。

下文：

> 督責之，則臣不敢不竭能以徇其主矣。此臣主之分定，上下之義明，則天下賢不肖莫敢不盡力竭任以徇其君矣。是故主獨制於天下而無所制也。能窮樂之極矣，賢明之主也，可不察焉！
> 故《申子》曰「有天下而不恣睢，命之曰以天下為桎梏」者，無他焉，不能督責，而顧以其身勞於天下之民，若堯、禹然，故謂之「桎梏」也。夫不能修申、韓之明術，行督責之

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`、`K0-A-CLMK-A8AA0FC70AFDBC8CF32E@SP-3BF160840AD337444F6D`、`K0-A-CLMK-E98A9D0388EC3A8C142D@SP-0BAE005F4ACC6553731F`、`K0-A-CLMK-7CE141A20E31B5506102@SP-93F1DE20E068869243A2`
- 理由：蒙恬被迫自杀与李斯提出督责之术涉及不同人物和处置背景，没有直接授权、结果或因果连接。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`、`K0-A-CLMK-7CE141A20E31B5506102@SP-93F1DE20E068869243A2`
- 理由：蒙恬被赐死与李斯因三川失守而迎合二世提出督责之术，是不同人物和事件，只有二世这一共同背景。

---

## 22. `RBC-36F8ADB0F1815D3DEDB1`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 3, "value": "炀帝"}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-458EFC35C6D1DD5F97C8`
- 人物：贺若弼
- 角色：["actor"]
- 行为：处置
- 责任：北巡榆林议政言论
- 责任族：`judicial_governance`

#### Assertion evidence

- `K0-A-CLMK-B3165927D41140E61B4C@SP-A17361F6C14FEAA2AD3D`
  - 时间：大业三年从驾北巡至榆林
  - 命题：炀帝 / 处置 / 贺若弼
  - 结果：竟坐诛；妻子为官奴婢，群从徙边
  - 摘要：竟坐诛；妻子为官奴婢，群从徙边
  - SourcePassage：`SP-A17361F6C14FEAA2AD3D`

#### SourcePassage 原文与上下文

<details><summary><code>SP-A17361F6C14FEAA2AD3D</code> · 隋書/卷52/賀若弼:3783-3867</summary>

上文：

> 破的。如其不然，發不中也。」既射，一發而中。上大悅，顧謂突厥曰：「此人天賜我也！」
> 煬帝之在東宮，嘗謂弼曰：「楊素、韓擒虎、史萬歲三人，俱稱良將，優劣如何？」弼曰：「楊素是猛將，非謀將；韓擒虎是鬥將，非領將；史萬歲是騎將，非大將。」太子曰：「然則大將誰也？」弼拜曰：「唯殿下所擇。」弼意自許為大將。及煬帝嗣位，尤被疏忌。

原文：

> 大業三年，從駕北巡，至榆林。帝時為大帳，其下可坐數千人，召突厥啟民可汗饗之。弼以為大侈，與高熲、宇文弼等私議得失，為人所奏，竟坐誅，時年六十四。妻子為官奴婢，群從徙邊。

下文：

> 子懷亮，慷慨有父風，以柱國世子拜儀同三司。坐弼為奴，俄亦誅死。
>
>
> == 【論】 ==
> 史臣曰：夫天地未泰，聖哲啟其機；疆埸尚梗，爪牙宣其力。周之方、邵，漢室韓、彭，代有其人，非一時也。自晉衰微，中原幅裂，區宇分隔，將三百年。陳氏憑長江之地險，恃金陵之餘氣，以為天限南北，人莫能窺。高祖爰應千齡，將一函夏。賀若弼慷慨，

</details>

### 右端内容

- Episode：`EP-55CE65C6275D0EFB6900`
- 人物：萧瑀
- 角色：["actor"]
- 行为：处置
- 责任：河池郡守
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-CLMK-B0022EC5A6D8E05A7E99@SP-5215CAC03679EA364630`
  - 时间：炀帝又将伐辽东时
  - 命题：炀帝 / 处置 / 萧瑀
  - 结果：出为河池郡守，即日遣之
  - 摘要：出为河池郡守，即日遣之
  - SourcePassage：`SP-5215CAC03679EA364630`

#### SourcePassage 原文与上下文

<details><summary><code>SP-5215CAC03679EA364630</code> · 舊唐書/卷63/蕭瑀:2293-2352</summary>

上文：

> 帝女為妻，必恃大國之援。若發一單使以告義成，假使無益，事亦無損。臣又竊聽輿人之誦，乃慮陛下平突厥後更事遼東，所以人心不一，或致挫敗。請下明詔告軍中，赦高麗而專攻突厥，則百姓心安，人自為戰。」煬帝從之，於是發使詣可賀敦諭旨。俄而突厥解圍去，於後獲其諜人，云：義成公主遣使告急於始畢，稱北方有警，由是突厥解圍，蓋公主之助也。

原文：

> 煬帝又將伐遼東，謂群臣曰：「突厥狂悖為寇，勢何能為？以其少時未散，蕭瑀遂相恐動，情不可恕。」因出為河池郡守，即日遣之。

下文：

> 既至郡，有山賊萬餘人寇暴縱橫，瑀潛募勇敢之士，設奇而擊之，當陣而降其眾。所獲財畜，咸賞有功，由是人竭其力。薛舉遣眾數萬侵掠郡境，瑀要擊之，自後諸賊莫敢進，郡中復安。
> 高祖定京城，遣書招之。瑀以郡歸國，授光祿大夫，封宋國公，拜民部尚書。太宗為右元帥，攻洛陽，以瑀為府司馬。武德五年，遷內史令。時軍國草創，方隅未寧，高祖乃委

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-B3165927D41140E61B4C@SP-A17361F6C14FEAA2AD3D`、`K0-A-CLMK-B0022EC5A6D8E05A7E99@SP-5215CAC03679EA364630`
- 理由：贺若弼因议论被诛与萧瑀因突厥判断被外放是不同人物、不同案由，只有同一皇帝背景。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-B3165927D41140E61B4C@SP-A17361F6C14FEAA2AD3D`、`K0-A-CLMK-B0022EC5A6D8E05A7E99@SP-5215CAC03679EA364630`
- 理由：贺若弼因私议被诛与萧瑀因辽东、突厥意见被外放，处分对象和缘由不同，共同君主不构成直接关系。

---

## 23. `RBC-3CFA424F9AA7266B5112`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 4, "value": "二世"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 0, "value": "李斯", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-5CE40AD5E4942178A262`
- 人物：李斯
- 角色：["actor"]
- 行为：处置
- 责任：丞相狱
- 责任族：`judicial_governance`

#### Assertion evidence

- `K0-A-CLMK-0121E2ABA7446A10B58C@SP-3642DF9CB0F2607DE5A8`
  - 时间：李斯言赵高后
  - 命题：二世 / 处置 / 李斯
  - 结果：责斯与子由谋反，皆收捕宗族宾客；李斯自诬服
  - 摘要：责斯与子由谋反，皆收捕宗族宾客；李斯自诬服
  - SourcePassage：`SP-3642DF9CB0F2607DE5A8`

#### SourcePassage 原文与上下文

<details><summary><code>SP-3642DF9CB0F2607DE5A8</code> · 史記/卷087/李斯:7356-7715</summary>

上文：

> 君又老，恐與天下絕矣。朕非屬趙君，當誰任哉？且趙君為人精廉彊力，下知人情，上能適朕，君其勿疑。」李斯曰：「不然。夫高，故賤人也，無識於理，貪欲無厭，求利不止，列勢次主，求欲無窮，臣故曰殆。」二世已前信趙高，恐李斯殺之，乃私告趙高。高曰：「丞相所患者獨高，高已死，丞相即欲為田常所為。」於是二世曰：「其以李斯屬郎中令！」

原文：

> 趙高案治李斯。李斯拘執束縛，居囹圄中，仰天而歎曰：「嗟乎，悲夫！不道之君，何可為計哉！昔者桀殺關龍逢，紂殺王子比干，吳王夫差殺伍子胥。此三臣者，豈不忠哉，然而不免於死，身死而所忠者非也。今吾智不及三子，而二世之無道過於桀、紂、夫差，吾以忠死，宜矣。且二世之治豈不亂哉！日者夷其兄弟而自立也，殺忠臣而貴賤人，作為阿房之宮，賦斂天下。吾非不諫也，而不吾聽也。凡古聖王，飲食有節，車器有數，宮室有度，出令造事，加費而無益於民利者禁，故能長久治安。今行逆於昆弟，不顧其咎；侵殺忠臣，不思其殃；大為宮室，厚賦天下，不愛其費：三者已行，天下不聽。今反者已有天下之半矣，而心尚未寤也，而以趙高為佐，吾必見寇至咸陽，麋鹿游於朝也。」
> 於是二世乃使高案丞相獄，治罪，責斯與子由謀反狀，皆收捕宗族賓客。趙高治斯，榜掠千餘，不勝痛，自誣服。

下文：

> 斯所以不死者，自負其辯，有功，實無反心，幸得上書自陳，幸二世之寤而赦之。李斯乃從獄中上書曰：「臣為丞相治民，三十餘年矣。逮秦地之狹隘。先王之時秦地不過千里，兵數十萬。臣盡薄材，謹奉法令，陰行謀臣，資之金玉，使游說諸侯，陰修甲兵，飾政敎，官鬬士，尊功臣，盛其爵祿，故終以脅韓弱魏，破燕、趙，夷齊、楚，卒兼六國，虜其王，立秦

</details>

### 右端内容

- Episode：`EP-5FDBD98C7EB596BE8056`
- 人物：李斯
- 角色：["actor"]
- 行为：制度高压
- 责任：督责之术
- 责任族：`institutional_governance`

#### Assertion evidence

- `K0-A-CLMK-7CE141A20E31B5506102@SP-93F1DE20E068869243A2`
  - 时间：群盗西略地、三川受案后
  - 命题：李斯 / 制度高压 / 二世
  - 结果：以书对曰贤主必行督责之术
  - 摘要：以书对曰贤主必行督责之术
  - SourcePassage：`SP-93F1DE20E068869243A2`

#### SourcePassage 原文与上下文

<details><summary><code>SP-93F1DE20E068869243A2</code> · 史記/卷087/李斯:5015-5123</summary>

上文：

> 遂以死于外，葬於會稽，臣虜之勞不烈於此矣』。然則夫所貴於有天下者，豈欲苦形勞神，身處逆旅之宿，口食監門之養，手持臣虜之作哉？此不肖人之所勉也，非賢者之所務也。彼賢人之有天下也，專用天下適己而已矣，此所貴於有天下也。夫所謂賢人者，必能安天下而治萬民，今身且不能利，將惡能治天下哉！故吾願賜志廣欲，長享天下而無害，為之奈何？

原文：

> 」李斯子由為三川守，群盜吳廣等西略地，過去弗能禁。章邯以破逐廣等兵，使者覆案三川相屬，誚讓斯居三公位，如何令盜如此。李斯恐懼，重爵祿，不知所出，乃阿二世意，欲求容，以書對曰：
>
> 夫賢主者，必且能全道而行督責之術者也。

下文：

> 督責之，則臣不敢不竭能以徇其主矣。此臣主之分定，上下之義明，則天下賢不肖莫敢不盡力竭任以徇其君矣。是故主獨制於天下而無所制也。能窮樂之極矣，賢明之主也，可不察焉！
> 故《申子》曰「有天下而不恣睢，命之曰以天下為桎梏」者，無他焉，不能督責，而顧以其身勞於天下之民，若堯、禹然，故謂之「桎梏」也。夫不能修申、韓之明術，行督責之

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-0121E2ABA7446A10B58C@SP-3642DF9CB0F2607DE5A8`、`K0-A-CLMK-7CE141A20E31B5506102@SP-93F1DE20E068869243A2`
- 理由：李斯提出督责术以求容与其后来因赵高构陷被案治是不同事由，端点证据没有直接因果说明。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-0121E2ABA7446A10B58C@SP-3642DF9CB0F2607DE5A8`、`K0-A-CLMK-7CE141A20E31B5506102@SP-93F1DE20E068869243A2`
- 理由：李斯提出督责之术源于三川失守后的自保，而其后下狱源于赵高案治和谋反指控，端点未建立直接因果。

---

## 24. `RBC-5D19AB679BC2CF8E45CD`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 4, "value": "二世"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 1, "value": "李斯", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-362E0408FC54A0F23960`
- 人物：李斯
- 角色：["actor"]
- 行为：拒谏
- 责任：乱后朝政谏议
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-CLMK-49DE200FD2F366DDEE24@SP-EBC26E1125322A3E2496`
  - 时间：陈胜吴广作乱后
  - 命题：李斯 / 拒谏 / 二世
  - 结果：二世不许
  - 摘要：二世不许
  - SourcePassage：`SP-EBC26E1125322A3E2496`

#### SourcePassage 原文与上下文

<details><summary><code>SP-EBC26E1125322A3E2496</code> · 史記/卷087/李斯:4661-4715</summary>

上文：

> ，臣得賜之。臣當從死而不能，為人子不孝，為人臣不忠。不忠者無名以立於世，臣請從死，願葬酈山之足。唯上幸哀憐之。」書上，胡亥大說，召趙高而示之，曰：「此可謂急乎？」趙高曰：「人臣當憂死而不暇，何變之得謀！」胡亥可其書，賜錢十萬以葬。
> 法令誅罰日益刻深，羣臣人人自危，欲畔者眾。又作阿房之宮，治直、馳道，賦斂愈重，戍徭無已。

原文：

> 於是楚戍卒陳勝、吳廣等乃作亂，起於山東，傑俊相立，自置為侯王，叛秦，兵至鴻門而卻。李斯數欲請間諫，二世不許。

下文：

> 而二世責問李斯曰：「吾有私議而有所聞於韓子也，曰『堯之有天下也，堂高三尺，采椽不斲，茅茨不翦，雖逆旅之宿不勤於此矣。冬日鹿裘，夏日葛衣，粢糲之食，藜藿之羹，飯土匭，啜土鉶，雖監門之養不觳於此矣。禹鑿龍門，通大夏，疏九河，曲九防，決渟水致之海，而股無胈，脛無毛，手足胼胝，面目黎黑，遂以死于外，葬於會稽，臣虜之勞不烈於此矣

</details>

### 右端内容

- Episode：`EP-5FDBD98C7EB596BE8056`
- 人物：李斯
- 角色：["actor"]
- 行为：制度高压
- 责任：督责之术
- 责任族：`institutional_governance`

#### Assertion evidence

- `K0-A-CLMK-7CE141A20E31B5506102@SP-93F1DE20E068869243A2`
  - 时间：群盗西略地、三川受案后
  - 命题：李斯 / 制度高压 / 二世
  - 结果：以书对曰贤主必行督责之术
  - 摘要：以书对曰贤主必行督责之术
  - SourcePassage：`SP-93F1DE20E068869243A2`

#### SourcePassage 原文与上下文

<details><summary><code>SP-93F1DE20E068869243A2</code> · 史記/卷087/李斯:5015-5123</summary>

上文：

> 遂以死于外，葬於會稽，臣虜之勞不烈於此矣』。然則夫所貴於有天下者，豈欲苦形勞神，身處逆旅之宿，口食監門之養，手持臣虜之作哉？此不肖人之所勉也，非賢者之所務也。彼賢人之有天下也，專用天下適己而已矣，此所貴於有天下也。夫所謂賢人者，必能安天下而治萬民，今身且不能利，將惡能治天下哉！故吾願賜志廣欲，長享天下而無害，為之奈何？

原文：

> 」李斯子由為三川守，群盜吳廣等西略地，過去弗能禁。章邯以破逐廣等兵，使者覆案三川相屬，誚讓斯居三公位，如何令盜如此。李斯恐懼，重爵祿，不知所出，乃阿二世意，欲求容，以書對曰：
>
> 夫賢主者，必且能全道而行督責之術者也。

下文：

> 督責之，則臣不敢不竭能以徇其主矣。此臣主之分定，上下之義明，則天下賢不肖莫敢不盡力竭任以徇其君矣。是故主獨制於天下而無所制也。能窮樂之極矣，賢明之主也，可不察焉！
> 故《申子》曰「有天下而不恣睢，命之曰以天下為桎梏」者，無他焉，不能督責，而顧以其身勞於天下之民，若堯、禹然，故謂之「桎梏」也。夫不能修申、韓之明術，行督責之

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-49DE200FD2F366DDEE24@SP-EBC26E1125322A3E2496`、`K0-A-CLMK-7CE141A20E31B5506102@SP-93F1DE20E068869243A2`
- 理由：二世拒绝李斯求间进谏与李斯后来因三川受责而迎合督责术，端点未明示直接承接。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-49DE200FD2F366DDEE24@SP-EBC26E1125322A3E2496`、`K0-A-CLMK-7CE141A20E31B5506102@SP-93F1DE20E068869243A2`
- 理由：李斯求谏被拒与其后因三川案恐惧而迎合督责虽同处乱事背景，但证据没有表明前端直接导致后端。

---

## 25. `RBC-75DC5C0C3014F3A3F0B1`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 4, "value": "二世"}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-362E0408FC54A0F23960`
- 人物：李斯
- 角色：["actor"]
- 行为：拒谏
- 责任：乱后朝政谏议
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-CLMK-49DE200FD2F366DDEE24@SP-EBC26E1125322A3E2496`
  - 时间：陈胜吴广作乱后
  - 命题：李斯 / 拒谏 / 二世
  - 结果：二世不许
  - 摘要：二世不许
  - SourcePassage：`SP-EBC26E1125322A3E2496`

#### SourcePassage 原文与上下文

<details><summary><code>SP-EBC26E1125322A3E2496</code> · 史記/卷087/李斯:4661-4715</summary>

上文：

> ，臣得賜之。臣當從死而不能，為人子不孝，為人臣不忠。不忠者無名以立於世，臣請從死，願葬酈山之足。唯上幸哀憐之。」書上，胡亥大說，召趙高而示之，曰：「此可謂急乎？」趙高曰：「人臣當憂死而不暇，何變之得謀！」胡亥可其書，賜錢十萬以葬。
> 法令誅罰日益刻深，羣臣人人自危，欲畔者眾。又作阿房之宮，治直、馳道，賦斂愈重，戍徭無已。

原文：

> 於是楚戍卒陳勝、吳廣等乃作亂，起於山東，傑俊相立，自置為侯王，叛秦，兵至鴻門而卻。李斯數欲請間諫，二世不許。

下文：

> 而二世責問李斯曰：「吾有私議而有所聞於韓子也，曰『堯之有天下也，堂高三尺，采椽不斲，茅茨不翦，雖逆旅之宿不勤於此矣。冬日鹿裘，夏日葛衣，粢糲之食，藜藿之羹，飯土匭，啜土鉶，雖監門之養不觳於此矣。禹鑿龍門，通大夏，疏九河，曲九防，決渟水致之海，而股無胈，脛無毛，手足胼胝，面目黎黑，遂以死于外，葬於會稽，臣虜之勞不烈於此矣

</details>

### 右端内容

- Episode：`EP-5E0220496AB90354CD27`
- 人物：扶苏/蒙恬安全链|蒙恬
- 角色：["actor"]
- 行为：处置
- 责任：将军处置|蒙恬定罪赐死
- 责任族：`succession_governance`

#### Assertion evidence

- `K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`
  - 时间：二世时
  - 命题：二世使者 / 处置 / 蒙恬
  - 结果：蒙恬吞药自杀
  - 摘要：蒙恬吞药自杀
  - SourcePassage：`SP-83823BFDF4F83A39A3FE`
- `K0-A-CLMK-A8AA0FC70AFDBC8CF32E@SP-3BF160840AD337444F6D`
  - 时间：二世时
  - 命题：二世 / 处置 / 蒙恬
  - 结果：无
  - 摘要：无
  - SourcePassage：`SP-3BF160840AD337444F6D`
- `K0-A-CLMK-E98A9D0388EC3A8C142D@SP-0BAE005F4ACC6553731F`
  - 时间：二世时期
  - 命题：胡亥 / 处置 / 蒙恬
  - 结果：蒙恬吞药自杀
  - 摘要：蒙恬吞药自杀
  - SourcePassage：`SP-0BAE005F4ACC6553731F`

#### SourcePassage 原文与上下文

<details><summary><code>SP-0BAE005F4ACC6553731F</code> · 史記/卷088/蒙恬:1385-1888</summary>

上文：

> 死情實。且夫順成全者，道之所貴也；刑殺者，道之所卒也。昔者秦穆公殺三良而死，罪百里奚而非其罪也，故立號曰『繆』。昭襄王殺武安君白起。楚平王殺伍奢。吳王夫差殺伍子胥。此四君者，皆為大失，而天下非之，以其君為不明，以是籍於諸侯。故曰『用道治者不殺無罪，而罰不加於無辜』。唯大夫留心！」使者知胡亥之意，不聽蒙毅之言，遂殺之。

原文：

> 二世又遣使者之陽周，令蒙恬曰：「君之過多矣，而卿弟毅有大罪，法及內史。」恬曰：「自吾先人，及至子孫，積功信於秦三世矣。今臣將兵三十餘萬，身雖囚系，其勢足以倍畔，然自知必死而守義者，不敢辱先人之教，以不忘先主也。昔周成王初立，未離襁緥周公旦負王以朝，卒定天下。及成王有病甚殆，公旦自揃其爪以沈於河，曰：『王未有識，是旦執事。有罪殃，旦受其不祥。』乃書而藏之記府，可謂信矣。及王能治國，有賊臣言：『周公旦欲為亂久矣，王若不備，必有大事。』王乃大怒，周公旦走而奔於楚。成王觀於記府，得周公旦沈書，乃流涕曰：『孰謂周公旦欲為亂乎！』殺言之者而反周公旦。故《周書》曰『必參而伍之』。今恬之宗，世無二心，而事卒如此，是必孽臣逆亂，內陵之道也。夫成王失而復振則卒昌；桀殺關龍逢，紂殺王子比干而不悔，身死則國亡。臣故曰過可振而諫可覺也。察於參伍，上聖之法也。凡臣之言，非以求免於咎也，將以諫而死，願陛下為萬民思從道也。」使者曰：「臣受詔行法於將軍，不敢以將軍言聞於上也。」蒙恬喟然太息曰：「我何罪於天，無過而死乎？」良久，徐曰：「恬罪固當死矣。起臨洮屬之遼東，城塹萬餘里，此其中不能無絕地脈哉？此乃恬之罪也。」乃吞藥自殺。

下文：

> == 贊 ==
> 太史公曰：吾適北邊，自直道歸，行觀蒙恬所為秦筑長城亭障，塹山堙谷，通直道，固輕百姓力矣。夫秦之初滅諸侯，天下之心未定，痍傷者未瘳，而恬為名將，不以此時彊諫，振百姓之急，養老存孤，務修眾庶之和，而阿意興功，此其兄弟遇誅，不亦宜乎！何乃罪地脈哉？

</details>

<details><summary><code>SP-3BF160840AD337444F6D</code> · 史記/卷088/蒙恬:1385-1420</summary>

上文：

> 死情實。且夫順成全者，道之所貴也；刑殺者，道之所卒也。昔者秦穆公殺三良而死，罪百里奚而非其罪也，故立號曰『繆』。昭襄王殺武安君白起。楚平王殺伍奢。吳王夫差殺伍子胥。此四君者，皆為大失，而天下非之，以其君為不明，以是籍於諸侯。故曰『用道治者不殺無罪，而罰不加於無辜』。唯大夫留心！」使者知胡亥之意，不聽蒙毅之言，遂殺之。

原文：

> 二世又遣使者之陽周，令蒙恬曰：「君之過多矣，而卿弟毅有大罪，法及內史。

下文：

> 」恬曰：「自吾先人，及至子孫，積功信於秦三世矣。今臣將兵三十餘萬，身雖囚系，其勢足以倍畔，然自知必死而守義者，不敢辱先人之教，以不忘先主也。昔周成王初立，未離襁緥周公旦負王以朝，卒定天下。及成王有病甚殆，公旦自揃其爪以沈於河，曰：『王未有識，是旦執事。有罪殃，旦受其不祥。』乃書而藏之記府，可謂信矣。及王能治國，有賊臣言

</details>

<details><summary><code>SP-83823BFDF4F83A39A3FE</code> · 史記/卷088/蒙恬:1786-1888</summary>

上文：

> 旦沈書，乃流涕曰：『孰謂周公旦欲為亂乎！』殺言之者而反周公旦。故《周書》曰『必參而伍之』。今恬之宗，世無二心，而事卒如此，是必孽臣逆亂，內陵之道也。夫成王失而復振則卒昌；桀殺關龍逢，紂殺王子比干而不悔，身死則國亡。臣故曰過可振而諫可覺也。察於參伍，上聖之法也。凡臣之言，非以求免於咎也，將以諫而死，願陛下為萬民思從道也。

原文：

> 」使者曰：「臣受詔行法於將軍，不敢以將軍言聞於上也。」蒙恬喟然太息曰：「我何罪於天，無過而死乎？」良久，徐曰：「恬罪固當死矣。起臨洮屬之遼東，城塹萬餘里，此其中不能無絕地脈哉？此乃恬之罪也。」乃吞藥自殺。

下文：

> == 贊 ==
> 太史公曰：吾適北邊，自直道歸，行觀蒙恬所為秦筑長城亭障，塹山堙谷，通直道，固輕百姓力矣。夫秦之初滅諸侯，天下之心未定，痍傷者未瘳，而恬為名將，不以此時彊諫，振百姓之急，養老存孤，務修眾庶之和，而阿意興功，此其兄弟遇誅，不亦宜乎！何乃罪地脈哉？

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-49DE200FD2F366DDEE24@SP-EBC26E1125322A3E2496`、`K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`、`K0-A-CLMK-A8AA0FC70AFDBC8CF32E@SP-3BF160840AD337444F6D`、`K0-A-CLMK-E98A9D0388EC3A8C142D@SP-0BAE005F4ACC6553731F`
- 理由：李斯求谏被拒与蒙恬被迫自杀涉及不同人物和事件，仅共享秦二世时期背景。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-49DE200FD2F366DDEE24@SP-EBC26E1125322A3E2496`、`K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`
- 理由：二世拒绝李斯就陈胜吴广之乱进谏与处死蒙恬分属不同人物、时点和政务链，端点没有直接联系。

---

## 26. `RBC-89447FA5AFE1C41D6119`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 0, "value": "李斯", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`mandate_or_outcome`
- 是否经裁决：`yes`

### 左端内容

- Episode：`EP-5CE40AD5E4942178A262`
- 人物：李斯
- 角色：["actor"]
- 行为：处置
- 责任：丞相狱
- 责任族：`judicial_governance`

#### Assertion evidence

- `K0-A-CLMK-0121E2ABA7446A10B58C@SP-3642DF9CB0F2607DE5A8`
  - 时间：李斯言赵高后
  - 命题：二世 / 处置 / 李斯
  - 结果：责斯与子由谋反，皆收捕宗族宾客；李斯自诬服
  - 摘要：责斯与子由谋反，皆收捕宗族宾客；李斯自诬服
  - SourcePassage：`SP-3642DF9CB0F2607DE5A8`

#### SourcePassage 原文与上下文

<details><summary><code>SP-3642DF9CB0F2607DE5A8</code> · 史記/卷087/李斯:7356-7715</summary>

上文：

> 君又老，恐與天下絕矣。朕非屬趙君，當誰任哉？且趙君為人精廉彊力，下知人情，上能適朕，君其勿疑。」李斯曰：「不然。夫高，故賤人也，無識於理，貪欲無厭，求利不止，列勢次主，求欲無窮，臣故曰殆。」二世已前信趙高，恐李斯殺之，乃私告趙高。高曰：「丞相所患者獨高，高已死，丞相即欲為田常所為。」於是二世曰：「其以李斯屬郎中令！」

原文：

> 趙高案治李斯。李斯拘執束縛，居囹圄中，仰天而歎曰：「嗟乎，悲夫！不道之君，何可為計哉！昔者桀殺關龍逢，紂殺王子比干，吳王夫差殺伍子胥。此三臣者，豈不忠哉，然而不免於死，身死而所忠者非也。今吾智不及三子，而二世之無道過於桀、紂、夫差，吾以忠死，宜矣。且二世之治豈不亂哉！日者夷其兄弟而自立也，殺忠臣而貴賤人，作為阿房之宮，賦斂天下。吾非不諫也，而不吾聽也。凡古聖王，飲食有節，車器有數，宮室有度，出令造事，加費而無益於民利者禁，故能長久治安。今行逆於昆弟，不顧其咎；侵殺忠臣，不思其殃；大為宮室，厚賦天下，不愛其費：三者已行，天下不聽。今反者已有天下之半矣，而心尚未寤也，而以趙高為佐，吾必見寇至咸陽，麋鹿游於朝也。」
> 於是二世乃使高案丞相獄，治罪，責斯與子由謀反狀，皆收捕宗族賓客。趙高治斯，榜掠千餘，不勝痛，自誣服。

下文：

> 斯所以不死者，自負其辯，有功，實無反心，幸得上書自陳，幸二世之寤而赦之。李斯乃從獄中上書曰：「臣為丞相治民，三十餘年矣。逮秦地之狹隘。先王之時秦地不過千里，兵數十萬。臣盡薄材，謹奉法令，陰行謀臣，資之金玉，使游說諸侯，陰修甲兵，飾政敎，官鬬士，尊功臣，盛其爵祿，故終以脅韓弱魏，破燕、趙，夷齊、楚，卒兼六國，虜其王，立秦

</details>

### 右端内容

- Episode：`EP-E41130F575665A62A1C6`
- 人物：李斯
- 角色：["actor"]
- 行为：处置
- 责任：赵高擅权争议
- 责任族：`judicial_governance`

#### Assertion evidence

- `K0-A-CLMK-255582327C35CE5D5CAF@SP-2DE11D85885A0E9FC1F6`
  - 时间：二世在甘泉时
  - 命题：李斯 / 处置 / 赵高
  - 结果：二世以李斯属郎中令，赵高案治李斯
  - 摘要：二世以李斯属郎中令，赵高案治李斯
  - SourcePassage：`SP-2DE11D85885A0E9FC1F6`

#### SourcePassage 原文与上下文

<details><summary><code>SP-2DE11D85885A0E9FC1F6</code> · 史記/卷087/李斯:6882-7354</summary>

上文：

> 立為帝，而丞相貴不益，此其意亦望裂地而王矣。且陛下不問臣，臣不敢言。丞相長男李由為三川守，楚盜陳勝等皆丞相傍縣之子，以故楚盜公行，過三川，城守不肯擊。高聞其文書相往來，未得其審，故未敢以聞。且丞相居外，權重於陛下。」二世以為然。欲案丞相，恐其不審，乃使人案驗三川守與盜通狀。李斯聞之。
> 是時二世在甘泉，方作觳抵優俳之觀。

原文：

> 李斯不得見，因上書言趙高之短曰：「臣聞之，臣疑其君，無不危國；妾疑其夫，無不危家。今有大臣於陛下擅利擅害，與陛下無異，此甚不便。昔者司城子罕相宋，身行刑罰，以威行之，朞年遂劫其君。田常為簡公臣，爵列無敵於國，私家之富與公家均，布惠施德，下得百姓，上得群臣，陰取齊國，殺宰予於庭，即弑簡公於朝，遂有齊國。此天下所明知也。今高有邪佚之志，危反之行，如子罕相宋也；私家之富，若田氏之於齊也。兼行田常、子罕之逆道而劫陛下之威信，其志若韓玘為韓安相也。陛下不圖，臣恐其為變也。」二世曰：「何哉？夫高，故宦人也，然不為安肆志，不以危易心，潔行修善，自使至此，以忠得進，以信守位，朕實賢之，而君疑之，何也？且朕少失先人，無所識知，不習治民，而君又老，恐與天下絕矣。朕非屬趙君，當誰任哉？且趙君為人精廉彊力，下知人情，上能適朕，君其勿疑。」李斯曰：「不然。夫高，故賤人也，無識於理，貪欲無厭，求利不止，列勢次主，求欲無窮，臣故曰殆。」二世已前信趙高，恐李斯殺之，乃私告趙高。高曰：「丞相所患者獨高，高已死，丞相即欲為田常所為。」於是二世曰：「其以李斯屬郎中令！

下文：

> 」
> 趙高案治李斯。李斯拘執束縛，居囹圄中，仰天而歎曰：「嗟乎，悲夫！不道之君，何可為計哉！昔者桀殺關龍逢，紂殺王子比干，吳王夫差殺伍子胥。此三臣者，豈不忠哉，然而不免於死，身死而所忠者非也。今吾智不及三子，而二世之無道過於桀、紂、夫差，吾以忠死，宜矣。且二世之治豈不亂哉！日者夷其兄弟而自立也，殺忠臣而貴賤人，作為阿房之

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-CLMK-0121E2ABA7446A10B58C@SP-3642DF9CB0F2607DE5A8`、`K0-A-CLMK-255582327C35CE5D5CAF@SP-2DE11D85885A0E9FC1F6`
- 理由：二世先将李斯交郎中令赵高办理，随后赵高即案治李斯并逼其自诬服，是同一处置授权的执行结果。

#### Reviewer B

- direct：`yes`
- coarse type：`explicit_causal`
- evidence refs：`K0-A-CLMK-0121E2ABA7446A10B58C@SP-3642DF9CB0F2607DE5A8`、`K0-A-CLMK-255582327C35CE5D5CAF@SP-2DE11D85885A0E9FC1F6`
- 理由：李斯上书指陈赵高后，二世明确把李斯交赵高处理；随后赵高案治并逼其自诬，证据形成直接因果链。

### 第三方裁决结果

#### Adjudicator C

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-CLMK-0121E2ABA7446A10B58C@SP-3642DF9CB0F2607DE5A8`、`K0-A-CLMK-255582327C35CE5D5CAF@SP-2DE11D85885A0E9FC1F6`
- 理由：右端记载二世明确将李斯交郎中令赵高处理，左端随即记载赵高奉命审理丞相狱、刑讯并使李斯自诬服，是同一处置命令的直接执行结果。

---

## 27. `RBC-8B1E55DE8767E64EE683`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 2, "value": "胡亥"}, {"blocking_signal": "shared_selective_endpoint_entity", "context_episode_frequency": 2, "value": "蒙恬"}, {"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 0, "value": "扶苏/蒙恬安全链|蒙恬", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`mandate_or_outcome`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-5E0220496AB90354CD27`
- 人物：扶苏/蒙恬安全链|蒙恬
- 角色：["actor"]
- 行为：处置
- 责任：将军处置|蒙恬定罪赐死
- 责任族：`succession_governance`

#### Assertion evidence

- `K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`
  - 时间：二世时
  - 命题：二世使者 / 处置 / 蒙恬
  - 结果：蒙恬吞药自杀
  - 摘要：蒙恬吞药自杀
  - SourcePassage：`SP-83823BFDF4F83A39A3FE`
- `K0-A-CLMK-A8AA0FC70AFDBC8CF32E@SP-3BF160840AD337444F6D`
  - 时间：二世时
  - 命题：二世 / 处置 / 蒙恬
  - 结果：无
  - 摘要：无
  - SourcePassage：`SP-3BF160840AD337444F6D`
- `K0-A-CLMK-E98A9D0388EC3A8C142D@SP-0BAE005F4ACC6553731F`
  - 时间：二世时期
  - 命题：胡亥 / 处置 / 蒙恬
  - 结果：蒙恬吞药自杀
  - 摘要：蒙恬吞药自杀
  - SourcePassage：`SP-0BAE005F4ACC6553731F`

#### SourcePassage 原文与上下文

<details><summary><code>SP-0BAE005F4ACC6553731F</code> · 史記/卷088/蒙恬:1385-1888</summary>

上文：

> 死情實。且夫順成全者，道之所貴也；刑殺者，道之所卒也。昔者秦穆公殺三良而死，罪百里奚而非其罪也，故立號曰『繆』。昭襄王殺武安君白起。楚平王殺伍奢。吳王夫差殺伍子胥。此四君者，皆為大失，而天下非之，以其君為不明，以是籍於諸侯。故曰『用道治者不殺無罪，而罰不加於無辜』。唯大夫留心！」使者知胡亥之意，不聽蒙毅之言，遂殺之。

原文：

> 二世又遣使者之陽周，令蒙恬曰：「君之過多矣，而卿弟毅有大罪，法及內史。」恬曰：「自吾先人，及至子孫，積功信於秦三世矣。今臣將兵三十餘萬，身雖囚系，其勢足以倍畔，然自知必死而守義者，不敢辱先人之教，以不忘先主也。昔周成王初立，未離襁緥周公旦負王以朝，卒定天下。及成王有病甚殆，公旦自揃其爪以沈於河，曰：『王未有識，是旦執事。有罪殃，旦受其不祥。』乃書而藏之記府，可謂信矣。及王能治國，有賊臣言：『周公旦欲為亂久矣，王若不備，必有大事。』王乃大怒，周公旦走而奔於楚。成王觀於記府，得周公旦沈書，乃流涕曰：『孰謂周公旦欲為亂乎！』殺言之者而反周公旦。故《周書》曰『必參而伍之』。今恬之宗，世無二心，而事卒如此，是必孽臣逆亂，內陵之道也。夫成王失而復振則卒昌；桀殺關龍逢，紂殺王子比干而不悔，身死則國亡。臣故曰過可振而諫可覺也。察於參伍，上聖之法也。凡臣之言，非以求免於咎也，將以諫而死，願陛下為萬民思從道也。」使者曰：「臣受詔行法於將軍，不敢以將軍言聞於上也。」蒙恬喟然太息曰：「我何罪於天，無過而死乎？」良久，徐曰：「恬罪固當死矣。起臨洮屬之遼東，城塹萬餘里，此其中不能無絕地脈哉？此乃恬之罪也。」乃吞藥自殺。

下文：

> == 贊 ==
> 太史公曰：吾適北邊，自直道歸，行觀蒙恬所為秦筑長城亭障，塹山堙谷，通直道，固輕百姓力矣。夫秦之初滅諸侯，天下之心未定，痍傷者未瘳，而恬為名將，不以此時彊諫，振百姓之急，養老存孤，務修眾庶之和，而阿意興功，此其兄弟遇誅，不亦宜乎！何乃罪地脈哉？

</details>

<details><summary><code>SP-3BF160840AD337444F6D</code> · 史記/卷088/蒙恬:1385-1420</summary>

上文：

> 死情實。且夫順成全者，道之所貴也；刑殺者，道之所卒也。昔者秦穆公殺三良而死，罪百里奚而非其罪也，故立號曰『繆』。昭襄王殺武安君白起。楚平王殺伍奢。吳王夫差殺伍子胥。此四君者，皆為大失，而天下非之，以其君為不明，以是籍於諸侯。故曰『用道治者不殺無罪，而罰不加於無辜』。唯大夫留心！」使者知胡亥之意，不聽蒙毅之言，遂殺之。

原文：

> 二世又遣使者之陽周，令蒙恬曰：「君之過多矣，而卿弟毅有大罪，法及內史。

下文：

> 」恬曰：「自吾先人，及至子孫，積功信於秦三世矣。今臣將兵三十餘萬，身雖囚系，其勢足以倍畔，然自知必死而守義者，不敢辱先人之教，以不忘先主也。昔周成王初立，未離襁緥周公旦負王以朝，卒定天下。及成王有病甚殆，公旦自揃其爪以沈於河，曰：『王未有識，是旦執事。有罪殃，旦受其不祥。』乃書而藏之記府，可謂信矣。及王能治國，有賊臣言

</details>

<details><summary><code>SP-83823BFDF4F83A39A3FE</code> · 史記/卷088/蒙恬:1786-1888</summary>

上文：

> 旦沈書，乃流涕曰：『孰謂周公旦欲為亂乎！』殺言之者而反周公旦。故《周書》曰『必參而伍之』。今恬之宗，世無二心，而事卒如此，是必孽臣逆亂，內陵之道也。夫成王失而復振則卒昌；桀殺關龍逢，紂殺王子比干而不悔，身死則國亡。臣故曰過可振而諫可覺也。察於參伍，上聖之法也。凡臣之言，非以求免於咎也，將以諫而死，願陛下為萬民思從道也。

原文：

> 」使者曰：「臣受詔行法於將軍，不敢以將軍言聞於上也。」蒙恬喟然太息曰：「我何罪於天，無過而死乎？」良久，徐曰：「恬罪固當死矣。起臨洮屬之遼東，城塹萬餘里，此其中不能無絕地脈哉？此乃恬之罪也。」乃吞藥自殺。

下文：

> == 贊 ==
> 太史公曰：吾適北邊，自直道歸，行觀蒙恬所為秦筑長城亭障，塹山堙谷，通直道，固輕百姓力矣。夫秦之初滅諸侯，天下之心未定，痍傷者未瘳，而恬為名將，不以此時彊諫，振百姓之急，養老存孤，務修眾庶之和，而阿意興功，此其兄弟遇誅，不亦宜乎！何乃罪地脈哉？

</details>

### 右端内容

- Episode：`EP-A947F2A60CA184D91302`
- 人物：扶苏/蒙恬安全链|蒙恬
- 角色：["actor"]
- 行为：处置
- 责任：继位处置|蒙氏案件
- 责任族：`succession_governance`

#### Assertion evidence

- `K0-A-CLMK-144D3696FB99BAAFF29B@SP-9D72D2B07581645F020A`
  - 时间：胡亥立为太子后
  - 命题：胡亥 / 处置 / 蒙恬
  - 结果：蒙恬疑而复请，属吏更置
  - 摘要：蒙恬疑而复请，属吏更置
  - SourcePassage：`SP-9D72D2B07581645F020A`
- `K0-A-CLMK-6FD7BCBD233E76A3A3CA@SP-DDE12E1A1C857FE009D8`
  - 时间：始皇崩后、胡亥继位前后
  - 命题：胡亥 / 处置 / 蒙恬
  - 结果：蒙恬被囚于阳周
  - 摘要：蒙恬被囚于阳周
  - SourcePassage：`SP-DDE12E1A1C857FE009D8`

#### SourcePassage 原文与上下文

<details><summary><code>SP-9D72D2B07581645F020A</code> · 史記/卷088/蒙恬:654-728</summary>

上文：

> ，直抵甘泉，乃使蒙恬通道，自九原抵甘泉，塹山堙谷，千八百里。道未就。
> 始皇三十七年冬，行出游會稽，并海上，北走瑯邪。道病，使蒙毅還禱山川，未反。
> 始皇至沙丘崩，祕之，群臣莫知。是時丞相李斯、公子胡亥、中車府令趙高常從。高雅得幸於胡亥，欲立之，又怨蒙毅法治之而不為己也。因有賊心，乃與丞相李斯、公子胡亥陰謀，立胡亥為太子。

原文：

> 太子已立，遣使者以罪賜公子扶蘇、蒙恬死。扶蘇已死，蒙恬疑而復請之。使者以蒙恬屬吏，更置。胡亥以李斯舍人為護軍。使者還報，胡亥已聞扶蘇死，即欲釋蒙恬。

下文：

> 趙高恐蒙氏復貴而用事，怨之。
> 毅還至，趙高因為胡亥忠計，欲以滅蒙氏，乃言曰：「臣聞先帝欲舉賢立太子久矣，而毅諫曰『不可』。若知賢而俞弗立，則是不忠而惑主也。以臣愚意，不若誅之。」胡亥聽而系蒙毅於代。前已囚蒙恬於陽周。喪至咸陽，已葬，太子立為二世皇帝，而趙高親近，日夜毀惡蒙氏，求其罪過，舉劾之。
> 子嬰進諫曰：「臣聞故趙王

</details>

<details><summary><code>SP-DDE12E1A1C857FE009D8</code> · 史記/卷088/蒙恬:709-836</summary>

上文：

> 瑯邪。道病，使蒙毅還禱山川，未反。
> 始皇至沙丘崩，祕之，群臣莫知。是時丞相李斯、公子胡亥、中車府令趙高常從。高雅得幸於胡亥，欲立之，又怨蒙毅法治之而不為己也。因有賊心，乃與丞相李斯、公子胡亥陰謀，立胡亥為太子。太子已立，遣使者以罪賜公子扶蘇、蒙恬死。扶蘇已死，蒙恬疑而復請之。使者以蒙恬屬吏，更置。胡亥以李斯舍人為護軍。

原文：

> 使者還報，胡亥已聞扶蘇死，即欲釋蒙恬。趙高恐蒙氏復貴而用事，怨之。
> 毅還至，趙高因為胡亥忠計，欲以滅蒙氏，乃言曰：「臣聞先帝欲舉賢立太子久矣，而毅諫曰『不可』。若知賢而俞弗立，則是不忠而惑主也。以臣愚意，不若誅之。」胡亥聽而系蒙毅於代。前已囚蒙恬於陽周。

下文：

> 喪至咸陽，已葬，太子立為二世皇帝，而趙高親近，日夜毀惡蒙氏，求其罪過，舉劾之。
> 子嬰進諫曰：「臣聞故趙王遷殺其良臣李牧而用顏聚，燕王喜陰用荊軻之謀而倍秦之約，齊王建殺其故世忠臣而用后勝之議。此三君者，皆各以變古者失其國而殃及其身。今蒙氏，秦之大臣謀士也，而主欲一旦棄去之，臣竊以為不可。臣聞輕慮者不可以治國，獨智者不可以

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`、`K0-A-CLMK-A8AA0FC70AFDBC8CF32E@SP-3BF160840AD337444F6D`、`K0-A-CLMK-E98A9D0388EC3A8C142D@SP-0BAE005F4ACC6553731F`、`K0-A-CLMK-144D3696FB99BAAFF29B@SP-9D72D2B07581645F020A`、`K0-A-CLMK-6FD7BCBD233E76A3A3CA@SP-DDE12E1A1C857FE009D8`
- 理由：胡亥先赐蒙恬死并将其囚于阳周，后再遣使执行死令使蒙恬吞药自杀，属于同一处置链结果。

#### Reviewer B

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`、`K0-A-CLMK-144D3696FB99BAAFF29B@SP-9D72D2B07581645F020A`
- 理由：蒙恬先被赐死后改囚阳周，随后二世再遣使至阳周执行死命并导致其自杀，是同一处置的续行与结果。

---

## 28. `RBC-9A111C6811C05DC07FB0`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 2, "value": "萧瑀", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`explicit_causal`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-55CE65C6275D0EFB6900`
- 人物：萧瑀
- 角色：["actor"]
- 行为：处置
- 责任：河池郡守
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-CLMK-B0022EC5A6D8E05A7E99@SP-5215CAC03679EA364630`
  - 时间：炀帝又将伐辽东时
  - 命题：炀帝 / 处置 / 萧瑀
  - 结果：出为河池郡守，即日遣之
  - 摘要：出为河池郡守，即日遣之
  - SourcePassage：`SP-5215CAC03679EA364630`

#### SourcePassage 原文与上下文

<details><summary><code>SP-5215CAC03679EA364630</code> · 舊唐書/卷63/蕭瑀:2293-2352</summary>

上文：

> 帝女為妻，必恃大國之援。若發一單使以告義成，假使無益，事亦無損。臣又竊聽輿人之誦，乃慮陛下平突厥後更事遼東，所以人心不一，或致挫敗。請下明詔告軍中，赦高麗而專攻突厥，則百姓心安，人自為戰。」煬帝從之，於是發使詣可賀敦諭旨。俄而突厥解圍去，於後獲其諜人，云：義成公主遣使告急於始畢，稱北方有警，由是突厥解圍，蓋公主之助也。

原文：

> 煬帝又將伐遼東，謂群臣曰：「突厥狂悖為寇，勢何能為？以其少時未散，蕭瑀遂相恐動，情不可恕。」因出為河池郡守，即日遣之。

下文：

> 既至郡，有山賊萬餘人寇暴縱橫，瑀潛募勇敢之士，設奇而擊之，當陣而降其眾。所獲財畜，咸賞有功，由是人竭其力。薛舉遣眾數萬侵掠郡境，瑀要擊之，自後諸賊莫敢進，郡中復安。
> 高祖定京城，遣書招之。瑀以郡歸國，授光祿大夫，封宋國公，拜民部尚書。太宗為右元帥，攻洛陽，以瑀為府司馬。武德五年，遷內史令。時軍國草創，方隅未寧，高祖乃委

</details>

### 右端内容

- Episode：`EP-7ABDC8BD934074D76BE0`
- 人物：萧瑀
- 角色：["actor"]
- 行为：其他
- 责任：突厥军务
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-CLMK-60AD56D1E89743F59CED@SP-09DCE087FCF59BABCD20`
  - 时间：炀帝至雁门为突厥所围时
  - 命题：萧瑀 / 其他 / 雁门突厥围困
  - 结果：炀帝从之，突厥解围去
  - 摘要：炀帝从之，突厥解围去
  - SourcePassage：`SP-09DCE087FCF59BABCD20`

#### SourcePassage 原文与上下文

<details><summary><code>SP-09DCE087FCF59BABCD20</code> · 舊唐書/卷63/蕭瑀:2056-2293</summary>

上文：

> 授太子右千牛。及踐祚，遷尚衣奉御，檢校左翊衛鷹揚郎將。忽遇風疾，命家人不即醫療，仍云：「若天假餘年，因此望為棲遁之資耳。」蕭後聞而誨之：「以爾才智，足堪揚名顯親，豈得輕毀形骸而求隱逸？若以此致譴，則罪在不測。」病且愈，其姊勸勉之，故復有仕進志。累加銀青光祿大夫、內史侍郎。既以後弟之親，委之機務，後數以言忤旨，漸見疏斥。

原文：

> 煬帝至雁門，為突厥所圍，瑀進謀曰：「如聞始畢托校獵至此，義成公主初不知其有違背之心。且北蕃夷俗，可賀敦知兵馬事。昔漢高祖解平城之圍，乃是閼氏之力。況義成以帝女為妻，必恃大國之援。若發一單使以告義成，假使無益，事亦無損。臣又竊聽輿人之誦，乃慮陛下平突厥後更事遼東，所以人心不一，或致挫敗。請下明詔告軍中，赦高麗而專攻突厥，則百姓心安，人自為戰。」煬帝從之，於是發使詣可賀敦諭旨。俄而突厥解圍去，於後獲其諜人，云：義成公主遣使告急於始畢，稱北方有警，由是突厥解圍，蓋公主之助也。

下文：

> 煬帝又將伐遼東，謂群臣曰：「突厥狂悖為寇，勢何能為？以其少時未散，蕭瑀遂相恐動，情不可恕。」因出為河池郡守，即日遣之。既至郡，有山賊萬餘人寇暴縱橫，瑀潛募勇敢之士，設奇而擊之，當陣而降其眾。所獲財畜，咸賞有功，由是人竭其力。薛舉遣眾數萬侵掠郡境，瑀要擊之，自後諸賊莫敢進，郡中復安。
> 高祖定京城，遣書招之。瑀以郡歸國，授

</details>

### 双审结果

#### Reviewer A

- direct：`yes`
- coarse type：`explicit_causal`
- evidence refs：`K0-A-CLMK-B0022EC5A6D8E05A7E99@SP-5215CAC03679EA364630`、`K0-A-CLMK-60AD56D1E89743F59CED@SP-09DCE087FCF59BABCD20`
- 理由：萧瑀在雁门围困中主张重视突厥并获采纳，后炀帝明确以其曾使朝廷恐动为由将其外放河池，因果明示。

#### Reviewer B

- direct：`yes`
- coarse type：`explicit_causal`
- evidence refs：`K0-A-CLMK-B0022EC5A6D8E05A7E99@SP-5215CAC03679EA364630`、`K0-A-CLMK-60AD56D1E89743F59CED@SP-09DCE087FCF59BABCD20`
- 理由：萧瑀在雁门围困中主张专攻突厥并促成解围；后端处分证据明确以其对突厥形势造成恐动为由将其外放，形成直接缘由。

---

## 29. `RBC-AEAFE43BEBA2A3C32EFE`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 6, "value": "屈突通", "window_years": 10}]
- 最终处置：`proposed_distinct_unrelated`
- 最终 direct：`no`
- 最终 coarse type：`无`
- 是否经裁决：`no`

### 左端内容

- Episode：`EP-517D926EED646BAAD0D9`
- 人物：屈突通
- 角色：["actor"]
- 行为：战役
- 责任：关内讨捕
- 责任族：`military_command`

#### Assertion evidence

- `K0-A-CLMK-DC22FE2B5A6D223CA310@SP-367AAACDAF7B7F7487C0`
  - 时间：大业中
  - 命题：屈突通 / 战役 / 刘迦论
  - 结果：斩迦论并首级万馀，虏老弱数万口
  - 摘要：斩迦论并首级万馀，虏老弱数万口
  - SourcePassage：`SP-367AAACDAF7B7F7487C0`

#### SourcePassage 原文与上下文

<details><summary><code>SP-367AAACDAF7B7F7487C0</code> · 舊唐書/卷59/屈突通:530-707</summary>

上文：

> ，無所縱舍。時通弟蓋為長安令，亦以嚴整知名。時人為之語曰：「寧食三斗艾，不見屈突蓋，寧服三斗蔥，不逢屈突通。」為人所忌憚如此。及文帝崩，煬帝遣通以詔征漢王諒。先是，文帝與諒有密約曰：「若璽書召汝，於敕字之傍別加一點，又與玉麟符合者，當就征。」及發書無驗，諒覺變，詰通，通佔對無所屈，竟得歸長安。大業中，累轉左驍衛大將軍。

原文：

> 時秦、隴盜賊蜂起，以通為關內討捕大使。有安定人劉迦論舉兵反，據雕陰郡，僭號建元，署置百官，有眾十餘萬。稽胡首領劉鷂子聚眾與迦論相影響。通發關中兵擊之，師臨安定，初不與戰，軍中以通為怯，通乃揚聲旋師而潛入上郡。迦論不之覺，遂進兵南寇，去通七十里而舍，分兵掠諸城邑。通候其無備，簡精甲夜襲之，賊眾大潰，斬迦論並首級萬餘，於上郡南山築為京觀，虜男女數萬口而還。

下文：

> 煬帝幸江都，令通鎮長安。義兵起，代王遣通進屯河東。既而義師濟河，大破通將桑顯和於飲馬泉，永豐倉又為義師所克。通大懼，留鷹揚郎將堯君素守河東，將自武關趨藍田以赴長安。軍至潼關，為劉文靜所遏，不得進，相持月餘。通又令顯和夜襲文靜，詰朝大戰，義軍不利。顯和縱兵破二柵，惟文靜一柵獨存，顯和兵復入柵而戰者往覆數焉。文靜為流矢所

</details>

### 右端内容

- Episode：`EP-C80BF812C6A6F64B5026`
- 人物：屈突通
- 角色：["actor"]
- 行为：授权
- 责任：召汉王谅
- 责任族：`civil_governance`

#### Assertion evidence

- `K0-A-CLMK-4F75751CD9611A0DCBF9@SP-D5F9E6B319198D6CD4DC`
  - 时间：炀帝即位
  - 命题：隋炀帝 / 授权 / 屈突通
  - 结果：通占对无屈，竟得归长安
  - 摘要：通占对无屈，竟得归长安
  - SourcePassage：`SP-D5F9E6B319198D6CD4DC`

#### SourcePassage 原文与上下文

<details><summary><code>SP-D5F9E6B319198D6CD4DC</code> · 舊唐書/卷59/屈突通:433-517</summary>

上文：

> 叱之，通又頓首曰：「臣一身如死，望免千餘人命。」帝寤，曰：「朕之不明，以至於是。感卿此意，良用惻然。今從所請，以旌諫諍。」悉達等竟以減死論。由是漸見委信，擢為右武候車騎將軍。奉公正直，雖親戚犯法，無所縱舍。時通弟蓋為長安令，亦以嚴整知名。時人為之語曰：「寧食三斗艾，不見屈突蓋，寧服三斗蔥，不逢屈突通。」為人所忌憚如此。

原文：

> 及文帝崩，煬帝遣通以詔征漢王諒。先是，文帝與諒有密約曰：「若璽書召汝，於敕字之傍別加一點，又與玉麟符合者，當就征。」及發書無驗，諒覺變，詰通，通佔對無所屈，竟得歸長安。

下文：

> 大業中，累轉左驍衛大將軍。時秦、隴盜賊蜂起，以通為關內討捕大使。有安定人劉迦論舉兵反，據雕陰郡，僭號建元，署置百官，有眾十餘萬。稽胡首領劉鷂子聚眾與迦論相影響。通發關中兵擊之，師臨安定，初不與戰，軍中以通為怯，通乃揚聲旋師而潛入上郡。迦論不之覺，遂進兵南寇，去通七十里而舍，分兵掠諸城邑。通候其無備，簡精甲夜襲之，賊眾大

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-DC22FE2B5A6D223CA310@SP-367AAACDAF7B7F7487C0`、`K0-A-CLMK-4F75751CD9611A0DCBF9@SP-D5F9E6B319198D6CD4DC`
- 理由：屈突通奉诏征汉王谅与后来作为讨捕大使平定刘迦论分属不同任务，端点未显示直接承接。

#### Reviewer B

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-DC22FE2B5A6D223CA310@SP-367AAACDAF7B7F7487C0`、`K0-A-CLMK-4F75751CD9611A0DCBF9@SP-D5F9E6B319198D6CD4DC`
- 理由：屈突通奉诏召汉王谅与多年后担任关内讨捕大使击败刘迦论，是不同授权和行动，证据未建立直接承接。

---

## 30. `RBC-AED36A09908D78FD4401`

- 数据集：`g2_6k0_g2_6j_source_v2_development`
- blocking reasons：[{"blocking_signal": "shared_focal_temporal_window", "minimum_year_gap": 0, "value": "扶苏/蒙恬安全链|蒙恬", "window_years": 10}]
- 最终处置：`proposed_direct_relation`
- 最终 direct：`yes`
- 最终 coarse type：`explicit_causal`
- 是否经裁决：`yes`

### 左端内容

- Episode：`EP-5491FDEC222A3B9F2FB7`
- 人物：扶苏/蒙恬安全链|蒙恬
- 角色：["actor"]
- 行为：处置
- 责任：秦二世继位后对蒙氏处置
- 责任族：`succession_governance`

#### Assertion evidence

- `K0-A-CLMK-FA588C7DE67BDE4D8F4C@SP-E01CFE8DBD96CFA2A212`
  - 时间：二世时
  - 命题：胡亥使者 / 处置 / 蒙毅
  - 结果：蒙毅被杀
  - 摘要：蒙毅被杀
  - SourcePassage：`SP-E01CFE8DBD96CFA2A212`

#### SourcePassage 原文与上下文

<details><summary><code>SP-E01CFE8DBD96CFA2A212</code> · 史記/卷088/蒙恬:1364-1384</summary>

上文：

> 死也，為羞累先主之名，願大夫為慮焉，使臣得死情實。且夫順成全者，道之所貴也；刑殺者，道之所卒也。昔者秦穆公殺三良而死，罪百里奚而非其罪也，故立號曰『繆』。昭襄王殺武安君白起。楚平王殺伍奢。吳王夫差殺伍子胥。此四君者，皆為大失，而天下非之，以其君為不明，以是籍於諸侯。故曰『用道治者不殺無罪，而罰不加於無辜』。唯大夫留心！

原文：

> 」使者知胡亥之意，不聽蒙毅之言，遂殺之。

下文：

> 二世又遣使者之陽周，令蒙恬曰：「君之過多矣，而卿弟毅有大罪，法及內史。」恬曰：「自吾先人，及至子孫，積功信於秦三世矣。今臣將兵三十餘萬，身雖囚系，其勢足以倍畔，然自知必死而守義者，不敢辱先人之教，以不忘先主也。昔周成王初立，未離襁緥周公旦負王以朝，卒定天下。及成王有病甚殆，公旦自揃其爪以沈於河，曰：『王未有識，是旦執

</details>

### 右端内容

- Episode：`EP-5E0220496AB90354CD27`
- 人物：扶苏/蒙恬安全链|蒙恬
- 角色：["actor"]
- 行为：处置
- 责任：将军处置|蒙恬定罪赐死
- 责任族：`succession_governance`

#### Assertion evidence

- `K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`
  - 时间：二世时
  - 命题：二世使者 / 处置 / 蒙恬
  - 结果：蒙恬吞药自杀
  - 摘要：蒙恬吞药自杀
  - SourcePassage：`SP-83823BFDF4F83A39A3FE`
- `K0-A-CLMK-A8AA0FC70AFDBC8CF32E@SP-3BF160840AD337444F6D`
  - 时间：二世时
  - 命题：二世 / 处置 / 蒙恬
  - 结果：无
  - 摘要：无
  - SourcePassage：`SP-3BF160840AD337444F6D`
- `K0-A-CLMK-E98A9D0388EC3A8C142D@SP-0BAE005F4ACC6553731F`
  - 时间：二世时期
  - 命题：胡亥 / 处置 / 蒙恬
  - 结果：蒙恬吞药自杀
  - 摘要：蒙恬吞药自杀
  - SourcePassage：`SP-0BAE005F4ACC6553731F`

#### SourcePassage 原文与上下文

<details><summary><code>SP-0BAE005F4ACC6553731F</code> · 史記/卷088/蒙恬:1385-1888</summary>

上文：

> 死情實。且夫順成全者，道之所貴也；刑殺者，道之所卒也。昔者秦穆公殺三良而死，罪百里奚而非其罪也，故立號曰『繆』。昭襄王殺武安君白起。楚平王殺伍奢。吳王夫差殺伍子胥。此四君者，皆為大失，而天下非之，以其君為不明，以是籍於諸侯。故曰『用道治者不殺無罪，而罰不加於無辜』。唯大夫留心！」使者知胡亥之意，不聽蒙毅之言，遂殺之。

原文：

> 二世又遣使者之陽周，令蒙恬曰：「君之過多矣，而卿弟毅有大罪，法及內史。」恬曰：「自吾先人，及至子孫，積功信於秦三世矣。今臣將兵三十餘萬，身雖囚系，其勢足以倍畔，然自知必死而守義者，不敢辱先人之教，以不忘先主也。昔周成王初立，未離襁緥周公旦負王以朝，卒定天下。及成王有病甚殆，公旦自揃其爪以沈於河，曰：『王未有識，是旦執事。有罪殃，旦受其不祥。』乃書而藏之記府，可謂信矣。及王能治國，有賊臣言：『周公旦欲為亂久矣，王若不備，必有大事。』王乃大怒，周公旦走而奔於楚。成王觀於記府，得周公旦沈書，乃流涕曰：『孰謂周公旦欲為亂乎！』殺言之者而反周公旦。故《周書》曰『必參而伍之』。今恬之宗，世無二心，而事卒如此，是必孽臣逆亂，內陵之道也。夫成王失而復振則卒昌；桀殺關龍逢，紂殺王子比干而不悔，身死則國亡。臣故曰過可振而諫可覺也。察於參伍，上聖之法也。凡臣之言，非以求免於咎也，將以諫而死，願陛下為萬民思從道也。」使者曰：「臣受詔行法於將軍，不敢以將軍言聞於上也。」蒙恬喟然太息曰：「我何罪於天，無過而死乎？」良久，徐曰：「恬罪固當死矣。起臨洮屬之遼東，城塹萬餘里，此其中不能無絕地脈哉？此乃恬之罪也。」乃吞藥自殺。

下文：

> == 贊 ==
> 太史公曰：吾適北邊，自直道歸，行觀蒙恬所為秦筑長城亭障，塹山堙谷，通直道，固輕百姓力矣。夫秦之初滅諸侯，天下之心未定，痍傷者未瘳，而恬為名將，不以此時彊諫，振百姓之急，養老存孤，務修眾庶之和，而阿意興功，此其兄弟遇誅，不亦宜乎！何乃罪地脈哉？

</details>

<details><summary><code>SP-3BF160840AD337444F6D</code> · 史記/卷088/蒙恬:1385-1420</summary>

上文：

> 死情實。且夫順成全者，道之所貴也；刑殺者，道之所卒也。昔者秦穆公殺三良而死，罪百里奚而非其罪也，故立號曰『繆』。昭襄王殺武安君白起。楚平王殺伍奢。吳王夫差殺伍子胥。此四君者，皆為大失，而天下非之，以其君為不明，以是籍於諸侯。故曰『用道治者不殺無罪，而罰不加於無辜』。唯大夫留心！」使者知胡亥之意，不聽蒙毅之言，遂殺之。

原文：

> 二世又遣使者之陽周，令蒙恬曰：「君之過多矣，而卿弟毅有大罪，法及內史。

下文：

> 」恬曰：「自吾先人，及至子孫，積功信於秦三世矣。今臣將兵三十餘萬，身雖囚系，其勢足以倍畔，然自知必死而守義者，不敢辱先人之教，以不忘先主也。昔周成王初立，未離襁緥周公旦負王以朝，卒定天下。及成王有病甚殆，公旦自揃其爪以沈於河，曰：『王未有識，是旦執事。有罪殃，旦受其不祥。』乃書而藏之記府，可謂信矣。及王能治國，有賊臣言

</details>

<details><summary><code>SP-83823BFDF4F83A39A3FE</code> · 史記/卷088/蒙恬:1786-1888</summary>

上文：

> 旦沈書，乃流涕曰：『孰謂周公旦欲為亂乎！』殺言之者而反周公旦。故《周書》曰『必參而伍之』。今恬之宗，世無二心，而事卒如此，是必孽臣逆亂，內陵之道也。夫成王失而復振則卒昌；桀殺關龍逢，紂殺王子比干而不悔，身死則國亡。臣故曰過可振而諫可覺也。察於參伍，上聖之法也。凡臣之言，非以求免於咎也，將以諫而死，願陛下為萬民思從道也。

原文：

> 」使者曰：「臣受詔行法於將軍，不敢以將軍言聞於上也。」蒙恬喟然太息曰：「我何罪於天，無過而死乎？」良久，徐曰：「恬罪固當死矣。起臨洮屬之遼東，城塹萬餘里，此其中不能無絕地脈哉？此乃恬之罪也。」乃吞藥自殺。

下文：

> == 贊 ==
> 太史公曰：吾適北邊，自直道歸，行觀蒙恬所為秦筑長城亭障，塹山堙谷，通直道，固輕百姓力矣。夫秦之初滅諸侯，天下之心未定，痍傷者未瘳，而恬為名將，不以此時彊諫，振百姓之急，養老存孤，務修眾庶之和，而阿意興功，此其兄弟遇誅，不亦宜乎！何乃罪地脈哉？

</details>

### 双审结果

#### Reviewer A

- direct：`no`
- coarse type：`无`
- evidence refs：`K0-A-CLMK-FA588C7DE67BDE4D8F4C@SP-E01CFE8DBD96CFA2A212`、`K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`、`K0-A-CLMK-A8AA0FC70AFDBC8CF32E@SP-3BF160840AD337444F6D`、`K0-A-CLMK-E98A9D0388EC3A8C142D@SP-0BAE005F4ACC6553731F`
- 理由：蒙毅被杀与蒙恬被迫自杀虽属蒙氏受害背景，但两端是分别执行的处置，未表明彼此直接导致。

#### Reviewer B

- direct：`yes`
- coarse type：`mandate_or_outcome`
- evidence refs：`K0-A-CLMK-FA588C7DE67BDE4D8F4C@SP-E01CFE8DBD96CFA2A212`、`K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`
- 理由：蒙毅与蒙恬均在二世同一蒙氏处置链中被使者奉意杀死，且蒙恬死命明确援引其弟蒙毅之罪，属于同案处置结果。

### 第三方裁决结果

#### Adjudicator C

- direct：`yes`
- coarse type：`explicit_causal`
- evidence refs：`K0-A-CLMK-FA588C7DE67BDE4D8F4C@SP-E01CFE8DBD96CFA2A212`、`K0-A-CLMK-27A7BBD2ED0E5ABB96C8@SP-83823BFDF4F83A39A3FE`、`K0-A-CLMK-A8AA0FC70AFDBC8CF32E@SP-3BF160840AD337444F6D`、`K0-A-CLMK-E98A9D0388EC3A8C142D@SP-0BAE005F4ACC6553731F`
- 理由：左端蒙毅被杀后，右端对蒙恬的诏令紧接着明确以其弟蒙毅有大罪、依法牵连为处置依据，并最终导致蒙恬奉诏自杀，证据直接写明两端的因果连接。

---
