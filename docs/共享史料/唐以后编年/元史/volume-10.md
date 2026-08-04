# 《元史》卷010四域同读视图

- 任务：`YUAN-YUANSHI-010-MULTIDOMAIN`
- 状态：`shadow`
- 固定修订：`2307785`
- 输入指纹：`e46d0a0c6f7adeca4aa42b648cd34dfd6d35bcbf1aec168e9c1fa4002f5a5502`
- 共享事实：42
- 战役交接路由：8
- 财政民生路由：18
- 大型工程路由：7
- 政治事件路由：20
- 完整通读：完成（shadow；未写正式事实或评分）

## 战役交接

### CHF-YUANSHI-010-LUZHOU-FUZHOU-WAR

- 时间：至元十五年正月—至元十五年正月
- 地点：瀘州、涪州
- 行动：元军攻取泸州，并击败涪州宋军。
- 结果：四川宋军据点继续失守。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-SICHUAN-1278`
- 引文：等攻克瀘州，

### CHF-YUANSHI-010-CHA0ZHOU-CAPTURE

- 时间：至元十五年春—至元十五年春
- 地点：潮州、广东沿海
- 行动：元军继续沿海进兵并攻取潮州。
- 结果：广东残余抵抗据点被攻克。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-GUANGDONG-1278`
- 引文：唆都率師攻潮州，破之

### CHF-YUANSHI-010-SICHUAN-SURRENDERS-1278

- 时间：至元十五年春夏—至元十五年春夏
- 地点：四川、德慶、紹慶
- 行动：四川多地归附，元军又围攻德庆、绍庆等地。
- 结果：四川归附范围扩大但战事仍持续。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-SICHUAN-1278`
- 引文：寨，相繼來降

### CHF-YUANSHI-010-YUNNAN-CAMPAIGN-1278

- 时间：至元十五年六月—至元十五年六月
- 地点：雲南
- 行动：征调一万军进讨云南反抗势力，随后一百零九寨等大批归附。
- 结果：云南军事推进带来寨落集中投降。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-YUNNAN-1278`
- 引文：簽軍萬人進討

### CHF-YUANSHI-010-WENSHAN-BATTLE

- 时间：至元十五年十二月—至元十五年十二月
- 地点：文山
- 行动：张弘范军在文山击败宋军，俘文天祥。
- 结果：宋残余抵抗失去重要领袖。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-WENSHAN-1278`
- 引文：追及于五坡嶺麓中，大敗之

### CHF-YUANSHI-010-HESHAN-SURRENDER-JUSTICE

- 时间：至元十六年正月—至元十六年正月
- 地点：合山、四川
- 行动：合山归降后，官员误拟杀降将王立，忽必烈紧急制止并斥责视人命如戏，召王立入觐任用。
- 结果：降将免于错误处决并获任职。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-SICHUAN-SURRENDERS-1279`
- 引文：前遣使計殺立久矣，今追悔何及

### CHF-YUANSHI-010-YASHAN-BATTLE

- 时间：至元十六年二月—至元十六年二月
- 地点：厓山、海上
- 行动：元军进攻厓山宋军，宋广王昺与官属赴海死。
- 结果：南宋海上残余政权覆亡。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-YASHAN-1279`
- 引文：張弘範將兵追宋二王至崖山寨

### CHF-YUANSHI-010-JAPAN-WARSHIPS

- 时间：至元十六年春夏—至元十六年春夏
- 地点：江南诸省、高麗
- 行动：命有关省份制造征日本战船六百艘，并要求高丽备船。
- 结果：第二次日本远征开始积累舰船。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-JAPAN-EXPEDITION-PREPARATION-1279`
- 引文：造戰船六百艘

## 财政民生

### CHF-YUANSHI-010-XIJING-FAMINE

- 时间：至元十五年正月—至元十五年正月
- 地点：西京
- 行动：西京发生饥荒，朝廷发粟一万石赈济，并令阿合马广储粮备乏。
- 结果：灾区获得官粮，中央同时加强储备。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-XIJING-FAMINE`
- 引文：西京饑，發粟一萬石賑之

### CHF-YUANSHI-010-DALIANGPING-RELIEF

- 时间：至元十五年二月—至元十五年二月
- 地点：咸淳、大良平
- 行动：咸淳、大良平等处饥，朝廷赐钞千锭赈济。
- 结果：灾民获得货币救助。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-DALIANGPING-RELIEF`
- 引文：咸淳府等郡

