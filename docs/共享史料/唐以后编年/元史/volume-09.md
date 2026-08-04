# 《元史》卷009四域同读视图

- 任务：`YUAN-YUANSHI-009-MULTIDOMAIN`
- 状态：`shadow`
- 固定修订：`1812917`
- 输入指纹：`a09b0fe7273c46b73f3c583f58a6233ea8da8406d6625f8f50ef14c1016069dd`
- 共享事实：32
- 战役交接路由：7
- 财政民生路由：14
- 大型工程路由：5
- 政治事件路由：12
- 完整通读：完成（shadow；未写正式事实或评分）

## 战役交接

### CHF-YUANSHI-009-TANZHOU-HUNAN-SURRENDER

- 时间：至元十三年正月—至元十三年正月
- 地点：潭州、湖南
- 行动：元军攻克潭州，李芾全家自焚；阿里海牙招徕后湖南州郡旬日相继降。
- 结果：元朝取得湖南府一、州六、军二、县四十，户五十六万余。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-TANZHOU-1276`
- 引文：朔，克潭州，宋

### CHF-YUANSHI-009-LINAN-SURRENDER

- 时间：至元十三年正月至二月—至元十三年正月至二月
- 地点：臨安
- 行动：宋主献传国玉玺与降表，伯颜受降后进至临安，宋文武百司出城向行省报到。
- 结果：南宋临安政权正式投降。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-LINAN-SURRENDER-1276`
- 引文：齎傳國玉璽及降表

### CHF-YUANSHI-009-HUAIWEST-SURRENDER

- 时间：至元十三年二月—至元十三年二月
- 地点：淮西
- 行动：夏贵率淮西诸郡来降，镇巢军一度反叛后亦降，守将洪福被斩。
- 结果：元朝取得淮西府二、州六、军四、县三十四，户五十一万余。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-HUAIWEST-1276`
- 引文：夏貴以淮西諸郡來降

### CHF-YUANSHI-009-YANGZHOU-TAIZHOU-CAMPAIGN

- 时间：至元十三年五月至八月—至元十三年五月至八月
- 地点：揚州、泰州、瓜洲、丁村
- 行动：姜才多次攻击元军堡寨失利，李庭芝与姜才突围后被俘，扬泰相继降，二人于扬州被斩。
- 结果：淮东主力抵抗终结，元取得州十六、县三十三。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-HUAIDONG-1276`
- 引文：姜才攻灣頭堡

### CHF-YUANSHI-009-CHONGQING-FALL

- 时间：至元十四年二月—至元十四年二月
- 地点：重慶、涪州
- 行动：元军围攻重庆，赵安开城投降；张珏乘舟出逃被截获后投降。
- 结果：重庆长期抵抗终结。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-CHONGQING-1277`
- 引文：造梯衝將攻之

### CHF-YUANSHI-009-MINGUANG-GUANGXI-SURRENDERS

- 时间：至元十四年三月至四月—至元十四年三月至四月
- 地点：福建、廣東、廣西
- 行动：漳泉、建宁、广东广西诸州及溪洞大批归附，行省留用降官治原郡。
- 结果：闽广征服大体完成，部分统计达一百四十七溪洞、二十五万六千户。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-MINGUANG-1277`
- 引文：建漳、泉二郡

### CHF-YUANSHI-009-XILIEJI-REBELLION

- 时间：至元十四年七月—至元十四年七月
- 地点：阿力麻里、和林
- 行动：昔里吉劫北平王、拘安童并胁诸王叛乱，海都与东道诸王不从；伯颜奉命率军抵御。
- 结果：西道宗王叛乱爆发，部分诸王归元军。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-XILIEJI-REBELLION`
- 引文：昔里吉劫北平王

## 财政民生

### CHF-YUANSHI-009-YUNNAN-CURRENCY-LOCALIZATION

- 时间：至元十三年正月—至元十三年正月
- 地点：雲南
- 行动：赛典赤称云南不谙钞法，请保留交会、𧴩子公私通行，获准。
- 结果：云南货币制度按地方交易习惯调整。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-YUNNAN-CURRENCY-LOCALIZATION`
- 引文：鈔法實所未諳

### CHF-YUANSHI-009-SILK-TAX-RELIEF-1276