### CHF-YUANSHI-010-SURRENDERED-SOLDIER-SETTLEMENT

- 时间：至元十五年四月—至元十五年四月
- 地点：新附诸路
- 行动：归附军士中强壮者按月给粮，老弱者给牛令屯田。
- 结果：降兵按体力分为继续服役和农业安置。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-SURRENDERED-SOLDIER-SETTLEMENT`
- 引文：月給錢糧；不

### CHF-YUANSHI-010-GENERAL-TAX-RELIEF-1278

- 时间：至元十五年五月—至元十五年五月
- 地点：诸路
- 行动：因各路年成不佳，免当年田租和丝银。
- 结果：受灾地区获得普遍赋税减免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-GENERAL-TAX-RELIEF-1278`
- 引文：免今年田租、絲銀

### CHF-YUANSHI-010-JIANGNAN-PACIFICATION-AUDIT

- 时间：至元十五年五月—至元十五年五月
- 地点：江南
- 行动：针对江南盗乱，命官员巡行安抚并核官吏、钱谷和灾伤，黜贪污者。
- 结果：平乱与行政财政监察并行。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：分道撫治軍民，檢覈錢穀

### CHF-YUANSHI-010-JIANGNAN-SALARY-OFFICIAL-FIELDS

- 时间：至元十五年八月—至元十五年八月
- 地点：江南
- 行动：核定江南官员俸禄与职田，并禁止官府额外科敛。
- 结果：地方官俸获得制度来源，百姓免受无理加征。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-JIANGNAN-SALARY-OFFICIAL-FIELDS`
- 引文：定江南俸祿職田

### CHF-YUANSHI-010-MILITARY-ROSTER-REDUCTION

- 时间：至元十五年八月至九月—至元十五年八月至九月
- 地点：诸路
- 行动：清查军籍，将老弱还民、强壮逃役者归军，并将至元九年所括三万军减半为民。
- 结果：军队规模与服役资格被重新调整。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-MILITARY-ROSTER-REDUCTION`
- 引文：分揀諸路所括軍

### CHF-YUANSHI-010-PROTECT-NEW-SUBJECT-PROPERTY

- 时间：至元十五年九月—至元十五年九月
- 地点：新附诸路
- 行动：禁止军民官占据民产、抑良为奴，并招海外商舶通商。
- 结果：新附民产权与人身身份获保护，海贸获得政策鼓励。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：務農樂業，軍民官毋得占據民產，抑良為奴

### CHF-YUANSHI-010-POOR-SALT-HOUSEHOLDS

- 时间：至元十五年十一月—至元十五年十一月
- 地点：盐司灶户
- 行动：发粟钞赈济贫困灶户。
- 结果：盐业生产户获得粮钞救助。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-POOR-SALT-HOUSEHOLDS`
- 引文：發粟鈔賑鹽司竈戶之貧者

### CHF-YUANSHI-010-YEAR15-DISASTER-RELIEF

- 时间：至元十五年—至元十五年
- 地点：诸路
- 行动：全年多地水旱，朝廷赈米八万余石、粟三万余石、钞二万余锭。
- 结果：灾区获得粮钞救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-YEAR15-DISASTER-RELIEF`
- 引文：賑米八萬八百九十石

### CHF-YUANSHI-010-HEXI-TUNTIAN

- 时间：至元十六年二月—至元十六年二月
- 地点：河西
- 行动：设置河西屯田并发给耕具。
- 结果：边地军农生产获得生产资料。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-HEXI-TUNTIAN`
- 引文：立河西屯田，給畊具

### CHF-YUANSHI-010-ANLETANG-SOLDIER-CARE

- 时间：至元十六年四月—至元十六年四月
- 地点：江南军队归途
- 行动：沿途每四五十里设安乐堂，医治、供粮归军病卒，死亡者就地藁葬。
- 结果：退归军人的医疗、口粮与殡葬获得制度安排。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-ANLETANG-SOLDIER-CARE`
- 引文：每四五十里立安樂堂

### CHF-YUANSHI-010-POST-HOUSEHOLD-CHILD-SALES

- 时间：至元十六年五月—至元十六年五月
- 地点：诸驿
- 行动：驿户因役重而质卖子女，朝廷命官员核查救济。
- 结果：驿役造成的家庭破产进入专项处置。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-POST-HOUSEHOLD-CHILD-SALES`
- 引文：有質賣子女以供役者

### CHF-YUANSHI-010-XIANGYANG-POST-LABOR

- 时间：至元十六年六月—至元十六年六月
- 地点：襄陽
- 行动：以襄阳屯田户四百代替军士承担驿役。
- 结果：驿役从军队转移给屯田户。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-XIANGYANG-POST-LABOR`
- 引文：以襄陽屯田戶四百代軍當驛役

### CHF-YUANSHI-010-SOUTHWEST-INCORPORATION

- 时间：至元十六年夏—至元十六年夏
- 地点：西南诸部
- 行动：招附西南三百余寨、十一万余户，设置赋税、驿站与护送制度。
- 结果：西南大批寨户被纳入行政和交通体系。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：招忙木、巨木禿等寨三百

### CHF-YUANSHI-010-STOP-CEREMONIAL-LEVIES

- 时间：至元十六年七月—至元十六年七月
- 地点：天下
- 行动：生日、元旦等礼仪费用原由百姓科敛，朝廷下诏罢除。
- 结果：民众免于礼仪性额外征收。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-STOP-CEREMONIAL-LEVIES`
- 引文：禮儀費用皆斂之民，詔天下罷之

### CHF-YUANSHI-010-TRANSPORT-OXEN-PROTECTED

- 时间：至元十六年秋—至元十六年秋
- 地点：诸路
- 行动：有司拟尽括民间车牛供运输，忽必烈以妨来年耕作为由制止。
- 结果：民间耕牛免于全面征用。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-010-TRANSPORT-OXEN-PROTECTED`
- 引文：民之艱苦汝等不問，但知役民

### CHF-YUANSHI-010-YEAR16-DISASTER-DEATH-SENTENCES

- 时间：至元十六年—至元十六年
- 地点：保定等二十余路
- 行动：全年二十余路遭水旱风雹害稼，朝廷记录灾情并断死罪一百三十二人。
- 结果：形成年度灾害与刑政汇总。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：保定等二十餘路水旱風雹害稼

## 大型工程

### CHF-YUANSHI-010-RUIYING-SPRING

- 时间：至元十五年正月—至元十五年正月
- 地点：金沙泉
- 行动：祭金沙泉后泉水复出，可灌田千亩，朝廷赐名瑞应泉。
- 结果：水源恢复并投入农业灌溉。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-010-RUIYING-SPRING`
- 引文：可溉田千畝

### CHF-YUANSHI-010-SICHUAN-WATER-POSTS

- 时间：至元十五年七月—至元十五年七月
- 地点：敍州、荊南府、烏蒙
- 行动：设置川蜀水驿，自叙州通达荆南，并开乌蒙驿路。
- 结果：四川与荆南、西南交通联络加强。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-010-SICHUAN-WATER-POSTS`
- 引文：立川蜀水驛，自敍州達荊南府

### CHF-YUANSHI-010-ASTRONOMY-OBSERVATORY-SURVEY

- 时间：至元十六年春—至元十六年春
- 地点：大都、上都、南海
- 行动：在大都建司天台制作仪器，郭守敬等自上都、大都向南海测验晷景。
- 结果：历法改革获得观测设施与跨地域数据。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-010-ASTRONOMY-OBSERVATORY-SURVEY`
- 引文：建司天臺于大都

### CHF-YUANSHI-010-JAPAN-WARSHIPS

- 时间：至元十六年春夏—至元十六年春夏
- 地点：江南诸省、高麗
- 行动：命有关省份制造征日本战船六百艘，并要求高丽备船。
- 结果：第二次日本远征开始积累舰船。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：造戰船六百艘

### CHF-YUANSHI-010-ANLETANG-SOLDIER-CARE

- 时间：至元十六年四月—至元十六年四月
- 地点：江南军队归途
- 行动：沿途每四五十里设安乐堂，医治、供粮归军病卒，死亡者就地藁葬。
- 结果：退归军人的医疗、口粮与殡葬获得制度安排。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：每四五十里立安樂堂

### CHF-YUANSHI-010-TONGZHOU-DREDGING

- 时间：至元十六年五月—至元十六年五月
- 地点：通州
- 行动：因通州水浅，动员五千军和雇工疏浚，五十日完工。
- 结果：漕运水道恢复通行条件。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-010-TONGZHOU-DREDGING`
- 引文：以五臺僧多