- 时间：至元十三年正月—至元十三年正月
- 地点：诸路
- 行动：至元七年新括协济合并户达二十万五千一百八十户，朝廷减当年丝赋一半。
- 结果：新增编户获得年度丝赋半免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-SILK-TAX-RELIEF-1276`
- 引文：新括協濟合併戶

### CHF-YUANSHI-009-LINAN-AMNESTY-PROTECTION

- 时间：至元十三年二月—至元十三年二月
- 地点：臨安及新附州县
- 行动：诏新附官民各守职业，赦归附前罪与抗拒逃亡者，免公私逋欠和部分山林河泊税，保护图书礼器古迹并救济鳏寡孤独。
- 结果：临安接收配套大赦、减负、文物保护与社会救济。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：等各守職業

### CHF-YUANSHI-009-CONFUCIAN-HOUSEHOLDS

- 时间：至元十三年三月—至元十三年三月
- 地点：诸路
- 行动：通文学儒户三千八百九十户免徭，富户借儒籍避役者还民籍，贫乏五百户隶太常寺。
- 结果：儒户待遇按学识和贫富重新分类。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-CONFUCIAN-HOUSEHOLDS`
- 引文：儒戶通文學者三千八百九十

### CHF-YUANSHI-009-SOLDIERS-RETURN-HOME

- 时间：至元十三年四月至六月—至元十三年四月至六月
- 地点：诸路
- 行动：侍卫亲军征戍已久者获准还家，约期六月归队；新附三卫老弱兵亦放还。
- 结果：长期服役和老弱军人获得阶段性复员。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-SOLDIERS-RETURN-HOME`
- 引文：征戍歲久，放令還家

### CHF-YUANSHI-009-RESTORE-SOUTHERN-PROPERTY-TAXES

- 时间：至元十三年十二月—至元十三年十二月
- 地点：江南新附诸路
- 行动：诏将军将强占的人口、田宅产业归还原籍原主，无主者给无产者；按实征田租商税等，废除宋代繁冗科差百余项。
- 结果：江南人口财产权复原、税目大幅清理。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-RESTORE-SOUTHERN-PROPERTY-TAXES`
- 引文：悉以人民歸之元籍州縣

### CHF-YUANSHI-009-YEAR13-RELIEF

- 时间：至元十三年—至元十三年
- 地点：東平、濟南、平陽、高麗瀋州等
- 行动：多地水旱缺食，全年赈米二十二万五千余石、粟四万七千余石、钞四千二百余锭，并免受灾地田租。
- 结果：军民站户获粮钞与税免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-YEAR13-RELIEF`
- 引文：賑軍民站戶米二十二萬五千五百六十石

### CHF-YUANSHI-009-JIANGNAN-TAX-RELIEF-1277

- 时间：至元十四年正月—至元十四年正月
- 地点：江南诸路
- 行动：因江南平定后百姓供军疲困，免当年丝银。
- 结果：新附江南获得普遍年度税免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-JIANGNAN-TAX-RELIEF-1277`
- 引文：江南平，百姓疲於供軍，免諸路今歲所納絲銀

### CHF-YUANSHI-009-YONGCHANG-POST-RELIEF

- 时间：至元十四年二月—至元十四年二月
- 地点：永昌路
- 行动：设山丹城等驿并给钞千锭取息供驿需；驿户因负担质押妻儿，朝廷另给钞赎回。
- 结果：驿站获得运营本金，一百二十户家属解除质押。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-YONGCHANG-POST-RELIEF`
- 引文：給鈔千錠為本

### CHF-YUANSHI-009-STOP-WINE-WASTE

- 时间：至元十四年三月—至元十四年三月
- 地点：天下
- 行动：因冬春少雨，翰林官建议节省浮费并禁酿酒、祈赛浪费，朝廷采纳。
- 结果：以节粮为目标的酒禁和祭祀费用限制启动。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-STOP-WINE-WASTE`
- 引文：足食之道，唯節浮費

### CHF-YUANSHI-009-RIVER-FISHING-RELIEF