### CHF-YUANSHI-010-SOUTHWEST-INCORPORATION

- 时间：至元十六年夏—至元十六年夏
- 地点：西南诸部
- 行动：招附西南三百余寨、十一万余户，设置赋税、驿站与护送制度。
- 结果：西南大批寨户被纳入行政和交通体系。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：招忙木、巨木禿等寨三百

## 政治事件

### CHF-YUANSHI-010-SOUTHERN-WOMEN-FREED

- 时间：至元十五年正月—至元十五年正月
- 地点：江南
- 行动：禁止将新附良家妇女转卖娼家，惩治买卖者并恢复妇女良民身份。
- 结果：被掠卖妇女获得返良保护。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-SOUTHERN-WOMEN-FREED`
- 引文：直，人復為良

### CHF-YUANSHI-010-CENSORATE-FISCAL-ACCESS

- 时间：至元十五年二月—至元十五年二月
- 地点：中央
- 行动：阿合马请求限制御史台检核钱谷仓库事务。
- 结果：财政机构与监察权之间形成权限争议。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-CENSORATE-FISCAL-ACCESS`
- 引文：檢覈錢穀；察

### CHF-YUANSHI-010-MILITARY-DESERTION-ASSET-PENALTY

- 时间：至元十五年二月—至元十五年二月
- 地点：诸军
- 行动：军官不加抚恤、侵扰军士致逃亡者，没其家产之半。
- 结果：以财产罚约束军官虐兵。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-MILITARY-DESERTION-ASSET-PENALTY`
- 引文：擾致逃亡者

### CHF-YUANSHI-010-SOUTHERN-OFFICIAL-SCREENING

- 时间：至元十五年二月—至元十五年二月
- 地点：江南
- 行动：核选江南官员，裁撤冗员与不胜任者。
- 结果：新附地方官僚体系得到清理。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-SOUTHERN-OFFICIAL-SCREENING`
- 引文：選擇江南廉能之官

### CHF-YUANSHI-010-TAISHI-YUAN

- 时间：至元十五年三月—至元十五年三月
- 地点：大都
- 行动：设置太史院，任王恂、郭守敬等掌天文历法。
- 结果：天文历法形成专门中央机构。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-TAISHI-YUAN`
- 引文：之。置太史院

### CHF-YUANSHI-010-JIANGNAN-PACIFICATION-AUDIT

- 时间：至元十五年五月—至元十五年五月
- 地点：江南
- 行动：针对江南盗乱，命官员巡行安抚并核官吏、钱谷和灾伤，黜贪污者。
- 结果：平乱与行政财政监察并行。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-JIANGNAN-PACIFICATION-AUDIT`
- 引文：分道撫治軍民，檢覈錢穀

### CHF-YUANSHI-010-YUNNAN-CAMPAIGN-1278

- 时间：至元十五年六月—至元十五年六月
- 地点：雲南
- 行动：征调一万军进讨云南反抗势力，随后一百零九寨等大批归附。
- 结果：云南军事推进带来寨落集中投降。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：簽軍萬人進討

### CHF-YUANSHI-010-AHAMAT-NEPOTISM-PURGE

- 时间：至元十五年夏—至元十五年夏
- 地点：中央、江南
- 行动：因阿合马子弟与亲党占据要职，朝廷罢黜相关人员。
- 结果：财政权臣的亲属用人受到纠正。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-AHAMAT-NEPOTISM-PURGE`
- 引文：復阿合馬子

### CHF-YUANSHI-010-JIANGNAN-INSTITUTION-CONSOLIDATION

- 时间：至元十五年七月至九月—至元十五年七月至九月
- 地点：江南
- 行动：裁并江南行省、宣慰司等冗滥机构和官职，按民意决定政令兴废。
- 结果：新附地区行政层级与员额被压缩。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-JIANGNAN-INSTITUTION-CONSOLIDATION`
- 引文：凡小大政事，順民之心所欲者行之，所不欲者罷之

### CHF-YUANSHI-010-MILITARY-ROSTER-REDUCTION