- 时间：至元十四年五月—至元十四年五月
- 地点：河南、山東
- 行动：河南山东水旱，免除河泊课并允许民众自由捕鱼。
- 结果：灾民获得渔业生计与税免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-RIVER-FISHING-RELIEF`
- 引文：以河南、山東水旱，除河泊課，聽民自漁

### CHF-YUANSHI-009-YEAR14-PRICE-RELIEF

- 时间：至元十四年十二月—至元十四年十二月
- 地点：大都、冠州、永年
- 行动：大都物价上涨，发官粮一万石减价赈粜贫民；冠州永年水灾免田租。
- 结果：首都贫民获平价粮，灾区获税免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-YEAR14-PRICE-RELIEF`
- 引文：都物價翔踴

### CHF-YUANSHI-009-ELEVEN-TRADE-WAREHOUSES

- 时间：至元十三年正月—至元十三年正月
- 地点：诸路
- 行动：诸路设置十一所回易库，买卖币帛等物；大都和顾和买要求权豪与平民均摊。
- 结果：官营贸易网建立，并规定采购负担不许只落民户。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-ELEVEN-TRADE-WAREHOUSES`
- 引文：立回易庫于諸路，凡十有一

### CHF-YUANSHI-009-YEAR14-FAMINE-RELIEF

- 时间：至元十四年—至元十四年
- 地点：東平、濟南等
- 行动：多地饥荒，全年赈米二万一千六百余石、粟二万八千六百余石、钞一万零一百余锭。
- 结果：灾民获得粮钞救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-009-YEAR14-FAMINE-RELIEF`
- 引文：賑東平、濟南等郡饑民

## 大型工程

### CHF-YUANSHI-009-JIZHOU-CANAL

- 时间：至元十三年正月—至元十三年正月
- 地点：濟州
- 行动：开凿济州漕渠。
- 结果：济州新增漕运水道工程。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-009-JIZHOU-CANAL`
- 引文：穿濟州漕渠

### CHF-YUANSHI-009-WUQING-CANAL

- 时间：至元十三年七月至八月—至元十三年七月至八月
- 地点：楊村、孫家務、武清蒙村
- 行动：因原漕渠回远，改道孙家务并开武清蒙村漕渠。
- 结果：大都方向漕运线路调整缩短。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-009-WUQING-CANAL`
- 引文：漕渠洄遠，改從孫家務

### CHF-YUANSHI-009-YONGCHANG-POST-RELIEF

- 时间：至元十四年二月—至元十四年二月
- 地点：永昌路
- 行动：设山丹城等驿并给钞千锭取息供驿需；驿户因负担质押妻儿，朝廷另给钞赎回。
- 结果：驿站获得运营本金，一百二十户家属解除质押。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：給鈔千錠為本

### CHF-YUANSHI-009-REN-RIVER-RECLAMATION

- 时间：至元十四年十二月—至元十四年十二月
- 地点：任河
- 行动：疏导任河，恢复民田三千余顷。
- 结果：大规模农田重新可耕。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-009-REN-RIVER-RECLAMATION`
- 引文：導任河，復民田三千餘頃

### CHF-YUANSHI-009-CALENDAR-REFORM

- 时间：至元十三年六月—至元十三年六月
- 地点：大都
- 行动：因大明历渐差，命王恂与江南日官设局造新历，并召许衡参与商订。
- 结果：全国历法重修工程启动。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-009-CALENDAR-REFORM`
- 引文：大明曆浸差

## 政治事件

### CHF-YUANSHI-009-LINAN-SURRENDER

- 时间：至元十三年正月至二月—至元十三年正月至二月
- 地点：臨安
- 行动：宋主献传国玉玺与降表，伯颜受降后进至临安，宋文武百司出城向行省报到。
- 结果：南宋临安政权正式投降。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：齎傳國玉璽及降表

### CHF-YUANSHI-009-LINAN-MILITARY-DISCIPLINE

- 时间：至元十三年正月—至元十三年正月
- 地点：臨安
- 行动：伯颜禁止军士入城，违者军法处置，并张榜安抚军民按堵如故。
- 结果：临安入城前建立严格军纪与秩序保障。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-009-LINAN-MILITARY-DISCIPLINE`
- 引文：禁軍士入城

### CHF-YUANSHI-009-LINAN-ADMINISTRATIVE-TAKEOVER

- 时间：至元十三年二月—至元十三年二月
- 地点：臨安、兩浙
- 行动：行省核实钱谷仓库，收百官诰命符印，撤宋官府和禁军，改临安为两浙大都督府。
- 结果：宋中央行政、财政与军队被制度性接收。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-009-LINAN-ADMINISTRATIVE-TAKEOVER`
- 引文：取軍民錢穀之數

### CHF-YUANSHI-009-LINAN-AMNESTY-PROTECTION

- 时间：至元十三年二月—至元十三年二月
- 地点：臨安及新附州县
- 行动：诏新附官民各守职业，赦归附前罪与抗拒逃亡者，免公私逋欠和部分山林河泊税，保护图书礼器古迹并救济鳏寡孤独。
- 结果：临安接收配套大赦、减负、文物保护与社会救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-009-LINAN-AMNESTY-PROTECTION`
- 引文：等各守職業

### CHF-YUANSHI-009-SONG-CULTURAL-ASSET-TRANSFER

- 时间：至元十三年二月至三月—至元十三年二月至三月
- 地点：臨安、大都
- 行动：元军收取宋宫衮冕、符玺、图籍、车舆、礼乐器、国史院和秘书省文书，陆续运送。
- 结果：南宋国家礼制与知识资产转归元廷。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-009-SONG-CULTURAL-ASSET-TRANSFER`
- 引文：收宋國衮冕、圭璧、符璽

### CHF-YUANSHI-009-SONG-RULER-TRANSFER

- 时间：至元十三年三月至五月—至元十三年三月至五月
- 地点：臨安、上都
- 行动：宋主与太后离宫入觐，五月抵上都，被封瀛国公。
- 结果：宋幼主由亡国君转为元朝封爵臣属。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-009-SONG-RULER-TRANSFER`
- 引文：趣宋主㬎同太后入覲

### CHF-YUANSHI-009-PINGSONG-HISTORIES

- 时间：至元十三年六月—至元十三年六月
- 地点：翰林国史院
- 行动：下诏编纂《平金录》《平宋录》及诸国臣服传记，由耶律铸监修国史。
- 结果：统一战争与属国臣服被纳入官方史书工程。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-009-PINGSONG-HISTORIES`
- 引文：作平金、平宋錄

### CHF-YUANSHI-009-RESTORE-SOUTHERN-PROPERTY-TAXES

- 时间：至元十三年十二月—至元十三年十二月
- 地点：江南新附诸路
- 行动：诏将军将强占的人口、田宅产业归还原籍原主，无主者给无产者；按实征田租商税等，废除宋代繁冗科差百余项。
- 结果：江南人口财产权复原、税目大幅清理。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：悉以人民歸之元籍州縣

### CHF-YUANSHI-009-MINGUANG-GUANGXI-SURRENDERS

- 时间：至元十四年三月至四月—至元十四年三月至四月
- 地点：福建、廣東、廣西
- 行动：漳泉、建宁、广东广西诸州及溪洞大批归附，行省留用降官治原郡。
- 结果：闽广征服大体完成，部分统计达一百四十七溪洞、二十五万六千户。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：建漳、泉二郡

### CHF-YUANSHI-009-ROBBERY-DEATH-PENALTY-REVERSED

- 时间：至元十四年七月—至元十四年七月
- 地点：天下
- 行动：初令盗窃者一律处死，董文忠指出强盗窃盗与赃额不同，不宜一概，忽必烈立即停止。
- 结果：机械一律死刑未实施或被迅速撤回。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-009-ROBBERY-DEATH-PENALTY-REVERSED`
- 引文：犯盜者皆棄市

### CHF-YUANSHI-009-XILIEJI-REBELLION

- 时间：至元十四年七月—至元十四年七月
- 地点：阿力麻里、和林
- 行动：昔里吉劫北平王、拘安童并胁诸王叛乱，海都与东道诸王不从；伯颜奉命率军抵御。
- 结果：西道宗王叛乱爆发，部分诸王归元军。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：昔里吉劫北平王

### CHF-YUANSHI-009-SOUTHERN-GOVERNMENT-SETTLEMENT

- 时间：至元十三年十二月—至元十三年十二月
- 地点：江南诸路
- 行动：确定江南官府设置，设五道宣慰使并调整州路，同时检核新旧钱谷。
- 结果：征服区由军政接收转向常设行政和财政清查。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-009-SOUTHERN-GOVERNMENT-SETTLEMENT`
- 引文：定江南所設官府