- 时间：至元十五年八月至九月—至元十五年八月至九月
- 地点：诸路
- 行动：清查军籍，将老弱还民、强壮逃役者归军，并将至元九年所括三万军减半为民。
- 结果：军队规模与服役资格被重新调整。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：分揀諸路所括軍

### CHF-YUANSHI-010-PROTECT-NEW-SUBJECT-PROPERTY

- 时间：至元十五年九月—至元十五年九月
- 地点：新附诸路
- 行动：禁止军民官占据民产、抑良为奴，并招海外商舶通商。
- 结果：新附民产权与人身身份获保护，海贸获得政策鼓励。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-PROTECT-NEW-SUBJECT-PROPERTY`
- 引文：務農樂業，軍民官毋得占據民產，抑良為奴

### CHF-YUANSHI-010-TANGWUDAI-ROBBERY-PUNISHMENT

- 时间：至元十五年九月—至元十五年九月
- 地点：新附地区
- 行动：军将唐兀带等劫掠新附百姓，朝廷诛首恶并将所掠财物归还。
- 结果：军事掠夺受到刑罚和返还处理。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-TANGWUDAI-ROBBERY-PUNISHMENT`
- 引文：以所掠者還其民

### CHF-YUANSHI-010-CROWN-PRINCE-COREGENT

- 时间：至元十五年十月—至元十五年十月
- 地点：中央
- 行动：下诏皇太子燕王真金参与裁决朝政，大小政务先启后闻。
- 结果：皇太子取得制度化参政权。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-CROWN-PRINCE-COREGENT`
- 引文：下詔皇太子燕王參決朝政

### CHF-YUANSHI-010-HESHAN-SURRENDER-JUSTICE

- 时间：至元十六年正月—至元十六年正月
- 地点：合山、四川
- 行动：合山归降后，官员误拟杀降将王立，忽必烈紧急制止并斥责视人命如戏，召王立入觐任用。
- 结果：降将免于错误处决并获任职。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-HESHAN-SURRENDER-JUSTICE`
- 引文：前遣使計殺立久矣，今追悔何及

### CHF-YUANSHI-010-SICHUAN-FOUR-CIRCUITS

- 时间：至元十六年正月—至元十六年正月
- 地点：四川
- 行动：四川新设四道宣慰等行政区划。
- 结果：征服后的四川形成分区治理框架。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-SICHUAN-FOUR-CIRCUITS`
- 引文：川蜀為四道

### CHF-YUANSHI-010-YASHAN-BATTLE

- 时间：至元十六年二月—至元十六年二月
- 地点：厓山、海上
- 行动：元军进攻厓山宋军，宋广王昺与官属赴海死。
- 结果：南宋海上残余政权覆亡。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：張弘範將兵追宋二王至崖山寨

### CHF-YUANSHI-010-SOUTHWEST-INCORPORATION

- 时间：至元十六年夏—至元十六年夏
- 地点：西南诸部
- 行动：招附西南三百余寨、十一万余户，设置赋税、驿站与护送制度。
- 结果：西南大批寨户被纳入行政和交通体系。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-SOUTHWEST-INCORPORATION`
- 引文：招忙木、巨木禿等寨三百

### CHF-YUANSHI-010-MILITARY-LOOTING-EXECUTION

- 时间：至元十六年秋—至元十六年秋
- 地点：新附地区
- 行动：军官劫掠新附民，朝廷处死首犯并返还所掠。
- 结果：再次以死刑和返还约束征服军掠夺。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-MILITARY-LOOTING-EXECUTION`
- 引文：畏。」詔處死。壬

### CHF-YUANSHI-010-MILITARY-PRIVATE-LABOR-PENALTY

- 时间：至元十六年冬—至元十六年冬
- 地点：诸军
- 行动：规定军官私役军士者按人数多寡定罪。
- 结果：军士免受长官无限私人役使的制度保护。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-MILITARY-PRIVATE-LABOR-PENALTY`
- 引文：凡軍官私役軍士者，視數多寡定其罪

### CHF-YUANSHI-010-YEAR16-DISASTER-DEATH-SENTENCES

- 时间：至元十六年—至元十六年
- 地点：保定等二十余路
- 行动：全年二十余路遭水旱风雹害稼，朝廷记录灾情并断死罪一百三十二人。
- 结果：形成年度灾害与刑政汇总。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-010-YEAR16-DISASTER-DEATH-SENTENCES`
- 引文：保定等二十餘路水旱風雹害稼
